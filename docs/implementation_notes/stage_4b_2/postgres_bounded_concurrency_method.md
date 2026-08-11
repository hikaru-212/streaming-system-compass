# Stage 4B.2 PR7 — PostgreSQL Bounded Concurrency Method

[← Back to Stage 4B.2](README.md)

## Status and Authority

This document is the current methodology authority for Stage 4B.2 PR7.

```text
PR7 responsibility
= Level-C bounded local concurrency / contention characterization

method
= DEFINED

connection-budget preflight
= REQUIRED / DEFINED / NOT EXECUTED

retained worker levels
= PENDING LIVE PREFLIGHT + HUMAN REVIEW

full concurrency runtime
= NOT IMPLEMENTED

canonical Level-C evidence
= NOT EXECUTED

production policy
= NONE
```

The method consumes the accepted PR6 Level-B comparison and Level-A producer
measurement without modifying either. PR6 schema version 1, runtime invariants,
tests, and canonical evidence remain frozen.

## 1. Responsibility Boundary

PR7 asks how the two accepted PostgreSQL write compositions change when a
bounded number of concurrent requests are released together in one recorded
environment.

```text
Level C
= bounded synchronized-burst concurrency / contention characterization

Level C
!= production capacity certification
!= sustained production load test
!= SLO benchmark
!= rate-limit derivation
!= automatic strategy selection
!= retry policy
```

The result is descriptive and environment-qualified. It may describe a visible
knee or no visible knee inside the human-approved retained levels. It cannot
establish universal capacity, a production worker count, or a saturation
threshold for another environment.

## 2. Fixed Compositions

PR7 retains exactly the current PR6 compositions:

```text
PRE_OCC
= PRE_TRANSACTION validation
+ current optimistic/OCC append-time admission

IN_PESSIMISTIC
= IN_TRANSACTION validation
+ current concrete PostgreSQL pessimistic admission
```

Both use the current measured CREATE surface, the real `FullProofValidator`
pipeline, and `ValidationMode.STRICT`.

PR7 does not introduce or measure:

- `IN_OCC`;
- PRE plus pessimistic admission;
- no-preliminary-idempotency variants; or
- any other counterfactual topology.

Those questions belong to a separately reviewed post-PR6 supplemental
investigation. They cannot enter PR7 merely to explain a Level-C observation.

## 3. Workload Families

The two workload families are distinct experiment cells and analysis groups.
They are never pooled.

### 3.1 `SAME_ORDER_HOT_STREAM`

One burst contains `N` concurrent fresh CREATE requests with:

```text
request_id
= distinct per lane

order_id
= one shared fresh order for the batch

expected accepted sequence
= 1

initial accepted history for that order
= empty
```

Purpose:

- characterize hot-stream contention;
- retain typed `ACCEPTED`, `APPEND_STALE_WRITE`, and
  `PREPARE_LOCK_TIMEOUT` observations;
- distinguish early from late rejection work; and
- characterize all-completion behavior for one synchronized burst.

The release barrier creates an opportunity for overlap but does not guarantee a
particular scheduler interleaving or rejection count. The recorded schedule is
never extended until a preferred outcome count appears.

### 3.2 `DIFFERENT_ORDER_GENERAL_CONCURRENCY`

One burst contains `N` concurrent fresh CREATE requests with:

```text
request_id
= distinct per lane

order_id
= distinct fresh order per lane

expected accepted sequence
= 1

initial accepted history for every order
= empty
```

Purpose:

- characterize accepted general database concurrency;
- characterize accepted completion scaling; and
- retain per-invocation latency under independent-stream concurrency.

The retained core cohort is `ACCEPTED`. A replay, conflict, validation block,
admission rejection, unsupported result combination, or exception does not
silently enter that core cohort.

At worker level 1, both families are uncontended but remain separately labeled
cells. They are not automatically pooled because their workload-family identity
is part of the Level-C evidence contract.

## 4. Synchronized-Burst Arrival Model

PR7 uses a bounded synchronized-burst protocol.

For each recorded batch:

1. `N` persistent worker threads already exist.
2. `N` persistent worker connections already exist.
3. writers, validation runtimes, commands, and identifiers are prepared before
   timing.
4. every worker waits at one release barrier outside its invocation timer.
5. the barrier action captures one common monotonic batch reference.
6. each worker starts its external invocation timer after barrier release.
7. batch timing spans release to the last invocation completion.
8. outcome classification, persistence verification, connection checks, and
   cleanup occur after batch timing.

```text
recorded protocol
= bounded synchronized-burst behavior

recorded protocol
!= steady-state sustained throughput
!= open-loop arrival process
!= production load generator
```

