# Stage 4B.2 — Measurement Mechanics Characterization

[← Back to Stage 4B.2](README.md)

## Status

```text
PR1 responsibility boundary
= complete

PR2 deterministic characterization
= in progress / documentation first

production measurement contract
= not implemented

production instrumentation
= not implemented
```

This note defines the Stage 4B.2 PR2 characterization plan before executable
evidence is added.

PR2 is intentionally characterization-first.

It does not freeze the later PR3 immutable contract, authorize PR4 production
instrumentation, run real performance experiments, or make latency claims.

The intended evidence artifact for the next commit is:

```text
tests/unit/pipeline/transactional/
test_postgres_write_side_measurement_characterization.py
```

The executable characterization should wrap current collaborator and
unit-of-work boundaries without reproducing the PRE_TRANSACTION or
IN_TRANSACTION write algorithms and without changing production source.

## 1. Responsibility to Preserve

PR2 must preserve:

```text
PostgresWriteSideExecutionTrace
= bounded execution topology

measurement evidence
= elapsed evidence for explicitly bounded work actually performed

PostgresWriteSideExecutionTrace
!= measurement evidence
```

No timing field should be added to `PostgresWriteSideExecutionTrace`.

The current primary Result, traced Execution, `SemanticOutcome`,
`DecisionReceipt`, accepted-event metadata, persistence model, and business
authority boundaries must remain unchanged.

PR2 should answer:

```text
How must measurement behave around the current PostgreSQL write-side
execution and transaction boundaries before PR3 freezes a contract?
```

It should not answer:

```text
Which strategy is faster?
```

That belongs to later empirical Stage 4B.2 work.

## 2. Deterministic Clock Characterization

PR2 should evaluate the smallest deterministic monotonic clock seam required to
test elapsed-time semantics without wall-clock thresholds.

The current planning direction is:

```text
clock call
→ integer monotonic reading

elapsed
= stopped_ns - started_ns
```

A callable shaped like:

```text
time.perf_counter_ns()
```

is the current candidate.

PR2 should characterize at least:

- deterministic non-zero elapsed values;
- measured zero as a valid value;
- no dependence on real sleep or scheduler timing;
- no need for latency thresholds;
- no external benchmark dependency.

PR2 must not yet freeze:

- the public measurement unit;
- the final immutable representation;
- presentation conversion;
- rounding rules.

Those remain PR3 decisions.

## 3. Candidate Timer Boundaries to Characterize

PR2 should test the mechanics for the following source-grounded boundaries.

| Candidate | Planned start | Planned stop |
|---|---|---|
| Whole write invocation | Immediately before entering the existing legacy or traced write API. | Immediately after that API returns normally, after business-UOW finalization when reached and before final measurement construction. |
| Business-UOW lifecycle | `PostgresWriteSideUnitOfWork.__enter__()` call entry. | After `PostgresWriteSideUnitOfWork.__exit__()` returns normally. |
| Validation-runtime call | Immediately before `ValidationRuntime.decide(...)`. | Immediately after its `ValidationDecision` returns. |
| Preliminary idempotency check | Immediately before the PRE read-store `check(...)`. | Immediately after its typed decision returns. |
| Preliminary read cleanup | Immediately before the PRE `connection.rollback()` in the `finally` block. | Immediately after that rollback returns. |
| Authoritative idempotency check | Immediately before the business-UOW `check(...)`. | Immediately after its typed decision returns. |
| Accepted-history load | Immediately before `PostgresEventStore.load(...)`. | Immediately after the history list returns, before aggregate rehydration continues. |
| Concurrency preparation | Immediately before `prepare_stream(...)`. | Immediately after its typed `StreamAdmissionResult` returns. |
| Pessimistic advisory try-lock | Immediately before concrete `_try_lock_stream(...)`. | Immediately after acquired/not-acquired returns. |
| Append admission | Immediately before `append_if_admitted(...)`. | Immediately after its typed `AdmissionResult` returns. |
| Idempotency record | Immediately before `PostgresIdempotencyStore.record(...)`. | Immediately after normal return inside the current transaction. |
| Commit finalization | Immediately before `PostgresWriteSideUnitOfWork.commit()`. | Only after `commit()` returns normally. |
| Rollback finalization | Immediately before `PostgresWriteSideUnitOfWork.rollback()`. | Only after `rollback()` returns normally. |

PR2 should verify that an operation which raises after timer start does not
silently become a completed normal-return interval.

Current exceptions must retain their existing propagation semantics.

### Whole-invocation self-measurement question

