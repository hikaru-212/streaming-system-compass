# Stage 4B.2 PR7 — PostgreSQL Bounded Concurrency Method

[← Back to Stage 4B.2](README.md)

## Status and Authority

This document is the current methodology authority for Stage 4B.2 PR7.

```text
PR7 responsibility
= Level-C bounded local concurrency / contention characterization

method
= DEFINED

method-definition-time connection-budget preflight
= REQUIRED / DEFINED / NOT EXECUTED

method-definition-time retained worker levels
= PENDING LIVE PREFLIGHT + HUMAN REVIEW

method-definition-time full concurrency runtime
= NOT IMPLEMENTED

current connection-budget preflight
= EXECUTED / VALID

current human-retained worker levels
= (1, 2, 4, 8)

current deterministic full Level-C runtime
= IMPLEMENTED / VALIDATED

current runtime deterministic tests
= GREEN

PostgreSQL smoke method
= DEFINED

PostgreSQL smoke execution
= EXECUTED / STRUCTURALLY_VALID

release-skew human review
= COMPLETE / ACCEPTED FOR THE NEXT PR7 GATE

canonical Level-C evidence/persistence contract
= DEFINED

canonical Level-C evidence persistence implementation
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
retained set was pending live preflight plus human review. No candidate was or
is retained merely because it appears in the planning set or fits the raw
connection ceiling before headroom.

The guarded live preflight subsequently executed and was valid. Human review
then retained exactly `1`, `2`, `4`, and `8` as environment-local experimental
points. That retained set is frozen into the canonical schedule before
execution. A recorded run never silently drops, adds, or extends a level.

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

The implemented and deterministically validated recorded runtime topology is:

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
ordering must be deterministic from a recorded schedule seed. The full
schedule generator and executor are implemented and deterministically
validated. The canonical schedule has not executed.

The first protocol omits p95. A same-order accepted cohort can contain at most
one accepted observation per batch, giving only 30 planned accepted
observations before any invalidity or insufficiency. That is not a credible
basis for a stable tail statistic across every exact cell. PR7 therefore reports
count, minimum, maximum, mean, and median only. Any later p95 addition requires
a separately reviewed fixed sample-count change and cannot adaptively extend a
recorded run.

## 13. Stability and Harness Evidence

The implemented runtime establishes the structural capability, and canonical
evidence must show:

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
- the canonical schedule is fixed and balanced;
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

At the method-definition point, the live connection-budget preflight had not
executed and could run only after the pure deterministic preflight tests
passed. From an already configured project shell, the accepted command was:

```bash
./.venv/bin/python -m experiments.stage4b2.postgres_bounded_concurrency --preflight
```

The command must emit only the sanitized preflight schema and must expose no
Level-C runtime or recorded-experiment entry point. Its result must remain a
proposal for human headroom review; it cannot retain worker levels by itself.

The subsequent live preflight was valid, and the completed evidence-alignment
checkpoint recorded:

- deterministic preflight validation results;
- sanitized live budget facts;
- raw feasibility and remaining slots for every candidate;
- the preflight status;
- the explicit human headroom decision; and
- the final experiment-local retained levels.

Until that checkpoint, retained worker levels were pending. That historical
condition is now closed: human review retained exactly `1`, `2`, `4`, and `8`.
Those levels define only fixed Level-C experimental points for the recorded
local environment. They do not certify production capacity, recommend
production concurrency, define safe production headroom, recommend a
connection pool, or establish saturation.

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

## 18. Separately Authorized PostgreSQL Smoke Protocol

The PostgreSQL smoke is a correctness and topology gate between deterministic
runtime validation and any separately authorized canonical Level-C run. Its
only purpose is to prove that the real guarded PostgreSQL topology,
synchronized release mechanics, current production compositions, exact
cohorts, frozen phase topology, persistent connection reuse, and durable
verification behave coherently in the recorded environment.

```text
PostgreSQL smoke
= experiment-local correctness and topology validation

PostgreSQL smoke
!= canonical Level-C evidence
!= performance evidence
!= a reduced performance benchmark
!= production concurrency certification
```

Smoke invocation and batch observations remain separately labeled smoke
evidence. They cannot enter canonical Level-C raw records, aggregates,
completion-rate summaries, curves, or comparisons.

### 18.1 Exact cells and fixed count

The smoke covers every already reviewed PR7 coordinate:

```text
4 retained worker levels
× 2 workload families
× 2 compositions
= 16 exact smoke cells

