# Storage Layer

[← Back to src README](../README.md)

This module provides the persistence abstractions that surround both the transactional semantic core and the Stage 3 baseline projection runtime.

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
- future database-backed implementations

Typical submodules or files may include:

- `event_store.py`
- `idempotency_store.py`
- `projection_store.py`
- `checkpoint_store.py`

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

This is the most important storage abstraction in the early stage of the project because accepted history is the foundation of replay and projection.

---

### `idempotency_store.py`

Stores request-level processing records.

Typical responsibilities:

- check whether a request has already been processed
- retrieve previous result for retries
- persist request-to-result mapping

This supports retry safety and duplicate request handling.

---

### `projection_store.py`

Stores materialized read-side state.

Typical responsibilities:

- save projected state
- load projected state
- update projection results incrementally

At the current stage, this now exists as part of the Stage 3 baseline projection runtime in a deterministic in-memory form.

---

### `checkpoint_store.py`

Stores consumer position / projection progress.

Typical responsibilities:

- save last processed offset or sequence
- restore projection progress after restart
- support replay / rebuild boundaries

At the current stage, this also now exists as part of the Stage 3 baseline projection runtime in a deterministic in-memory form.

---

## Current Implementation Scope

At the current stage, this module now supports both:

1. write-side persistence boundaries
   - `event_store.py`
   - `idempotency_store.py`

2. Stage 3 baseline read-side persistence boundaries
   - `projection_store.py`
   - `checkpoint_store.py`

This means the storage layer is no longer only write-side focused.

However, the current read-side storage baseline remains intentionally limited:

- projection state persistence is still in-memory
- checkpoint persistence is still in-memory
- durable database-backed semantics are not yet implemented

Those are the next major storage-evolution target.

---

## Implementation Strategy

Each storage concern should ideally expose:

- a minimal abstract boundary or protocol where useful
- an in-memory implementation for early development
- a future database-backed implementation

Example progression:

- in-memory baseline first
- `postgres.py` or equivalent later

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

As the Stage 3 baseline read-side path that now depends on projection-state and checkpoint persistence boundaries.

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

- event streams must remain append-only
- event version progression must remain continuous
- idempotency records must be stable across retries
- persisted accepted history must support deterministic replay
- projection state must remain consistent with processed history in the current in-memory baseline
- checkpoint position must reflect actual baseline projection progress

Later invariants will include:

- persistence-backed replay and incremental state must remain equivalent
- durable checkpoint position must survive restart correctly
- write-side and read-side persistence semantics must remain mutually consistent

---

## Practical Reading Order

If reading this module from scratch, the recommended order is:

1. `event_store.py`
2. `idempotency_store.py`
3. `projection_store.py`
4. `checkpoint_store.py`

This reflects the current project evolution:

- transactional persistence first
- baseline read-side persistence second
- durable storage evolution next

---

## Summary

This module does not define semantic truth.  
It defines where semantic truth and runtime progress are persisted, recovered, and tracked.

If the core is the system's semantic source, storage is the memory boundary that preserves that source across time.


