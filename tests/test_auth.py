import httpx
import pytest

from app.core.security import check_rate_limit
from tests.conftest import TEST_CLIENT_ID, TEST_CLIENT_SECRET


@pytest.mark.asyncio
async def test_unauthenticated_request_fails(client: httpx.AsyncClient):
    resp = await client.get("/v1/accounts")
    assert resp.status_code == 401
    assert "Missing or invalid authentication" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_api_key_fails(client: httpx.AsyncClient):
    resp = await client.get("/v1/accounts", headers={"X-API-Key": "completely_fake_invalid_key"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_oauth_jwt_flow_and_bearer_access(client: httpx.AsyncClient):
    # 1. Exchange client credentials for tokens
    token_resp = await client.post(
        "/v1/auth/token",
        json={"client_id": TEST_CLIENT_ID, "client_secret": TEST_CLIENT_SECRET},
    )
    assert token_resp.status_code == 200
    token_data = token_resp.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    access_token = token_data["access_token"]
    refresh_token = token_data["refresh_token"]

    # 2. Use JWT Bearer token to access protected endpoint
    jwt_headers = {"Authorization": f"Bearer {access_token}"}
    acc_resp = await client.get("/v1/accounts", headers=jwt_headers)
    assert acc_resp.status_code == 200

    # 3. Refresh token
    refresh_resp = await client.post(
        "/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 200
    new_data = refresh_resp.json()
    assert "access_token" in new_data
    assert new_data["access_token"] != access_token


@pytest.mark.asyncio
async def test_redis_token_bucket_rate_limiter(test_redis):
    # Test token bucket with capacity 3, refill rate 0.1 tokens/sec
    identifier = "test_limiter_client"

    # Consume 3 tokens
    allow1, rem1 = await check_rate_limit(test_redis, identifier, capacity=3, refill_rate=0.1, requested=1)
    allow2, rem2 = await check_rate_limit(test_redis, identifier, capacity=3, refill_rate=0.1, requested=1)
    allow3, rem3 = await check_rate_limit(test_redis, identifier, capacity=3, refill_rate=0.1, requested=1)

    assert allow1 is True and rem1 == 2
    assert allow2 is True and rem2 == 1
    assert allow3 is True and rem3 == 0

    # 4th request must be rejected
    allow4, rem4 = await check_rate_limit(test_redis, identifier, capacity=3, refill_rate=0.1, requested=1)
    assert allow4 is False
    assert rem4 == 0


@pytest.mark.asyncio
async def test_create_api_key_and_client_endpoints(client: httpx.AsyncClient):
    # 1. Create API Key
    key_resp = await client.post("/v1/auth/api-keys", json={"name": "Integration Test Key"})
    assert key_resp.status_code == 201
    key_data = key_resp.json()
    assert key_data["api_key"].startswith("pk_live_")
    raw_key = key_data["api_key"]

    # 2. Verify new API Key can access protected endpoint
    acc_resp = await client.get("/v1/accounts", headers={"X-API-Key": raw_key})
    assert acc_resp.status_code == 200

    # 3. Register OAuth Client
    client_resp = await client.post("/v1/auth/clients", json={"name": "Automated Testing Suite Client"})
    assert client_resp.status_code == 201
    c_data = client_resp.json()
    assert c_data["client_id"].startswith("client_")
    assert c_data["client_secret"].startswith("sec_")

    # 4. Exchange new client credentials for token
    token_resp = await client.post(
        "/v1/auth/token",
        json={"client_id": c_data["client_id"], "client_secret": c_data["client_secret"]},
    )
    assert token_resp.status_code == 200
    assert "access_token" in token_resp.json()
