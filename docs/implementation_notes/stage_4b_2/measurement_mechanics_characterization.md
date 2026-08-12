# Stage 4B.2 — Measurement Mechanics Characterization

[← Back to Stage 4B.2](README.md)

## Status

```text
PR1 responsibility boundary
= complete

PR2 deterministic characterization
= COMPLETE / MERGED / ACCEPTED

production measurement contract
= COMPLETE / MERGED

production instrumentation
= COMPLETE / MERGED

Stage 4B.2
= COMPLETE / CLOSED
```

This note records Stage 4B.2 PR2 findings from deterministic, test-owned
characterization of the current PostgreSQL write-side source. It does not
freeze the later PR3 immutable contract or authorize PR4 instrumentation.

The executable evidence is:

- [`test_postgres_write_side_measurement_characterization.py`](../../../tests/unit/pipeline/transactional/test_postgres_write_side_measurement_characterization.py).

The test wraps current collaborator and unit-of-work boundaries through
`monkeypatch`. It does not reproduce the PRE_TRANSACTION or IN_TRANSACTION
write algorithms, change production source, use PostgreSQL, assert real
latency, or run performance or concurrency experiments.

## 1. Responsibility Preserved

PR2 preserves:

```text
PostgresWriteSideExecutionTrace
= bounded execution topology

measurement evidence
= elapsed evidence for explicitly bounded work actually performed

PostgresWriteSideExecutionTrace
!= measurement evidence
```

No timing field is added to `PostgresWriteSideExecutionTrace`. The current
primary Result, traced Execution, `SemanticOutcome`, `DecisionReceipt`, and
accepted-event metadata remain unchanged.

## 2. Deterministic Clock Mechanics

A minimal clock seam is sufficient:

```text
clock call
→ integer monotonic reading

elapsed
= stopped_ns - started_ns
```

The characterization uses a manual callable shaped like
`time.perf_counter_ns()`. Explicit manual advancement proves deterministic
non-zero elapsed values, and no advancement proves a valid measured zero. No
wall-clock threshold is needed.

This supports, but does not yet freeze, the PR1 planning direction:

```text
collection source
= time.perf_counter_ns()

internal collection unit
= integer nanoseconds
```

PR3 still owns the public unit, exact immutable representation, conversion,
and presentation rounding decisions.

## 3. Characterized Timer Boundaries

The executable test uses the following call boundaries:

| Candidate | Characterized start | Characterized stop |
|---|---|---|
| Whole write invocation | Immediately before entering the existing legacy or traced write API. | Immediately after that API returns normally, which is after business-UOW finalization when reached and before final measurement construction. |
| Business-UOW lifecycle | `PostgresWriteSideUnitOfWork.__enter__()` call entry. | After `PostgresWriteSideUnitOfWork.__exit__()` returns normally. A failed `__enter__()` does not produce a completed interval. |
| Validation-runtime call | Immediately before `ValidationRuntime.decide(...)`. | Immediately after its `ValidationDecision` returns. |
| Preliminary idempotency check | Immediately before the PRE read-store `check(...)`. | Immediately after its typed decision returns. |
| Preliminary read cleanup | Immediately before the PRE `connection.rollback()` in the `finally` block. | Immediately after that rollback returns. |
| Authoritative idempotency check | Immediately before the business-UOW `check(...)`. | Immediately after its typed decision returns. |
| Accepted-history load | Immediately before `PostgresEventStore.load(...)`. | Immediately after the history list returns, before aggregate rehydration continues. |
| Concurrency preparation | Immediately before `prepare_stream(...)`. | Immediately after its typed `StreamAdmissionResult` returns. |
| Pessimistic advisory try-lock | Immediately before concrete `_try_lock_stream(...)`. | Immediately after acquired/not-acquired returns. This is contained by preparation and is not named lock wait. |
| Append admission | Immediately before `append_if_admitted(...)`. | Immediately after its typed `AdmissionResult` returns. |
| Idempotency record | Immediately before `PostgresIdempotencyStore.record(...)`. | Immediately after it returns inside the current transaction. |
| Commit finalization | Immediately before `PostgresWriteSideUnitOfWork.commit()`. | Only after `commit()` returns normally. |
| Rollback finalization | Immediately before `PostgresWriteSideUnitOfWork.rollback()`. | Only after `rollback()` returns normally. |

An operation that raises after timer start does not produce a completed
normal-return interval in the test-owned snapshot. The original exception
continues to propagate.

### Whole-invocation self-measurement limit

Final measurement construction must follow the whole-invocation stop because
the constructor needs that final delta as input. Deterministic construction
work advanced after the stop does not change the retained whole-invocation
interval.