PR2 must explicitly characterize the boundary between the existing write
operation and measurement artifact construction / delivery.

The current candidate interpretation is:

```text
existing write API entry
→ existing write API normal return after UOW finalization
→ whole-invocation stop
→ final measurement construction
```

If accepted, the producer-owned whole-invocation elapsed value excludes its own
post-stop measurement-artifact construction and delivery overhead.

PR2 should establish whether this boundary is mechanically sound without
freezing the final PR3 field name.

## 4. Containment and Overlap Questions

PR2 must characterize timing as nested intervals rather than independent
additive buckets.

The current expected relationships are:

```text
whole invocation
contains
business UOW when reached

business UOW
contains for PRE and IN
authoritative idempotency
+ concurrency preparation
+ append admission
+ idempotency record
+ finalization

business UOW
contains additionally for IN
accepted-history load
+ aggregate / context / candidate preparation
+ validation-runtime call

concurrency preparation
contains for concrete IN pessimistic admission
pessimistic advisory try-lock call

validation-runtime call
contains
validator-local elapsed
```

For PRE, accepted-history loading and validation occur before the business UOW.

PR2 should verify that nested durations can legitimately sum to more than the
whole-invocation duration.

PR3 must not later define:

```text
whole elapsed
= sum(all detailed phase elapsed)
```

unless executable evidence proves non-overlap.

## 5. Presence and Absence Semantics

PR2 must characterize these states as semantically distinct:

```text
phase not applicable
!= phase applicable but not reached
!= phase reached but measurement not collected
!= measured duration equal to zero
```

The characterization may use test-only vocabulary or enums, but PR2 must not
freeze the final PR3 representation.

Numeric zero must not become the missing-value sentinel.

A genuine zero clock delta must remain a measured value.

## 6. Planned Normal-Return Measurement Topology

The following abbreviations are planning notation only:

| Abbreviation | Candidate phase |
|---|---|
| `W` | whole write invocation |
| `U` | business-UOW lifecycle |
| `PI` | preliminary idempotency check |
| `PC` | preliminary read rollback / cleanup |
| `AI` | authoritative idempotency check |
| `H` | accepted-history load |
| `C` | concurrency-preparation call |
| `L` | pessimistic advisory try-lock call |
| `V` | validation-runtime call, containing existing validator-local timing |
| `A` | append-admission call |
| `IR` | idempotency-record call |
| `CM` | commit finalization |
| `RB` | rollback finalization |

### PRE_TRANSACTION candidate topology

| Current normal-return path | Expected candidate measurement phases |
|---|---|
| Preliminary replay | `W, PI, PC` |
| Preliminary conflict | `W, PI, PC` |
| Validation block | `W, PI, H, PC, V` |
| Authoritative replay | `W, PI, H, PC, V, U, AI, RB` |
| Authoritative conflict | `W, PI, H, PC, V, U, AI, RB` |
| Injected preparation rejection | `W, PI, H, PC, V, U, AI, C, RB` |
| Append `STALE_WRITE` | `W, PI, H, PC, V, U, AI, C, A, RB` |
| Accepted write | `W, PI, H, PC, V, U, AI, C, A, IR, CM` |

The default optimistic gate's current preparation is expected to remain an
admitted no-op. The preparation-rejection row is only a candidate for the
existing injected gate contract and must not be described as default optimistic
behavior.

### IN_TRANSACTION + concrete pessimistic candidate topology

| Current normal-return path | Expected candidate measurement phases |
|---|---|
| Authoritative replay | `W, U, AI, RB` |
| Authoritative conflict | `W, U, AI, RB` |
| Advisory non-acquisition / preparation rejection | `W, U, AI, C, L, RB` |
| Validation block | `W, U, AI, C, L, H, V, RB` |
| Append rejection | `W, U, AI, C, L, H, V, A, RB` |
| Accepted write | `W, U, AI, C, L, H, V, A, IR, CM` |

PR2 should verify that pessimistic preparation rejection exits before protected
history loading and validation.

## 7. Commit and Rollback Characterization Questions

PR2 must characterize finalization ordering for clean accepted, normal
non-accepted, and exceptional unfinished UOW paths.

The current expected ordering is:

```text
clean accepted path
→ commit returns
→ commit timer stops
→ UOW lifecycle stops
→ whole invocation stops
```

```text
normal non-accepted UOW path
→ explicit rollback returns
→ rollback timer stops
→ completed UOW context exits
→ UOW lifecycle stops
→ whole invocation stops
```

