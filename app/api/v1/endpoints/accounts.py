import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_current_auth, get_db
from app.schemas.account import (
    AccountCreateSchema,
    AccountListResponseSchema,
    AccountResponseSchema,
    LedgerEntryListResponseSchema,
)
from app.services.ledger_service import (
    AccountNotFoundError,
    close_account,
    create_account,
    get_account,
    list_account_ledger,
    list_accounts,
)

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.post("", response_model=AccountResponseSchema, status_code=status.HTTP_201_CREATED, summary="Create an account")
async def create_new_account(
    payload: AccountCreateSchema,
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_current_auth),
) -> AccountResponseSchema:
    """Create a new ledger account."""
    return await create_account(session, payload)


@router.get("", response_model=AccountListResponseSchema, summary="List accounts")
async def get_accounts_list(
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_current_auth),
) -> AccountListResponseSchema:
    """List accounts using cursor-based pagination."""
    return await list_accounts(session, limit=limit, cursor=cursor)


@router.get("/{account_id}", response_model=AccountResponseSchema, summary="Get account details & balance")
async def get_single_account(
    account_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_current_auth),
) -> AccountResponseSchema:
    """Fetch an account by UUID including current balance snapshot."""
    try:
        return await get_account(session, account_id)
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/{account_id}/close", response_model=AccountResponseSchema, summary="Soft-close account")
async def close_existing_account(
    account_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_current_auth),
) -> AccountResponseSchema:
    """Soft-close an account. Closed accounts cannot post or receive transactions."""
    try:
        return await close_account(session, account_id)
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/{account_id}/ledger", response_model=LedgerEntryListResponseSchema, summary="Get account ledger history")
async def get_account_ledger_history(
    account_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_current_auth),
) -> LedgerEntryListResponseSchema:
    """Get chronological paginated ledger audit trail of entries and running balances."""
    # Verify account exists first
    try:
        await get_account(session, account_id)
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return await list_account_ledger(session, account_id, limit=limit, cursor=cursor)
