# ADR 0012: Two-Phase Concurrency Admission for PostgreSQL Write-Side

[← Back to ADR Index](README.md)

## Status

Proposed

## Context

Stage 3.5B PR5 introduces PostgreSQL-backed concurrency admission for the durable write-side flow.

Earlier in PR5, the project established a single-phase admission interface:

```text
append_if_admitted(candidate_event, expected_current_version)
```

This interface models **append-time admission**. It answers whether a candidate event may occupy the next accepted-history stream position.

This was sufficient for optimistic concurrency control:

```text
load accepted history
→ rehydrate aggregate
→ create candidate event
→ run Compass validation
→ append_if_admitted(candidate_event, expected_version)
→ append event if admitted
```

For optimistic admission, this is natural:

```text
Do not lock early.
Try to append.
Reject stale writers at append time.
```

However, when pessimistic admission was introduced, the same single-phase interface forced the lock to be acquired inside `append_if_admitted()`. Because `append_if_admitted()` requires a `candidate_event`, the lock could only be acquired after:

```text
accepted-history loading
→ aggregate rehydration
→ candidate event creation
→ Compass validation
```

This created **late locking**.

Late locking can still prevent conflicting writes, but it does not prevent duplicated read and validation work under high contention. Multiple competing writers may all read the same stream, rehydrate the same aggregate, and run validation before only one writer is finally admitted.

This is not a correction of a broken design. It is an evolution of the admission abstraction.

The original single-phase admission interface correctly modeled append-time admission. The need for two phases appeared only after the system expanded from optimistic append-time admission to true pessimistic stream protection.

## Problem

Pessimistic locking has a different timing requirement from optimistic locking.

Optimistic admission is naturally late:

```text
read
→ validate
→ try append
→ reject stale writer if needed
```

Pessimistic admission often needs to be early:

```text
acquire stream lock
→ read
→ validate
→ append while lock is held
```

The original interface only allowed this:

```text
append_if_admitted(candidate_event, expected_version)
```

But before reading and validation, no candidate event exists yet.

Therefore, a single `append_if_admitted()` method cannot represent both moments:

```text
1. entering the stream critical section
2. occupying the next accepted-history position
```

A possible short-term solution would be to create separate write-side flows:

```text
create_order_optimistic()
create_order_pessimistic()
pay_order_optimistic()
pay_order_pessimistic()
```

This option is rejected because it would split write-side business orchestration by physical locking strategy.

The write-side flow owns more than locking:

```text
idempotency check
accepted-history loading
aggregate rehydration
candidate event creation
Compass validation
admission
idempotency record persistence
transaction commit / rollback
```

Duplicating the flow for each concurrency strategy would create long-term maintenance risk. Future changes to idempotency, validation, Stage 4 SemanticOutcome mapping, or governance reporting could easily be applied to one path and missed in another.

The physical lock strategy should not force business orchestration to fork.

## Decision

Evolve the admission interface from single-phase admission to **two-phase concurrency admission**.

The gate interface should support two distinct moments:

```text
prepare_stream(order_id)
append_if_admitted(candidate_event, expected_current_version)
```

## Phase 1: Stream Preparation

`prepare_stream(order_id)` runs after idempotency classification but before accepted-history loading, aggregate rehydration, candidate event creation, and Compass validation.

It answers:

```text
May this writer enter the stream critical section?
```

For optimistic admission:

```text
prepare_stream(order_id)
→ no-op
→ ADMITTED
```

For pessimistic admission:

```text
prepare_stream(order_id)
→ acquire transaction-scoped stream lock
→ ADMITTED if the lock is acquired
→ LOCK_TIMEOUT if the lock is unavailable
```

This allows pessimistic admission to protect the expensive read / rehydrate / validation section without requiring a separate write-side flow.

## Phase 2: Append-Time Admission

`append_if_admitted(candidate_event, expected_current_version)` runs after candidate event creation and Compass validation.

It answers:

```text
May this candidate event occupy the next accepted-history stream position?
```

For optimistic admission:

```text
append_if_admitted(candidate_event, expected_version)
→ attempt append
→ ADMITTED or STALE_WRITE
```

For pessimistic admission:

```text
append_if_admitted(candidate_event, expected_version)
→ append while the stream lock is already held
→ ADMITTED or STALE_WRITE
```

Even under pessimistic locking, append-time expected-version checking remains necessary as a final safety boundary.

The early lock protects the stream critical section. The append-time check protects accepted-history continuity.

