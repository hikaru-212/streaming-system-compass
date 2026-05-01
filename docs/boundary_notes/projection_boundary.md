# Projection Boundary Note

[← Back to Boundary Notes Index](README.md)

## Purpose

This note defines the responsibility boundary inside the projection subsystem before the first projection runtime implementation begins.

The goal is to prevent semantic confusion while Stage 3 is still small.

In particular, this note separates:

- **pure state reduction**
- **runtime orchestration**
- **state persistence**
- **checkpoint persistence**

This separation is important because the project has already established a strong write-side boundary model:

- aggregate owns write-side domain transitions
- Compass Layer 1 owns event-level transition truth validation
- admission gate owns conditional persistence / stale-write rejection
- accepted history is the source of truth

The read-side projection path should preserve the same architectural discipline.

This note focuses on the internal Stage 3 boundary inside the projection subsystem.

For the higher-level module responsibility of projection as a whole, see [Projection Module Boundary](projection_module.md).

---

## Current Position

The repository already has an executable baseline for:

- transactional semantic core
- accepted-history persistence
- request-level idempotency
- optimistic admission for stale-write rejection
- Compass Layer 1 validation before persistence
- replay and adversarial baseline tests on the write-side

However, read-side projection is not yet implemented as a formal runtime subsystem.

At the moment, the repository only has:

- replay helpers used for testing
- replay-consistency checks
- adversarial history scenarios

These are useful preparation layers, but they are **not yet** the actual projection runtime.

The next implementation step is to introduce a minimal read-side runtime with a clear internal boundary.

---

## Core Distinction

The projection subsystem will be split into two fundamentally different roles.

In the language of this repository’s design philosophy:

- the **Reducer** behaves like the local **Core** of the projection path
- the **Worker** behaves like the local **Enabler** of the projection path

This does **not** mean they are separate top-level systems in the repository.
It means that, **inside the projection runtime itself**, they play different architectural roles:

- the reducer owns semantic state derivation
- the worker exists to support safe runtime execution under physical constraints

This distinction matters because projection should preserve the same discipline already established on the write-side:

- semantic logic should remain small, explicit, and testable
- runtime coordination should not silently absorb state-transition meaning

---

### 1. Reducer

The reducer is the **semantic heart** of the projection path.

Within the local projection boundary, it behaves like a **Core** component.

It answers one question only:

> Given the current projected state and the next accepted event,  
> what should the next projected state be?

The reducer is therefore:

- pure
- deterministic
- side-effect free
- storage-agnostic
- checkpoint-agnostic
- buffering-agnostic

It must not know:

- where events came from
- where state is stored
- what the current checkpoint is
- whether the system is replaying or processing live input
- how retries, buffering, or restart recovery are handled

Its responsibility is only:

- state transition from accepted event to next projected state
- read-side invariant enforcement local to pure state evolution

In short:

> The reducer decides **what the next state should be**.

---

### 2. Worker

The worker is the **runtime coordinator** of the projection path.

Within the local projection boundary, it behaves like an **Enabler** component.

It answers questions such as:

- what offset has already been consumed
- whether a record should be skipped, applied, or rejected
- whether sequence progression is acceptable
- when state should be persisted
- when checkpoint should be advanced
- how replay and incremental processing share the same execution path

The worker is therefore:

- side-effectful
- checkpoint-aware
- storage-aware
- control-flow aware
- responsible for runtime sequencing

It must not redefine domain transition semantics.

Its responsibility is only:

- deciding whether an accepted event reaches the reducer
- preserving physical processing order and checkpoint progression
- coordinating side effects after validation passes

In short:

> The worker decides **when and under what runtime conditions a state transition is allowed to execute**.

---

## Why This Boundary Matters

If reducer and worker are mixed together, the projection subsystem becomes hard to reason about.

Typical failure patterns include:

- putting checkpoint logic inside the reducer
- letting storage code silently decide transition legality
- coupling retry behavior with state transition semantics
- creating one logic path for replay and another for live processing
- making projection correctness depend on I/O details instead of accepted history

That would break the same design discipline already established on the write-side.

This project intentionally keeps:

- **semantic correctness**
- **runtime correctness**
- **storage persistence**
- **processing progress metadata**

as separate layers.

---

## Projection Data Model Boundary

The first projection runtime will distinguish between two kinds of data:

### A. Projected State

Projected state is the read-side derived representation for one entity.

For the current v1 scope, this is still based on `OrderState`, but the important point is architectural:

- projected state is **derived**
- projected state is **rebuildable**
- projected state is **not** the source of truth

Accepted history remains the source of truth.

---

### B. Checkpoint / Offset

Checkpoint data represents processing progress.

Examples:

- last consumed offset
- last consumed sequence in a stream partition
- worker-local progress metadata

Checkpoint data is **not domain truth**.

It exists only to support:

- restart continuation
- replay control
- incremental processing

This distinction must remain explicit:

> projected state describes **business meaning derived from accepted history**  
> checkpoint describes **how far the runtime has processed**

These two should never be collapsed into one responsibility.

---

## Store Boundary

The first projection runtime will use two storage abstractions.

### 1. Projection Store

Projection store owns:

- load projected state
- save projected state

Projection store does **not** own:

- transition legality
- sequence classification policy
- replay logic
- checkpoint advancement policy

