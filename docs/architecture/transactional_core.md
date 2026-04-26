# Transactional Core
[← Back to Architectures Index](README.md)

## Purpose

This document describes the transactional core of the system.

The transactional core is the first major implementation milestone of the project.  
It is the part of the system responsible for producing semantically valid domain events and preserving a deterministic event history.

---

## Why the Transactional Core Comes First

The project does not start from analytics, chaos injection, or distributed deployment.

It starts from the transactional core because that is where semantic correctness is first defined.

Before the system can process failure, scale, or late data, it must first answer:

- what is a legal event?
- what is a legal state transition?
- what does version progression mean?
- how does replay reconstruct state?
- what is the minimum correctness baseline of the write-side path?

Without this boundary, later layers become unstable or ambiguous.

---

## Transactional Core Scope

The transactional core includes:

- domain event schema
- aggregate state machine
- proof / provenance claim structure
- event store
- idempotency handling
- transactional orchestration flow
- replay / rehydration

This is enough to form a minimal write-side semantic loop.

---

## Main Modules

### `src/core/order/`
Defines the order-domain semantics.

Main responsibilities:
- `OrderEvent`
- `Proof`
- `OrderAggregate`
- status / type definitions
- aggregate invariants

---

### `src/storage/event_store/`
Defines how event history is appended and loaded.

Main responsibilities:
- append event
- load event stream
- get last event
- enforce version continuity at persistence boundary

---

### `src/storage/idempotency_store/`
Defines request-level retry protection.

Main responsibilities:
- detect previously processed requests
- return previous result if needed
- persist request-to-event mapping

---

### `src/pipeline/transactional/`
Defines the write-side runtime flow.

Main responsibilities:
- command handling
- aggregate loading / creation
- replay
- event admission path
- event persistence coordination

---

### `src/compass/transition/`
Defines event-level semantic admission checks.

Main responsibilities:
- validate event truth
- compare proof claim against actual prior history
- reject semantically inconsistent candidate events

---

## Minimal Transactional Flow

The intended write-side flow is:

1. receive command
2. check idempotency
3. load or create aggregate
4. replay historical events if needed
5. produce candidate event
6. validate transition truth through Compass
7. admit event through concurrency gate / conditional persistence
8. apply accepted event to aggregate state
9. return result

This is the first semantic runtime loop of the system.

The key distinction is:

- Compass validation decides whether the candidate event is semantically trustworthy.
- The concurrency / admission boundary decides whether the candidate event can still become the next accepted fact.
  
---

## Key Invariants

The transactional core is expected to preserve at least the following:

- aggregate transitions must remain legal
- event sequence must remain continuous
- accepted events must be replayable
- replay must deterministically rebuild aggregate state
- if proof is used, proof claims must match actual history
- duplicate requests must not create duplicate semantic effects

---

## Current Practical Interpretation

At the current stage, the transactional core should be understood as a **semantic baseline**, not yet a production-distributed infrastructure.

That means:
- in-memory implementations are acceptable early on
- projection can remain a simple replay helper at first
- analytical processing can wait
- chaos scenarios can be simulated later

What matters first is that the transactional semantics are explicit, deterministic, and testable.

---

## What the Transactional Core Does NOT Yet Solve

At this stage, the transactional core does not fully solve:

- real projection runtime behavior
- checkpoint persistence
- event-time analytics
- distributed coordination
- full governance policy actions
- chaos hardening at scale

Those come later, after the core itself is clear.

---

## Why This Matters to the Whole Project

The transactional core is not just one subsystem among many.  
It is the foundation that later layers depend on.

- projection depends on accepted event history
- state-level Compass depends on projected state derived from that history
- chaos testing depends on the existence of a meaningful correctness baseline

If the transactional core is weak, the rest of the project becomes difficult to interpret.

---

## Summary

The transactional core is where the project first becomes semantically real.

It is the smallest part of the system that must already be coherent before streaming, analytics, failure modeling, and governance can be meaningfully layered on top.