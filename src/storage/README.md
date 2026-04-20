# Storage Layer

This module provides the persistence abstractions that surround the transactional semantic core.

It does **not** define domain meaning by itself.  
Instead, it preserves, retrieves, and checkpoints the semantic artifacts produced by the core and used by the pipeline.

---

## Purpose

The purpose of this module is to provide storage boundaries for:

- event history
- idempotency records
- projection state
- projection checkpoints / offsets

This layer exists so that domain logic does not need to directly depend on concrete persistence details.

---

## Responsible For

This module is responsible for:

- event append / load abstractions
- version-aware event persistence
- idempotency record persistence
- projection state persistence
- checkpoint / offset persistence
- future database-backed implementations

Typical submodules may include:

- `event_store/`
- `idempotency_store/`
- `projection_store/`
- `checkpoint_store/`

---

## Not Responsible For

This module is **not** responsible for:

- deciding whether an event is domain-legitimate
- deciding the next sequence or next state
- validating semantic transition truth
- running projection workers
- defining governance policies
- injecting failures

Those responsibilities belong to:

- `src/core/`
- `src/pipeline/`
- `src/compass/`
- `chaos_engine/`

---

## Design Principle

This layer should be viewed as a **persistence boundary**, not as the owner of business truth.

In other words:

- the core decides what an event means
- storage preserves that event history
- the pipeline executes around it
- Compass validates it

---

## Main Storage Boundaries

### `event_store/`
Stores the append-only event history.

Typical responsibilities:
- append event
- load event stream
- get last event
- enforce version continuity at the persistence boundary

This is the most important storage abstraction in the early stage of the project.

---

### `idempotency_store/`
Stores request-level processing records.

Typical responsibilities:
- check whether a request has already been processed
- retrieve previous result for retries
- persist request-to-result mapping

This supports retry safety and duplicate request handling.

---

### `projection_store/`
Stores materialized read-side state.

Typical responsibilities:
- save projected state
- load projected state
- update projection results incrementally

This is more important after the projection layer becomes a real worker.

---

### `checkpoint_store/`
Stores consumer position / projection progress.

Typical responsibilities:
- save last processed offset or sequence
- restore projection progress after restart
- support replay / rebuild boundaries

This becomes important when projection evolves beyond demo-level replay.

---

## Current Implementation Scope

At the current stage, the immediate focus is:

1. `event_store`
2. `idempotency_store`

These are enough to support the first transactional baseline.

`projection_store` and `checkpoint_store` are intentionally reserved for the next stage, once the projection pipeline becomes a real runtime component rather than a simple replay helper.

---

## Implementation Strategy

Each storage concern should ideally expose:

- a minimal abstract interface
- an in-memory implementation for early development
- a future database-backed implementation

Example progression:

- `in_memory.py` first
- `postgres.py` later

This allows the semantic core to stabilize before infrastructure becomes more complex.

---

## Near-Term Integration Points

This module directly supports:

### `src/core/order/`
As the persistence boundary for order events and replay.

### `src/pipeline/transactional/`
As the write-side execution path that needs event append and idempotency storage.

### `src/compass/transition/`
As the source of actual event history used to validate predecessor claims and version continuity.

---

## Long-Term Integration Points

Later, this module will also support:

### `src/pipeline/projection/`
For projection state and checkpoint persistence.

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

At this stage, the main storage-related invariants include:

- event streams must remain append-only
- event version progression must remain continuous
- idempotency records must be stable across retries
- persisted history must support deterministic replay

Later invariants will include:

- projection state must match processed history
- checkpoint position must reflect actual progress

---

## Practical Reading Order

If reading this module from scratch, the recommended order is:

1. `event_store/`
2. `idempotency_store/`
3. `projection_store/`
4. `checkpoint_store/`

This reflects the intended evolution:

- transactional persistence first
- read-side persistence later

---

## Summary

This module does not define semantic truth.  
It defines where semantic truth is persisted, recovered, and tracked.

If the core is the system's semantic source, storage is the memory boundary that preserves that source across time.