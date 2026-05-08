# Projection Pipeline

[← Back to Architectures Index](README.md)

## Purpose

This document describes the intended evolution of the projection layer.

At the current stage of the project, projection is no longer only a replay helper.  
A minimal Stage 3 baseline projection runtime now exists, but it is still intentionally narrow and in-memory.

This document exists to clarify that distinction and to define the next implementation path toward a more durable and verified projection runtime.

---

## Current Situation

The projection layer now has a minimal executable runtime baseline.

This baseline already supports:

- pure deterministic state reduction
- checkpoint-aware worker sequencing
- in-memory projection state storage
- in-memory checkpoint storage
- replay / rebuild through the same worker + reducer path

This is enough to establish a real Stage 3 baseline.

However, the projection subsystem is still intentionally limited.

It does not yet establish:

- persistent projection state storage
- durable checkpoint semantics across restart
- advanced recovery logic
- out-of-order buffering
- DLQ routing
- watermark-based timing semantics
- state-level Compass Layer 2 validation

---

## Why the Current Projection Is Still Not Enough

A stronger projection pipeline should eventually answer questions such as:

- how are accepted events consumed incrementally across durable restarts?
- how is projection state persisted beyond in-memory lifetime?
- how is processing progress tracked safely across restarts?
- how do replay and incremental processing remain equivalent under persistent storage?
- how should more complex runtime issues such as disorder, lateness, or recovery be handled?

The current Stage 3 baseline is sufficient for deterministic baseline correctness, but not yet for durable or production-like runtime semantics.

---

## Intended Projection Evolution

Projection in this project originally existed only in a simplified replay-helper form.

The current major milestone in the project roadmap is **Stage 3: Projection Runtime**.  
That stage now exists at a baseline level.

The next steps should evolve from that baseline rather than skipping directly into advanced runtime complexity.

### Earlier Form: Replay Helper

Before the Stage 3 baseline, projection existed mainly as a deterministic fold over event history.

Used for:

- demo state reconstruction
- correctness checks
- early testing

That earlier form is still important as historical context, but it is no longer the current boundary.

---

### Current Baseline: Stage 3 Projection Runtime

The current baseline is built around the following implemented steps.

#### Step 3.1: Pure Deterministic Reducer

A pure reducer now exists that:

- consumes accepted `OrderEvent`
- transforms projected state deterministically
- remains side-effect free
- enforces exact-next-sequence semantics locally

This baseline establishes:

- what the next projected state should be
- which local transition invariants belong to pure reduction
- which event fields are actually required for derivation

#### Step 3.2: Checkpoint-Aware Worker Baseline

A minimal runtime worker now exists that:

- loads checkpoint / offset
- loads current projected state
- classifies skip / apply / gap behavior
- calls the reducer
- saves projected state
- advances checkpoint

This baseline establishes:

- how projection runs incrementally
- how processing progress remains separate from business state
- how replay and live processing share the same runtime path

#### Step 3.3: In-Memory Stores and Replay / Rebuild Baseline

The current baseline is supported by minimal persistence abstractions:

- in-memory projection state store
- in-memory checkpoint store
- replay / rebuild using the same worker + reducer path

This baseline establishes:

- that projected state can be rebuilt from accepted history
- that replay follows the same semantics as incremental processing
- that the projection baseline is deterministic enough to support later persistence and recovery work

---

### Next Target: Persistent Projection Runtime Baseline

After the in-memory Stage 3 baseline, the next projection target is not DLQ or buffering first.

The next priority should be a persistent baseline that introduces:

- durable projection state storage
- durable checkpoint storage
- replay / rebuild validation against persistence-backed state

This is the next meaningful step because storage durability and restart semantics should be clarified before advanced runtime complexity is introduced.

---

### Later Target: Stage 4 Verified Projection Runtime

Only after the Stage 3 baseline path and persistent storage semantics are stable should the projection pipeline move into a verified runtime stage.

This corresponds to [Compass Layer 2: Runtime State / Projection Validation](compass_layers.md#layer-2-runtime-state--projection-validation).

Expected additions include:

- state invariant validation
- replay vs incremental consistency checks
- checkpoint correctness validation
- drift detection or semantic mismatch reporting

---

## Main Components of the Current Stage 3 Baseline

The current runtime baseline includes:

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

Persistence boundary for projected read-side state.

### `checkpoint_store.py`

Persistence boundary for processing progress metadata.

Additional wrappers or later-stage modules may be introduced after the baseline runtime path and persistence semantics are stable, but they are intentionally deferred for now.

---

## Relationship to the Rest of the System

Projection sits after event admission and event persistence.

It consumes only **accepted event history**.

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

## Current Baseline Scope

The current Stage 3 projection runtime intentionally does **not yet** include:

- out-of-order buffering
- pending queues
- DLQ routing
- watermark-based timing semantics
- advanced recovery logic
- distributed multi-worker coordination
- state-level Compass Layer 2 validation

These concerns are real, but they do not belong to the current baseline.

The current goal is narrower:

> establish a deterministic, replay-safe, checkpoint-aware projection baseline before introducing durable storage semantics or more complex physical runtime behavior.

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

Projection in this project should be understood as a runtime subsystem whose Stage 3 baseline now exists in minimal form.

The current baseline is built around:

- a pure reducer
- a checkpoint-aware worker
- projected state persistence boundaries
- checkpoint persistence boundaries
- replay / rebuild through the same runtime path

The next step is to strengthen this baseline through durable persistence-backed evolution before introducing more advanced runtime concerns such as buffering, watermarking, or state-level Compass validation.
