# Stage 3.5C PR Breakdown

[← Back to Stage 3.5C Notes](README.md)

## Purpose

This note preserves the completed implementation sequence for:

```text
Stage 3.5C — Durable Read-Side Baseline
```

The goal of Stage 3.5C was to move the read-side runtime from in-memory stores toward durable PostgreSQL-backed projection state, checkpoint progress, global-position consumption, and replay / rebuild validation.

This note is intentionally more detailed than the project roadmap. It preserves PR-level implementation history, boundary decisions, tests, and non-goals that are too detailed for the roadmap.

---

## Stage Principle

```text
accepted history = authority
projection state = derived read model
checkpoint = operational progress metadata
accepted-history replay = authority path
```

---

## Completed PR Sequence

```text
PR0 — Durable Order Event Vocabulary Hardening
PR1 — Durable Read-Side Schema Baseline
PR2 — PostgresProjectionStore
PR3 — PostgresCheckpointStore
PR4 — Global-Position Projection Worker Baseline
PR5 — Durable Replay / Rebuild Validation Baseline
PR6 — Stage 3.5C Documentation and Completion Alignment
```

---

## PR Details

### PR0 — Durable Order Event Vocabulary Hardening

#### Status

Completed.

#### Goal

Finalize the durable `order_events` vocabulary and selected schema constraints before Stage 3.5C durable read-side persistence starts depending on stored event records.

#### Why

Stage 3.5B established the durable write-side baseline. Before read-side projection and checkpoint persistence consume durable accepted events, the stored event vocabulary should be explicit and stable.

This PR0 is a schema-hardening pass, not the durable read-side baseline itself.

#### Completed Scope

- normalize durable `event_type` values from lowercase to uppercase:
  - `created` → `CREATED`
  - `paid` → `PAID`
- align Python `OrderEventType` enum values with the database vocabulary
- update the `order_events.event_type` CHECK constraint
- add `proof_prev_status` CHECK constraint for `INIT`, `CREATED`, and `PAID`
- rename the order stream-position unique constraint to `uq_order_events_order_id_sequence`
- add PostgreSQL schema-constraint tests for rejected lowercase event types and invalid proof statuses

#### Boundary Decision

Durable accepted-event vocabulary now uses uppercase enum-style values:

```text
CREATED
PAID
```

`CommandType` remains lowercase because it represents request/action identity for idempotency records, not accepted event identity.

#### Non-goals

This PR0 does not implement:

- durable projection state
- durable checkpoint state
- `PostgresProjectionStore`
- `PostgresCheckpointStore`
- snapshot or replay optimization
- Compass Layer 2 validation

---

### PR1 — Durable Read-Side Schema Baseline

#### Status

Completed.

#### Goal

Define the PostgreSQL schema boundary for durable read-side state before implementing PostgreSQL-backed read-side stores.

#### Why

Stage 3.5C should first clarify what durable derived state and checkpoint progress look like at the database boundary.

This PR should answer:

```text
Where does derived projection state live?
Where does worker progress live?
Which database constraints protect the minimum valid shape of read-side state?
```

It should not yet answer:

```text
How does the Python projection store persist state?
How does the PostgreSQL-backed worker scan accepted history?
How does Compass Layer 2 validate projection drift?
```

#### Completed Scope

- add `projection_states` table
- add `projection_checkpoints` table
- define schema constraints for projection status, money values, version, sequence, and identity fields
- define checkpoint `cursor_kind` / `cursor_value` alignment constraints
- add schema-constraint integration tests
- update CI to apply the durable read-side migration
- document the durable read-side schema boundary
- keep accepted history as the source of truth
- preserve the distinction between physical shape constraints and future Compass Layer 2 semantic-drift validation

#### Candidate Tables

`projection_states` may include:

```text
order_id
status
total_amount
paid_amount
version
last_sequence
updated_at
```

`projection_checkpoints` includes:

```text
worker_name
cursor_kind
cursor_value
updated_at
```

PR1 deliberately avoids `last_processed_sequence` because `order_events.sequence` is aggregate-local, not a global worker offset.

The final checkpoint scanning strategy is deferred until the PostgreSQL-backed projection worker is introduced. The schema supports `UNSPECIFIED`, `APPENDED_AT`, `EVENT_ID`, and `GLOBAL_POSITION` cursor kinds without committing PR1 to one worker strategy.

#### Boundary Decision

PR1 lets PostgreSQL protect physical shape and checkpoint cursor consistency.

It intentionally does not add cross-field domain constraints such as:

```text
CREATED implies paid_amount = 0
PAID implies paid_amount = total_amount
```

