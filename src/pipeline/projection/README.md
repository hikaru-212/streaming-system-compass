# Projection Pipeline

[← Back to Pipeline README](../README.md)

This module defines the read-side projection runtime.

A projection is derived state.

It is built from accepted history, but it is not the source of truth.

```text
order_events = accepted-history truth
projection state = derived runtime view
per-order projection progress = operational progress evidence
checkpoint = generic legacy operational progress metadata
```

---

## Purpose

The purpose of this module is to turn accepted events into materialized read-side state.

It coordinates:

- accepted event consumption
- projection-state derivation
- checkpoint-aware progress
- replay / rebuild behavior
- storage-backed projection execution

The module started as a deterministic in-memory Stage 3 baseline and now includes a PostgreSQL-backed Stage 3.5C PR4 worker baseline plus a Stage 3.5C PR5 durable replay / rebuild validation baseline.

---

## Responsible For

This module is responsible for:

- applying accepted events to projection state
- keeping reducer logic deterministic
- coordinating worker execution
- retaining generic legacy checkpoint support for the in-memory / historical baseline
- tracking current durable order-local progress through exact-next per-order rows
- supporting replay / rebuild through the same projection semantics
- orchestrating PostgreSQL-backed projection state and per-order progress persistence

---

## Not Responsible For

This module is **not** responsible for:

- deciding whether a candidate event is legal
- admitting events into accepted history
- validating write-side transition truth
- defining domain event meaning
- acting as the accepted-history store
- choosing semantic or runtime action from read-side validation evidence
- implementing runtime decision policy
- implementing out-of-order buffering
- implementing DLQ or watermark semantics
- coordinating distributed multi-worker execution

Those responsibilities belong to other layers or later stages.

---

## Current Files

### `reducer.py`

Defines the canonical projection reducer.

The reducer is pure projection logic.

It is responsible for deriving the next `OrderState` from:

```text
current projection state
+
accepted OrderEvent
```

The reducer should remain storage-agnostic.

It should not know whether an event came from memory, PostgreSQL, Kafka, or a future replay engine.

---

### `worker.py`

Defines the deterministic in-memory projection worker baseline.

It established the original Stage 3 projection runtime shape:

```text
ProjectionRecord
→ ProjectionWorker
→ reducer
→ projection store
→ checkpoint store
```

This worker remains useful as the simple baseline for understanding projection sequencing and replay behavior.

---

### `postgres_worker.py`

Defines the PostgreSQL-backed projection worker baseline introduced in Stage 3.5C PR4.

It connects:

```text
PostgresProjectionEligibleEventSource
→ reducer
→ PostgresProjectionStore
→ PostgresProjectionProgressStore
```

inside one PostgreSQL transaction boundary.

It processes at most one accepted event per `process_next()` call.

The repaired worker progress identity is:

```text
(projection_name = order_state_projection, projection_epoch = 1, order_id)
→ last_sequence + accepted-event lineage
```

This is the only supported production projection definition and epoch. The
epoch prevents legacy progress reinterpretation; it is not a general
multi-version runtime. Because `projection_states` is keyed only by
`order_id`, a future epoch requires a human-controlled rebuild or a separately
designed versioned state store. Concurrent epoch execution and parallel epoch
rebuilds are not supported.

An event is eligible only when its order-local sequence is exactly next.
`global_position` is lineage and deterministic scheduling metadata, not a
complete committed-history frontier.

The supported production topology is:

```text
one active worker for this projection definition and epoch
```

`worker_name` is operational identity only. It is not repaired progress identity,
and changing it does not create an independently coordinated projection. The
worker does not implement leasing, claiming, or distributed multi-worker
coordination.

---

### `replay_validator.py`

Defines the durable replay / rebuild validation baseline introduced in Stage 3.5C PR5.

It compares accepted-history replay through the canonical reducer with persisted projection state.

The minimal validation statuses are:

```text
MATCH
MISSING_PROJECTION
DRIFT
NO_ACCEPTED_HISTORY
```

This validator does not mutate accepted history, rebuild projection state
automatically, advance progress, or make runtime recovery decisions. Stage 4A
provides a separate adapter from `ReplayValidationResult` to `SemanticOutcome`;
the validator itself remains an evidence producer.

