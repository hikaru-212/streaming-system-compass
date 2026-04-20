# Projection Pipeline

## Purpose

This document describes the intended evolution of the projection layer.

At the current stage of the project, projection is still only a simplified replay helper.  
It is not yet a true runtime projection pipeline.

This document exists to clarify that distinction and define the direction of future implementation.

---

## Current Situation

The current projection logic can replay a sequence of events and reconstruct a state-like object.

This is useful for:
- deterministic replay demonstrations
- validating event ordering assumptions
- testing simple state reconstruction

However, this is still only a **demo-level reducer**, not a real projection subsystem.

---

## Why the Current Projection Is Not Enough

A true projection pipeline should answer questions such as:

- how are events consumed incrementally?
- how is projection state persisted?
- how is progress tracked across restarts?
- how are duplicates handled?
- how are crashes recovered from?
- how do replay and incremental processing stay consistent?

A simple pure function over a list of events does not yet answer these runtime questions.

---

## Intended Projection Evolution

The projection layer should evolve through three stages.

### Stage 1: Replay Helper
A deterministic fold over event history.

Used for:
- demo state reconstruction
- correctness checks
- early testing

### Stage 2: Projection Worker
A runtime consumer of accepted events.

Expected responsibilities:
- consume event stream incrementally
- apply projection logic continuously
- persist projection state
- persist checkpoint / offset
- recover after restart

### Stage 3: Verified Projection Runtime
A projection pipeline whose results are also semantically checked.

Expected additions:
- state invariant validation
- replay vs incremental consistency checks
- checkpoint correctness validation
- drift detection or semantic mismatch reporting

---

## Main Components of the Future Projection Pipeline

The long-term projection subsystem is expected to include:

- `projector.py`
- `reducer.py`
- `worker.py`
- `checkpointing.py`
- `recovery.py`

These represent different concerns:

### `reducer.py`
Pure state transition logic from event to state.

### `projector.py`
Projection application wrapper around reducer logic.

### `worker.py`
Incremental event consumption and runtime update loop.

### `checkpointing.py`
Persistence of processing progress.

### `recovery.py`
Rebuild and restart behavior.

---

## Relationship to the Rest of the System

Projection sits after event admission and event persistence.

It should consume only **accepted event history**.

This means:

- transactional core decides which events are admitted
- storage preserves accepted history
- projection derives read-side state from that history
- Compass state validation later checks whether the derived state remains semantically correct

Projection therefore depends on the transactional core, but should remain as independent as possible from event-admission details such as proof metadata.

---

## Minimal Dependency Principle

Projection should depend only on the minimum semantic fields required to derive state.

Typical examples:
- entity identifier
- event type
- sequence
- payload needed for state updates

Projection should not need to know all admission-related metadata, especially if those fields exist mainly for transition truth validation or audit purposes.

This keeps the projection layer stable and focused.

---

## Future Role of Compass in Projection

Compass will later validate projection results at a higher layer.

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

The current replay-style implementation is useful as a stepping stone, but the intended direction is a true projection worker with persistent state, checkpoints, recovery, and semantic validation.