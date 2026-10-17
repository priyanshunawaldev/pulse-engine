import httpx
import pytest


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
