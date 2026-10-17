import asyncio
import secrets
import uuid
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager

from redis.asyncio import Redis

from app.core.logging import logger

LUA_ACQUIRE_LOCK = """
if redis.call("set", KEYS[1], ARGV[1], "NX", "PX", ARGV[2]) then
    return 1
else
    return 0
end
"""

LUA_RELEASE_LOCK = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


class LockAcquisitionError(Exception):
    """Raised when a distributed lock cannot be acquired within timeout."""
    pass


class DistributedLock:
    """
    Redlock-compatible single-instance distributed lock with atomic Lua release.
    Guarantees only the token owner can release the lock (prevents unlocking after TTL expiry).
    """

    def __init__(
        self,
        redis: Redis,
        key: str,
        ttl_ms: int = 30_000,
        acquire_timeout_ms: int = 5_000,
        retry_delay_ms: int = 50,
    ):
        self._redis = redis
        self._key = f"lock:{key}"
        self._token = secrets.token_hex(32)
        self._ttl_ms = ttl_ms
        self._acquire_timeout_ms = acquire_timeout_ms
        self._retry_delay_ms = retry_delay_ms
        self._acquired = False

    async def acquire(self) -> bool:
        start_time = asyncio.get_event_loop().time()
        timeout_seconds = self._acquire_timeout_ms / 1000.0
        retry_seconds = self._retry_delay_ms / 1000.0

        while True:
            # Atomic set with NX and PX
            acquired = await self._redis.eval(
                LUA_ACQUIRE_LOCK,
                1,
                self._key,
                self._token,
                str(self._ttl_ms),
            )
            if acquired == 1:
                self._acquired = True
                return True

            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout_seconds:
                return False

            await asyncio.sleep(retry_seconds)

    async def release(self) -> bool:
        if not self._acquired:
            return False
        # Atomic release via Lua
        result = await self._redis.eval(
            LUA_RELEASE_LOCK,
            1,
            self._key,
            self._token,
        )
        self._acquired = False
        return bool(result == 1)

    async def __aenter__(self) -> "DistributedLock":
        acquired = await self.acquire()
        if not acquired:
            logger.error("lock_acquisition_failed", key=self._key)
            raise LockAcquisitionError(f"Could not acquire lock for {self._key} within timeout")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.release()


@asynccontextmanager
async def acquire_account_locks(
    redis: Redis,
    account_ids: Sequence[uuid.UUID],
    ttl_ms: int = 30_000,
) -> AsyncGenerator[list[DistributedLock], None]:
    """
    CRITICAL DISTRIBUTED SYSTEMS SAFETY PATTERN:
    Acquire locks on all accounts in ASCENDING UUID order.
    Ascending sort guarantees a strict global acquisition order, eliminating
    circular wait conditions (deadlocks) across concurrent workers.
    """
    # Deduplicate and sort accounts by UUID string in ascending order
    sorted_ids = sorted({str(a_id) for a_id in account_ids})
    locks: list[DistributedLock] = []

    try:
        for acc_id_str in sorted_ids:
            lock = DistributedLock(
                redis=redis,
                key=f"account:{acc_id_str}",
                ttl_ms=ttl_ms,
            )
            await lock.acquire()
            locks.append(lock)
        yield locks
    finally:
        # Release in reverse order of acquisition
        for lock in reversed(locks):
            try:
                await lock.release()
            except Exception as e:
                logger.warning("lock_release_failed", key=lock._key, error=str(e))
