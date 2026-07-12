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

## Current Position

Stage 4A is complete.

Stage 4 Interlude PR0 — test helper consolidation before Stage 4B — is complete.

The next implementation focus is:

```text
Stage 4B — DecisionReceipt / Runtime Evidence Record
```

Stage 4A introduced the stable `SemanticOutcome` core, runtime technical-status mapping, read-side / snapshot outcome mapping, and write-side admission outcome mapping.

Stage 4B builds on that semantic interpretation layer by defining how selected `SemanticOutcome`-derived evidence becomes compact, reviewable, machine-readable runtime governance evidence.

Stage 4B should not reopen Stage 4A mapping scope unless receipt requirements expose a missing evidence contract.

Stage 4B should also not collapse later Stage 4 layers into the receipt boundary.

```test
Later Stage 4 work remains separate:
Stage 4B.1 — DiagnosticTrace / ResolutionTrace
Stage 4B.2 — Measurement Matrix / Cost Evidence Inventory
Stage 4B.5 — Order Domain Policy Contract v0
Stage 4C   — RuntimeDecisionPolicy
Stage 4D   — StrategySelector / Fast-Path Health Policy
Stage 4E   — Retry Governance / Attempt Classification
```

## Boundary

The roadmap should describe project sequencing and current direction.

Implementation notes should preserve detailed execution history and stage-specific design decisions.

Deferred architecture concerns should remain in the deferred backlog only when they are not yet implemented and still have future architectural consequences.