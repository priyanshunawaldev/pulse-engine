import socket
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import jwt
import pytest
from pydantic import ValidationError

from app.core.database import get_db
from app.core.redis import close_redis, get_redis, get_redis_dep
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.main import app, lifespan
from app.models.account import Account, AccountStatus
from app.models.auth import ClientRecord
from app.models.transaction import Transaction, TransactionStatus
from app.models.webhook import WebhookDelivery, WebhookSubscription
from app.schemas.account import AccountCreateSchema
from app.schemas.transaction import EntryCreateSchema, TransactionCreateSchema
from app.schemas.webhook import WebhookSubscriptionCreateSchema, validate_target_url
from app.services.ledger_service import (
    AccountClosedError,
    CurrencyMismatchError,
    TransactionAlreadyReversedError,
    create_account,
    decode_cursor,
    encode_cursor,
    post_transaction,
    reverse_transaction,
)
from app.services.lock_service import (
    DistributedLock,
    LockAcquisitionError,
    acquire_account_locks,
)
from app.workers.tasks import (
    _dispatch_webhook_async,
    _do_dispatch_webhook,
    _trigger_webhooks_for_transaction_async,
    check_runtime_ssrf,
    dispatch_webhook,
    run_nightly_reconciliation,
    trigger_webhooks_for_transaction,
)

# ==============================================================================
# 1. Background Workers & Celery Tasks (app/workers/tasks.py)
# ==============================================================================

@pytest.mark.asyncio
async def test_runtime_ssrf_ip_checks_and_dns():
    # Direct IP private check
    with pytest.raises(ValueError, match="forbidden"):
        await check_runtime_ssrf("http://192.168.1.1/hook")

    with pytest.raises(ValueError, match="forbidden"):
        await check_runtime_ssrf("http://10.0.0.1/hook")

    # Hostname DNS gaierror handling (should pass gracefully without crashing)
    with patch("asyncio.base_events.BaseEventLoop.getaddrinfo", side_effect=socket.gaierror):
        await check_runtime_ssrf("https://non-existent-domain-pulseengine-test.org/webhook")


@pytest.mark.asyncio
async def test_do_dispatch_webhook_not_found(test_db):
    result = await _do_dispatch_webhook(test_db, str(uuid.uuid4()))
    assert result is False


@pytest.mark.asyncio
async def test_do_dispatch_webhook_successful_delivery(test_db):
    acc = Account(
        account_number="ACC-DISPATCH-OK",
        owner_name="Dispatch OK",
        currency="USD",
        initial_balance=Decimal("100.0000"),
        balance=Decimal("100.0000"),
        status=AccountStatus.ACTIVE,
    )
    test_db.add(acc)
    await test_db.flush()

    tx = Transaction(
        idempotency_key="tx_dispatch_ok_key",
        status=TransactionStatus.COMPLETED,
    )
    test_db.add(tx)
    await test_db.flush()

    sub = WebhookSubscription(
        account_id=acc.id,
        target_url="https://webhook.site/dispatch-success",
        event_types=["transaction.completed"],
        secret="whsec_test_success_secret",
        is_active=True,
    )
    test_db.add(sub)
    await test_db.flush()

    delivery = WebhookDelivery(
        subscription_id=sub.id,
        transaction_id=tx.id,
        event_type="transaction.completed",
        payload={"event": "transaction.completed"},
        status="PENDING",
    )
    test_db.add(delivery)
    await test_db.commit()

    # Mock successful HTTP post response
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        success = await _dispatch_webhook_async(str(delivery.id), session=test_db)
        assert success is True

    await test_db.refresh(delivery)
    assert delivery.status == "DELIVERED"
    assert delivery.response_status_code == 200
    assert delivery.error_detail is None


@pytest.mark.asyncio
async def test_dispatch_webhook_async_without_session(test_db):
    # Tests the branch: if session is None: async with async_session_factory()
    mock_sess_cm = AsyncMock()
    mock_sess_cm.__aenter__.return_value = test_db
    mock_sess_cm.__aexit__.return_value = None

    with patch("app.workers.tasks.async_session_factory", return_value=mock_sess_cm):
        result = await _dispatch_webhook_async(str(uuid.uuid4()))
        assert result is False


