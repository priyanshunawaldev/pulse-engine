import hashlib
import hmac
import json
from unittest.mock import patch

import httpx
import pytest

from app.workers.tasks import (
    _dispatch_webhook_async,
    _trigger_webhooks_for_transaction_async,
    generate_hmac_signature,
)


@pytest.mark.asyncio
async def test_webhook_subscription_lifecycle(client: httpx.AsyncClient, auth_headers: dict[str, str]):
    # 1. Create account
    acc = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Webhook Tester", "currency": "USD", "initial_balance": "100.0000"},
        headers=auth_headers,
    )).json()

    # 2. Register subscription
    sub_resp = await client.post(
        "/v1/webhooks",
        json={
            "account_id": acc["id"],
            "target_url": "https://webhook.site/test-endpoint",
            "event_types": ["transaction.completed", "transaction.reversed"],
        },
        headers=auth_headers,
    )
    assert sub_resp.status_code == 201
    sub_data = sub_resp.json()
    assert sub_data["target_url"] == "https://webhook.site/test-endpoint"
    assert sub_data["secret"].startswith("whsec_")
    sub_id = sub_data["id"]

    # 3. List subscriptions
    list_resp = await client.get(f"/v1/webhooks?account_id={acc['id']}", headers=auth_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()["items"]) == 1

    # 4. Deactivate subscription
    del_resp = await client.delete(f"/v1/webhooks/{sub_id}", headers=auth_headers)
    assert del_resp.status_code == 204

    # 5. Verify inactive
    list_resp2 = await client.get(f"/v1/webhooks?account_id={acc['id']}", headers=auth_headers)
    assert list_resp2.json()["items"][0]["is_active"] is False


def test_hmac_signature_generation():
    secret = "whsec_supersecretkey12345"
    payload = {"event": "transaction.completed", "amount": "100.0000"}
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")

    sig = generate_hmac_signature(secret, payload_bytes)
    expected = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

    assert sig == expected
    assert len(sig) == 64


@pytest.mark.asyncio
async def test_webhook_delivery_dlq_on_repeated_failure(test_db, client: httpx.AsyncClient, auth_headers: dict[str, str]):
    """
    Test that when an external webhook endpoint returns errors continuously,
    the delivery attempts increment and after 3 failures, status transitions to 'DLQ' (Dead-Letter Queue).
    """
    # Create account and transaction
    acc = (await client.post(
        "/v1/accounts",
        json={"owner_name": "DLQ Account", "currency": "USD", "initial_balance": "100.0000"},
        headers=auth_headers,
    )).json()

    # Create subscription
    sub = (await client.post(
        "/v1/webhooks",
        json={
            "account_id": acc["id"],
            "target_url": "https://failing-endpoint.internal/webhook",
            "event_types": ["transaction.completed"],
        },
        headers=auth_headers,
    )).json()

    # Post a transaction
    acc_sink = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Sink", "currency": "USD", "initial_balance": "0.0000"},
        headers=auth_headers,
    )).json()

    tx = (await client.post(
        "/v1/transactions",
        json={
            "idempotency_key": "tx_webhook_dlq_trigger",
            "entries": [
                {"account_id": acc["id"], "amount": "-10.0000", "entry_type": "DEBIT"},
                {"account_id": acc_sink["id"], "amount": "10.0000", "entry_type": "CREDIT"},
            ],
        },
        headers=auth_headers,
    )).json()

    # Trigger delivery creation directly
    delivery_ids = await _trigger_webhooks_for_transaction_async(
        transaction_id_str=tx["id"],
        account_ids_str=[acc["id"], acc_sink["id"]],
        event_type="transaction.completed",
        session=test_db,
    )
    assert len(delivery_ids) == 1
    delivery_id = delivery_ids[0]

    # Mock failing HTTP client
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused by endpoint")):
        # Attempt 1: should raise and record attempt_count=1, status=FAILED
        with pytest.raises(httpx.ConnectError):
            await _dispatch_webhook_async(delivery_id, session=test_db)

        # Attempt 2: should raise and record attempt_count=2, status=FAILED
        with pytest.raises(httpx.ConnectError):
            await _dispatch_webhook_async(delivery_id, session=test_db)

        # Attempt 3: max retries reached -> moves to DLQ
        result = await _dispatch_webhook_async(delivery_id, session=test_db)
        assert result is False

    # Check delivery status in DB / API
    deliveries_resp = await client.get(f"/v1/webhooks/{sub['id']}/deliveries?status=DLQ", headers=auth_headers)
    assert deliveries_resp.status_code == 200
    deliveries_data = deliveries_resp.json()
    assert len(deliveries_data["items"]) == 1
    dlq_record = deliveries_data["items"][0]
    assert dlq_record["status"] == "DLQ"
    assert dlq_record["attempt_count"] == 3
    assert "Connection refused" in dlq_record["error_detail"]
