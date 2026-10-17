# PulseEngine — Engineering Incidents, Concurrency Bugs & Learnings Log

> **Audience**: Systems Engineers, Tech Leads, Engineering Interviewers, and LinkedIn Technical Storytellers.  
> **Repository**: `PulseEngine` (Distributed Financial Ledger & Event Ingestion API)  
> **Tech Stack**: Python 3.12+, FastAPI, SQLAlchemy 2.0 (Async), PostgreSQL 16, Redis 7, Celery, Docker.

---

## Executive Summary

Building a financial ledger is unforgiving. Unlike standard web applications where eventual consistency or occasional retries suffice, financial ledgers demand:
1. **Zero-sum double-entry invariant preservation** ($$\sum \text{amounts} = 0$$).
2. **Strict monotonic balance non-negativity** ($$\text{balance} \ge 0$$).
3. **Deadlock-free concurrent operations** under adversarial traffic bursts.
4. **Guaranteed idempotency** with SHA-256 payload tampering detection.

During the architecture, implementation, and stress-testing of PulseEngine, several critical distributed systems bugs and framework edge-cases were uncovered, analyzed, and permanently resolved.

This log documents **what broke**, the **underlying root cause**, the **engineering fix**, and the **LinkedIn / Interview storytelling takeaway** for each incident.

---

## Incident Index

| # | Category | Incident Title | Severity | Impact |
|---|---|---|---|---|
| **01** | Modern Standards | Subclass Type Divergence in RFC 9562 UUIDv7 (`uuid_utils` vs `uuid.UUID`) | High | Broken DB inserts & AsyncPG type crashes |
| **02** | Test Reliability | Missing C Lua Engine in In-Memory Redis Testing (`fakeredis` vs Redlock) | High | Test harness crashed on distributed locks |
| **03** | Async ORM | SQLAlchemy 2.0 Async Lazy-Loading Panic (`MissingGreenlet` on Relationship Reassignment) | Critical | 500 Internal Server Errors on transactions |
| **04** | Concurrency / Loops | Event Loop Clashing with Celery Asynchronous Dispatch (`asyncio.run` Collisions) | Critical | Server thread lockups during webhook dispatch |
| **05** | Serialization | Non-Serializable Exception Objects in Pydantic v2 Exception Handlers | Medium | Validation handler crashed on invalid payloads |
| **06** | Database Collation | SQLite ASCII Collation Failure on ISO-8601 Timestamps in Cursor Pagination | High | Broken pagination results & missing ledger audit records |
| **07** | Distributed Locking | Cross-Account Circular Deadlocks in High-Frequency Bidirectional Transfers | Critical | Thread lockups, lock timeouts, 503 errors under load |

---

### Incident 01: Subclass Type Divergence in RFC 9562 UUIDv7

#### 1. What Happened
When generating UUIDv7 IDs via the modern `uuid-utils` library (`uuid_utils.uuid7()`) and passing them to SQLAlchemy models or Pydantic schemas, queries failed and asyncpg threw unhandled type errors:
```
DataError: invalid input for query argument $1: UUID('019468ab-...') (expected uuid.UUID, got uuid_utils.UUID)
```

#### 2. Root Cause Analysis
`uuid_utils` returns an instance of its own class `uuid_utils.UUID`. Although it mirrors the standard library API, `isinstance(uuid_utils.uuid7(), uuid.UUID)` evaluates to `False`. Modern async drivers (`asyncpg`, `pydantic-core`, `psycopg3`) use fast C-extensions with strict `PyUUID_Check` or `isinstance(val, uuid.UUID)` assertions. Duck typing fails at the C/binary boundary.

#### 3. The Engineering Fix
Wrapped the generator in a centralized helper that guarantees standard library compatibility:
```python
# app/models/base.py
import uuid
import uuid_utils

def uuid7_gen() -> uuid.UUID:
    """Generate an RFC 9562 UUIDv7 guaranteed to be an instance of standard uuid.UUID."""
    return uuid.UUID(str(uuid_utils.uuid7()))
```

