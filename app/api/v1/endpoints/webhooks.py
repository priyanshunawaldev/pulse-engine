import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_current_auth, get_db
from app.models.account import Account
from app.models.webhook import WebhookDelivery, WebhookSubscription
from app.schemas.webhook import (
    WebhookDeliveryListResponseSchema,
    WebhookDeliveryResponseSchema,
    WebhookSubscriptionCreateSchema,
    WebhookSubscriptionListResponseSchema,
    WebhookSubscriptionResponseSchema,
    mask_webhook_secret,
)
from app.services.ledger_service import decode_cursor, encode_cursor

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("", response_model=WebhookSubscriptionResponseSchema, status_code=status.HTTP_201_CREATED, summary="Create Webhook Subscription")
async def create_webhook_subscription(
    payload: WebhookSubscriptionCreateSchema,
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_current_auth),
) -> WebhookSubscriptionResponseSchema:
    """Register a new HMAC-signed webhook subscription scoped to an account."""
    # Verify account exists
    stmt = select(Account).where(Account.id == payload.account_id)
    res = await session.execute(stmt)
    if not res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account '{payload.account_id}' does not exist.",
        )

    # Generate dedicated HMAC secret for this subscription
    secret = f"whsec_{secrets.token_hex(24)}"

    subscription = WebhookSubscription(
        account_id=payload.account_id,
        target_url=payload.target_url,
        event_types=payload.event_types,
        secret=secret,
        is_active=True,
    )
    session.add(subscription)
    await session.commit()
    await session.refresh(subscription)

    return WebhookSubscriptionResponseSchema.model_validate(subscription)


@router.get("", response_model=WebhookSubscriptionListResponseSchema, summary="List Webhook Subscriptions")
async def list_webhook_subscriptions(
    account_id: uuid.UUID | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_current_auth),
) -> WebhookSubscriptionListResponseSchema:
    """List webhook subscriptions with optional account filtering."""
    stmt = select(WebhookSubscription).order_by(
        WebhookSubscription.id.desc(),
    ).limit(limit + 1)

    if account_id:
        stmt = stmt.where(WebhookSubscription.account_id == account_id)

    if cursor:
        cursor_id = decode_cursor(cursor)
        stmt = stmt.where(WebhookSubscription.id < cursor_id)

    result = await session.execute(stmt)
    subscriptions = list(result.scalars().all())

    has_more = len(subscriptions) > limit
    items = subscriptions[:limit]

    next_cursor = None
    if has_more and items:
        next_cursor = encode_cursor(items[-1].id)

    return WebhookSubscriptionListResponseSchema(
        items=[
            WebhookSubscriptionResponseSchema.model_validate(s).model_copy(
                update={"secret": mask_webhook_secret(s.secret)}
            )
            for s in items
        ],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Deactivate Webhook Subscription")
async def deactivate_webhook_subscription(
    subscription_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_current_auth),
) -> None:
    """Deactivate a webhook subscription to cease future deliveries."""
    stmt = select(WebhookSubscription).where(WebhookSubscription.id == subscription_id)
    result = await session.execute(stmt)
    sub = result.scalar_one_or_none()

    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook subscription not found.")

    sub.is_active = False
    await session.commit()


@router.get("/{subscription_id}/deliveries", response_model=WebhookDeliveryListResponseSchema, summary="Get Delivery History & DLQ")
async def get_subscription_deliveries(
    subscription_id: uuid.UUID,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_current_auth),
) -> WebhookDeliveryListResponseSchema:
    """Get delivery history and dead-letter queue records for a webhook subscription."""
    stmt = (
        select(WebhookDelivery)
        .where(WebhookDelivery.subscription_id == subscription_id)
        .order_by(WebhookDelivery.id.desc())
        .limit(limit + 1)
    )

    if status_filter:
        stmt = stmt.where(WebhookDelivery.status == status_filter.upper())

    if cursor:
        cursor_id = decode_cursor(cursor)
        stmt = stmt.where(WebhookDelivery.id < cursor_id)

    result = await session.execute(stmt)
    deliveries = list(result.scalars().all())

    has_more = len(deliveries) > limit
    items = deliveries[:limit]

    next_cursor = None
    if has_more and items:
        next_cursor = encode_cursor(items[-1].id)

    return WebhookDeliveryListResponseSchema(
        items=[WebhookDeliveryResponseSchema.model_validate(d) for d in items],
        next_cursor=next_cursor,
        has_more=has_more,
    )
