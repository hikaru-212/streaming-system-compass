# Implementation Roadmap

[← Back to Roadmaps Index](README.md)

## Purpose

This roadmap describes the intended implementation order of the project.

It is not merely a list of desired features.  
It is a sequencing guide for building the system without losing semantic clarity.

---

## Current Position

The project has now completed an executable baseline across:

- transactional semantic core
- accepted-history persistence and replay
- request-level idempotency with replay/conflict distinction
- optimistic admission with stale-write rejection
- event-level Compass validation before persistence
- Stage 3 baseline projection runtime in a deterministic in-memory form
- Stage 3.5A decimal / money hardening before durable persistence
- executable baseline tests across unit, integration, semantic-case, adversarial-history, and Stage 3 projection-baseline layers

This means:

- Stage 1 is complete at a baseline level
- Stage 2 is complete at a baseline level
- Stage 3 exists as a minimal executable read-side runtime baseline
- Stage 3.5A is now complete as the pre-persistence money / exact-value hardening step

The next major focus is:

- **Stage 3.5B — durable write-side baseline**

Only after write-side durable semantics are clarified should the project proceed toward:

- Stage 3.5C durable read-side baseline
- Stage 4 runtime semantic validation and outcome structuring
- later demo / packaging, governance, and chaos expansion

---

## Guiding Principle

The project should evolve from:

1. semantic truth
2. transactional execution
3. concurrency-safe admission
4. event truth validation
5. projection/runtime correctness
6. exact durable money semantics
7. durable persistence semantics
8. runtime semantic outcomes
9. demo / packaging value
10. governance and adversarial hardening

This order is intentional.

The system should not attempt to solve chaos, analytics, or distributed complexity before its semantic core, write-side safety boundaries, runtime semantics, and durable money representation are clear.

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
- `src/storage/event_store.py`
- `src/storage/idempotency_store.py`
- `src/pipeline/transactional/`

### Deliverable

A deterministic transactional baseline capable of:

- producing candidate events
- conditionally admitting accepted events
- persisting accepted history
- replaying aggregate state
- preventing duplicate semantic effects
- preventing stale writes through conditional admission

### Status

Implemented as the current write-side baseline.

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
- validation runtime integration with transactional pipeline
- runtime assembly through `src/bootstrap/`

### Deliverable

A write-side flow that can reject semantically inconsistent events before they enter accepted history, while preserving the distinction between:

- semantic validation through Compass
- conditional admission through the persistence / concurrency boundary

### Status

Implemented at a baseline level as the current Compass Layer 1 path.

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

### Main Modules

- `src/pipeline/projection/`
- `src/storage/projection_store.py`
- `src/storage/checkpoint_store.py`

### Deliverable

A read-side runtime capable of incremental state derivation and replay / rebuild through the same runtime path.

### Status

Implemented at a deterministic in-memory baseline level.

### Current Note

The current Stage 3 baseline already establishes:

- reducer / worker separation
- projection-state and checkpoint-store separation
- replay-safe projection sequencing
- deterministic in-memory replay / rebuild behavior

However, it does not yet establish durable storage-backed runtime semantics.

---

## Stage 3.5A: Decimal Hardening Before Durable Persistence

### Goal

Ensure that money-like values are represented exactly before write-side or read-side durable persistence grows larger.

### Why

The project originally used in-memory baselines and later evolved toward durable persistence.  
Before persistence-backed schema and transactional durability are introduced, money semantics must be stabilized so that replay, idempotency comparison, projection state, and future persistence-backed history do not inherit float-based ambiguity.

### Main Work

- add shared money primitive / helper logic
- migrate transactional money semantics from `float` to `Decimal`
- align aggregate / event / state / registry / idempotency signature handling
- align fixtures / unit / integration / semantic / adversarial / demo paths with Decimal
- align projection reducer path with Decimal-based state initialization
- retire the temporary replay helper and replace it with the formal projection reducer path

### Main Modules

- `src/core/common/money.py`
- `src/core/order/`
- `src/pipeline/transactional/`
- `src/pipeline/projection/`
- `tests/`

### Deliverable

An exact-money baseline that preserves semantic correctness before persistent storage is introduced more deeply.

### Status

Completed.

---

## Stage 3.5B: Durable Write-Side Baseline

### Goal

Move the current write-side baseline from in-memory persistence toward durable storage-backed semantics.

### Why

After Stage 3.5A, the next meaningful step is not durable read-side storage first, and not advanced runtime complexity first.

It is durable write-side evolution, because accepted-history durability, idempotency durability, transaction grouping, and append-only event-store semantics must be clarified before the rest of the runtime grows larger.

### Main Work

- durable event-store evolution
- durable idempotency-store evolution
- write-side schema / migration definition
- transaction grouping for event append + idempotency write
- durable replay / conflict classification support
- persistence-backed write-side tests

