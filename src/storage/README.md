# Storage Layer

[← Back to src README](../README.md)

This module provides the persistence abstractions that surround both the transactional semantic core and the projection runtime.

It does **not** define domain meaning by itself.  
Instead, it preserves, retrieves, and checkpoints the semantic artifacts produced by the core and used by the pipeline.

---

## Purpose

The purpose of this module is to provide storage boundaries for:

- accepted event history
- idempotency records
- projection state
- projection checkpoints / offsets

This layer exists so that domain logic and runtime orchestration do not need to directly depend on concrete persistence details.

---

## Responsible For

This module is responsible for:

- event append / load abstractions
- version-aware event persistence
- idempotency record persistence
- projection state persistence
- checkpoint / offset persistence
- PostgreSQL-backed persistence implementations where the current stage requires durability

Typical submodules or files include:

- `event_store.py`
- `postgres_event_store.py`
- `idempotency_store.py`
- `postgres_idempotency_store.py`
- `projection_store.py`
- `postgres_projection_store.py`
- `checkpoint_store.py`
- `postgres_checkpoint_store.py`

---

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

Stores consumer position / projection progress.

Typical responsibilities:

- save last processed offset or sequence
- restore projection progress after restart
- support replay / rebuild boundaries

At the current stage, this exists as part of the Stage 3 baseline projection runtime in a deterministic in-memory form.

### `postgres_checkpoint_store.py`

Provides the PostgreSQL-backed projection checkpoint store.

Typical responsibilities:

- persist projection worker progress into `projection_checkpoints`
- load projection worker progress by `worker_name`
- upsert checkpoint cursor state
- clear checkpoint progress for tests and future rebuild paths

This store owns durable checkpoint persistence only.

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

At the current stage, this module supports both write-side and read-side persistence boundaries.

Write-side storage currently includes:

- `event_store.py` — in-memory accepted-history store
- `postgres_connection.py` — low-level PostgreSQL connection helper
- `postgres_event_store.py` — PostgreSQL-backed accepted-history store baseline
- `idempotency_store.py` — in-memory request replay / conflict store
- `postgres_idempotency_store.py` — PostgreSQL-backed request replay / conflict store baseline

Read-side storage currently includes:

- `projection_store.py` — projection state protocol and in-memory projection state store
- `postgres_projection_store.py` — PostgreSQL-backed projection state store
- `checkpoint_store.py` — checkpoint / offset protocol and in-memory checkpoint store
- `postgres_checkpoint_store.py` — PostgreSQL-backed checkpoint store

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
Stage 3.5C PR4 — PostgreSQL-Backed Projection Worker planned
Stage 3.5C PR5 — Durable Replay / Rebuild Validation planned
```

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

As the read-side path that depends on projection-state and checkpoint persistence boundaries.

Stage 3.5C PR2 makes `projection_states` usable through a Python storage boundary, but it does not yet connect that store to a PostgreSQL-backed projection worker.

---

## Long-Term Integration Points

Later, this module will also support:

### persistence-backed transactional flow

For durable accepted-history and idempotency semantics across restart.

### persistence-backed projection flow

For durable projection-state and checkpoint semantics across restart.

### `src/compass/state/`

For comparing runtime projected state against replayed or checkpointed state.

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
- checkpoint position must reflect actual projection progress once the durable checkpoint store is added

Later invariants will include:

- projection state and checkpoint progress should be committed atomically by the PostgreSQL-backed projection worker
- persistence-backed replay and incremental state must remain equivalent
- durable checkpoint position must survive restart correctly
- write-side and read-side persistence semantics must remain mutually consistent

---

## Practical Reading Order

If reading this module from scratch, the recommended order is:

1. `event_store.py`
2. `postgres_event_store.py`
3. `idempotency_store.py`
4. `postgres_idempotency_store.py`
5. `projection_store.py`
6. `postgres_projection_store.py`
7. `checkpoint_store.py`

This reflects the current project evolution:

- transactional persistence first
- durable read-side projection state second
- durable checkpoint progress next
- worker orchestration after both durable stores exist

---

## Summary

This module does not define semantic truth.  
It defines where semantic truth and runtime progress are persisted, recovered, and tracked.

If the core is the system's semantic source, storage is the memory boundary that preserves that source across time.