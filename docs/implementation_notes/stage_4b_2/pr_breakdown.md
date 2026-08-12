# Stage 4B.2 PR Breakdown

[← Back to Stage 4B.2](README.md)

## Purpose

This note defines the implementation sequence for:

```text
Stage 4B.2 — Measurement Evidence
```

Stage 4B.1 established producer-specific execution-topology evidence. Stage
4B.2 adds a separate responsibility:

```text
Level A
= single-execution producer measurement

Level B
= controlled PRE+OCC vs IN+pessimistic comparison

Level C
= bounded concurrency / contention characterization
```

The stage produces descriptive evidence. It does not select an execution
strategy, authorize retry, define semantic acceptability, implement rate
limiting, or claim universal production capacity.

The PR1 responsibility authority is [Measurement Vocabulary and
Ownership](measurement_vocabulary_and_ownership.md). The final completion
authority is the [Stage 4B.2 Closeout](stage_4b_2_closeout.md).

## Current Status

```text
Stage 4B.1
= COMPLETE / CLOSED

Stage 4B.2
= COMPLETE / CLOSED

PR1
= COMPLETE / MERGED

PR2
= COMPLETE / MERGED

PR3
= COMPLETE / MERGED

PR4
= COMPLETE / MERGED

PR5
= COMPLETE / MERGED

PR6
= COMPLETE / MERGED

post-PR6 supplement
= COMPLETE / CLOSED / MERGED VIA PR #84

PR7
= COMPLETE / CLOSED / MERGED VIA PR #85

PR8
= COMPLETE / DOCUMENTATION CLOSEOUT
```

PR2 does not authorize or begin PR3.

## Stage Principle

Stage 4B.2 preserves:

```text
DiagnosticTrace
= what happened during one execution

measurement evidence
= how long explicitly bounded work actually performed took

one execution's measurement
!= multi-execution experiment aggregate

measurement
!= strategy decision

bounded concurrency evidence
!= production capacity or rate-limit policy
```

Detailed measurement remains producer-specific, in memory, and write-side first
until evidence from the current PostgreSQL producer justifies broader ownership.

## Branch Workflow

Stage 4B.2 uses the integration branch:

```text
feat/stage4b2-measurement-evidence
```

Each PR branch targets that integration branch. Only after Stage 4B.2 closeout
does the integration branch target:

```text
feat/stage4-runtime-semantic-governance
```

The planned branch sequence is:

```text
feat/stage4b2-measurement-evidence
├── docs/stage4b2-pr1-measurement-evidence-boundary
├── test/stage4b2-pr2-measurement-mechanics-characterization
├── feat/stage4b2-pr3-postgres-write-measurement-contract
├── feat/stage4b2-pr4-postgres-write-measurement-instrumentation
├── test/stage4b2-pr5-postgres-write-measurement-correctness
├── experiment/stage4b2-pr6-postgres-strategy-comparison
├── experiment/stage4b2-pr7-bounded-concurrency-characterization
└── docs/stage4b2-pr8-closeout
```

One PR may contain multiple commits, but each PR has one responsibility.

## Evidence-First Sequence

```text
documentation
→ deterministic measurement-mechanics characterization
→ immutable producer-specific contract
→ shared-path production instrumentation
→ measurement correctness validation
→ controlled empirical strategy comparison
→ bounded concurrency characterization
→ closeout
```

The PR3 contract must not be frozen before PR2 resolves the timer and delivery
questions. Performance conclusions must not precede PR4 instrumentation and PR5
correctness evidence.

---

## PR1 — Measurement Evidence Responsibility Boundary

### Branch

```text
docs/stage4b2-pr1-measurement-evidence-boundary
```

### Responsibility

```text
documentation only
```

### Purpose

Define the current Stage 4B.2 architecture and empirical completion boundary
without implementing or executing measurement.

### Deliverables

- Stage 4B.2 README / navigation entry point;
- current measurement responsibility and ownership authority;
- three evidence levels;
- source-grounded candidate measurement boundaries;
- containment and absence semantics;
- naming constraints;
- validator-timing reality;
- historical accepted-event metadata seam and persistence deferral;
- `DecisionReceipt` boundary;
- empirical goals and fair-comparison constraints;
- timing-methodology direction;
- post-UOW delivery question;
- explicit non-goals and stop conditions;
- PR2–PR8 sequence; and
- narrow roadmap / navigation alignment.

### Dependencies

- completed Stage 4B.1 PR4 PostgreSQL write-side characterization;
- completed Stage 4B.1 PR5 trace contract;
- completed Stage 4B.1 PR6 traced-execution integration;
- Stage 4B.1 closeout and ADR 0022; and
- current source, tests, accepted ADRs, and human direction.

### Non-Goals

