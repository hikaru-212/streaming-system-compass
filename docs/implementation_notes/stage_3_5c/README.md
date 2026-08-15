# Stage 3.5C — Durable Read-Side Baseline

[← Back to Implementation Notes](../README.md)

This folder preserves implementation notes for the completed Stage 3.5C durable read-side baseline.

Stage 3.5C moved the read-side runtime from in-memory stores toward durable
PostgreSQL-backed projection state, progress, and replay validation. ADR 0020
repairs the original global-checkpoint assumption: the current order-state
worker uses exact-next per-order progress for
`(order_state_projection, epoch 1, order_id)`. `global_position` is lineage and
scheduling metadata, not a complete committed-history frontier.

Epoch 1 is the only currently supported production epoch. The epoch remains
part of progress identity so legacy checkpoint evidence cannot be
reinterpreted as repaired progress. Because `projection_states` remains keyed
only by `order_id`, the current runtime does not support concurrent epochs. A
future epoch change requires a human-controlled derived-state rebuild or a
separately designed versioned state store; parallel epoch rebuilds are not
implemented.

## Core Boundaries

```text
accepted history = authority
projection state = derived read model
checkpoint = operational progress metadata
per-order repaired progress = worker restart evidence
accepted-history replay = authority path
```

## Human-Controlled Cutover

Migration 006 creates empty repaired progress. Existing pre-repair projection
state cannot automatically be paired with that empty epoch-1 evidence.

The supported cutover for the current pre-production, single-developer
baseline is:

1. Preserve `order_events`; it is accepted business authority.
2. Do not seed repaired progress from legacy global checkpoints.
3. Stop the old projection worker.
4. Do not run old and repaired workers concurrently against the same
   projection state.
5. Treat pre-repair derived evidence as unqualified until replayed or rebuilt.
6. Perform a human-controlled reset of affected derived data, including, as
   applicable, `projection_states`, `projection_order_progress`, legacy
   `projection_checkpoints` for the affected worker, and
   `projection_snapshots`.
7. Do not delete or rewrite `order_events`, accepted-history identity, or
   business authority.
8. Replay accepted history through the repaired worker, then rebuild or
   revalidate snapshots.

No migration or startup path performs this reset automatically. Retaining
existing projection rows in a future production cutover requires a separately
verified per-order bootstrap procedure, which is not implemented here.

## Notes

- [PR Breakdown](./pr_breakdown.md)

## Status

Stage 3.5C is complete at the durable read-side baseline level.

Later snapshot trust, Compass Layer 2 semantic validation, worker leasing, checkpoint locking, and distributed projection orchestration remain outside this folder unless they become part of a future implementation stage.
