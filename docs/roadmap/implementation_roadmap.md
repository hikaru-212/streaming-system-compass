# Implementation Roadmap

## Purpose

This roadmap describes the intended implementation order of the project.

It is not merely a list of desired features.  
It is a sequencing guide for building the system without losing semantic clarity.

---

## Guiding Principle

The project should evolve from:

1. semantic truth
2. transactional execution
3. projection/runtime correctness
4. analytical extension
5. adversarial hardening

This order is intentional.

The system should not attempt to solve chaos, analytics, or distributed complexity before its semantic core is clear.

---

## Stage 1: Transactional Semantic Core

### Goal
Establish the write-side meaning of the system.

### Main Work
- order event schema
- proof structure
- aggregate logic
- apply-based mutation
- version / sequence semantics
- event store
- idempotency store
- transactional orchestration baseline

### Main Modules
- `src/core/order/`
- `src/storage/event_store/`
- `src/storage/idempotency_store/`
- `src/pipeline/transactional/`

### Deliverable
A deterministic transactional baseline capable of:
- producing candidate events
- persisting accepted history
- replaying aggregate state
- preventing duplicate semantic effects

---

## Stage 2: Event Truth Validation

### Goal
Integrate the first Compass layer into the transactional path.

### Main Work
- proof-carrying event structure
- transition validator
- predecessor checks
- claimed previous version checks
- transition legality checks
- event admission path

### Main Modules
- `src/compass/transition/`
- integration with transactional pipeline

### Deliverable
A write-side flow that can reject semantically inconsistent events before they enter accepted history.

---

## Stage 3: Projection Runtime

### Goal
Upgrade projection from replay helper into a real runtime subsystem.

### Main Work
- projection reducer
- projection worker
- projection store
- checkpoint store
- replay / rebuild flow
- crash recovery semantics

### Main Modules
- `src/pipeline/projection/`
- `src/storage/projection_store/`
- `src/storage/checkpoint_store/`

### Deliverable
A read-side runtime capable of incremental state derivation and restart recovery.

---

## Stage 4: State-Level Compass Validation

### Goal
Validate runtime state correctness after events have been projected.

### Main Work
- projected state invariants
- replay vs incremental consistency checks
- checkpoint semantic checks
- runtime state validator

### Main Modules
- `src/compass/state/`

### Deliverable
A second Compass layer capable of validating state-level semantic correctness.

---

## Stage 5: Analytical Pipeline

### Goal
Build the analytical interpretation of the event stream.

### Main Work
- event-time processing
- aggregation workers
- windows
- lateness handling
- statistical materialization

### Main Modules
- `src/pipeline/analytical/`

### Deliverable
An analytical path that interprets the same event history under a different semantic objective.

---

## Stage 6: Governance and Chaos Hardening

### Goal
Turn validation into governance and test the system under adversarial conditions.

### Main Work
- policy actions
- evidence logging
- quarantine / warning behavior
- chaos scenario injection
- partial commit tests
- duplicate / out-of-order / poison event tests

### Main Modules
- `src/compass/policy/`
- `src/compass/evidence/`
- `chaos_engine/`

### Deliverable
A failure-aware semantic governance layer that has been pressure-tested against adversarial runtime conditions.

---

## Summary View

### Stage 1
Transactional semantic core

### Stage 2
Event truth validation

### Stage 3
Projection runtime

### Stage 4
State-level Compass validation

### Stage 5
Analytical pipeline

### Stage 6
Governance + chaos hardening

---

## Important Note

This roadmap should not be interpreted as a rigid no-overlap sequence.

Some modules may be explored in parallel, especially:
- transactional core
- transition validation
- early replay helpers

However, the semantic dependency order should still be respected:

- event meaning before validation
- validation before governance
- accepted history before projection runtime
- projection runtime before state-level Compass
- core correctness before chaos hardening