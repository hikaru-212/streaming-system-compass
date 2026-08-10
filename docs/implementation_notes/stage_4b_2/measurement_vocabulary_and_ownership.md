# Stage 4B.2 — Measurement Vocabulary and Ownership

[← Back to Stage 4B.2](README.md)

## Current Status

```text
Stage 4A
= COMPLETE

Stage 4B
= COMPLETE / CLOSED

Stage 4B.1
= COMPLETE / CLOSED

Stage 4B.2
= CURRENT FORMAL DEVELOPMENT STAGE

PR1
= documentation only

runtime measurement contract
= not implemented

runtime instrumentation
= not implemented

empirical strategy comparison
= not executed

bounded concurrency characterization
= not executed
```

This document is the current Stage 4B.2 PR1 planning authority. It supersedes
the historical pre-Stage-4B.1 draft wording in this same file.

PR1 documents responsibility, source-grounded candidate boundaries, empirical
goals, methodology constraints, deferrals, and the downstream PR sequence. It
does not claim that any timer, measurement contract, instrumentation, benchmark,
or performance result exists.

## 1. Responsibility

Stage 4B.1 answered:

```text
What happened during one supported producer execution?
```

Stage 4B.2 answers:

```text
What did that execution strategy cost?
```

The Stage 4B.2 responsibility is more specific than defining vocabulary for a
future strategy selector. It is:

```text
exact per-execution measurement semantics
+ producer-specific write-side measurement evidence
+ controlled PostgreSQL strategy comparison
+ bounded concurrency / contention characterization
```

The stage is evidence-producing and descriptive. It does not decide whether a
strategy is semantically acceptable and does not select or switch strategies.

```text
semantic acceptability
!= measurement evidence

measurement evidence
!= experiment aggregate

experiment aggregate
!= runtime decision

runtime decision
!= execution strategy

measured latency
!= retry authorization

bounded concurrency evidence
!= production rate-limit policy
```

The [Stage 4B.1 closeout](../stage_4b_1/stage_4b_1_closeout.md) is the accepted
predecessor authority. It hands off PR4's executable PostgreSQL topology, PR5's
producer-specific checkpoint vocabulary, and PR6's shared traced/untraced write
algorithms without defining timing or cost evidence.

## 2. Three Evidence Levels

### Level A — Single-Execution Measurement Evidence

Level A records factual elapsed evidence for work actually performed by one
normal-returning PostgreSQL write execution.

Conceptually:

```text
one execution
→ explicitly bounded work
→ elapsed evidence for reached phases
```

The first Level-A owner should remain:

```text
producer-specific
+ in memory
+ PostgreSQL write-side first
```

PR1 does not freeze a class name. In particular, it does not create a generic
repository-wide `MeasurementEvidence` abstraction.

### Level B — Controlled Strategy Comparison

Level B collects multiple Level-A observations under matched PostgreSQL
conditions and compares:

```text
PRE_TRANSACTION + optimistic append-time admission
vs
IN_TRANSACTION + concrete pessimistic admission
```

Level B owns empirical observations such as sample counts, outcome-stratified
latency, and descriptive aggregates. Those aggregates are experiment-owned;
they are not fields of one execution's measurement artifact.

### Level C — Bounded Concurrency / Contention Characterization

Level C observes how the two current compositions behave as concurrent demand
increases in one recorded environment and workload.

It may examine:

```text
concurrency → accepted throughput
concurrency → all-completion throughput
concurrency → median / supported p95 latency
concurrency → typed rejection or non-acquisition rate
concurrency → business-UOW elapsed
concurrency → validation elapsed in non-accepted executions
concurrency → validation cost per accepted write
```

The result is a bounded local curve, not a universal capacity number. A visible
knee and no visible knee within the tested range are both valid observations.

## 3. Existing Evidence Ownership

The current separation remains:

