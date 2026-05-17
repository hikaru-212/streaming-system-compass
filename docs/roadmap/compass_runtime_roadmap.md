# Compass Runtime Roadmap

[← Back to Roadmaps Index](README.md)

## 0. Current Position

The project now has:

- an implemented write-side baseline
- a minimal Stage 3 read-side projection baseline
- a completed Stage 3.5A exact-money hardening step before durable persistence

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

### Stage 3.5A Is Now Complete

The project has now also completed the pre-persistence exact-money hardening step:

- Decimal-based money semantics replaced earlier float-based handling
- fixtures / unit / integration / semantic / adversarial / demo paths were aligned
- projection replay consistency now uses the formal projection reducer path
- the temporary replay helper has been retired

This means the next persistence work can proceed from an exact-money baseline rather than from ambiguous float semantics.

### Current Boundary

What is already true:

- Compass can validate event claims before persistence
- admission still owns version consistency and conditional persistence
- aggregate state still mutates only through `apply(event)`
- idempotency remains distinct from semantic validation
- Stage 3 projection baseline now exists in deterministic in-memory form
- Stage 3.5A exact-money hardening is complete
- selected failure paths are executable through tests on both write-side and Stage 3 baseline read-side paths

What is not yet true:

- persistent storage-backed runtime behavior is not yet implemented
- durable write-side schema and transactional durability are not yet implemented
- durable read-side storage is not yet implemented
- state-level Compass validation is not yet implemented
- structured semantic outcome families are not yet implemented
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

## 3.5A: Exact-Money Hardening Before Durable Persistence

### Goal

Ensure that money-like values are exact before durable persistence is introduced more deeply.

### Why

Persistence-backed replay, idempotency comparison, projection state, and later schema design should not be built on float-based ambiguity.

### Achieved Outcome

The current baseline now includes:

- shared money primitive / helper logic
- Decimal-based money semantics across write-side and projection paths
- aligned fixtures / tests across unit, integration, semantic, adversarial, and demo layers
- formal projection reducer path as the only replay reduction truth path

### Deliverable

An exact-money baseline that can safely support Stage 3.5B write-side durability work.

### Status

Completed.

---

## 3.5B Next Step: Durable Write-Side Baseline

### Goal

Strengthen the current write-side baseline through durable persistence-backed semantics.

### Why

The next meaningful step after Stage 3.5A is not advanced runtime complexity first.

It is durable write-side evolution, because accepted-history durability, idempotency durability, append-only event history shape, and transaction grouping must be clarified before durable read-side evolution or richer runtime governance.

### Target Outcome

A persistence-backed write-side baseline with:

- durable event-store evolution
- durable idempotency-store evolution
- write-side schema and migration definition
- exact money durability
- transaction grouping for event append + idempotency write
- replay / conflict validation against persistence-backed state

### Deliverable

A storage-backed write-side baseline that preserves current semantic boundaries while strengthening durable write-side truth.

### Status

Next.

---

## 3.5C Later Step: Durable Read-Side Baseline

### Goal

Strengthen the current read-side projection baseline through durable persistence-backed semantics.

### Why

After the write-side durable baseline is clear, the read-side can safely evolve toward:

- durable projection-state storage
- durable checkpoint storage
- persistence-backed replay / rebuild validation

### Target Outcome

A persistence-backed projection baseline with:

- durable projection-state store
- durable checkpoint store
- replay / rebuild validation against persistence-backed read-side state

### Deliverable

A storage-backed read-side baseline that preserves replay-safe projection behavior across restart and rebuild.

### Status

Planned after Stage 3.5B.

---

## 4. Stage 4: Runtime Semantic Validation and Outcome Structuring

### Goal

Move Compass beyond simple event admission and into structured runtime semantic outcomes.

### Why

Even if every event is individually valid, the projection process can still drift or fail.

By the time durability work is complete, the next meaningful step is not only to detect runtime semantic failure, but also to express it in a structured form that can later support shared outcome families and minimal trust evaluation.

### Target Outcome

A runtime semantic layer that can:

- validate projection-state correctness
- compare replayed state against incrementally projected state
- emit structured semantic outcomes instead of relying only on ad-hoc exceptions
- begin aligning Layer 1 and Layer 2 around a common outcome family
- prepare the ground for later trust verdict simulation

### Candidate Invariants

- projected version must match last consumed event sequence
- paid amount must not exceed total amount
- projected status progression must remain legal
- replayed state must equal incrementally projected state

### Deliverable

A true runtime semantic layer for state evolution, together with the first structured runtime semantic outcomes.

### Status

Planned after durable write-side and read-side baselines.

---

## 5. Stage 5: Reviewer-Facing Demo and System Story

### Goal

Turn the implemented system into a clear, demo-ready, reviewer-facing milestone.

### Why

By this point the project should not only validate truth internally.  
It should also explain its system value clearly to reviewers, hiring managers, and future open-source readers.

### Target Outcome

A demo-ready system story that can show:

- Layer 1 rejection of invalid event truth
- Layer 2 detection of invalid runtime / projection truth
- structured semantic outcomes
- optional minimal layered trust simulation if ready
- rebuild / replay / recovery value in a concise reviewer-friendly flow

### Deliverable

A demo, packaging, and documentation milestone that makes the system legible in a short review window.

### Status

Planned after Stage 4 becomes coherent enough to demonstrate.

---

## 6. Stage 6: Move from Validation to Governance

### Goal

Turn Compass from a validator into a governance layer.

### Target Outcome

Support for advanced governance behavior:

- warn / quarantine policies
- evidence logging
- semantic alerts
- drift classification
- auditability and recovery workflows
- later richer trust-aware action gating

Basic `ALLOW` / `BLOCK` enforcement belongs to the earlier validation dispatch path.  
This later stage focuses on richer governance actions after semantic outcomes and reviewer-facing demos are already coherent.

### Deliverable

A semantic governance layer sitting above both write-side and read-side execution.

### Status

Future work.

---

## 7. Summary of Intended Evolution

### Stage 1

Transactional semantic core establishes the deterministic write-side baseline.

### Stage 2

Event truth validation integrates Compass Layer 1 into transactional execution and conditional admission.

### Stage 3

Projection runtime baseline now exists as a real deterministic in-memory runtime path rather than only a replay helper.

### Stage 3.5A

Exact-money hardening is complete and now protects future persistence work from float-based ambiguity.

### Stage 3.5B

Durable write-side baseline strengthens accepted-history and idempotency durability.

### Stage 3.5C

Durable read-side baseline strengthens projection-state and checkpoint durability.

### Stage 4

Compass evolves into runtime semantic validation and structured outcome generation.

### Stage 5

The system becomes a clear reviewer-facing demo and portfolio-ready story.

### Stage 6

Compass grows from validation into richer governance.
