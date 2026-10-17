"""Initial schema for PulseEngine ledger

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-17 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Accounts
    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_number", sa.String(length=32), nullable=False),
        sa.Column("owner_name", sa.String(length=128), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("initial_balance", sa.Numeric(precision=18, scale=4), nullable=False, server_default="0.0000"),
        sa.Column("balance", sa.Numeric(precision=18, scale=4), nullable=False, server_default="0.0000"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("balance >= 0", name="ck_account_non_negative_balance"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_number"),
    )
    op.create_index("ix_accounts_account_number", "accounts", ["account_number"])
    op.create_index("ix_accounts_currency_status", "accounts", ["currency", "status"])

    # 2. Transactions
    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="COMPLETED"),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_transactions_idempotency_key", "transactions", ["idempotency_key"])

    # 3. Ledger Entries
    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("entry_type", sa.String(length=10), nullable=False),
        sa.Column("running_balance", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "(entry_type = 'DEBIT' AND amount < 0) OR (entry_type = 'CREDIT' AND amount > 0)",
            name="ck_ledger_entry_sign_matches_type",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ledger_entries_account_id", "ledger_entries", ["account_id"])
    op.create_index("ix_ledger_entries_transaction_id", "ledger_entries", ["transaction_id"])
    op.create_index("ix_ledger_account_created", "ledger_entries", ["account_id", "created_at"])

    # 4. Idempotency Records
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PROCESSING"),
        sa.Column("response_status_code", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_idempotency_records_idempotency_key", "idempotency_records", ["idempotency_key"])
    op.create_index("ix_idempotency_key_status", "idempotency_records", ["idempotency_key", "status"])

    # 5. Webhook Subscriptions
    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("target_url", sa.String(length=512), nullable=False),
        sa.Column("event_types", sa.JSON(), nullable=False),
        sa.Column("secret", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_webhook_subscriptions_account_id", "webhook_subscriptions", ["account_id"])

    # 6. Webhook Deliveries
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("response_status_code", sa.Integer(), nullable=True),
        sa.Column("error_detail", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["subscription_id"], ["webhook_subscriptions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_webhook_deliveries_subscription_id", "webhook_deliveries", ["subscription_id"])
    op.create_index("ix_webhook_deliveries_transaction_id", "webhook_deliveries", ["transaction_id"])
    op.create_index("ix_webhook_deliveries_status_retry", "webhook_deliveries", ["status", "next_retry_at"])

    # 7. Auth: API Keys & Clients
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"])

    op.create_table(
        "auth_clients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("client_secret_hash", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id"),
    )
    op.create_index("ix_auth_clients_client_id", "auth_clients", ["client_id"])

    # 8. Reconciliation Audits
    op.create_table(
        "reconciliation_audits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_balance", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("calculated_balance", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("discrepancy", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("details", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reconciliation_audits_account_id", "reconciliation_audits", ["account_id"])
    op.create_index("ix_reconciliation_status_date", "reconciliation_audits", ["status", "created_at"])


def downgrade() -> None:
    op.drop_table("reconciliation_audits")
    op.drop_table("auth_clients")
    op.drop_table("api_keys")
    op.drop_table("webhook_deliveries")
    op.drop_table("webhook_subscriptions")
    op.drop_table("idempotency_records")
    op.drop_table("ledger_entries")
    op.drop_table("transactions")
    op.drop_table("accounts")
