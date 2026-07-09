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

## Current Position

Stage 4A is complete.

The next implementation focus is:

```text
Stage 4B — DecisionReceipt / DiagnosticTrace
```

Stage 4A introduced the stable `SemanticOutcome` core, runtime technical-status mapping, read-side / snapshot outcome mapping, and write-side admission outcome mapping.

Stage 4B should build on that semantic interpretation layer by defining durable receipt and trace boundaries without reopening Stage 4A mapping scope unless receipt or trace requirements expose a missing evidence contract.

## Boundary

The roadmap should describe project sequencing and current direction.

Implementation notes should preserve detailed execution history and stage-specific design decisions.

Deferred architecture concerns should remain in the deferred backlog only when they are not yet implemented and still have future architectural consequences.
