# PR9 — Production Retry Validation Method

[← Back to Load / Capacity Protection](README.md)

```text
PR9 — ACTIVE
Method / source audit / observation seams — implemented for human review
Executable measurement machinery — deterministic validation; no live evidence
Live PostgreSQL comparison — NOT RUN / NOT AUTHORIZED in this task
Final live numerical configuration — NOT SELECTED
```

## 1. Purpose and Authority

[PR5](pr5_retry_refusal_amplification_report.md) characterized experiment-owned
retry policies. [PR7](pr7_retry_attempt_policy_selection.md) selected only the
opt-in bounded-retry plus delayed-backoff class.
[PR8](pr8_bounded_retry_backoff.md) implemented that class and tested mechanism
correctness. None establishes the performance or retained-resource behavior of
the actual production-capable composition under live PostgreSQL.

PR9 asks whether that composition exhibits useful retry-pressure behavior while
preserving writer occupancy and authority boundaries, and what idle resources
remain retained during synchronous backoff. Historical PR5 results supply
motivation, not the disabled control group or production numerical defaults.
[ADR 0031](../../adr/0031_separate_resource_occupancy_retry_and_arrival_protection.md)
continues to separate occupancy, retry pressure and arrival-rate protection.

This document describes implemented measurement machinery for human review,
not live-run approval, an architectural decision or evidence of performance.
The initial source audit stopped at the observation gap in Section 3. The user
subsequently approved exactly the three production files in Section 4 and the
experiment machinery. No additional production owner or behavior was introduced.

## 2. Exact Production Path

The audit used committed source
`7d3bac8b211aebab8544b7c18d1c78aaa31c110d` on
`experiment/load-capacity-pr9-production-retry-validation`.
This identifies the audit base, not a future evidence-generating revision.

```text
build_postgres_writer_request(...)
→ PostgresWriterRequest.invoke()
→ PostgresWriterRequest._execute()
→ retained PostgresTransactionalWriteSide.create_order_with_measurement(...)
  / pay_order_with_measurement(...)
→ public _capacity_protected wrapper
→ enabled: private _AttemptAdmission view
→ shared concrete BoundedWriterAdmission.run(body)
→ original protected writer body
```

Disabled composition calls the same public writer through the same concrete
shared gate, without the private retry-provenance view. That difference belongs
to the production mechanism under test. The experiment must not add another
attempt loop, replace the production owner with the PR5 scheduler, or weaken the
concrete gate requirement. A1/A2 and Stage 4E are outside this graph.

The inspected production sources are the
[policy](../../../src/pipeline/writer_retry_policy.py),
[request owner](../../../src/pipeline/postgres_writer_request.py),
[builder](../../../src/bootstrap/build_postgres_writer_request.py),
[capacity primitive](../../../src/pipeline/transactional/writer_capacity.py)
and [writer](../../../src/pipeline/transactional/postgres_write_side.py).

## 3. Initial Supported-Interface Observation Gap

This table records the PR8 source before the approved optional seams below.

| Required evidence | Current source finding | Consequence |
|---|---|---|
| Logical/attempt identity, capacity refusal, eligibility, budget and terminal disposition | `PostgresWriterRequest.observations` exposes immutable snapshots. | Available for mapping, with the qualifications below. |
| Scheduled/actual retry timing and wait-time connection status | The owner accepts `clock` and `wait`; a caller-owned waiter can bracket its own execution and sample its retained connection without SQL. | A supported resource-observation seam exists. |
| Complete admitted-body entry/exit and overlap | `BoundedWriterAdmission.run` documents subclass-based operation wrapping. PR8 construction requires `type(capacity_admission) is BoundedWriterAdmission` and rejects subclasses. The private view retains only refusal identity. | The earlier experiment observer cannot be supplied to enabled PR8 composition. No supported concrete-gate body observer is exposed. |
| UOW / append / commit measurements | PR8 `_execute` always chooses unmeasured `create_order` / `pay_order`. The writer's measured variants call `_execute_command_with_measurement`; the unmeasured variants do not. | Existing Level-A measurements are not delivered through the owner under test. |
| Composition of the required observations | The builder forwards policy, gate, clock, waiter and lifetime controls; it exposes neither body observation nor measured-delivery selection. | Full requested PR9 evidence is unavailable through current supported composition interfaces. |