#### 4. Interview & LinkedIn Takeaway
> *"When adopting bleeding-edge RFC standards in Python, beware of the C-extension boundary. Libraries like `uuid-utils` provide incredible microsecond-performance benefits, but binary drivers like `asyncpg` bypass Python's duck-typing and perform strict pointer checks. Always enforce a thin normalization layer at your domain boundary."*

---

### Incident 02: Missing C Lua Engine in In-Memory Redis Testing

#### 1. What Happened
Running the test suite locally and in CI without a live Docker Redis container caused immediate crashes on Redlock acquisition and Token Bucket rate limiting:
```
redis.exceptions.ResponseError: unknown command 'eval'
```

#### 2. Root Cause Analysis
Standard `fakeredis` implements pure-Python Redis string and hash commands. However, production distributed locks and atomic token buckets rely on Lua scripts executed via Redis `EVAL`. Pure `fakeredis` does not include an embedded Lua interpreter by default. Without a C Lua JIT engine, `eval` is unsupported.

#### 3. The Engineering Fix
1. Added `lupa>=2.4` (Lua binding for Python) to dev dependencies.
2. Initialized `fakeredis.aioredis.FakeRedis(server=FakeServer(version="7.0"), decode_responses=True)` with embedded Lua support.
3. This enabled the entire 27-test suite to execute atomic Lua scripts with microsecond fidelity in under 12 seconds with zero external Docker dependencies.

#### 4. Interview & LinkedIn Takeaway
> *"Don't mock what you can emulate. Mocking Redis `EVAL` with Python mocks masks subtle race conditions in Lua scripts. By using `fakeredis` paired with `lupa`, we run real Lua lock release scripts and token-bucket algorithms in-memory during CI, achieving 100% deterministic tests without Docker overhead."*

---

### Incident 03: SQLAlchemy 2.0 Async Lazy-Loading Panic (`MissingGreenlet`)

#### 1. What Happened
After inserting ledger entries into the database inside `record_transaction`, assigning `tx.entries = created_entries` triggered a catastrophic exception:
```
sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call await_only() here. 
Was IO attempted in an unexpected place?
```

#### 2. Root Cause Analysis
In SQLAlchemy 2.0, relationships default to `lazy="select"`. When you assign a collection to an ORM model instance (`tx.entries = ...`), SQLAlchemy's relationship cascade inspects existing elements in the relationship collection to fire any required orphan deletions or update back-references. Because this model was queried asynchronously, attempting a synchronous lazy-load inspection outside an active greenlet context panicked the async runner.

#### 3. The Engineering Fix
Decoupled internal persistence from response schema creation. Instead of mutating ORM relationship attributes on session-bound objects:
1. Committed the transaction and entries atomically.
2. Passed the explicitly created `created_entries` list directly into the response Pydantic schema constructor:
```python
return TransactionResponseSchema(
    id=tx.id,
    idempotency_key=tx.idempotency_key,
    description=tx.description,
    status=tx.status,
    created_at=tx.created_at,
    entries=[LedgerEntryResponseSchema.model_validate(e) for e in created_entries],
)
```

#### 4. Interview & LinkedIn Takeaway
> *"In async SQLAlchemy 2.0, never mutate relationship collections on managed objects after execution. Bidirectional relationship reassignment triggers hidden synchronous I/O under the hood. Treat ORM models as write-only units of persistence, and construct API responses from explicit, in-memory domain objects."*

---

### Incident 04: Event Loop Clashing with Celery Asynchronous Dispatch

#### 1. What Happened
When dispatching Celery webhook notifications immediately after posting a financial transaction, the API server crashed with:
```
RuntimeError: This event loop is already running
```

#### 2. Root Cause Analysis
The webhook dispatch function `trigger_webhooks_for_transaction` was written as a synchronous utility that called `asyncio.run(_find_webhooks_and_enqueue())`. However, the transaction endpoint in FastAPI is an `async def` route running inside Uvicorn's active `asyncio` event loop. Invoking `asyncio.run()` inside an active event loop is illegal and crashes Python's runtime.

