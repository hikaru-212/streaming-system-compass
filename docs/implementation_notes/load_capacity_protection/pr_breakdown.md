# Load / Capacity Protection PR Breakdown

[← Back to Load / Capacity Protection](README.md)

## Purpose

This file owns the staged delivery plan and PR-level responsibilities for
Load / Capacity Protection. The
[PR0 research and responsibility boundary](pr0_research_and_responsibility_boundary.md)
owns the source-grounded research contract and technical non-goals.

The delivery principle is:

```text
evidence
→ characterization
→ interpretation
→ mechanism only if justified
→ validation of protection
```

This is the completed PR0–PR11 delivery record. PR-specific responsibilities
below retain their chronology; current statuses and the final closeout do not
authorize later implementation or select a production limiter.

## Current Status

| Responsibility | Final status |
|---|---|
| Research and characterization | COMPLETE |
| Production-capable opt-in mechanism | IMPLEMENTED AND VALIDATED |
| Actual production deployment | NOT QUALIFIED |

The [workstream closeout](workstream_closeout.md) owns the final status,
evidence/Release index, remaining deployment obligations and conditions for
reopening work. No PR12 implementation or umbrella-to-main merge is authorized.
Historical notes retain their original stage-specific status labels; accepted
ADRs and evidence reports retain their respective decision and measurement roles.

| PR | Responsibility | Status |
|---|---|---|
| PR0 | Research / responsibility boundary | COMPLETE |
| PR1 | Unprotected load characterization | COMPLETE / EVIDENCE COLLECTION CLOSED |
| PR2 | Capacity / degradation / operating-headroom interpretation | COMPLETE |
| PR3 | First bounded in-flight capacity mechanism | COMPLETE |
| PR4 | Protected vs unprotected characterization | COMPLETE / EVIDENCE COLLECTION CLOSED |
| PR5 | Retry / Refusal Amplification Characterization | COMPLETE / EVIDENCE COLLECTION CLOSED |
| PR6 | ADR: separate resource occupancy, retry and arrival protection | ADR COMPLETE |
| PR7 | Production Retry / Attempt-Pressure Policy Selection | COMPLETE |
| PR8 | Production implementation of the selected bounded retry with backoff class | COMPLETE / MERGED |
| PR9 | Live production-path retry characterization | COMPLETE / MERGED / EVIDENCE COLLECTION CLOSED |
| PR10 | Retry Waiting Ownership Architecture Decision | COMPLETE / MERGED / Accepted in ADR 0032 |
| PR11 | Caller Resource Envelope and Deployment Qualification Audit | COMPLETE / MERGED / deployment NOT QUALIFIED |

PR8–PR11 are merged into `feat/load-capacity-protection`. PR10's conditional
Option A recommendation is human-approved and recorded in
[ADR 0032](../../adr/0032_keep_capacity_retry_synchronous_under_explicit_caller_resource_budgets.md).

## Branch / PR Workflow

The umbrella integration branch is:

```text
feat/load-capacity-protection
```

The PR0 branch at workstream start was:

```text
docs/load-capacity-pr0-boundary
```

The current documentation closeout branch is:

```text
docs/load-capacity-workstream-closeout
```

Workstream PR branches target the umbrella integration branch. The recorded
PR branch recommendations were:

| PR | Recommended branch |
|---|---|
| PR1 | `experiment/load-capacity-pr1-characterization` |
| PR2 | `docs/load-capacity-pr2-capacity-interpretation` |
| PR3 | `feat/load-capacity-pr3-inflight-protection` |
| PR4 | `experiment/load-capacity-pr4-protected-comparison` |
| PR5 | `experiment/load-capacity-pr5-retry-amplification` |
| PR6 | `docs/load-capacity-pr6-occupancy-retry-adr` |
| PR7 | `docs/load-capacity-pr7-retry-policy-selection` |
| PR8 | `feat/load-capacity-pr8-bounded-retry-backoff` |
| PR9 | `experiment/load-capacity-pr9-production-retry-validation` |
| PR10 | `docs/load-capacity-pr10-retry-waiting-ownership` |
| PR11 | `docs/load-capacity-pr11-caller-resource-envelope` |

