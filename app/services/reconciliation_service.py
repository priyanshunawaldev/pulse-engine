from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.account import Account
from app.models.reconciliation import ReconciliationAudit
from app.models.transaction import LedgerEntry


async def run_reconciliation(session: AsyncSession) -> list[ReconciliationAudit]:
    """
    Nightly / Scheduled Financial Reconciliation Job:
    Audits snapshot account balances against calculated sum of all ledger entries.
    
    REGULATORY COMPLIANCE MANDATE (SOX 404 / PCI-DSS):
    - Balance discrepancies are logged as CRITICAL security/compliance alerts.
    - Discrepancies are permanently recorded in the reconciliation_audits table.
    - AUTOMATED MUTATION/BALANCING IS STRICTLY FORBIDDEN.
      Any automated overwrite of financial ledgers constitutes record tampering.
      Corrections must proceed through manual operator-reviewed journal adjustments.
    """
    logger.info("reconciliation_run_started")

    # Fetch all accounts
    stmt = select(Account)
    result = await session.execute(stmt)
    accounts = list(result.scalars().all())

    audits: list[ReconciliationAudit] = []

    for acc in accounts:
        # Sum all ledger entries for this account
        sum_stmt = select(func.coalesce(func.sum(LedgerEntry.amount), Decimal("0.0000"))).where(
            LedgerEntry.account_id == acc.id
        )
        sum_result = await session.execute(sum_stmt)
        calculated_balance = Decimal(str(sum_result.scalar_one()))
        snapshot_balance = Decimal(str(acc.balance))

        discrepancy = snapshot_balance - calculated_balance

        if discrepancy != Decimal("0.0000"):
            status = "DISCREPANCY_ALERT"
            logger.critical(
                "reconciliation_discrepancy_detected",
                account_id=str(acc.id),
                account_number=acc.account_number,
                snapshot_balance=str(snapshot_balance),
                calculated_balance=str(calculated_balance),
                discrepancy=str(discrepancy),
                action="MANUAL_OPERATOR_AUDIT_REQUIRED_NO_AUTO_CORRECTION",
            )
        else:
            status = "MATCHED"

        audit_entry = ReconciliationAudit(
            account_id=acc.id,
            snapshot_balance=snapshot_balance,
            calculated_balance=calculated_balance,
            discrepancy=discrepancy,
            status=status,
            details=f"Audit completed: discrepancy {discrepancy}",
        )
        session.add(audit_entry)
        audits.append(audit_entry)

    await session.commit()
    logger.info("reconciliation_run_completed", total_audited=len(audits))
    return audits
