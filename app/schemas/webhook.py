import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WebhookSubscriptionCreateSchema(BaseModel):
    account_id: uuid.UUID
    target_url: str = Field(..., max_length=512, json_schema_extra={"example": "https://api.example.com/webhooks/pulseengine"})
    event_types: list[str] = Field(
        default=["transaction.completed", "transaction.reversed"],
        min_length=1,
        json_schema_extra={"example": ["transaction.completed"]},
    )


class WebhookSubscriptionResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    target_url: str
    event_types: list[str]
    secret: str
    is_active: bool
    created_at: datetime


class WebhookSubscriptionListResponseSchema(BaseModel):
    items: list[WebhookSubscriptionResponseSchema]
    next_cursor: str | None = None
    has_more: bool = False


class WebhookDeliveryResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subscription_id: uuid.UUID
    transaction_id: uuid.UUID
    event_type: str
    payload: dict[str, Any]
    attempt_count: int
    last_attempt_at: datetime | None
    next_retry_at: datetime | None
    status: str
    response_status_code: int | None
    error_detail: str | None
    created_at: datetime


class WebhookDeliveryListResponseSchema(BaseModel):
    items: list[WebhookDeliveryResponseSchema]
    next_cursor: str | None = None
    has_more: bool = False
