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
PR1 — COMPLETE / EVIDENCE COLLECTION CLOSED
PR2 — capacity / degradation / operating-headroom interpretation — COMPLETE
PR3 — bounded in-flight writer admission — COMPLETE
PR4 — COMPLETE / EVIDENCE COLLECTION CLOSED
PR5 — NOT STARTED / CANDIDATE RETRY-REFUSAL CHARACTERIZATION
```

PR2 selects N=8 as a candidate protected experimental point and bounded
in-flight writer admission as the first mechanism class to evaluate. This is
workstream interpretation, not a production capacity limit. PR3 implements
opt-in, explicitly shared, process-local fail-fast admission with no numerical
default. PR4 completed same-source paired characterization and durable verification.
The gate bounded writer overlap and reduced later UOW/append elapsed amplification,
but every recorded protected overload cell accepted eight and terminally refused
504 of 512 items before the first admitted body completed. This establishes local
writer-resource protection, not end-to-end overload resolution or retry-storm
evidence. The closeout package passed internal checks and is ready for human
review; publication of the exact raw ZIP remains a separate final action.

## Research Direction

```text
measurement
→ load characterization
→ capacity interpretation
→ protection mechanism if justified
→ protected/unprotected comparison
→ candidate retry/refusal amplification characterization
→ further mechanisms only if separately justified
```

Completed Stage 4B.2 evidence supplies a measured starting point. It does not
establish a production capacity limit or reopen that completed stage.

## Documents

| Document | Responsibility |
|---|---|
| [PR Breakdown](pr_breakdown.md) | Delivery sequence, PR-level responsibilities, branch recommendations, and documentation placement. |
| [PR0 Research and Responsibility Boundary](pr0_research_and_responsibility_boundary.md) | Source-grounded capacity responsibility, inherited evidence, observation gaps, first experiment question, and non-goals. |
| [PR1 Unprotected Characterization Method](pr1_unprotected_characterization_method.md) | Fixed-work experiment method, outer evidence, validity requirements, and separate live-run approval gate. |
| [PR1 Unprotected Characterization Report](pr1_unprotected_characterization_report.md) | Accepted exploratory/refinement evidence, descriptive results, limitations, and PR1 closeout; no capacity policy selected. |
| [PR2 Capacity Interpretation and Operating Headroom](pr2_capacity_interpretation.md) | Verified N=8 vs N=10 comparison, experimental headroom selection, capacity responsibility, PR3 entry criteria, and PR4 validation contract. |
| [PR3 Bounded In-Flight PostgreSQL Writer Admission](pr3_bounded_inflight_admission.md) | Source-grounded placement/ownership audit, fail-fast configuration and lifecycle, A2 coverage, deterministic characterization, and PR4 observation handoff. |
| [PR4 Protected vs Unprotected Method](pr4_protected_vs_unprotected_method.md) | Pre-run method: same-source pairing, offered/admitted/refused/accepted evidence, shared gate observation, durable verification, metrics, and live-run approval boundary. |
| [PR4 Protected vs Unprotected Report](pr4_protected_vs_unprotected_report.md) | Accepted 70-cell A/B evidence, 60 recorded comparisons, exact manifest/archive identity, local writer protection and refusal displacement, limitations, and PR4 closeout; PR5 remains NOT STARTED. |

## Important Boundary

```text
Capacity Admission
!= Semantic Admission
!= Concurrency Control
```

Capacity admission asks whether work may consume the specified backend capacity
now. It does not establish business truth, concurrency correctness, or
retry/replanning authority. PR0 introduced the conceptual boundary; PR3's
capacity-specific refusal remains separate from production semantic results.
