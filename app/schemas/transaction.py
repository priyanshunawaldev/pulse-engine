import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.transaction import TransactionStatus
from app.schemas.account import LedgerEntryResponseSchema


class EntryCreateSchema(BaseModel):
    account_id: uuid.UUID
    amount: Decimal = Field(..., decimal_places=4)
    entry_type: str = Field(..., pattern="^(DEBIT|CREDIT)$")

    @model_validator(mode="after")
    def validate_sign_and_type(self) -> "EntryCreateSchema":
        if self.entry_type == "DEBIT" and self.amount >= Decimal("0"):
            raise ValueError("DEBIT amount must be strictly negative (e.g. -100.0000)")
        if self.entry_type == "CREDIT" and self.amount <= Decimal("0"):
            raise ValueError("CREDIT amount must be strictly positive (e.g. 100.0000)")
        return self


class TransactionCreateSchema(BaseModel):
    idempotency_key: str = Field(..., min_length=1, max_length=128, json_schema_extra={"example": "tx_order_12345"})
    description: str | None = Field(None, max_length=255, json_schema_extra={"example": "Transfer from checking to savings"})
    entries: list[EntryCreateSchema] = Field(..., min_length=2)
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_double_entry(self) -> "TransactionCreateSchema":
        total = sum((entry.amount for entry in self.entries), Decimal("0.0000"))
        if total != Decimal("0.0000"):
            raise ValueError(f"Double-entry bookkeeping invariant violated: sum of entries must equal 0.0000, got {total}")
        return self


class TransactionResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    idempotency_key: str
    description: str | None
    status: TransactionStatus
    metadata: dict[str, Any] | None = Field(default=None, alias="metadata_")
    created_at: datetime
    entries: list[LedgerEntryResponseSchema] = []


class TransactionListResponseSchema(BaseModel):
    items: list[TransactionResponseSchema]
    next_cursor: str | None = None
    has_more: bool = False