def test_dispatch_webhook_celery_task_retry():
    # Test dispatch_webhook Celery task when dispatch fails and triggers retry
    dispatch_webhook.request.retries = 1
    dispatch_webhook.retry = MagicMock(side_effect=RuntimeError("RetryScheduled"))

    with patch("app.workers.tasks.asyncio.run", side_effect=Exception("Connection timed out")):
        with pytest.raises(RuntimeError, match="RetryScheduled"):
            dispatch_webhook.run(str(uuid.uuid4()))
    assert dispatch_webhook.retry.called


@pytest.mark.asyncio
async def test_trigger_webhooks_for_transaction_async_without_session(test_db):
    mock_sess_cm = AsyncMock()
    mock_sess_cm.__aenter__.return_value = test_db
    mock_sess_cm.__aexit__.return_value = None

    with patch("app.workers.tasks.async_session_factory", return_value=mock_sess_cm):
        result = await _trigger_webhooks_for_transaction_async(
            str(uuid.uuid4()),
            [str(uuid.uuid4())],
            "transaction.completed",
        )
        assert result == []


def test_trigger_webhooks_for_transaction_sync_fallback():
    # Test trigger_webhooks_for_transaction when called with and without running loop
    with patch("app.workers.tasks.dispatch_webhook.delay") as mock_delay:
        with patch("app.workers.tasks._trigger_webhooks_for_transaction_async", new_callable=AsyncMock, return_value=["deliv-1"]):
            trigger_webhooks_for_transaction(str(uuid.uuid4()), [str(uuid.uuid4())])
            assert mock_delay.called


def test_run_nightly_reconciliation_celery_task():
    with patch("app.workers.tasks.run_reconciliation", new_callable=AsyncMock):
        mock_sess_cm = AsyncMock()
        mock_sess_cm.__aenter__.return_value = AsyncMock()
        mock_sess_cm.__aexit__.return_value = None
        with patch("app.workers.tasks.async_session_factory", return_value=mock_sess_cm):
            run_nightly_reconciliation()


# ==============================================================================
# 2. Application Lifespan & Global Handlers (app/main.py)
# ==============================================================================

@pytest.mark.asyncio
async def test_app_lifespan_context():
    # Test normal lifespan execution
    async with lifespan(app):
        pass

    # Test lifespan when Redis ping fails
    mock_redis = AsyncMock()
    mock_redis.ping.side_effect = Exception("Redis connection refused")
    with patch("app.main.get_redis", return_value=mock_redis):
        async with lifespan(app):
            pass


@pytest.mark.asyncio
async def test_validation_error_handler(client: httpx.AsyncClient, auth_headers: dict[str, str]):
    # Missing required 'owner_name'
    resp = await client.post(
        "/v1/accounts",
        json={"currency": "USD"},
        headers=auth_headers,
    )
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "details" in data["error"]


# ==============================================================================
# 3. Core Database & Redis Generators (app/core/database.py, app/core/redis.py)
# ==============================================================================

@pytest.mark.asyncio
async def test_database_get_db_dependency():
    mock_sess = AsyncMock()
    mock_sess_cm = AsyncMock()
    mock_sess_cm.__aenter__.return_value = mock_sess
    mock_sess_cm.__aexit__.return_value = None

    with patch("app.core.database.async_session_factory", return_value=mock_sess_cm):
        gen = get_db()
        sess = await anext(gen)
        assert sess is mock_sess
        with pytest.raises(StopAsyncIteration):
            await anext(gen)


@pytest.mark.asyncio
async def test_redis_get_dep_and_close():
    # Test get_redis and close_redis
    r = get_redis()
    assert r is not None

    gen = get_redis_dep()
    client_dep = await anext(gen)
    assert client_dep is not None
    with pytest.raises(StopAsyncIteration):
        await anext(gen)

    await close_redis()


def test_security_tokens_with_custom_expiry_and_decode():
    # Test create_access_token with custom expires_delta
    acc_tok = create_access_token({"sub": "custom_user"}, expires_delta=timedelta(minutes=30))
    decoded = decode_token(acc_tok)
    assert decoded["sub"] == "custom_user"
    assert decoded["type"] == "access"

    # Test create_refresh_token with custom expires_delta
    ref_tok = create_refresh_token({"sub": "custom_user"}, expires_delta=timedelta(days=7))
    decoded_ref = decode_token(ref_tok)
    assert decoded_ref["sub"] == "custom_user"
    assert decoded_ref["type"] == "refresh"

    # Invalid token decoding raises PyJWTError
    with pytest.raises(jwt.PyJWTError):
        decode_token("this.is.an.invalid.jwt.token")


