# Storage Layer

[← Back to src README](../README.md)

This module provides the persistence abstractions that surround both the transactional semantic core and the projection runtime.

It does **not** define domain meaning by itself.  
Instead, it preserves, retrieves, and checkpoints the semantic artifacts produced by the core and used by the pipeline.

## Current repaired read-side contract

[ADR 0020](../../docs/adr/0020_per_order_projection_progress_and_order_local_snapshot_tails.md)
replaces the historical global-checkpoint completeness cursor for the current
order-state projection. The worker discovers exact-next events by order-local
sequence and commits projection state with progress scoped to projection
definition, epoch, and `order_id` on one connection and transaction.
`global_position` remains accepted-event lineage and deterministic scheduling
metadata among eligible events; it is not commit order or a complete
committed-history frontier. Legacy checkpoint stores remain available as
generic infrastructure but are not used by the repaired worker for correctness
or restart.

A worker `no_event` result means only that no currently visible accepted event
is the exact next event for the supported projection definition and epoch. It
does not prove global catch-up or exclude a later commit.

---

## Purpose

The purpose of this module is to provide storage boundaries for:

- accepted event history
- idempotency records
- projection state
- per-order projection progress
- projection checkpoints / offsets
- projection snapshots
- decision receipts

This layer exists so that domain logic and runtime orchestration do not need to directly depend on concrete persistence details.

---

## Responsible For

This module is responsible for:

- event append / load abstractions
- version-aware event persistence
- idempotency record persistence
- projection state persistence
- exact-next projection progress persistence
- checkpoint / offset persistence
- projection snapshot persistence
- PostgreSQL-backed persistence implementations where the current stage requires durability
- caller-transaction-owned DecisionReceipt insert and load contracts

Typical submodules or files include:

- `event_store.py`
- `postgres_event_store.py`
- `order_event_hydration.py`
- `postgres_projection_event_source.py`
- `idempotency_store.py`
- `postgres_idempotency_store.py`
- `projection_store.py`
- `postgres_projection_store.py`
- `projection_progress_store.py`
- `postgres_projection_progress_store.py`
- `postgres_projection_eligible_event_source.py`
- `postgres_order_event_tail_source.py`
- `checkpoint_store.py`
- `postgres_checkpoint_store.py`
- `postgres_projection_snapshot_store.py`
- `decision_receipt_store.py`
- `postgres_decision_receipt_store.py`

---


### `postgres_projection_snapshot_store.py`

Provides the PostgreSQL-backed projection snapshot store.

Typical responsibilities:

- persist `ProjectionSnapshot` records into `projection_snapshots`
- load the latest snapshot for one order by highest `source_event_sequence`
- clear projection snapshots for one order
- preserve Decimal amount, metadata JSON, snapshot schema version, reducer version, payload hash, and database-created `created_at`
- treat duplicate writes with the same complete source boundary and same snapshot evidence as idempotent success
- raise `SnapshotWriteCollisionError` for inconsistent lineage or payload evidence

This store owns projection snapshot persistence only.

It does **not**:

- decide whether a snapshot is trustworthy
- compute canonical payload hashes
- build snapshot payloads
- run snapshot-assisted replay
- run the projection reducer
- mutate accepted history
- commit or rollback transactions

Transaction ownership remains outside the store.

This is important because a later snapshot-assisted replay validator must be able to load snapshot evidence and then decide whether that evidence is qualified for fast-path replay.


## Not Responsible For

This module is **not** responsible for:

- deciding whether an event is domain-legitimate
- deciding the next sequence or next state
- validating semantic transition truth
- running transactional or projection workers
- defining governance policies
- injecting failures

Those responsibilities belong to:

- [core/](../core/README.md)
- [pipeline/](../pipeline/README.md)
- [compass/](../compass/README.md)
- `chaos_engine/`

---

## Design Principle

This layer should be viewed as a **persistence boundary**, not as the owner of business truth.

In other words:

- the core decides what an event means
- storage preserves accepted history and runtime progress
- the pipeline executes around it
- Compass validates it

Storage is not the semantic source of truth.
It is the boundary that preserves and restores semantic artifacts across time.

---

## Main Storage Boundaries

### `decision_receipt_store.py`

Defines storage-neutral persistence envelopes, insertion outcomes, conflict
categories, and materialization provenance. Callers pass strict serialized
receipt data; this boundary does not map producer results or evaluate
governance.

### `postgres_decision_receipt_store.py`

Persists and loads version-1 DecisionReceipt envelopes through a caller-owned
PostgreSQL connection and transaction. It does not commit, roll back,
automatically materialize mapper output, scan accepted history, or reconcile
missing receipts.

### `event_store.py`

Stores the append-only accepted history.

Typical responsibilities:

- append event
- load event stream
- get last event
- enforce version continuity at the persistence boundary