smoke bursts per exact cell
= 1

total smoke bursts
= 16
```

The retained worker levels remain exactly `1`, `2`, `4`, and `8`. The workload
families remain exactly `SAME_ORDER_HOT_STREAM` and
`DIFFERENT_ORDER_GENERAL_CONCURRENCY`. The compositions remain exactly
`PRE_OCC` and `IN_PESSIMISTIC`; the smoke introduces no `IN_OCC` or other
counterfactual composition.

The smoke uses the same deterministic cell-order semantics already frozen by
the canonical seed-73 schedule. Only its batch count differs:

| Cell order | Worker level | Workload family | Composition |
| ---: | ---: | --- | --- |
| 1 | 8 | `SAME_ORDER_HOT_STREAM` | `PRE_OCC` |
| 2 | 8 | `SAME_ORDER_HOT_STREAM` | `IN_PESSIMISTIC` |
| 3 | 8 | `DIFFERENT_ORDER_GENERAL_CONCURRENCY` | `IN_PESSIMISTIC` |
| 4 | 8 | `DIFFERENT_ORDER_GENERAL_CONCURRENCY` | `PRE_OCC` |
| 5 | 2 | `DIFFERENT_ORDER_GENERAL_CONCURRENCY` | `PRE_OCC` |
| 6 | 2 | `DIFFERENT_ORDER_GENERAL_CONCURRENCY` | `IN_PESSIMISTIC` |
| 7 | 2 | `SAME_ORDER_HOT_STREAM` | `IN_PESSIMISTIC` |
| 8 | 2 | `SAME_ORDER_HOT_STREAM` | `PRE_OCC` |
| 9 | 1 | `SAME_ORDER_HOT_STREAM` | `PRE_OCC` |
| 10 | 1 | `SAME_ORDER_HOT_STREAM` | `IN_PESSIMISTIC` |
| 11 | 1 | `DIFFERENT_ORDER_GENERAL_CONCURRENCY` | `IN_PESSIMISTIC` |
| 12 | 1 | `DIFFERENT_ORDER_GENERAL_CONCURRENCY` | `PRE_OCC` |
| 13 | 4 | `DIFFERENT_ORDER_GENERAL_CONCURRENCY` | `PRE_OCC` |
| 14 | 4 | `DIFFERENT_ORDER_GENERAL_CONCURRENCY` | `IN_PESSIMISTIC` |
| 15 | 4 | `SAME_ORDER_HOT_STREAM` | `IN_PESSIMISTIC` |
| 16 | 4 | `SAME_ORDER_HOT_STREAM` | `PRE_OCC` |

The smoke has no recorded warmup series and does not use the canonical three
warmup plus thirty recorded batches per cell. It performs no retry, replacement
batch, outcome-sensitive repetition, or adaptive extension. Every planned
smoke cell executes at most once.

### 18.2 Persistent topology and ownership

For each retained worker level `N`:

```text
N persistent worker threads
= N persistent PostgreSQL connections
= N fixed lane owners
```

The topology is opened before that level's first smoke burst. Its `N` threads,
connections, validation runtimes, composition writers, and lane owners are
reused across all four smoke cells for that level. No connection is shared
concurrently and no connection is created inside a smoke batch.

The synchronized producer batch adds no dedicated controller or observer
connection. Lane 0 may perform guarded reset, fresh-identity setup, and
post-timing verification only while no batch is active, consistent with the
accepted Level-C runtime topology.

### 18.3 Synchronized release and timing review

Every smoke burst uses the canonical synchronized-release boundary:

1. identities and commands are prepared before timing;
2. all `N` lanes reach one outside-timer barrier;
3. the barrier action captures one common monotonic release reference;
4. each lane captures its invocation start only after release and immediately
   before the public measured CREATE call;
5. each lane captures its invocation stop on normal return or when an ordinary
   `Exception` reaches the experiment boundary;
6. batch elapsed ends at the latest invocation stop; and
7. classification, durable verification, connection checks, and cleanup begin
   only after every lane has captured its stop reading.

Each smoke batch retains its first and last start offsets, observed release
skew, and release-to-last-completion batch elapsed. The following structural
facts are machine validated:

- exactly one release reference exists for the batch;
- no invocation start precedes that reference;
- no invocation stop precedes its start;
- first and last offsets equal the minimum and maximum lane offsets;
- batch elapsed equals the last completion relative to release;
- completed count equals the worker level; and
- verification starts only after every invocation stop.

PR7 defines no arbitrary numeric smoke-skew threshold. The observed release
skew magnitude is reviewed by a human relative to invocation and batch
duration before canonical authorization. Canonical execution cannot proceed if
that review shows an obvious harness-dominated release failure. Passing this
review is environment-local and is not a production concurrency guarantee.

### 18.4 Expected workload and cohort behavior

For `DIFFERENT_ORDER_GENERAL_CONCURRENCY`, every invocation must classify as:

```text
ACCEPTED
```

Any other normal cohort invalidates the smoke cell and therefore the smoke.

For `SAME_ORDER_HOT_STREAM`, only these composition-specific cohorts are
supported:

```text
PRE_OCC
→ ACCEPTED
→ ADMISSION_REJECTED_APPEND_STALE_WRITE

