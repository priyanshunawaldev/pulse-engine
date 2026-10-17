from decimal import Decimal

import httpx
import pytest


@pytest.mark.asyncio
async def test_create_and_get_account(client: httpx.AsyncClient, auth_headers: dict[str, str]):
    # 1. Create account
    create_resp = await client.post(
        "/v1/accounts",
        json={
            "owner_name": "Satoshi Nakamoto",
            "currency": "USD",
            "initial_balance": "500.0000",
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert data["owner_name"] == "Satoshi Nakamoto"
    assert data["currency"] == "USD"
    assert Decimal(data["balance"]) == Decimal("500.0000")
    assert data["status"] == "ACTIVE"
    account_id = data["id"]

    # 2. Get account by ID
    get_resp = await client.get(f"/v1/accounts/{account_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["id"] == account_id
    assert get_data["account_number"] == data["account_number"]


@pytest.mark.asyncio
async def test_post_balanced_transaction_two_accounts(client: httpx.AsyncClient, auth_headers: dict[str, str]):
    # Setup Account A ($200) and Account B ($50)
    acc_a = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Account Alpha", "currency": "USD", "initial_balance": "200.0000"},
        headers=auth_headers,
    )).json()
    acc_b = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Account Beta", "currency": "USD", "initial_balance": "50.0000"},
        headers=auth_headers,
    )).json()

    # Post balanced transaction: Transfer $75.5000 from A to B
    tx_resp = await client.post(
        "/v1/transactions",
        json={
            "idempotency_key": "tx_test_balanced_1",
            "description": "Wire transfer Alpha -> Beta",
            "entries": [
                {"account_id": acc_a["id"], "amount": "-75.5000", "entry_type": "DEBIT"},
                {"account_id": acc_b["id"], "amount": "75.5000", "entry_type": "CREDIT"},
            ],
            "metadata": {"channel": "SWIFT"},
        },
        headers=auth_headers,
    )
    assert tx_resp.status_code == 200
    tx_data = tx_resp.json()
    assert tx_data["status"] == "COMPLETED"
    assert len(tx_data["entries"]) == 2

    # Verify updated balances
    bal_a = Decimal((await client.get(f"/v1/accounts/{acc_a['id']}", headers=auth_headers)).json()["balance"])
    bal_b = Decimal((await client.get(f"/v1/accounts/{acc_b['id']}", headers=auth_headers)).json()["balance"])
    assert bal_a == Decimal("124.5000")
    assert bal_b == Decimal("125.5000")


@pytest.mark.asyncio
async def test_post_multi_entry_fan_out_transaction(client: httpx.AsyncClient, auth_headers: dict[str, str]):
    # Setup 1 source ($300) and 3 recipients ($0 each)
    source = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Corporate Payroll", "currency": "USD", "initial_balance": "300.0000"},
        headers=auth_headers,
    )).json()
    r1 = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Emp 1", "currency": "USD", "initial_balance": "0.0000"},
        headers=auth_headers,
    )).json()
    r2 = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Emp 2", "currency": "USD", "initial_balance": "0.0000"},
        headers=auth_headers,
    )).json()
    r3 = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Emp 3", "currency": "USD", "initial_balance": "0.0000"},
        headers=auth_headers,
    )).json()

    # Split $300 across 3 employees ($100 each)
    tx_resp = await client.post(
        "/v1/transactions",
        json={
            "idempotency_key": "tx_fan_out_batch_1",
            "description": "Monthly payroll distribution",
            "entries": [
                {"account_id": source["id"], "amount": "-300.0000", "entry_type": "DEBIT"},
                {"account_id": r1["id"], "amount": "100.0000", "entry_type": "CREDIT"},
                {"account_id": r2["id"], "amount": "100.0000", "entry_type": "CREDIT"},
                {"account_id": r3["id"], "amount": "100.0000", "entry_type": "CREDIT"},
            ],
        },
        headers=auth_headers,
    )
    assert tx_resp.status_code == 200

    assert Decimal((await client.get(f"/v1/accounts/{source['id']}", headers=auth_headers)).json()["balance"]) == Decimal("0.0000")
    for r in [r1, r2, r3]:
        assert Decimal((await client.get(f"/v1/accounts/{r['id']}", headers=auth_headers)).json()["balance"]) == Decimal("100.0000")