This is not an architectural contradiction: the capacity primitive permits a
general experiment adapter, while PR8 intentionally narrows eligible composition
to protect refusal provenance. PR9 must preserve that narrowing.

Additional evidence qualifications matter even before instrumentation:

- Disabled `ATTEMPT_DISPATCHED.observed_at` is None; its capacity refusal's
  `pre_body_refusal` is also None. These cannot be converted into measured
  timestamps or verified body absence merely because enabled mode records them.
- Terminal observations do not timestamp public-writer return. Outer logical
  invocation timestamps are available to an experiment, but do not by themselves
  delimit the protected body or individual SQL-backed phases.
- Retry schedule/ready intervals are not body intervals. Public-call overlap
  includes refused attempts and cannot stand in for admitted-body overlap.
- Source reasoning establishes why a verified refusal cannot hold a permit;
  it does not provide the live body-entry/exit series required for PR9's overlap
  measurement.

The [earlier lane adapter](../../../experiments/load_capacity_protection/postgres_runtime.py)
directly calls `create_order_with_measurement`, and the
[PR5 runtime](../../../experiments/load_capacity_protection/pr5_postgres_runtime.py)
supplies an observed admission subclass. Reusing those paths would omit PR8 or
fail its constructor. They are reference material, not the PR9 execution path.

No private-object replacement, runtime monkeypatching, gate-guard relaxation or
substitute retry implementation was introduced. External Python profiling is
another possible measurement method, but is not the existing Level-A contract;
it would require a separately reviewed boundary mapping and overhead treatment.
This audit does not assert that all possible external instrumentation is impossible.

## 4. Approved Narrow Observation Scope — Implemented

The user approved the following optional observation capabilities. The
unobserved default and retry policy remain unchanged:

| Approved production file | Implemented capability |
|---|---|
| `src/pipeline/transactional/writer_capacity.py` | Observe admitted-body entry/exit and the end of an admission call through the concrete gate, without replacing acquisition, operation invocation, release or the refusal issuer. |
| `src/pipeline/postgres_writer_request.py` | Opt into the existing measured writer variants; retain/deliver their measurement separately while returning the identical primary writer result and retaining the same capacity-only retry logic. Correlate observations with the logical invocation and attempt number. |
| `src/bootstrap/build_postgres_writer_request.py` | Wire those optional observation capabilities into both A/B conditions through the real builder. No writer replacement or alternate retry owner. |

### Exact APIs and Ownership

`WriterCapacityObserver(clock_ns=monotonic_ns)` retains immutable snapshots in
`observations` and separate `failures`. A failed, invalid or regressing clock
reading produces a `WriterCapacityObservationFailure` with identity, intended
boundary kind, thread ID and exception class; it produces no successful event or
replacement timestamp. No error message or provider payload is retained.
The recorder contains no business callback. The clock must be nonblocking,
observation-only and must not reenter the recorder or perform business work.

`BoundedWriterAdmission.observe_attempt(identity, observer)` binds one exact
`WriterAttemptIdentity(logical_invocation_id, request_id, attempt_number)` in a
`ContextVar`, scoped to this concrete gate and the synchronous call. `run()`
emits `CALL_STARTED`; either `REFUSED`, or `BODY_ENTERED`, `BODY_EXITED`,
`RELEASED`; then `CALL_COMPLETED`. Body exit is before release; release and call
completion are observed after the permit is returned. A refusal has no body or
release event. The clock/recording boundary never encloses the writer operation.
Clock failures, including a same-typed `WriterCapacityRefused`, stay inside the
recorder. The original writer result or exception therefore remains unchanged.

The context binding is restored in `finally`. Separate concurrent requests do
not share a mutable current-request field. Deterministic concurrent-thread and
nested-binding witnesses prove exact identity restoration and correlation.
PR8's `type(capacity_admission) is BoundedWriterAdmission` restriction remains;
observation additionally requires the exact concrete recorder and gate even in
disabled mode. The private retry-provenance view still independently proves
body absence; observation records never grant retry eligibility.

Both owner and builder accept `capacity_observer=None` and
`measure_writer=False`. With measurement enabled, the owner calls the existing
measured CREATE/PAY public method, returns its identical primary producer value,
and retains `WriterAttemptMeasurement(identity, delivery)` separately in
`PostgresWriterRequest.measurements`. Refused/native-exception attempts have no
delivery. Existing recorder clock/final-construction failures preserve
UNAVAILABLE or NOT_COLLECTED; no timing is substituted with zero. The existing
measurement implementation and business algorithm were not modified.