Any throughput-like result must be named as recorded burst or batch completion
rate under this protocol. The term `throughput` without this qualification is
not an accepted PR7 conclusion.

## 5. Timing Boundaries

All elapsed collection uses `time.perf_counter_ns()` or an exactly equivalent
monotonic nanosecond clock seam.

### 5.1 Per-invocation timer

The external invocation timer starts immediately after the worker leaves the
release barrier and immediately before the public measured CREATE call. It
stops on normal return or immediately when an ordinary `Exception` reaches the
experiment boundary.

It excludes:

- connection, worker, writer, validator, and runtime construction;
- command and identity construction;
- barrier waiting and release coordination;
- warmup;
- outcome classification;
- persistence and connection verification;
- serialization and aggregation; and
- cleanup.

### 5.2 Batch timer

The batch reference is captured once by the release-barrier action. Batch
elapsed stops at the latest external invocation stop reading in the batch.

```text
batch_elapsed_ns
= last_invocation_completion_ns - release_reference_ns
```

The batch timer does not include post-return verification. A separate
controller-overhead observation may measure orchestration and verification
outside producer timing, but it cannot be added to producer or batch elapsed.

### 5.3 Start offsets

Each worker retains:

```text
start_offset_ns
= invocation_start_ns - release_reference_ns
```

Each batch retains the minimum and maximum start offsets. Their difference is
the observed release skew for that batch. PR7 defines no universal acceptable
skew percentage. Skew material relative to invocation or batch duration is a
human-review condition.

## 6. Level-C Raw Observations

### 6.1 Invocation record

Every planned invocation retains:

- PR7 schema name and version;
- experiment-local run and sample identity;
- worker level;
- workload family;
- composition;
- batch index;
- lane index;
- external elapsed nanoseconds;
- start offset nanoseconds;
- exact producer outcome;
- exact rejection stage and admission verdicts needed for classification;
- exact typed cohort;
- measurement availability;
- all thirteen PR3 phase records when measurement is available; and
- exception class name only when an ordinary exception propagates.

The thirteen phase names remain:

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

Phase state preserves `NOT_APPLICABLE`, `NOT_REACHED`, `NOT_COLLECTED`, and
`MEASURED`; missing is never rewritten as measured zero.

### 6.2 Batch record

Every recorded batch retains:

- PR7 schema name and version;
- experiment-local run and batch identity;
- worker level;
- workload family;
- composition;
- monotonic release reference;
- first invocation start offset;
- last invocation start offset;
- release-to-last-completion elapsed nanoseconds;
- completed count;
- accepted count; and
- exact typed outcome counts.

For a structurally complete batch:

```text
completed_count
= worker_level
```

An ordinary exception still completes its planned lane for accounting, but it
invalidates the affected recorded cell or run. It is not assigned a latency
cohort.

## 7. Descriptive Metrics

Per exact workload-family, composition, worker-level, and typed-outcome cohort,
PR7 may report:

- count;
- minimum;
- maximum;
- mean; and
- median.

Per batch it may derive:

```text
accepted_completion_rate_per_second
= accepted_count * 1_000_000_000 / batch_elapsed_ns

all_completion_rate_per_second
= completed_count * 1_000_000_000 / batch_elapsed_ns
```

These are protocol-qualified synchronized-burst completion rates. They are not
arrival limits or production throughput guarantees.

PR7 must not derive:

```text
rate_limit = 1 / mean_latency
```

Internal phase intervals may overlap and are never summed as if they were
disjoint wall-clock components.

## 8. Outcome and Latency Rules

Terminal outcomes remain separate.

For `SAME_ORDER_HOT_STREAM`, supported latency cohorts are only exact current
combinations that classify as:

- `ACCEPTED`;
- `APPEND_STALE_WRITE`; or
- `PREPARE_LOCK_TIMEOUT`.

Their latencies are never averaged into one strategy latency. Typed outcome
counts and rates may be described without asserting outcome equivalence.

For `DIFFERENT_ORDER_GENERAL_CONCURRENCY`, the retained core cohort is
`ACCEPTED`. An unsupported normal result, inconsistent verdict combination,
unavailable required measurement, missing required phase, or unexpected
exception invalidates the affected recorded cell or run according to the
frozen validation method.

There is no automatic retry, replacement sample, run-more-until-accepted rule,
or adaptive cohort extension.

## 9. Candidate and Retained Worker Levels

The planning candidates remain:

```text
1
2
4
8
```

