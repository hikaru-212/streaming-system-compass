# Stage 4B.2 — PostgreSQL Write Measurement Correctness Validation

[← Back to Stage 4B.2](README.md)

## Status

```text
PR4 production instrumentation
= COMPLETE / MERGED

PR5 deterministic unit correctness evidence
= COMPLETE

PR5 real PostgreSQL correctness evidence
= COMPLETE

PR5
= COMPLETE / MERGED / ACCEPTED CORRECTNESS FOUNDATION

Stage 4B.2
= COMPLETE / CLOSED
```

This note records Stage 4B.2 PR5 measurement-correctness evidence. It validates
whether PR4's opt-in instrumentation represents the existing PostgreSQL
write-side source boundaries without changing producer results, transactions,
traces, exceptions, persistence semantics, or unmeasured API behavior.

It does not interpret performance or select an execution strategy.

## 1. Accepted Boundary

PR5 retains the accepted PR3 contract, ADR 0023, ADR 0024, one shared PRE
algorithm, one shared IN algorithm, and the four explicit measured APIs.

The only interpretation-safe measured compositions remain:

```text
PRE_TRANSACTION
+ current optimistic/OCC append-time admission

IN_TRANSACTION
+ current concrete PostgreSQL pessimistic admission
```

No production module, contract, ADR, migration, schema, dependency, trace,
receipt, persistence, retry, strategy, sampling, telemetry, or rate-limiting
surface changes in PR5.

## 2. Canonical Normal-Return Matrix

| Case | Composition and path | Producer outcome | Business finalization | Trace terminal when traced |
|---|---|---|---|---|
| P1 | PRE + OCC accepted | `ACCEPTED` | commit | `IDEMPOTENCY_PERSISTENCE_RETURNED` |
| P2 | PRE preliminary replay | `REPLAY` | no business UOW; preliminary read cleanup only | `PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED` |
| P3 | PRE validation blocked | `VALIDATION_BLOCKED` | no business UOW; preliminary read cleanup only | `VALIDATION_RETURNED` |
| P4 | PRE + OCC append-time stale rejection | `ADMISSION_REJECTED`; append `STALE_WRITE` | rollback | `APPEND_ADMISSION_RETURNED` |
| I1 | IN + concrete pessimistic accepted | `ACCEPTED` | commit | `IDEMPOTENCY_PERSISTENCE_RETURNED` |
| I2 | IN authoritative replay | `REPLAY` | rollback | `AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED` |
| I3 | IN advisory try-lock non-acquisition | `ADMISSION_REJECTED`; preparation `LOCK_TIMEOUT` | rollback | `CONCURRENCY_PREPARATION_RETURNED` |
| I4 | IN validation blocked after successful preparation | `VALIDATION_BLOCKED` | rollback | `VALIDATION_RETURNED` |

P4 uses the current optimistic gate's admitted no-op preparation followed by
append-time `STALE_WRITE`. It does not substitute a custom preparation-rejecting
gate. I3 times the normally returning nonblocking advisory try-lock call even
though its returned value is false.

## 3. Exact Thirteen-Phase Population

Legend:

```text
M  = MEASURED
NA = NOT_APPLICABLE
NR = NOT_REACHED
```

| Phase | P1 | P2 | P3 | P4 | I1 | I2 | I3 | I4 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `producer_write_invocation` | M | M | M | M | M | M | M | M |
| `business_uow` | M | NR | NR | M | M | M | M | M |
| `validation_runtime_call` | M | NR | M | M | M | NR | NR | M |
| `preliminary_idempotency_check` | M | M | M | M | NA | NA | NA | NA |
| `preliminary_read_cleanup` | M | M | M | M | NA | NA | NA | NA |
| `authoritative_idempotency_check` | M | NR | NR | M | M | M | M | M |
| `accepted_history_load` | M | NR | M | M | M | NR | NR | M |
| `concurrency_preparation_call` | M | NR | NR | M | M | NR | M | M |
| `pessimistic_advisory_try_lock_call` | NA | NA | NA | NA | M | NR | M | M |
| `append_admission_call` | M | NR | NR | M | M | NR | NR | NR |
| `idempotency_record_call` | M | NR | NR | NR | M | NR | NR | NR |
| `commit_finalization` | M | NR | NR | NR | M | NR | NR | NR |
| `rollback_finalization` | NR | NR | NR | M | NR | M | M | M |

The new deterministic matrix invokes the actual PR4 measured production
surfaces. All eight rows produced this exact state population. No PR3 contract
change was required.

## 4. Deterministic Boundary Method

PR5 reuses the PR2 manual nanosecond clock and source probe while calling PR4's
actual recorder and measured APIs.

For each reached phase:

```text
actual elapsed
= PR4 measurement field elapsed_ns

expected elapsed
= independent source-boundary stop_ns - start_ns
```

The parent rule is explicitly not:

```text
parent elapsed
!= sum of child elapsed values
```

The independent probe observes the source operation inside the PR4 timer. With
the deterministic clock, its endpoints prove the timer begins before and stops
after the bounded operation. P1, I1, and P4 additionally preserve strict event
ordering for producer entry, UOW entry, child entry/return, UOW exit, and
producer return.

The characterized detail deltas remain:

| Detail boundary | Deterministic elapsed |
|---|---:|
| preliminary idempotency check | 11 ns |
| preliminary read cleanup | 13 ns |
| authoritative idempotency check | 17 ns |
| accepted history load | 19 ns |
| validation-runtime call | 15 ns |
| optimistic preparation | 0 ns |
| concrete pessimistic preparation / try-lock in the current test seam | 5 ns / 5 ns |
| append admission | 29 ns |
| idempotency record | 31 ns |
| commit finalization | 37 ns |
| rollback finalization | 41 ns |

