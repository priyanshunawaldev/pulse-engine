import base64
import secrets
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import logger
from app.models.account import Account, AccountStatus
from app.models.transaction import LedgerEntry, Transaction, TransactionStatus
from app.schemas.account import (
    AccountCreateSchema,
    AccountListResponseSchema,
    AccountResponseSchema,
    LedgerEntryListResponseSchema,
    LedgerEntryResponseSchema,
)
from app.schemas.transaction import (
    EntryCreateSchema,
    TransactionCreateSchema,
    TransactionListResponseSchema,
    TransactionResponseSchema,
)
from app.services.idempotency_service import (
    check_or_create_idempotency,
    complete_idempotency,
    compute_request_hash,
    mark_idempotency_failed,
)
from app.services.lock_service import DistributedLock, acquire_account_locks


class LedgerError(Exception):
    """Base exception for ledger operations."""
    pass


class AccountNotFoundError(LedgerError):
    """Raised when an account ID does not exist."""
    pass


class AccountClosedError(LedgerError):
    """Raised when attempting an operation on a CLOSED or FROZEN account."""
    pass


class InsufficientFundsError(LedgerError):
    """Raised when debiting an account would result in a negative balance."""
    pass


class CurrencyMismatchError(LedgerError):
    """Raised when accounts in a transaction have different currencies."""
    pass


class DoubleEntryInvariantError(LedgerError):
    """Raised when sum(amount) across all entries in a transaction != 0."""
    pass


class TransactionNotFoundError(LedgerError):
    """Raised when transaction ID does not exist."""
    pass


class TransactionAlreadyReversedError(LedgerError):
    """Raised when attempting to reverse an already reversed or failed transaction."""
    pass


def encode_cursor(record_id: uuid.UUID) -> str:
    """Encode time-sortable UUIDv7 into base64 cursor."""
    return base64.urlsafe_b64encode(str(record_id).encode("utf-8")).decode("utf-8")


def decode_cursor(cursor: str) -> uuid.UUID:
    """Decode cursor string into UUIDv7."""
    raw = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
    if "|" in raw:
        raw = raw.split("|")[-1]
    return uuid.UUID(raw)


# ---------------------------------------------------------
# Account Management Service
# ---------------------------------------------------------

async def create_account(
    session: AsyncSession,
    payload: AccountCreateSchema,
) -> AccountResponseSchema:
    """Create a new financial ledger account with 0 or initial positive balance."""
    # Generate unique account number
    random_part = secrets.token_hex(6).upper()
    acc_num = f"ACC-{payload.currency.upper()}-{random_part}"

    account = Account(
        account_number=acc_num,
        owner_name=payload.owner_name,
        currency=payload.currency.upper(),
        initial_balance=payload.initial_balance,
        balance=payload.initial_balance,
        status=AccountStatus.ACTIVE,
    )
    session.add(account)
    await session.commit()
    await session.refresh(account)

    logger.info("account_created", account_id=str(account.id), account_number=acc_num, balance=str(account.balance))
    return AccountResponseSchema.model_validate(account)


async def get_account(
    session: AsyncSession,
    account_id: uuid.UUID,
) -> AccountResponseSchema:
    """Fetch an account by UUID."""
    stmt = select(Account).where(Account.id == account_id)
    result = await session.execute(stmt)
    account = result.scalar_one_or_none()
    if not account:
        raise AccountNotFoundError(f"Account with ID '{account_id}' was not found.")
    return AccountResponseSchema.model_validate(account)


async def list_accounts(
    session: AsyncSession,
    limit: int = 20,
    cursor: str | None = None,
) -> AccountListResponseSchema:
    """List accounts using UUIDv7 cursor-based pagination."""
    stmt = select(Account).order_by(Account.id.desc()).limit(limit + 1)

    if cursor:
        cursor_id = decode_cursor(cursor)
        stmt = stmt.where(Account.id < cursor_id)

    result = await session.execute(stmt)
    accounts = list(result.scalars().all())

    has_more = len(accounts) > limit
    items = accounts[:limit]

    next_cursor = None
    if has_more and items:
        next_cursor = encode_cursor(items[-1].id)

    return AccountListResponseSchema(
        items=[AccountResponseSchema.model_validate(a) for a in items],
        next_cursor=next_cursor,
        has_more=has_more,
    )