Those are semantic projection-drift concerns for the canonical reducer and future Compass Layer 2 validation, not PR1 database CHECK constraints.

#### Non-goals

PR1 does not implement:

- `PostgresProjectionStore`
- `PostgresCheckpointStore`
- PostgreSQL-backed projection worker
- durable replay / rebuild flow
- Compass Layer 2 validation
- Snapshot Trust Contract
- retry reason classification
- Stage 3.5E database role hardening

---

### PR2 — PostgresProjectionStore

#### Status

Completed.

#### Goal

Implement PostgreSQL-backed persistence for derived projection state.

#### Why

The current Stage 3 projection state exists only in the in-memory baseline.

PR2 moves projection state toward durable persistence while preserving the rule that projection state is derived and rebuildable, not the source of truth.

#### Completed Scope

- implement `PostgresProjectionStore`
- support loading projection state by `order_id`
- support inserting or updating projection state through `projection_states`
- preserve Decimal money values across write / read
- preserve status and version semantics
- persist `projection_states.last_sequence` from `OrderState.version`
- support `clear()` for tests and future rebuild paths
- add integration tests for save / load / upsert / clear behavior
- verify multiple orders remain independent
- verify stored projection state survives the PostgreSQL round trip
- verify caller-owned rollback restores connection usability after constraint failure

#### Boundary Decision

`PostgresProjectionStore` persists derived projection state only.

It does not:

- run the projection reducer
- decide event sequencing policy
- manage checkpoint progress
- validate semantic drift
- decide replay / rebuild orchestration
- commit or rollback transactions

Transaction ownership remains outside the store so that a later PostgreSQL-backed projection worker can commit projection-state updates and checkpoint progress atomically.

At the current projection model level:

```text
OrderState.version
= last aggregate-local accepted event sequence reflected by this projection state
```

Therefore PR2 persists:

```text
projection_states.last_sequence = state.version
```

This mapping should be revisited during Stage 3.5D if snapshot trust, reducer-version tracking, projection schema versioning, or projection-row versioning require separating source event sequence from projection version metadata.

#### Non-goals

PR2 does not implement:

- checkpoint persistence
- PostgreSQL-backed projection worker
- replay / rebuild orchestration
- Layer 2 validation
- snapshot optimization
- production database roles

---

### PR3 — PostgresCheckpointStore

#### Status

Completed.

#### Goal

Implement PostgreSQL-backed persistence for projection worker progress.

#### Why

A durable projection worker needs a durable checkpoint boundary so it can resume processing after restart.

Checkpoint state is operational progress metadata.

It is not business truth.

#### Main Work

- implement `PostgresCheckpointStore`
- support loading checkpoint by worker name
- support inserting or updating checkpoint progress
- support missing-checkpoint behavior
- add integration tests for checkpoint persistence
- verify checkpoint state survives a new database connection

#### Non-goals

PR3 does not implement:

- projection-state persistence
- full PostgreSQL-backed worker orchestration
- global ordering redesign
- Layer 2 validation
- snapshot optimization
- production database roles

---

### PR4 — Global-Position Projection Worker Baseline

#### Status

Completed.

#### Goal

Connect accepted history, the canonical reducer, durable projection state, and durable checkpoint progress into the first PostgreSQL-backed read-side worker path.

#### Why

Stage 3 already established the reducer / worker model in memory.

PR4 proves that the same conceptual read-side runtime can operate against durable storage without turning PostgreSQL into a second reconstruction algorithm.

This PR also makes the worker cursor strategy explicit before durable replay / rebuild validation and future Compass Layer 2 projection-drift validation are introduced.

#### Completed Scope

- add `order_events.global_position`
- add a migration for the global event-log position
- update CI migration setup
- document the global-position worker cursor boundary
- add `PostgresProjectionEventSource`
- add `ProjectionEventRecord` as the envelope between storage metadata and domain event meaning
- add shared order-event hydration through `order_event_hydration.py`
- load accepted events after a global position
- order accepted-history consumption by `global_position`
- add `PostgresProjectionWorker`
- apply the canonical projection reducer
- persist projection state through `PostgresProjectionStore`
- persist checkpoint progress through `PostgresCheckpointStore`
- store checkpoint progress as `cursor_kind = GLOBAL_POSITION`
- persist projection state and checkpoint progress in one PostgreSQL transaction
- add integration tests for global-position event loading
- add integration tests for worker processing
- add rollback tests for projection-state / checkpoint atomicity
- document the single-worker baseline and defer worker leasing / checkpoint locking

#### Cursor Boundary

PR4 preserves this distinction:

