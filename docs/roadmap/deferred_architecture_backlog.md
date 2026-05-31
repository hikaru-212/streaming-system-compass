# Deferred Architecture Backlog

[← Back to Roadmaps Index](README.md)

## Purpose

This document records architecture issues intentionally deferred from the current implementation scope.

The purpose of this backlog is not to expand the current PR scope. Instead, it preserves design concerns that were identified during Stage 3.5B work but should be handled only when the system reaches the right implementation stage.

Current focus:

```text
Stage 3.5B PR6 / Stage 4 Prelude — Validation Placement Strategy
```

Next planned focus:

```text
Stage 3.5B PR6 / Stage 4 Prelude — Validation Placement Strategy
```

---

## Status Legend

```text
Completed
→ already handled in the current Stage 3.5B baseline

PR6 active candidate
→ appropriate for the validation-placement strategy PR after PR5 admission exists

Optional Stage 3.5B hardening
→ can be done after PR5 if worth the schema/documentation churn

Stage 4 / evidence design
→ should wait for SemanticOutcome, runtime evidence, or governance work

Later production hardening
→ useful, but not part of the current correctness baseline
```

---

## 1. Durable `EventType` Vocabulary Normalization

### Current Decision

Do not change `EventType` values during PR4 / PR5.

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
- durable event fixtures / expected values

That would expand PR4 / PR5 beyond their intended scope.

### Current Classification

```text
Optional Stage 3.5B hardening after PR5
```

This is **not** Stage 4 Error Model work.

It is durable vocabulary / schema hardening.

### Suggested Timing

After Stage 3.5B PR5, if there is a clear reason to normalize durable storage vocabulary.

Possible future PR:

```text
schema: harden durable event vocabulary constraints
```

### Possible Future Issue

```text
Evaluate durable EventType vocabulary normalization
```

---

## 2. `OrderStatus` Durable Constraint Hardening

### Current Decision

`OrderStatus` values may already be normalized at the Python domain level:

```python
OrderStatus.INIT = "INIT"
OrderStatus.CREATED = "CREATED"
OrderStatus.PAID = "PAID"
```

However, the database schema currently defines:

```sql
proof_prev_status TEXT NOT NULL
```

It does not yet enforce allowed status values.

### Future Work

After durable persistence behavior is stable, consider adding a DB constraint such as:

```sql
CHECK (proof_prev_status IN ('INIT', 'CREATED', 'PAID'))
```

### Current Classification

```text
Optional Stage 3.5B hardening after PR5
```

This is durable schema hardening, not Stage 4 `SemanticOutcome` / Error Model work.

### Suggested Timing

After PR5 or before Stage 3.5C, if the project wants to harden durable proof-status vocabulary.

---

## 3. UUIDv7 / Time-Ordered UUID Evaluation

### Current Decision

Do not introduce UUIDv7 during Stage 3.5B PR4 / PR5.

Current approach:

- keep UUIDv4
- centralize event ID generation
- preserve PostgreSQL UUID compatibility
- defer UUIDv7 / time-ordered UUID evaluation

### Why Not Now

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

### Current Classification

```text
Later evaluation
```

### Suggested Timing

After Stage 3.5B or after durable read-side baseline, unless storage locality or operational inspection becomes a real bottleneck.

---

## 4. Formal `EventStoreProtocol`

### Current Decision

Do not introduce a formal `Protocol` or abstract base class just because PostgreSQL persistence now exists.

The project currently relies on constructor injection and method-shape compatibility:

```python
append(candidate_event, expected_current_version)
load(order_id)
last_event(order_id)
```

### Why Not Now

A protocol should be introduced only when it clarifies coordination between multiple implementations or admission strategies.

Defining it too early may result in an abstraction shaped by incomplete information.

### Current Classification

```text
Deferred until multiple storage implementations need stricter type-level coordination
```

### Future Work

Consider defining:

```python
class EventStoreProtocol(Protocol):
    def append(self, candidate_event: OrderEvent, expected_current_version: int) -> None: ...
    def load(self, order_id: str) -> list[OrderEvent]: ...
    def last_event(self, order_id: str) -> OrderEvent | None: ...
```

### Suggested Timing

Do not introduce only because PR5 admission exists.

Defer until multiple storage implementations or admission strategies require stricter type-level coordination.

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

### Current Classification

```text
Stage 4 / evidence design
```

### Suggested Timing

During audit, evidence, or SemanticOutcome persistence design.

---

## 6. Registry-Stage Timing in `metadata_json`

### Current Decision

PR4 did not implement timing collection.

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

PR4 focused on durable transaction composition and Compass-guarded accepted-history mutation.

Timing collection is meaningful, but it should not distract from correctness boundaries.

### Current Classification

```text
PR6 latency experiment candidate / Stage 4 evidence design
```

### Suggested Timing

During PR6 if lightweight in-memory timing metadata helps compare validation placements; otherwise defer to Stage 4 evidence / outcome persistence.

---

## 7. Transaction Lifecycle Ownership

### Status

```text
Completed in Stage 3.5B PR4
```

### What Changed

`PostgresEventStore.append()` should not automatically call `commit()`.

The caller owns connection and transaction lifecycle.

PR4 introduced:

```text
PostgresWriteSideUnitOfWork
```

to coordinate:

```text
event append + idempotency record write
```

inside the same database transaction.

### Current Classification

```text
Completed
```

### Future Work

Further transaction ownership work may occur in PR6 when validation placement introduces pre-transaction and in-transaction orchestration modes.

---

## 7A. Pessimistic Admission Autocommit Guard

### Status

```text
Completed in Stage 3.5B PR5
```

### Current Decision

A PostgreSQL transaction-scoped advisory lock is only meaningful when the connection preserves a transaction boundary across the protected work.

