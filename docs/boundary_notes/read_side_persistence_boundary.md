# Read-Side Persistence Boundary

[← Back to Boundary Notes Index](README.md)

## Purpose

This note defines the Stage 3.5C PR1 boundary between accepted history, derived projection state, checkpoint progress, and future PostgreSQL-backed projection-worker behavior.

It exists to prevent the read-side durable schema from accidentally redefining the source of truth.

It also records the checkpoint cursor decision made during PR1 planning:

> a projection worker checkpoint must not use aggregate-local `order_events.sequence` as if it were a global event-log offset.

---

## Status

Stage 3.5C PR1 planning / durable read-side schema boundary.

This note is intentionally written before `PostgresProjectionStore`, `PostgresCheckpointStore`, or the PostgreSQL-backed projection worker is implemented.

---

## Core Boundary

The durable read-side has three different concepts that must remain separate.

```text
order_events
= accepted-history source of truth

projection_states
= derived runtime view

projection_checkpoints
= worker progress metadata
```

Only `order_events` is the accepted-history truth source.

`projection_states` and `projection_checkpoints` are durable read-side support tables.

They are allowed to be rebuilt, reset, or corrected from accepted history.

---

## Boundary 1: Accepted History vs Derived State

### Accepted History

`order_events` stores admitted facts.

It answers:

> what happened and was accepted by the write side?

Accepted history is replayable and should remain the authoritative source.

### Derived State

`projection_states` stores the latest derived state for efficient read-side access.

It answers:

> what does accepted history currently project to?

It must not answer:

> what is the sovereign truth if accepted history disagrees?

If there is disagreement, accepted history wins.

---

## Boundary 2: Projection State vs Checkpoint State

### `projection_states`

Projection state is per-order derived runtime state.

A row may record:

- `order_id`
- `status`
- `total_amount`
- `paid_amount`
- `version`
- `last_sequence`
- `updated_at`

Here, `last_sequence` is valid because each projection state row is scoped to one order.

It means:

> this order's derived state has processed accepted history up to this aggregate-local sequence.

### `projection_checkpoints`

Checkpoint state is worker-level progress metadata.

It records where a worker stopped while scanning accepted history.

It is not per-order business state.

It must not use aggregate-local `sequence` as if it were a global cursor.

---

## Boundary 3: Local Sequence vs Worker Cursor

The write-side event table uses:

```text
(order_id, sequence)
```

This is aggregate-local ordering.

It protects stream continuity for one order.

Example:

```text
Order A sequence 1, 2
Order B sequence 1, 2
Order C sequence 1, 2
```

This is correct for aggregate replay.

It is not a global event-log offset.

A background projection worker needs a cursor over the whole accepted-history stream, not only one order stream.

Therefore, this PR1 boundary rule is required:

> `projection_checkpoints` must not store `last_processed_sequence` as the worker checkpoint.

That name would incorrectly imply that `order_events.sequence` is a global worker offset.

---

## PR1 Checkpoint Decision

For Stage 3.5C PR1, checkpoints should use a generic cursor shape:

```text
cursor_kind
cursor_value
```

Suggested baseline:

```sql
cursor_kind TEXT NOT NULL DEFAULT 'UNSPECIFIED',
cursor_value TEXT NOT NULL DEFAULT ''
```

Allowed `cursor_kind` values may include:

```text
UNSPECIFIED
APPENDED_AT
EVENT_ID
GLOBAL_POSITION
```

This decision keeps the schema honest.

The project has not yet implemented the PostgreSQL-backed projection worker.

Therefore, PR1 should not force a final event-log scanning strategy.

---

## Why `cursor_kind` Is Better Than `last_processed_sequence`

`last_processed_sequence` is too specific and semantically wrong for a multi-order event log.

It suggests:

```text
sequence = worker offset
```

But in the current schema:

```text
sequence = aggregate-local position
```

`cursor_kind` is better because it states:

```text
this checkpoint stores a worker cursor
```

without pretending the cursor is already a global numeric sequence.

It also allows the future worker to choose among several strategies.

---

## Candidate Cursor Strategies

### 1. `APPENDED_AT`

The worker scans by `order_events.appended_at`.

This avoids adding a global event-log position in the write-side table.

Trade-offs:

- same timestamp tie-breakers must be handled
- late transaction visibility must be handled
- overlap scanning may be required
- duplicate event handling may be required
- worker code becomes more complex

This strategy favors write-side minimalism but increases read-side worker complexity.

### 2. `GLOBAL_POSITION`

The worker scans by a global monotonic position.

