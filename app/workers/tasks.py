import asyncio
import hashlib
import hmac
import ipaddress
import json
import socket
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.logging import logger
from app.models.webhook import WebhookDelivery, WebhookSubscription
from app.schemas.webhook import (
    TEST_DOMAINS,
    is_ip_private_or_restricted,
    validate_target_url,
)
from app.services.reconciliation_service import run_reconciliation
from app.workers.celery_app import celery_app


def generate_hmac_signature(secret: str, payload_bytes: bytes) -> str:
    """Generate SHA256 HMAC signature for webhook payload."""
    return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()


async def check_runtime_ssrf(target_url: str) -> None:
    """
    Defense-in-depth Runtime SSRF Guard:
    1. Validates syntactic correctness, scheme, and non-private IP/domain rules.
    2. Resolves DNS asynchronously for external hostnames to detect DNS rebinding
       or dynamic domain attacks pointing to loopback, link-local, or private subnets.
    """
    validate_target_url(target_url)

    parsed = urlsplit(target_url.strip())
    hostname = (parsed.hostname or "").lower()

    if hostname == "testserver" or any(hostname.endswith(tld) for tld in TEST_DOMAINS):
        return

    # If hostname is already a valid IP address, validate_target_url already checked it
    try:
        ip = ipaddress.ip_address(hostname)
        if is_ip_private_or_restricted(ip):
            raise ValueError(f"Webhook target URL IP '{hostname}' is forbidden (private/cloud metadata address).")
        return
    except ValueError:
        pass

    # Resolve domain asynchronously to prevent DNS rebinding attacks
    loop = asyncio.get_running_loop()
    try:
        addr_info = await loop.getaddrinfo(hostname, None)
        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            resolved_ip = ipaddress.ip_address(ip_str)
            if is_ip_private_or_restricted(resolved_ip):
                raise ValueError(
                    f"Resolved IP '{ip_str}' for host '{hostname}' is forbidden (SSRF restricted subnet)."
                )
    except socket.gaierror:
        # Non-resolvable host; httpx will fail connection naturally
        pass