@pytest.mark.asyncio
async def test_reject_unbalanced_transaction(client: httpx.AsyncClient, auth_headers: dict[str, str]):
    acc_a = (await client.post(
        "/v1/accounts",
        json={"owner_name": "A", "currency": "USD", "initial_balance": "100.0000"},
        headers=auth_headers,
    )).json()
    acc_b = (await client.post(
        "/v1/accounts",
        json={"owner_name": "B", "currency": "USD", "initial_balance": "100.0000"},
        headers=auth_headers,
    )).json()

    # Unbalanced: -100.0000 + 80.0000 != 0
    resp = await client.post(
        "/v1/transactions",
        json={
            "idempotency_key": "tx_unbalanced_reject",
            "entries": [
                {"account_id": acc_a["id"], "amount": "-100.0000", "entry_type": "DEBIT"},
                {"account_id": acc_b["id"], "amount": "80.0000", "entry_type": "CREDIT"},
            ],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_reject_insufficient_funds_no_overdraft(client: httpx.AsyncClient, auth_headers: dict[str, str]):
    acc_a = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Poor User", "currency": "USD", "initial_balance": "25.0000"},
        headers=auth_headers,
    )).json()
    acc_b = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Merchant", "currency": "USD", "initial_balance": "0.0000"},
        headers=auth_headers,
    )).json()

    # Attempt to debit $100 from an account with only $25
    resp = await client.post(
        "/v1/transactions",
        json={
            "idempotency_key": "tx_overdraft_attempt",
            "entries": [
                {"account_id": acc_a["id"], "amount": "-100.0000", "entry_type": "DEBIT"},
                {"account_id": acc_b["id"], "amount": "100.0000", "entry_type": "CREDIT"},
            ],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422
    assert "insufficient funds" in resp.json()["detail"].lower()

    # Verify balance was NOT mutated
    bal_a = Decimal((await client.get(f"/v1/accounts/{acc_a['id']}", headers=auth_headers)).json()["balance"])
    assert bal_a == Decimal("25.0000")


@pytest.mark.asyncio
async def test_reject_cross_currency_transaction(client: httpx.AsyncClient, auth_headers: dict[str, str]):
    usd_acc = (await client.post(
        "/v1/accounts",
        json={"owner_name": "USD User", "currency": "USD", "initial_balance": "100.0000"},
        headers=auth_headers,
    )).json()
    eur_acc = (await client.post(
        "/v1/accounts",
        json={"owner_name": "EUR User", "currency": "EUR", "initial_balance": "100.0000"},
        headers=auth_headers,
    )).json()

    resp = await client.post(
        "/v1/transactions",
        json={
            "idempotency_key": "tx_cross_currency",
            "entries": [
                {"account_id": usd_acc["id"], "amount": "-50.0000", "entry_type": "DEBIT"},
                {"account_id": eur_acc["id"], "amount": "50.0000", "entry_type": "CREDIT"},
            ],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422
    assert "cross-currency" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reject_closed_account_transaction(client: httpx.AsyncClient, auth_headers: dict[str, str]):
    acc_a = (await client.post(
        "/v1/accounts",
        json={"owner_name": "To Close", "currency": "USD", "initial_balance": "100.0000"},
        headers=auth_headers,
    )).json()
    acc_b = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Receiver", "currency": "USD", "initial_balance": "100.0000"},
        headers=auth_headers,
    )).json()

    # Close account A
    close_resp = await client.patch(f"/v1/accounts/{acc_a['id']}/close", headers=auth_headers)
    assert close_resp.status_code == 200
    assert close_resp.json()["status"] == "CLOSED"

    # Attempt to transact from closed account
    tx_resp = await client.post(
        "/v1/transactions",
        json={
            "idempotency_key": "tx_closed_account",
            "entries": [
                {"account_id": acc_a["id"], "amount": "-10.0000", "entry_type": "DEBIT"},
                {"account_id": acc_b["id"], "amount": "10.0000", "entry_type": "CREDIT"},
            ],
        },
        headers=auth_headers,
    )
    assert tx_resp.status_code == 409
    assert "CLOSED" in tx_resp.json()["detail"]


@pytest.mark.asyncio
async def test_transaction_reversal_creates_equal_opposite_entries(client: httpx.AsyncClient, auth_headers: dict[str, str]):
    acc_a = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Reversal Sender", "currency": "USD", "initial_balance": "200.0000"},
        headers=auth_headers,
    )).json()
    acc_b = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Reversal Recipient", "currency": "USD", "initial_balance": "100.0000"},
        headers=auth_headers,
    )).json()

    # 1. Post initial transaction ($40 transfer)
    tx_resp = await client.post(
        "/v1/transactions",
        json={
            "idempotency_key": "tx_to_reverse_initial",
            "entries": [
                {"account_id": acc_a["id"], "amount": "-40.0000", "entry_type": "DEBIT"},
                {"account_id": acc_b["id"], "amount": "40.0000", "entry_type": "CREDIT"},
            ],
        },
        headers=auth_headers,
    )
    tx_id = tx_resp.json()["id"]

    # 2. Reverse the transaction
    rev_resp = await client.post(f"/v1/transactions/{tx_id}/reverse", headers=auth_headers)
    assert rev_resp.status_code == 200
    rev_data = rev_resp.json()
    assert rev_data["status"] == "COMPLETED"

    # Verify balances returned to exact initial amounts ($200 and $100)
    bal_a = Decimal((await client.get(f"/v1/accounts/{acc_a['id']}", headers=auth_headers)).json()["balance"])
    bal_b = Decimal((await client.get(f"/v1/accounts/{acc_b['id']}", headers=auth_headers)).json()["balance"])
    assert bal_a == Decimal("200.0000")
    assert bal_b == Decimal("100.0000")

    # Verify original transaction status is marked REVERSED
    orig_tx = (await client.get(f"/v1/transactions/{tx_id}", headers=auth_headers)).json()
    assert orig_tx["status"] == "REVERSED"

    # Attempting to reverse a second time must fail with 409 Conflict
    rev_again = await client.post(f"/v1/transactions/{tx_id}/reverse", headers=auth_headers)
    assert rev_again.status_code == 409


