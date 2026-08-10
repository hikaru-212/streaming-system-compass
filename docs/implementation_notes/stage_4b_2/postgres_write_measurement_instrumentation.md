# Stage 4B.2 — PostgreSQL Write Measurement Instrumentation

[← Back to Stage 4B.2](README.md)

## Status

```text
PR3 immutable contract
= COMPLETE / MERGED

PR4 production instrumentation
= IMPLEMENTED
+ DETERMINISTIC UNIT VALIDATION COMPLETE
+ AWAITING HUMAN REVIEW

PR5 measurement correctness validation
= NOT STARTED
```

This note is the formal Stage 4B.2 PR4 implementation record. It documents how
the merged PR3 contract is populated by the explicit production measurement
surface without reopening its shape, ADR 0023, or ADR 0024.

## 1. Implementation Finding

The PR3 contract is populated through narrow seams around the current shared
write algorithms.

```text
PR3 contract change required
= no

ADR 0023 or ADR 0024 change required
= no

write algorithm duplication required
= no
```

The load-bearing design is one invocation-local recorder passed only by an
explicit measured API. Existing unmeasured calls pass no recorder. PRE and IN
each retain one shared production algorithm; the unmeasured path therefore
retains small recorder-absence branches, whose cost is not characterized by
PR4.

## 2. Measured Public Surface

The current naming convention uses explicit capability suffixes such as
`*_with_trace`. PR4 therefore adds:

```text
create_order_with_measurement(...)
pay_order_with_measurement(...)

create_order_with_trace_and_measurement(...)
pay_order_with_trace_and_measurement(...)
```

Every method returns `PostgresWriteSideMeasurementDelivery`.

The legacy measured forms retain the exact `PostgresWriteSideResult` produced by
the shared algorithm. The traced measured forms retain the exact
`PostgresWriteSideExecution`, including the same trace object built under ADR
0022 before clean UOW exit.

Existing method signatures are unchanged. No enable flag, per-phase switch,
sampling percentage, or dynamic policy is added.

The Stage 4B.2 measured interpretation is intentionally limited to two current
canonical compositions:

```text
PRE_TRANSACTION + current optimistic/OCC append-time admission
IN_TRANSACTION + current concrete PostgreSQL pessimistic admission
```

`PRE_TRANSACTION + pessimistic` and `IN_TRANSACTION + optimistic` remain valid
only according to their existing unmeasured business APIs; they are outside the
Stage 4B.2 measured interpretation surface and must not support phase-
applicability or strategy-performance conclusions.

The admission factory is an opaque callable and is first invoked at its current
position inside business execution. Clean pre-execution rejection would
require constructing the gate early, bypassing the factory, or adding new
configuration machinery. PR4 does none of those. Unsupported measured
cross-combinations are documented as not interpretation-safe rather than
rejected through a behavior-changing preflight.

## 3. Invocation-Local State and Clock

`_PostgresWriteSideMeasurementRecorder` owns mutable readings for one explicit
measured invocation. It is created immediately before the producer whole timer
starts and is not stored on `PostgresTransactionalWriteSide`.

Each mutable reading retains:

```text
applicable
reached
elapsed_ns
```

Only final post-return construction translates those readings into the frozen
PR3 state vocabulary.

The production seam is:

```text
time.perf_counter_ns
→ Callable[[], int]
→ non-negative elapsed integer nanoseconds
```

The callable is captured by the invocation-local recorder. Tests replace only
that callable with the existing PR2 manual clock. No wall-clock timestamp,
sleep, threshold, or millisecond conversion is used.

Clock exceptions, non-integer readings, boolean readings, or backwards deltas
do not escape into business execution. The affected reached phase remains
`NOT_COLLECTED`. Clock acquisition is the narrow safe-collection boundary; the
recorder does not catch the business operation supplied to `measure_call`.

The whole producer interval is mechanically special only because the frozen
PR3 snapshot requires it to be `MEASURED`. A failed start or stop reading does
not change a normally returned producer value, but post-return snapshot
construction cannot satisfy that invariant and delivery becomes `UNAVAILABLE`.

## 4. Current Algorithm Instrumentation

The PRE and IN algorithms remain one source path each. Optional recorder checks
wrap only the established calls. No aggregate rehydration, context construction,
or candidate construction timer is added.

### PRE_TRANSACTION

The invocation-local recorder exists before preliminary work. It retains:

- preliminary idempotency timing;
- accepted-history load timing;
- preliminary rollback/cleanup timing from the current `finally` block;
- validation-runtime call timing outside the business UOW; and
- later UOW-owned phases when validation allows execution to continue.

