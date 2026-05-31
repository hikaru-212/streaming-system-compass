# Deferred Architecture Backlog

[← Back to Roadmaps Index](README.md)

## Purpose

This document records architecture issues intentionally deferred from the current implementation scope.

The purpose of this backlog is not to expand the current implementation scope. Instead, it preserves design concerns that should be handled only when the system reaches the right implementation stage.

This backlog should not collect every possible cleanup idea.

An item should remain here only if it has at least one of the following:

- a plausible future trigger
- an architectural consequence
- a stage dependency
- a production-hardening reason
- a clear relationship to runtime evidence, governance, or durability

Pure naming preference, style cleanup, or already-completed implementation work should not remain in this backlog.

Completed Stage 3.5B work should be recorded in roadmaps, ADRs, postmortems, or implementation notes instead of staying here as deferred work.

Current focus:

```text
Stage 3.5C — Durable Read-Side Baseline
```

Recently completed baseline:

```text
Stage 3.5B — Durable Write-Side Baseline
```

Stage 3.5B now includes:

```text
PR1 Schema + Local PostgreSQL + Migration
PR2 PostgresEventStore
PR3 PostgresIdempotencyStore
PR4 Transactional Semantic Write-Side Boundary
PR5 PostgreSQL Concurrency Admission Boundary
PR6 Validation Placement Strategy Boundary / Stage 4 Prelude
```

This backlog should now be used only for concerns intentionally deferred beyond the durable write-side baseline.

---

## Status Legend

```text
Optional durable schema hardening
→ can be done later if the schema boundary becomes meaningful enough to justify migration churn

Stage 4 / evidence design
→ should wait for SemanticOutcome, runtime evidence, or governance work

Stage 4 / connection-pool hardening
→ should wait until structured error modeling, connection lifecycle policy, or pooled database connections exist

Later evaluation
→ should be revisited only when a concrete runtime, storage, or operational need appears

Later production hardening
→ useful, but not part of the current correctness baseline
```

---

## 1. Proof Previous Status Constraint Hardening

### Current Decision

The database currently stores previous-status proof claims as plain text:

```sql
proof_prev_status TEXT NOT NULL
```

Python domain status values are already normalized:

```python
OrderStatus.INIT = "INIT"
OrderStatus.CREATED = "CREATED"
OrderStatus.PAID = "PAID"
```

The current application write path constructs proof status from domain objects, so normal command execution is already protected by Python-side domain logic and Compass validation.

### Why Not Now

Adding a database constraint is useful defense-in-depth, but it is not required for the current Stage 3.5B durable write-side baseline.

The completed Stage 3.5B baseline focused on:

```text
durable accepted history
durable idempotency memory
transactional write-side execution
two-phase concurrency admission
validation placement strategy
```

A proof-status database constraint would be a durable schema-hardening task, not a requirement for write-side baseline correctness.

### Future Trigger

Consider adding a database constraint when one of the following becomes true:

- proof fields are treated as durable evidence in Stage 4
- durable read-side or validation logic starts relying on proof fields as trusted database evidence
- additional write paths or migration tools may touch `order_events`
- manual SQL / operational repair scripts become part of the workflow
- the project wants stronger database-side proof vocabulary enforcement before production hardening

Possible future constraint:

```sql
CHECK (proof_prev_status IN ('INIT', 'CREATED', 'PAID'))
```

### Current Classification

```text
Optional durable schema hardening
```

This is durable schema hardening, not Stage 4 `SemanticOutcome` / Error Model work.

### Suggested Timing

During Stage 3.5C if durable read-side work starts depending on proof fields as trusted evidence.

Otherwise, revisit before Stage 4 durable evidence work or during a dedicated schema-hardening pass.

---

## 2. UUIDv7 / Time-Ordered UUID Evaluation

### Current Decision

Do not introduce UUIDv7 during Stage 3.5B.

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

After Stage 3.5C or during later storage/operational hardening, unless storage locality or operational inspection becomes a real bottleneck.

---

## 3. Formal `EventStoreProtocol`

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
Later evaluation
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

Defer until multiple storage implementations or admission strategies require stricter type-level coordination.

---

## 4. Stored Event Record / JSONB Evidence Hydration

### Current Decision

`PostgresEventStore.load()` returns `list[OrderEvent]` and only hydrates fields required to reconstruct the domain event.

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

## 5. Registry-Stage Timing in `metadata_json`

### Current Decision

Stage 3.5B did not implement durable timing collection.

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
- validation placement mode
- admission strategy identity

### Why Not Now

Stage 3.5B focused on correctness boundaries:

- durable accepted history
- durable idempotency
- transaction atomicity
- concurrency admission
- validation placement

Timing collection is meaningful, but it should not distract from correctness boundaries.

### Current Classification

```text
Stage 4 / evidence design
```

