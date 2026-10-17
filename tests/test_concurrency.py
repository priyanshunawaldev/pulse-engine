import asyncio
from decimal import Decimal

import httpx
import pytest


@pytest.mark.asyncio
async def test_concurrent_debits_no_overdraft(client: httpx.AsyncClient, auth_headers: dict[str, str]):
    """
    CRITICAL RACE CONDITION TEST:
    Fund an account with exactly $100.0000.
    Fire 20 concurrent $10.0000 debit requests simultaneously.
    Under race condition bugs, lost updates occur and the account could overdraft into negative.
    With Distributed Locking + DB consistency:
    - EXACTLY 10 requests must succeed with 200 OK.
    - EXACTLY 10 requests must fail with 422 Unprocessable Entity (Insufficient Funds).
    - Final balance must be EXACTLY $0.0000.
    """
    # 1. Create source account with $100.0000
    source = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Hot Wallet", "currency": "USD", "initial_balance": "100.0000"},
        headers=auth_headers,
    )).json()

    # Destination account
    dest = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Cold Storage", "currency": "USD", "initial_balance": "0.0000"},
        headers=auth_headers,
    )).json()

    source_id = source["id"]
    dest_id = dest["id"]

    # 2. Fire 20 concurrent debit requests with unique idempotency keys
    async def _post_debit(idx: int):
        return await client.post(
            "/v1/transactions",
            json={
                "idempotency_key": f"tx_concurrent_race_{idx}",
                "description": f"Concurrent debit #{idx}",
                "entries": [
                    {"account_id": source_id, "amount": "-10.0000", "entry_type": "DEBIT"},
                    {"account_id": dest_id, "amount": "10.0000", "entry_type": "CREDIT"},
                ],
            },
            headers=auth_headers,
        )

    tasks = [_post_debit(i) for i in range(20)]
    responses = await asyncio.gather(*tasks)

    successes = [r for r in responses if r.status_code == 200]
    failures = [r for r in responses if r.status_code == 422]

    # Verification: EXACTLY 10 successes and 10 failures
    assert len(successes) == 10, f"Expected 10 successes, got {len(successes)}"
    assert len(failures) == 10, f"Expected 10 failures, got {len(failures)}"

    # Verification: Final balance must be strictly 0.0000 (no overdraft, no lost update)
    final_source_bal = Decimal((await client.get(f"/v1/accounts/{source_id}", headers=auth_headers)).json()["balance"])
    final_dest_bal = Decimal((await client.get(f"/v1/accounts/{dest_id}", headers=auth_headers)).json()["balance"])

    assert final_source_bal == Decimal("0.0000")
    assert final_dest_bal == Decimal("100.0000")


@pytest.mark.asyncio
async def test_bidirectional_transfers_no_deadlock(client: httpx.AsyncClient, auth_headers: dict[str, str]):
    """
    CRITICAL DISTRIBUTED DEADLOCK TEST:
    Worker 1 transfers from Account A to Account B.
    Worker 2 simultaneously transfers from Account B to Account A.
    Without global lock ordering, Worker 1 locks A (waiting for B) while Worker 2 locks B (waiting for A),
    creating a circular wait deadlock.
    With Ascending UUID Lock Ordering, both workers acquire locks in the exact same order,
    eliminating deadlocks.
    """
    acc_a = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Peer A", "currency": "USD", "initial_balance": "500.0000"},
        headers=auth_headers,
    )).json()
    acc_b = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Peer B", "currency": "USD", "initial_balance": "500.0000"},
        headers=auth_headers,
    )).json()

    a_id = acc_a["id"]
    b_id = acc_b["id"]

    async def transfer_a_to_b(idx: int):
        return await client.post(
            "/v1/transactions",
            json={
                "idempotency_key": f"tx_deadlock_a_to_b_{idx}",
                "entries": [
                    {"account_id": a_id, "amount": "-15.0000", "entry_type": "DEBIT"},
                    {"account_id": b_id, "amount": "15.0000", "entry_type": "CREDIT"},
                ],
            },
            headers=auth_headers,
        )

    async def transfer_b_to_a(idx: int):
        return await client.post(
            "/v1/transactions",
            json={
                "idempotency_key": f"tx_deadlock_b_to_a_{idx}",
                "entries": [
                    {"account_id": b_id, "amount": "-15.0000", "entry_type": "DEBIT"},
                    {"account_id": a_id, "amount": "15.0000", "entry_type": "CREDIT"},
                ],
            },
            headers=auth_headers,
        )

    # Run 10 interleaved cross-transfers concurrently
    tasks = []
    for i in range(5):
        tasks.append(transfer_a_to_b(i))
        tasks.append(transfer_b_to_a(i))

    responses = await asyncio.gather(*tasks)

    # All 10 requests should complete cleanly with 200 OK and no deadlock timeouts
    for r in responses:
        assert r.status_code == 200

    bal_a = Decimal((await client.get(f"/v1/accounts/{a_id}", headers=auth_headers)).json()["balance"])
    bal_b = Decimal((await client.get(f"/v1/accounts/{b_id}", headers=auth_headers)).json()["balance"])

    # 5 transfers each way = balances should return to $500.0000
    assert bal_a == Decimal("500.0000")
    assert bal_b == Decimal("500.0000")