Without an observation binding the gate uses its original acquire/call/finally
release path, with no observation clock or evidence allocation. Default owner
composition remains unmeasured. These seams add observation, not retries or
authority. Instrumentation adds timestamp/locking/allocation overhead; both A/B
conditions use it identically. Body observation overhead occurs inside permit
ownership; retry waiting remains outside it.

Required seam invariants before adoption:

- Disabled observation preserves current production behavior and cost boundaries.
- Both A/B conditions use identical measurement settings and observation code.
- The concrete gate still acquires once, executes once and releases in `finally`.
  No subclass or observer-issued exception can become verified refusal evidence.
- An instrumentation failure is retained separately, invalidates characterization
  evidence and never grants retry eligibility, masks an accepted result or changes
  the original writer exception. It cannot fabricate body entry/exit or release.
- Measured-delivery availability remains separate from producer outcome.
  Unavailable/incomplete measurements remain visible; missing timings are not zero.
- No callback is permitted to invoke business work, acquire authority or retain
  a permit across retry waiting. Timestamp overhead and callback failure behavior
  require deterministic witnesses and explicit documentation.

Production changes are confined to the three approved files. Focused seam
tests passed before the experiment adapter was added; source review confirmed
that the retry loop and eligibility rule remain unchanged. Stage 4E files were
not modified. The machinery is ready for human review, not approved live use.

## 5. Same-Source Disabled / Enabled Comparison

The runner pairs these conditions at one committed revision:

| Property | RETRY DISABLED | RETRY ENABLED |
|---|---|---|
| Caller | Real `build_postgres_writer_request` / `PostgresWriterRequest` | Same |
| Policy | `retry_policy=None` | Explicit `WriterRetryPolicy` |
| Budget | One attempt | Explicit M total attempts, including initial |
| Delay | None | Explicit tuple of M−1 positive finite durations |
| Capacity | Same concrete shared gate with explicit bound B | Same |
| Workload / connections / instrumentation | Same declared fixture, K, N and observation settings | Same |

K, offered concurrency levels N, B, M, all delay values, amount, warmups and
recorded repetitions remain **unselected**. There is no live-ready example plan
or numerical default. A later plan must enumerate these fields, the resulting
maximum attempts, maximum scheduled waiting and retained-connection budget.

A proposed first fixture is finite independent CREATE requests using
PRE_TRANSACTION / OCC / STRICT FullProof and distinct retained connections.
This is a method proposal for review, not an assertion about PAY/hot-key capacity.
Each paired cell needs equivalent logical content/order and fresh disjoint
Request IDs and Order IDs; reusing identifiers across cells would introduce
REPLAY contamination. Within a request, every attempt keeps its exact signature.

Each lane retains its thread, connection and current logical request until
terminal. Workload indices are assigned modulo N, identically in both conditions;
each lane then advances through its finite assigned items. All lane threads are
ready before one common cohort offer timestamp and release. This is experiment
dispatch, not a production queue. Retry waiting delays that lane's access to
fresh work; conclusions must preserve that qualification.

Pairs should be adjacent with recorded execution order and counterbalanced
condition ordering. Warmup and recorded cohorts must have separate identities,
accounting and summaries. Pairwise comparison requires matching source,
configuration, database/runtime facts and declared workload; mismatches invalidate
the pair rather than silently falling back to historical PR5 results.

## 6. PR9 Evidence Contract and Modules

Independent identifiers are schema version `1` and method identity
`pr9-production-retry-validation-v1`. The strict JSON codec preserves typed
signatures, events, measurements and missing values; it rejects unknown types,
fields, methods, versions, duplicate JSON keys and nonfinite values. It never
loads code named by an artifact. PR5 readers, artifacts and meanings stay intact.

