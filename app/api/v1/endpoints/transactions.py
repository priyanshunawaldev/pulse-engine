import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.api.deps import AuthContext, get_current_auth, get_db, get_redis_dep
from app.schemas.transaction import (
    TransactionCreateSchema,
    TransactionListResponseSchema,
    TransactionResponseSchema,
)
from app.services.idempotency_service import (
    IdempotencyConflictError,
    IdempotencyPayloadMismatchError,
)
from app.services.ledger_service import (
    AccountClosedError,
    AccountNotFoundError,
    CurrencyMismatchError,
    DoubleEntryInvariantError,
    InsufficientFundsError,
    TransactionAlreadyReversedError,
    TransactionNotFoundError,
    get_transaction,
    list_transactions,
    post_transaction,
    reverse_transaction,
)
from app.services.lock_service import LockAcquisitionError

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("", response_model=TransactionResponseSchema, summary="Post a double-entry ledger transaction")
async def create_transaction(
    payload: TransactionCreateSchema,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_dep),
    auth: AuthContext = Depends(get_current_auth),
) -> TransactionResponseSchema:
    """
    Post an atomic, balanced double-entry transaction.
    Enforces idempotency, deadlock-free distributed locking, and balance non-negative constraints.
    """
    try:
        response, _ = await post_transaction(
            session=session,
            redis=redis,
            payload=payload,
        )
        return response
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except AccountClosedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except InsufficientFundsError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    except (CurrencyMismatchError, DoubleEntryInvariantError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    except IdempotencyPayloadMismatchError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except StaleDataError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CONCURRENT_VERSION_CONFLICT")
    except LockAcquisitionError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@router.get("", response_model=TransactionListResponseSchema, summary="List transactions")
async def get_transactions_list(
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_current_auth),
) -> TransactionListResponseSchema:
    """List transactions with cursor pagination."""
    return await list_transactions(session, limit=limit, cursor=cursor)


@router.get("/{transaction_id}", response_model=TransactionResponseSchema, summary="Get transaction details")
async def get_single_transaction(
    transaction_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_current_auth),
) -> TransactionResponseSchema:
    """Fetch transaction details along with all balanced ledger entries."""
    try:
        return await get_transaction(session, transaction_id)
    except TransactionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{transaction_id}/reverse", response_model=TransactionResponseSchema, summary="Reverse a transaction")
async def reverse_existing_transaction(
    transaction_id: uuid.UUID,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_dep),
    auth: AuthContext = Depends(get_current_auth),
) -> TransactionResponseSchema:
    """
    Reverse a completed transaction.
    Creates equal and opposite ledger entries (debit -> credit, credit -> debit) and marks original as REVERSED.
    """
    try:
        return await reverse_transaction(
            session=session,
            redis=redis,
            transaction_id=transaction_id,
            idempotency_key=idempotency_key,
        )
    except TransactionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (TransactionAlreadyReversedError, AccountClosedError, IdempotencyConflictError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except StaleDataError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CONCURRENT_VERSION_CONFLICT")
    except (InsufficientFundsError, CurrencyMismatchError, DoubleEntryInvariantError, IdempotencyPayloadMismatchError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    except LockAcquisitionError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