Therefore the self-contained producer measurement is:

```text
existing write API entry
→ existing write API normal return after UOW finalization
→ whole-invocation stop
→ final measurement construction
```

It excludes its own post-stop artifact-construction and delivery overhead. An
external observer could measure a wider API call, but that would be a different
boundary and must not be silently assigned to this field.

## 4. Containment and Overlap

Accepted PRE and IN executable paths prove:

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
+ commit finalization

business UOW
contains additionally for IN
accepted-history load
+ validation-runtime call

concurrency preparation
contains for concrete IN pessimistic admission
pessimistic advisory try-lock call

validation-runtime call
contains
validator-local elapsed
```

For PRE, accepted-history load and validation-runtime call complete before the
business UOW begins. Aggregate rehydration, validation-context construction,
and candidate construction remain the lower-priority PR1 detail: they are
outside the UOW for PRE and inside it for IN, but PR2 does not promote them to
first-contract production timers.

The deterministic sum of nested phase intervals exceeds the whole-invocation
interval. That is expected overlap, not an inconsistency. PR3 must not define
the whole as the sum of all phase fields.

## 5. Presence and Absence

Executable characterization keeps four states distinct:

```text
phase not applicable
!= phase applicable but not reached
!= phase reached but measurement not collected
!= measured duration equal to zero
```

The test-owned enum used to prove the distinction is not a proposed PR3
representation. PR3 must choose an immutable representation that preserves the
same semantics. Numeric zero cannot be the missing-value sentinel.

## 6. Current Normal-Return Measurement Topology

The following abbreviations apply only to this table:

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

### PRE_TRANSACTION

| Current normal-return path | Reached candidate measurement phases |
|---|---|
| Preliminary replay | `W, PI, PC` |
| Preliminary conflict | `W, PI, PC` |
| Validation block | `W, PI, H, PC, V` |
| Authoritative replay | `W, PI, H, PC, V, U, AI, RB` |
| Authoritative conflict | `W, PI, H, PC, V, U, AI, RB` |
| Injected preparation rejection | `W, PI, H, PC, V, U, AI, C, RB` |
| Append `STALE_WRITE` | `W, PI, H, PC, V, U, AI, C, A, RB` |
| Accepted write | `W, PI, H, PC, V, U, AI, C, A, IR, CM` |

The default optimistic gate's current preparation is an admitted no-op. The
PRE preparation-rejection row is reachable through the existing injected gate
contract, not through the default optimistic implementation.

The PRE `finally` cleanup is reached even for preliminary replay and conflict.
Those paths do not reach the business UOW.

### IN_TRANSACTION + Concrete Pessimistic Admission

| Current normal-return path | Reached candidate measurement phases |
|---|---|
| Authoritative replay | `W, U, AI, RB` |
| Authoritative conflict | `W, U, AI, RB` |
| Advisory non-acquisition / preparation rejection | `W, U, AI, C, L, RB` |
| Validation block | `W, U, AI, C, L, H, V, RB` |
| Append rejection | `W, U, AI, C, L, H, V, A, RB` |
| Accepted write | `W, U, AI, C, L, H, V, A, IR, CM` |

Preparation rejection does not reach protected history or validation.

## 7. Commit and Rollback Mechanics

The executable ordering is:

```text
clean accepted path
→ commit returns
→ commit timer stops
→ UOW lifecycle stops
→ whole invocation stops

normal non-accepted UOW path
→ explicit rollback returns
→ rollback timer stops
→ already-finished UOW context exits
→ UOW lifecycle stops
→ whole invocation stops

exceptional unfinished UOW path
→ current __exit__ invokes rollback
→ rollback returns
→ UOW lifecycle can finish
→ original exception continues propagating
→ no normal-return whole-invocation measurement is delivered
```

A commit or rollback timer completes only when the corresponding method
returns normally. Commit and rollback exceptions remain exceptions; they are
not translated into typed measurement results.

## 8. Existing Validator Timing

An executable test uses the real `NoOpValidator`, `ValidationDispatcher`,
`ValidationPolicy`, and `ValidationRuntime` with a deterministic ticking clock.
It proves:

```text
ValidationResult.total_time_ms
= validator-local elapsed

validation-runtime call elapsed
= dispatcher + validator + policy + ValidationDecision construction boundary

