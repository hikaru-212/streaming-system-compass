# Pipeline Layer

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

Typical submodules may include:

- `transactional/`
- `projection/`
- `analytical/`

---

## Not Responsible For

This module is **not** responsible for:

- defining domain event meaning
- defining aggregate legality rules
- acting as the persistence layer itself
- being the final owner of semantic policy
- injecting adversarial failure

Those responsibilities belong to:

- `src/core/`
- `src/storage/`
- `src/compass/`
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
- storage preserves movement
- Compass checks whether movement remains semantically correct

---

## Main Pipeline Boundaries

### `transactional/`
Defines the write-side transactional flow.

Typical responsibilities:
- handle incoming commands
- coordinate idempotency checks
- call aggregate logic
- run event admission checks
- persist events
- apply accepted events to in-memory aggregate state
- rebuild aggregate state through replay

This is the first pipeline segment to implement.

---

### `projection/`
Defines the read-side projection flow.

Typical responsibilities:
- consume events from a stream or history
- incrementally build materialized state
- persist projection state
- track checkpoints / offsets
- recover after restart
- rebuild projections through replay if necessary

This should eventually replace the current demo-level fold function.

---

### `analytical/`
Defines the analytical interpretation of the same event stream.

Typical responsibilities:
- event-time processing
- aggregation
- windows
- lateness handling
- analytical metrics or statistical views

This layer should be built after the transactional and projection flows are stable.

---

## Current Implementation Scope

At the current stage, the immediate focus is:

1. `transactional/`
2. later `projection/`
3. much later `analytical/`

The reason is simple:

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

---

## Projection Flow as the Second Milestone

After the transactional path is stable, the projection path should evolve from:

- a demo-level replay helper

into:

- a real projection worker with state persistence and checkpointing

Key goals include:
- incremental application
- replayability
- crash recovery
- duplicate tolerance strategy
- projection-state correctness

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

At this stage, the main pipeline-related invariants include:

- transactional event admission must preserve domain legality
- replay must rebuild aggregate state deterministically
- projection must produce state consistent with processed event history
- projection progress must align with actual consumed sequence or offset

Later analytical invariants may include:
- window boundaries are respected
- lateness handling remains semantically consistent

---

## Practical Reading Order

If reading this module from scratch, the recommended order is:

1. `transactional/`
2. `projection/`
3. `analytical/`

This reflects the intended implementation order of the system.

---

## Summary

This module is where semantic rules turn into runtime flow.

If the core defines what the system means, the pipeline defines how that meaning moves through time.
