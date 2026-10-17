import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.models.base import Base, uuid7_gen

JSONType = JSONB().with_variant(JSON(), "sqlite")


class TransactionStatus(enum.StrEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REVERSED = "REVERSED"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7_gen)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus, native_enum=False),
        default=TransactionStatus.COMPLETED,
        nullable=False,
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    entries: Mapped[list["LedgerEntry"]] = relationship(
        "LedgerEntry",
        back_populates="transaction",
        cascade="all, delete-orphan",
        order_by="LedgerEntry.created_at",
    )


class LedgerEntry(Base):
    """
    Double-entry ledger entry:
    - Debits carry negative amounts (amount < 0)
    - Credits carry positive amounts (amount > 0)
    - Sum across all entries in a transaction MUST be 0.
    """
    __tablename__ = "ledger_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7_gen)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "DEBIT" | "CREDIT"
    running_balance: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    transaction = relationship("Transaction", back_populates="entries")
    account = relationship("Account", back_populates="ledger_entries")

    __table_args__ = (
        Index("ix_ledger_account_created", "account_id", "created_at"),
        CheckConstraint(
            "(entry_type = 'DEBIT' AND amount < 0) OR (entry_type = 'CREDIT' AND amount > 0)",
            name="ck_ledger_entry_sign_matches_type",
        ),
    )
