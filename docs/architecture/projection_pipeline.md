# Projection Pipeline

[← Back to Architectures Index](README.md)

## Purpose

This document describes the intended evolution of the projection layer.

At the current stage of the project, projection is still only a simplified replay helper.  
It is not yet a true runtime projection pipeline.

This document exists to clarify that distinction and to define the next implementation path toward a real projection runtime.

---

## Current Situation

The current projection logic can replay a sequence of events and reconstruct a state-like object.

This is useful for:

- deterministic replay demonstrations
- validating event ordering assumptions
- testing simple state reconstruction

However, this is still only a **demo-level replay helper**, not a real projection subsystem.

It does not yet establish:

- a formal projection worker
- persistent projection state storage
- checkpoint / offset progression
- replay / rebuild runtime behavior
- a stable boundary between pure reduction and runtime orchestration

---

## Why the Current Projection Is Not Enough

A true projection pipeline should answer questions such as:

- how are accepted events consumed incrementally?
- how is projection state persisted?
- how is processing progress tracked across restarts?
- how do replay and incremental processing share the same semantics?
- how should sequence progression be enforced at runtime?
- how can projection be rebuilt from accepted history?

A simple pure function over a list of events does not yet answer these runtime questions.

---

## Intended Projection Evolution

Projection in this project currently exists only in a simplified replay-helper form.

The next major target in the project roadmap is **Stage 3: Projection Runtime**.  
Within that stage, the projection subsystem should evolve through the following baseline steps.

### Current Form: Replay Helper

A deterministic fold over event history.

Used for:

- demo state reconstruction
- correctness checks
- early testing

This form already exists in simplified form.

---

### Next Target: Stage 3 Projection Runtime

This is the next major implementation target in the overall project roadmap.

It should be built incrementally through the following baseline steps.

#### Step 3.1: Pure Deterministic Reducer

The first goal is to establish a pure reducer that:

- consumes accepted `OrderEvent`
- transforms projected state deterministically
- remains side-effect free
- enforces exact-next-sequence semantics locally

This step should answer:

- what is the next projected state?
- what local state-transition invariants must hold?
- which event fields are actually necessary for derivation?

#### Step 3.2: Checkpoint-Aware Worker Baseline

The second goal is to introduce a minimal runtime worker that:

- loads checkpoint / offset
- loads current projected state
- classifies skip / apply / gap behavior
- calls the reducer
- saves projected state
- advances checkpoint

This step should answer:

- how is projection run incrementally?
- how is processing progress separated from business state?
- how do replay and live processing share the same runtime path?

#### Step 3.3: In-Memory Stores and Replay / Rebuild Baseline

The third goal is to support the baseline runtime path with minimal persistence abstractions:

- in-memory projection state store
- in-memory checkpoint store
- replay / rebuild using the same worker + reducer path

This step should answer:

- can projected state be rebuilt from accepted history?
- does replay follow the same semantics as incremental processing?
- is the projection baseline deterministic enough to serve as the foundation for later recovery logic?

---

### Later Target: Stage 4 Verified Projection Runtime

Only after the Stage 3 baseline path is stable should the projection pipeline move into a verified runtime stage.

This corresponds to [Compass Layer 2: Runtime State / Projection Validation](compass_layers.md#layer-2-runtime-state--projection-validation).

Expected additions include:

- state invariant validation
- replay vs incremental consistency checks
- checkpoint correctness validation
- drift detection or semantic mismatch reporting

---

## Main Components of the Stage 3 Baseline

The first runtime baseline is expected to include:

- `reducer.py`
- `worker.py`
- `projection_store.py`
- `checkpoint_store.py`

These represent different concerns.

### `reducer.py`

Pure state transition logic from accepted event to projected state.

### `worker.py`

Incremental event consumption and runtime sequencing.

### `projection_store.py`

Persistence of projected read-side state.

### `checkpoint_store.py`

Persistence of processing progress metadata.

Additional wrappers or later-stage modules may be introduced after the baseline runtime path is stable, but they are intentionally deferred for now.

---

## Relationship to the Rest of the System

Projection sits after event admission and event persistence.

It should consume only **accepted event history**.

This means:

- transactional core decides which events are admitted
- storage preserves accepted history
- projection derives read-side state from that history
- Compass state validation later checks whether the derived state remains semantically correct

Projection therefore depends on the transactional core, but should remain as independent as possible from event-admission details such as proof internals or predecessor-tracing metadata not required for state derivation.

---

## Minimal Dependency Principle

Projection should depend only on the minimum semantic fields required to derive state.

Typical examples:

- entity identifier
- event type
- sequence
- payload needed for state updates

Projection should not need to know all admission-related metadata, especially if those fields exist mainly for transition-truth validation or audit purposes.

This keeps the projection layer stable and focused.

---

## First Baseline Scope

The first projection runtime baseline intentionally does **not yet** include:

- out-of-order buffering
- pending queues
- DLQ routing
- watermark-based timing semantics
- advanced recovery logic
- distributed multi-worker coordination
- state-level Compass Layer 2 validation

These concerns are real, but they do not belong to the first runtime baseline.

The initial goal is narrower:

> establish a deterministic, replay-safe, checkpoint-aware projection baseline before introducing more complex physical runtime behavior.

---

## Future Role of Compass in Projection

Compass will later validate projection results at a higher layer: [Compass Layer 2: Runtime State / Projection Validation](compass_layers.md#layer-2-runtime-state--projection-validation).

This may include:

- projected state legality
- replay vs incremental consistency
- version progression correctness
- checkpoint semantic alignment

This is different from event truth validation.

Event truth validation happens before projection.  
Projection validation happens after events have been consumed into runtime state.

---

## Summary

Projection in this project should be understood as a planned runtime subsystem, not just a helper function.

The current replay-style implementation is useful as a stepping stone, but the next implementation target is a Stage 3 baseline projection runtime built around:

- a pure reducer
- a checkpoint-aware worker
- projected state persistence
- checkpoint persistence
- replay / rebuild through the same runtime path

Only after that baseline is stable should the project expand toward buffering, recovery hardening, and state-level Compass validation.