Measured zero remains valid evidence. Parent intervals use their independently
captured endpoints rather than any arithmetic derivation from this table.

## 5. End-to-End Collection Failure

PR5 injects one safe stop-clock exception at the reached I4
`validation_runtime_call` boundary through an actual measured producer API.

The result is:

```text
producer result
= VALIDATION_BLOCKED

business rollback
= unchanged

delivery
= AVAILABLE

validation_runtime_call
= NOT_COLLECTED

all other phases
= normal I4 state
```

This is distinct from whole-invocation collection failure, which PR4 already
proves produces `UNAVAILABLE` because the frozen contract requires the whole
phase to be measured.

## 6. Measured / Unmeasured Parity

The deterministic parity allocation is:

| Existing and measured pair | Cases |
|---|---|
| `create_order` / `create_order_with_measurement` | P1–P4 |
| `create_order_with_trace` / `create_order_with_trace_and_measurement` | I1–I4 |
| `pay_order` / `pay_order_with_measurement` | accepted PAY and preliminary replay |
| `pay_order_with_trace` / `pay_order_with_trace_and_measurement` | accepted PAY and preliminary replay |

Comparisons include normalized accepted-event business shape, idempotency,
stream and append admission, validation, commit/rollback calls, producer
outcome, and exact trace placement/checkpoints/terminal. Trace construction
retains only `validation_placement` and `checkpoints`; timing does not move into
the trace.

Fresh accepted executions are not required to share generated `event_id` or
`occurred_at_ms`. Proof comparison retains previous-status/version and previous-
event presence without treating independent fresh identity as parity evidence.

All allocated deterministic parity cases passed.

PR5 does not duplicate PR4's producer, commit, or rollback exception cases or
its unmeasured no-recorder/no-clock cases. The complete accepted PR4
instrumentation regression, including those boundaries, remains green at 39
tests.

## 7. Real PostgreSQL Compatibility Method

The PR5 integration module contains six collected cases across three bounded
test responsibilities.

### Accepted persistence parity

Four parameter rows cover:

- PRE legacy CREATE;
- IN traced CREATE;
- PRE legacy PAY; and
- IN traced PAY.

Each row compares measured and unmeasured business semantics on independent
streams, verifies exact accepted phase-state shape, requires every measured
value to be a non-negative Python integer, verifies each returned accepted event
against its own durable history and idempotency replay, and checks connection
`TransactionStatus.IDLE` plus `SELECT 1` reuse after producer return.

### IN pessimistic validation rollback

The test requires real advisory preparation, real history load, validation
`BLOCK`, measured rollback finalization, no commit finalization, no candidate or
idempotency persistence, and an idle/reusable connection.

### IN pessimistic try-lock non-acquisition

One connection retains the transaction-scoped advisory lock. A second
connection performs measured IN execution. No thread, sleep, retry loop,
waiting assertion, or latency threshold is used. The expected result is typed
`LOCK_TIMEOUT` / `ADMISSION_REJECTED`, measured try-lock and rollback phases,
unreached history/validation/append, no current persistence, and explicit locker
rollback/close in `finally`.

## 8. Executed Validation

All Python commands used the repository-local `.venv` interpreter.

The final repository-wide validation executed from the active project shell:

```text
pytest tests -q
= 1784 passed in 32.17s
```

No failures or skips were reported. The PR5 PostgreSQL correctness module is part
of the repository test tree, so the six PR5 integration cases executed
successfully in that run under the active guarded test environment.

Previously recorded focused validation also remained green:

```text
focused PR5 unit correctness
= 16 passed

accepted PR4 instrumentation regression
= 39 passed

accepted PR3 contract regression
= 38 passed

complete unit suite
= 1163 passed

PR5 PostgreSQL integration cases
= 6 passed as part of the final repository-wide test run

Git whitespace validation
= git diff --check passed
```

A later isolated tooling process attempted to rerun only the focused PR5
integration file but did not inherit `TEST_DATABASE_URL`, so fixture setup could
not begin in that separate process. That environment-specific rerun failure does
not supersede the successful repository-wide execution recorded above.

No environment file or credential was inspected by the documentation-alignment
step, and no database configuration was changed.

## 9. Correctness Finding

Deterministic executable evidence found no production instrumentation defect:

```text
PR3 reopening required
= no

ADR 0023 / ADR 0024 change required
= no

PR4 algorithm or architecture redesign required
= no

second business algorithm required
= no
```

The current source supports all thirteen claimed boundaries and the exact eight-
case population matrix. Real PostgreSQL accepted persistence, rollback,
advisory try-lock non-acquisition, and connection IDLE/reuse compatibility are
also covered by the successful repository-wide test execution.

No production instrumentation defect was discovered.

## 10. Limitations and PR6 Handoff

PR5 does not establish:

- latency thresholds or rankings;
- throughput, saturation, contention scaling, or capacity;
- observer-effect magnitude;
- retry, strategy-selection, sampling, telemetry, or rate policy; or
- performance equivalence between PRE/OCC and IN/pessimistic execution.

PR5 correctness evidence is complete on this branch and is ready for final human
review and merge into the Stage 4B.2 integration branch.

PR6 may begin after PR5 is merged. It may then use the accepted measurement
surface for controlled PRE/OCC versus IN/pessimistic comparison, but it must not
reinterpret PR5's correctness evidence as a performance result.