Its successful `MATCH` is one point-in-time state-consistency observation. It
does not inspect repaired per-order progress and is not a continuation-capable
validated projection boundary. See the
[Stage 4B.3 responsibility boundary](../../../docs/implementation_notes/stage_4b_3/projection_trust_continuation_boundary.md).

---

## PostgreSQL-Backed Projection Flow

The Stage 3.5C PR4 durable projection flow is:

```text
1. discover a currently visible exact-next event for one order
2. load current per-order progress
3. load current projection state for the event's order_id
4. apply the canonical reducer
5. save projection state
6. advance exact-next per-order progress
7. commit projection state and progress together
```

The physical flow is:

```text
order_events
→ PostgresProjectionEligibleEventSource
→ ProjectionEventRecord
→ PostgresProjectionWorker
→ reduce_order_event(...)
→ PostgresProjectionStore
→ PostgresProjectionProgressStore
```

---

## Durable Replay Validation Flow

The Stage 3.5C PR5 durable replay validation flow is:

```text
1. choose an order_id
2. load accepted history for that order
3. replay events through the canonical reducer
4. produce expected OrderState
5. load persisted projection state
6. compare expected state with persisted state
7. return a minimal validation result
```

The purpose is to answer:

```text
Does persisted projection state still match accepted-history replay?
```

Stage 4A can map this evidence into `SemanticOutcome`, and Stage 4B can map it
into `DecisionReceipt`. Neither mapping makes the observation continuing trust
or decides what runtime action should follow. Runtime decision and recovery
policy remain separately owned.

---

## Cursor Boundary

The repaired PostgreSQL worker does not use a scalar global checkpoint.

The key distinction is:

```text
aggregate-local sequence
≠
global event-log position
≠
worker checkpoint cursor
```

`order_events.sequence` answers:

```text
Is this event the next legal event for this order?
```

`order_events.global_position` now answers:

```text
What unique storage coordinate and scheduling lineage does this event carry?
```

`projection_order_progress.last_sequence` answers:

```text
What local sequence was durably applied for this projection, epoch, and order?
```

For the full decision, see:

- [Global-Position Projection Worker Boundary](../../../docs/boundary_notes/global_position_projection_worker_boundary.md)

---

## Transaction Boundary

The PostgreSQL-backed worker owns the read-side transaction boundary.

It persists:

```text
projection state
+
per-order progress
```

inside one transaction.

If progress saving fails after projection state is saved, the whole transaction rolls back.

If projection state saving fails, per-order progress is not advanced.

This prevents inconsistent read-side states such as:

```text
projection state updated
progress not advanced
```

or:

```text
progress advanced
projection state not updated
```

---

## Fail-Fast Policy

The PostgreSQL-backed worker intentionally does not silently repair
projection-state / per-order-progress mismatch.

If existing projection state cannot apply the event selected by repaired
progress, the reducer fails fast rather than silently skipping.

This is a baseline correctness decision.

Repair, rebuild, and recovery policy belong to later stages.

---

## Current Non-goals

The current projection pipeline does not implement:

- projection trust continuation or durable trust checkpoints
- automatic repair or rebuild from `SemanticOutcome` / `DecisionReceipt`
- runtime decision policy
- out-of-order buffering
- DLQ
- watermark semantics
- worker leasing
- checkpoint row locking
- distributed multi-worker coordination
- multi-region / sharded / multi-primary cursor models

---

## Current Stage Status

```text
Stage 3 — In-memory Projection Runtime Baseline ✅
Stage 3.5C PR1 — Durable Read-Side Schema Baseline ✅
Stage 3.5C PR2 — PostgresProjectionStore ✅
Stage 3.5C PR3 — PostgresCheckpointStore ✅
Stage 3.5C PR4 — Global-Position Projection Worker Baseline ✅
Stage 3.5C PR5 — Durable Replay / Rebuild Validation Baseline ✅
ADR 0020 Repair — Per-Order Projection Progress and Order-Local Snapshot Tails ✅
```

---

## Next Step

The current correctness model uses `projection_order_progress` and remains
limited to one active worker for the supported projection definition and
epoch. Multi-worker leasing, coordination, and production recovery policy are
deferred. Projection state and snapshots remain derived; accepted history
remains authoritative.

---

## Summary

The projection pipeline converts accepted history into derived runtime state.

The reducer defines the projection semantics.

The worker defines the execution order.

The stores preserve derived state and operational progress.

The event log remains the source of truth.
