# Pipeline Layer

[← Back to src README](../README.md)

This module defines how events and state transitions move through the system.

If `src/core/` defines semantic meaning, and `src/storage/` preserves history, then `src/pipeline/` defines the execution flow built around them.

---

## Purpose

The purpose of this module is to coordinate how domain events are:

- admitted
- persisted
- replayed
- projected
- analytically processed

This is the layer where the system begins to behave like a runtime rather than only a domain model.

---

## Responsible For

This module is responsible for:

- transactional command flow
- event admission path
- replay / rehydration flow
- projection execution flow
- analytical event-processing flow

Current and planned submodules include:

- `transactional/`
- `projection/`
- `analytical/` (planned later)

---

## Not Responsible For

This module is **not** responsible for:

- defining domain event meaning
- defining aggregate legality rules
- acting as the persistence layer itself
- being the final owner of semantic policy
- injecting adversarial failure

Those responsibilities belong to:

- [core/](../core/README.md)
- [storage/](../storage/README.md)
- [compass/](../compass/README.md)
- `chaos_engine/`

---

## Design Principle

This layer should be treated as the **execution topology** of the system.

It answers questions such as:

- In what order are components called?
- When does validation happen?
- When is an event persisted?
- When is state applied?
- When is projection updated?
- How does replay happen after restart?

In short:

- core defines meaning
- pipeline defines movement
- storage preserves movement and progress
- Compass checks whether movement remains semantically correct

---

## Main Pipeline Boundaries

### [transactional/](transactional/)

Defines the write-side transactional flow.

Typical responsibilities:

- handle incoming commands
- coordinate idempotency checks
- call aggregate logic
- run event admission checks
- persist events
- apply accepted events to in-memory aggregate state
- rebuild aggregate state through replay

This is the first pipeline segment that was implemented.

For the higher-level write-side design, see:

- [Transactional Core](../../docs/architecture/transactional_core.md)

---

### [projection/](projection/)

Defines the read-side projection flow.

Typical responsibilities:

- consume events from accepted history
- incrementally build materialized state
- persist projection state
- track checkpoints / offsets
- recover through replay / rebuild
- enforce baseline sequencing assumptions

At the current stage, a Stage 3 baseline projection runtime now exists in deterministic in-memory form, built around:

- a pure reducer
- a checkpoint-aware worker
- projection-state persistence boundary
- checkpoint persistence boundary
- replay / rebuild through the same runtime path

For the higher-level projection design, see:

- [Projection Pipeline](../../docs/architecture/projection_pipeline.md)
- [Projection Boundary](../../docs/boundary_notes/projection_boundary.md)

---

### `analytical/` (planned)

Defines the future analytical interpretation of the same event stream.

Typical responsibilities may later include:

- event-time processing
- aggregation
- windows
- lateness handling
- analytical metrics or statistical views

This layer is intentionally deferred until the transactional and projection baselines are stronger.

---

## Current Implementation Scope

At the current stage, the implemented focus now includes:

1. [transactional/](transactional/)
2. [projection/](projection/)

while:

1. `analytical/`

remains a later stage.

The reason is still the same:

- transactional flow establishes correctness of event admission and persistence
- projection flow establishes correctness of state derivation
- analytical flow is valuable, but should be built on top of a stable semantic foundation

---

## Transactional Flow as the First Milestone

The first important pipeline path is:

1. receive command
2. check idempotency
3. load or create aggregate
4. replay historical events if needed
5. produce candidate event
6. validate event admission / transition truth
7. persist accepted event
8. apply event to aggregate state
9. return result

This is the minimum runtime path of the transactional system.

That write-side path now exists as the current baseline.

---

## Projection Flow as the Second Milestone

After the transactional path became stable, the projection path evolved from:

- a demo-level replay helper

into:

- a baseline projection runtime with worker / reducer separation

The current Stage 3 baseline now supports:

- incremental application
- replayability
- checkpoint-aware sequencing
- deterministic replay / rebuild through the same runtime path

However, it still does **not yet** include:

- persistent storage-backed semantics
- advanced recovery logic
- out-of-order buffering
- DLQ handling
- watermark semantics
- multi-worker coordination

Those concerns are intentionally deferred until after the durable persistence baseline is introduced.

---

## Near-Term Integration Points

This module directly connects:

### `src/core/order/`

For event production and aggregate rehydration.

### `src/storage/`

For event persistence, idempotency storage, projection state, and checkpointing.

### `src/compass/transition/`

For validating whether candidate events are admissible.

---

## Long-Term Integration Points

Later, this module will also connect heavily with:

### persistence-backed storage evolution

To strengthen write-side and read-side restart semantics beyond the current in-memory baseline.

### `src/compass/state/`

To validate projection correctness and checkpoint semantics.

### `chaos_engine/`

To test how pipeline behavior survives:

- out-of-order delivery
- duplicate events
- poison messages
- partial commits
- network delays
- recovery interruptions

---

## Key Invariants

At the current stage, the main pipeline-related invariants include:

- transactional event admission must preserve domain legality
- replay must rebuild aggregate state deterministically
- projection must produce state consistent with processed accepted history
- projection progress must align with actual consumed sequence or offset
- replay / rebuild must follow the same baseline projection semantics as incremental processing

Later analytical invariants may include:

- window boundaries are respected
- lateness handling remains semantically consistent

---

## Practical Reading Order

If reading this module from scratch, the recommended order is:

1. `transactional/`
2. `projection/`
3. `analytical/` later

This reflects the current implementation order of the system.

---

## Summary

This module is where semantic rules turn into runtime flow.

If the core defines what the system means, the pipeline defines how that meaning moves through time.