IN_PESSIMISTIC
→ ACCEPTED
→ ADMISSION_REJECTED_PREPARE_LOCK_TIMEOUT
```

At worker level `1`, both workload families are uncontended and must return
`ACCEPTED`. At levels greater than `1`, the smoke does not prescribe an
accepted/rejected numerical split. It instead requires every invocation to
belong to the exact supported workload/composition cohort set, accepted
history to remain durable and coherent, rejected request identities to remain
absent from accepted history, and every lane connection to remain reusable.
The smoke is never repeated to obtain a preferred outcome count.

### 18.5 Frozen thirteen-phase topology

The smoke reuses the exact current thirteen-phase state matrices already frozen
by the Level-C runtime for these four supported composition/cohort pairs:

- `PRE_OCC + ACCEPTED`;
- `PRE_OCC + APPEND_STALE_WRITE`;
- `IN_PESSIMISTIC + ACCEPTED`; and
- `IN_PESSIMISTIC + PREPARE_LOCK_TIMEOUT`.

All thirteen records must exist exactly once, every state must match its frozen
matrix, measured phases must retain elapsed nanoseconds, and non-measured
phases must retain `elapsed_ns = None`. Missing phases, unexpected measured
phases, or any other state mismatch invalidate the smoke. The smoke defines no
second measurement vocabulary or smoke-specific phase topology.

### 18.6 Durable and connection validation

After every timed smoke batch, outside producer and batch timing:

- accepted writes must exist exactly as expected in accepted history;
- a rejected request identity must not appear as an accepted write;
- strict `FullProofValidator` evidence and `ValidationMode.STRICT` must remain
  coherent where the accepted runtime requires them;
- every lane must pass a `SELECT 1` reuse check;
- every lane connection must be restored to PostgreSQL `IDLE`; and
- stable lane-to-thread and lane-to-connection ownership must remain intact.

An unexpected ordinary exception invalidates the smoke. Only its class name may
enter experiment-local diagnostic evidence; its message does not. No retry or
replacement follows an exception, verification failure, or invalid batch.

### 18.7 Smoke result boundary

The separately labeled smoke result may retain only correctness and topology
facts needed for the canonical-authorization decision, including:

- the exact sixteen-cell identity and one-batch accounting;
- invocation and batch completeness;
- exact supported typed cohorts;
- the frozen thirteen-phase state topology;
- stable thread, lane, and connection ownership and reuse facts;
- durable accepted/rejected history verification;
- release offsets, release skew, and batch elapsed; and
- sanitized PostgreSQL runtime facts such as server version, isolation level,
  autocommit state, and topology label.

It does not retain credentials or connection endpoint identity. It cannot be
interpreted as production throughput, production capacity, a saturation point,
an SLO, a rate limit, a safe concurrency limit, a connection-pool
recommendation, or universal PRE/IN superiority.

PR7's bounded concurrency evidence may later serve as an empirical input to
load-admission or rate-limiting work, but PR7 does not derive or select such a
policy.

### 18.8 Smoke stop conditions and canonical gate

The smoke stops without retry, replacement, or further smoke cells when any
cell shows:

- an unexpected ordinary exception;
- an unsupported workload/composition cohort;
- missing measurement or a missing, duplicate, or wrong phase state;
- an incomplete invocation or batch account;
- lane, thread, or connection ownership violation;
- connection reuse or PostgreSQL `IDLE` restoration failure;
- durable accepted-history or rejected-request verification failure;
- wrong same-order or different-order request/order identity behavior;
- invalid release reference, start offset, stop, skew, or batch elapsed
  accounting; or
- PostgreSQL test-database guard failure.

No failed cell may be replaced, and no later cell may be run merely to improve
the smoke result. A structurally valid smoke still requires explicit human
review of observed release skew before canonical authorization. The smoke
definition does not itself authorize smoke execution, and neither a valid
smoke nor its skew review authorizes the canonical Level-C run without the next
separate human checkpoint.

## 19. Accepted Live PostgreSQL Smoke Checkpoint

The human-operated real PostgreSQL smoke executed exactly once from committed
source and completed structurally valid. This section records the accepted
execution checkpoint without changing the protocol defined in Section 18.

### 19.1 Execution identity and status

```text
source commit
= 8dcfbdc1e1bc4cca8a8e7c48a73126a40ec9c958