- no production source or test implementation;
- no timer or measurement contract;
- no experiment runner or empirical result;
- no persistence, migration, schema, receipt, or trace change; and
- no policy, strategy, retry, capacity, or rate-limiting decision.

### Stop Condition

Stop if PR1 would need to claim an exact immutable field representation,
implemented timer, or performance conclusion without executable characterization.

---

## PR2 — Measurement Mechanics Characterization

### Branch

```text
test/stage4b2-pr2-measurement-mechanics-characterization
```

### Responsibility

```text
measurement-semantics characterization

NOT

performance benchmark
```

### Purpose

Use deterministic and fake-clock executable evidence to determine the exact
mechanics required before freezing the Level-A producer contract.

### Required Characterization

- timer start and stop behavior;
- nested timing boundaries;
- phase applicable versus not reached;
- measurement missing versus measured zero;
- commit and rollback finalization measurement;
- business-UOW and whole-invocation completion;
- post-UOW measurement delivery;
- measured and existing API semantic parity;
- normal-return evidence completeness; and
- preservation of currently propagating exceptions.

### Dependencies

- accepted PR1 responsibility and candidate-boundary documentation; and
- source-stable current PostgreSQL write algorithms and UOW behavior.

### Non-Goals

- no performance or latency comparison;
- no PostgreSQL load or contention experiment;
- no immutable production contract;
- no production instrumentation;
- no exception wrapping; and
- no receipt, trace, or persistence change.

### Stop Condition

Stop if measurement requires changing the current primary result, business UOW,
commit/rollback behavior, or exception propagation.

Stop if post-UOW delivery can mask committed business success or if ADR 0022's
trace-specific fail-closed semantics would have to be imported without a
separate measurement decision.

---

## PR3 — PostgreSQL Write Measurement Contract

### Branch

```text
feat/stage4b2-pr3-postgres-write-measurement-contract
```

### Responsibility

Define the immutable producer-specific Level-A contract justified by PR2.

### Implementation Status

Complete and merged. The delivered scope is the producer-specific immutable
phase, snapshot, availability, and result-first delivery contract with pure
unit tests. Production timer collection and measurement-enabled producer
methods remain owned by PR4.

### Required Decisions

- exact measurement fields;
- units and precision;
- clock-delta representation;
- presence and absence semantics;
- completeness semantics;
- containment and overlap semantics;
- post-UOW delivery semantics;
- result / measurement composition; and
- validation of immutable construction.

### Ownership Boundary

The first contract remains PostgreSQL write-side specific. It must not create a
generic repository-wide `MeasurementEvidence` abstraction merely for naming
convenience.

It remains separate from:

- `PostgresWriteSideExecutionTrace`;
- `PostgresWriteSideResult` field ownership;
- `SemanticOutcome`;
- `DecisionReceipt`; and
- multi-execution aggregate statistics.

### Dependencies

- accepted PR2 executable characterization; and
- resolved post-UOW delivery, unit, absence, and completeness semantics.

### Non-Goals

- no production instrumentation;
- no PostgreSQL performance experiment;
- no generic cross-producer abstraction;
- no stable strategy enum;
- no persistence or receipt projection; and
- no aggregate experiment contract.

### Stop Condition

Stop on any unresolved field boundary, unit, presence, overlap, construction, or
post-UOW delivery question.

---

## PR4 — PostgreSQL Write Measurement Instrumentation

### Branch

```text
feat/stage4b2-pr4-postgres-write-measurement-instrumentation
```

### Responsibility

Instrument the existing shared PostgreSQL write algorithms and expose equivalent
measurement-enabled surfaces for both current compositions:

```text
PRE_TRANSACTION + optimistic append-time admission

IN_TRANSACTION + concrete pessimistic admission
```

### Implementation Status

Complete and merged. The shared PRE and IN algorithms expose explicit legacy
and traced measurement-enabled surfaces while existing unmeasured APIs remain
valid. PR5 now owns source-boundary correctness validation.

### Required Implementation Boundary

- one invocation-local measurement owner;
- contract-compliant timers at accepted PR3 boundaries;
- equivalent measurement surface for both compositions;
- preservation of shared PRE and IN execution algorithms;
- legacy API behavior unchanged; and
- current result, UOW, trace, and exception semantics preserved.

### Dependencies

- accepted immutable PR3 contract.

### Non-Goals

- no aggregate experiment logic;
- no performance ranking;
- no DiagnosticTrace timing;
- no receipt population or event-metadata persistence;
- no policy or strategy selection; and
- no retry or exception redesign.

### Stop Condition

Stop if instrumentation changes business results, accepted-history authority,
commit/rollback, traced execution, exception behavior, or legacy API semantics.

---

## PR5 — Measurement Correctness Validation

### Branch

```text
test/stage4b2-pr5-postgres-write-measurement-correctness
```

### Responsibility