```text
PostgresWriteSideResult
= terminal producer result and nested typed evidence

PostgresWriteSideExecutionTrace
= what happened and which bounded topology was traversed

Level-A measurement evidence
= how long explicitly bounded work actually performed took

Level-B / Level-C artifact
= multi-execution controlled experiment samples and aggregates

SemanticOutcome
= shared semantic interpretation

DecisionReceipt
= compact durable governance evidence
```

`PostgresWriteSideExecutionTrace` remains unchanged. Its `*_RETURNED`
checkpoints prove only that a bounded operation returned normally. They are not
timers and do not prove lock acquisition, durability, commit, retry safety, or
semantic meaning.

Therefore:

```text
DiagnosticTrace checkpoint boundary
!= automatically a measurement timing boundary
```

Some candidate timers align with the same calls observed by a checkpoint. Other
measurements require an earlier start, a later stop, or instrumentation above or
below the checkpoint owner. No Stage 4B.2 timing belongs inside the trace.

## 4. Current PostgreSQL Write Compositions

### 4.1 PRE_TRANSACTION + Optimistic Append-Time Admission

The successful current ordering is:

```text
preliminary idempotency check
→ accepted-history load
→ preliminary read-transaction rollback / cleanup
→ aggregate rehydration
→ validation-context construction
→ candidate construction
→ validation outside the business UOW
→ business UOW entry
→ authoritative idempotency check
→ optimistic concurrency preparation
→ append-time version / continuity / insertion arbitration
→ idempotency record insertion
→ clean UOW finalization
→ ACCEPTED return
```

The preliminary read and authoritative business UOW are phases of one execution,
not separate attempts.

### 4.2 IN_TRANSACTION + Concrete Pessimistic Admission

The successful current ordering is:

```text
business UOW entry
→ authoritative idempotency check
→ nonblocking transaction-scoped advisory try-lock
→ accepted-history load while protection may exist
→ aggregate rehydration
→ validation-context construction
→ candidate construction
→ validation inside the business UOW
→ append admission
→ idempotency record insertion
→ clean UOW finalization and advisory-lock release
→ ACCEPTED return
```

The concrete pessimistic preparation uses
`pg_try_advisory_xact_lock(...)`. It returns acquired or not acquired; the
current implementation does not block waiting for that advisory lock to become
available.

Validation placement and admission-gate construction remain independent axes.
Current source does not define one stable public strategy enum for the two
compositions, and Stage 4B.2 does not invent one merely to label measurements.

## 5. Characterized Candidate Measurement Vocabulary

The following vocabulary is source-grounded candidate design pending PR2
executable measurement-mechanics characterization. It is not a frozen PR3
dataclass or unit representation.

### 5.1 First Producer-Measurement Candidates

