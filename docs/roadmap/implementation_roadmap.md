# Implementation Roadmap

[← Back to Roadmaps Index](README.md)

## Purpose

This roadmap describes the intended implementation order of the project.

It is not merely a list of desired features.  
It is a sequencing guide for building the system without losing semantic clarity.

---

## Guiding Principle

The project should evolve from:

1. semantic truth
2. transactional execution
3. concurrency-safe admission
4. event truth validation
5. projection/runtime correctness
6. analytical extension
7. adversarial hardening

This order is intentional.

The system should not attempt to solve chaos, analytics, or distributed complexity before its semantic core and write-side safety boundaries are clear.

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
- concurrency / admission gate
- conditional persistence with expected version
- transactional orchestration baseline

### Main Modules

- `src/core/order/`
- `src/storage/event_store/`
- `src/storage/idempotency_store/`
- `src/pipeline/transactional/`

### Deliverable

A deterministic transactional baseline capable of:

- producing candidate events
- conditionally admitting accepted events
- persisting accepted history
- replaying aggregate state
- preventing duplicate semantic effects
- preventing stale writes through conditional admission

---

## Stage 2: Event Truth Validation

### Goal

Integrate the first Compass layer into the transactional path.

### Main Work

- proof-carrying event structure
- transition validator
- validation dispatcher
- validation runner
- basic validation policy with `ALLOW` / `BLOCK`
- predecessor checks
- claimed previous version checks
- transition legality checks
- event admission integration with the transactional path

### Main Modules

- `src/compass/transition/`
- `src/compass/policy/` for basic enforcement policy
- integration with transactional pipeline

### Deliverable

A write-side flow that can reject semantically inconsistent events before they enter accepted history, while preserving the distinction between:

- semantic validation through Compass
- conditional admission through the persistence / concurrency boundary

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

- advanced governance policy actions
- warn / quarantine / audit behavior
- evidence logging
- semantic alerts
- chaos scenario injection
- partial commit tests
- duplicate / out-of-order / poison event tests

### Main Modules

- `src/compass/policy/`
- `src/compass/evidence/`
- `chaos_engine/`

### Deliverable

A failure-aware semantic governance layer that has been pressure-tested against adversarial runtime conditions.

Basic `ALLOW` / `BLOCK` enforcement belongs to the earlier validation dispatch path.  
This stage focuses on richer governance behavior such as warning, quarantine, auditability, evidence logging, and failure response.

---

## Summary View

### Stage 1

Transactional semantic core with concurrency-safe admission

### Stage 2

Event truth validation with basic validation dispatch and enforcement policy

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
- basic validation policy

However, the semantic dependency order should still be respected:

- event meaning before validation
- conditional admission before accepted history is trusted
- validation before advanced governance
- accepted history before projection runtime
- projection runtime before state-level Compass
- core correctness before chaos hardening