Prove the correctness of implemented Level-A measurement before interpreting
performance.

### Implementation Status

Complete and merged. Deterministic eight-case source-boundary, elapsed,
containment, collection-failure, and measured/unmeasured parity evidence is
complete. Real PostgreSQL accepted persistence, rollback, advisory try-lock
non-acquisition, and connection IDLE/reuse compatibility were also validated.
No production instrumentation defect was discovered.

The accepted PR5 evidence is the correctness foundation consumed by the
completed PR6 controlled comparison.

### Required Evidence

- exact boundary placement;
- correct phase presence and absence;
- expected units and non-negative elapsed representation;
- nesting and coherence;
- outcome-specific measurement presence;
- PRE and IN topology alignment;
- measured versus existing API semantic parity;
- commit / rollback and post-UOW behavior; and
- real PostgreSQL compatibility.

### Dependencies

- accepted PR4 instrumentation.

### Non-Goals

- no latency thresholds;
- no assertion that one strategy is faster;
- no benchmark framework;
- no concurrency saturation claim; and
- no policy or durable projection.

### Stop Condition

Stop if correctness can only be asserted through probabilistic wall-clock
thresholds or if measurement changes the existing producer behavior.

---

## PR6 — Controlled PostgreSQL Strategy Comparison

### Status

```text
PR6
= COMPLETE

Canonical run
= VALID

Recorded samples
= 450

Exceptions
= 0

Empirical report
= COMPLETE
```

The canonical evidence and descriptive interpretation are recorded in the
[PostgreSQL Strategy Comparison
Report](postgres_strategy_comparison_report.md). The result remains Level-B
environment-qualified evidence and does not select a production strategy.

### Branch

```text
experiment/stage4b2-pr6-postgres-strategy-comparison
```

### Responsibility

Obtain real empirical evidence comparing the current correctness-preserving
PostgreSQL write compositions under controlled matched workloads.

### Core Scenarios

```text
A — uncontended accepted baseline

B — same-order competition

C — different-order concurrency
```

### Mechanism-Explanation Scenarios

Pursue when they can be obtained without changing production semantics or
contaminating the claimed measurement boundary:

```text
D — PRE validation followed by returned STALE_WRITE

E — pessimistic advisory try-lock non-acquisition
```

D/E do not authorize production hooks, exception conversion, or artificial
delay inside reported timers merely to manufacture samples.

### Later Stage 4B.2 Sensitivity

Scenario F compares cheap validation with deliberately more expensive
experiment-only validation while preserving the same semantic outcome. It must
be clearly labeled and must distinguish CPU-bound work from delay or I/O-like
work.

Idempotent replay remains outside the first strategy-comparison core unless
later human review promotes it. No counterfactual `avoided_work_ms` is inferred.

### Fairness Requirements

Hold constant, where applicable:

- PostgreSQL instance, schema, and isolation assumptions;
- measurement API surface;
- command and domain-data shape;
- actual validation runtime, validator, and mode;
- connection preparation and reuse;
- matched history depth;
- setup and cleanup exclusion; and
- balanced strategy execution ordering.

Keep accepted and non-accepted outcome cohorts separate.

### Expected Artifacts

- bounded standard-library experiment runner;
- deterministic tests of experiment accounting, not latency thresholds;
- sanitized environment and method manifest;
- raw bounded samples where reviewable;
- outcome-stratified descriptive aggregates; and
- Stage 4B.2 comparison report with limitations.

### Dependencies

- accepted PR5 measurement-correctness evidence; and
- a stable, equivalent measurement surface for both compositions.

### Non-Goals

- no production benchmark infrastructure;
- no continuous performance-regression service;
- no universal performance claim;
- no strategy selector or automatic switching;
- no rate limit or load-admission policy; and
- no production telemetry backend.

### Stop Condition

Stop on mismatched APIs or configuration, uncontrolled setup/cleanup cost,
coordination time inside claimed boundaries, insufficient outcome samples,
unbalanced workloads, or results dominated by an unstable environment.

---

## PR7 — Bounded Concurrency Characterization

### Status

```text
PR7
= COMPLETE / CLOSED

canonical run
= stage4b2-pr7-canonical-cdbe542

canonical result
= VALID

canonical release-skew review
= ACCEPTED FOR CANONICAL INTERPRETATION

production policy
= NONE
```

The final method and canonical interpretation are recorded in the
[PostgreSQL Bounded Concurrency
Method](postgres_bounded_concurrency_method.md) and [PostgreSQL Bounded
Concurrency Report](postgres_bounded_concurrency_report.md). The report keeps
general different-order concurrency separate from same-order hot-stream
contention and closes PR7 without deriving capacity, a rate limit, or strategy
selection.

### Branch

```text
experiment/stage4b2-pr7-bounded-concurrency-characterization
```

### Responsibility