| Experiment module | Responsibility |
|---|---|
| [pr9_model.py](../../../experiments/load_capacity_protection/pr9_model.py) | Explicit validated Plan, counterbalanced cell schedule, disjoint CREATE identities and PR9 raw records. No numerical plan defaults. |
| [pr9_evidence.py](../../../experiments/load_capacity_protection/pr9_evidence.py) | Independent allowlisted typed JSON round trip. No automatic file writes. |
| [pr9_characterization.py](../../../experiments/load_capacity_protection/pr9_characterization.py) | ProductionLane calls the real builder once per logical item; records waits, maps PR8/gate/measurement evidence, validates durable linkage and computes per-cell samples/counts. |
| [pr9_postgres_runtime.py](../../../experiments/load_capacity_protection/pr9_postgres_runtime.py) | Future guarded N+1 retained connection fixture, fresh-identity checks, post-drain control-connection verification and close evidence. Import performs no I/O. |
| [pr9_runner.py](../../../experiments/load_capacity_protection/pr9_runner.py) | Same-source paired orchestration, fixed lane assignment, stop/drain, verification and cumulative raw sink delivery. No alternate attempt loop. |

Each logical request gets its own bounded observer, while all lanes share the
same concrete gate in a cell. This avoids copying a growing cell-wide event
history for every completed request. Aggregate overlap uses the same clock domain.

| Record | Required facts |
|---|---|
| Run / cell | Run ID, source revision and source-state checks, method/schema identity, Python/psycopg/platform and clock identity, cohort/repetition/pair/execution index, K/N/B, explicit policy/delays, workload identity and composition identities. |
| Logical request | Workload index, complete generated signature, production logical invocation ID, lane/thread/connection identity, offer/invoke/terminal times, exact result evidence or sanitized failure classification, terminal disposition. |
| Attempt | Production attempt number and budget spend, admission-call times inside the public wrapper, capacity refusal, separate verified provenance and eligibility, protected-body entry/exit, original outcome/effect evidence and available phase measurements. |
| Retry wait | Refused attempt number, configured delay, production schedule/not-before/ready times, each actual waiter entry/exit, capacity/body activity evidence, transaction status, same retained connection and thread identity. |
| Durable verification | Post-quiescence event history and counts by request/order, idempotency verdict/signature/event linkage and raw identity row count, exact correspondence to the acknowledged result, explicit absence/unknown/mismatch. |
| Resource / validity | Connection acquisition/retention/close intervals, waiting intervals, incomplete intervals, source/runtime drift, observer failures, native/ambiguous outcomes, verification status and residual work. |

Preserve original PR8 observations alongside their PR9 projection. Never turn
None provenance/timestamps into measured evidence. Body/wait observations must
correlate to the same request/attempt, not rely only on exception type. Keep
native failure, ambiguous effect, semantic/concurrency result, disabled refusal,
enabled budget exhaustion, cancelled/expired and acknowledged acceptance distinct.

Store no DSNs, credentials, environment values or raw provider messages. Source
qualification must prove the experiment machinery itself is committed along with
the production code, not merely record a HEAD hash while running untracked code.
Protected `scripts/` is not part of source enumeration or evidence generation.
`collect_source` checks clean tracked state and that every required production
and PR9 module exists in HEAD, including explicitly checking HEAD membership
beyond `ls-files`. Source is checked before and after every cell; software/clock
facts and paired database/version/isolation/topology must match. An unavailable
post-cell source check stays None and invalidates evidence. A future reviewed
commit containing this machinery is required before live execution.

## 7. Accounting, Timings and Retained Resources

For a completed cell, preserve K logical requests, total dispatched attempts A,
verified pre-body capacity refusals R, additional attempts, terminal counts and
acknowledged ACCEPTED requests C. Additional attempts are the sum of each
request's attempts beyond its initial dispatch. Exhaustion is not completion.

Report at least:

- Attempt amplification A/K and logical completion proportion C/K; incomplete
  work remains in K and must not disappear from denominators.
- Acknowledged logical completion throughput C divided by offer-to-final-terminal
  drain duration, separate from generic terminal rate or attempt rate.
- Accepted logical offer-to-acknowledgement latency, all-terminal latency,
  invoke-to-terminal latency and first-dispatch waiting, with cohort/sample counts.
- Protected-body and admission-call latency separately, plus available
  UOW / append-admission / commit-finalization timing under the existing
  [Level-A contract](../../../src/pipeline/transactional/postgres_write_side_measurement.py).
  Overlapping phases must not be summed or interpreted as server CPU/SQL cost.
  Admission-call boundaries are inside the public writer wrapper; they do not
  timestamp the entire outer method. Logical invoke/terminal timestamps provide
  the separate owner interval.