### Deliverable

A storage-backed write-side baseline that preserves:

- accepted-history durability
- idempotency durability
- append-only event history shape
- exact money persistence
- restart-safe write-side semantics

### Status

Next.

---

## Stage 3.5C: Durable Read-Side Baseline

### Goal

Move the current Stage 3 read-side baseline from in-memory stores toward durable persistence-backed semantics.

### Main Work

- durable projection-state store
- durable checkpoint store
- replay / rebuild validation against persistence-backed read-side state
- persistence-backed projection worker tests

### Deliverable

A storage-backed read-side baseline that preserves replay-safe projection semantics under restart and rebuild conditions.

### Status

Planned after Stage 3.5B.

---

## Stage 4: Runtime Semantic Validation and Outcome Structuring

### Goal

Extend Compass beyond basic projection-state checking into structured runtime semantic outcomes.

### Why

By the time durable write-side and read-side baselines exist, the next meaningful step is not merely “add another validator.”

The system should begin to answer two connected questions:

- is derived runtime state semantically correct?
- if not, how should that failure be expressed in a structured, machine-readable form?

This stage therefore begins with Layer 2 validation and expands toward a shared outcome family across write-side and read-side semantic failures.

### Main Work

- Layer 2 minimal validator
- replay vs incremental consistency checks
- projected-state invariant checks
- structured semantic outcome model for runtime failures
- outcome-family alignment between Layer 1 and Layer 2
- foundation for later layered trust verdict simulation

### Main Modules

- `src/compass/state/`
- runtime semantic outcome structures
- future shared outcome-family modules

### Deliverable

A runtime semantic layer that can both detect invalid projected state and express failures in a structured, machine-readable form.

### Status

Planned after Stage 3.5B and Stage 3.5C.

---

## Stage 5: Demo, Packaging, and Reviewer-Facing System Story

### Goal

Package the implemented system into a reviewer-friendly, portfolio-ready, and open-source-ready milestone.

### Why

At this point the project should not only be technically correct.  
It should also be understandable, demonstrable, and coherent as a system story for external review.

### Main Work

- README refinement
- architecture diagram alignment
- ADR / roadmap alignment
- demo script packaging
- semantic rejection demo
- projection drift / runtime semantic outcome demo
- layered trust minimal simulation demo (if completed by then)
- rebuild / recovery walkthrough
- implementation vs future-work boundary clarification

### Main Modules

- `README.md`
- `docs/`
- `experiments/`
- selected demo entrypoints across `src/`

### Deliverable

A demo-ready milestone that can explain the project clearly in 3–5 minutes and function as both:

- flagship portfolio project
- open-source release baseline

### Status

Planned after Stage 4 becomes coherent enough to demonstrate.

---

## Stage 6: Governance and Chaos Hardening

### Goal

Turn semantic validation into richer governance and pressure-test the system under adversarial conditions.

### Main Work

- layered trust evaluation
- advanced governance policy actions
- warn / quarantine / audit behavior
- evidence logging
- semantic alerts
- chaos scenario injection
- partial commit tests
- duplicate / out-of-order / poison event tests
- later operational signal integration where appropriate

### Main Modules

- `src/compass/policy/`
- `src/compass/evidence/`
- future trust-evaluator modules
- `chaos_engine/`

### Deliverable

A failure-aware semantic governance layer that has been pressure-tested against adversarial runtime conditions.

Basic `ALLOW` / `BLOCK` enforcement belongs to the earlier validation dispatch path.  
This stage focuses on richer governance behavior such as warning, quarantine, auditability, evidence logging, and failure response.

### Status

Future work.

---

## Summary View

### Stage 1

Transactional semantic core with concurrency-safe admission

### Stage 2

Event truth validation with basic validation dispatch and enforcement policy

### Stage 3

Projection runtime baseline

### Stage 3.5A

Decimal hardening before durable persistence

### Stage 3.5B

Durable write-side baseline

### Stage 3.5C

Durable read-side baseline

### Stage 4

Runtime semantic validation and outcome structuring

### Stage 5

Demo, packaging, and reviewer-facing system story

### Stage 6

Governance and chaos hardening

---

## Important Note

This roadmap should not be interpreted as a rigid no-overlap sequence.

Some modules may be explored in parallel, especially:

- transactional core
- transition validation
- basic validation policy
- early durable schema notes

However, the semantic dependency order should still be respected:

- event meaning before validation
- conditional admission before accepted history is trusted
- validation before advanced governance
- accepted history before projection runtime
- projection runtime baseline before durable persistence baseline
- exact money semantics before durable event / idempotency persistence
- write-side durable baseline before read-side durable baseline
- durable runtime baseline before richer runtime semantic outcomes
- runtime semantic outcomes before full reviewer-facing demo packaging
- core correctness before chaos hardening
