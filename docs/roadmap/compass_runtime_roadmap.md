# Compass Runtime Roadmap

[← Back to Roadmaps Index](README.md)

## 0. Current Position

The project now has an implemented write-side baseline and a minimal Stage 3 read-side projection baseline.

### Transactional Baseline Already Integrated

The current executable write-side path includes:

- aggregate-based command handling
- event generation
- event store append through an admission boundary
- aggregate replay / rehydration
- idempotency handling
- proof embedded in each candidate event
- transition validation through Compass Layer 1
- basic validation dispatch and `ALLOW` / `BLOCK` policy
- optimistic stale-write rejection at the admission boundary

This means the original "merge the two lines" step is no longer a future target.
It now exists as the current write-side baseline.

### Projection Baseline Now Exists

The current read-side baseline now includes:

- a pure projection reducer
- a checkpoint-aware projection worker
- in-memory projection state storage
- in-memory checkpoint storage
- replay / rebuild through the same worker + reducer path

This means projection is no longer only a replay helper.
A minimal Stage 3 baseline projection runtime now exists.

### Current Boundary

What is already true:

- Compass can validate event claims before persistence
- admission still owns version consistency and conditional persistence
- aggregate state still mutates only through `apply(event)`
- idempotency remains distinct from semantic validation
- Stage 3 projection baseline now exists in deterministic in-memory form
- selected failure paths are executable through tests on both write-side and Stage 3 baseline read-side paths

What is not yet true:

- persistent storage-backed runtime behavior is not yet implemented
- state-level Compass validation is not yet implemented
- governance behavior is not yet richer than basic `ALLOW` / `BLOCK`
- advanced runtime concerns such as DLQ, buffering, watermarking, or multi-worker coordination are not yet in scope

---

## 1. Stage 1: Transactional Semantic Core

### Goal

Establish the write-side semantic baseline of the system.

### Achieved Outcome

The current baseline now supports:

- aggregate-based command handling
- candidate-event generation
- accepted-history replay / rehydration
- event-store append through an admission boundary
- optimistic stale-write rejection at the persistence boundary
- idempotency handling
- aggregate mutation only through `apply(event)`

### Deliverable

A write-side transactional path that is deterministic, replayable, and protected by conditional admission.

### Status

Completed at the baseline level.

---

## 2. Stage 2: Event Truth Validation

### Goal

Integrate Compass Layer 1 into the transactional path.

### Achieved Outcome

The current baseline now supports:

- aggregates produce events with proof
- Compass validates event claims before persistence
- validation dispatch routes the candidate event through the active validation path
- a basic validation policy converts validation results into `ALLOW` / `BLOCK`
- the admission gate / event store still enforces version consistency
- aggregate state is updated only through `apply(event)`
- idempotency remains preserved

### Deliverable

A single write-side path that is operational, semantically validated, and protected by conditional admission.

### Status

Completed at the baseline level.

---

## 3. Stage 3: Projection Runtime Baseline

### Goal

Replace the earlier replay-helper / demo-style projection logic with a real baseline projection runtime.

### Why

The earlier replay reduction logic was useful for replay-consistency testing, but it was not yet a runtime projection subsystem.

### Achieved Outcome

The current Stage 3 baseline now includes:

- reducer / worker separation
- event consumption flow in minimal baseline form
- incremental projection updates
- projection state store
- offset / checkpoint tracking
- replay / rebuild through the same runtime path

### Deliverable

A read-side pipeline that behaves like a real projection worker in a deterministic in-memory baseline form.

### Status

Completed at the baseline level.

### Current Limitation

The current Stage 3 baseline does **not yet** include:

- persistent storage-backed runtime behavior
- advanced recovery logic
- out-of-order buffering
- DLQ handling
- watermark semantics
- distributed multi-worker coordination

Those are intentionally deferred.

---

## 3.5 Next Step: Persistent Storage Baseline

### Goal

Strengthen the current write-side and read-side runtime baselines through durable persistence-backed semantics.

### Why

The next meaningful step after the in-memory projection baseline is not advanced runtime complexity first.

It is persistent storage evolution, because restart semantics, durable replay, and persistence-backed correctness should be clarified before DLQ, buffering, watermarking, or multi-worker coordination are introduced.

### Target Outcome

A persistence-backed runtime baseline with:

- durable event-store evolution
- durable idempotency-store evolution
- durable projection-state store
- durable checkpoint store
- replay / rebuild validation against persistence-backed state

### Deliverable

A storage-backed baseline that preserves the current semantic boundaries while strengthening runtime durability.

---

## 4. Stage 4: Add Projection / State-Level Compass Verification

### Goal

Move Compass beyond event admission and into runtime state verification.

### Why

Even if every event is individually valid, the projection process can still drift or fail.

That risk becomes even more important once the runtime moves beyond purely in-memory baseline behavior and into persistence-backed semantics.

### Target Outcome

A second Compass layer that validates:

- projected version correctness
- projected state invariants
- consistency between replayed state and incrementally projected state
- semantic correctness at checkpoint boundaries

### Candidate Invariants

- projected version must match last consumed event sequence
- paid amount must not exceed total amount
- projected status progression must remain legal
- replayed state must equal incrementally projected state

### Deliverable

A true runtime verification layer for state evolution.

---

## 5. Stage 5: Move from Validation to Governance

### Goal

Turn Compass from a validator into a governance layer.

### Target Outcome

Support for advanced governance behavior:

- warn / quarantine policies
- evidence logging
- semantic alerts
- drift classification
- auditability and recovery workflows

Basic `ALLOW` / `BLOCK` enforcement belongs to the earlier validation dispatch path.  
Stage 5 focuses on richer governance actions after validation becomes observable and policy-driven.

### Deliverable

A semantic governance layer sitting above both write-side and read-side execution.

---

## 6. Summary of Intended Evolution

### Stage 1

Transactional semantic core establishes the deterministic write-side baseline.

### Stage 2

Event truth validation integrates Compass Layer 1 into transactional execution and conditional admission.

### Stage 3

Projection runtime baseline now exists as a real deterministic in-memory runtime path rather than only a replay helper.

### Stage 3.5

Persistent storage baseline strengthens write-side and read-side runtime durability.

### Stage 4

Compass validates whether projected state remains semantically correct.

### Stage 5

Compass becomes a runtime governance framework rather than just a validator.