The concrete optimistic preparation call is measured and may validly produce a
zero delta. Pessimistic advisory try-lock is `NOT_APPLICABLE` for the accepted
PRE + optimistic composition.

### IN_TRANSACTION + concrete pessimistic admission

A measured UOW subclass is instantiated only for an explicit measured call. It
reuses the current UOW implementation while timing normal `__enter__` through
normal `__exit__`, plus current `commit()` and `rollback()` calls.

The admission factory remains authoritative and runs at its existing point. If
it returns the exact current concrete pessimistic class, a measured subclass is
constructed before preparation from only the returned gate's public/current
constructor inputs (`connection` and `event_store`). The inherited preparation
and append algorithms are reused, while the subclass overrides only
`_try_lock_stream` and calls the current superclass method inside the timer.

The adapter does not copy `_prepared_order_ids` and does not retain a bound
`_try_lock_stream` method from a second gate. Avoiding the ordinary factory
result entirely would bypass the current factory authority, so PR4 does
not make that semantically unsafe optimization.

History load and validation timing remain after successful preparation and
inside the business UOW.

## 5. Exact PR3 Field Population

| PR3 field | PR4 owner and boundary |
|---|---|
| `producer_write_invocation` | Explicit measured method immediately before the shared producer algorithm through its normal return; stops before final artifact construction. |
| `business_uow` | Measured UOW subclass entry call through normal exit return. |
| `validation_runtime_call` | Optional recorder directly around current `ValidationRuntime.decide(...)`. |
| `preliminary_idempotency_check` | PRE recorder around the current read-store `check(...)`. |
| `preliminary_read_cleanup` | PRE recorder around current `connection.rollback()` in `finally`. |
| `authoritative_idempotency_check` | Recorder around current business-UOW idempotency `check(...)`. |
| `accepted_history_load` | Recorder around current event-store `load(...)`, in its existing PRE or IN placement. |
| `concurrency_preparation_call` | Recorder around current `prepare_stream(...)`. |
| `pessimistic_advisory_try_lock_call` | Measured concrete pessimistic-gate wrapper around current nonblocking `_try_lock_stream(...)`; not lock wait. |
| `append_admission_call` | Recorder around current `append_if_admitted(...)`; not pure OCC or INSERT cost. |
| `idempotency_record_call` | Recorder around current transaction-local `record(...)`. |
| `commit_finalization` | Measured UOW override around current `commit()`. |
| `rollback_finalization` | Measured UOW override around current `rollback()`. |

`ValidationResult.total_time_ms` is neither changed nor derived. It remains
validator-local float-millisecond evidence inside the separately measured
validation-runtime interval.

## 6. Presence and Absence

The recorder maps states as follows:

```text
phase excluded from the accepted concrete composition
→ NOT_APPLICABLE

applicable phase never entered before normal return
→ NOT_REACHED

phase entered but safe clock collection did not complete
→ NOT_COLLECTED

completed valid integer delta, including zero
→ MEASURED
```

For the accepted Stage 4B.2 pair, validation placement supplies initial
try-lock applicability before a gate exists:

```text
PRE_TRANSACTION
→ not applicable

IN_TRANSACTION
→ applicable but not reached until concrete pessimistic preparation
```

When preparation is reached, the actual current concrete gate confirms or
removes applicability. This preserves early IN idempotency returns without
introducing a strategy enum or constructing a gate early. This inference is
defined only for the canonical measured pair; no correct try-lock applicability
claim is made for unsupported cross-combinations.

## 7. ADR 0023 Failure Ordering

The implemented PR4 order is:

```text
create invocation-local recorder
→ start producer-write interval
→ call shared existing producer algorithm
→ existing commit or rollback finalization completes
→ exact Result or Execution returns
→ stop producer-write interval
→ construct immutable measurement
→ construct available delivery
```

The producer call is outside the final construction handler.

The `except Exception` is intentionally broad by ADR 0023 ownership and narrow
by code location. Its `try` block contains only:

- translation of already-retained recorder readings into frozen PR3 phase
  values;
- construction of `PostgresWriteSideMeasurement`; and
- construction of the AVAILABLE `PostgresWriteSideMeasurementDelivery`.

It contains no producer execution, trace construction, clock read, external
callback, PostgreSQL I/O, UOW entry/exit, commit, rollback, persistence,
telemetry, or correctness-required logging. If that narrowly owned pure
construction fails:

```text
exact producer object is retained
+ availability = UNAVAILABLE
+ measurement = None
```

The unavailable fallback remains the normal frozen PR3 delivery constructor. It
receives the already-valid producer object plus the fixed `UNAVAILABLE` enum and
`None`; it uses no recursive fallback, invariant bypass, or ad-hoc result type.
Producer, validation, idempotency, admission, trace, UOW, commit, and rollback
exceptions bypass final construction and keep their current types and
propagation.