run ID
= stage4b2-pr7-postgres-smoke-8dcfbdc

PostgreSQL smoke
= EXECUTED / STRUCTURALLY_VALID

canonical Level-C
= NOT EXECUTED

production policy
= NONE
```

### 19.2 Exact smoke accounting

```text
planned cells
= 16

completed cells
= 16

planned invocations
= 60

observed invocations
= 60

failed cell
= NONE
```

The smoke completed every retained coordinate:

```text
worker levels
= 1, 2, 4, 8

workload families
= SAME_ORDER_HOT_STREAM
  DIFFERENT_ORDER_GENERAL_CONCURRENCY

compositions
= PRE_OCC
  IN_PESSIMISTIC
```

### 19.3 Observed live topology

Every visited worker level reported:

```text
N lanes
= N threads
= N PostgreSQL connections

topology label
= guarded-test-postgresql

PostgreSQL server version identity
= 160014

transaction isolation
= READ_COMMITTED

autocommit
= false
```

This checkpoint records no endpoint identity, database name, role identity,
credentials, or `TEST_DATABASE_URL` value.

### 19.4 Observed smoke cohorts

For `DIFFERENT_ORDER_GENERAL_CONCURRENCY`, every observed invocation was
`ACCEPTED` for both compositions at worker levels `1`, `2`, `4`, and `8`.

For `SAME_ORDER_HOT_STREAM`, worker level `1` produced:

```text
PRE_OCC
= ACCEPTED

IN_PESSIMISTIC
= ACCEPTED
```

At worker levels `2`, `4`, and `8`, the observed composition-specific splits
were:

```text
PRE_OCC
= 1 ACCEPTED
+ (N - 1) ADMISSION_REJECTED_APPEND_STALE_WRITE

IN_PESSIMISTIC
= 1 ACCEPTED
+ (N - 1) ADMISSION_REJECTED_PREPARE_LOCK_TIMEOUT
```

These numerical splits are bounded observations from this one local smoke.
They are not promoted to production invariants, universal concurrency
semantics, guaranteed rejection counts, or expectations for another run or
environment.

### 19.5 Completed release-skew human review

The required human release-skew review completed using the per-cell invocation
and batch diagnostics. The observed release-skew ranges were:

| Worker level | Observed release-skew range |
| ---: | ---: |
| 1 | `0 ns` |
| 2 | `30,583 ns` to `75,625 ns` |
| 4 | `84,666 ns` to `112,083 ns` |
| 8 | `197,041 ns` to `345,916 ns` |

The most notable relative smoke cell was:

```text
worker level
= 8

workload family
= SAME_ORDER_HOT_STREAM

composition
= IN_PESSIMISTIC

release skew
= 219,792 ns

median invocation elapsed
= 2,244,312.5 ns

batch elapsed
= 4,302,292 ns
```

```text
human review conclusion
= ACCEPTED FOR THE NEXT PR7 GATE

reason
= No observed smoke cell showed obvious release-harness domination relative
  to its invocation and batch durations.