Observe how the two compositions change as concurrent demand increases in one
recorded environment.

### Historical Candidate and Final Retained Levels

The original planning candidates were:

```text
1
2
4
8
```

Following the valid connection-budget preflight and human review,
all four levels were retained for the canonical Level-C run.

These retained levels are environment-local experimental points, not universal
Stage 4B.2 requirements, production-safe concurrency settings, capacity
certifications, or rate-admission thresholds.

The completed preflight and human review established the experiment-local
connection budget, required headroom, and environment suitability before the
levels were retained and frozen into the canonical schedule.

### Required Workload Distinction

```text
same-order hot-stream contention
!= different-order general concurrency
```

Same-order bursts characterize conflict and early-exit behavior. Different-order
writes characterize general database concurrency more directly.

### Candidate Observations

- accepted throughput;
- all-completion throughput;
- median invocation latency;
- p95 only where sample size and protocol support it;
- typed outcome rates;
- append `STALE_WRITE` rate;
- advisory try-lock non-acquisition rate;
- business-UOW elapsed;
- validation elapsed in non-accepted executions; and
- validation cost per accepted write.

### Interpretation Boundary

The result is a bounded local scaling / saturation curve. It may report a visible
knee or no visible knee within the tested range.

It must not claim universal production capacity or derive:

```text
rate_limit = 1 / mean_latency
```

### Dependencies

- accepted PR6 controlled strategy-comparison method and evidence; and
- a preflighted local connection and environment budget.

### Non-Goals

- no production load generator;
- no distributed benchmark cluster;
- no connection-pool redesign;
- no SLO or latency policy;
- no autoscaling or rate limiter; and
- no universal saturation threshold.

### Stop Condition

Stop if the connection budget is unknown, a level cannot pre-open all required
connections with headroom, environment instability dominates the curve, or the
harness rather than the write composition becomes the measured bottleneck.

If only one or two credible levels are possible, report contention evidence but
do not claim saturation characterization without human review.

---

## PR8 — Stage 4B.2 Closeout

### Status

```text
PR8
= COMPLETE / DOCUMENTATION CLOSEOUT
```

### Branch

```text
docs/stage4b2-pr8-closeout
```

### Responsibility

Record the final implemented and empirical Stage 4B.2 boundary.

### Required Closeout Record

- implemented Level-A measurement contract;
- measurement correctness evidence;
- real PRE+OCC versus IN+pessimistic empirical findings;
- bounded concurrency findings;
- recorded environment and method limitations;
- outcome and workload qualifications;
- explicit deferrals;
- no-policy interpretation boundary; and
- handoff to future capacity and rate-admission work.

### Dependencies

- accepted PR7 bounded concurrency evidence, or an explicit human decision that
  valid Level-C work requires a separately named immediate follow-up.

### Non-Goals

- no strategy selection;
- no retry governance;
- no production capacity or rate policy;
- no receipt or event-metadata persistence expansion; and
- no implementation beyond closeout documentation and status alignment.

### Stop Condition

Stop if the contract, correctness evidence, controlled comparison, bounded
concurrency evidence, or limitations record is incomplete, or if local findings
are being overstated as universal policy.

---

## Stage Completion Boundary

Stage 4B.2 is not complete when it has only a vocabulary.

It is complete when:

1. exact Level-A semantics are characterized and accepted;
2. an immutable producer-specific contract is implemented;
3. equivalent measurement instrumentation exists for both compositions;
4. measurement correctness and existing-API parity are proved;
5. controlled PostgreSQL comparison produces real PRE/OCC and IN/pessimistic
   evidence;
6. bounded same-order and different-order concurrency questions are answered in
   the supported environment;
7. method and limitations are reviewable; and
8. no automatic policy conclusion is derived from lower cost.

If Level-C characterization is not meaningful in the available environment,
the stage stops for human review rather than silently closing as vocabulary-only.

The accepted PR8 closeout records all eight criteria as satisfied:

```text
Stage 4B.2
= COMPLETE / CLOSED
```

## Stage-Wide Non-Goals

The Stage 4B.2 sequence does not absorb:

- production rate limiting or load-admission policy;
- token-bucket or leaky-bucket implementation;
- autoscaling or SLO definition;
- continuous performance-regression infrastructure;
- Prometheus, Grafana, OpenTelemetry, dashboards, or metrics backends;
- production connection-pool redesign;
- automatic strategy selection or switching;
- retry governance, `AttemptLog`, `execution_id`, or `attempt_id`;
- `DecisionReceipt` redesign or automatic cost population;
- accepted-event timing metadata persistence;
- `DiagnosticTrace` timing or persistence;
- read-side measurement parity or snapshot benchmarks;
- commit-ambiguity redesign;
- idempotency TOCTOU hardening; or
- generic telemetry or exception-capture infrastructure.
