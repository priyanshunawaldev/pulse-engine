from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest

from app.models.idempotency import IdempotencyRecord
from app.services.idempotency_service import compute_request_hash


@pytest.mark.asyncio
async def test_identical_replay_returns_cached_response_10_times(client: httpx.AsyncClient, auth_headers: dict[str, str]):
    """
    Submitting the same idempotency key + identical payload 10 times must:
    - Return 200 OK for all 10 calls.
    - Return identical transaction IDs and response bodies.
    - Debit the account ONLY ONCE ($50 deducted, not $500).
    """
    acc_a = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Idempotent Sender", "currency": "USD", "initial_balance": "500.0000"},
        headers=auth_headers,
    )).json()
    acc_b = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Idempotent Receiver", "currency": "USD", "initial_balance": "0.0000"},
        headers=auth_headers,
    )).json()

    payload = {
        "idempotency_key": "tx_idempotent_order_9999",
        "description": "Order 9999 payment",
        "entries": [
            {"account_id": acc_a["id"], "amount": "-50.0000", "entry_type": "DEBIT"},
            {"account_id": acc_b["id"], "amount": "50.0000", "entry_type": "CREDIT"},
        ],
    }

    # Submit 10 consecutive identical requests
    responses = [await client.post("/v1/transactions", json=payload, headers=auth_headers) for _ in range(10)]

    for r in responses:
        assert r.status_code == 200

    first_tx_id = responses[0].json()["id"]
    for r in responses[1:]:
        assert r.json()["id"] == first_tx_id
        assert r.json()["idempotency_key"] == "tx_idempotent_order_9999"

    # Crucial check: balance must only have decreased by 50, not 500
    bal_a = Decimal((await client.get(f"/v1/accounts/{acc_a['id']}", headers=auth_headers)).json()["balance"])
    bal_b = Decimal((await client.get(f"/v1/accounts/{acc_b['id']}", headers=auth_headers)).json()["balance"])

    assert bal_a == Decimal("450.0000")
    assert bal_b == Decimal("50.0000")


@pytest.mark.asyncio
async def test_replay_with_different_body_fails_with_hash_mismatch(client: httpx.AsyncClient, auth_headers: dict[str, str]):
    """
    If a client reuses an idempotency key with a mutated payload (different amount or recipient),
    the server must detect SHA-256 mismatch and reject with 422 Unprocessable Entity.
    """
    acc_a = (await client.post(
        "/v1/accounts",
        json={"owner_name": "User 1", "currency": "USD", "initial_balance": "500.0000"},
        headers=auth_headers,
    )).json()
    acc_b = (await client.post(
        "/v1/accounts",
        json={"owner_name": "User 2", "currency": "USD", "initial_balance": "0.0000"},
        headers=auth_headers,
    )).json()

    key = "tx_replay_tamper_check"

    # Initial request: $20 transfer
    resp1 = await client.post(
        "/v1/transactions",
        json={
            "idempotency_key": key,
            "entries": [
                {"account_id": acc_a["id"], "amount": "-20.0000", "entry_type": "DEBIT"},
                {"account_id": acc_b["id"], "amount": "20.0000", "entry_type": "CREDIT"},
            ],
        },
        headers=auth_headers,
    )
    assert resp1.status_code == 200

    # Tampered request: same key, but $80 transfer
    resp2 = await client.post(
        "/v1/transactions",
        json={
            "idempotency_key": key,
            "entries": [
                {"account_id": acc_a["id"], "amount": "-80.0000", "entry_type": "DEBIT"},
                {"account_id": acc_b["id"], "amount": "80.0000", "entry_type": "CREDIT"},
            ],
        },
        headers=auth_headers,
    )
    assert resp2.status_code == 422
    assert "different request payload" in resp2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_concurrent_in_flight_processing_conflict(client: httpx.AsyncClient, auth_headers: dict[str, str], test_db):
    """
    If an idempotency key is currently in PROCESSING status, concurrent requests must return 409 Conflict.
    """
    acc_a = (await client.post(
        "/v1/accounts",
        json={"owner_name": "A", "currency": "USD", "initial_balance": "100.0000"},
        headers=auth_headers,
    )).json()
    acc_b = (await client.post(
        "/v1/accounts",
        json={"owner_name": "B", "currency": "USD", "initial_balance": "100.0000"},
        headers=auth_headers,
    )).json()

    key = "tx_in_flight_conflict_key"
    payload = {
        "idempotency_key": key,
        "entries": [
            {"account_id": acc_a["id"], "amount": "-10.0000", "entry_type": "DEBIT"},
            {"account_id": acc_b["id"], "amount": "10.0000", "entry_type": "CREDIT"},
        ],
    }

    from app.schemas.transaction import TransactionCreateSchema
    parsed_payload = TransactionCreateSchema(**payload).model_dump(mode="json")
    req_hash = compute_request_hash(parsed_payload)
    in_flight = IdempotencyRecord(
        idempotency_key=key,
        request_hash=req_hash,
        status="PROCESSING",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    test_db.add(in_flight)
    await test_db.commit()

    # Attempt to post transaction while in flight
    resp = await client.post("/v1/transactions", json=payload, headers=auth_headers)
    assert resp.status_code == 409
    assert "currently being processed" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_concurrent_idempotency_race_condition(client: httpx.AsyncClient, auth_headers: dict[str, str]):
    """
    CRITICAL RACE CONDITION TEST:
    Fire two concurrent requests simultaneously with the EXACT same new idempotency key.
    One must succeed with 200 OK.
    The concurrent request must NOT crash with 500 DB IntegrityError;
    it must return 409 Conflict (in-flight processing) or 200 (cached response).
    Account must only be debited ONCE.
    """
    import asyncio

    acc_a = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Racer A", "currency": "USD", "initial_balance": "500.0000"},
        headers=auth_headers,
    )).json()
    acc_b = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Racer B", "currency": "USD", "initial_balance": "0.0000"},
        headers=auth_headers,
    )).json()

    key = "tx_concurrent_idempotency_race_key"
    payload = {
        "idempotency_key": key,
        "entries": [
            {"account_id": acc_a["id"], "amount": "-30.0000", "entry_type": "DEBIT"},
            {"account_id": acc_b["id"], "amount": "30.0000", "entry_type": "CREDIT"},
        ],
    }

    # Fire both concurrently
    resp1, resp2 = await asyncio.gather(
        client.post("/v1/transactions", json=payload, headers=auth_headers),
        client.post("/v1/transactions", json=payload, headers=auth_headers),
    )

    codes = [resp1.status_code, resp2.status_code]
    # At least one must be 200 OK
    assert 200 in codes
    # The other must be either 200 (cached hit) or 409 (conflict) - NEVER 500!
    assert all(c in (200, 409) for c in codes)

    # Balance check: only 30 deducted, not 60
    bal_a = Decimal((await client.get(f"/v1/accounts/{acc_a['id']}", headers=auth_headers)).json()["balance"])
    assert bal_a == Decimal("470.0000")
