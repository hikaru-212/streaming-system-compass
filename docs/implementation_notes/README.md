# Implementation Notes

This folder contains implementation-level notes for completed or active project stages.

Implementation notes preserve PR breakdowns, boundary decisions, storage contracts, validator contracts, resolver contracts, test boundaries, and execution details that are too detailed for the project roadmap.

For project-wide sequencing, see:

- [Implementation Roadmap](../roadmap/implementation_roadmap.md)

## Stage Notes

- [Stage 3.5B — Durable Write-Side Baseline](./stage_3_5b/)
- [Stage 3.5C — Durable Read-Side Baseline](./stage_3_5c/)
- [Stage 3.5D — Snapshot Trust Contract / Replay Efficiency](./stage_3_5d/)
- [Stage 3.5E — Durable History and Permission Hardening](./stage_3_5e/)
- [Stage 4A — SemanticOutcome Core](./stage_4a/)
- [Stage 4B — DecisionReceipt / Runtime Evidence Record](./stage_4b/)
- [Stage 4B.1 — DiagnosticTrace / ResolutionTrace](./stage_4b_1/)
- [Stage 4B.2 — Measurement Evidence](./stage_4b_2/)
- [Stage 4B.3 — Projection Trust Boundary and Continuation Closeout](./stage_4b_3/)
- [Stage 4B.5 — Order Correctness Contract v0](./stage_4b_5/)
- [Stage 4C — Runtime Decision Authority — complete / closed](./stage_4c/)
- [Stage 4E — Same-Request Re-Invocation Authority — complete / closed](./stage_4e/)
- [Stage 4E closeout](./stage_4e/stage_4e_closeout.md)
- [Load / Capacity Protection](./load_capacity_protection/README.md) — separately owned investigation; PR0 research / boundary documentation active.

## Current Position

Stage 4A, Stage 4B PR1–PR7, Stage 4B.1 PR1–PR7, Stage 4B.2 PR1–PR8,
Stage 4B.5 through PR8, Stage 4C, and Stage 4E through PR6 are complete.
Stage 4B.2, Stage 4B.5, Stage 4C, and Stage 4E are closed.

Stage 4 Interlude PR0 — test helper consolidation before Stage 4B — is complete.

Stage 4B.2 is complete and closed. Its final delivery record is the
[Stage 4B.2 closeout](stage_4b_2/stage_4b_2_closeout.md).

The current Stage 4 foundation position is:

```text
Stage 4B.3
= Projection Trust Boundary and Continuation
= COMPLETE / CLOSED AS NOT CURRENTLY JUSTIFIED

Stage 4B.5
= Order Correctness Contract v0 — COMPLETE / CLOSED

Stage 4C
= Runtime Decision Authority — COMPLETE / CLOSED
= PR1 source-grounded implementation-entry boundary
= PR2 generic RuntimeDecision + first Layer-1 PostgreSQL / Order profile
= Stage 4C.5 compatibility / documentation closeout

Stage 4E
= Same-Request Re-Invocation Authority — COMPLETE / CLOSED
= exactly two reviewed production-positive authority profiles
= one-shot owner custody and AVAILABLE → SPENT lifecycle
= PR6 documentation closeout / responsibility freeze
```

Stage 4B.3 PR1 responsibility-boundary work and PR2 executable mechanics
characterization remain complete historical/reference investigation. The
canonical [ADR 0026 closeout](../adr/0026_projection_trust_continuation_is_not_currently_justified.md)
records why PR3+ do not proceed. Stage 4B.5 completed in a separately owned
parallel development stream and remains technically independent from the closed
Stage 4B.3 stage.

Stage 4A introduced the stable `SemanticOutcome` core, runtime technical-status mapping, read-side / snapshot outcome mapping, and write-side admission outcome mapping.

Stage 4B builds on that semantic interpretation layer by defining how selected `SemanticOutcome`-derived evidence becomes compact, reviewable, machine-readable runtime governance evidence. Its completed delivery record is the [Stage 4B closeout](stage_4b/stage_4b_closeout.md).

Stage 4B.1 preserves bounded producer-specific execution topology separately
from primary results and receipts. Its completed delivery record is the
[Stage 4B.1 closeout](stage_4b_1/stage_4b_1_closeout.md).

Stage 4B.2 completed producer-specific single-execution measurement,
controlled PostgreSQL strategy comparison, explanatory characterization,
bounded concurrency evidence, and documentation closeout. Its entry point is
the [Stage 4B.2 implementation index](stage_4b_2/README.md).

Stage 4B.5 completed the identity-driven 18-rule Order correctness contract,
six-rule FullProof evidence producer, same-invocation runtime/write-side
propagation, explicit terminal refinement, deterministic YAML projection, and
bounded overhead characterization. Its entry point is the
[Stage 4B.5 implementation index](stage_4b_5/README.md).

Stage 4B should not reopen Stage 4A mapping scope unless receipt requirements expose a missing evidence contract.

Stage 4B should also not collapse later Stage 4 layers into the receipt boundary.

```text
Completed and later Stage 4 work remains separate:
Stage 4B.2 — Measurement Evidence — COMPLETE / CLOSED
Stage 4B.3 — Projection Trust Boundary and Continuation — COMPLETE / CLOSED AS NOT CURRENTLY JUSTIFIED
Stage 4B.5 — Order Correctness Contract v0 — COMPLETE / CLOSED
Stage 4C   — Runtime Decision Authority — COMPLETE / CLOSED
Stage 4C.5 — Compatibility / documentation closeout — COMPLETE
Stage 4D   — Strategy Selection Authority — RESPONSIBILITY RETAINED / IMPLEMENTATION DEFERRED
Stage 4E   — Same-Request Re-Invocation Authority — COMPLETE / CLOSED
```

Stage 4C is complete and closed under
[ADR 0027](../adr/0027_separate_runtime_decision_strategy_and_retry_authority.md)
and the [Stage 4C closeout](stage_4c/stage_4c_closeout.md). PR1 established the
source-grounded entry boundary; PR2 delivered the generic immutable
`RuntimeDecision` and the first Layer-1 PostgreSQL / Order write-side profile;
Stage 4C.5 confirmed compatibility through the shared producer-neutral
`SemanticOutcome` structure without adding Layer-2 or snapshot policy.

Stage 4D retains the valid responsibility for dynamic `HOW` selection, but its
implementation is deferred because current strategy composition is static, no
authorized operation has multiple dynamically eligible strategies, no reviewed
selection rule exists, and a selector would not change observable behavior.
This disposition is recorded in
[ADR 0028](../adr/0028_defer_dynamic_strategy_selection_until_multiple_eligible_execution_paths_exist.md).

Stage 4E is complete and closed under its
[implementation index](stage_4e/README.md) and
[closeout](stage_4e/stage_4e_closeout.md). It implements exactly two reviewed
positive profiles: early preparation `LOCK_TIMEOUT`, and coherent append-time
`STALE_WRITE` with typed forward version-mismatch evidence. Eligible evidence
may issue at most one authority for a fresh public-writer invocation with the
owner-retained same complete `RequestSignature`; authority is not execution or
a reusable retry budget. Everything else remains non-authorizing unless
separately reviewed.

## Boundary

The roadmap should describe project sequencing and current direction.

Implementation notes should preserve detailed execution history and stage-specific design decisions.

Deferred architecture concerns should remain in the deferred backlog only when they are not yet implemented and still have future architectural consequences.
