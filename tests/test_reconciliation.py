import uuid
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from app.models.account import Account
from app.services.reconciliation_service import run_reconciliation


@pytest.mark.asyncio
async def test_reconciliation_matched_audit(client: httpx.AsyncClient, auth_headers: dict[str, str], test_db):
    acc_a = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Recon User A", "currency": "USD", "initial_balance": "0.0000"},
        headers=auth_headers,
    )).json()
    await client.post(
        "/v1/accounts",
        json={"owner_name": "Recon User B", "currency": "USD", "initial_balance": "0.0000"},
        headers=auth_headers,
    )

    # Credit acc_a with $100 and debit acc_b with $100
    # Wait, in ledger entry sign matches type:
    # A has +100, B has -100 (balance non-negative ck applies to accounts, so start B with 100 first)
    # Let's post transaction
    acc_source = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Funder", "currency": "USD", "initial_balance": "500.0000"},
        headers=auth_headers,
    )).json()

    await client.post(
        "/v1/transactions",
        json={
            "idempotency_key": "tx_recon_matched",
            "entries": [
                {"account_id": acc_source["id"], "amount": "-100.0000", "entry_type": "DEBIT"},
                {"account_id": acc_a["id"], "amount": "100.0000", "entry_type": "CREDIT"},
            ],
        },
        headers=auth_headers,
    )

    # With initial_balance tracking, both acc_a and acc_source reconcile to exact MATCHED status!
    audits = await run_reconciliation(test_db)
    acc_a_audit = next(a for a in audits if str(a.account_id) == acc_a["id"])
    acc_source_audit = next(a for a in audits if str(a.account_id) == acc_source["id"])

    assert acc_a_audit.status == "MATCHED"
    assert acc_a_audit.discrepancy == Decimal("0.0000")
    assert acc_a_audit.snapshot_balance == Decimal("100.0000")
    assert acc_a_audit.calculated_balance == Decimal("100.0000")

    assert acc_source_audit.status == "MATCHED"
    assert acc_source_audit.discrepancy == Decimal("0.0000")
    assert acc_source_audit.snapshot_balance == Decimal("400.0000")
    assert acc_source_audit.calculated_balance == Decimal("400.0000")


@pytest.mark.asyncio
async def test_reconciliation_detects_discrepancy_and_never_auto_mutates(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    test_db,
):
    """
    REGULATORY COMPLIANCE TEST:
    If an account snapshot balance is tampered with or desynchronized:
    1. Reconciliation detects the discrepancy.
    2. Status is flagged as 'DISCREPANCY_ALERT'.
    3. ZERO AUTO-MUTATION: the balance is NEVER silently altered or overwritten.
    """
    acc = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Tampered Account", "currency": "USD", "initial_balance": "0.0000"},
        headers=auth_headers,
    )).json()
    acc_id = acc["id"]

    # Post a transaction of $50
    funder = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Funder", "currency": "USD", "initial_balance": "200.0000"},
        headers=auth_headers,
    )).json()

    await client.post(
        "/v1/transactions",
        json={
            "idempotency_key": "tx_tamper_setup",
            "entries": [
                {"account_id": funder["id"], "amount": "-50.0000", "entry_type": "DEBIT"},
                {"account_id": acc_id, "amount": "50.0000", "entry_type": "CREDIT"},
            ],
        },
        headers=auth_headers,
    )

    # Intentionally tamper with account snapshot balance directly in DB to simulate discrepancy
    acc_uuid = uuid.UUID(acc_id)
    stmt = select(Account).where(Account.id == acc_uuid)
    result = await test_db.execute(stmt)
    account_row = result.scalar_one()
    # Legitimate balance is 50.0000; tamper to 999.0000
    account_row.balance = Decimal("999.0000")
    await test_db.commit()

    # Run reconciliation audit
    audits = await run_reconciliation(test_db)
    tampered_audit = next(a for a in audits if a.account_id == acc_uuid)

    # Verification: Discrepancy is flagged
    assert tampered_audit.status == "DISCREPANCY_ALERT"
    assert tampered_audit.snapshot_balance == Decimal("999.0000")
    assert tampered_audit.calculated_balance == Decimal("50.0000")
    assert tampered_audit.discrepancy == Decimal("949.0000")

    # CRITICAL: Verify balance was NOT auto-corrected/mutated
    stmt_check = select(Account).where(Account.id == acc_uuid)
    recheck_row = (await test_db.execute(stmt_check)).scalar_one()
    assert recheck_row.balance == Decimal("999.0000")
