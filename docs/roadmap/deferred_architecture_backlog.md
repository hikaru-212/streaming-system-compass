# Deferred Architecture Backlog

[← Back to Roadmaps Index](README.md)

## Purpose

This document records architecture issues intentionally deferred from the current implementation scope.

The purpose of this backlog is not to expand the current PR scope. Instead, it preserves design concerns that were identified during Stage 3.5B work but should be handled only when the system reaches the right implementation stage.

Current focus remains:

```text
Stage 3.5B PR2 — PostgresEventStore baseline
```

---

## 1. Durable `EventType` Vocabulary Normalization

### Current Decision

Do not change `EventType` values during PR2.

Current values remain:

```python
EventType.CREATED = "created"
EventType.PAID = "paid"
```

This is intentionally aligned with the current SQL migration constraint:

```sql
CHECK (event_type IN ('created', 'paid'))
```

### Why Not Now

Changing `EventType` to uppercase values such as `"CREATED"` and `"PAID"` would require coordinated changes to:

- SQL migration constraints
- existing local database state
- PostgresEventStore insert behavior
- integration tests
- documentation

That would expand PR2 beyond its intended scope.

### Suggested Timing

After Stage 3.5B durable write-side baseline is complete.

### Possible Future Issue

```text
Evaluate durable EventType vocabulary normalization
```

---

## 2. `OrderStatus` Durable Constraint Hardening

### Current Decision

`OrderStatus` values may be normalized to uppercase before durable event-store implementation:

```python
OrderStatus.INIT = "INIT"
OrderStatus.CREATED = "CREATED"
OrderStatus.PAID = "PAID"
```

This is acceptable because `proof_prev_status` currently has no SQL CHECK constraint.

### Why Not Fully Harden Now

The database schema currently defines:

```sql
proof_prev_status TEXT NOT NULL
```

It does not yet enforce allowed status values.

### Future Work

After durable persistence behavior is stable, consider adding a DB constraint such as:

```sql
CHECK (proof_prev_status IN ('INIT', 'CREATED', 'PAID'))
```

### Suggested Timing

After Stage 3.5B baseline, during durable schema hardening.

---

## 3. UUIDv7 / Time-Ordered UUID Evaluation

### Current Decision

Do not introduce UUIDv7 in PR2.

Current approach:

- keep UUIDv4
- centralize event ID generation
- preserve PostgreSQL UUID compatibility
- defer UUIDv7 / time-ordered UUID evaluation

### Why Not Now

PR2 should focus on making accepted history durable through `PostgresEventStore`.

UUIDv7 adoption may require:

- Python version compatibility review
- dependency decision
- migration strategy
- test updates
- decision on whether ordering should be represented by identity, sequence, or append time

### Existing Issue

```text
#7 Evaluate UUIDv7 for durable event identity generation
```

### Suggested Timing

After `PostgresEventStore` and the transactional write-side boundary are stable.

---

## 4. Formal `EventStoreProtocol`

### Current Decision

Do not introduce a formal `Protocol` or abstract base class during PR2.

The project currently relies on constructor injection and method-shape compatibility:

```python
append(candidate_event, expected_current_version)
load(order_id)
last_event(order_id)
```

### Why Not Now

Only one durable implementation is being introduced.

Defining a protocol too early may result in an abstraction shaped by incomplete information.

### Future Work

Consider defining:

```python
class EventStoreProtocol(Protocol):
    def append(self, candidate_event: OrderEvent, expected_current_version: int) -> None: ...
    def load(self, order_id: str) -> list[OrderEvent]: ...
    def last_event(self, order_id: str) -> OrderEvent | None: ...
```

### Suggested Timing

After PR4 transactional write-side boundary, or when multiple storage implementations need stricter type-level coordination.

---

## 5. Stored Event Record / JSONB Evidence Hydration

### Current Decision

`PostgresEventStore.load()` should return `list[OrderEvent]` and only hydrate fields required to reconstruct the domain event.

It does not currently hydrate:

- `payload_json`
- `proof_json`
- `metadata_json`
- `appended_at`
- `event_schema_version`

### Why Not Now

`OrderEvent` does not currently carry those fields.

Hydrating JSONB evidence into `OrderEvent` would blur the boundary between:

- domain event reconstruction
- durable audit / evidence record retrieval

### Future Work

Introduce a persistence-level record such as:

