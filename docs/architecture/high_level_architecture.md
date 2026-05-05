# High-Level Architecture

[← Back to Architectures Index](README.md)

## Purpose

This document describes the top-level structure of the Streaming System + Compass project.

The goal is not to explain every implementation detail, but to define the major layers of the system and how they relate to one another.

---

## System Goal

This project is a production-inspired streaming system focused on three concerns:

1. transactional correctness
2. analytical observability
3. failure resilience under adversarial conditions

The system is designed around the idea that correctness is not just successful execution, but semantic survival under failure.

---

## Core Architectural Principle

> One event stream, two semantic worlds.

The same accepted event history is interpreted under two different execution goals:

- the **transactional world**, where events drive domain state transitions and accepted-history truth
- the **analytical / observational world**, where events become read-side state, statistical signal, or operational evidence

This allows one accepted history to support both correctness-oriented and analytics-oriented processing.

---

## Top-Level Structure

```text
src/
├── core/          # semantic truth of the domain
├── storage/       # persistence boundaries
├── pipeline/      # runtime execution flows
├── compass/       # semantic validation and governance
chaos_engine/      # adversarial testing / failure injection
experiments/       # isolated demos and prototypes
docs/              # architecture notes, roadmaps, postmortems
tests/             # verification across levels
```

---

## Layer Responsibilities

### `src/core/`

Defines domain meaning.

This is where the system answers:

- what an event means
- what an aggregate means
- what a legal transition is
- which invariants belong to the domain itself

This is the semantic starting point of the project.

---

### `src/storage/`

Defines persistence boundaries.

This is where the system answers:

- how accepted history is appended and loaded
- how idempotency records are stored
- how projection state is persisted
- how checkpoints / offsets are tracked

Storage preserves semantic artifacts but does not define their meaning.

---

### `src/pipeline/`

Defines runtime movement.

This is where the system answers:

- how commands become candidate events
- how candidate events are admitted into accepted history
- how aggregates are rehydrated
- how projections are executed
- how analytical flows consume the event stream

Pipeline is the execution topology of the project.

---

### `src/compass/`

Defines semantic validation and governance.

This is where the system answers:

- whether a candidate event truthfully represents a legal transition before persistence
- whether projected state remains semantically valid after derivation
- whether violations should be accepted, warned, rejected, or quarantined

Compass is the semantic checking layer of the system.

At the current baseline, the implemented focus is still the write-side transition-truth layer.  
The later state-level/runtime verification layer remains part of the intended evolution.

---

### `chaos_engine/`

Defines adversarial test pressure.

This is where the system injects:

- duplicates
- out-of-order events
- poison messages
- partial commits
- timing distortions
- load pressure

Chaos does not define correctness.  
It tests whether the correctness mechanisms in `src/` actually survive real failure conditions.

---

## Runtime View

At a high level, the system evolves in this order:

1. define transactional domain semantics
2. define how accepted history is persisted and replayed
3. define how commands flow through the transactional pipeline
4. define how Compass validates event truth before persistence
5. define projection and read-side runtime execution
6. later validate projected/runtime state semantics
7. pressure the whole system using chaos scenarios

This sequencing reflects the design philosophy of the project:

- meaning first
- execution second
- validation third
- adversarial testing last

---

## Architectural Development Strategy

The project does not start from distributed deployment, cloud integration, or failure injection.

Instead, the implementation starts from:

- transactional semantic core
- event truth validation
- projection/runtime baseline correctness

Only after those are stable does the system expand toward:

- persistent storage-backed runtime behavior
- analytical processing
- richer governance policies
- chaos hardening
- broader failure modeling

---

## Summary

The architecture is intentionally layered.

- `core` defines truth
- `storage` preserves truth
- `pipeline` executes truth
- `compass` validates truth
- `chaos_engine` attacks truth

This separation is essential to keeping the project understandable as it evolves from a semantic prototype into a failure-aware streaming system.