### Suggested Timing

During Stage 4 evidence / outcome persistence, or during a dedicated observability pass after durable read-side persistence exists.

---

## 6. Event Payload / Proof / Metadata JSON Shape

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
Stage 4 / evidence design
```

### Suggested Timing

After durable read-side baseline, before or during SemanticOutcome persistence design.

---

## 7. Append-Only Database Hardening

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

After durable read-side baseline, or during production-hardening work.

---

## 8. Integration Test Boundary and CI Strategy

### Current Decision

Stage 3.5B introduced or aligned:

- `TEST_DATABASE_URL`
- `compass_test`
- test database guardrails
- destructive DB test isolation
- CI test database creation
- migration against test database
- integration test directory reorganization
- transactional integration test README
- in-memory integration test README

These are sufficient for the current durable write-side baseline.

### Remaining Future Work

Possible later follow-ups:

- pytest markers for DB-backed tests
- storage integration README
- integration root README
- performance / benchmark test separation
- optional test container lifecycle helpers

### Current Classification

```text
Later production hardening
```

### Suggested Timing

Revisit when the test matrix expands for Stage 3.5C durable read-side persistence or when CI runtime becomes difficult to manage.

---

## 9. Pre-Transaction Cleanup Failure Handling

### Current Decision

Stage 3.5B PR6 introduced a simple cleanup boundary during the preliminary read phase for `PRE_TRANSACTION` validation:

```python
try:
    preliminary_idempotency_decision = read_idempotency_store.check(signature)

    if preliminary_idempotency_decision.verdict == IdempotencyVerdict.REPLAY:
        return PostgresWriteSideResult(...)

    if preliminary_idempotency_decision.verdict == IdempotencyVerdict.CONFLICT:
        return PostgresWriteSideResult(...)

    history = read_event_store.load(order_id)
finally:
    connection.rollback()
```

This is required because read-only `SELECT` operations can still open an implicit transaction when the PostgreSQL connection is not in autocommit mode.

The current baseline ensures that CPU-side Compass validation does not accidentally run while the connection still carries an implicit read transaction.

### Deferred Concern

The current baseline does not yet implement structured handling for rollback failure itself.

Future production-like handling may need to distinguish:

```text
primary read / load failure
vs
cleanup rollback failure
```

This matters because rollback can itself fail if the connection is already closed, aborted, or physically broken.

There are two different failure cases:

```text
Case 1:
primary read failure happens
+
cleanup rollback failure also happens

Risk:
cleanup failure may mask the original read failure
```

```text
Case 2:
primary read succeeds
+
cleanup rollback fails

Risk:
the system may continue as if the connection were clean even though cleanup failed
```

The project should not silently swallow cleanup failures with a broad:

```python
except Exception:
    pass
```

That would avoid masking the primary error, but it could also hide connection-state corruption.

### Future Direction

When Stage 4 error modeling or connection pooling is introduced, consider a hardened cleanup model that can:

- preserve the primary error when cleanup also fails
- attach cleanup failure as diagnostic context
- map cleanup failure into a structured infrastructure error
- mark the connection as unsafe for reuse
- discard or invalidate broken pooled connections
- log cleanup failures with trace context
- expose cleanup failure as operational evidence

A possible future pattern is:

```text
if primary error exists:
    preserve primary error
    attach cleanup failure as diagnostic context

if no primary error exists:
    surface cleanup failure as infrastructure failure
```

This future work should be integrated with the Stage 4 error model instead of being implemented as ad hoc exception handling inside Stage 3.5B.

### Current Classification

```text
Stage 4 / connection-pool hardening
```

### Suggested Timing

Revisit when at least one of the following becomes true:

- Stage 4 error model work begins
- connection pooling is introduced
- infrastructure errors are mapped into structured runtime outcomes
- production-like observability is added
- cleanup failures need to become operational evidence

### Related Note

See:

- [Pre-Transaction Read Cleanup Boundary](../postmortems/pre_transaction_read_cleanup_boundary.md)

---

## Summary

The deferred backlog should now be read with the following stage alignment:

| Item | Current Alignment |
|---|---|
| Proof previous status constraint hardening | Optional durable schema hardening |
| UUIDv7 | Later evaluation |
| EventStoreProtocol | Later evaluation |
| StoredEventRecord / JSONB hydration | Stage 4 / evidence design |
| Registry-stage timing | Stage 4 / evidence design |
| Payload/proof/metadata JSON shape | Stage 4 evidence / outcome persistence |
| Append-only DB hardening | Later production hardening |
| Integration test boundary / CI strategy | Later production hardening |
| Pre-transaction cleanup failure handling | Stage 4 / connection-pool hardening |

The backlog remains a scope-control document.

It should not be used to pull every valid architecture concern into the current PR or stage.