# ==============================================================================
# 4. Auth Endpoints Edge Cases (app/api/v1/endpoints/auth.py, app/api/deps.py)
# ==============================================================================

@pytest.mark.asyncio
async def test_auth_invalid_credentials_and_tokens(client: httpx.AsyncClient, test_db):
    # Invalid bearer token on protected endpoint
    resp_auth = await client.get("/v1/accounts", headers={"Authorization": "Bearer invalid_bearer_token"})
    assert resp_auth.status_code == 401
    assert "Invalid or expired" in resp_auth.json()["detail"]

    # Non-existent client_id on /auth/token
    resp1 = await client.post(
        "/v1/auth/token",
        json={"client_id": "non_existent_client", "client_secret": "any_secret"},
    )
    assert resp1.status_code == 401
    assert resp1.json()["detail"] == "Invalid client credentials."

    # Inactive client on /auth/token
    inactive_client = ClientRecord(
        client_id="inactive_client_id",
        client_secret_hash="hash",
        name="Inactive Client",
        is_active=False,
    )
    test_db.add(inactive_client)
    await test_db.commit()

    resp2 = await client.post(
        "/v1/auth/token",
        json={"client_id": "inactive_client_id", "client_secret": "wrong_secret"},
    )
    assert resp2.status_code == 401
    assert resp2.json()["detail"] == "Invalid client credentials."

    # Invalid refresh token on /auth/refresh
    resp3 = await client.post(
        "/v1/auth/refresh",
        json={"refresh_token": "invalid_refresh_token_string"},
    )
    assert resp3.status_code == 401
    assert "Invalid or expired" in resp3.json()["detail"]


# ==============================================================================
# 5. Transaction Endpoints Edge Cases (app/api/v1/endpoints/transactions.py)
# ==============================================================================

@pytest.mark.asyncio
async def test_transactions_endpoints_not_found(client: httpx.AsyncClient, auth_headers: dict[str, str]):
    dummy_uuid = str(uuid.uuid4())

    # Get non-existent transaction details
    resp_get = await client.get(f"/v1/transactions/{dummy_uuid}", headers=auth_headers)
    assert resp_get.status_code == 404
    assert f"'{dummy_uuid}' was not found" in resp_get.json()["detail"]

    # Reverse non-existent transaction
    resp_rev = await client.post(f"/v1/transactions/{dummy_uuid}/reverse", headers=auth_headers)
    assert resp_rev.status_code == 404
    assert f"'{dummy_uuid}' was not found" in resp_rev.json()["detail"]


@pytest.mark.asyncio
async def test_transactions_lock_acquisition_error_handler(client: httpx.AsyncClient, auth_headers: dict[str, str]):
    payload = {
        "idempotency_key": "tx_lock_err_key",
        "entries": [
            {"account_id": str(uuid.uuid4()), "amount": "-50.0000", "entry_type": "DEBIT"},
            {"account_id": str(uuid.uuid4()), "amount": "50.0000", "entry_type": "CREDIT"},
        ],
    }

    with patch("app.api.v1.endpoints.transactions.post_transaction", side_effect=LockAcquisitionError("Lock failure")):
        resp = await client.post("/v1/transactions", json=payload, headers=auth_headers)
        assert resp.status_code == 503
        assert "Lock failure" in resp.json()["detail"]

    with patch("app.api.v1.endpoints.transactions.reverse_transaction", side_effect=LockAcquisitionError("Reversal lock failure")):
        resp_rev = await client.post(f"/v1/transactions/{uuid.uuid4()}/reverse", headers=auth_headers)
        assert resp_rev.status_code == 503
        assert "Reversal lock failure" in resp_rev.json()["detail"]


# ==============================================================================
# 6. Webhook Deliveries Cursor Pagination (app/api/v1/endpoints/webhooks.py)
# ==============================================================================

