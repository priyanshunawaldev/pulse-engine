from collections.abc import AsyncGenerator

from redis.asyncio import Redis, from_url

from app.core.config import settings

_redis_client: Redis | None = None


def get_redis() -> Redis:
    """Get or create singleton Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    """Close Redis client on shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


async def get_redis_dep() -> AsyncGenerator[Redis, None]:
    """FastAPI dependency for async Redis client."""
    client = get_redis()
    yield client
