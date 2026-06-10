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
- validate durable projection state against accepted-history replay
- enforce baseline sequencing assumptions

The projection runtime now has three baseline forms:

1. a deterministic in-memory Stage 3 baseline
2. a PostgreSQL-backed Stage 3.5C PR4 worker baseline
3. a Stage 3.5C PR5 durable replay / rebuild validation baseline

The current PostgreSQL-backed projection worker connects:

```text
order_events
→ PostgresProjectionEventSource
→ canonical reducer
→ PostgresProjectionStore
→ PostgresCheckpointStore
```

and persists:

```text
projection state
+
checkpoint progress
```

inside one read-side transaction boundary.

The PostgreSQL-backed worker uses:

```text
cursor_kind = GLOBAL_POSITION
cursor_value = latest processed order_events.global_position
```

as the first durable accepted-history consumption strategy.

Durable replay validation compares:

```text
accepted-history replay
vs
persisted projection state
```

This prepares the project for future Compass Layer 2 projection-drift validation without implementing Layer 2 runtime governance yet.

For the higher-level projection design, see:

- [Projection Pipeline](../../docs/architecture/projection_pipeline.md)
- [Projection Boundary](../../docs/boundary_notes/projection_boundary.md)
- [Global-Position Projection Worker Boundary](../../docs/boundary_notes/global_position_projection_worker_boundary.md)
- [Projection README](projection/README.md)

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

This write-side path exists as the current durable PostgreSQL-backed baseline after Stage 3.5B.

---

## Projection Flow as the Second Milestone

After the transactional path became stable, the projection path evolved from:

- a demo-level replay helper

into:

- a baseline projection runtime with worker / reducer separation

The Stage 3 in-memory projection baseline supports:

- incremental application
- replayability
- checkpoint-aware sequencing
- deterministic replay / rebuild through the same runtime path

Stage 3.5C PR4 extends the projection path into a PostgreSQL-backed durable runtime baseline.

It now supports:

- durable accepted-history scanning through `order_events.global_position`
- storage-side event loading through `PostgresProjectionEventSource`
- shared order-event hydration through `order_event_hydration.py`
- durable projection state through `PostgresProjectionStore`
- durable checkpoint progress through `PostgresCheckpointStore`
- atomic projection-state and checkpoint-progress persistence through `PostgresProjectionWorker`
- fail-fast handling for projection-state / checkpoint mismatch

It still does **not yet** include:

- durable replay / rebuild validation
- Compass Layer 2 validation
- advanced recovery logic
- out-of-order buffering
- DLQ handling
- watermark semantics
- worker leasing
- checkpoint row locking
- multi-worker coordination

Those concerns are intentionally deferred until after the durable projection worker baseline.

---

## Near-Term Integration Points

This module directly connects:

### `src/core/order/`

For event production and aggregate rehydration.

### `src/storage/`

For event persistence, idempotency storage, projection state, event-source loading, and checkpointing.

### `src/compass/transition/`

For validating whether candidate events are admissible.

---

## Long-Term Integration Points

Later, this module will also connect heavily with:

### persistence-backed storage evolution

To strengthen write-side and read-side restart semantics beyond the current durable baseline.

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
- projection progress must align with the actual accepted-history cursor
- PostgreSQL-backed projection must persist projection state and checkpoint progress atomically
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
