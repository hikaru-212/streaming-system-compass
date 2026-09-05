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
| PR1 | Unprotected load characterization | NOT STARTED |
| PR2 | Capacity / degradation interpretation | NOT STARTED |
| PR3 | First bounded in-flight capacity mechanism | CONDITIONAL |
| PR4 | Protected vs unprotected characterization | CONDITIONAL |
| PR5 | Optional arrival-rate / burst shaping | OPTIONAL / EVIDENCE-GATED |

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

These names are recommendations only, not claims that the branches exist.
PR5 branch planning is deferred until its need is established. This document
does not create branches or authorize Git mutations, PR creation, or merging.

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
NOT STARTED
```

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
ledger covering offered, dispatched, pending, entered, completed, refused, and
failed-before-entry observations. It must retain overload failures as evidence
while distinguishing them from fixture, correctness, and harness defects.
The detailed observation requirements remain in the PR0 boundary document.

### Scope and Non-Goals

Record acknowledged accepted throughput, waiting, latency, failures, and
durable verification under the declared topology. Retained-connection setup
observations remain separate from writer timing. Do not silently reuse PR7's
unexpected-exception invalidation rules for overload characterization.

PR1 does not select a protection limit, introduce a capacity mechanism, integrate
Stage 4E A2, or promote an experimental result into a production guarantee.
Its method and database execution require separate review and authorization.

## PR2 — Capacity / Degradation Interpretation

### Status

```text
NOT STARTED
```

### Goal and Responsibility

Interpret PR1 evidence within its actual workload, environment, topology, and
measurement boundaries. Valid conclusions may include:

```text
possible capacity knee established
```

or:

```text
no useful knee established in tested range
```

PR2 must not force a numerical answer. It distinguishes observed degradation,
possible knee, or saturation evidence from a chosen operating limit and safety
margin. A negative or inconclusive result may justify additional
characterization instead of mechanism work.

### Scope and Non-Goals

PR2 owns interpretation and limitations, not protection implementation. It does
not convert a failure point into an automatic operating policy or claim a
universal production capacity constant.

## PR3 — First Bounded In-Flight Capacity Mechanism

### Status

```text
CONDITIONAL
```

### Goal and Entry Conditions

Introduce the smallest capacity-protection mechanism only if PR1/PR2 evidence
justifies it. PR3 requires a fresh source-grounded audit before implementation,
including the proposed capacity scope, operating objective, headroom,
waiting/refusal semantics, and applicable authority-composition constraints.

```text
PR3 is not guaranteed.
```

### Scope and Non-Goals

A semaphore, token bucket, queue, or connection pool is an implementation
possibility, not a current decision. Neither a primitive nor a numerical limit
is selected by this plan. A future mechanism must preserve concurrency
correctness, semantic governance, and transaction ownership. Stage 4E A2
integration is not implicit and must not silently change one-shot authority.

## PR4 — Protected vs Unprotected Characterization

### Status

```text
CONDITIONAL
```

### Goal and Responsibility

If a justified mechanism exists, compare equivalent offered work under:

```text
unprotected execution
vs
bounded protected execution
```

Observe accepted throughput, waiting, refusal, latency, failures, and
correctness. Match workload and relevant environment/topology conditions, and
make any necessary differences explicit.

### Scope and Non-Goals

Rejected or refused work must remain visible in the accounting. Improved
accepted-request latency alone does not establish protection quality when
waiting, refusal, failure, or correctness evidence is omitted. PR4 does not
automatically establish a production SLO/SLA.

## PR5 — Optional Arrival-Rate / Burst Shaping

### Status

```text
OPTIONAL / EVIDENCE-GATED
```

### Goal and Entry Conditions

PR5 exists only if arrival evidence shows that bounded in-flight capacity
protection alone does not address the relevant arrival problem.

```text
PR5 is not guaranteed.
```

### Scope and Non-Goals

Only then should a separate shaping responsibility be evaluated. Do not assume
a token bucket or any rate limiter is required. This plan selects no arrival
rate, burst allowance, or shaping algorithm.
