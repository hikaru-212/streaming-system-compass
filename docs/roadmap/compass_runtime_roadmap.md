# Compass Runtime Roadmap

[← Back to Roadmaps Index](README.md)

## 0. Current Position

The project currently has two partially developed lines:

### Line A: Transactional Event-Sourcing Baseline

This line already includes:

- aggregate-based command handling
- event generation
- event store append
- aggregate replay / rehydration
- idempotency handling
- a demo-level projection function

This provides a minimal transactional core.

### Line B: Compass Event Truth Prototype

This line already includes:

- proof embedded in each event
- predecessor linkage (`prev_event_id`)
- transition validation through `CompassRuntime`
- accept / reject verdicts for incoming events

This provides an initial semantic validation mechanism at the event level.

---

## 1. Stage 1: Merge the Two Lines

### Goal

Integrate event-level Compass validation into the transactional baseline.

### Target Outcome

A write-side core where:

- aggregates produce events with proof
- Compass validates event claims before persistence
- validation dispatch can route the candidate event through the appropriate validation path
- a basic validation policy converts validation results into `ALLOW` / `BLOCK`
- the admission gate / event store still enforces version consistency
- aggregate state is updated only through `apply(event)`
- idempotency remains preserved

### Key Questions

- What exact fields should be included in `Proof`?
- Which aggregate state is required to produce proof?
- Should Compass validation happen before or after store append?
- What minimal validation dispatch structure is needed for the first implementation?
- What is the first `ALLOW` / `BLOCK` policy boundary?
- How does Compass validation relate to the admission gate / conditional persistence?
- How should rejected events be handled?
- How should replay restore proof-related state such as `last_event_id`?

### Deliverable

A single write-side path that is operational, semantically validated, and protected by conditional admission.

---

## 2. Stage 2: Upgrade Demo Projection into a Real Projection Worker

### Goal

Replace the current fold-style demo projection with an actual projection pipeline.

### Why

The current `project(events)` function is only a deterministic replay helper.  
It is not yet a real projection layer.

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

Compass validates whether an event truthfully represents a legal transition, while the admission gate still protects accepted history through version consistency.

### Stage 2

Projection becomes a real pipeline rather than a replay helper.

### Stage 3

Compass validates whether projected state remains semantically correct.

### Stage 4

Compass becomes a runtime governance framework rather than just a validator.
