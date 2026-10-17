"""
PulseEngine Locust Load & Stress Testing Suite.

Targets high-concurrency ledger operations:
- Double-entry atomic balance mutations
- Deadlock-free Redis distributed locks under contention
- DB-backed idempotency replay caching
- High-throughput balance read queries

Target Performance:
- 1,000+ requests per second
- sub-40ms p95 latency on balanced transfers
"""

import os
import random
import uuid

import structlog
from locust import HttpUser, between, events, tag, task

logger = structlog.get_logger(__name__)


class LedgerUser(HttpUser):
    # Minimal wait time to simulate high-throughput ingestion (>1,000 req/sec)
    wait_time = between(0.001, 0.005)

    def on_start(self) -> None:
        """Initialize authentication and prepare working accounts for load simulation."""
        self.api_key = os.getenv("PULSEENGINE_API_KEY", "")
        self.headers = {"Content-Type": "application/json"}

        # 1. Acquire API Key if not provided in environment
        if not self.api_key:
            resp = self.client.post(
                "/v1/auth/api-keys",
                json={"name": f"Locust-Runner-{uuid.uuid4().hex[:6]}"},
                headers=self.headers,
                name="/v1/auth/api-keys (Setup)",
            )
            if resp.status_code == 201:
                self.api_key = resp.json()["api_key"]
            else:
                self.api_key = "pk_live_default_locust_key"

        self.headers["X-API-Key"] = self.api_key

        # 2. Seed accounts for this worker
        self.account_ids: list[str] = []
        for _ in range(3):
            acc_resp = self.client.post(
                "/v1/accounts",
                json={
                    "owner_name": f"Locust Account {uuid.uuid4().hex[:8]}",
                    "currency": "USD",
                    "initial_balance": "1000000.0000",
                },
                headers=self.headers,
                name="/v1/accounts (Setup)",
            )
            if acc_resp.status_code == 201:
                self.account_ids.append(acc_resp.json()["id"])

        self.last_posted_payload: dict | None = None
        self.last_posted_key: str | None = None

    @tag("transfers")
    @task(6)
    def transfer_funds(self) -> None:
        """Simulate high-throughput 2-legged balanced transfers across random account pairs."""
        if len(self.account_ids) < 2:
            return

        source, dest = random.sample(self.account_ids, 2)
        amount = f"{random.randint(1, 50):.4f}"
        idempotency_key = f"locust_tx_{uuid.uuid4()}"

        payload = {
            "idempotency_key": idempotency_key,
            "description": "Locust synthetic transfer",
            "entries": [
                {"account_id": source, "amount": f"-{amount}", "entry_type": "DEBIT"},
                {"account_id": dest, "amount": amount, "entry_type": "CREDIT"},
            ],
        }

        with self.client.post(
            "/v1/transactions",
            json=payload,
            headers={**self.headers, "Idempotency-Key": idempotency_key},
            name="/v1/transactions [Create Transfer]",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 201):
                resp.success()
                self.last_posted_payload = payload
                self.last_posted_key = idempotency_key
            else:
                resp.failure(f"Transfer failed with status {resp.status_code}: {resp.text}")

    @tag("idempotency")
    @task(1)
    def replay_idempotent_transfer(self) -> None:
        """Simulate duplicate event ingestion with identical payload and key (assert 200/201 replay)."""
        if not self.last_posted_payload or not self.last_posted_key:
            return

        with self.client.post(
            "/v1/transactions",
            json=self.last_posted_payload,
            headers={**self.headers, "Idempotency-Key": self.last_posted_key},
            name="/v1/transactions [Idempotent Replay]",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 201):
                resp.success()
            else:
                resp.failure(f"Idempotent replay failed with status {resp.status_code}: {resp.text}")

    @tag("reads")
    @task(3)
    def check_account_balance(self) -> None:
        """Read account balance to test read scalability under active ledger writes."""
        if not self.account_ids:
            return

        acc_id = random.choice(self.account_ids)
        with self.client.get(
            f"/v1/accounts/{acc_id}",
            headers=self.headers,
            name="/v1/accounts/{id} [Get Balance]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Get account failed: {resp.status_code}")

    @tag("reads")
    @task(1)
    def list_transactions(self) -> None:
        """Cursor pagination query across recent transactions."""
        with self.client.get(
            "/v1/transactions?limit=25",
            headers=self.headers,
            name="/v1/transactions [List Cursor]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"List transactions failed: {resp.status_code}")

    @tag("health")
    @task(1)
    def health_check(self) -> None:
        """Readiness probe checking Redis & DB health."""
        with self.client.get(
            "/health/ready",
            name="/health/ready",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Readiness check failed: {resp.status_code}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs) -> None:
    """Print high-level latency summary when Locust stops."""
    total_reqs = environment.stats.total.num_requests
    p95 = environment.stats.total.get_response_time_percentile(0.95)
    print(f"\n[Locust Summary] Total Requests: {total_reqs} | p95 Latency: {p95:.2f}ms")