It is a persistence boundary, not a semantic engine.

---

### 2. Checkpoint Store

Checkpoint store owns:

- load checkpoint / offset
- save checkpoint / offset

Checkpoint store does **not** own:

- projected state mutation
- event transition semantics
- event validation
- buffering / retry policy

It is processing metadata persistence, not domain logic.

---

## First-Version Processing Policy

The first projection runtime will deliberately be conservative.

It will only support the simplest deterministic policy:

1. if `record.offset <= checkpoint`, skip as already consumed
2. if `event.sequence <= current_state.version`, skip as already projected
3. if `event.sequence == current_state.version + 1`, apply through reducer
4. if `event.sequence > current_state.version + 1`, fail fast with a sequence-gap error

This means the first version intentionally does **not** support:

- out-of-order buffering
- pending queues
- TTL expiration
- DLQ routing
- replay-gap healing
- duplicate reconciliation beyond simple sequence-based skip

These may come later, but they do not belong in the first baseline.

---

## Read-Side Invariants

The first projection runtime should preserve at least the following invariants.

### Invariant 1: Accepted History is the Source of Truth

Projection never invents truth.

It only derives state from already accepted events.

If projected state is lost or corrupted, it must be rebuildable from accepted history.

---

### Invariant 2: Reducer Requires Exact Next Sequence

The reducer should only accept:

- current projected version = `n`
- incoming accepted event sequence = `n + 1`

Anything else is not a pure transition problem.
It is a runtime sequencing problem and belongs to the worker.

---

### Invariant 3: Replay and Incremental Processing Must Share Reduction Semantics

Replay should not use a different transition rule than the live worker.

The same reducer must be used for both.

This is essential for later guarantees such as:

- replay result equals incremental result
- rebuild correctness
- checkpoint recovery trustworthiness

---

### Invariant 4: Checkpoint Must Not Advance Before Successful State Persistence

In the ideal model, state persistence and checkpoint advancement should be committed together.

The first implementation may still use separate in-memory writes, but the architectural rule is already clear:

> The worker must not conceptually treat a record as completed  
> before projected state has successfully advanced.

This invariant will become more important once storage semantics become stronger.

---

## Anti-Patterns

The following are considered architectural mistakes for this stage.

### Anti-Pattern 1: Database or Offset Logic Inside Reducer

Wrong:

- reducer reads checkpoint
- reducer writes checkpoint
- reducer queries storage
- reducer classifies late events

Reason:
That mixes runtime orchestration into pure semantic transition logic.

---

### Anti-Pattern 2: Worker Mutates Projected State Without Reducer

Wrong:

- worker directly edits projected fields
- worker contains embedded business transition rules

Reason:
That bypasses the pure transition core and destroys semantic single source of truth.

---

### Anti-Pattern 3: Projection Store Decides Transition Legality

Wrong:

- store rejects transitions because status is wrong
- store embeds sequence policy

Reason:
Persistence boundary must not absorb semantic rules that belong to reducer or worker.

---

### Anti-Pattern 4: Separate Replay Logic and Live Logic

Wrong:

- one projection path for rebuild
- another projection path for live consumption
- slightly different state evolution rules between the two

Reason:
This makes replay correctness impossible to reason about.

---

## Relation to Compass

At the current stage, Compass Layer 1 is still a write-side boundary.

It validates whether a candidate event truthfully follows accepted history **before** persistence.

Projection runtime begins only **after** accepted history already exists.

Therefore, the first projection runtime does not re-run write-side Compass Layer 1.

However, this boundary note is intentionally preparing the next stage:

- projection reducer establishes deterministic state evolution
- projection worker establishes checkpoint-aware runtime orchestration
- later, Compass Layer 2 can validate projected state correctness

So the projection boundary is a prerequisite for future state-level Compass validation.

---

## Stage 3 Internal Sequencing

Within Stage 3, the implementation should evolve in the following order.

### Stage 3.1 — Pure Reducer

Implement a minimal deterministic reducer that:

- consumes accepted `OrderEvent`
- produces next projected `OrderState`
- enforces exact-next-sequence semantics locally
- remains side-effect free

---

### Stage 3.2 — Checkpoint-Aware Worker

Implement a minimal worker that:

- loads checkpoint
- loads projected state
- classifies skip / apply / gap
- calls reducer
- saves state
- advances checkpoint

No buffering yet.

---

### Stage 3.3 — Replay / Rebuild Flow

Implement deterministic replay and rebuild using the same reducer + worker semantics.

Goal:

- rebuild from accepted history
- preserve replay vs incremental equivalence

---

### Stage 3.4 — Stronger Recovery / Later Extensions

Only after the baseline is stable should the system consider:

- stronger checkpoint / persistence semantics
- restart recovery guarantees
- out-of-order handling
- buffering strategy
- later state-level Compass verification

---

## Summary

The projection boundary for the first implementation is:

- **Reducer** = pure semantic state transition
- **Worker** = runtime sequencing and orchestration
- **Projection Store** = projected state persistence
- **Checkpoint Store** = processing progress persistence

This distinction is not cosmetic.

It is the projection-side equivalent of the write-side architectural discipline already established in the repository.

The design principle remains the same:

> explain the boundary before explaining the implementation