async def close_account(
    session: AsyncSession,
    account_id: uuid.UUID,
) -> AccountResponseSchema:
    """Soft-close an account. Audit trail is strictly preserved."""
    stmt = select(Account).where(Account.id == account_id)
    result = await session.execute(stmt)
    account = result.scalar_one_or_none()
    if not account:
        raise AccountNotFoundError(f"Account with ID '{account_id}' was not found.")

    account.status = AccountStatus.CLOSED
    await session.commit()
    await session.refresh(account)

    logger.info("account_closed", account_id=str(account.id))
    return AccountResponseSchema.model_validate(account)


async def list_account_ledger(
    session: AsyncSession,
    account_id: uuid.UUID,
    limit: int = 50,
    cursor: str | None = None,
) -> LedgerEntryListResponseSchema:
    """Get paginated ledger audit trail for a specific account using UUIDv7 cursor."""
    stmt = (
        select(LedgerEntry)
        .where(LedgerEntry.account_id == account_id)
        .order_by(LedgerEntry.id.desc())
        .limit(limit + 1)
    )

    if cursor:
        cursor_id = decode_cursor(cursor)
        stmt = stmt.where(LedgerEntry.id < cursor_id)

    result = await session.execute(stmt)
    entries = list(result.scalars().all())

    has_more = len(entries) > limit
    items = entries[:limit]

    next_cursor = None
    if has_more and items:
        next_cursor = encode_cursor(items[-1].id)

    return LedgerEntryListResponseSchema(
        items=[LedgerEntryResponseSchema.model_validate(e) for e in items],
        next_cursor=next_cursor,
        has_more=has_more,
    )


# ---------------------------------------------------------
# Double-Entry Transaction Service
# ---------------------------------------------------------

