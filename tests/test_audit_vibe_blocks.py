import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy.orm.exc import StaleDataError

from app.core.config import settings
from app.models.idempotency import IdempotencyRecord
from app.models.transaction import LedgerEntry
from app.models.webhook import WebhookDelivery, WebhookSubscription
from app.workers.tasks import _dispatch_webhook_async


@pytest.mark.asyncio
async def test_ssrf_guard_rejections_and_allowlist(client: httpx.AsyncClient, auth_headers: dict[str, str]):
    """
    Vibe Block 26 (SSRF Guard):
    Verify that webhook registration rejects loopback, private networks, cloud metadata,
    and non-http/https schemes, while permitting allowed test domains.
    """
    acc = (await client.post(
        "/v1/accounts",
        json={"owner_name": "SSRF Account", "currency": "USD", "initial_balance": "100.0000"},
        headers=auth_headers,
    )).json()

    forbidden_urls = [
        "http://127.0.0.1/hook",
        "http://127.0.0.1:8000/hook",
        "http://localhost/hook",
        "http://sub.localhost:3000/hook",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5:9000/webhook",
        "http://172.16.1.100/webhook",
        "http://192.168.0.1/webhook",
        "http://[::1]/hook",
        "http://[::ffff:127.0.0.1]/hook",
        "http://service.local/webhook",
        "ftp://example.com/hook",
        "file:///etc/passwd",
        "gopher://127.0.0.1:6379/_",
    ]

    for url in forbidden_urls:
        resp = await client.post(
            "/v1/webhooks",
            json={
                "account_id": acc["id"],
                "target_url": url,
                "event_types": ["transaction.completed"],
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422, f"Expected 422 for forbidden URL '{url}', got {resp.status_code}"

    # Allowed domains & schemes (including domains containing the substring 'forbidden')
    allowed_urls = [
        "https://webhook.site/secure-test",
        "https://failing-endpoint.internal/webhook",
        "http://testserver/webhook",
        "https://service.test/webhook",
        "https://api.example.com/webhooks/pulseengine",
        "https://api.forbidden-planet.org/webhook",
        "https://forbidden-city.example.com/events",
    ]

    for url in allowed_urls:
        resp = await client.post(
            "/v1/webhooks",
            json={
                "account_id": acc["id"],
                "target_url": url,
                "event_types": ["transaction.completed"],
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201, f"Expected 201 for allowed URL '{url}', got {resp.status_code}"


@pytest.mark.asyncio
async def test_runtime_ssrf_blocking_in_worker(test_db):
    """
    Vibe Block 26 (Runtime SSRF Protection):
    Even if a webhook subscription with a malicious target URL bypasses registration,
    the background worker must detect the SSRF violation at runtime, abort outbound network I/O,
    and route the delivery directly to DLQ.
    """
    from app.models.account import Account, AccountStatus
    from app.models.transaction import Transaction, TransactionStatus

    # Seed account, transaction, and malicious subscription directly in DB
    acc = Account(
        account_number="ACC-SSRF-TEST",
        owner_name="SSRF Tester",
        currency="USD",
        initial_balance=Decimal("100.0000"),
        balance=Decimal("100.0000"),
        status=AccountStatus.ACTIVE,
    )
    test_db.add(acc)
    await test_db.flush()

    tx = Transaction(
        idempotency_key="tx_ssrf_runtime_trigger",
        status=TransactionStatus.COMPLETED,
    )
    test_db.add(tx)
    await test_db.flush()

    malicious_sub = WebhookSubscription(
        account_id=acc.id,
        target_url="http://169.254.169.254/latest/meta-data/iam/credentials",
        event_types=["transaction.completed"],
        secret="whsec_malicious_test_secret",
        is_active=True,
    )
    test_db.add(malicious_sub)
    await test_db.flush()

    delivery = WebhookDelivery(
        subscription_id=malicious_sub.id,
        transaction_id=tx.id,
        event_type="transaction.completed",
        payload={"event": "transaction.completed"},
        status="PENDING",
    )
    test_db.add(delivery)
    await test_db.commit()

    # Dispatch via async worker
    success = await _dispatch_webhook_async(str(delivery.id), session=test_db)
    assert success is False

    await test_db.refresh(delivery)
    assert delivery.status == "DLQ"
    assert delivery.error_detail is not None
    assert "SSRF security violation" in delivery.error_detail

    # 2. Test DNS rebinding protection: public-looking domain that resolves to loopback 127.0.0.1
    rebinding_sub = WebhookSubscription(
        account_id=acc.id,
        target_url="https://attacker-rebinding.org/webhook",
        event_types=["transaction.completed"],
        secret="whsec_rebinding_test_secret",
        is_active=True,
    )
    test_db.add(rebinding_sub)
    await test_db.flush()

    rebinding_delivery = WebhookDelivery(
        subscription_id=rebinding_sub.id,
        transaction_id=tx.id,
        event_type="transaction.completed",
        payload={"event": "transaction.completed"},
        status="PENDING",
    )
    test_db.add(rebinding_delivery)
    await test_db.commit()

    # Mock getaddrinfo on event loop to simulate DNS resolution yielding 127.0.0.1
    mock_addrinfo = [(2, 1, 6, "", ("127.0.0.1", 443))]
    with patch("asyncio.base_events.BaseEventLoop.getaddrinfo", return_value=mock_addrinfo):
        rebinding_success = await _dispatch_webhook_async(str(rebinding_delivery.id), session=test_db)
        assert rebinding_success is False

    await test_db.refresh(rebinding_delivery)
    assert rebinding_delivery.status == "DLQ"
    assert "SSRF security violation" in rebinding_delivery.error_detail


@pytest.mark.asyncio
async def test_cors_origin_restriction_and_credentials(client: httpx.AsyncClient):
    """
    Vibe Block 25 (Secure CORS Configuration):
    Verify that CORS origins are restricted to configured settings and wildcard is not used with credentials.
    """
    assert "http://localhost:3000" in settings.CORS_ORIGINS
    assert "http://localhost:8000" in settings.CORS_ORIGINS

    # Valid origin preflight
    resp_allowed = await client.options(
        "/v1/transactions",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert resp_allowed.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert resp_allowed.headers.get("access-control-allow-credentials") == "true"

    # Disallowed origin preflight
    resp_disallowed = await client.options(
        "/v1/transactions",
        headers={
            "Origin": "http://evil-attacker.example.org",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp_disallowed.headers.get("access-control-allow-origin") != "http://evil-attacker.example.org"
    assert resp_disallowed.headers.get("access-control-allow-origin") != "*"


def test_composite_btree_indexes_present():
    """
    Vibe Blocks 18 & 19 (Composite B-Tree Indexes):
    Verify that composite indexes on (account_id, id.desc()) and (subscription_id, id.desc())
    are registered in model table metadata for optimal cursor-based pagination.
    """
    ledger_indexes = {idx.name for idx in LedgerEntry.__table__.indexes}
    assert "ix_ledger_entries_account_id_id_desc" in ledger_indexes

    webhook_indexes = {idx.name for idx in WebhookDelivery.__table__.indexes}
    assert "ix_webhook_deliveries_subscription_id_id_desc" in webhook_indexes


@pytest.mark.asyncio
async def test_idempotency_expiration_permits_fresh_execution(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    test_db,
):
    """
    Vibe Block 17 (Idempotency Expiration Handling):
    1. At the service level: when a COMPLETED record has expired (expires_at <= now),
       check_or_create_idempotency must reset it to PROCESSING, clear cached body, and return is_cached=False.
    2. At the API level: when an in-flight request has timed out and expired, re-submitting the request
       must NOT return 409 Conflict, but reset to PROCESSING and execute successfully with 200 OK.
    """
    from app.services.idempotency_service import (
        check_or_create_idempotency,
        complete_idempotency,
        compute_request_hash,
    )

    # 1. Service-level test for completed record expiration
    key_service = "tx_service_level_ttl_test"
    dummy_hash = compute_request_hash({"amount": "100.0000"})

    # Initial check -> fresh execution
    rec1, is_cached1 = await check_or_create_idempotency(test_db, key_service, dummy_hash, ttl_hours=1)
    assert is_cached1 is False
    assert rec1.status == "PROCESSING"

    # Complete it
    await complete_idempotency(test_db, key_service, 200, {"status": "SUCCESS", "tx_id": "019468ab"})
    await test_db.commit()

    # Re-check while valid -> cache hit
    rec2, is_cached2 = await check_or_create_idempotency(test_db, key_service, dummy_hash, ttl_hours=1)
    assert is_cached2 is True
    assert rec2.status == "COMPLETED"

    # Expire the record
    rec2.expires_at = datetime.now(UTC) - timedelta(hours=2)
    await test_db.commit()

    # Re-check after expiration -> must reset to PROCESSING and return is_cached=False
    rec3, is_cached3 = await check_or_create_idempotency(test_db, key_service, dummy_hash, ttl_hours=1)
    assert is_cached3 is False
    assert rec3.status == "PROCESSING"
    assert rec3.response_body is None

    # 2. API-level test: Expired in-flight request recovers and completes
    acc_a = (await client.post(
        "/v1/accounts",
        json={"owner_name": "InFlight A", "currency": "USD", "initial_balance": "200.0000"},
        headers=auth_headers,
    )).json()
    acc_b = (await client.post(
        "/v1/accounts",
        json={"owner_name": "InFlight B", "currency": "USD", "initial_balance": "0.0000"},
        headers=auth_headers,
    )).json()

    key_api = "tx_expired_in_flight_recovery"
    payload = {
        "idempotency_key": key_api,
        "entries": [
            {"account_id": acc_a["id"], "amount": "-30.0000", "entry_type": "DEBIT"},
            {"account_id": acc_b["id"], "amount": "30.0000", "entry_type": "CREDIT"},
        ],
    }

    # Seed an in-flight record that expired 1 hour ago (e.g. previous server crash)
    from app.schemas.transaction import TransactionCreateSchema
    parsed_payload = TransactionCreateSchema(**payload).model_dump(mode="json")
    req_hash = compute_request_hash(parsed_payload)
    expired_in_flight = IdempotencyRecord(
        idempotency_key=key_api,
        request_hash=req_hash,
        status="PROCESSING",
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    test_db.add(expired_in_flight)
    await test_db.commit()

    # Client retries -> Must NOT return 409 Conflict; must reset and complete with 200 OK!
    resp = await client.post("/v1/transactions", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "COMPLETED"

    # Account balance check: 30 deducted
    bal_a = Decimal((await client.get(f"/v1/accounts/{acc_a['id']}", headers=auth_headers)).json()["balance"])
    assert bal_a == Decimal("170.0000")

    # 3. Expired record re-submitted with DIFFERENT payload (must reset and NOT throw IdempotencyPayloadMismatchError)
    key_diff = "tx_expired_different_payload_test"
    hash_old = compute_request_hash({"amount": "50.0000"})
    hash_new = compute_request_hash({"amount": "999.0000"})

    rec_diff, _ = await check_or_create_idempotency(test_db, key_diff, hash_old, ttl_hours=1)
    await complete_idempotency(test_db, key_diff, 200, {"status": "SUCCESS"})
    await test_db.commit()

    # Force expiration
    rec_diff.expires_at = datetime.now(UTC) - timedelta(hours=3)
    await test_db.commit()

    # Reuse expired key with completely different payload -> Must NOT raise IdempotencyPayloadMismatchError!
    rec_fresh, is_cached_fresh = await check_or_create_idempotency(test_db, key_diff, hash_new, ttl_hours=1)
    assert is_cached_fresh is False
    assert rec_fresh.status == "PROCESSING"
    assert rec_fresh.request_hash == hash_new
    assert rec_fresh.response_body is None


@pytest.mark.asyncio
async def test_stale_data_error_mapping_to_409_conflict(client: httpx.AsyncClient, auth_headers: dict[str, str]):
    """
    Vibe Block 35 (CAS StaleDataError Mapping):
    When SQLAlchemy optimistic locking detects concurrent row modifications and raises StaleDataError,
    the API endpoint must catch it and return HTTP 409 Conflict with detail 'CONCURRENT_VERSION_CONFLICT'.
    """
    acc_a = (await client.post(
        "/v1/accounts",
        json={"owner_name": "CAS Tester A", "currency": "USD", "initial_balance": "100.0000"},
        headers=auth_headers,
    )).json()
    acc_b = (await client.post(
        "/v1/accounts",
        json={"owner_name": "CAS Tester B", "currency": "USD", "initial_balance": "100.0000"},
        headers=auth_headers,
    )).json()

    payload = {
        "idempotency_key": "tx_cas_stale_data_test",
        "entries": [
            {"account_id": acc_a["id"], "amount": "-10.0000", "entry_type": "DEBIT"},
            {"account_id": acc_b["id"], "amount": "10.0000", "entry_type": "CREDIT"},
        ],
    }

    # Test POST /v1/transactions with mocked StaleDataError
    with patch("app.api.v1.endpoints.transactions.post_transaction", side_effect=StaleDataError("accounts", "stale data")):
        resp = await client.post("/v1/transactions", json=payload, headers=auth_headers)
        assert resp.status_code == 409
        assert resp.json()["detail"] == "CONCURRENT_VERSION_CONFLICT"

    # Test POST /v1/transactions/{id}/reverse with mocked StaleDataError
    dummy_tx_id = uuid.uuid4()
    with patch("app.api.v1.endpoints.transactions.reverse_transaction", side_effect=StaleDataError("accounts", "stale data")):
        resp_rev = await client.post(f"/v1/transactions/{dummy_tx_id}/reverse", headers=auth_headers)
        assert resp_rev.status_code == 409
        assert resp_rev.json()["detail"] == "CONCURRENT_VERSION_CONFLICT"