| Candidate | Candidate boundary | Reach / comparison qualification |
|---|---|---|
| Whole write invocation | Measurement-enabled public API entry through normal return after current UOW finalization. Final measurement-artifact construction overhead and exception-path delivery require PR2 characterization. | Both compositions. Compare only the same API surface, command/data shape, validator, and outcome cohort. |
| Business-UOW lifecycle | Successful `PostgresWriteSideUnitOfWork` entry through current context exit after commit, rollback, or already-completed finalization. | Both when reached. This is an application UOW boundary, not exact server-side physical transaction lifetime. |
| Validation-runtime call | `ValidationRuntime.decide(...)` entry through `ValidationDecision` return. | Both when validation is reached. This is distinct from validator-local timing. |
| Existing validator-local total | Existing built-in validator entry through the validator's final timer read before `ValidationResult` construction. | Reuse its current meaning; do not add a second timer that silently claims the same boundary. |
| Preliminary idempotency check | PRE preliminary `PostgresIdempotencyStore.check(...)` entry through typed decision return. | PRE only; explanatory, not a like-for-like cross-strategy phase. |
| Preliminary read rollback / cleanup | PRE preliminary `connection.rollback()` call entry through normal return. | PRE only; closes the implicit read transaction before CPU-side validation or return. |
| Authoritative idempotency check | Business-UOW `PostgresIdempotencyStore.check(...)` entry through typed decision return. | Both when reached; compare matched idempotency state. |
| Accepted-history load | `PostgresEventStore.load(...)` entry through hydrated history-list return. | Both when reached; compare matched history depth. Includes database, client/network, fetch, and row hydration work. |
| Concurrency-preparation call | `prepare_stream(...)` entry through `StreamAdmissionResult` return. | Both when reached. Optimistic preparation is currently local; pessimistic preparation includes SQL. |
| Concrete pessimistic advisory try-lock call | Concrete `_try_lock_stream(...)` entry through acquired/not-acquired boolean return. | IN + concrete pessimistic only; contained by concurrency preparation and stratified by acquired/not acquired. |
| Append-admission call | `append_if_admitted(...)` entry through typed `AdmissionResult` return. | Both when reached. Includes current-version observation, continuity checks, INSERT attempt, selected failure translation, and possible database arbitration; excludes commit. |
| Idempotency-record call | `PostgresIdempotencyStore.record(...)` entry through normal return. | Both after admitted append. The transaction-local INSERT call returning does not prove committed durability. |
| Commit / rollback finalization | Concrete UOW `commit()` or `rollback()` call entry through normal return. | Compare commit with commit and rollback with rollback. Post-UOW delivery and propagating failures remain PR2 questions. |

### 5.2 Lower-Priority Experiment Detail

The following CPU-side boundaries may be useful to explain an observed
difference but are not first-contract requirements in PR1:

- aggregate rehydration;
- validation-context construction; and
- candidate construction.

They should be promoted into a production producer contract only if PR2 or the
controlled experiments demonstrate that the detail is material and stable.

### 5.3 Containment and Overlap

The candidate durations are not independent buckets:

```text
whole invocation
contains
business UOW when reached

business UOW
contains for both PRE_TRANSACTION and IN_TRANSACTION
authoritative idempotency
+ concurrency preparation
+ append admission
+ idempotency record
+ finalization

business UOW
additionally contains for IN_TRANSACTION
accepted-history load
+ aggregate rehydration / validation-context construction / candidate construction
+ validation-runtime call

concurrency preparation
contains
concrete pessimistic advisory try-lock where applicable

validation-runtime call
contains
validator-local elapsed
```

Consequently, Stage 4B.2 must not blindly sum all fields and present the result
as a decomposed total. PR2/PR3 must document nesting and any residual clearly.

## 6. Existing Validator Timing Reality

`ValidationResult` currently contains:

```text
logic_validation_time_ms: float
io_time_ms: float
total_time_ms: float
```

The two built-in validators use `time.perf_counter()` internally.

For `FullProofValidator`:

- `logic_validation_time_ms` measures local Python validation logic through the
  terminal validation branch or successful final check, before result and
  metadata construction;
- `io_time_ms` is currently fixed at `0.0`; and
- `total_time_ms` measures validator-local entry through its final timer read,
  before `ValidationResult` construction.

For `NoOpValidator`, `logic_validation_time_ms` and `io_time_ms` are fixed at
`0.0`, while `total_time_ms` is the elapsed interval between two adjacent
validator-local clock reads.

The exact boundary is:

```text
ValidationResult.total_time_ms
= validator-local elapsed evidence

NOT
= full ValidationRuntime.decide(...) elapsed
```

It excludes at least:

- dispatcher selection;
- policy mapping;
- `ValidationDecision` construction;
- accepted-history loading;
- aggregate rehydration;
- validation-context construction; and
- candidate construction.

A future `validation_runtime_decide_call_elapsed` is therefore a distinct
candidate measurement. It must not rename or reinterpret the existing validator
field.

Current write-side results retain the nested `ValidationDecision` in memory on
normal-return paths where validation was reached. That retention is not durable
measurement persistence and does not make the mutable nested result an immutable
Stage 4B.2 contract.