This is the most important storage abstraction in the early durable baseline because accepted history is the foundation of replay and projection.

### `postgres_event_store.py`

Provides the PostgreSQL-backed accepted-history store.

Typical responsibilities:

- persist accepted events into `order_events`
- load accepted events ordered by aggregate-local sequence
- retrieve the latest accepted event
- preserve UUID identity, Decimal amount, proof fields, and selected JSONB evidence fields

This store owns accepted-history persistence only.
It does not own idempotency, Compass validation, or transactional write-side orchestration.

### `order_event_hydration.py`

Provides the shared database-row-to-domain-event hydration boundary.

Typical responsibilities:

- define the canonical `order_events` SELECT column set used by storage readers
- hydrate an `OrderEvent` from a database row
- preserve the mapping between PostgreSQL UUID values and the Python `OrderEvent.event_id` string contract
- keep storage metadata such as `global_position` outside the domain event

This helper prevents multiple PostgreSQL readers from copying their own row-to-event mapping logic.

### `postgres_projection_event_source.py`

Provides the PostgreSQL-backed accepted-history event source for legacy global-position scans.

Typical responsibilities:

- load accepted events after a durable global event-log position
- order accepted-history consumption by `order_events.global_position`
- return `ProjectionEventRecord` values containing:
  - `global_position` as storage / worker metadata
  - `OrderEvent` as domain event meaning

This source only reads accepted history.

The repaired order-state worker uses
`PostgresProjectionEligibleEventSource` instead. That source joins accepted
events to per-order progress and selects only exact-next local sequences;
`global_position` is only its deterministic scheduling tie-breaker.

It does **not**:

- run the projection reducer
- update projection state
- update checkpoint progress
- commit or rollback transactions
- validate projection drift
- decide replay / rebuild orchestration

---

### `idempotency_store.py`

Stores request-level processing records.

Typical responsibilities:

- check whether a request has already been processed
- retrieve previous result for retries
- persist request-to-result mapping

This supports retry safety and duplicate request handling.

### `postgres_idempotency_store.py`

Provides the PostgreSQL-backed idempotency memory.

Typical responsibilities:

- classify durable request state as `MISS`, `REPLAY`, or `CONFLICT`
- persist successful request-to-accepted-event mappings
- preserve semantic fingerprint and fingerprint-version evidence
- ensure idempotency records reference accepted events

This store owns request-level idempotency memory only.
It does not own event append, transaction orchestration, or retry policy.

---

### `projection_store.py`

Stores materialized read-side state.

Typical responsibilities:

- save projected state
- load projected state
- update projection results incrementally

This file defines the minimal projection-state storage boundary and the deterministic in-memory baseline.

### `postgres_projection_store.py`

Provides the PostgreSQL-backed projection-state store.

Typical responsibilities:

- persist derived projection state into `projection_states`
- load derived projection state by `order_id`
- upsert the current projected state for one order
- clear projection state for tests and future rebuild paths

This store owns derived projection state persistence only.

It does **not**:

- run the projection reducer
- decide event sequencing policy
- manage checkpoint progress
- validate semantic drift
- decide replay / rebuild orchestration
- commit or rollback transactions

Transaction ownership remains outside the store.

This is important because a later PostgreSQL-backed projection worker must be able to persist:

```text
projection state
+
checkpoint progress
```

inside one read-side transaction boundary.

#### Current `last_sequence` Mapping

At the current projection model level:

```text
OrderState.version
= last aggregate-local accepted event sequence reflected by this projection state
```

Therefore `PostgresProjectionStore` persists:

```text
projection_states.last_sequence = state.version
```

This mapping is intentional for Stage 3.5C PR2.

It should be revisited during Stage 3.5D if snapshot trust, reducer-version tracking, projection schema versioning, or projection-row versioning require separating:

```text
source event sequence
projection version
reducer version
snapshot lineage
projection schema version
```

---

### `checkpoint_store.py`

Stores generic consumer cursor / checkpoint evidence.

Typical responsibilities:

- save last processed offset or sequence
- restore cursor state for consumers that use this generic abstraction
- support replay / rebuild boundaries

At the current stage, this exists as part of the Stage 3 baseline projection runtime in a deterministic in-memory form.

### `postgres_checkpoint_store.py`

Provides the PostgreSQL-backed projection checkpoint store.

Typical responsibilities:

- persist generic worker checkpoint evidence into `projection_checkpoints`
- load projection worker progress by `worker_name`
- upsert checkpoint cursor state
- clear checkpoint progress for tests and future rebuild paths

This store owns durable checkpoint persistence only.

The repaired order-state projection worker does not use this store for
correctness or restart; its durable restart evidence is
`projection_order_progress`.

It does **not**:

