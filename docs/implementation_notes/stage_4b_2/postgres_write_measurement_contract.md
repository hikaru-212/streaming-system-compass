# Stage 4B.2 — PostgreSQL Write Measurement Contract

[← Back to Stage 4B.2](README.md)

## Status

```text
PR1 responsibility boundary
= complete

PR2 deterministic characterization
= accepted input

PR3 contract decisions
= implemented

PR3 implementation and validation
= COMPLETE / MERGED

PR4 production instrumentation
= COMPLETE / MERGED

PR5 correctness validation
= COMPLETE / MERGED

Stage 4B.2
= COMPLETE / CLOSED
```

This note records the Stage 4B.2 PR3 producer-specific Level-A contract selected
from PR1 vocabulary and PR2 executable mechanics. It does not authorize or
implement production timers.

## 1. Responsibility

The contract answers:

```text
for one normal-returning PostgreSQL write execution,
what elapsed evidence is available for the explicitly bounded work?
```

It remains separate from:

```text
PostgresWriteSideResult
= primary producer truth

PostgresWriteSideExecutionTrace
= bounded execution topology

PostgresWriteSideMeasurement
= execution-local elapsed evidence

DecisionReceipt
= durable governance evidence
```

No generic repository-wide `MeasurementEvidence` abstraction is introduced.

## 2. Immutable Contract Shape

PR3 selects these producer-specific public types:

```text
PostgresWriteSidePhaseMeasurementState
PostgresWriteSidePhaseMeasurement
PostgresWriteSideMeasurement
PostgresWriteSideMeasurementAvailability
PostgresWriteSideMeasurementDelivery
```

`PostgresWriteSidePhaseMeasurementState` has exactly four meanings:

```text
NOT_APPLICABLE
NOT_REACHED
NOT_COLLECTED
MEASURED
```

`PostgresWriteSidePhaseMeasurement` pairs one state with
`elapsed_ns: int | None`.

`PostgresWriteSideMeasurement` has the complete first-contract field surface:

```text
producer_write_invocation
business_uow
validation_runtime_call
preliminary_idempotency_check
preliminary_read_cleanup
authoritative_idempotency_check
accepted_history_load
concurrency_preparation_call
pessimistic_advisory_try_lock_call
append_admission_call
idempotency_record_call
commit_finalization
rollback_finalization
```

The full numeric path for the whole interval is intentionally:

```text
measurement.producer_write_invocation.elapsed_ns
```

`producer_write_invocation` is more precise than an unqualified `write` name:
the interval begins immediately before calling the existing producer API and
ends immediately after its normal return. It excludes the subsequent final
measurement-artifact construction and delivery work.

## 3. Units and Precision

Every new elapsed value uses integer nanoseconds.

```text
public collection representation
= non-negative integer nanoseconds

presentation conversion
= deferred to report or presentation boundaries
```

This preserves the native integer delta supported by PR2's
`perf_counter_ns()`-shaped seam, retains valid sub-millisecond evidence, avoids
float rounding in the immutable contract, and keeps measured zero valid.

The existing float-millisecond `ValidationResult.total_time_ms` remains
validator-local evidence and is unchanged. `validation_runtime_call` is a
different interval around `ValidationRuntime.decide(...)`.

## 4. Presence and Absence

The state/value invariant is:

```text
MEASURED
→ elapsed_ns is an integer >= 0

NOT_APPLICABLE | NOT_REACHED | NOT_COLLECTED
→ elapsed_ns is None
```

Therefore:

```text
measured zero
= state MEASURED + elapsed_ns 0

missing or absent evidence
!= numeric zero
```

Every available snapshot carries every named phase field. Applicability, reach,
and collection state are explicit; fields are not omitted.

## 5. Normal-Return Completeness

A constructible available snapshot guarantees:

- every named field is a `PostgresWriteSidePhaseMeasurement`;
- `producer_write_invocation` is measured;
- preliminary check and preliminary cleanup have compatible reached state;
- validation cannot be reached unless accepted-history load was reached;
- authoritative idempotency cannot be reached unless the business UOW was
  reached;