Stage 4B.1 write-side characterization and traced-execution tests use synthetic
`0.0` validation timings. Those tests establish topology and contract behavior,
not real performance evidence.

## 7. Absence Semantics

Stage 4B.2 freezes the semantic distinction:

```text
phase not applicable
!= phase applicable but not reached
!= measurement not collected
!= measured duration equal to zero
```

PR1 does not freeze the exact dataclass representation. PR2 must characterize
the reachable cases, and PR3 must choose the immutable representation.

Numeric zero must never be used as the universal missing-value sentinel. A true
zero clock delta, including one created by timer resolution, remains a measured
value.

## 8. Naming Rules

### 8.1 Advisory Try-Lock Call, Not Lock Wait

The current pessimistic gate executes:

```sql
SELECT pg_try_advisory_xact_lock(...)
```

Therefore:

```text
pessimistic advisory try-lock call elapsed
!= lock wait
```

Candidate wording should be equivalent to:

```text
pessimistic_advisory_try_lock_call_elapsed
```

Do not populate or reinterpret `DecisionReceiptCostSummary.lock_wait_ms` for the
current mechanism.

### 8.2 Business UOW, Not Exact Physical Transaction Lifetime

`PostgresWriteSideUnitOfWork.__enter__()` checks configuration but does not issue
an explicit `BEGIN`. The first database statement may open the physical
transaction.

Use wording equivalent to:

```text
business_uow_elapsed
```

Do not call that application lifecycle exact PostgreSQL transaction lifetime.

### 8.3 Append Admission, Not Pure OCC or Pure DB Append

The append-admission boundary includes current-version observation, local
continuity checks, an INSERT attempt, driver/client work, and selected error
translation. Under contention it may also contain PostgreSQL stream-position
arbitration.

Use wording equivalent to:

```text
append_admission_call_elapsed
```

Do not call it pure OCC time or pure database append time.

### 8.4 Invocation, Not Attempt

One current `create_order(...)` or `pay_order(...)` call is one invocation or
execution. Multiple-invocation retry and intent relationships belong to later
Stage 4E governance.

Use invocation terminology rather than:

```text
total_attempt_elapsed
```

### 8.5 Factual PRE-Before-Stale Evidence, Not Universal Waste

Stage 4B.2 may derive:

```text
PRE validation elapsed
+ later returned append STALE_WRITE
```

That is factual observed evidence. It does not prove one exact OCC root cause
for every translated `STALE_WRITE` form and does not establish the policy
judgment that the validation was universally wasted.

## 9. Historical Accepted-Event Metadata Seam

The original write-side schema created `metadata_json` and reserved it for
possible future non-domain runtime metadata, including validation and
registry-stage timing.

Current production source does not populate timing there:

```text
payload_json
= {}

metadata_json
= {}
```

Current event hydration also reconstructs the domain `OrderEvent` rather than a
stored-event evidence record containing `metadata_json`.

The boundary remains:

```text
validator timing exists
!= durable timing exists

metadata_json exists
!= measurement is currently persisted

historical reservation
!= accepted Stage 4B.2 persistence ownership
```

Accepted-event metadata is not the initial Stage 4B.2 sink. It can represent
only executions that produced an accepted event and would omit important
measurement cohorts, including:

- append `STALE_WRITE` rejection;
- pessimistic advisory non-acquisition;
- validation block; and
- other typed non-accepted results.

Using accepted-event metadata alone would bias the observable sample set toward
accepted writes. Whole-invocation and commit/finalization measurements also
become complete after the event INSERT boundary.

PR1 explicitly defers accepted-event timing persistence. It does not modify the
schema, migration 001, event-store APIs, or event hydration.

## 10. DecisionReceipt Boundary

`DecisionReceiptCostSummary` already provides nullable compact fields:

```text
elapsed_ms
validation_elapsed_ms
replay_elapsed_ms
transaction_elapsed_ms
lock_wait_ms
```

