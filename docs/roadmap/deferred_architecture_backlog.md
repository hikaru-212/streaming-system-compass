# Deferred Architecture Backlog

[← Back to Roadmaps Index](README.md)

## Purpose

This document records architecture issues intentionally deferred from the current implementation scope.

The purpose of this backlog is not to expand the current PR scope. Instead, it preserves design concerns that were identified during Stage 3.5B work but should be handled only when the system reaches the right implementation stage.

This backlog should not collect every possible cleanup idea.

An item should remain here only if it has at least one of the following:

- a plausible future trigger
- an architectural consequence
- a stage dependency
- a production-hardening reason
- a clear relationship to runtime evidence, governance, or durability

Pure naming preference or style cleanup should not remain in this backlog unless it has a concrete future compatibility cost.

Current focus:

```text
Stage 3.5B PR6 / Stage 4 Prelude — Validation Placement Strategy
```

Next planned focus:

```text
Stage 3.5C — Durable Read-Side Baseline
```

PR6 remains the current focus until the validation placement baseline is merged and marked complete.

---

## Status Legend

```text
Completed
→ already handled in the current Stage 3.5B baseline

PR6 active candidate
→ appropriate for the validation-placement strategy PR after PR5 admission exists

Optional durable schema hardening
→ can be done later if the schema boundary becomes meaningful enough to justify migration churn

Stage 4 / evidence design
→ should wait for SemanticOutcome, runtime evidence, or governance work

Later production hardening
→ useful, but not part of the current correctness baseline

Stage 4 / connection-pool hardening
→ should wait until structured error modeling, connection lifecycle policy, or pooled database connections exist
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

Adding a database constraint is useful defense-in-depth, but it is not required for the current PR6 validation placement baseline.

PR6 focuses on:

```text
ValidationPlacement.IN_TRANSACTION
ValidationPlacement.PRE_TRANSACTION
```

and on making sure pre-transaction validation remains protected by append-time admission and connection-state cleanup.

A proof-status database constraint would be a durable schema hardening task, not a validation-placement requirement.

### Future Trigger

Consider adding a database constraint when one of the following becomes true:

- proof fields are treated as durable evidence in Stage 4
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

Before Stage 4 durable evidence work, or during a dedicated schema-hardening pass.

---

## 2. UUIDv7 / Time-Ordered UUID Evaluation

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

## 4. Stored Event Record / JSONB Evidence Hydration

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

## 5. Registry-Stage Timing in `metadata_json`

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

## 6. Transaction Lifecycle Ownership

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

## 6A. Pessimistic Admission Autocommit Guard

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

## 7. Custom Persistence Exceptions

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

## 8. Event Payload / Proof / Metadata JSON Shape

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

## 9. Append-Only Database Hardening

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

## 10. Integration Test Boundary and CI Strategy

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

## 11. Validation Placement Strategy

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
→ append_if_admitted(candidate_event, expected_current_version)
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

## 12. Pre-Transaction Cleanup Failure Handling

### Status

```text
Deferred until Stage 4 error model or connection-pool hardening
```

### Context

Stage 3.5B PR6 introduces `PRE_TRANSACTION` validation placement.

The current PR6 baseline uses a cleanup boundary during the preliminary read phase:

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

The current PR6 goal is to ensure that CPU-side Compass validation does not accidentally run while the connection still carries an implicit read transaction.

### Current Decision

Use the simple cleanup guarantee for PR6:

```text
preliminary read phase
→ always attempt rollback cleanup
→ run CPU-side validation only after the read transaction is closed
```

This is sufficient for the current local PostgreSQL and non-pooled connection baseline.

It preserves the physical meaning of:

```text
ValidationPlacement.PRE_TRANSACTION
```

by ensuring that validation is not merely outside the write-side Unit of Work logically, but also separated from the preliminary read transaction physically.

### Deferred Concern

The current PR6 baseline does not yet implement structured handling for rollback failure itself.

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

This future work should be integrated with the Stage 4 error model instead of being implemented as ad hoc exception handling inside PR6.

### Why Not Now

PR6 is focused on validation placement:

```text
IN_TRANSACTION
vs
PRE_TRANSACTION
```

It should not introduce a full production-grade connection lifecycle policy.

The current project does not yet own:

- connection pool abstraction
- connection invalidation policy
- structured infrastructure error model
- durable infrastructure-error evidence
- production observability pipeline
- cleanup failure metrics or traces

Adding all of that in PR6 would expand the PR beyond validation placement strategy.

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
| Pre-transaction cleanup failure handling | Stage 4 / connection-pool hardening |

The backlog remains a scope-control document.

It should not be used to pull every valid architecture concern into the current PR.
