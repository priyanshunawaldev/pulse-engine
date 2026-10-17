from unittest.mock import AsyncMock

import httpx
import pytest

from app.api.deps import get_db, get_redis_dep
from app.core.logging import setup_logging
from app.core.redis import close_redis
from app.main import app, lifespan


@pytest.mark.asyncio
async def test_health_live_endpoint(client: httpx.AsyncClient):
    resp = await client.get("/health/live")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["app"] == "PulseEngine"


@pytest.mark.asyncio
async def test_health_ready_endpoint(client: httpx.AsyncClient):
    resp = await client.get("/health/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["postgres"] == "ok"
    assert data["redis"] == "ok"


@pytest.mark.asyncio
async def test_health_ready_postgres_failure(client: httpx.AsyncClient):
    mock_session = AsyncMock()
    mock_session.execute.side_effect = Exception("DB Connection Lost")

    async def _failing_db():
        yield mock_session

    app.dependency_overrides[get_db] = _failing_db
    try:
        resp = await client.get("/health/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert "degraded" in data["detail"]["status"]
    finally:
        del app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_health_ready_redis_failure(client: httpx.AsyncClient):
    mock_redis = AsyncMock()
    mock_redis.ping.side_effect = Exception("Redis Connection Dropped")

    async def _failing_redis():
        yield mock_redis

    app.dependency_overrides[get_redis_dep] = _failing_redis
    try:
        resp = await client.get("/health/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert "degraded" in data["detail"]["status"]
    finally:
        del app.dependency_overrides[get_redis_dep]


def test_structured_logging_configuration():
    setup_logging(debug=True)
    setup_logging(debug=False)


@pytest.mark.asyncio
async def test_app_lifespan_and_redis_lifecycle(test_redis):
    # Test lifespan startup and shutdown
    async with lifespan(app):
        pass

    # Test get_redis_dep dependency
    async for r in get_redis_dep():
        assert r is not None

    await close_redis()