The generic mapper can accept an explicitly supplied summary, and the durable
receipt store can persist one. Current write-side and read-side producer mappers
do not supply cost measurements; producer-created receipts contain an empty
summary.

Therefore:

```text
storage capability
!= current producer population
!= Stage 4B.2 detailed-measurement ownership
```

The current Stage 4B.2 PR1–PR8 sequence does not modify or automatically
populate `DecisionReceipt`. Detailed measurements remain transient initially.

A future compact durable projection requires a concrete governance consumer and
separate approval of:

- exact field semantics;
- unit and precision;
- conversion and rounding;
- absence semantics;
- producer ownership; and
- why the value is governance evidence rather than experiment or diagnostic
  evidence.

## 11. Controlled PostgreSQL Strategy Comparison

Vocabulary alone is not Stage 4B.2 completion.

The intended progression is:

```text
exact measurement semantics
→ producer-specific measurement contract
→ runtime instrumentation
→ correctness validation
→ real PostgreSQL PRE/OCC vs IN/pessimistic comparison
→ bounded concurrency / contention characterization
→ documented limitations
```

### 11.1 First Controlled Comparison

The Level-B core should include:

```text
A — uncontended accepted baseline

B — same-order competition

C — different-order concurrency
```

Mechanism-explanation scenarios should also be pursued when cleanly supportable:

```text
D — PRE validation followed by returned STALE_WRITE

E — pessimistic advisory try-lock non-acquisition
```

D and E must not require production-semantic changes or measurement-contaminating
coordination merely to manufacture samples.

Scenario F compares current cheap validation with a deliberately more expensive,
clearly labeled experiment-only validator workload. It belongs later in Stage
4B.2 after measurement correctness, and it must distinguish CPU-bound work from
sleep or I/O-like delay.

Idempotent replay remains outside the first strategy-comparison core unless
later human review promotes it. Replay must never be converted into a
counterfactual `avoided_work_ms` value from one invocation alone.

### 11.2 Outcome-Stratified Evidence

Level-B reporting must keep separate:

- accepted results;
- append `STALE_WRITE` results;
- advisory non-acquisition results;
- validation-blocked results;
- replay or conflict results when later included; and
- any unexpected propagating exception that invalidates a comparison cohort.

One mixed mean across those paths can make a strategy appear faster merely
because it rejects more work earlier.

### 11.3 Environment-Scoped Claims

Stage 4B.2 may conclude:

```text
under this recorded PostgreSQL environment, API surface, workload,
contention pattern, and sample protocol,
composition A exhibited X and composition B exhibited Y
```

It must not conclude:

```text
A is universally better

B should always be selected

the production rate limit should be X
```

## 12. Fair-Comparison Methodology Boundary

PR1 records methodological requirements without claiming that the experiment
has run.

A valid comparison holds relevant factors constant, including:

- PostgreSQL instance, version, schema, and migrations;
- API measurement surface;
- command type and domain-data shape;
- actual injected validation runtime, validator, and mode;
- isolation assumptions;
- connection creation, preparation, and reuse policy;
- history depth where the phase comparison requires it;
- warmup and setup/cleanup exclusion;
- same-order versus different-order stream mapping;
- iteration protocol; and
- balanced or seeded strategy execution ordering.

Current legacy and traced APIs are different surfaces: traced calls create a
collector and execution envelope, while legacy calls do not.

Therefore:

```text
measured PRE vs measured IN
= legitimate

traced PRE vs traced IN
= legitimate when explicitly labeled

traced PRE vs untraced IN
= invalid comparison
```

The preferred empirical surface is one equivalent measurement-enabled surface
for both compositions without optional DiagnosticTrace construction. PR3/PR4
must decide and implement that surface; PR1 does not name its API.

PR1 does not freeze sample counts, worker counts, or a performance threshold.
Those values belong to a recorded experimental protocol after the environment
and connection budget are known.

## 13. Bounded Concurrency and Future Rate Admission

The intended relationship is:

```text
Stage 4B.1
→ execution topology

Stage 4B.2 Level A
→ one execution's bounded cost

Stage 4B.2 Level B
→ controlled strategy comparison

Stage 4B.2 Level C
→ bounded concurrency / contention curves

future capacity engineering
→ database, connection, resource, contention, and arrival model

future rate limiting / load admission
→ policy
```

Candidate planning levels may include:

```text
1, 2, 4, 8
```

but PR1 does not freeze them. Current source proves only a small direct-connection
concurrency harness and does not define a production connection-pool or capacity
budget. PR7 must preflight and record its environment, then stop increasing
concurrency when the connection budget, harness, or environment ceases to support
a fair cell.

PR7 must distinguish:

```text
same-order hot-stream contention
!= different-order general database concurrency
```

The purpose is to observe whether the recorded environment has a region where:

```text
additional concurrency
→ little additional useful throughput
+ rapid latency or contention growth
```

Do not derive:

```text
rate_limit = 1 / mean_latency
```

Future capacity policy may depend on connection limits, pool size, CPU, I/O,
database saturation, hot-key distribution, arrival distribution, transaction
duration, typed conflict rates, and p95/p99 or SLO requirements.

## 14. Timing Methodology Direction

The current recommendation for new Stage 4B.2 elapsed collection is:

```text
clock
= monotonic elapsed-time source

candidate clock API
= time.perf_counter_ns()

candidate internal representation
= integer nanoseconds

human / report representation
= milliseconds

rounding
= presentation boundary only
```

This is planning direction, not an implemented contract.

The existing `ValidationResult.total_time_ms` remains unchanged as
float-millisecond validator-local evidence. It is not converted for aesthetic
uniformity.

PR2/PR3 must still decide:

- exact clock seam and injection method;
- internal and public units;
- precision and rounding;
- treatment of sub-millisecond values;
- immutable representation;
- absence representation; and
- post-UOW delivery.

## 15. Post-UOW Delivery Is a Blocking PR2 Question

The current traced write-side APIs follow the producer-specific ADR 0022
fail-closed rule:

```text
valid Result + valid Trace + valid Execution
must exist before clean business-UOW exit
```

That trace decision does not automatically govern measurement evidence.

Important Stage 4B.2 values become complete only after finalization:

- business-UOW elapsed;
- whole-invocation elapsed; and
- commit or rollback finalization elapsed.

Therefore:

```text
measurement delivery failure semantics
!= automatically ADR 0022 trace failure semantics
```

PR2 must characterize how post-UOW measurement can be delivered without:

- masking a committed business success;
- changing commit or rollback behavior;
- catching previously propagating exceptions;
- rewriting primary result semantics;
- weakening traced-API guarantees; or
- introducing a generic exception-carried evidence mechanism.

PR3 must not freeze the immutable contract until this question is resolved.

## 16. Aggregate Experiment Ownership

Multi-execution results belong to an experiment-owned artifact, not to:

- `PostgresWriteSideExecutionTrace`;
- one execution's measurement evidence;
- `PostgresWriteSideResult`;
- `SemanticOutcome`; or
- `DecisionReceipt`.

The later bounded experiment may own:

- raw per-execution samples;
- outcome and workload cohort labels;
- sanitized environment and method metadata;
- sample counts;
- mean, median, observed minimum/maximum;
- p95 only where the protocol supplies an adequate sample size;
- accepted and all-completion throughput; and
- limitations and interpretation.

No latency threshold belongs in ordinary correctness tests, and no production
aggregate-performance contract is introduced without a consumer.

## 17. PR Sequence

The accepted Stage 4B.2 sequence is:

```text
PR1 — Measurement Evidence Responsibility Boundary
PR2 — Measurement Mechanics Characterization
PR3 — PostgreSQL Write Measurement Contract
PR4 — PostgreSQL Write Measurement Instrumentation
PR5 — Measurement Correctness Validation
PR6 — Controlled PostgreSQL Strategy Comparison
PR7 — Bounded Concurrency Characterization
PR8 — Stage 4B.2 Closeout
```

