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
- [Stage 4C — Runtime Decision Authority — docs-first entry](./stage_4c/)

## Current Position

Stage 4A, Stage 4B PR1–PR7, Stage 4B.1 PR1–PR7, Stage 4B.2 PR1–PR8, and
Stage 4B.5 through PR8 are complete. Stage 4B.2 and Stage 4B.5 are closed.

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
Stage 4C   — Runtime Decision Authority
Stage 4C.5 — Layer 1 / Layer 2 Outcome Alignment
Stage 4D   — Strategy Selection Authority
Stage 4E   — Retry / Attempt Authorization
```

Stage 4C is now in docs-first boundary definition under
[ADR 0027](../adr/0027_separate_runtime_decision_strategy_and_retry_authority.md).
No Stage 4C production implementation is claimed. Its first design center is
live, in-memory `SemanticOutcome` plus terminally applicable exact rule
refinement when source-applicable; `DecisionReceipt` remains durable governance
evidence but is not required for the first live hot path.

## Boundary

The roadmap should describe project sequencing and current direction.

Implementation notes should preserve detailed execution history and stage-specific design decisions.

Deferred architecture concerns should remain in the deferred backlog only when they are not yet implemented and still have future architectural consequences.