- scan accepted history
- decide the final cursor strategy
- run the projection worker
- persist projection state
- validate semantic drift
- decide replay / rebuild orchestration
- commit or rollback transactions

Transaction ownership remains outside the store.

This is important because a later PostgreSQL-backed projection worker must be able to persist:

```text
projection state
+
checkpoint progress
```

inside one read-side transaction boundary.

---

## Current Implementation Scope

At the current stage, after Stage 4B completion, this module supports write-side persistence, read-side persistence, projection snapshot persistence, and explicit DecisionReceipt persistence boundaries.

Write-side storage currently includes:

- `event_store.py` — in-memory accepted-history store
- `postgres_connection.py` — low-level PostgreSQL connection helper
- `postgres_event_store.py` — PostgreSQL-backed accepted-history store baseline
- `idempotency_store.py` — in-memory request replay / conflict store
- `postgres_idempotency_store.py` — PostgreSQL-backed request replay / conflict store baseline

Read-side storage currently includes:

- `projection_store.py` — projection state protocol and in-memory projection state store
- `postgres_projection_store.py` — PostgreSQL-backed projection state store
- `projection_progress_store.py` — per-order progress model and protocol
- `postgres_projection_progress_store.py` — PostgreSQL-backed exact-next per-order progress store
- `postgres_projection_eligible_event_source.py` — currently visible exact-next event discovery
- `postgres_order_event_tail_source.py` — same-order local-sequence snapshot-tail loading
- `checkpoint_store.py` — checkpoint / offset protocol and in-memory checkpoint store
- `postgres_checkpoint_store.py` — PostgreSQL-backed generic / legacy checkpoint store
- `postgres_projection_event_source.py` — PostgreSQL-backed legacy global-position event source
- `order_event_hydration.py` — shared database-row-to-domain-event hydration helper
- `postgres_projection_snapshot_store.py` — PostgreSQL-backed projection snapshot store

Snapshot-related storage currently includes:

- `postgres_projection_snapshot_store.py` — projection snapshot persistence for derived read-side state compression

DecisionReceipt storage currently includes:

- `decision_receipt_store.py` — storage-neutral persistence envelopes and conflict contracts
- `postgres_decision_receipt_store.py` — caller-transaction-owned PostgreSQL insert and load behavior

The current durable write-side progress is:

```text
Stage 3.5B PR1 — PostgreSQL schema / local setup / migration ✅
Stage 3.5B PR2 — PostgresEventStore baseline ✅
Stage 3.5B PR3 — PostgresIdempotencyStore baseline ✅
Stage 3.5B PR4 — Transactional Semantic Write-Side Boundary ✅
Stage 3.5B PR5 — PostgreSQL Concurrency Admission Boundary ✅
Stage 3.5B PR6 — Validation Placement Strategy Boundary / Stage 4 Prelude ✅
```

The current durable read-side progress is:

```text
Stage 3.5C PR1 — Durable Read-Side Schema Baseline ✅
Stage 3.5C PR2 — PostgresProjectionStore ✅
Stage 3.5C PR3 — PostgresCheckpointStore ✅
Stage 3.5C PR4 — Global-Position Projection Worker Baseline ✅
Stage 3.5C PR5 — Durable Replay / Rebuild Validation Baseline ✅
```

The current snapshot trust / replay-efficiency progress is:

```text
Stage 3.5D PR1 — General Snapshot Trust Contract Boundary ✅
Stage 3.5D PR2 — Projection Snapshot Schema Baseline ✅
Stage 3.5D PR3 — PostgresProjectionSnapshotStore ✅
Stage 3.5D PR4 — Projection Snapshot-Assisted Replay Validator ✅
Stage 3.5D PR4.5 — Projection Snapshot-Assisted State Resolver ✅
Stage 3.5D PR5 — Aggregate Snapshot Trust Boundary / Deferral Decision ✅
```

Stage 3.5C PR4 historically added storage-side accepted-history consumption:

```text
order_events.global_position
→ PostgresProjectionEventSource
→ ProjectionEventRecord
```

The historical event source keeps its global scan coordinate outside
`OrderEvent`; that coordinate remains storage lineage rather than domain
meaning.

The repaired worker now uses:

```text
order_events + projection_order_progress
→ PostgresProjectionEligibleEventSource
→ exact-next OrderEvent for one order
→ projection state + PostgresProjectionProgressStore in one transaction
```

No progress row means sequence zero for that order. Processing another order
cannot exclude a late-committing event, and a rolled-back global-position
allocation does not block unrelated orders.

Stage 3.5D adds projection snapshot persistence as a derived-state compression boundary:

```text
projection_snapshots
→ PostgresProjectionSnapshotStore
→ snapshot-assisted replay validator / resolver
```

The snapshot store persists snapshot evidence, but it does not decide whether that evidence is trusted. Trust qualification remains in validator / resolver logic outside the store.