## Ordering Rule

The durable write-side flow should classify idempotency before stream preparation:

```text
BEGIN / UoW
→ idempotency check
→ if REPLAY / CONFLICT: rollback and return
→ prepare_stream(order_id)
→ load accepted history
→ rehydrate aggregate
→ create candidate event
→ Compass validation
→ append_if_admitted(candidate_event, expected_version)
→ record idempotency result
→ COMMIT
```

This avoids wasting stream locks on requests that are already known replay or conflict cases.

Idempotency replay and conflict classification are not concurrency admission problems. They should be resolved before acquiring a pessimistic stream lock.

## Physical Transaction Boundary Note

Pessimistic `prepare_stream(order_id)` relies on a transaction-scoped PostgreSQL advisory lock.

That means the connection must preserve an active transaction boundary while the protected work runs.

If `autocommit=True`, a transaction-scoped lock may be acquired and then released immediately when the lock statement completes. This would make the pessimistic gate look valid at the API level while failing to protect the stream critical section physically.

Therefore, the PostgreSQL pessimistic admission gate should fail closed when `autocommit=True`, returning an infrastructure-level admission failure instead of pretending the stream lock is active.


## Rejected Alternative: Separate Pessimistic Write-Side Flow

A separate pessimistic write-side implementation was considered and rejected.

Rejected shape:

```text
create_order_optimistic()
create_order_pessimistic()
pay_order_optimistic()
pay_order_pessimistic()
```

This approach would make the physical locking strategy leak into business orchestration.

It would also duplicate idempotency, validation, admission, and transaction-control logic across multiple flows.

The project should preserve one write-side orchestration path and allow concurrency strategy to vary behind the admission interface.

## Consequences

### Positive

- Preserves one durable write-side orchestration flow.
- Allows pessimistic admission to acquire a stream lock before expensive read / validation work.
- Keeps optimistic admission lightweight.
- Prevents physical lock strategy from splitting business logic.
- Keeps admission results separate from Stage 4 SemanticOutcome.
- Allows future policy-based strategy selection without changing write-side command methods.
- Makes the lock timing explicit instead of hiding it inside append-time admission.

### Negative

- The admission interface becomes more complex.
- The write-side flow must handle both stream-preparation rejection and append-time rejection.
- Early pessimistic admission increases transaction and lock duration. When a pessimistic gate acquires the stream lock during `prepare_stream(order_id)`, the lock is held across accepted-history loading, aggregate rehydration, candidate-event creation, Compass validation, append-time admission, idempotency recording, and commit / rollback.
- This reduces duplicated work under contention, but it also means slow validation or long-running write-side logic can hold the database transaction and stream lock for longer. This may increase pressure on the connection pool under high contention.
- Tests must distinguish between:
  - replay / conflict before stream preparation
  - prepare-time `LOCK_TIMEOUT`
  - validation block
  - append-time `STALE_WRITE`
  - successful admission

### Deferred

This ADR does not introduce:

- admission attempt persistence
- retry policy
- hot-stream detection
- automatic optimistic-to-pessimistic switching
- Stage 4 SemanticOutcome mapping
- Stage 5 governance metrics
- durable lock table

Those remain future concerns.

## Implementation Direction

Suggested commit sequence:

```text
Commit 6:
- Add StreamAdmissionResult
- Add ConcurrencyGate.prepare_stream(order_id)
- Implement optimistic prepare_stream as no-op
- Move pessimistic advisory lock acquisition into prepare_stream
- Keep append_if_admitted(candidate_event, expected_version) as append-time admission

Commit 7:
- Integrate prepare_stream + append_if_admitted into PostgresTransactionalWriteSide
- Preserve idempotency-before-prepare ordering
- Add tests for prepare-time LOCK_TIMEOUT
- Add tests proving replay / conflict does not acquire stream lock
- Add tests proving admission rejection does not persist event or idempotency record
```

## Related

- [ADR 0010: Transaction Atomicity vs Concurrency Admission](0010_transaction_atomicity_vs_concurrency_admission.md)
- [ADR 0011: Validation Mode vs Validation Placement](0011_validation_mode_vs_validation_placement.md)
- [PostgreSQL Concurrency Admission Boundary Note](../boundary_notes/postgres_concurrency_admission_boundary.md)
- [Postmortem: Autocommit, Transaction Boundaries, and Partial-Write Risk](../postmortems/autocommit_boundary_and_partial_write_risk.md)
