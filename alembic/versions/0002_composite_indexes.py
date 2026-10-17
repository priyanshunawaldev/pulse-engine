"""Add composite B-tree indexes for cursor pagination

Revision ID: 0002_composite_indexes
Revises: 0001_initial_schema
Create Date: 2026-10-17 14:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_composite_indexes"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_ledger_entries_account_id_id_desc",
        "ledger_entries",
        ["account_id", sa.text("id DESC")],
    )
    op.create_index(
        "ix_webhook_deliveries_subscription_id_id_desc",
        "webhook_deliveries",
        ["subscription_id", sa.text("id DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_webhook_deliveries_subscription_id_id_desc", table_name="webhook_deliveries")
    op.drop_index("ix_ledger_entries_account_id_id_desc", table_name="ledger_entries")
