# Stage 3.5D — Snapshot Trust Contract / Replay Efficiency

[← Back to Implementation Notes](../README.md)

This folder preserves implementation notes for the completed Stage 3.5D snapshot trust and replay-efficiency baseline.

Stage 3.5D introduced projection snapshot trust boundaries, snapshot storage, snapshot-assisted replay validation, snapshot-assisted state resolution, and the aggregate snapshot deferral decision.

ADR 0020 repairs the projection snapshot tail contract. Current validator and
resolver tails are scoped to the snapshot `order_id`, begin after
`source_event_sequence`, and require contiguous order-local sequence.
`source_global_position` remains lineage rather than tail-completeness proof.

## Core Boundaries

```text
accepted history = authority
snapshot = derived state compression
fast path = qualified snapshot + tail replay + trust checks
authority path = full accepted-history replay
```

## Notes

- [PR Breakdown](./pr_breakdown.md)
- [Snapshot Payload Hashing](./snapshot_payload_hashing.md)
- [Snapshot Generation Policy](./snapshot_generation_policy.md)
- [Projection Snapshot Schema Baseline](./projection_snapshot_schema_baseline.md)
- [Postgres Projection Snapshot Store](./postgres_projection_snapshot_store.md)
- [Projection Snapshot-Assisted Replay Validator](./projection_snapshot_assisted_replay_validator.md)
- [Projection Snapshot-Assisted State Resolver](./projection_snapshot_assisted_state_resolver.md)
- [Aggregate Snapshot Trust Deferral](./aggregate_snapshot_trust_deferral.md)

## Status

Stage 3.5D is complete at the read-side projection snapshot trust / replay-efficiency baseline level.

Write-side aggregate snapshot storage and snapshot-assisted write-side rehydration are explicitly deferred because they may influence future command validation and accepted-history admission.