```text
candidate level
!= retained level

budget-feasible candidate
= candidate whose raw live connection requirement fits before safety headroom

proposed level
= budget-feasible candidate returned for human review

retained level
= proposed level accepted only after human review chooses environment-specific
  safety headroom
```

The connection-budget preflight always reports an empty final retained-level
set. It cannot make the human headroom decision. At method-definition time the
retained set remains pending live preflight plus human review. No candidate is
retained merely because it appears in the planning set or fits the raw
connection ceiling before headroom.

After human review, the exact retained set is frozen into the canonical
schedule and manifest before execution. A recorded run never silently drops,
adds, or extends a level.

If worker level 8 is not credible, that is not a preflight failure. If fewer
than three levels survive human review, PR7 may still report bounded contention
evidence but cannot claim a meaningful saturation curve without separate human
review.

## 10. Connection-Budget Preflight

The PR7-owned preflight is read-only and untimed. It uses one temporary
controller connection to a database whose name passes the repository `_test`
suffix guard. It performs no producer call, write, warmup, concurrency, reset,
evidence publication, or benchmark.

It records only sanitized facts:

- PostgreSQL server-version number;
- `max_connections`;
- `superuser_reserved_connections`;
- `reserved_connections` when exposed by the server;
- whether the current role is superuser-capable or may use reserved slots;
- current client-backend session count, including the preflight controller;
- preflight controller consumption;
- current other-session count after excluding that controller;
- the current role's usable connection ceiling;
- worker connections available before human-selected headroom; and
- the requirement and remaining raw slots for each candidate level.

It never records or prints:

- DSN;
- hostname or host;
- port;
- database name;
- username;
- password or credentials; or
- environment-variable values.

The preflight does not change PostgreSQL configuration, terminate sessions,
create a connection pool, or reserve future capacity.

### 10.1 Role-qualified usable ceiling

When `reserved_connections` is unavailable, its applied value is zero. The
raw current-role ceiling is:

```text
superuser role
usable_connection_ceiling
= max_connections

role allowed to use reserved connections
usable_connection_ceiling
= max_connections - superuser_reserved_connections

regular role
usable_connection_ceiling
= max_connections
  - superuser_reserved_connections
  - reserved_connections_applied
```

The current client-backend count is a point-in-time observation, not a future
reservation.

### 10.2 Connection accounting

The future recorded runtime topology is:

```text
N workers
= N persistent worker threads
= N persistent worker connections

dedicated recorded-runtime controller connections
= 0

dedicated observer connections
= 0

required_connections(N)
= N
```

Lane 0 may own setup/reset and post-timing verification only while no timed
batch is active. Every lane owns exactly one connection, and no connection is
shared concurrently. All worker connections must be pre-opened before warmup.

The budget preflight itself temporarily consumes one controller connection:

```text
other_sessions
= current_client_sessions - 1 preflight controller

available_worker_connections_before_headroom
= max(0, usable_connection_ceiling - other_sessions)
```

A candidate is proposed for human review when:

```text
required_connections(candidate)
<= available_worker_connections_before_headroom
```

This is feasibility before headroom, not acceptance. The preflight deliberately
does not invent or apply a universal numeric headroom.

### 10.3 Budget statuses

```text
HUMAN_REVIEW_REQUIRED
= at least one candidate is feasible before headroom

INSUFFICIENT_BUDGET
= no candidate is feasible before headroom

invalid preflight
= server facts are missing, malformed, internally inconsistent,
  or the guarded database requirement fails
```

No status automatically produces final retained levels.

## 11. PR7-Owned Schemas

PR7 defines a new namespace and version for future Level-C evidence:

```text
schema_name
= stage4b2-pr7-bounded-concurrency

schema_version
= 1
```

The future evidence schema must include separate invocation and batch records
with the fields in Sections 6.1 and 6.2. Aggregates must key by worker level,
workload family, composition, and exact typed cohort where applicable.

The connection-budget preflight has a separate sanitized schema:

```text
schema_name
= stage4b2-pr7-connection-budget-preflight

schema_version
= 1
```

Neither schema modifies or aliases PR6 schema version 1. PR7 records use only
experiment-local accounting identities. They introduce no `attempt_id`,
`execution_id`, retry meaning, or runtime-governance authority.

## 12. Fixed Counts and p95 Decision

The first PR7 protocol freezes:

```text
warmup batches per exact cell
= 3

recorded batches per exact cell
= 30

exact cell
= one retained worker level
+ one workload family
+ one composition
```

Every recorded batch contains exactly `worker_level` planned invocations. The
schedule is generated once after retained-level review and consumed once. It
does not adapt to observed latency, outcomes, or cohort counts.