Therefore, pessimistic admission should reject `autocommit=True` instead of pretending that the stream lock is active.

### Why

If `autocommit=True`, a transaction-scoped lock can be acquired and released immediately when the lock statement completes.

That would collapse the physical protection promised by `prepare_stream(order_id)`.

### Current Classification

```text
Completed PR5 guardrail
```

### Related Note

See:

- [Autocommit, Transaction Boundaries, and Partial-Write Risk](../postmortems/autocommit_boundary_and_partial_write_risk.md)


---

## 8. Custom Persistence Exceptions

### Status

```text
Completed in Stage 3.5B PR5 at the storage/admission boundary
```

### Current Decision

The project should not jump directly from raw PostgreSQL exceptions to Stage 4 `SemanticOutcome`.

There are two separate layers:

```text
PR5:
storage/admission-level errors and stable admission results

Stage 4:
SemanticOutcome / RuntimeDecision mapping
```

### Why Not All in Stage 4

PR5 needs application-level handling for concurrent writer admission.

For example, stale writes should not remain raw database-specific exceptions.

But that does not require the full Stage 4 Error Model.

PR5 introduces storage/admission-level error vocabulary so raw storage conflicts can be translated into stable admission semantics before any future Stage 4 governance mapping exists.

### Current Classification

```text
Completed for PR5 baseline
Stage 4 remains responsible for SemanticOutcome mapping
```

### Remaining Future Work

Future Stage 4 work may map storage/admission results into structured `SemanticOutcome` and `RuntimeDecision` records.

PR5 does not persist admission attempts or introduce governance outcomes.

---

## 9. Event Payload / Proof / Metadata JSON Shape

### Current Decision

Stage 3.5B uses minimal JSONB objects:

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

### Current Classification

```text
Stage 4 evidence / outcome persistence
```

### Suggested Timing

After durable write-side baseline, before or during SemanticOutcome persistence design.

---

## 10. Append-Only Database Hardening

### Current Decision

Stage 3.5B does not implement production-grade append-only hardening.

Current defenses are:

- application append logic
- `accepted_event_id` primary key
- `UNIQUE(order_id, sequence)`
- expected-version check in the store
- PR4 transaction boundary
- PR5 admission boundary

### Future Work

Evaluate:

- trigger-based rejection of `UPDATE` / `DELETE`
- limited database role permissions
- append-only audit policies
- partitioning strategy
- operational backup / restore behavior

### Current Classification

```text
Later production hardening
```

### Suggested Timing

After Stage 3.5B durable baseline is complete, during production-hardening work.

---

## 11. Integration Test Boundary and CI Strategy

### Status

```text
Mostly completed in Stage 3.5B PR4
```

### What Changed

PR4 introduced or aligned:

- `TEST_DATABASE_URL`
- `compass_test`
- test database guardrails
- destructive DB test isolation
- CI test database creation
- migration against test database
- integration test directory reorganization
- transactional integration test README
- in-memory integration test README

### Current Classification

```text
Mostly completed
```

### Remaining Future Work

Possible later follow-ups:

- pytest markers for DB-backed tests
- storage integration README
- integration root README
- performance / benchmark test separation
- optional test container lifecycle helpers

These are not required for PR4.

---

## 12. Validation Placement Strategy

### Status

```text
Active PR6 candidate after PR5
```

### Current Decision

PR4 established the high-defense baseline:

```text
IN_TRANSACTION Compass validation
```

ADR 0011 records the conceptual distinction:

```text
ValidationMode
≠
ValidationPlacement
```

PR5 completed the required admission dependency by introducing two-phase PostgreSQL concurrency admission:

```text
prepare_stream(order_id)
→ admit(candidate_event, expected_current_version)
```

After PR5, validation placement is no longer only a deferred concern. The required append-time admission boundary now exists, so `PRE_TRANSACTION` validation can be evaluated safely as a PR6 / Stage 4 Prelude.

### Why It Becomes Active After PR5

Safe `PRE_TRANSACTION` validation requires append-time concurrency admission.

Without PR5, a candidate event could be validated against accepted history and then become stale before append.

With PR5, append-time admission can reject the stale candidate before it enters accepted history.

### PR6 Work

PR6 should introduce:

```text
IN_TRANSACTION
PRE_TRANSACTION
future ASYNC_AUDIT
```

It should preserve `IN_TRANSACTION` as the default and add a minimal `PRE_TRANSACTION` orchestration path for latency / safety comparison.

### Current Classification

```text
Active PR6 / Stage 4 prelude
```

### Suggested Timing

Immediately after PR5 merge, before Stage 4 timing / evidence persistence work.

---

## Summary

The deferred backlog should now be read with the following stage alignment:

| Item | Current Alignment |
|---|---|
| EventType vocabulary normalization | Optional after PR5 / durable schema hardening |
| OrderStatus durable constraint | Optional after PR5 / durable schema hardening |
| UUIDv7 | Later evaluation |
| EventStoreProtocol | Deferred until stricter type-level coordination is needed |
| StoredEventRecord / JSONB hydration | Stage 4 / evidence design |
| Registry-stage timing | PR6 latency experiment candidate / Stage 4 evidence design |
| Transaction lifecycle ownership | Completed in PR4 |
| Pessimistic admission autocommit guard | Completed in PR5 |
| Custom persistence exceptions | Completed in PR5 for storage/admission errors; Stage 4 for SemanticOutcome |
| Payload/proof/metadata JSON shape | Stage 4 evidence / outcome persistence |
| Append-only DB hardening | Later production hardening |
| Integration test boundary / CI strategy | Mostly completed in PR4 |
| Validation placement strategy | Active PR6 / Stage 4 prelude |

The backlog remains a scope-control document.

It should not be used to pull every valid architecture concern into the current PR.