async def post_transaction(
    session: AsyncSession,
    redis: Redis,
    payload: TransactionCreateSchema,
) -> tuple[TransactionResponseSchema, bool]:
    """
    Executes a strict double-entry ledger transaction:
    1. Idempotency verification and lock.
    2. Redis distributed lock acquisition in ASCENDING account UUID order.
    3. Multi-currency and account status validation.
    4. Balance check and non-negative invariant validation.
    5. Atomic row updates with optimistic concurrency check.
    6. Double-entry entries insertion with running balance snapshots.
    7. Celery webhook trigger dispatch.
    Returns (TransactionResponseSchema, was_cached).
    """
    request_hash = compute_request_hash(payload.model_dump(mode="json"))

    # Step 1: Idempotency Check
    record, is_cached = await check_or_create_idempotency(
        session=session,
        idempotency_key=payload.idempotency_key,
        request_hash=request_hash,
    )
    if is_cached and record.response_body:
        return TransactionResponseSchema.model_validate(record.response_body), True

    account_ids = [entry.account_id for entry in payload.entries]
    if len(set(account_ids)) < 2:
        raise DoubleEntryInvariantError(
            "Transaction must involve at least two distinct accounts to preserve double-entry integrity."
        )

    try:
        # Step 2: Acquire Distributed Locks in Ascending Order
        async with acquire_account_locks(redis, account_ids):
            # Step 3: Fetch all involved accounts with row locking in ascending UUID order (Vibe Block 07)
            dialect_name = session.bind.dialect.name if session.bind else ""
            stmt = select(Account).where(Account.id.in_(account_ids)).order_by(Account.id)
            if dialect_name == "postgresql":
                stmt = stmt.with_for_update()

            result = await session.execute(stmt)
            accounts_list = list(result.scalars().all())
            accounts_by_id = {acc.id: acc for acc in accounts_list}

            # Verify all accounts exist
            for a_id in account_ids:
                if a_id not in accounts_by_id:
                    raise AccountNotFoundError(f"Account ID '{a_id}' does not exist.")

            # Verify all accounts are active
            for acc in accounts_by_id.values():
                if acc.status != AccountStatus.ACTIVE:
                    raise AccountClosedError(
                        f"Account '{acc.account_number}' is {acc.status.value}; transactions are prohibited."
                    )

            # Verify multi-currency integrity: all accounts must share the same currency
            currencies = {acc.currency for acc in accounts_by_id.values()}
            if len(currencies) > 1:
                raise CurrencyMismatchError(
                    f"Cross-currency transaction rejected. Involved currencies: {currencies}"
                )

            # Step 4: Verify Double-Entry Invariant (sum == 0)
            total_sum = sum((entry.amount for entry in payload.entries), Decimal("0.0000"))
            if total_sum != Decimal("0.0000"):
                raise DoubleEntryInvariantError(
                    f"Double-entry violation: entry sum equals {total_sum}, required 0.0000"
                )

            # Step 5: Check Debits & Calculate New Balances
            deltas: dict[uuid.UUID, Decimal] = {}
            for entry in payload.entries:
                deltas[entry.account_id] = deltas.get(entry.account_id, Decimal("0.0000")) + entry.amount

            for a_id, delta in deltas.items():
                acc = accounts_by_id[a_id]
                new_bal = acc.balance + delta
                if new_bal < Decimal("0.0000"):
                    raise InsufficientFundsError(
                        f"Account '{acc.account_number}' has insufficient funds. Balance: {acc.balance}, Debit: {-delta}"
                    )

            # Step 6: Create Transaction and Ledger Entries with Running Balances
            tx = Transaction(
                idempotency_key=payload.idempotency_key,
                description=payload.description,
                status=TransactionStatus.COMPLETED,
                metadata_=payload.metadata,
            )
            session.add(tx)
            await session.flush()

            created_entries: list[LedgerEntry] = []
            running_balances: dict[uuid.UUID, Decimal] = {acc.id: acc.balance for acc in accounts_by_id.values()}

            for entry_data in payload.entries:
                current_bal = running_balances[entry_data.account_id]
                new_bal = current_bal + entry_data.amount
                if new_bal < Decimal("0.0000"):
                    raise InsufficientFundsError(
                        f"Account '{accounts_by_id[entry_data.account_id].account_number}' balance cannot dip below zero during transaction execution."
                    )
                running_balances[entry_data.account_id] = new_bal

                entry = LedgerEntry(
                    transaction_id=tx.id,
                    account_id=entry_data.account_id,
                    amount=entry_data.amount,
                    entry_type=entry_data.entry_type,
                    running_balance=new_bal,
                )
                session.add(entry)
                created_entries.append(entry)

            # Flush to database so entry.id and entry.created_at are generated
            await session.flush()

            # Update Account snapshot balances (version is automatically managed via version_id_col for OCC)
            for a_id, final_bal in running_balances.items():
                acc = accounts_by_id[a_id]
                acc.balance = final_bal

            # Prepare response object
            response_schema = TransactionResponseSchema(
                id=tx.id,
                idempotency_key=tx.idempotency_key,
                description=tx.description,
                status=tx.status,
                metadata=tx.metadata_,
                created_at=tx.created_at or datetime.now(UTC),
                entries=[LedgerEntryResponseSchema.model_validate(e) for e in created_entries],
            )

            # Save to idempotency store
            await complete_idempotency(
                session=session,
                idempotency_key=payload.idempotency_key,
                status_code=200,
                response_body=response_schema.model_dump(mode="json"),
            )

            await session.commit()
            logger.info("transaction_completed", transaction_id=str(tx.id), idempotency_key=tx.idempotency_key)

            # Trigger async webhooks post-commit
            try:
                from app.workers.tasks import (
                    _trigger_webhooks_for_transaction_async,
                    dispatch_webhook,
                )
                delivery_ids = await _trigger_webhooks_for_transaction_async(
                    str(tx.id), [str(aid) for aid in account_ids], "transaction.completed", session=session
                )
                for d_id in delivery_ids:
                    try:
                        dispatch_webhook.delay(d_id)
                    except Exception:
                        pass
            except Exception as w_exc:
                logger.warning("webhook_dispatch_skipped", error=str(w_exc))

            return response_schema, False

    except Exception as exc:
        await session.rollback()
        await mark_idempotency_failed(session, payload.idempotency_key)
        await session.commit()
        raise exc