async def _do_dispatch_webhook(session: AsyncSession, delivery_id_str: str) -> bool:
    """Internal implementation of webhook dispatching."""
    delivery_id = uuid.UUID(delivery_id_str)

    stmt = (
        select(WebhookDelivery)
        .options(selectinload(WebhookDelivery.subscription))
        .where(WebhookDelivery.id == delivery_id)
    )
    result = await session.execute(stmt)
    delivery = result.scalar_one_or_none()

    if not delivery:
        logger.error("webhook_delivery_not_found", delivery_id=delivery_id_str)
        return False

    subscription = delivery.subscription
    delivery.attempt_count += 1
    delivery.last_attempt_at = datetime.now(UTC)

    # Runtime SSRF Guard Check (Vibe Block 26) with DNS Rebinding Protection
    try:
        await check_runtime_ssrf(subscription.target_url)
    except ValueError as exc:
        delivery.status = "DLQ"
        delivery.error_detail = f"SSRF security violation: {exc}"
        delivery.next_retry_at = None
        await session.commit()
        logger.error(
            "webhook_ssrf_blocked",
            delivery_id=delivery_id_str,
            target_url=subscription.target_url,
            error=str(exc),
        )
        return False

    payload_bytes = json.dumps(delivery.payload, sort_keys=True, default=str).encode("utf-8")
    signature = generate_hmac_signature(subscription.secret, payload_bytes)

    headers = {
        "Content-Type": "application/json",
        "X-PulseEngine-Signature": f"sha256={signature}",
        "X-PulseEngine-Event": delivery.event_type,
        "X-PulseEngine-Delivery-ID": delivery_id_str,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            response = await client.post(
                subscription.target_url,
                content=payload_bytes,
                headers=headers,
            )
            delivery.response_status_code = response.status_code
            response.raise_for_status()

        delivery.status = "DELIVERED"
        delivery.error_detail = None
        await session.commit()
        logger.info("webhook_delivered_successfully", delivery_id=delivery_id_str, target_url=subscription.target_url)
        return True

    except Exception as exc:
        delivery.error_detail = str(exc)
        if delivery.attempt_count >= settings.WEBHOOK_MAX_RETRIES:
            delivery.status = "DLQ"
            delivery.next_retry_at = None
            await session.commit()
            logger.error(
                "webhook_delivery_moved_to_dlq",
                delivery_id=delivery_id_str,
                attempts=delivery.attempt_count,
                error=str(exc),
            )
            return False
        else:
            delivery.status = "FAILED"
            backoff_idx = min(delivery.attempt_count - 1, len(settings.WEBHOOK_RETRY_BACKOFF) - 1)
            retry_delay = settings.WEBHOOK_RETRY_BACKOFF[backoff_idx]
            delivery.next_retry_at = datetime.now(UTC) + timedelta(seconds=retry_delay)
            await session.commit()
            raise exc


async def _dispatch_webhook_async(delivery_id_str: str, session: AsyncSession | None = None) -> bool:
    """Core async worker logic for sending HMAC-signed webhook and tracking delivery/DLQ status."""
    if session is not None:
        return await _do_dispatch_webhook(session, delivery_id_str)
    async with async_session_factory() as sess:
        return await _do_dispatch_webhook(sess, delivery_id_str)


@celery_app.task(
    bind=True,
    max_retries=3,
    acks_late=True,
)
def dispatch_webhook(self, delivery_id: str) -> None:
    """Celery task executing webhook delivery with exponential backoff and DLQ routing."""
    try:
        asyncio.run(_dispatch_webhook_async(delivery_id))
    except Exception as exc:
        retries = self.request.retries
        backoff_idx = min(retries, len(settings.WEBHOOK_RETRY_BACKOFF) - 1)
        countdown = settings.WEBHOOK_RETRY_BACKOFF[backoff_idx]
        logger.warning(
            "webhook_retrying",
            delivery_id=delivery_id,
            attempt=retries + 1,
            retry_in_seconds=countdown,
        )
        raise self.retry(exc=exc, countdown=countdown)


async def _trigger_webhooks_for_transaction_async(
    transaction_id_str: str,
    account_ids_str: list[str],
    event_type: str,
    session: AsyncSession | None = None,
) -> list[str]:
    """Find active webhook subscriptions for affected accounts and generate delivery records."""
    account_uuids = [uuid.UUID(aid) for aid in account_ids_str]
    tx_uuid = uuid.UUID(transaction_id_str)
    spawned_delivery_ids: list[str] = []

    async def _process(sess: AsyncSession):
        stmt = select(WebhookSubscription).where(
            WebhookSubscription.account_id.in_(account_uuids),
            WebhookSubscription.is_active.is_(True),
        )
        result = await sess.execute(stmt)
        subscriptions = list(result.scalars().all())

        for sub in subscriptions:
            if event_type in sub.event_types or "*" in sub.event_types:
                delivery = WebhookDelivery(
                    subscription_id=sub.id,
                    transaction_id=tx_uuid,
                    event_type=event_type,
                    payload={
                        "event": event_type,
                        "transaction_id": transaction_id_str,
                        "account_id": str(sub.account_id),
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                    status="PENDING",
                )
                sess.add(delivery)
                await sess.flush()
                spawned_delivery_ids.append(str(delivery.id))

        await sess.commit()

    if session is not None:
        await _process(session)
    else:
        async with async_session_factory() as sess:
            await _process(sess)

    return spawned_delivery_ids


def trigger_webhooks_for_transaction(
    transaction_id: str,
    account_ids: list[str],
    event_type: str = "transaction.completed",
) -> None:
    """Post-commit trigger to schedule webhook deliveries via Celery (safe on or off event loop)."""
    try:
        try:
            loop = asyncio.get_running_loop()
            async def _bg_task():
                d_ids = await _trigger_webhooks_for_transaction_async(transaction_id, account_ids, event_type)
                for d_id in d_ids:
                    dispatch_webhook.delay(d_id)
            loop.create_task(_bg_task())
        except RuntimeError:
            delivery_ids = asyncio.run(
                _trigger_webhooks_for_transaction_async(transaction_id, account_ids, event_type)
            )
            for d_id in delivery_ids:
                dispatch_webhook.delay(d_id)
    except Exception as exc:
        logger.warning("trigger_webhooks_failed", error=str(exc))


@celery_app.task
def run_nightly_reconciliation() -> None:
    """Celery scheduled task running nightly financial audit."""
    async def _run():
        async with async_session_factory() as session:
            await run_reconciliation(session)

    asyncio.run(_run())
