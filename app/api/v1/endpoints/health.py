from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_redis_dep

router = APIRouter()


@router.get("/health/live", summary="Liveness probe")
async def health_live() -> dict[str, str]:
    """Kubernetes / Docker liveness probe: returns 200 if server process is running."""
    return {"status": "ok", "app": settings.APP_NAME, "environment": settings.APP_ENV}


@router.get("/health/ready", summary="Readiness probe")
async def health_ready(
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_dep),
) -> dict[str, str]:
    """
    Readiness probe: verifies downstream connectivity to PostgreSQL and Redis.
    Returns 503 if any required subsystem is unreachable.
    """
    health_status = {"status": "ok", "postgres": "unknown", "redis": "unknown"}

    # 1. Check PostgreSQL
    try:
        await session.execute(text("SELECT 1"))
        health_status["postgres"] = "ok"
    except Exception as exc:
        health_status["postgres"] = f"error: {exc}"
        health_status["status"] = "degraded"

    # 2. Check Redis
    try:
        pong = await redis.ping()
        if pong:
            health_status["redis"] = "ok"
    except Exception as exc:
        health_status["redis"] = f"error: {exc}"
        health_status["status"] = "degraded"

    if health_status["status"] != "ok":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=health_status,
        )

    return health_status
