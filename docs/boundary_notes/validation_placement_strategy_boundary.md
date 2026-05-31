# Validation Placement Strategy Boundary

[← Back to Boundary Notes Index](README.md)

## Purpose

This note defines the Stage 3.5B PR6 / Stage 4 Prelude boundary:

```text
Validation Placement Strategy
```

This boundary note does not replace ADR 0011.

ADR 0011 records the architecture decision that `ValidationMode`, `ValidationPlacement`, `TransactionAtomicity`, and `ConcurrencyAdmission` are separate design axes.

This note is narrower. It describes how PR6 should turn that decision into an implementation boundary after PR5 two-phase PostgreSQL concurrency admission exists.

---

## Why This Boundary Exists Now

PR4 established the PostgreSQL-backed transactional semantic write-side baseline:

```text
accepted event append
+ idempotency record persistence
+ Compass Layer 1 validation
+ shared PostgreSQL transaction
```

PR5 established PostgreSQL-backed two-phase concurrency admission:

```text
prepare_stream(order_id)
→ append_if_admitted(candidate_event, expected_current_version)
```

After PR5, the project can safely evaluate a second validation placement:

```text
PRE_TRANSACTION validation
+ append-time concurrency admission
```

Before PR5, this would have been unsafe because a candidate event validated outside the transaction could become stale before append.

PR5 provides the final admission boundary needed to reject that stale candidate before it enters accepted history.

---

## Core Boundary

```text
ValidationMode
≠
ValidationPlacement
```

`ValidationMode` answers:

```text
How strong is validation?
```

Examples:

```text
STRICT
OFF
future PARTIAL / AUDIT
```

`ValidationPlacement` answers:

```text
Where does validation run relative to the PostgreSQL transaction boundary?
```

Initial placement options:

```text
IN_TRANSACTION
PRE_TRANSACTION
future ASYNC_AUDIT
```

PR6 is about `ValidationPlacement`.

It should not redefine validation strength, domain legality, idempotency classification, or concurrency admission.

---

## Relationship to ADR 0011

ADR 0011 already defines the conceptual distinction:

```text
Validation mode
≠
Validation placement
≠
concurrency admission
```

This boundary note uses that decision as a starting point.

PR6 should not re-litigate whether validation mode and validation placement are separate.

PR6 should decide the minimal implementation shape needed to support placement-aware write-side orchestration.

---

## Relationship to PR5

PR5 is a required dependency because `PRE_TRANSACTION` validation relies on append-time admission.

The safe model is:

```text
candidate event validated before transaction
→ BEGIN / UoW
→ idempotency check
→ prepare_stream(order_id)
→ append_if_admitted(candidate_event, expected_current_version)
→ only admitted candidate can become accepted history
→ record idempotency result
→ COMMIT
```

The critical safety rule is:

```text
PRE_TRANSACTION validation is not safe without append-time concurrency admission.
```

PR5 provides that admission boundary.

---

## Placement Option: IN_TRANSACTION

`IN_TRANSACTION` validation runs Compass validation inside the PostgreSQL write-side transaction.

Typical flow:

```text
BEGIN / UoW
→ idempotency check
→ prepare_stream(order_id)
→ load accepted history
→ rehydrate aggregate
→ create candidate event
→ Compass validation
→ append_if_admitted(candidate_event, expected_current_version)
→ record idempotency result
→ COMMIT
```

Expected properties:

- strongest semantic and physical coupling
- validation and append happen in one transaction scope
- pessimistic stream locks may be held across validation
- transaction duration may be longer
- useful for high-risk or irreversible flows

This is the current durable write-side baseline.

---

## Placement Option: PRE_TRANSACTION

`PRE_TRANSACTION` validation runs Compass validation before the PostgreSQL write transaction.

Typical flow:

```text
load accepted history
→ rehydrate aggregate
→ create candidate event
→ Compass validation

BEGIN / UoW
→ idempotency check
→ prepare_stream(order_id)
→ append_if_admitted(candidate_event, expected_current_version)
→ record idempotency result
→ COMMIT
```

Expected properties:

- shorter database transaction duration
- validation does not hold PostgreSQL transaction resources
- stale candidates must be rejected by append-time admission
- may increase stale-write rejection or retry frequency under contention
- useful for latency comparison and lower-risk / compensatable flows