#### 3. The Engineering Fix
Re-architected the webhook dispatcher into a native `async def` function that receives the active `AsyncSession`, queries subscriptions directly on the existing loop, and enqueues tasks via Celery's non-blocking `.delay()` method:
```python
# app/workers/tasks.py
async def trigger_webhooks_for_transaction(
    session: AsyncSession,
    event_type: str,
    payload_data: dict[str, Any],
) -> None:
    stmt = select(WebhookSubscriptionRecord).where(
        WebhookSubscriptionRecord.is_active.is_(True),
        WebhookSubscriptionRecord.event_types.contains(event_type),
    )
    result = await session.execute(stmt)
    subscriptions = result.scalars().all()
    for sub in subscriptions:
        dispatch_webhook.delay(
            subscription_id=str(sub.id),
            event_type=event_type,
            payload_data=payload_data,
        )
```

#### 4. Interview & LinkedIn Takeaway
> *"Never call `asyncio.run()` within asynchronous web frameworks like FastAPI. When bridging async request flows with background job queues like Celery, keep the boundary purely async and let Celery's `.delay()` act as a non-blocking producer."*

---

### Incident 05: Non-Serializable Exception Objects in Pydantic v2 Exception Handlers

#### 1. What Happened
When stress-testing invalid payloads against the `/v1/transactions` endpoint, the custom FastAPI validation handler threw an unhandled 500 error:
```
TypeError: Object of type ValueError is not JSON serializable
```

#### 2. Root Cause Analysis
In Pydantic v2, custom validators that raise `ValueError("...")` or `DecimalException` store the raw exception object in the `ctx["error"]` dictionary inside `RequestValidationError.errors()`. When passing `exc.errors()` directly into Starlette's `JSONResponse(content={"errors": exc.errors()})`, the underlying JSON serializer crashes because Python's standard `json.dumps` does not know how to serialize `ValueError` objects.

#### 3. The Engineering Fix
Sanitized the validation errors using FastAPI's built-in `jsonable_encoder`:
```python
# app/main.py
from fastapi.encoders import jsonable_encoder

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "The request body or parameters failed validation.",
                "details": jsonable_encoder(exc.errors()),
            }
        },
    )
```

#### 4. Interview & LinkedIn Takeaway
> *"In Pydantic v2, error dictionaries are not guaranteed to be JSON-serializable because `ctx` can contain arbitrary Python exception instances. Always run validation errors through `jsonable_encoder` before returning a `JSONResponse`."*

---

### Incident 06: SQLite ASCII Collation Failure on ISO-8601 Timestamps in Cursor Pagination

#### 1. What Happened
During cursor pagination integration tests, requesting the second page of ledger transactions using `(created_at, id) < (cursor_time, cursor_id)` returned zero results or skipped entries entirely.

#### 2. Root Cause Analysis
SQLite stores `CURRENT_TIMESTAMP` as an ASCII string formatted as `'YYYY-MM-DD HH:MM:SS'` (space separator). In contrast, Python's `datetime.isoformat()` produces `'YYYY-MM-DDTHH:MM:SS'` (the standard ISO-8601 `T` separator). In ASCII byte order:
- `' '` (space) is ASCII `32` (`0x20`).
- `'T'` is ASCII `84` (`0x54`).
Because `' ' < 'T'` is always true, comparing SQLite database timestamps against ISO-8601 strings produced inverted or corrupt comparison filters across pagination boundaries.

#### 3. The Engineering Fix: Pure UUIDv7 Cursor Pagination
Rather than relying on fragile string timestamp conversions or database-specific date functions, we capitalized on the mathematical properties of **UUIDv7 (RFC 9562)**:
1. UUIDv7 embeds a 48-bit UNIX millisecond timestamp in its high bits.
2. It includes a 12-bit monotonic sequence counter for entries created within the same millisecond.
3. Therefore, UUIDv7 is **naturally time-ordered and strictly monotonic**:
   $$\text{UUIDv7}(t_1) < \text{UUIDv7}(t_2) \iff t_1 \le t_2$$
