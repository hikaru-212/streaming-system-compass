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

This is a conditional research plan, not authorization to begin later PRs or a
commitment to implement a production limiter.

## Current Status

| PR | Responsibility | Status |
|---|---|---|
| PR0 | Research / responsibility boundary | COMPLETE |
| PR1 | Unprotected load characterization | COMPLETE |
| PR2 | Capacity / degradation / operating-headroom interpretation | COMPLETE |
| PR3 | First bounded in-flight capacity mechanism | COMPLETE |
| PR4 | Protected vs unprotected characterization | COMPLETE / EVIDENCE COLLECTION CLOSED |
| PR5 | Retry / Refusal Amplification Characterization | ACTIVE / MACHINERY FOR REVIEW |

## Branch / PR Workflow

The umbrella integration branch is:

```text
feat/load-capacity-protection
```

The current PR0 branch is:

```text
docs/load-capacity-pr0-boundary
```

Workstream PR branches target the umbrella integration branch. Recommended
future branch names are:

| PR | Recommended branch |
|---|---|
| PR1 | `experiment/load-capacity-pr1-characterization` |
| PR2 | `docs/load-capacity-pr2-capacity-interpretation` |
| PR3 | `feat/load-capacity-pr3-inflight-protection` |
| PR4 | `experiment/load-capacity-pr4-protected-comparison` |
| PR5 | `experiment/load-capacity-pr5-retry-amplification` |

These names are recommendations only, not claims that the branches exist.
PR5 is active on the named experiment branch. This document does not create
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
Closeout package internally checked; ready for human review
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
ACTIVE / CHARACTERIZATION MACHINERY FOR HUMAN REVIEW
Live matrix — NOT SELECTED / NOT RUN
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

### Scope and Non-Goals

Retry budgets, backoff and jitter here are experiment stimuli with explicit
parameters, not production mechanisms or Stage 4E reinvocation authority.
Production retry, rate limiting and arrival shaping require later evidence and
authorization. No live K/N, attempt budget, delay/cap/jitter values, warmups or
recorded repetitions are selected. No live PostgreSQL retry experiment ran.

After PR5 evidence, a later decision/ADR may consider:

```text
resource-occupancy protection != retry/arrival protection
```

Only a later explicitly approved PR may implement a justified production
retry/rate/arrival mechanism. No ADR is created by this PR5 machinery task.