- concurrency preparation cannot be reached unless authoritative idempotency
  was reached;
- pessimistic advisory try-lock cannot be reached unless concurrency
  preparation was reached;
- append admission cannot be reached unless concurrency preparation was
  reached;
- idempotency record cannot be reached unless append admission was reached;
- a reached business UOW has exactly one reached commit or rollback
  finalization; and
- reached commit finalization requires a reached idempotency record.

`MEASURED` and `NOT_COLLECTED` both mean that a phase was reached for these
topology checks. `NOT_APPLICABLE` and `NOT_REACHED` do not.

These invariants describe current normal-return source topology. The contract
does not infer producer outcome or validation placement from elapsed evidence.
PR4 owns correct population, and PR5 owns source-boundary correctness tests.

## 6. Containment and Overlap

PR2's containment rules remain semantic requirements for instrumentation:

```text
producer write invocation
contains business UOW when reached

business UOW
contains its current authoritative, concurrency, append, record,
and finalization calls

concurrency preparation
may contain the concrete pessimistic advisory try-lock call

validation-runtime call
contains existing validator-local elapsed
```

Elapsed deltas alone do not prove positional containment, so the immutable
constructor does not invent start/stop timestamps or infer containment by
summing. Child intervals overlap with parent and sibling work. The contract
deliberately permits the sum of detailed elapsed values to exceed the producer
write invocation.

## 7. Result-First Delivery and Availability

`PostgresWriteSideMeasurementDelivery` stores, first, the exact producer value:

```text
PostgresWriteSideResult
or
PostgresWriteSideExecution
```

It then stores:

```text
availability = AVAILABLE
+ measurement = PostgresWriteSideMeasurement

or

availability = UNAVAILABLE
+ measurement = None
```

The unavailable form is reserved for narrowly measurement-owned final
construction failure after the existing producer returned normally. It does
not require fabricated phase values and does not reinterpret the producer
value.

The delivery envelope validates only its own type and availability coherence.
It does not duplicate result, trace, outcome, admission, idempotency, or
accepted-event semantics. The producer object is retained by identity.

[ADR 0023](../../adr/0023_measurement_availability_does_not_govern_business_truth.md)
owns the transaction/correctness boundary.

## 8. Explicit Capability Boundary

Detailed measurement is opt-in at the execution surface:

```text
existing create_order / pay_order
+ existing traced variants
→ remain valid and unmeasured

future explicit PR4 measurement-enabled surface
→ returns PostgresWriteSideMeasurementDelivery
```

PR3 does not name or implement the PR4 methods. It adds no runtime flags,
sampling, dynamic policy, or always-present collector.

[ADR 0024](../../adr/0024_detailed_postgres_write_measurement_is_opt_in.md)
owns this capability and observer-overhead decision.

## 9. Explicit Non-Goals

PR3 does not implement:

- production clock reads or timers;
- measured producer methods;
- performance, load, concurrency, or benchmark experiments;
- DiagnosticTrace timing;
- DecisionReceipt cost population;
- persistence, migrations, schemas, or event metadata;
- strategy selection, sampling, retry, AttemptLog, or rate limiting; or
- generic measurement, telemetry, or observability infrastructure.

## 10. Validation Record

Repository-local Python was used for every test command.

```text
focused PR3 contract tests
= 38 passed

PR2 mechanics + relevant write-side / UOW / admission / trace /
validation / DecisionReceipt boundary unit tests
= 355 passed

complete tests/unit tree
= 1108 passed
```

The relevant run includes PR2's expanded accepted/non-accepted and
legacy/traced post-UOW construction-failure matrix, replacing the pending rerun
qualification recorded in the PR2 note.

No PostgreSQL integration test was run or claimed for this pure immutable-
contract PR. No environment file or credential was inspected, no database was
started, and no performance, load, concurrency, or benchmark experiment ran.
