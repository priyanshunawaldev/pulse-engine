import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.account import AccountStatus


class AccountCreateSchema(BaseModel):
    owner_name: str = Field(..., min_length=1, max_length=128, json_schema_extra={"example": "Alice Smith"})
    currency: str = Field(..., min_length=3, max_length=3, json_schema_extra={"example": "USD"})
    initial_balance: Decimal = Field(
        default=Decimal("0.0000"),
        ge=Decimal("0.0000"),
        decimal_places=4,
        json_schema_extra={"example": "100.0000"},
    )


class AccountResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_number: str
    owner_name: str
    currency: str
    balance: Decimal
    status: AccountStatus
    version: int
    created_at: datetime
    updated_at: datetime


class AccountListResponseSchema(BaseModel):
    items: list[AccountResponseSchema]
    next_cursor: str | None = None
    has_more: bool = False


class LedgerEntryResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    transaction_id: uuid.UUID
    account_id: uuid.UUID
    amount: Decimal
    entry_type: str
    running_balance: Decimal
    created_at: datetime


class LedgerEntryListResponseSchema(BaseModel):
    items: list[LedgerEntryResponseSchema]
    next_cursor: str | None = None
    has_more: bool = False