```python
@dataclass(frozen=True)
class StoredOrderEvent:
    event: OrderEvent
    payload_json: dict
    proof_json: dict
    metadata_json: dict
    appended_at: datetime
    event_schema_version: int
```

Then consider separate APIs:

```python
load(order_id) -> list[OrderEvent]
load_records(order_id) -> list[StoredOrderEvent]
```

### Suggested Timing

During audit, evidence, or SemanticOutcome persistence design.

---

## 6. Registry-Stage Timing in `metadata_json`

### Current Decision

PR2 does not implement timing collection.

`metadata_json` remains a reserved container for future runtime metadata.

### Future Metadata Candidates

Possible future timing fields:

- idempotency check duration
- aggregate rehydration duration
- validation context build duration
- candidate event creation duration
- Compass validation duration
- event append duration
- idempotency record write duration
- transaction total duration

### Why Not Now

PR2 only implements event-store durability.

Full registry-stage timing becomes meaningful when the full durable write-side flow exists.

### Suggested Timing

After PR4 transactional write-side boundary, or during observability / runtime evidence work.

---

## 7. Transaction Lifecycle Ownership

### Current Decision

`PostgresEventStore.append()` should not automatically call `commit()`.

The caller should own connection and transaction lifecycle.

### Why Not Now

PR4 will need to coordinate:

```text
event append + idempotency record write
```

inside the same database transaction.

If `PostgresEventStore.append()` commits by itself, PR4 transaction coordination becomes harder.

### Future Work

Define a clear transaction boundary, possibly through:

- `PostgresUnitOfWork`
- durable write-side handler
- transactional registry wrapper
- explicit transaction context manager

### Suggested Timing

PR4 — Transactional write-side boundary.

---

## 8. Custom Persistence Exceptions

### Current Decision

PR2 may continue using `ValueError` to align with the current in-memory `EventStore` behavior.

Examples:

- version conflict
- append-time continuity violation

### Why Not Now

Introducing custom exception hierarchy during PR2 would expand scope into error modeling.

### Future Work

Consider dedicated exceptions:

```python
class VersionConflictError(Exception): ...
class AppendContinuityError(Exception): ...
class DurablePersistenceError(Exception): ...
```

These may later map into structured SemanticOutcome / RuntimeDecision behavior.

### Suggested Timing

Stage 4B — Structured Semantic Outcome / Error Model v1, or after PR4.

---

## 9. Event Payload / Proof / Metadata JSON Shape

### Current Decision

PR2 may use minimal JSONB objects:

```python
payload_json = {}
proof_json = {
    "prev_event_id": ...,
    "prev_version": ...,
    "prev_status": ...,
}
metadata_json = {}
```

### Why Not Now

The project has not yet defined a full durable event payload schema or audit evidence model.

### Future Work

Clarify:

- whether `payload_json` should duplicate event domain fields
- whether `proof_json` is only a proof copy or a richer proof-carrying evidence container
- whether `metadata_json` should be restricted to runtime metadata
- how these fields relate to SemanticOutcome persistence

### Suggested Timing

After durable write-side baseline, before or during SemanticOutcome persistence design.

---

## 10. Append-Only Database Hardening

### Current Decision

PR2 does not implement production-grade append-only hardening.

Current defenses are:

- application append logic
- `accepted_event_id` primary key
- `UNIQUE(order_id, sequence)`
- expected-version check in the store

### Future Work

Evaluate:

- trigger-based rejection of `UPDATE` / `DELETE`
- limited database role permissions
- append-only audit policies
- partitioning strategy
- operational backup / restore behavior

### Suggested Timing

After Stage 3.5B durable baseline is complete, during production-hardening work.

---

## 11. Integration Test Boundary and CI Strategy

### Current Decision

`postgres_connection.py` unit tests should not require a real database.

`PostgresEventStore` tests are the correct place for database-backed integration coverage.

### Future Work

Clarify integration test setup:

- whether Docker PostgreSQL must be running
- how migrations are applied before tests
- whether tests should clean tables before each case
- whether integration tests should use pytest markers
- whether CI should run database-backed tests by default

### Suggested Timing

During PR2 integration test implementation and later CI hardening.

---

## Summary

The current PR2 scope should remain focused on:

```text
PostgresEventStore baseline
append / load / last_event
UUID / Decimal / proof status round-trip
stale expected version rejection
duplicate sequence rejection
```

The items in this backlog are valid architecture concerns, but they are intentionally deferred to avoid scope creep.

They should be converted into GitHub Issues only when their suggested timing becomes active.
