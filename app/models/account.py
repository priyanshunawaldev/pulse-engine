import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Enum, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, uuid7_gen


class AccountStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    FROZEN = "FROZEN"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7_gen)
    account_number: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    owner_name: Mapped[str] = mapped_column(String(128), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)  # ISO 4217, e.g. "USD", "INR"
    initial_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        default=Decimal("0.0000"),
        nullable=False,
    )
    balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        default=Decimal("0.0000"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(default=1, nullable=False)  # For Optimistic Concurrency Control
    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, native_enum=False),
        default=AccountStatus.ACTIVE,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    ledger_entries = relationship("LedgerEntry", back_populates="account")
    webhook_subscriptions = relationship("WebhookSubscription", back_populates="account")

    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_account_non_negative_balance"),
        Index("ix_accounts_currency_status", "currency", "status"),
    )
    __mapper_args__ = {"version_id_col": version}