```

This conclusion defines no numeric acceptable-skew threshold and does not claim
that the observed skew is universally safe. Canonical Level-C evidence must
still retain and expose release-skew distribution. Interpretation may still
stop if canonical batches show material harness domination.

### 19.6 Performance interpretation boundary

The one-burst-per-cell smoke is not performance evidence. Its invocation or
batch latency cannot establish:

- PRE superiority or inferiority;
- IN superiority or inferiority;
- capacity or saturation;
- production throughput;
- a rate limit or safe concurrency limit;
- an SLO; or
- a connection-pool or production worker recommendation.

The smoke establishes only live correctness and topology viability for
proceeding to the next PR7 experiment gate.

### 19.7 Next authorized gate

The accepted smoke plus completed human release-skew review authorizes work on
the canonical Level-C evidence and persistence boundary. It does not authorize
the canonical Level-C PostgreSQL execution.

Canonical execution still requires:

- evidence schema and persistence implementation;
- deterministic validation of that boundary;
- clean committed source; and
- a separate explicit human execution authorization.

## 20. Canonical Level-C Evidence and Persistence Contract

This section defines the evidence boundary authorized by the accepted smoke
checkpoint. It authorizes future implementation of closed serialization,
valid-only durable publication, exact source and schedule lineage,
deterministic aggregate publication, and immediate read-back verification for
already-defined canonical Level-C observations.

It does not change runtime semantics, worker levels, workload families,
compositions, cohort vocabulary, phase matrices, timing boundaries, or the
seed-73 canonical schedule. It does not execute PostgreSQL, authorize the
canonical run, choose a strategy, or derive capacity, saturation, an SLO, or a
rate limit.

### 20.1 Distinct immutable namespace

One future canonical Level-C run publishes beneath:

```text
experiments/stage4b2/evidence/
stage4b2-pr7-canonical-levelc/
<run_id>/
```

This namespace is distinct from PR6 canonical evidence, post-PR6 supplemental
Layer 1/2/3 evidence, and PR7 PostgreSQL smoke diagnostics. Smoke diagnostics
never enter this directory.

The final `<run_id>/` directory is immutable after publication. A publisher
must fail closed when that directory already exists; it never overwrites,
merges into, deletes, or repairs an existing canonical run directory.

### 20.2 Exact published file set

A successfully published run directory contains exactly these six files:

```text
manifest.json
invocations.jsonl
batches.jsonl
ownership.json
invocation_aggregates.json
batch_rate_aggregates.json
```

No checksum sidecar, completion marker, diagnostic log, skew-score file,
exception file, hidden result file, or other artifact belongs to the canonical
contract. Hidden same-parent staging state is an implementation detail and
must not remain after successful publication.

### 20.3 Closed sanitized manifest

`manifest.json` is one closed JSON object with exactly these fields:

| Field | Required value or meaning |
| --- | --- |
| `schema_name` | `stage4b2-pr7-canonical-levelc-evidence` |
| `schema_version` | `1` |
| `run_id` | exact canonical experiment-local run identity |
| `source_commit` | one full Git commit identity |
| `source_tree_clean_before_run` | `true` |
| `schedule_identity` | `stage4b2-pr7-seed73-levels1-2-4-8-cells16-warmup3-recorded30` |
| `recorded_schedule_seed` | `73` |
| `retained_worker_levels` | `[1, 2, 4, 8]` |
| `exact_cell_count` | `16` |
| `warmup_batches_per_exact_cell` | `3` |
| `recorded_batches_per_exact_cell` | `30` |
| `expected_recorded_batch_count` | `480` |
| `expected_recorded_invocation_count` | `1800` |
| `expected_ownership_count` | `15` |
| `clock_identity` | `time.perf_counter_ns` |
| `postgresql_server_version` | sanitized server-version identity |
| `transaction_isolation` | sanitized transaction-isolation identity |
| `autocommit` | observed boolean fact |
| `topology_label` | sanitized runtime topology label |
| `validation_status` | `VALID` |
| `smoke_source_commit` | `8dcfbdc1e1bc4cca8a8e7c48a73126a40ec9c958` |
| `smoke_run_id` | `stage4b2-pr7-postgres-smoke-8dcfbdc` |
| `smoke_release_skew_review` | `ACCEPTED` |
| `publication_rule` | `VALID_ONLY_ATOMIC_IMMUTABLE_DIRECTORY` |

The three smoke fields establish experiment-gate lineage only. Smoke timing,
invocations, batches, cohorts, and aggregates do not enter canonical evidence.

The manifest never retains `TEST_DATABASE_URL`, a DSN, host, port, database
name, username, credentials, environment-variable values, raw connection
objects, or endpoint identity.

### 20.4 `invocations.jsonl`

`invocations.jsonl` contains exactly `1800` recorded canonical invocations.
Each UTF-8 line is one closed serialization of the already-frozen
`InvocationRecord` and contains exactly:

```text
schema_name
schema_version
run_id
invocation_index
cell_index
batch_index
lane_index
connection_slot
worker_level
workload_family
composition
external_elapsed_ns
start_offset_ns
producer_outcome
rejection_stage
stream_admission_verdict
append_admission_verdict
cohort
measurement_availability
phases
exception_type
```

Each `phases` value preserves all thirteen ordered records with only `name`,
`state`, and `elapsed_ns`. Warmup invocations never enter the file. Every line
uses the manifest run ID and the exact recorded invocation index, cell, batch,
lane, connection slot, worker level, workload family, composition, outcome,
verdicts, cohort, measurement availability, external elapsed, start offset,
and phase evidence already produced by the runtime.

For a publishable `VALID` run:

```text
unexpected exception count
= 0
```

`exception_type` therefore remains `null` in publishable canonical records;
the closed field remains present because it belongs to the frozen record
schema. The file does not add `request_id`, `order_id`, credentials, endpoint
identity, `attempt_id`, or `execution_id`.

### 20.5 `batches.jsonl`

`batches.jsonl` contains exactly `480` recorded `BatchRecord` entries. Warmup
batches never enter the file. Each UTF-8 line contains exactly:

```text
schema_name
schema_version
run_id
batch_record_index
cell_index
batch_index
worker_level
workload_family
composition
release_reference_ns
first_start_offset_ns
last_start_offset_ns
batch_elapsed_ns
completed_count
accepted_count
typed_outcome_counts
```

Each `typed_outcome_counts` value preserves only exact sorted `outcome` and
`count` pairs. Canonical release skew remains derivable per batch as:

```text
release_skew_ns
= last_start_offset_ns - first_start_offset_ns
```

No stored or derived field assigns a universal release-skew pass/fail
threshold.

### 20.6 `ownership.json`

`ownership.json` is one closed JSON array containing exactly the fifteen
canonical `LaneOwnershipRecord` observations:

```text
1 + 2 + 4 + 8
= 15
```

Every array entry contains exactly:

```text
worker_level
lane_index
connection_slot
thread_id
```

`thread_id` is experiment-local observed thread identity. The file proves the
fixed lane, thread, and connection-slot ownership of this run; it contains no
connection object, server endpoint, credential, or external governance
identity.

### 20.7 `invocation_aggregates.json`

`invocation_aggregates.json` is one closed JSON array generated only from the
complete raw `InvocationRecord` sequence through the existing canonical
`aggregate_invocations(...)` function. Array order is the deterministic tuple
order returned by that function. The publisher does not duplicate, reorder,
or reinterpret its grouping logic.

Every aggregate group remains exact:

```text
worker level
× workload family
× composition
× typed cohort
```

`SAME_ORDER_HOT_STREAM` is never pooled with
`DIFFERENT_ORDER_GENERAL_CONCURRENCY`. `ACCEPTED`, `APPEND_STALE_WRITE`, and
`PREPARE_LOCK_TIMEOUT` are never pooled with one another.

Each closed aggregate entry contains:

- `run_id`;
- `worker_level`;
- `workload_family`;
- `composition`;
- exact `cohort`;
- `external_elapsed_ns`; and
- `phases`, containing independent statistics only for actually `MEASURED`
  phases.

`phases` is an ordered array of closed objects containing exactly
`phase_name` and `statistics_ns`. Its order is the existing PR3 phase order
returned by `aggregate_invocations(...)`.

Every descriptive-statistics object contains exactly:

```text
count
minimum
maximum
mean
median
```

There is no p95, summed-phase metric, generic rejection score, generic PRE or
IN score, strategy winner, or cross-family/cohort aggregate.

### 20.8 `batch_rate_aggregates.json`

`batch_rate_aggregates.json` is one closed JSON array generated only from the
complete raw `BatchRecord` sequence through the existing canonical
`aggregate_batch_rates(...)` function. Array order is the deterministic tuple
order returned by that function. The publisher does not duplicate, reorder,
or reinterpret its grouping logic. The array contains exactly sixteen groups,
one per exact:

```text
worker level
× workload family
× composition
```

Each closed group contains:

- `run_id`;
- `worker_level`;
- `workload_family`;
- `composition`;
- `accepted_completion_rate_per_second`; and
- `all_completion_rate_per_second`.

Each completion-rate field contains exactly `count`, `minimum`, `maximum`,
`mean`, and `median`, with `count = 30`. Names and interpretation remain
protocol-qualified synchronized-burst completion rates. They are not
production throughput, arrival capacity, rate limits, SLOs, or production
admission settings.

### 20.9 Canonical release-skew evidence

The contract creates no separate skew score or skew artifact. Canonical
release-skew interpretation is derived from `invocations.jsonl` plus
`batches.jsonl`, which preserve start offsets, invocation elapsed values,
first and last start offsets, and batch elapsed.

These raw observations support later human review of start-offset
distributions, batch release-skew distributions, and release skew relative to
invocation and batch duration. No universal numeric threshold is introduced.
Human review remains required, and material harness domination may still stop
canonical interpretation.

### 20.10 Valid-only publication gate

The future publisher may construct canonical payloads only after all of these
conditions hold:

- `source_commit` is one known full Git identity;
- the source tree was clean before execution;
- the schedule equals the exact seed-73 canonical schedule;
- runtime validation status is `VALID`;
- recorded batch count is exactly `480`;
- recorded invocation count is exactly `1800`;
- ownership count is exactly `15`;
- there is no missing, duplicate, or unplanned invocation or batch;
- every observed cohort is supported;
- every `DIFFERENT_ORDER_GENERAL_CONCURRENCY` invocation is `ACCEPTED`;
- every invocation has `AVAILABLE` required measurement;
- all thirteen phases exist exactly once and match the frozen matrix;
- unexpected exception count is zero;
- every recorded batch has `completed_count = worker_level`;
- lane, thread, and connection-slot ownership is exact;
- `aggregate_invocations(...)` succeeds;
- `aggregate_batch_rates(...)` succeeds and returns exactly sixteen groups;
  and
- accepted smoke source, run, and release-skew-review lineage is present.

Failure of any gate means no canonical evidence file or final run directory is
published. There is no sample replacement, run extension, alternate run ID,
partial canonical publication, or outcome-sensitive rerun.

### 20.11 Valid-only atomic publication

Future implementation must publish one already-complete valid result with this
exact sequence:

1. validate the full run and construct all six complete payloads in memory;
2. confirm that the final `<run_id>/` directory does not exist;
3. create one hidden staging directory in the same parent as the final run
   directory;
4. exclusively create each of the six expected files;
5. fully write, flush, and `fsync` every file;
6. `fsync` the staging directory;
7. atomically rename the complete staging directory to `<run_id>/`; and
8. `fsync` the canonical evidence root.

A pre-validation failure writes nothing. A staging or partial-write failure
must leave no visible final run directory and must clean up only its own hidden
staging state. A successful publication leaves no staging state. Existing
final run directories remain immutable and are never overwritten.

Publication failure does not authorize retry, replacement, extension, or a
second PostgreSQL canonical execution.

### 20.12 Immediate read-back and recomputation

The same future execution workflow must immediately read the final run
directory back after atomic publication. Acceptance requires:

- exactly the six contract filenames and no others;
- parsed manifest equality with the in-memory manifest;
- exactly `1800` invocation lines;
- exactly `480` batch lines;
- exactly `15` ownership entries;
- one consistent manifest and raw-record run ID;
- reconstruction and canonical validation status `VALID`;
- published invocation aggregates equal a fresh
  `aggregate_invocations(...)` recomputation from read-back raw invocations;
- published batch-rate aggregates equal a fresh
  `aggregate_batch_rates(...)` recomputation from read-back raw batches;
- exactly sixteen recomputed batch-rate groups; and
- no secret, environment-variable value, credential, raw connection, database
  identity, or endpoint identity anywhere in the six files.

A read-back failure stops acceptance for human review. It does not authorize a
second PostgreSQL canonical run, mutation of the immutable final directory, or
publication under an alternate run ID.

### 20.13 Canonical execution authorization boundary

This contract authorizes only future implementation of the canonical evidence
writer and read-back boundary. It does not authorize canonical PostgreSQL
execution, a human-operated canonical runner, evidence generation from
PostgreSQL, another smoke, different worker levels, or different sample
counts.

The canonical run still requires, in order:

1. evidence writer implementation;
2. deterministic writer and read-back tests;
3. committed clean source;
4. a separately reviewed one-shot canonical runner; and
5. separate explicit human execution authorization.

### 20.14 Future rate-admission boundary

Canonical Level-C evidence may later become one empirical input to future
load-admission or rate-limiting work. This persistence contract does not derive
a rate limit, safe concurrency setting, capacity, saturation point, SLO, or
strategy selector.