---



## Implementation Strategy

Each storage concern should ideally expose:

- a minimal abstract boundary or protocol where useful
- an in-memory implementation for early development
- a database-backed implementation when the durable stage requires it

Example progression:

```text
in-memory baseline
→ PostgreSQL-backed store
→ worker orchestration
→ replay / rebuild validation
```

This allows the semantic core and baseline runtime behavior to stabilize before infrastructure becomes more complex.

---

## Near-Term Integration Points

This module directly supports:

### `src/core/order/`

As the persistence boundary for accepted history and deterministic replay.

### `src/pipeline/transactional/`

As the write-side execution path that needs event append and idempotency storage.

### `src/compass/transition/`

As the source of actual accepted history used to validate predecessor claims and version continuity.

### `src/pipeline/projection/`

As the read-side path that depends on projection-state and exact-next
per-order progress persistence boundaries. Generic checkpoint infrastructure
remains available for other consumers.

Stage 3.5C PR2 historically made `projection_states` usable through a Python
storage boundary. The current repaired worker connects that state store to
exact-next per-order progress under ADR 0020.

---

## Long-Term Integration Points

Later, this module will also support:

### persistence-backed transactional flow

For durable accepted-history and idempotency semantics across restart.

### persistence-backed projection flow

For durable projection-state and per-order progress semantics across restart.
This is established for the current aggregate-local projection; a legacy
global checkpoint is not repaired-worker restart evidence.

### projection snapshot persistence

For derived read-side state compression, replay-efficiency evidence, and snapshot-assisted resolver inputs. This is established at the Stage 3.5D baseline level.

### `src/compass/state/`

For comparing runtime projected state against replayed or checkpointed state as a future full Compass Layer 2 subsystem. Stage 3.5D provides snapshot and replay evidence substrates, but does not yet implement full Layer 2 governance.

### `chaos_engine/`

For testing how storage-related guarantees behave under:

- partial commit
- delayed writes
- duplicate delivery
- crash recovery

---

## Key Invariants

At the current stage, the main storage-related invariants include:

- event streams must remain append-only at the application boundary
- event version progression must remain continuous
- idempotency records must be stable across retries
- persisted accepted history must support deterministic replay
- projection state must remain derived and rebuildable
- PostgreSQL-backed projection state must round-trip status, Decimal money values, and version evidence correctly
- `projection_states.last_sequence` currently reflects `OrderState.version`
- repaired projection progress must advance by exact-next order-local sequence
- projection state and matching per-order progress must be committed atomically by the PostgreSQL-backed projection worker
- persistence-backed replay and incremental state must remain equivalent
- durable per-order progress must survive restart correctly
- projection snapshots must remain derived state compression, not accepted-history authority
- projection snapshot duplicate writes must distinguish benign idempotent writes from inconsistent evidence collisions
- write-side and read-side persistence semantics must remain mutually consistent
- database role boundaries prevent runtime roles from casually updating or deleting accepted history
- DecisionReceipt serialization and persistence must preserve exact versioned semantic evidence and caller-owned transaction boundaries

Later invariants will include:

- append-only hardening should protect `order_events` without freezing mutable derived read-side tables
- future governance may consume validation receipts without turning snapshot rows into authority

---

## Practical Reading Order

If reading this module from scratch, the recommended order is:

1. `event_store.py`
2. `postgres_event_store.py`
3. `idempotency_store.py`
4. `postgres_idempotency_store.py`
5. `projection_store.py`
6. `postgres_projection_store.py`
7. `projection_progress_store.py`
8. `postgres_projection_progress_store.py`
9. `postgres_projection_eligible_event_source.py`
10. `checkpoint_store.py`
11. `postgres_checkpoint_store.py`
12. `postgres_projection_event_source.py`
13. `postgres_projection_snapshot_store.py`
14. `decision_receipt_store.py`
15. `postgres_decision_receipt_store.py`

This reflects the current project evolution:

- transactional persistence first
- durable read-side projection state second
- durable per-order progress and worker orchestration
- legacy checkpoint infrastructure retained for generic consumers
- replay validation after durable worker semantics exist
- snapshot persistence and snapshot-assisted replay after accepted-history authority is clear
- DecisionReceipt persistence after the semantic contract and producer mappings stabilize

---

## Summary

This module does not define semantic truth.  
It defines where semantic truth and runtime progress are persisted, recovered, and tracked.

If the core is the system's semantic source, storage is the memory boundary that preserves that source across time.

After Stage 4B, storage also preserves projection snapshot artifacts for replay
efficiency and versioned DecisionReceipt governance evidence. Snapshot artifacts
remain subordinate to accepted history, and receipt persistence remains an
explicit caller-owned operation rather than automatic materialization.