async def get_transaction(
    session: AsyncSession,
    transaction_id: uuid.UUID,
) -> TransactionResponseSchema:
    """Fetch a transaction with all ledger entries."""
    stmt = (
        select(Transaction)
        .options(selectinload(Transaction.entries))
        .where(Transaction.id == transaction_id)
    )
    result = await session.execute(stmt)
    tx = result.scalar_one_or_none()
    if not tx:
        raise TransactionNotFoundError(f"Transaction ID '{transaction_id}' was not found.")

    return TransactionResponseSchema(
        id=tx.id,
        idempotency_key=tx.idempotency_key,
        description=tx.description,
        status=tx.status,
        metadata=tx.metadata_,
        created_at=tx.created_at,
        entries=[LedgerEntryResponseSchema.model_validate(e) for e in tx.entries],
    )


async def list_transactions(
    session: AsyncSession,
    limit: int = 20,
    cursor: str | None = None,
) -> TransactionListResponseSchema:
    """List transactions using UUIDv7 cursor-based pagination."""
    stmt = (
        select(Transaction)
        .options(selectinload(Transaction.entries))
        .order_by(Transaction.id.desc())
        .limit(limit + 1)
    )

    if cursor:
        cursor_id = decode_cursor(cursor)
        stmt = stmt.where(Transaction.id < cursor_id)

    result = await session.execute(stmt)
    txs = list(result.scalars().all())

    has_more = len(txs) > limit
    items = txs[:limit]

    next_cursor = None
    if has_more and items:
        next_cursor = encode_cursor(items[-1].id)

    return TransactionListResponseSchema(
        items=[
            TransactionResponseSchema(
                id=tx.id,
                idempotency_key=tx.idempotency_key,
                description=tx.description,
                status=tx.status,
                metadata=tx.metadata_,
                created_at=tx.created_at,
                entries=[LedgerEntryResponseSchema.model_validate(e) for e in tx.entries],
            )
            for tx in items
        ],
        next_cursor=next_cursor,
        has_more=has_more,
    )


async def reverse_transaction(
    session: AsyncSession,
    redis: Redis,
    transaction_id: uuid.UUID,
    idempotency_key: str | None = None,
) -> TransactionResponseSchema:
    """
    Reverse a completed transaction by generating an exact equal and opposite mirror transaction.
    Guarded by a distributed lock on the transaction ID to eliminate concurrent double-reversals.
    """
    async with DistributedLock(redis, f"reversal:{transaction_id}"):
        stmt = (
            select(Transaction)
            .options(selectinload(Transaction.entries))
            .where(Transaction.id == transaction_id)
        )
        result = await session.execute(stmt)
        original_tx = result.scalar_one_or_none()

        if not original_tx:
            raise TransactionNotFoundError(f"Transaction '{transaction_id}' was not found.")

        if original_tx.status == TransactionStatus.REVERSED:
            raise TransactionAlreadyReversedError(f"Transaction '{transaction_id}' has already been reversed.")

        if original_tx.status != TransactionStatus.COMPLETED:
            raise TransactionAlreadyReversedError(
                f"Cannot reverse transaction '{transaction_id}' with status {original_tx.status.value}."
            )

        # Invert all entries to construct mirror transaction
        reversal_entries: list[EntryCreateSchema] = []
        for entry in original_tx.entries:
            inverted_amount = -entry.amount
            inverted_type = "CREDIT" if inverted_amount > Decimal("0") else "DEBIT"
            reversal_entries.append(
                EntryCreateSchema(
                    account_id=entry.account_id,
                    amount=inverted_amount,
                    entry_type=inverted_type,
                )
            )

        rev_key = idempotency_key or f"rev_{original_tx.id}_{secrets.token_hex(4)}"
        reversal_payload = TransactionCreateSchema(
            idempotency_key=rev_key,
            description=f"Reversal of Transaction {original_tx.id}",
            entries=reversal_entries,
            metadata={"original_transaction_id": str(original_tx.id)},
        )

        reversal_resp, _ = await post_transaction(
            session=session,
            redis=redis,
            payload=reversal_payload,
        )

        # Re-fetch and mark original transaction as REVERSED
        stmt = select(Transaction).where(Transaction.id == transaction_id)
        result = await session.execute(stmt)
        tx_to_update = result.scalar_one_or_none()
        if tx_to_update:
            tx_to_update.status = TransactionStatus.REVERSED
            await session.commit()

        logger.info(
            "transaction_reversed",
            original_transaction_id=str(transaction_id),
            reversal_id=str(reversal_resp.id),
        )

        return reversal_resp