Phase `NOT_COLLECTED` is distinct: it reports one reached phase whose safe clock
reading did not complete while an immutable snapshot may still be available.
Delivery `UNAVAILABLE` means the final PR3 artifact could not be constructed.

For the required `producer_write_invocation` phase, either start-clock or stop-
clock failure leaves that reached phase `NOT_COLLECTED`. After normal accepted
or typed non-accepted return, the exact producer object remains final, but the
required whole-phase invariant makes the complete Level-A snapshot unavailable:

```text
same exact producer object
+ availability = UNAVAILABLE
+ measurement = None
```

This post-return fallback neither rolls back accepted work nor hides a typed
non-accepted result.

## 8. Unmeasured Observer-Effect Boundary

Existing APIs instantiate no recorder and do not call
`time.perf_counter_ns()`. Their existing direct operations remain in the same
order and return the same value shapes.

The shared algorithms contain only recorder-absence branches. They do not
allocate phase objects, call clocks, construct measurement snapshots, or create
an always-present no-op collector for unmeasured execution.

Accordingly, existing unmeasured execution is free of detailed measurement
collection machinery, but it is not claimed to be byte-for-byte or literally
zero-instruction-overhead relative to pre-PR4 source. The residual cost is the
small branch/seam tax in the shared implementation. Its size is unknown.

PR6 can later compare three separately identified surfaces without PR4 making
an overhead claim:

```text
A = frozen PR3 baseline with no PR4 instrumentation seams
B = PR4 shared-code unmeasured execution with inactive recorder branches
C = PR4 measured execution with recorder, clock reads, and artifact construction

B - A = shared instrumentation seam / branch tax
C - B = active detailed measurement collection cost
C - A = total observer effect of the measured capability
```

The PRE and IN unmeasured and measured surfaces remain separately callable.
PR4 does not benchmark or characterize any of these differences.

## 9. Frozen PR3 Experiment Reference

PR4 preserves the committed pre-PR4 write-side source byte-for-byte at:

```text
tests/fixtures/stage4b2_measurement/
  postgres_write_side_pr3_baseline.py.source
```

The non-`.py` suffix deliberately prevents it from becoming an importable
alternate implementation. `README.md` marks it experiment-only and
intentionally unmaintained; `provenance.json` records the source path, SHA-256,
Git blob, and PR4 base HEAD.

The snapshot was frozen from merged PR3 commit
`fd3733d57ff82beeaf9d54446924f8830c49db76` immediately before PR4
instrumentation. Later fixes do not update it. PR6 must label any comparison as
a historical PR3 observer-effect baseline, not a business-correctness oracle.

## 10. PR5 Handoff

PR5 should independently validate:

- every PRE and IN normal-return topology against real instrumented source;
- exact nanosecond deltas with a deterministic clock;
- `NOT_APPLICABLE`, `NOT_REACHED`, `NOT_COLLECTED`, and measured zero;
- individual interval containment using start/stop test evidence;
- measurement versus existing result, mutation, trace, UOW, and exception
  parity;
- clock-read failure containment;
- final snapshot/available-envelope failure fallback;
- real PostgreSQL commit/rollback and concrete advisory try-lock compatibility;
- legacy and traced identity preservation; and
- absence of measurement work from existing APIs.

The source-population presence-state handoff is:

```text
PRE + optimistic/OCC pessimistic advisory try-lock
→ NOT_APPLICABLE

IN + concrete pessimistic normal early return
→ later applicable phases not entered on that path are NOT_REACHED

accepted path rollback finalization
→ NOT_REACHED

normal rollback path commit finalization
→ NOT_REACHED
```

`NOT_COLLECTED` remains reserved for a reached phase without a retained
completed elapsed value, while `MEASURED` includes a completed zero delta. PR5
owns exact source-population evidence; these rules do not change the frozen PR3
contract or its constructible fixture examples.

PR5 should also preserve source-boundary evidence that clock handling remains
narrow, the measured pessimistic adapter reuses the concrete gate algorithm,
and unsupported cross-combinations are outside Stage 4B.2 interpretation.

PR5 must not assert latency thresholds or compare strategy performance.

## 11. PR4 Validation Record

Validation uses the repository-local Python environment from the repository
root.

```text
focused PR4 instrumentation tests
= 39 passed

PR3 measurement contract tests
= 38 passed

complete tests/unit tree
= 1147 passed
```

`TEST_DATABASE_URL` was not configured, so PostgreSQL integration was not run.
No performance, load, concurrency, or benchmark test was run.
