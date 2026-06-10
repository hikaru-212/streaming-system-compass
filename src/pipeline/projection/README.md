# Projection Pipeline

[← Back to Pipeline README](../README.md)

This module defines the read-side projection runtime.

A projection is derived state.

It is built from accepted history, but it is not the source of truth.

```text
order_events = accepted-history truth
projection state = derived runtime view
checkpoint = operational progress metadata
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
- tracking worker progress through checkpoints
- supporting replay / rebuild through the same projection semantics
- orchestrating PostgreSQL-backed projection state and checkpoint persistence

---

## Not Responsible For

This module is **not** responsible for:

- deciding whether a candidate event is legal
- admitting events into accepted history
- validating write-side transition truth
- defining domain event meaning
- acting as the accepted-history store
- implementing Compass Layer 2 validation
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
PostgresProjectionEventSource
→ reducer
→ PostgresProjectionStore
→ PostgresCheckpointStore
```

inside one PostgreSQL transaction boundary.

It processes at most one accepted event per `process_next()` call.

The worker checkpoint strategy is:

```text
cursor_kind = GLOBAL_POSITION
cursor_value = latest processed order_events.global_position
```

This worker assumes:

```text
one active process per worker_name
```

It does not implement worker leasing, checkpoint row locking, or distributed multi-worker coordination.

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

This validator does not mutate accepted history, rebuild projection state automatically, advance checkpoint progress, produce `SemanticOutcome`, or make runtime recovery decisions.

---

## PostgreSQL-Backed Projection Flow

The Stage 3.5C PR4 durable projection flow is:

```text
1. load checkpoint progress
2. load the next accepted event after the checkpoint
3. load current projection state for the event's order_id
4. apply the canonical reducer
5. save projection state
6. save checkpoint progress
7. commit projection state and checkpoint progress together
```

The physical flow is:

```text
order_events
→ PostgresProjectionEventSource
→ ProjectionEventRecord
→ PostgresProjectionWorker
→ reduce_order_event(...)
→ PostgresProjectionStore
→ PostgresCheckpointStore
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

It does not answer what runtime decision should be made if drift is detected.

That belongs to later Compass Layer 2, structured outcome, runtime decision, and recovery policy work.

---

## Cursor Boundary

Stage 3.5C PR4 uses `GLOBAL_POSITION` as the first durable worker cursor strategy.

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

`order_events.global_position` answers:

```text
Which accepted event comes next in the global event log?
```

`projection_checkpoints.cursor_value` answers:

```text
Where should this worker resume after restart?
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
checkpoint progress
```

inside one transaction.

If checkpoint saving fails after projection state is saved, the whole transaction rolls back.

If projection state saving fails, checkpoint progress is not advanced.

This prevents inconsistent read-side states such as:

```text
projection state updated
checkpoint not advanced
```

or:

```text
checkpoint advanced
projection state not updated
```

---

## Fail-Fast Policy

The PostgreSQL-backed worker intentionally does not silently repair projection-state / checkpoint mismatch.

If the durable projection state is already ahead of the checkpoint, the reducer should fail fast rather than silently skip and advance.

This is a baseline correctness decision.

Repair, rebuild, and recovery policy belong to later stages.

---

## Current Non-goals

The current projection pipeline does not implement:

- durable replay / rebuild validation
- Snapshot Trust Contract
- Compass Layer 2 projection-drift validation
- structured `SemanticOutcome`
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
```

---

## Next Step

The next projection-related milestone is:

```text
Stage 3.5C PR5 — Durable Replay / Rebuild Validation
```

That work should prove:

```text
accepted history replay
=
durable projection state
```

or produce explicit evidence when they differ.

It should not turn projection state into the source of truth.

---

## Summary

The projection pipeline converts accepted history into derived runtime state.

The reducer defines the projection semantics.

The worker defines the execution order.

The stores preserve derived state and operational progress.

The event log remains the source of truth.
