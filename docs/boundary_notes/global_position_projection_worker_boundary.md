# Global-Position Projection Worker Boundary

[← Back to Boundary Notes](README.md)

## Purpose

This note defines the Stage 3.5C PR4 boundary for introducing a PostgreSQL-backed projection worker that consumes accepted events from durable history.

The main question is:

> How should the durable projection worker know which accepted events it has already processed?

This is not only a worker implementation detail.

It affects:

- `order_events` schema
- projection checkpoint semantics
- accepted-history scan order
- deterministic replay
- future Compass Layer 2 drift detection
- read-side transaction atomicity

Stage 3.5C PR4 should therefore make the worker cursor strategy explicit before implementing the PostgreSQL-backed worker.

---

## Problem

The durable write-side already stores accepted events in `order_events`.

Each accepted event currently has an aggregate-local sequence:

```text
(order_id, sequence)
```

This sequence is correct for protecting per-order stream continuity.

Example:

```text
order-a sequence 1
order-a sequence 2

order-b sequence 1
order-b sequence 2
```

However, a projection worker does not consume one aggregate in isolation.

A projection worker consumes accepted history as a stream of events across many orders.

It needs to answer a different question:

> What is the next accepted event after the last event this worker processed?

Aggregate-local sequence cannot answer that question globally.

If a checkpoint stored only:

```text
last_processed_sequence = 2
```

the worker would not know whether that means:

```text
order-a sequence 2
```

or:

```text
order-b sequence 2
```

or whether another order has an unprocessed event with the same local sequence.

Therefore, `order_events.sequence` must not be used as the durable projection worker checkpoint.

---

## Key Distinction

Stage 3.5C PR4 must preserve this distinction:

```text
aggregate-local sequence
≠
global event-log position
≠
worker checkpoint cursor
```

### Aggregate-Local Sequence

```text
order_events.sequence
```

Purpose:

```text
protect per-order causal continuity
```

Scope:

```text
one order / one aggregate stream
```

Example:

```text
(order_id = order-a, sequence = 1)
(order_id = order-a, sequence = 2)
```

This is a write-side and reducer continuity concept.

It answers:

> Is this event the next legal event for this order?

---

### Global Event-Log Position

```text
order_events.global_position
```

Purpose:

```text
provide a durable total order for accepted-history consumption
```

Scope:

```text
all accepted events in order_events
```

Example:

```text
global_position 1: order-a CREATED
global_position 2: order-b CREATED
global_position 3: order-a PAID
global_position 4: order-b PAID
```

This is a projection worker consumption concept.

It answers:

> Which accepted event comes next in the global event log?

---

### Worker Checkpoint Cursor

```text
projection_checkpoints.cursor_kind
projection_checkpoints.cursor_value
```

Purpose:

```text
remember worker progress
```

For PR4, the worker should persist:

```text
cursor_kind = GLOBAL_POSITION
cursor_value = latest processed global_position
```

This is operational progress metadata.

It is not business truth.

It answers:

> Where should this worker resume after restart?

---

## Decision

Stage 3.5C PR4 should use:

```text
GLOBAL_POSITION
```

as the durable projection worker cursor strategy.

This implies adding a global event-log position to `order_events`.

The intended query shape is:

```sql
SELECT *
FROM order_events
WHERE global_position > %s
ORDER BY global_position ASC
LIMIT %s;
```

The worker checkpoint should then persist:

```text
cursor_kind = GLOBAL_POSITION
cursor_value = <latest processed global_position>
```

---

## Why Not `order_events.sequence`

`order_events.sequence` is aggregate-local.

It protects order-level causality.

It is not unique across the whole event log.

Using it as a worker checkpoint would confuse:

```text
per-order stream progress
```

with:

```text
global accepted-history consumption progress
```

That would create an ambiguous and unsafe projection-worker resume boundary.

---

## Why Not `APPENDED_AT`

A timestamp cursor can preserve write-side throughput because it does not introduce a global ordering column.

However, timestamp-based polling introduces additional correctness and operational concerns:

- multiple events may share the same timestamp precision
- transaction commit order may differ from timestamp assignment order
- late-committed transactions can be skipped if the worker advances past their timestamp
- safe polling often requires overlap scans and de-duplication
- worker logic becomes more complex

Timestamp cursor strategies may be reasonable for log analytics, clickstream, or high-throughput eventually-consistent systems.

This project currently prioritizes:

```text
deterministic replay
auditability
Compass Layer 2 future validation
clear read-side correctness boundaries
```

Therefore, PR4 should not choose timestamp polling as the first durable worker strategy.

---

## Why Not `EVENT_ID`

An event ID is useful as a durable identity.

However, an event ID alone does not imply a stable ordering unless the ID generation strategy itself is ordered and explicitly adopted as the event-log cursor.