This is the main new placement mode PR6 should evaluate.

---

## Future Placement Option: ASYNC_AUDIT

`ASYNC_AUDIT` is not part of PR6.

It may later support:

- background validation
- low-risk audit
- delayed semantic inspection
- non-blocking runtime evidence collection

This belongs to later Stage 4 / Stage 5 work.

---

## Why This Matters Before Stage 4

Stage 4 may introduce:

- structured `SemanticOutcome`
- runtime decision policy
- validation timing evidence
- registry-stage timing
- runtime evidence persistence
- action safety gates

However, timing and evidence are less useful if the system has only one fixed orchestration path.

Without validation placement strategy, Stage 4 timing can only measure:

```text
the current in-transaction flow
```

It cannot compare:

```text
IN_TRANSACTION validation
vs
PRE_TRANSACTION validation + append-time concurrency admission
```

Therefore PR6 acts as a Stage 4 prelude.

It establishes the placement dimension before Stage 4 decides how to persist timing, outcomes, evidence, or runtime decisions.

---

## PR6 Scope

PR6 should introduce a minimal validation placement strategy baseline.

Expected work:

- define `ValidationPlacement`
- introduce a minimal write-side configuration or factory boundary
- preserve `IN_TRANSACTION` as the default behavior
- add a minimal `PRE_TRANSACTION` orchestration path
- keep append-time admission mandatory for `PRE_TRANSACTION`
- add tests proving stale pre-validated candidates cannot enter accepted history
- optionally expose in-memory timing metadata for latency comparison

---

## PR6 Non-Goals

PR6 does not introduce:

- Stage 4 `SemanticOutcome`
- `RuntimeDecisionPolicy`
- validation attempt persistence table
- registry-stage timing table
- admission attempt persistence table
- automatic placement selection
- retry policy
- hot-stream routing
- async audit pipeline
- production observability integration

Those belong to later Stage 4 / Stage 5 work.

---

## Required Safety Rules

### Rule 1: PRE_TRANSACTION must still use append-time admission

Pre-transaction validation can become stale.

Therefore append-time admission remains mandatory:

```text
validated candidate event
→ append_if_admitted(candidate_event, expected_current_version)
→ accepted history mutation only if admitted
```

### Rule 2: Validation placement must not change domain legality

Domain legality still belongs to the aggregate.

Validation placement only changes where Compass validation runs.

It does not redefine command legality.

### Rule 3: Validation placement must not bypass idempotency

Replay and conflict classification remain part of the write-side safety model.

PR6 may compare where validation runs, but it must not allow duplicate requests to create duplicate semantic effects.

### Rule 4: Validation placement must remain separate from validation mode

The system should support combinations such as:

```text
STRICT + IN_TRANSACTION
STRICT + PRE_TRANSACTION
OFF + IN_TRANSACTION
OFF + PRE_TRANSACTION
```

This allows future measurement baselines without confusing validation strength and validation location.

---

## Implementation Notes

A likely minimal implementation path is:

```text
ValidationPlacement enum
PostgresWriteSideConfig
write-side factory
IN_TRANSACTION flow wrapper around current behavior
PRE_TRANSACTION flow using PR5 admission as final guard
placement-specific tests
```

The implementation should avoid duplicating domain logic.

The goal is not to create unrelated write-side systems.

The goal is to share:

```text
PostgresEventStore
PostgresIdempotencyStore
PostgresWriteSideUnitOfWork
ValidationRuntime
OrderAggregate
ValidationContext construction
AdmissionGate
PostgresWriteSideResult
```

while allowing orchestration placement to vary.

---

## Related

- [ADR 0010: Separate Transaction Atomicity from Concurrency Admission](../adr/0010_transaction_atomicity_vs_concurrency_admission.md)
- [ADR 0011: Separate Validation Mode from Validation Placement Strategy](../adr/0011_validation_mode_vs_validation_placement.md)
- [ADR 0012: Two-Phase Concurrency Admission for PostgreSQL Write-Side](../adr/0012_two_phase_concurrency_admission.md)
- [Autocommit, Transaction Boundaries, and Partial-Write Risk](../postmortems/autocommit_boundary_and_partial_write_risk.md)