```text
aggregate-local sequence
≠
global event-log position
≠
worker checkpoint cursor
```

`order_events.sequence` remains aggregate-local and protects per-order continuity.

`order_events.global_position` provides a durable total order for accepted-history consumption.

`projection_checkpoints.cursor_value` records where a worker should resume.

#### Transaction Boundary

The PostgreSQL-backed projection worker owns the read-side transaction boundary.

It commits:

```text
projection state
+
checkpoint progress
```

together.

If either write fails, both writes roll back.

This is the read-side equivalent of the Stage 3.5B write-side atomicity boundary:

```text
accepted event append
+
idempotency record write
```

#### Design Boundary

`reducer.py` remains storage-agnostic.

`PostgresProjectionWorker` orchestrates storage access and reducer execution.

It does not duplicate reduction rules.

#### Non-goals

PR4 does not implement:

- durable replay / rebuild validation
- Compass Layer 2 validation
- Snapshot Trust Contract
- structured `SemanticOutcome`
- runtime decision policy
- out-of-order buffering
- DLQ
- watermark semantics
- distributed multi-worker coordination
- worker leasing / checkpoint row locking
- multi-region / sharded / multi-primary event-log cursor models
- production database role hardening
- append-only trigger enforcement

---

### PR5 — Durable Replay / Rebuild Validation Baseline

#### Goal

Prove that durable read-side state can be discarded and rebuilt deterministically from accepted history.

#### Why

Projection state is derived state.

If it becomes corrupted, stale, or inconsistent, the recovery path should be:

```text
accepted history
→ canonical reducer
→ rebuilt projection state
```

This PR proves that durable read-side persistence does not redefine the source of truth.

#### Main Work

- add durable replay / rebuild tests
- reset or rebuild projection state from `order_events`
- verify rebuilt state equals expected reducer output
- verify checkpoint behavior during rebuild
- verify projection state remains derived and replaceable
- document replay / rebuild assumptions

#### Boundary

PR5 does not implement Compass Layer 2.

It provides the durable comparison substrate that future Layer 2 validation can consume:

```text
accepted-history replay
vs
persisted projection state
```

#### Non-goals

PR5 does not implement:

- Layer 2 drift validator
- `SemanticOutcome`
- runtime decision policy
- snapshot optimization
- production database role hardening

---

### PR6 — Stage 3.5C Documentation and Completion Alignment

#### Status

Completed.

#### Goal

Mark the durable read-side baseline as complete and align documentation, test guides, and roadmap state.

#### Why

Stage 3.5C changes the project from:

```text
durable write-side only
```

to:

```text
durable write-side + durable read-side baseline
```

The documentation should reflect that the project now has a minimal durable closed loop:

```text
accepted history
→ projection worker
→ durable projection state
→ durable checkpoint
→ replay / rebuild from accepted history
```

#### Main Work

- update project README
- update docs README
- update implementation roadmap
- update Compass runtime roadmap
- update test documentation
- update development setup if new migrations are required
- mark Stage 3.5C completion criteria as satisfied
- prepare transition notes for Stage 3.5D Snapshot Trust Contract / replay efficiency

#### Non-goals

PR6 does not implement:

- new runtime behavior
- snapshot schema
- Layer 2 validation
- `SemanticOutcome`
- Stage 3.5E database role hardening

## Candidate Tables

### `projection_states`

Possible fields:

- `order_id`
- `status`
- `total_amount`
- `paid_amount`
- `version`
- `last_sequence`
- `updated_at`

### `projection_checkpoints`

Current fields:

- `worker_name`
- `cursor_kind`
- `cursor_value`
- `updated_at`

For the Stage 3.5C PR4 worker baseline, checkpoint progress is stored as:

```text
cursor_kind = GLOBAL_POSITION
cursor_value = latest processed order_events.global_position
```

This keeps worker progress as operational metadata rather than business truth.

## Completion Criteria

- projection state survives restart
- checkpoint survives restart
- worker can consume accepted history through `GLOBAL_POSITION`
- worker can persist projection state and checkpoint progress atomically
- worker can resume from checkpoint
- projection can rebuild from accepted history
- read-side persistence does not redefine source of truth
- replay from durable `order_events` can rebuild the projection deterministically

## Boundary Statement

Stage 3.5C does not implement snapshot trust, aggregate snapshots, Layer 2 validation, retry reason classification, or agent-facing isolation.

Stage 3.5C only establishes the durable read-side target:

```text
event log
→ projection worker
→ durable projection state
→ durable checkpoint
```

This durable read-side target is required before later stages can validate, rebuild, optimize, or isolate derived state.

---