Detailed responsibilities, branches, dependencies, non-goals, and stop
conditions live in the [Stage 4B.2 PR Breakdown](pr_breakdown.md).

The evidence-first sequence is:

```text
documentation
→ executable measurement-mechanics characterization
→ immutable producer contract
→ production instrumentation
→ correctness validation
→ empirical strategy evidence
→ bounded concurrency evidence
→ closeout
```

PR1 does not begin PR2.

## 18. Explicit Non-Goals

Stage 4B.2 PR1 does not authorize:

- production timing instrumentation;
- measurement contract implementation;
- performance, load, or concurrency experiment execution;
- latency thresholds or performance claims;
- production benchmark infrastructure or a continuous regression service;
- rate limiting, token buckets, leaky buckets, or load-admission policy;
- autoscaling, SLO definition, or production capacity claims;
- connection-pool redesign;
- `DiagnosticTrace` timing fields or trace persistence;
- `DecisionReceipt` cost population, redesign, or persistence changes;
- accepted-event timing metadata persistence;
- migrations or schema changes;
- Prometheus, Grafana, OpenTelemetry, dashboards, or a metrics backend;
- generic telemetry infrastructure;
- a production load generator or distributed benchmark cluster;
- runtime strategy selection or automatic OCC/pessimistic switching;
- retry governance, `AttemptLog`, `execution_id`, or `attempt_id`;
- generic exception capture;
- same-execution provenance hardening;
- read-side measurement parity; or
- snapshot benchmark expansion.

A small bounded Stage 4B.2 experiment harness in PR6/PR7 is distinct from
production benchmark or observability infrastructure.

## 19. Stop Conditions

Stop and request human review if downstream Stage 4B.2 work would:

- close the stage without real PostgreSQL strategy-comparison evidence;
- compare traced and untraced surfaces across strategy arms;
- add timing to `DiagnosticTrace`;
- automatically apply ADR 0022 trace failure behavior to measurement evidence;
- construct required evidence after commit in a way that can mask committed
  success;
- change current result, UOW, commit, rollback, or exception behavior;
- persist timing merely because `metadata_json` or receipt cost columns exist;
- use zero as a universal missing-value sentinel;
- call advisory try-lock duration lock wait;
- call business-UOW elapsed exact physical transaction lifetime;
- call append-admission duration pure OCC or pure database append time;
- use attempt terminology without retry-governance ownership;
- aggregate materially different terminal outcomes into one latency;
- conflate same-order contention with different-order concurrency;
- include experiment coordination, setup, cleanup, or connection creation in a
  claimed invocation boundary without explicit intent;
- freeze unsupported sample counts, worker counts, or capacity claims;
- infer a universal strategy choice or rate limit from bounded local evidence;
- require production telemetry, pooling, retry, policy, or persistence redesign;
  or
- add read-side measurement without a concrete consumer and separate review.

## 20. PR1 Completion Boundary

PR1 is complete when repository documentation establishes:

```text
Stage 4B.2 purpose
= measurement + bounded empirical evidence

DiagnosticTrace
!= measurement evidence

Level A
= one execution

Level B
= controlled PRE+OCC vs IN+pessimistic comparison

Level C
= bounded concurrency / contention characterization

measurement evidence
!= strategy decision

bounded concurrency evidence
!= production rate-limit policy
```

and when:

- candidate boundaries are source-grounded but not frozen as a PR3 dataclass;
- existing validator timing keeps its exact validator-local meaning;
- misleading timing names are rejected;
- historical `metadata_json` intent is documented but not adopted as the sink;
- `DecisionReceipt` remains unchanged and unpopulated by producers;
- post-UOW delivery remains an explicit PR2 blocker;
- PR2 through PR8 sequencing is reviewable;
- roadmap and navigation state identify Stage 4B.2 as current; and
- no runtime implementation or empirical result is claimed.