This likely requires adding a future column such as:

```text
order_events.global_position
```

Trade-offs:

- introduces a global event-log ordering point during insert
- simplifies worker scanning
- simplifies checkpoint persistence
- improves deterministic replay and auditability
- makes Layer 2 validation easier to reason about

This strategy favors deterministic read-side processing over maximum write throughput.

### 3. `EVENT_ID`

The worker uses event identity as a cursor or tie-breaker.

This should be used carefully.

Event identity alone should not be assumed to represent commit order unless the chosen identity policy explicitly guarantees that property.

### 4. CDC / WAL-Based Stream

A production-grade alternative is to consume committed changes through logical replication or CDC.

This can provide committed-order streaming without application-level polling.

It is intentionally outside Stage 3.5C PR1.

---

## Preferred Future Direction

The preferred future direction is likely `GLOBAL_POSITION`.

This project prioritizes:

- deterministic replay
- auditability
- semantic validation
- Compass Layer 2 drift detection
- action-safety reasoning

over maximum write throughput.

For this project, a small global ordering cost is acceptable if it gives the read-side worker a simple, stable, and testable cursor.

However, PR1 should still use `cursor_kind` / `cursor_value` because the final worker strategy belongs to the PostgreSQL-backed worker PR, not the schema-baseline PR.

---

## Boundary Rules

### Rule 1: Accepted history remains sovereign

`order_events` is the accepted-history truth source.

No read-side table should override it.

### Rule 2: Projection state is rebuildable

`projection_states` must remain derived state.

If corrupted or stale, it should be rebuilt from accepted history through the canonical reducer.

### Rule 3: Checkpoint state is operational

`projection_checkpoints` is worker progress metadata.

It is not business correctness.

### Rule 4: Local sequence is not global cursor

`order_events.sequence` is scoped by `order_id`.

It must not be used as a worker-wide checkpoint offset.

### Rule 5: Reducer remains canonical

PostgreSQL storage should persist derived state and checkpoint progress.

It should not introduce a second projection algorithm.

The canonical projection reducer remains the source of derived-state logic.

### Rule 6: Final worker cursor strategy is deferred

PR1 should define a cursor-compatible checkpoint schema.

The final event-log scanning strategy should be decided when the PostgreSQL-backed projection worker is introduced.

---

## What Python Owns

Python continues to own:

- reducer logic
- projection-state derivation
- worker orchestration
- replay / rebuild flow
- checkpoint update semantics
- future Layer 2 comparison logic
- final interpretation of cursor strategy

---

## What PostgreSQL Owns

PostgreSQL should own:

- durable storage of projection state
- durable storage of worker checkpoint state
- minimum valid row shape
- exact numeric representation
- status vocabulary constraints
- checkpoint cursor vocabulary constraints
- restart-surviving persistence

PostgreSQL should not own:

- projection business meaning
- replay correctness proof
- Layer 2 semantic validation
- runtime decision policy
- action safety

---

## Non-goals

Stage 3.5C PR1 does not implement:

- `PostgresProjectionStore`
- `PostgresCheckpointStore`
- PostgreSQL-backed projection worker
- final cursor strategy
- `order_events.global_position`
- snapshot trust
- replay optimization
- Compass Layer 2
- `SemanticOutcome`
- database role hardening
- CDC / WAL streaming

---

## Suggested Test Implications

The schema tests for PR1 should verify:

- valid projection state can be inserted
- invalid projection status is rejected
- negative money values are rejected
- paid amount greater than total amount is rejected
- negative projection version is rejected
- negative aggregate-local `last_sequence` is rejected
- valid checkpoint can be inserted
- empty worker name is rejected
- invalid `cursor_kind` is rejected
- flexible `cursor_value` can store a token

The tests should not verify:

```text
negative last_processed_sequence is rejected
```

because that field should not exist.

---

## Future ADR Candidate

When the PostgreSQL-backed projection worker is introduced, the project should likely add an ADR such as:

```text
ADR 0013 — Projection Worker Cursor Strategy
```

That ADR should compare:

- appended-at polling
- global event-log position
- event-id tie-breakers
- CDC / WAL-based streaming

The likely decision is:

```text
GLOBAL_POSITION
```

if the project continues to prioritize deterministic replay, auditability, and semantic correctness over maximum write throughput.

---

## Closing Rule

The most important read-side persistence boundary is:

> Durable read-side state helps the system observe and recover.  
> It does not become the system's truth.

The most important checkpoint boundary is:

> A worker checkpoint is a global scan cursor, not an aggregate-local sequence.
