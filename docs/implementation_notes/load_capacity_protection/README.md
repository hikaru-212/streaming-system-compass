# Load / Capacity Protection

[← Back to Implementation Notes](../README.md)

## Purpose

This separately owned workstream investigates backend load/capacity protection:
how much application work may enter a specified resource-consuming execution
boundary when offered demand exceeds useful capacity.

Capacity protection remains separate from semantic admission, concurrency
correctness, transaction atomicity, Stage 4C Current-Response Authority, and
Stage 4E Re-invocation Authority.

## Current Status

```text
PR0 — responsibility / research boundary — COMPLETE
PR1 — ACTIVE
```

PR0 is documentation-only work. Later PRs remain subject to evidence and
separate review; no production mechanism or numerical limit has been selected.

## Research Direction

```text
measurement
→ load characterization
→ capacity interpretation
→ protection mechanism if justified
→ protected/unprotected comparison
→ optional arrival-rate shaping if separately justified
```

Completed Stage 4B.2 evidence supplies a measured starting point. It does not
establish a production capacity limit or reopen that completed stage.

## Documents

| Document | Responsibility |
|---|---|
| [PR Breakdown](pr_breakdown.md) | Delivery sequence, PR-level responsibilities, branch recommendations, and documentation placement. |
| [PR0 Research and Responsibility Boundary](pr0_research_and_responsibility_boundary.md) | Source-grounded capacity responsibility, inherited evidence, observation gaps, first experiment question, and non-goals. |
| [PR1 Unprotected Characterization Method](pr1_unprotected_characterization_method.md) | Fixed-work experiment method, outer evidence, validity requirements, and separate live-run approval gate. |

## Important Boundary

```text
Capacity Admission
!= Semantic Admission
!= Concurrency Control
```

Capacity admission asks whether work may consume the specified backend capacity
now. It does not establish business truth, concurrency correctness, or
retry/replanning authority. The terminology is conceptual at PR0, not a new
production type.
