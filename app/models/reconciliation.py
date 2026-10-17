import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid7_gen


class ReconciliationAudit(Base):
    __tablename__ = "reconciliation_audits"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7_gen)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    snapshot_balance: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    calculated_balance: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    discrepancy: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # MATCHED | DISCREPANCY_ALERT
    details: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_reconciliation_status_date", "status", "created_at"),
    )