@pytest.mark.asyncio
async def test_webhook_deliveries_cursor_pagination(client: httpx.AsyncClient, auth_headers: dict[str, str], test_db):
    acc = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Delivery Paginator", "currency": "USD", "initial_balance": "100.0000"},
        headers=auth_headers,
    )).json()

    sub = (await client.post(
        "/v1/webhooks",
        json={"account_id": acc["id"], "target_url": "https://example.com/paged", "event_types": ["*"]},
        headers=auth_headers,
    )).json()

    tx = Transaction(idempotency_key="tx_deliv_page", status=TransactionStatus.COMPLETED)
    test_db.add(tx)
    await test_db.flush()

    # Seed 3 delivery records
    sub_uuid = uuid.UUID(sub["id"])
    d1 = WebhookDelivery(subscription_id=sub_uuid, transaction_id=tx.id, event_type="e1", payload={}, status="PENDING")
    d2 = WebhookDelivery(subscription_id=sub_uuid, transaction_id=tx.id, event_type="e2", payload={}, status="PENDING")
    d3 = WebhookDelivery(subscription_id=sub_uuid, transaction_id=tx.id, event_type="e3", payload={}, status="PENDING")
    test_db.add_all([d1, d2, d3])
    await test_db.commit()

    # Page 1
    p1 = (await client.get(f"/v1/webhooks/{sub['id']}/deliveries?limit=2", headers=auth_headers)).json()
    assert len(p1["items"]) == 2
    assert p1["has_more"] is True
    cursor = p1["next_cursor"]
    assert cursor is not None

    # Page 2
    p2 = (await client.get(f"/v1/webhooks/{sub['id']}/deliveries?limit=2&cursor={cursor}", headers=auth_headers)).json()
    assert len(p2["items"]) == 1
    assert p2["has_more"] is False


# ==============================================================================
# 7. Webhook & Transaction Schema Validations (app/schemas/webhook.py, app/schemas/transaction.py)
# ==============================================================================

def test_webhook_schema_validations():
    # Missing scheme or invalid scheme
    with pytest.raises(ValidationError):
        WebhookSubscriptionCreateSchema(
            account_id=uuid.uuid4(),
            target_url="ftp://example.com/webhook",
            event_types=["transaction.completed"],
        )

    # Empty target URL
    with pytest.raises(ValidationError):
        WebhookSubscriptionCreateSchema(
            account_id=uuid.uuid4(),
            target_url="   ",
            event_types=["transaction.completed"],
        )

    # Validate target url without host
    with pytest.raises(ValueError, match="hostname is required"):
        validate_target_url("http:///no-host")

    # Localhost in validate_target_url
    with pytest.raises(ValueError, match="loopback"):
        validate_target_url("http://localhost:5000/hook")

    # Private IP
    with pytest.raises(ValueError, match="forbidden"):
        validate_target_url("http://127.0.0.1/hook")

    with pytest.raises(ValueError, match="forbidden"):
        validate_target_url("http://10.0.0.1/hook")

    # Cloud metadata
    with pytest.raises(ValueError, match="cloud metadata"):
        validate_target_url("http://instance-data/hook")

    # Local / mDNS
    with pytest.raises(ValueError, match="local/mDNS"):
        validate_target_url("http://service.local/hook")


def test_transaction_entry_schema_validations():
    # DEBIT with positive amount raises ValidationError
    with pytest.raises(ValidationError, match="DEBIT amount must be strictly negative"):
        EntryCreateSchema(account_id=uuid.uuid4(), amount=Decimal("10.0000"), entry_type="DEBIT")

    # CREDIT with negative amount raises ValidationError
    with pytest.raises(ValidationError, match="CREDIT amount must be strictly positive"):
        EntryCreateSchema(account_id=uuid.uuid4(), amount=Decimal("-10.0000"), entry_type="CREDIT")

    # Sum of entries != 0 in TransactionCreateSchema
    with pytest.raises(ValidationError, match="invariant violated"):
        TransactionCreateSchema(
            idempotency_key="tx_test_schema_sum",
            entries=[
                EntryCreateSchema(account_id=uuid.uuid4(), amount=Decimal("-10.0000"), entry_type="DEBIT"),
                EntryCreateSchema(account_id=uuid.uuid4(), amount=Decimal("20.0000"), entry_type="CREDIT"),
            ],
        )


# ==============================================================================
# 8. Lock Service Branches (app/services/lock_service.py)
# ==============================================================================

@pytest.mark.asyncio
async def test_distributed_lock_acquisition_failure(test_redis):
    lock = DistributedLock(test_redis, "test_resource_busy", ttl_ms=1000, acquire_timeout_ms=50, retry_delay_ms=10)

    # Pre-occupy lock with a foreign token
    await test_redis.set("lock:test_resource_busy", "foreign_token")

    # Attempt acquire -> should timeout and return False
    acquired = await lock.acquire()
    assert acquired is False

    # Attempt release with unacquired lock -> should return False
    released = await lock.release()
    assert released is False


