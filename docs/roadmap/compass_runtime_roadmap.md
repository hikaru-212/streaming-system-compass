# Compass Runtime Roadmap

[← Back to Roadmaps Index](README.md)

## 0. Current Position

The project now has an implemented write-side baseline that merges the two lines that were previously separate.

### Transactional Baseline Already Integrated

The current executable path includes:

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

### Current Boundary

What is already true:

- Compass can validate event claims before persistence
- admission still owns version consistency and conditional persistence
- aggregate state still mutates only through `apply(event)`
- idempotency remains distinct from semantic validation
- selected failure paths are executable through tests

What is not yet true:

- projection is not yet a real runtime subsystem
- state-level Compass validation is not yet implemented
- governance behavior is not yet richer than basic `ALLOW` / `BLOCK`

---

## 1. Stage 1: Write-Side Compass Baseline

### Goal

Establish a single write-side path where transactional execution and Compass Layer 1 already coexist.

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

## 2. Stage 2: Upgrade Demo Projection into a Real Projection Worker

### Goal

Replace the current replay-helper / demo-style projection logic with an actual projection pipeline.

### Why

The current replay reduction logic is useful for replay-consistency testing, but it is not yet a real projection layer.

### Target Outcome

A projection subsystem with:

- event consumption flow
- incremental projection updates
- projection state store
- offset / checkpoint tracking
- duplicate handling strategy
- failure / retry behavior

### Key Questions

- What is the projection input contract?
- Where is projection state stored?
- How are consumer offsets tracked?
- How does the projection recover after crash or restart?
- How are duplicate or out-of-order events handled?

### Deliverable

A read-side pipeline that behaves like a real projection worker.

---

## 3. Stage 3: Add Projection / State-Level Compass Verification

### Goal

Move Compass beyond event admission and into runtime state verification.

### Why

Even if every event is individually valid, the projection process can still drift or fail.

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

## 4. Stage 4: Move from Validation to Governance

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
Stage 4 focuses on richer governance actions after validation becomes observable and policy-driven.

### Deliverable

A semantic governance layer sitting above both write-side and read-side execution.

---

## 5. Summary of Intended Evolution

### Stage 1

Write-side Compass baseline already integrated with transactional execution and conditional admission.

### Stage 2

Projection becomes a real pipeline rather than a replay helper.

### Stage 3

Compass validates whether projected state remains semantically correct.

### Stage 4

Compass becomes a runtime governance framework rather than just a validator.