Current durable event identity is not intended to serve as a global event-log ordering mechanism.

`EVENT_ID` remains a possible future cursor kind, but PR4 should not depend on it for ordered consumption.

---

## Why `GLOBAL_POSITION`

`GLOBAL_POSITION` gives the projection worker a simple and explicit durable progress model.

Advantages:

- worker query is simple
- checkpoint meaning is clear
- replay order is deterministic
- future rebuild validation is easier
- future Compass Layer 2 drift comparison has a stable accepted-history order
- checkpoint progress can be represented as a single global cursor

Trade-off:

- write-side accepted event insertion gains a global ordering point
- extremely high-throughput systems may later need a more advanced strategy

For this project, that trade-off is acceptable.

The project is focused on correctness, semantic governance, auditability, and deterministic replay rather than maximum write throughput.

---

### Scaling Note

`GLOBAL_POSITION` assumes a single-primary event log where PostgreSQL can assign a stable global ordering point.

If future requirements evolve toward multi-region, sharded, or multi-primary event logs, this cursor model may need to evolve into a composite cursor such as:

```test
(cluster_id, local_position)

or:

(stream_partition, local_position)
```

This is intentionally out of scope for Stage 3.5C PR4.

The purpose of PR4 is to establish the first deterministic durable projection worker baseline, not to solve distributed event-log ordering across clusters or partitions.

---

## PR4 Boundary

Stage 3.5C PR4 should introduce the first PostgreSQL-backed projection worker baseline.

The intended flow is:

```text
order_events
→ PostgreSQL projection event source
→ canonical reducer
→ PostgresProjectionStore
→ PostgresCheckpointStore
```

The worker should:

1. load current checkpoint
2. load the next accepted event after the checkpoint
3. load current projection state for the event's `order_id`
4. apply the canonical reducer
5. save projection state
6. save checkpoint progress
7. commit both updates together

---

## Transaction Boundary

PR4 must preserve read-side atomicity.

The worker must persist:

```text
projection state
+
checkpoint progress
```

inside one transaction.

If projection state is saved but checkpoint saving fails, the transaction should roll back.

If checkpoint progress is saved but commit fails, the transaction should roll back.

This prevents inconsistent states such as:

```text
projection state updated
checkpoint not advanced
```

or:

```text
checkpoint advanced
projection state not updated
```

This read-side transaction boundary is the read-side equivalent of the Stage 3.5B write-side atomicity boundary:

```text
write side:
accepted event append
+
idempotency record write

read side:
projection state update
+
checkpoint progress update
```

---

## What PR4 Should Add

Stage 3.5C PR4 should add:

- `order_events.global_position`
- migration for the global event-log position
- PostgreSQL projection event source
- tests for loading accepted events after a global position
- PostgreSQL-backed projection worker baseline
- tests for worker processing
- tests for projection-state and checkpoint atomicity
- documentation updates for the new worker boundary

---

## What PR4 Should Not Add

Stage 3.5C PR4 should not implement:

- Snapshot Trust Contract
- durable replay / rebuild validation
- Compass Layer 2 validation
- structured `SemanticOutcome`
- runtime decision policy
- out-of-order buffering
- DLQ
- watermark semantics
- distributed multi-worker coordination
- production database role hardening
- append-only trigger enforcement
- Stage 3.5E permission hardening

Those belong to later stages.

---

## Relationship to Existing Boundaries

### Relation to Projection Store

`PostgresProjectionStore` persists derived projection state.

It does not decide worker progress.

### Relation to Checkpoint Store

`PostgresCheckpointStore` persists worker progress metadata.

It does not scan accepted history or decide the cursor strategy by itself.

### Relation to Projection Worker

The projection worker owns orchestration.

It coordinates:

```text
event source
+ reducer
+ projection store
+ checkpoint store
+ transaction boundary
```

### Relation to Accepted History

`order_events` remains the source of truth.

Projection state remains derived and rebuildable.

Checkpoint state remains operational progress metadata.

---

## Future Work

After PR4, the next likely work is durable replay / rebuild validation.

That later stage should prove:

```text
accepted history replay
=
durable projection state
```

or produce evidence when they differ.

Future stages may also revisit:

- batch processing
- out-of-order handling
- rebuild orchestration
- snapshot trust
- projection drift detection
- Compass Layer 2 validation
- performance impact of global ordering
- alternative cursor strategies if the workload changes

---

## Summary

Stage 3.5C PR4 should use `GLOBAL_POSITION` as the first durable projection worker cursor strategy.

The essential rule is:

```text
Aggregate-local sequence protects per-order causality.
Global position protects worker-level accepted-history consumption.
Checkpoint cursor records worker progress.
```

The database stores accepted history.

The projection worker consumes accepted history in global order.

The checkpoint records where the worker should resume.