- Maximum admitted-body overlap computed from complete half-open intervals;
  an exit at time t precedes an entry at t. Any missing interval or overlap above
  B invalidates the claimed bound. Application body overlap is not physical
  PostgreSQL transaction overlap.
  Incomplete body evidence produces no overlap estimate (None), rather than a
  fabricated zero. Incomplete waiting/resource evidence likewise leaves its
  population/retention aggregates unavailable. Raw observations remain retained.

For retry waiting, retain both the production schedule-to-ready interval and
actual waiter-call intervals. Early wakeups can produce multiple calls for one
scheduled retry; count distinct waiting logical requests, not nested event rows.
Report waiting population over time, its peak, total waiting duration, and the
integral of retained waiting connections over time. These are attributable
retention costs, not connection-pool occupancy or utilization claims.
Original owner schedule/ready values remain floating monotonic seconds. The
summary converts those intervals to nanoseconds for a common timeline, without
claiming additional clock precision. Wait-call and capacity timestamps retain
their original integer nanoseconds.

The retained topology is N distinct lane connections plus one distinct control
connection. Record that total separately from connections attributable to
currently waiting requests. Each waiter must retain its own lane/thread and
the same still-open connection. Capture transaction status immediately before
and after waiting without executing SQL through the business connection.

IDLE boundary samples plus exclusive custody and a waiter that only waits support
the no-active-transaction witness; samples alone are not continuous server-side
monitoring. The body/capacity timeline must independently establish that the
waiting request owns no permit and is outside writer execution. No caller-held
session or lifecycle locks may enter the declared fixture.

No CPU cost, scheduler contention, GIL explanation, fairness or pool behavior is
inferred from synchronous wait duration. Instrumentation adds overhead; its
placement and identical use in A/B must be documented, and PR5 phase numbers
must not be assumed directly comparable.

## 8. Durable Verification and Failure Preservation

Before a cell, verify fresh identities in the declared test database. After all
lanes quiesce, use the distinct control connection to verify every offered
logical request. Verification is outside the timed workload and does not invoke
the writer or authorize another attempt.

For each acknowledged ACCEPTED independent CREATE, require exactly one sequence-1
CREATED event, exact request/order/amount and returned event correspondence,
exact idempotency REPLAY signature/event linkage, exactly one raw idempotency row
matching request OR order, and no duplicate accepted event identity across
logical requests. Event counts by request and history by order must agree.

For refusal-only exhaustion, require no order history, zero matching events by
request, zero matching idempotency rows by request OR order, and an idempotency
MISS with no signature/event mapping. Apply equivalent absence verification to
disabled pre-body refusal once that provenance is independently established.

Native failures and ambiguous effects retain separate reconciliation evidence;
observed durable presence cannot be relabeled acknowledged acceptance. A normal
non-accepted result remains terminal. No retry follows verification. Unexpected
outcomes, source drift, instrumentation failure or verification mismatch stop
later cells while preserving raw evidence and draining already running work.
Instrumentation failures also invalidate evidence. Earlier completed request
records survive a later lane failure. Offered identities without complete
invocation records are retained as `UnobservedRequestEvidence`; verification is
still attempted after drain. If setup prevents verification, its state is
explicitly unavailable. Such identities never become acknowledged acceptance.

The implemented stop policy is explicit `stop_claims_and_drain_without_deadline`:
it does not abort an active writer. A hung native writer can prevent drain.
There is no watchdog or asynchronous cancellation. A later live approval must
accept this limitation or request a separately reviewed bounded-runtime method.
Raw evidence is delivered to a caller-supplied sink after every cell; a sink
failure stops subsequent cells and leaves the returned in-memory evidence
available. No crash-durable streaming guarantee is claimed.

No deletion/cleanup operation is selected or authorized here. A later live plan
must name its row-retention or exact cleanup scope separately. No general reset,
database cleanup or replay of historical PR5 cleanup is implied.
The implemented retention mode leaves earlier cells' rows in the test fixture.
Fresh logical identities prevent replay contamination but do not restore table
size, caches, WAL or physical database state. Counterbalanced adjacent pairs and
explicit cohorts qualify that limitation; they do not eliminate it.

## 9. Deterministic Machinery Tests

The focused tests cover the following without real sleeps or live PostgreSQL:

1. Both conditions use the real builder/owner, with only the declared retry
   configuration difference and identical observation settings.
2. Logical identities and distinct serial attempt identities reconcile with
   PR8 observations, eligibility and deterministic budget spend.
3. Waiting and body execution are separate, with no permit/transaction during
   waiting and stable retained connection/thread ownership.
4. Explicit finite budgets, exhaustion and admitted-body overlap are enforced
   and correctly represented, including incomplete/invalid evidence.
5. Verification detects duplicate/mismatched accepted effects and idempotency
   linkage, and requires reliable absence after refusal-only exhaustion.
6. Native/ambiguous failures and all normal semantic/concurrency terminals never
   retry; an admitted-body `WriterCapacityRefused` is not pre-body refusal.
7. PR8 events project without invented timestamps/provenance; measurement
   availability and instrumentation failures remain independent of writer results.
8. Warmup/recorded cohorts, pairing, same-source provenance, source changes and
   uncommitted machinery are distinguishable and checked.
9. No experiment retry scheduler, Rate Limiter, jitter, production queue, async
   execution, pool or Stage 4E authority path appears in the execution graph.

Deterministic storage doubles can validate verification logic but are not a
live durable-effect witness. That witness belongs to the later approved run.

## 10. Work Performed and Approval Boundary

Read the requested ADR, PR5/PR7/PR8 notes, current navigation and production
sources. Inspected the earlier runtime adapters and the existing phase
measurement contract to trace the observation gap. No historical evidence
archive, Release, credential file or local database was accessed.

The repository-local interpreter was verified with:

```bash
./.venv/bin/python -c "import sys; print(sys.executable)"
```

The focused validation command is:

```bash
PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/experiments/load_capacity_protection/test_pr9_characterization.py \
  tests/experiments/load_capacity_protection/test_pr9_runner.py \
  tests/experiments/load_capacity_protection/test_pr9_evidence.py \
  tests/unit/pipeline/transactional/test_writer_capacity_observation.py \
  tests/unit/pipeline/test_postgres_writer_request_observation.py \
  tests/unit/bootstrap/test_build_postgres_writer_request.py \
  tests/unit/pipeline/transactional/test_postgres_writer_capacity.py \
  tests/unit/pipeline/test_postgres_writer_request.py \
  tests/unit/pipeline/test_writer_retry_policy.py \
  tests/unit/pipeline/transactional/test_postgres_write_side_invocation_owner.py \
  tests/unit/pipeline/transactional/test_postgres_write_side_decision_receipt_runtime_owner.py \
  tests/unit/bootstrap/test_build_postgres_write_side_decision_receipt_runtime.py \
  tests/unit/compass/runtime/test_reinvocation_authority.py \
  tests/unit/compass/runtime/test_postgres_write_side_reinvocation_authority.py
```

This includes the new concrete-gate, owner, builder and PR9 evidence tests,
plus existing capacity, PR8 and Stage 4E regressions. The invocation uses the
repository-local interpreter, suppresses bytecode writes and disables pytest's
cache provider. Event/barrier coordination and injected advancing clocks replace
real sleeps. Storage doubles exercise the actual measured writer algorithm's
UOW/append/commit path; they are not evidence from a live PostgreSQL server.

Final focused result: **369 passed**. The local Markdown check verified **63**
file links. All **17** authorized changed/added files were checked for trailing
whitespace and final newlines, including the untracked PR9 additions.

`git diff --check`, a scoped diff/status review and local Markdown link checks
complete the review preparation. No live PostgreSQL, load matrix, full suite,
lint, build or static type check was run. Dependencies, environment files,
historical evidence, Releases and protected `scripts/` remain untouched. No
staging, commit, push or remote operation was performed.

The next human decision is review of the seams and machinery. A separate
approved live plan must then select K/N/B/M, exact delay tuples, amount, cohorts,
test-database identity, connection budget, connect timeout, stop/drain limits,
evidence sink and data-retention scope. The current implementation only supports
retaining rows and draining without a deadline. No live values are frozen here,
and test constants must not be promoted to live or production defaults.

PR9 remains **ACTIVE**, with machinery ready for human review. It cannot be marked
complete until contemporaneous live evidence is collected, durably verified and
reviewed. No claim of improved production performance, optimal numbers, or the
permanent necessity/unnecessity of rate limiting, jitter or queueing follows.