@pytest.mark.asyncio
async def test_account_ledger_audit_trail_and_cursor_pagination(client: httpx.AsyncClient, auth_headers: dict[str, str]):
    acc_a = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Audit User A", "currency": "USD", "initial_balance": "1000.0000"},
        headers=auth_headers,
    )).json()
    acc_b = (await client.post(
        "/v1/accounts",
        json={"owner_name": "Audit User B", "currency": "USD", "initial_balance": "100.0000"},
        headers=auth_headers,
    )).json()

    # Post 3 transactions
    for i in range(3):
        await client.post(
            "/v1/transactions",
            json={
                "idempotency_key": f"tx_audit_trail_{i}",
                "entries": [
                    {"account_id": acc_a["id"], "amount": "-10.0000", "entry_type": "DEBIT"},
                    {"account_id": acc_b["id"], "amount": "10.0000", "entry_type": "CREDIT"},
                ],
            },
            headers=auth_headers,
        )

    # Check ledger history with limit=2
    ledger_p1 = await client.get(f"/v1/accounts/{acc_a['id']}/ledger?limit=2", headers=auth_headers)
    assert ledger_p1.status_code == 200
    data_p1 = ledger_p1.json()
    assert len(data_p1["items"]) == 2
    assert data_p1["has_more"] is True
    assert data_p1["next_cursor"] is not None

    # Fetch next page using cursor
    cursor = data_p1["next_cursor"]
    ledger_p2 = await client.get(f"/v1/accounts/{acc_a['id']}/ledger?limit=2&cursor={cursor}", headers=auth_headers)
    assert ledger_p2.status_code == 200
    data_p2 = ledger_p2.json()
    assert len(data_p2["items"]) == 1
    assert data_p2["has_more"] is False


@pytest.mark.asyncio
async def test_list_accounts_and_transactions_endpoints(client: httpx.AsyncClient, auth_headers: dict[str, str]):
    # 1. Create two accounts first
    acc1 = (await client.post(
        "/v1/accounts",
        json={"owner_name": "List User 1", "currency": "USD", "initial_balance": "500.0000"},
        headers=auth_headers,
    )).json()
    acc2 = (await client.post(
        "/v1/accounts",
        json={"owner_name": "List User 2", "currency": "USD", "initial_balance": "100.0000"},
        headers=auth_headers,
    )).json()

    # Post a transaction
    await client.post(
        "/v1/transactions",
        json={
            "idempotency_key": "tx_list_test_key",
            "entries": [
                {"account_id": acc1["id"], "amount": "-25.0000", "entry_type": "DEBIT"},
                {"account_id": acc2["id"], "amount": "25.0000", "entry_type": "CREDIT"},
            ],
        },
        headers=auth_headers,
    )

    # 2. Test accounts list pagination
    accounts_resp = await client.get("/v1/accounts?limit=2", headers=auth_headers)
    assert accounts_resp.status_code == 200
    acc_data = accounts_resp.json()
    assert len(acc_data["items"]) == 2

    # 3. Test transactions list and detail
    tx_list = await client.get("/v1/transactions?limit=2", headers=auth_headers)
    assert tx_list.status_code == 200
    t_items = tx_list.json()["items"]
    assert len(t_items) == 1
    tx_id = t_items[0]["id"]

    tx_detail = await client.get(f"/v1/transactions/{tx_id}", headers=auth_headers)
    assert tx_detail.status_code == 200
    assert tx_detail.json()["id"] == tx_id
