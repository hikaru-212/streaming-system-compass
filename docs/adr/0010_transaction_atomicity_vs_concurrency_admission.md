# ADR 0010: Separate Transaction Atomicity from Concurrency Admission

[← Back to ADR Index](README.md)

## Status

Proposed

---

## Context

Stage 3.5B moves the write-side baseline from in-memory persistence toward PostgreSQL-backed durable execution.

By the end of Stage 3.5B PR3, the project has established two durable write-side stores:

- `PostgresEventStore` for accepted event history
- `PostgresIdempotencyStore` for request-level replay / conflict memory

Stage 3.5B PR4 then introduces a PostgreSQL write-side unit of work and a minimal transactional write-side flow. The purpose of PR4 is to ensure that accepted event append and idempotency record persistence are coordinated in the same database transaction.

During PR4 design, a separate correctness concern became explicit:

> transaction atomicity does not fully solve concurrent writer admission.

A transaction can guarantee that related writes commit or roll back together. However, it does not by itself define how multiple writers competing for the same aggregate stream should be admitted, rejected, serialized, or classified.

The project already had an earlier in-memory admission abstraction through `ConcurrencyGate` and `OptimisticVersionGate`. That earlier design separated persistence admission from domain legality, validation truth, and idempotency classification.

The durable PostgreSQL write-side should preserve the same boundary separation instead of collapsing concurrency handling into the transaction unit of work.

---

## Decision

Stage 3.5B will explicitly separate two concerns:

1. **Transaction atomicity**
2. **Concurrency admission**

The implementation sequence will be adjusted as follows:

```text
Stage 3.5B PR1 — PostgreSQL schema / local setup / migration ✅
Stage 3.5B PR2 — PostgresEventStore baseline ✅
Stage 3.5B PR3 — PostgresIdempotencyStore baseline ✅
Stage 3.5B PR4 — transactional write-side boundary
Stage 3.5B PR5 — PostgreSQL concurrency admission boundary
```

PR4 remains focused on transaction atomicity:

- accepted event append and idempotency record write share one database transaction
- both writes commit together
- both writes roll back together
- replay / conflict paths do not create new durable rows

PR5 will focus on PostgreSQL-backed concurrent writer admission:

- explicit storage-level stale-write / concurrency errors
- optimistic PostgreSQL admission strategy
- pessimistic PostgreSQL admission strategy
- stable admission results for concurrent writers
- tests proving that only one writer can occupy a stream sequence slot

---

## Rationale

### Transaction atomicity and concurrency admission answer different questions

Transaction atomicity answers:

> Do related writes commit or roll back together?

Concurrency admission answers:

> Should this writer be allowed to occupy the next stream position?

These are related, but they are not the same correctness problem.

A transaction boundary can prevent partial durable writes such as:

- event persisted but idempotency record missing
- idempotency record persisted but event missing

However, it does not fully define how the system should handle cases such as:

- two workers reading the same latest version
- two workers attempting to append the same next sequence
- one writer succeeding while another becomes stale
- database constraint errors leaking as raw infrastructure exceptions
- stale writers needing stable application-level classification

Therefore, concurrent admission should be handled as an explicit boundary rather than treated as an incidental side effect of the transaction wrapper.

---

## Boundary Distinction

The durable write-side should preserve the following separation:

```text
domain legality
≠ idempotency replay / conflict classification
≠ Compass transition-truth validation
≠ transaction atomicity
≠ concurrency admission
≠ durable storage representation
```

PR4 owns:

```text
transaction atomicity
```

PR5 owns:

```text
concurrency admission
```

This mirrors the earlier in-memory design where admission was represented by a separate `ConcurrencyGate` contract.

---

## Planned PR5 Direction

### Storage-level concurrency errors

A future PR5 should introduce explicit storage-level errors, for example:

```python
class StorageConflictError(Exception):
    pass


class StaleWriteError(StorageConflictError):
    pass
```

These errors should prevent raw PostgreSQL exceptions, such as unique constraint violations, from leaking directly into higher-level write-side flow logic.

Potential location:

```text
src/storage/errors.py
```

Affected implementation:

```text
src/storage/postgres_event_store.py
```

---

### PostgreSQL optimistic admission

The optimistic admission strategy should preserve the earlier design idea:

- do not lock first
- append based on `expected_current_version`
- rely on append-time version / sequence continuity
- reject stale writers when the durable stream has already advanced

Potential implementation:

```text
src/pipeline/transactional/postgres_admission.py
```

Possible class:

```python
class PostgresOptimisticAdmissionGate:
    ...
```

Expected behavior:

```text
same stream + same expected version + competing writers
→ one writer admitted
→ stale writer rejected
→ rejected candidate does not become accepted history
```

---

### PostgreSQL pessimistic admission