```text
exceptional unfinished UOW path
→ current __exit__ invokes rollback
→ original exception continues propagating
→ no normal-return whole-invocation measurement delivery
```

PR2 must not translate commit or rollback exceptions into typed measurement
results.

## 8. Existing Validator Timing Question

The current source already exposes:

```text
ValidationResult.total_time_ms
```

PR2 should prove its exact relationship to:

```text
ValidationRuntime.decide(...)
```

The current expected distinction is:

```text
ValidationResult.total_time_ms
= validator-local elapsed

validation-runtime call elapsed
= dispatcher
+ validator
+ policy
+ ValidationDecision construction boundary
```

PR2 must not silently reinterpret the existing validator-local field.

Existing synthetic `0.0` timing values in Stage 4B.1 topology tests must remain
topology evidence rather than performance evidence.

## 9. Post-UOW Delivery — Primary Characterization Question

This is the highest-priority PR2 question.

ADR 0022 remains specific to the current traced APIs:

```text
valid Result + Trace + Execution
must exist before clean UOW exit
```

Stage 4B.2 cannot assume the same lifecycle for final measurement evidence,
because important elapsed values become complete only after UOW finalization.

PR2 must test the consequences of fallible measurement construction inside an
unfinished UOW and compare that with a result-first post-UOW construction model.

The required safety objective is:

```text
business truth
must not depend on
measurement availability
```

Candidate safe direction:

```text
existing producer call returns after UOW finalization
→ primary Result or traced Execution is already final
→ whole-invocation timer stops
→ attempt final measurement construction
```

If measurement-owned construction fails after business truth is already
established, PR2 should determine whether the producer value can remain
unchanged while measurement is represented unavailable.

The characterization must cover:

- accepted producer results after commit;
- normal typed non-accepted producer results after rollback;
- legacy producer surfaces;
- traced producer surfaces.

PR2 must not catch or translate existing producer, validation, admission,
idempotency, commit, rollback, or trace exceptions merely to guarantee
measurement delivery.

## 10. Measured / Existing API Parity Constraint

The future measurement-enabled execution must preserve:

- primary result values and nested evidence;
- accepted-event identity;
- accepted-history and idempotency mutation;
- validation, admission, and idempotency semantics;
- commit and rollback behavior;
- exception types and propagation;
- existing traced API construction ordering and behavior;
- existing legacy API behavior.

PR2 should characterize this parity without implementing the final measured API.

## 11. PR3 Handoff Criteria

PR2 is complete only when executable evidence is sufficient for human review of:

- exact producer-specific immutable type and field names;
- internal/public units and precision;
- representation of not applicable, not reached, not collected, measured zero,
  and measurement unavailable;
- normal-return completeness invariants;
- exact result/measurement delivery envelope;
- the narrow measurement-construction failure boundary;
- containment and overlap semantics.

PR2 must stop if these decisions would still require guessing about transaction,
finalization, result, trace, or exception mechanics.

The intended output is:

```text
characterized mechanics
→ reviewed findings
→ safe PR3 contract design
```

not:

```text
characterization
→ immediate production instrumentation
```

## 12. Non-Goals

PR2 does not implement:

- the immutable production measurement contract;
- production timing instrumentation;
- performance comparison;
- load or concurrency experiments;
- PostgreSQL benchmark artifacts;
- `DiagnosticTrace` timing;
- `DecisionReceipt` cost population;
- accepted-event metadata timing;
- schema or migration changes;
- persistence;
- generic `MeasurementEvidence`;
- strategy selection;
- automatic strategy switching;
- retry;
- `AttemptLog`;
- telemetry backend;
- OpenTelemetry;
- connection pooling;
- rate limiting.

## 13. Planned Validation

After the executable characterization commit is added, validation should proceed
from focused to wider unit coverage.

Planned validation:

```text
focused PR2 characterization tests
→ relevant write-side / UOW / trace / validator unit tests
→ complete tests/unit tree
```

PostgreSQL integration validation may be attempted only as deterministic
regression evidence if the required test database is already configured.

PR2 must not run performance, load, or concurrency experiments.

No validation result is claimed by this documentation-first commit.

## Completion Rule

This documentation-first commit defines what PR2 must prove.

It does not claim those mechanics have already been established.

After executable characterization is added and reviewed, this note should be
updated in a later documentation commit to record:

- actual findings;
- accepted timer boundaries;
- validated presence / absence topology;
- post-UOW delivery evidence;
- exception-preservation evidence;
- validation results;
- PR3 handoff decisions.