@pytest.mark.asyncio
async def test_acquire_account_locks_failure(test_redis):
    acc1 = uuid.uuid4()
    acc2 = uuid.uuid4()

    # Mock acquire timeout
    with patch.object(DistributedLock, "acquire", new_callable=AsyncMock, return_value=False):
        with pytest.raises(LockAcquisitionError):
            async with acquire_account_locks(test_redis, [acc1, acc2], ttl_ms=1000):
                pass


# ==============================================================================
# 9. Ledger Service Edge Cases & Cursor Handling (app/services/ledger_service.py)
# ==============================================================================

def test_ledger_cursor_encode_decode():
    test_id = uuid.uuid4()
    cursor = encode_cursor(test_id)
    decoded_id = decode_cursor(cursor)
    assert decoded_id == test_id

    # Cursor with '|' separator
    import base64
    compound = base64.urlsafe_b64encode(f"timestamp|{test_id}".encode()).decode("utf-8")
    assert decode_cursor(compound) == test_id


@pytest.mark.asyncio
async def test_ledger_service_closed_account_transfer(test_db, test_redis):
    acc_a = await create_account(
        test_db,
        AccountCreateSchema(owner_name="Closed Tester A", currency="USD", initial_balance=Decimal("100.0000")),
    )
    acc_b = await create_account(
        test_db,
        AccountCreateSchema(owner_name="Closed Tester B", currency="USD", initial_balance=Decimal("100.0000")),
    )

    # Soft-close acc_a in DB
    acc_obj = await test_db.get(Account, acc_a.id)
    acc_obj.status = AccountStatus.CLOSED
    await test_db.commit()

    # Attempt transfer from closed account
    tx_schema = TransactionCreateSchema(
        idempotency_key="tx_closed_acc_test",
        entries=[
            EntryCreateSchema(account_id=acc_a.id, amount=Decimal("-10.0000"), entry_type="DEBIT"),
            EntryCreateSchema(account_id=acc_b.id, amount=Decimal("10.0000"), entry_type="CREDIT"),
        ],
    )
    with pytest.raises(AccountClosedError):
        await post_transaction(test_db, test_redis, tx_schema)


@pytest.mark.asyncio
async def test_ledger_service_currency_mismatch(test_db, test_redis):
    acc_usd = await create_account(
        test_db,
        AccountCreateSchema(owner_name="USD Acc", currency="USD", initial_balance=Decimal("100.0000")),
    )
    acc_eur = await create_account(
        test_db,
        AccountCreateSchema(owner_name="EUR Acc", currency="EUR", initial_balance=Decimal("100.0000")),
    )

    tx_schema = TransactionCreateSchema(
        idempotency_key="tx_curr_mismatch_test",
        entries=[
            EntryCreateSchema(account_id=acc_usd.id, amount=Decimal("-10.0000"), entry_type="DEBIT"),
            EntryCreateSchema(account_id=acc_eur.id, amount=Decimal("10.0000"), entry_type="CREDIT"),
        ],
    )
    with pytest.raises(CurrencyMismatchError):
        await post_transaction(test_db, test_redis, tx_schema)


@pytest.mark.asyncio
async def test_ledger_service_already_reversed(test_db, test_redis):
    acc = await create_account(
        test_db,
        AccountCreateSchema(owner_name="Solo Acc", currency="USD", initial_balance=Decimal("100.0000")),
    )
    acc2 = await create_account(
        test_db,
        AccountCreateSchema(owner_name="Partner Acc", currency="USD", initial_balance=Decimal("0.0000")),
    )
    valid_tx = TransactionCreateSchema(
        idempotency_key="tx_to_be_reversed",
        entries=[
            EntryCreateSchema(account_id=acc.id, amount=Decimal("-10.0000"), entry_type="DEBIT"),
            EntryCreateSchema(account_id=acc2.id, amount=Decimal("10.0000"), entry_type="CREDIT"),
        ],
    )
    tx_resp, _ = await post_transaction(test_db, test_redis, valid_tx)

    # First reversal succeeds
    rev_resp = await reverse_transaction(test_db, test_redis, tx_resp.id)
    assert rev_resp.status == TransactionStatus.COMPLETED

    # Verify original transaction is marked REVERSED
    original_tx = await test_db.get(Transaction, tx_resp.id)
    assert original_tx.status == TransactionStatus.REVERSED

    # Second reversal fails with TransactionAlreadyReversedError
    with pytest.raises(TransactionAlreadyReversedError):
        await reverse_transaction(test_db, test_redis, tx_resp.id)