The pessimistic admission strategy should serialize writers before append.

A minimal PostgreSQL-backed baseline may use transaction-scoped advisory locks:

```sql
SELECT pg_advisory_xact_lock(hashtext(%s));
```

where `%s` is the stream identity, such as `order_id`.

This avoids adding a new lock table in the first baseline while still allowing the system to model lock-based admission.

Possible class:

```python
class PostgresPessimisticAdmissionGate:
    ...
```

Expected behavior:

```text
same stream writers
→ serialized through transaction-scoped lock

different stream writers
→ not unnecessarily blocked by each other
```

---

### Write-side flow mapping

After storage-level stale-write behavior exists, `PostgresTransactionalWriteSide` can translate admission rejection into a stable write-side result.

Potential future outcome:

```python
class PostgresWriteSideOutcome(Enum):
    ACCEPTED = "ACCEPTED"
    REPLAY = "REPLAY"
    CONFLICT = "CONFLICT"
    ADMISSION_REJECTED = "ADMISSION_REJECTED"
```

This keeps concurrency rejection distinct from idempotency conflict.

---

## Consequences

### Positive Consequences

- PR4 remains focused on transaction atomicity.
- PR5 receives a clear, testable responsibility.
- The project preserves the earlier admission-boundary abstraction instead of losing it during PostgreSQL migration.
- Optimistic and pessimistic strategies can be compared without changing domain semantics.
- PostgreSQL-specific concurrency behavior can be tested explicitly.
- Raw database errors can later be mapped into stable application-level results.

### Negative Consequences

- Stage 3.5B becomes longer.
- The durable write-side baseline adds one more PR before moving to Stage 3.5C.
- The project must maintain a clear distinction between transaction failure, idempotency conflict, and admission rejection.

### Neutral but Important Consequence

PR5 is still not Stage 4 `SemanticOutcome` / runtime decision policy work.

PR5 may produce stable admission results, but formal semantic outcomes and runtime decisions remain later-stage concerns.

---

## Alternatives Considered

### Alternative A: Put concurrency handling directly into PR4

Rejected.

PR4 already introduces unit-of-work behavior and transactional command flow. Adding optimistic and pessimistic admission strategies into the same PR would mix transaction atomicity, command orchestration, and concurrent admission strategy in one review scope.

### Alternative B: Rely only on PostgreSQL constraints forever

Rejected.

Database constraints are necessary, but they are not enough as the application-level contract. The system should not force higher layers to reason directly about raw `UniqueViolation` or other low-level database exceptions.

### Alternative C: Defer concurrency admission until much later

Rejected as the default path.

The durable write-side baseline is incomplete if concurrent writers can only be understood as raw infrastructure failures. Since the project already had an in-memory admission boundary, it is appropriate to reintroduce that boundary after transaction atomicity is established.

---

## Non-goals

This decision does not require PR4 to implement concurrency admission.

This decision does not require PR5 to implement full Stage 4 `SemanticOutcome` or `RuntimeDecisionPolicy`.

This decision does not require production-grade distributed locking, connection pooling, retry orchestration, or operational alerting.

This decision does not claim the system is production-deployment complete.

---


## Related ADRs and Postmortems

- [ADR 0011 — Separate Validation Mode from Validation Placement Strategy](0011_validation_mode_vs_validation_placement.md)
- [Postmortem — From Durable Persistence to Semantic Gate Preservation](../postmortems/from_durable_persistence_to_semantic_gate_preservation.md)

Both ADR 0010 and ADR 0011 record boundary separations discovered during Stage 3.5B PR4.

ADR 0010 separates transaction atomicity from concurrency admission.

ADR 0011 applies the same boundary-first reasoning to Compass validation by separating validation strength from validation placement.

The related postmortem records the implementation lesson that durable persistence hardening must preserve Compass semantic gates rather than only preserving physical transaction correctness.

---

## Production-Grade Positioning

After PR5, Stage 3.5B can reasonably be described as a production-inspired durable write-side correctness baseline.

It will establish:

- durable accepted history
- durable idempotency memory
- transaction atomicity
- concurrent writer admission control
- exact money persistence
- UUID-compatible event identity
- replayable accepted history
- clear candidate / accepted event identity boundaries

It should not yet be described as a full production system.

Remaining production concerns include:

- connection pooling
- migration tooling
- structured observability
- operational retry policy
- deadlock handling
- production DB role hardening
- append-only triggers
- performance and load testing
- deployment configuration

---

## Summary

PR4 prevents partial durable writes.

PR5 will prevent uncontrolled concurrent admission.

Together, they complete the durable write-side correctness baseline for Stage 3.5B.

This decision keeps the architecture honest:

```text
transaction atomicity
≠ concurrent writer admission
```