Composition-first order must balance across matched cells. Level and workload
ordering must be deterministic from a recorded schedule seed. The full schedule
generator and executor remain later PR7 implementation work.

The first protocol omits p95. A same-order accepted cohort can contain at most
one accepted observation per batch, giving only 30 planned accepted
observations before any invalidity or insufficiency. That is not a credible
basis for a stable tail statistic across every exact cell. PR7 therefore reports
count, minimum, maximum, mean, and median only. Any later p95 addition requires
a separately reviewed fixed sample-count change and cannot adaptively extend a
recorded run.

## 13. Stability and Harness Evidence

The future runtime and evidence must show:

- start-offset distributions per worker level;
- first and last start offsets per batch;
- batch release skew;
- controller/orchestration timing outside measured producer time;
- stable lane-to-thread and lane-to-connection ownership;
- no connection creation during warmup or recorded timing;
- one deterministic fixed schedule;
- three fixed warmup batches per exact cell;
- thirty fixed recorded batches per exact cell;
- no retry, replacement, or adaptive extension; and
- sanitized environment facts recorded once per run.

PR7 defines no universal skew percentage, controller-overhead threshold, or
environment-drift threshold. Material skew, orchestration cost, or instability
relative to producer and batch duration stops interpretation for human review.

## 14. Validation and Stop Conditions

Before any canonical run, deterministic tests must prove:

- candidate levels remain distinct from proposed and retained levels;
- connection requirement accounting is exact;
- preflight serialization cannot contain secret-shaped metadata;
- invalid and insufficient budget states remain distinct;
- the future schedule is fixed and balanced;
- same-order and different-order identities cannot be pooled;
- connections and workers are preconstructed and stable;
- barrier wait occurs outside invocation timing;
- batch timing ends before verification;
- typed cohorts remain separate;
- no adaptive extension occurs; and
- invalid evidence cannot be published as complete.

Stop for human review if:

- live connection facts cannot be obtained safely;
- the `_test` database guard fails;
- the connection budget or chosen headroom remains unknown;
- a retained level cannot pre-open every required worker connection;
- environment instability dominates the curve;
- release skew or controller work dominates producer/batch timing;
- the harness becomes the bottleneck;
- unsupported outcomes would need to be pooled or ignored;
- required Level-A measurement becomes unavailable;
- production source, migrations, dependencies, PR6 artifacts, retry behavior,
  idempotency semantics, or runtime policy would need to change; or
- fewer than three levels are being described as a meaningful saturation curve
  without human review.

## 15. Execution Sequence

The accepted PR7 sequence is:

```text
method authority
→ pure connection-budget accounting tests
→ guarded read-only live budget preflight
→ human headroom and retained-level review
→ separate full runtime design and deterministic tests
→ separately authorized PostgreSQL smoke
→ separately authorized canonical Level-C run
→ evidence validation and report
```

This method and preflight capability do not authorize the later arrows.

## 16. Required Preflight Execution

The live connection-budget preflight has not executed at the method-definition
point. It may run only after the pure deterministic preflight tests pass. From
an already configured project shell, the accepted command is:

```bash
./.venv/bin/python -m experiments.stage4b2.postgres_bounded_concurrency --preflight
```

The command must emit only the sanitized preflight schema and must expose no
Level-C runtime or recorded-experiment entry point. Its result must remain a
proposal for human headroom review; it cannot retain worker levels by itself.

After live preflight, a separate evidence-alignment checkpoint may record:

- deterministic preflight validation results;
- sanitized live budget facts;
- raw feasibility and remaining slots for every candidate;
- the preflight status;
- the explicit human headroom decision; and
- the final experiment-local retained levels.

Until that checkpoint, retained worker levels remain pending. Any later retained
set defines only fixed Level-C experimental points for the recorded local
environment. It cannot certify production capacity, recommend production
concurrency, define safe production headroom, recommend a connection pool, or
establish saturation.

## 17. Explicit Non-Goals

PR7 does not implement or decide:

- production load generation or distributed benchmarking;
- steady-state or open-loop arrival behavior;
- production capacity, SLOs, autoscaling, or rate limiting;
- a connection pool or pool redesign;
- strategy selection or automatic switching;
- retry governance or attempt identity;
- idempotency redesign or supplemental counterfactual compositions;
- production telemetry or durable measurement persistence;
- migrations or schema changes;
- `DecisionReceipt`, accepted-event metadata, or `DiagnosticTrace` changes;
- read-side or snapshot measurement; or
- universal performance, skew, saturation, or headroom thresholds.