These names retain planning chronology, not claims that every branch still
exists. The current closeout branch is named above. This document does not create
branches or authorize Git mutations, PR creation, or merging.

## Commit Discipline

```text
one PR = one coherent responsibility
one PR may contain multiple smaller commits
```

Keep each change reviewable within its PR's responsibility. Commit, push, and
merge operations still require explicit authorization; this plan grants none.

## Documentation Placement Rule

```text
workstream / PR-specific design, method, report, characterization
→ docs/implementation_notes/load_capacity_protection/

stable cross-cutting architectural boundary
→ docs/boundary_notes/

accepted architectural choice among alternatives
→ docs/adr/
```

The workstream directory owns current PR0 research and implementation-boundary
material. Future PR audits must determine whether a stable cross-cutting
contract or accepted choice among alternatives justifies promotion. PR0 does
not pre-create a boundary note or ADR.

This classification follows the existing roles of
[Implementation Notes](../README.md),
[Boundary Notes](../../boundary_notes/README.md), and
[Architecture Decision Records](../../adr/README.md).

## PR0 — Research / Responsibility Boundary

### Status

```text
COMPLETE
```

### Goal and Responsibility

- Establish the missing capacity responsibility.
- Separate capacity admission from semantic admission, concurrency correctness,
  transaction atomicity, and Stage 4C / Stage 4E authority.
- Inherit completed Stage 4B.2 evidence without rewriting its conclusions.
- Record the minimum missing outer observation surface.
- Freeze measure-before-protect discipline.
- Define the first experiment question.

### Scope and Non-Goals

Documentation only: the workstream entry point, this delivery plan, the PR0
boundary document, and the parent navigation entry. No production code,
experiment execution, mechanism selection, or numerical capacity policy belongs
to PR0. PR1 does not begin as part of PR0 finalization.

## PR1 — Unprotected Load Characterization

### Status

```text
COMPLETE
```

The [PR1 characterization method](pr1_unprotected_characterization_method.md)
owns the experiment method. The
[PR1 characterization report](pr1_unprotected_characterization_report.md)
records the accepted exploratory/refinement evidence and closeout. PR1 evidence
collection is closed; the separate
[PR2 interpretation](pr2_capacity_interpretation.md) is now COMPLETE.

### Goal and Responsibility

Characterize the current PostgreSQL writer under increasing offered concurrency
before any capacity protection exists. The initial research boundary is:

```text
fixed finite workload
fresh independent Order IDs
unique request IDs
PRE_TRANSACTION
optimistic admission / OCC
STRICT validation
retained distinct connection per active lane
offered concurrency varies
actual overlap must be observed
```

PR1 owns an explicit experiment method and an experiment-owned outer execution
ledger covering planned/offered work, dispatched/pending work, writer-entered
work, terminal/failure observations, and residual/incomplete work. A capacity
refusal mechanism is absent. It must retain overload failures as evidence while
distinguishing them from fixture, correctness, and harness defects.
The detailed observation requirements remain in the PR0 boundary document.

### Scope and Non-Goals

Record acknowledged accepted throughput, waiting, latency, failures, and
durable verification under the declared topology. Retained-connection setup
observations remain separate from writer timing. Do not silently reuse PR7's
unexpected-exception invalidation rules for overload characterization.

PR1 does not select a protection limit, introduce a capacity mechanism, integrate
Stage 4E A2, or promote an experimental result into a production guarantee.
Its method and database execution require separate review and authorization.

## PR2 — Capacity / Degradation / Operating-Headroom Interpretation

### Status

```text
COMPLETE
```

### Goal and Responsibility

The [PR2 interpretation](pr2_capacity_interpretation.md) verifies PR1's compact
evidence and separates:

```text
observed throughput maximum
!= observed degradation transition
!= candidate operating region
!= selected experimental protection point
!= universal production capacity
```

It selects N=8 for a first bounded in-flight writer experiment: below the
descriptive N=10–12 degradation transition, measured in both runs, retaining
95.83% of N=10 refinement median throughput with lower writer and DB-backed
elapsed cost. Concurrency-distance headroom is a design choice, not a
statistically established reserve. PR2 owns the detailed comparison,
limitations, PR3 entry criteria, and PR4 validation contract.

### Scope and Non-Goals

PR2 owns interpretation and limitations, not protection implementation. Its
experimental selection is not a production default, an exact knee, or a
universal capacity constant. The separate PR3 implementation is now COMPLETE.

## PR3 — First Bounded In-Flight Capacity Mechanism

### Status

```text
COMPLETE
```

### Goal and Entry Conditions

The [PR3 implementation note](pr3_bounded_inflight_admission.md) records the
completed placement/ownership audit and implementation under the
[PR2 entry criteria](pr2_capacity_interpretation.md#9-pr3-entry-criteria).
One explicitly shared, process-local admission object protects all public
CREATE/PAY writer variants, including authorized A2. Fail-fast refusal occurs
before the original body; normal and exceptional exits release capacity.

### Scope and Non-Goals

Configuration is opt-in with an explicit positive bound and no numerical default.
N=8 remains PR2's first experimental point. The primitive uses nonblocking
bounded-semaphore acquisition, with no waiting queue or new semantic outcome.
Stage 4E's existing one-shot spend and exception lifecycle remain unchanged.
Rate/burst shaping, connection-pool tuning, and external queue policy remain
separately evidence-gated. PR3 tests mechanics, not protected load performance.

## PR4 — Protected vs Unprotected Characterization

### Status

```text
COMPLETE / EVIDENCE COLLECTION CLOSED
Closeout complete; evidence collection closed
Exact PR4 raw evidence archive — PUBLISHED via the GitHub Release referenced by the PR4 report/manifest
```

### Goal and Responsibility

With PR3's configured mechanism, compare equivalent offered work under a
separately reviewed and authorized run plan:

```text
unprotected execution
vs
bounded protected execution
```

Observe accepted throughput, waiting, refusal, latency, failures, and
correctness. Match workload and relevant environment/topology conditions, and
make any necessary differences explicit.

The [PR2 validation contract](pr2_capacity_interpretation.md#10-pr4-validation-contract)
requires offered execution opportunity above the protected bound, observed
writer-entry overlap within it, unchanged correctness, complete work accounting,
and evaluation of throughput, DB-backed latency, and waiting before entry.
Bounding overlap alone or merely relocating pressure does not establish benefit.
PR3 exposes the admitted-operation boundary. The
[PR4 method](pr4_protected_vs_unprotected_method.md) records the separate PR4
model and runner: pre-entry refusal versus admitted body, continued claims after
refusal, verified absence, and accepted-only cleanup. It supports adjacent,
counterbalanced same-source protected/unprotected cells. Historical PR1 machinery
remains unchanged. The [PR4 report](pr4_protected_vs_unprotected_report.md)
closes the accepted 70-cell same-source run, including 60 recorded cells.

The protected writer overlap stayed at eight under observed public overlap above
eight. UOW/append elapsed amplification fell; commit improved at N=12/16/32 but
increased at N=10. N=8 showed no material instrumented-path penalty in the central
metrics. Every recorded protected overload cell accepted eight and refused 504
of 512 logical items before the first admitted body completed. This establishes
a working occupancy boundary and scoped local protection, not end-to-end overload
resolution. There were no retries; pressure displacement is not retry-storm evidence.

### Scope and Non-Goals

Rejected or refused work must remain visible in the accounting. Improved
accepted-request latency alone does not establish protection quality when
waiting, refusal, failure, or correctness evidence is omitted. PR4 does not
automatically establish a production SLO/SLA.

## PR5 — Retry / Refusal Amplification Characterization

### Status

```text
COMPLETE / EVIDENCE COLLECTION CLOSED
Closeout complete; evidence collection closed
Exact PR5 raw evidence archive — PUBLISHED via the GitHub Release referenced by the PR5 report/manifest
```

### Goal and Entry Conditions

PR4's observed refusal displacement motivates the separately owned
[PR5 method](pr5_retry_refusal_amplification_method.md):

> Can a protected PostgreSQL writer remain within its occupancy bound while
> caller retry behavior amplifies attempts and pressure outside that region?

The machinery supports contemporaneous NO_RETRY, IMMEDIATE_RETRY, FIXED_BACKOFF,
EXPONENTIAL_BACKOFF and EXPONENTIAL_BACKOFF_WITH_JITTER. Stable logical intent is
separate from attempt identity. Only observed pre-body WriterCapacityRefused
feeds the experiment-owned bounded policy. Raw trajectories, logical completion,
amplification, real protected overlap and durable verification remain distinct.
PR4 did not exercise retries and does not establish retry amplification.

The [PR5 report](pr5_retry_refusal_amplification_report.md) closes the accepted
30-cell run, including 25 recorded cells. Recorded immediate retry amplified
attempts 7.5625× with the same 6.25% logical completion as NO_RETRY. All policies
kept observed writer-body overlap at eight. Backoff increased completion while
extending drain time and pacing later fresh work; successful retry recovery
explains only part of the additional accepted work. Concentration comparisons
remain explicitly qualified by analysis-window width.

### Scope and Non-Goals

Retry budgets, backoff and jitter here are experiment stimuli with explicit
parameters, not production mechanisms or Stage 4E reinvocation authority.
PR7/PR8 separately selected and implemented opt-in production retry; rate limiting
and arrival shaping remain deferred. The report and manifest record the completed
run's exact K/N, attempt budgets, delays, jitter, warmups and repetitions. No additional
PostgreSQL experiment was run for closeout; evidence collection is closed.

PR5 supplied the evidence for the separately authorized PR6 decision below.
Its experiment policies remain historical stimuli, not production selections.

## PR6 — ADR: Separate Resource Occupancy, Retry, and Arrival Protection

### Status

```text
ADR COMPLETE
Architectural separation — Accepted in ADR 0031
Subsequent retry implementation — PR8 COMPLETE / MERGED
```

### Goal and Responsibility

[ADR 0031](../../adr/0031_separate_resource_occupancy_retry_and_arrival_protection.md)
uses PR1 degradation, PR2 experimental headroom, PR3 shared occupancy admission,
PR4 refusal displacement and PR5 retry amplification to decide:

```text
Resource Occupancy Protection
!= Retry Pressure Protection
!= Arrival-Rate Protection
```

`BoundedWriterAdmission` retains simultaneous admitted writer occupancy only.
`WriterCapacityRefused` remains capacity-specific and authority-neutral; it is
neither a semantic outcome nor automatic retry, Stage 4E or replanning authority.
Retry budget/timing belongs to a separate explicit policy layer. Arrival/attempt
rate and burst protection remain separately evidence-gated responsibilities.

### Scope and Non-Goals

Documentation and architecture interpretation only. Acceptance decides
responsibility boundaries, not a production Rate Limiter, Token Bucket, queue
or retry algorithm. No production code, experiments, evidence or dependencies
change, and no PostgreSQL workload or test suite is run for PR6.

### Policy-Selection Handoff

ADR 0031 handed the following question to separately authorized policy selection:

> Which explicit retry / attempt-pressure mechanism should be promoted into
> production, if any?

The [PR7 policy selection](pr7_retry_attempt_policy_selection.md) below now answers
that question. ADR 0031 remains the accepted responsibility-separation decision;
PR7 does not rewrite its historical non-selection into a PR6 implementation.

## PR7 — Production Retry / Attempt-Pressure Policy Selection

### Status

```text
COMPLETE / selected class implemented by PR8
Production numerical policy — NOT SELECTED
PR8 entry contract — handed off to the separately authorized implementation below
```

### Goal and Responsibility

The [PR7 selection](pr7_retry_attempt_policy_selection.md) verifies tracked PR5
counts/timing and the PR4 shedding evidence, compares eight concrete alternatives,
and selects the smallest supported enabled class: **explicit finite retry budget
plus delayed backoff**. Budget limits additional attempts; timing decides when
eligible attempts may occur. No retry remains the disabled baseline. Immediate
retry is rejected for the first enabled mechanism. Fixed versus exponential
shape remains an explicit PR8 design/configuration choice; jitter is deferred
pending a more isolated comparison. No Rate Limiter, Token Bucket or bounded
queue/backpressure mechanism is selected.

PR7 selected a caller/orchestration policy layer outside the protected
writer, capacity primitive and Stage 4E invocation/runtime owners, implemented
by PR8 below. Explicit configuration supplies narrow authority to react to
verified pre-body capacity refusal; the refusal itself does not authorize retry.
PR5's retained-lane pacing
continues to qualify completion and jitter interpretation.

### Scope and Non-Goals

Evidence-backed policy selection and current navigation only. No production
code, experiment, evidence, numerical default, dependency or environment change.
PR5's attempt count, delays, cap and jitter values remain characterization probes.
No PostgreSQL run, experiment rerun or test suite is part of PR7. The entry
contract defines later work without starting it.

## PR8 — Production Bounded Retry with Backoff

### Status

```text
COMPLETE / MERGED into feat/load-capacity-protection
Production numerical policy and deployment qualification remain open
```

### Goal and Entry Conditions

PR8 implements the selected opt-in caller-owned class, narrow interfaces and
focused validation under the full
[PR7 entry contract](pr7_retry_attempt_policy_selection.md#12-pr8-entry-contract).
It supplies a direct-writer API, verifies pre-body refusal provenance, defines
explicit configuration and finite budget spend, preserves logical identity
across distinct serial attempts, terminates on acceptance or other ineligible
outcomes, exposes logical-versus-attempt observations, and retains disabled behavior.

Waiting occurs outside capacity ownership, with no permit, business
transaction or invocation-owner lifecycle lock held. PR8 defines cooperative
cancellation/expiry and retained-resource ownership; a finite attempt budget
does not provide a hard writer deadline. Concrete schedule and numerical
configuration require explicit justification and must not copy experimental
constants as defaults.

The separately authorized [PR8 implementation](pr8_bounded_retry_backoff.md)
adds `build_postgres_writer_request` and `PostgresWriterRequest` as a direct-writer
composition outside the existing Stage 4E runtime. No existing safe direct-writer
production caller was found; the existing DecisionReceipt runtime holds a lock
across delegation and its one-shot invocation methods cannot be retried.
The new owner uses an explicit finite `max_attempts` including the first and an
immutable sequence of positive delays, with no enabled numerical defaults.
Only adapter-verified pre-body refusal can continue; waiting checks caller
transaction idleness and retains no writer permit or lifecycle lock. Exhaustion
preserves the final refusal in a capacity-specific exception. Focused mechanism,
capacity and Stage 4E regressions passed (298 tests).

### Scope and Non-Goals

No retry inside `BoundedWriterAdmission`, `PostgresTransactionalWriteSide` or
Stage 4E owners. No native/ambiguous/semantic-failure retry, hidden Rate Limiter,
Token Bucket, queue, jitter or Stage 4E integration. Production numerical
qualification and any new experiment/database execution remain separately scoped.
PR8 established mechanism correctness. PR9 subsequently completed live
characterization through that production composition. Deployment qualification,
numerical policy and any further characterization require separate scope and
authorization.

## PR9 — Production-Path Retry Validation

### Status

```text
COMPLETE / MERGED into feat/load-capacity-protection / EVIDENCE COLLECTION CLOSED
Canonical live matrix — reconciled offline; no rerun
Canonical raw archive — PUBLISHED via the GitHub Release referenced by the PR9 report/manifest
Production numerical defaults / deployment acceptance — NOT SELECTED
```

### Goal and Responsibility

The [PR9 method](pr9_production_retry_validation_method.md) implements
contemporaneous disabled/enabled comparison through the real
`build_postgres_writer_request` / `PostgresWriterRequest` composition. The
fixture, logical workload, capacity bound, committed source, observation settings
and retained-connection topology must match, with retry policy as the intended
difference. Observe attempts, logical completion, body overlap, phase timing,
synchronous waiting and retained idle resources; verify durable effects separately.

The initial source audit found a supported-interface gap. The user approved
optional observation in exactly the concrete capacity primitive, request owner
and builder. Context-bound request/attempt observations retain failures
separately; measured delivery remains separate from the primary result. The
concrete-gate provenance restriction and retry policy remain unchanged.
PR9 now supplies its own model/codec, real-builder adapter, paired runner,
durable verification and retained-resource accounting with deterministic tests.

The subsequently authorized live matrix and
[PR9 report](pr9_production_retry_validation_report.md) establish a contemporaneous
comparison at `41e33d3a855caa03afbf0b10fe4b2ee01c478a33`: 36 total cells,
30 recorded cells and 3,840 recorded logical requests. N=8 retry is dormant.
At N=16/32, enabled retry raises eventual completion with bounded writer overlap,
more attempts and substantially longer drain; paired completion throughput remains
broadly similar. All 2,854 acknowledgements match durable accepted effects and
all 986 refusal-only terminal requests have verified absence, including 186
exhaustions. All 2,080 wait calls sample IDLE → IDLE while retaining existing
lane/thread/connection ownership. Completion improvement includes pacing of later
fresh work, not only direct retry recovery.

The unchanged method retains its pre-run chronology. The
[compact CSV](../../../experiments/load_capacity_protection/results/pr9_recorded_repetitions.csv)
and [manifest](../../../experiments/load_capacity_protection/results/pr9_evidence_manifest.json)
preserve repetition-level scalars, paired summaries and canonical evidence/archive
identity. Only the original complete `final.json` is archived; cumulative
snapshots are checkpoint artifacts, not additional observations. The canonical
archive is published via the GitHub Release linked in the
[PR9 report](pr9_production_retry_validation_report.md#raw-evidence-publication)
and manifest.

### Scope and Non-Goals

Closeout uses the existing canonical evidence only; no PostgreSQL rerun, added
repetitions, parameter changes or production/experiment-code edits occurred.
The approved K=128, N=8/16/32, bound=8 and eight-attempt fixed 5 ms schedule remain
experimental parameters, not production defaults or optimality claims.
No retry reimplementation, PR5 scheduler substitution, Rate Limiter, jitter,
queue, async scheduler, pool or Stage 4E change belongs to this closeout.
Historical evidence and Releases remain intact.

PR9 is COMPLETE and merged after evidence reconciliation. Its retained-resource
ownership question is addressed by PR10 and accepted ADR 0032 below. Deployment
acceptance remains caller-specific; no ownership redesign is automatically
authorized, and neither Rate Limiter nor jitter is ruled out permanently.

## PR10 — Retry Waiting Ownership Architecture Decision

### Status

```text
COMPLETE / MERGED / conditional Option A accepted in ADR 0032
Deployment acceptance / numerical policy — NOT ESTABLISHED
Production implementation / new live execution — NOT AUTHORIZED
```

### Goal and Responsibility

The [PR10 decision](pr10_retry_waiting_ownership_decision.md) audits connection
acquisition/custody, synchronous thread lifetime, session/transaction state and
durable identity against current source and tracked PR9 results. It compares
retention, release/reacquisition inside the current owner, retry above per-attempt
resource acquisition, and a deferred scheduler/queue/async alternative.

[ADR 0032](../../adr/0032_keep_capacity_retry_synchronous_under_explicit_caller_resource_budgets.md)
accepts retaining the current synchronous borrowed-connection
contract only for callers with explicit concurrency, connection/thread headroom,
finite retry lifetime, custody and shutdown/cancellation preconditions.
Connection identity is not semantic identity. If a caller needs connection-free
waiting, Option C is the preferred candidate for separate design; neither implementation nor equal
performance is inferred. The writer bound still does not bound connections or
waiting callers. Option B is not selected; scheduler/queue/async ownership remains
deferred. PR9's retained-lane pacing qualification remains essential.

### Scope and Non-Goals

Documentation-only investigation, accepted ADR and navigation. The PR10 note
preserves its pre-acceptance chronology; ADR 0032 records the human-approved
decision. No source, tests, experiment machinery/results, historical evidence,
production numerical defaults, Rate Limiter, pool, queue, async scheduler or Stage 4E change. No
PostgreSQL or additional characterization is authorized. PR11 below audits
whether a current caller meets the accepted resource/lifetime preconditions;
no implementation PR is automatically started.

## PR11 — Caller Resource Envelope and Deployment Qualification Audit

### Status

```text
COMPLETE / MERGED into feat/load-capacity-protection / investigation closed
Production retry-enabled consumer — NONE FOUND in the audited repository
Caller envelope / deployment qualification — NOT ESTABLISHED / NOT QUALIFIED
Production implementation / new live execution — NOT AUTHORIZED
```

### Goal and Responsibility

The [PR11 audit](pr11_caller_resource_envelope_audit.md) traces all tracked uses
of the retry owner, policy, builder and capacity primitive, separating production
composition from tests and experiments. No production application routes requests
through the opt-in retry composition. Stage 4E and DecisionReceipt still use the
transactional writer directly; PR9's bounded retained lanes are experiment-owned.

The qualification matrix distinguishes source-enforced per-gate occupancy,
per-owner finite attempts, IDLE checks and cooperative cancellation from absent
caller concurrency, aggregate connection/thread budgets, overall lifetime and
shutdown/cleanup ownership. Finite attempt count does not bound total invocation
lifetime; IDLE does not prove exclusive custody or absence of session locks.

### Disposition and Follow-up Boundary

Disposition D: production-capable composition without a qualified production
consumer. ADR 0032's conditional Option A remains accepted (disposition B's
architectural context). The smallest follow-up is an explicit resource and
lifecycle contract for one named intended caller, followed by qualification of
that actual integration. Only a concrete unmet requirement could justify separate
implementation; no new ownership mechanism or subsequent implementation PR is
automatically selected.

Documentation and current navigation only. No production code, tests,
experiments, historical evidence, numerical defaults, Rate Limiter, Token Bucket,
pool, queue, async scheduler or Stage 4E change; no PostgreSQL or evidence replay.

## Final Workstream Disposition

PR0–PR11 are complete within their declared responsibilities. The
[workstream closeout](workstream_closeout.md) consolidates evidence publication,
accepted architectural boundaries and unresolved deployment obligations.
Research and characterization are COMPLETE; the production-capable opt-in
mechanism is IMPLEMENTED AND VALIDATED; actual production deployment is
NOT QUALIFIED. No tracked production caller enables retry.

Only the [explicit re-entry conditions](workstream_closeout.md#conditions-for-reopening-work)
can justify a separately authorized follow-up: a named caller/integration and its
resource/lifecycle contract, a concrete unmet requirement, or a reproducible defect.
New evidence may be needed before any mechanism change. This record starts no
PR12 implementation, selects no Rate Limiter/pool/queue/async scheduler or
production numerical defaults, and authorizes no umbrella-to-main merge.
