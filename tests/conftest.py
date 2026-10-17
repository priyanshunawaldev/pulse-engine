import asyncio
import hashlib
from collections.abc import AsyncGenerator

import fakeredis.aioredis
import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

import app.core.redis as redis_core
from app.api.deps import get_db, get_redis_dep
from app.core.security import hash_api_key
from app.main import app
from app.models.auth import APIKeyRecord, ClientRecord
from app.models.base import Base
from app.workers.celery_app import celery_app

# Configure Celery in-memory broker for instant, non-blocking test execution
celery_app.conf.update(
    broker_url="memory://",
    result_backend="cache+memory://",
    task_ignore_result=True,
)

TEST_API_KEY = "pk_test_live_secret_key_pulseengine_123456"
TEST_CLIENT_ID = "client_test_id"
TEST_CLIENT_SECRET = "client_test_secret"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_redis() -> AsyncGenerator[fakeredis.aioredis.FakeRedis, None]:
    """Provide an isolated in-memory FakeRedis client with Lua support."""
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    # Monkey-patch get_redis in app.core.redis to return our test redis
    redis_core._redis_client = redis
    yield redis
    await redis.flushall()
    await redis.aclose()


@pytest.fixture
async def test_engine():
    """Create in-memory SQLite async engine for high-speed, isolated test execution."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def test_session_factory(test_engine):
    return async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


@pytest.fixture
async def test_db(test_session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with test_session_factory() as session:
        # Seed test API Key
        key_hash = hash_api_key(TEST_API_KEY)
        api_key_rec = APIKeyRecord(
            key_hash=key_hash,
            name="Automated Test Suite API Key",
            is_active=True,
        )
        session.add(api_key_rec)

        # Seed test OAuth Client
        secret_hash = hashlib.sha256(TEST_CLIENT_SECRET.encode("utf-8")).hexdigest()
        client_rec = ClientRecord(
            client_id=TEST_CLIENT_ID,
            client_secret_hash=secret_hash,
            name="Automated Test OAuth Client",
            is_active=True,
        )
        session.add(client_rec)
        await session.commit()

        yield session


@pytest.fixture
async def client(
    test_session_factory,
    test_redis,
    test_db,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async HTTP client pre-configured with FastAPI dependency overrides."""
    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_factory() as session:
            yield session

    async def _override_get_redis() -> AsyncGenerator[fakeredis.aioredis.FakeRedis, None]:
        yield test_redis

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis_dep] = _override_get_redis

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"X-API-Key": TEST_API_KEY}