validation-runtime call elapsed
contains
ValidationResult.total_time_ms
```

The two values are distinct. Existing Stage 4B.1 synthetic `0.0` values remain
topology evidence and are not performance claims.

## 9. Post-UOW Delivery Finding

ADR 0022 remains specific to the current traced APIs. Its pre-commit rule is:

```text
valid Result + Trace + Execution
must exist before clean UOW exit
```

PR2 deterministically proves that applying the same ordering to a fallible
final measurement constructor has different semantics:

```text
measurement construction failure inside unfinished UOW
→ exceptional UOW exit
→ rollback
```

That would make measurement construction part of business success and would
violate measured/existing API parity. ADR 0022 must not be generalized to
measurement evidence.

The minimum synchronous safety constraint established by PR2 is:

```text
existing producer call returns after UOW finalization
→ primary Result or traced Execution is already final
→ whole-invocation timer stops
→ attempt final measurement construction

measurement construction succeeds
→ deliver exact producer value + available measurement

measurement construction fails in the explicitly measurement-owned boundary
→ deliver exact producer value unchanged
+ represent measurement as unavailable
→ do not raise the measurement failure over committed business truth
```

The prototype retains the producer-returned object by identity. The reviewed
characterization covers both accepted and normal typed non-accepted results,
and both legacy and traced producer surfaces: an explicitly measurement-owned
construction failure occurs only after commit or rollback finalization and
leaves the exact producer value unchanged while measurement becomes
unavailable.

It catches no producer, commit, rollback, validation, admission, idempotency, or
trace exception. Those exceptions bypass measurement construction and retain
their current type and propagation behavior.

All measurement validation that may reject the final readings must remain
inside that explicitly handled construction boundary. The later result-first
delivery composition must not add a second fallible semantic validator after
commit. Likewise, PR4 collection must not introduce ordinary clock or recorder
exceptions into the business UOW merely to obtain evidence; no generic catch of
existing producer exceptions is authorized.

This establishes the required safety semantics, not the final API. PR3 must
still select and review the exact producer-specific immutable delivery shape,
the measurement-unavailability representation, and the narrowly owned set of
construction failures that become unavailability. If more than one safe
representation remains, PR3 must not guess between them.

## 10. Measured / Existing API Parity Constraint

The test-owned post-UOW wrapper preserves both current surfaces by identity:

```text
legacy PostgresWriteSideResult
→ unchanged producer object

traced PostgresWriteSideExecution
→ unchanged producer object
+ unchanged PostgresWriteSideExecutionTrace
```

The future measurement-enabled execution must preserve:

- primary result values and nested evidence;
- accepted-event identity;
- accepted-history and idempotency mutation;
- validation, admission, and idempotency semantics;
- commit and rollback behavior;
- exception types and propagation;
- existing traced API construction ordering and behavior; and
- existing legacy API behavior.

PR2 does not implement that future API.

## 11. PR3 Handoff and Remaining Decisions

No production source change is required to complete PR2 characterization. No
production-neutral seam was requested.

The current source can support later instrumentation at the characterized call
sites, but PR3 must first freeze only the contract decisions justified by this
evidence:

- exact producer-specific immutable type and field names;
- internal/public units and precision;
- representation of not applicable, not reached, not collected, measured zero,
  and measurement unavailable;
- normal-return completeness invariants;
- exact result/measurement delivery envelope;
- the narrow measurement-construction failure boundary; and
- documentation of containment and overlap.

The mechanics no longer require an architectural change to the current Result,
Trace, UOW, or exception contracts. The delivery representation remains a PR3
human-review decision and is intentionally not frozen here.

## 12. Non-Goals Preserved

PR2 did not begin:

- production measurement contract or instrumentation;
- performance, load, strategy-comparison, or concurrency experiments;
- PostgreSQL experiment artifacts;
- `DiagnosticTrace` or `DecisionReceipt` changes;
- accepted-event metadata timing or other persistence;
- schema, migration, dependency, or telemetry work;
- strategy selection, retry, `AttemptLog`, or policy; or
- rate limiting.

## 13. Validation Record

Repository-local Python was used for every test command.

The pre-review implementation run recorded:

```text
focused PR2 characterization
= 32 passed

PR2 + relevant write-side / UOW / trace / validator pure-unit tests
= 139 passed

complete tests/unit tree
= 1067 passed
```

Human review then broadened the post-UOW measurement-construction-failure
characterization from one accepted legacy case to a matrix covering accepted
and normal typed non-accepted results across both legacy and traced producer
surfaces. That reviewed test file must be rerun after it is copied into the
repository; the earlier counts above must not be presented as validation of the
expanded matrix.

The selected deterministic PostgreSQL write-side, UOW, and traced-execution
integration command was attempted, but `TEST_DATABASE_URL` was not configured.
All 48 selected cases stopped during fixture setup before executing a test
body. No environment file or credential was inspected, no database was
started, and no PostgreSQL, performance, load, or concurrency experiment was
run.
