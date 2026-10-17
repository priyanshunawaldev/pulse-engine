import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.idempotency import IdempotencyRecord


class IdempotencyError(Exception):
    """Base exception for idempotency violations."""
    pass


class IdempotencyConflictError(IdempotencyError):
    """Raised when an operation with the same idempotency key is currently in progress."""
    pass


class IdempotencyPayloadMismatchError(IdempotencyError):
    """Raised when the same idempotency key is submitted with a different request payload."""
    pass


def compute_request_hash(payload: Any) -> str:
    """Compute a deterministic SHA-256 hash of the request payload."""
    if isinstance(payload, str):
        serialized = payload
    else:
        serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


async def check_or_create_idempotency(
    session: AsyncSession,
    idempotency_key: str,
    request_hash: str,
    ttl_hours: int = 24,
) -> tuple[IdempotencyRecord, bool]:
    """
    Checks if an idempotency record exists:
    - If COMPLETED: returns (record, True) [Cache Hit]
    - If PROCESSING: raises IdempotencyConflictError (409)
    - If hash mismatch: raises IdempotencyPayloadMismatchError (422)
    - If non-existent or expired: creates new record with status='PROCESSING' and returns (record, False)
    """
    now = datetime.now(UTC)
    stmt = select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == idempotency_key)
    result = await session.execute(stmt)
    record = result.scalar_one_or_none()

    if record is not None:
        # Check payload integrity
        if record.request_hash != request_hash:
            logger.warning(
                "idempotency_payload_mismatch",
                idempotency_key=idempotency_key,
                expected_hash=record.request_hash,
                received_hash=request_hash,
            )
            raise IdempotencyPayloadMismatchError(
                f"Idempotency key '{idempotency_key}' was previously used with a different request payload."
            )

        if record.status == "PROCESSING":
            logger.info("idempotency_concurrent_in_flight", idempotency_key=idempotency_key)
            raise IdempotencyConflictError(
                f"A request with idempotency key '{idempotency_key}' is currently being processed."
            )

        if record.status == "COMPLETED":
            logger.info("idempotency_cache_hit", idempotency_key=idempotency_key)
            return record, True

        # If previous attempt FAILED, allow re-processing by setting back to PROCESSING
        record.status = "PROCESSING"
        record.expires_at = now + timedelta(hours=ttl_hours)
        await session.flush()
        return record, False

    # Create new idempotency record
    new_record = IdempotencyRecord(
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        status="PROCESSING",
        expires_at=now + timedelta(hours=ttl_hours),
    )
    session.add(new_record)
    try:
        await session.flush()
        return new_record, False
    except IntegrityError:
        await session.rollback()
        raise IdempotencyConflictError(
            f"A request with idempotency key '{idempotency_key}' is currently being processed."
        )


async def complete_idempotency(
    session: AsyncSession,
    idempotency_key: str,
    status_code: int,
    response_body: dict[str, Any],
) -> None:
    """Store the final response for subsequent idempotent replay requests."""
    stmt = select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == idempotency_key)
    result = await session.execute(stmt)
    record = result.scalar_one_or_none()
    if record:
        record.status = "COMPLETED"
        record.response_status_code = status_code
        record.response_body = response_body
        await session.flush()


async def mark_idempotency_failed(
    session: AsyncSession,
    idempotency_key: str,
) -> None:
    """Mark idempotency record as FAILED so that clients can safely retry."""
    stmt = select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == idempotency_key)
    result = await session.execute(stmt)
    record = result.scalar_one_or_none()
    if record:
        record.status = "FAILED"
        await session.flush()