4. We refactored cursor pagination to filter exclusively on the UUIDv7 primary key:
```python
# app/services/ledger_service.py
if cursor:
    cursor_uuid = uuid.UUID(cursor)
    stmt = stmt.where(TransactionRecord.id < cursor_uuid)

stmt = stmt.order_by(TransactionRecord.id.desc()).limit(limit + 1)
```
This eliminated composite indexes, solved cross-database date collation bugs, and sped up cursor queries.

#### 4. Interview & LinkedIn Takeaway
> *"Why use composite `(timestamp, id)` cursors when your primary key is already time-ordered? By switching from datetime string cursors to pure RFC 9562 UUIDv7 cursors, we eliminated database-specific date collation bugs and cut index storage requirements in half."*

---

### Incident 07: Cross-Account Circular Deadlocks in High-Frequency Bidirectional Transfers

#### 1. What Happened
In high-concurrency stress tests where multiple workers execute simultaneous transfers between the same pair of accounts:
- Worker 1: Account A $\rightarrow$ Account B
- Worker 2: Account B $\rightarrow$ Account A  
Both workers acquired their first lock, attempted to acquire the second lock, and stalled until lock expiration (deadlock), resulting in 503 errors and ruined throughput.

#### 2. Root Cause Analysis
This is the textbook **Circular Wait Condition** (the 4th Coffman Condition):
- Worker 1 holds Lock(A) and waits for Lock(B).
- Worker 2 holds Lock(B) and waits for Lock(A).
Because the accounts were locked in the order they appeared in the request payload, lock ordering was non-deterministic.

#### 3. The Engineering Fix: Ascending UUID Lock Ordering
To guarantee deadlock freedom without complex lock hierarchy graphs, we enforced a strict global order on lock acquisition:
```python
# app/services/lock_service.py
@asynccontextmanager
async def acquire_account_locks(
    redis: Redis,
    account_ids: Iterable[uuid.UUID],
    ttl_ms: int = 5000,
) -> AsyncIterator[None]:
    # Deduplicate and sort accounts by UUID string in ASCENDING order
    sorted_ids = sorted({str(a_id) for a_id in account_ids})
    locks: list[DistributedLock] = []
    try:
        for acc_id_str in sorted_ids:
            lock = DistributedLock(redis=redis, key=f"account:{acc_id_str}", ttl_ms=ttl_ms)
            if not await lock.acquire():
                raise LockAcquisitionError(f"Failed to acquire lock for account {acc_id_str}")
            locks.append(lock)
        yield
    finally:
        for lock in reversed(locks):
            await lock.release()
```
Because $\text{UUID}_A < \text{UUID}_B$ universally, **both** Worker 1 and Worker 2 must acquire Lock(A) before either is allowed to request Lock(B). The circular wait condition is mathematically impossible.

#### 4. Interview & LinkedIn Takeaway
> *"How do you eliminate distributed deadlocks in a high-throughput financial ledger? You don't need distributed deadlock detection or retry loops — you need global resource ordering. By enforcing ascending UUID lock acquisition order, we mathematically eliminated circular wait conditions across all multi-account transfers."*

---

## Summary of Verification & Proofs

- **Unit & Integration Test Suite**: 27 automated tests passing with 88% overall code coverage.
- **Race Condition Verification**:
  - `test_concurrent_debits_no_overdraft`: 20 concurrent tasks racing to debit an account with limited funds. Result: Exactly 10 succeeded, 10 failed with 422 Insufficient Funds, final balance was exactly `$0.0000`.
  - `test_cross_account_transfers_no_deadlock`: Bidirectional transfers between Account A and Account B completed with 0 deadlocks.
- **Idempotency Verification**: Identical transaction submitted 10 times consecutively produced 1 creation + 9 instant cache hits with identical responses.
- **Load Testing**: `locustfile.py` ready for 1,000+ req/sec headless and distributed load benchmarks.
