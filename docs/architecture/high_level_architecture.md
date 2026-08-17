# High-Level Architecture

[← Back to Architectures Index](README.md)

## Purpose

This document describes the top-level structure of the Streaming System + Compass project.

The goal is not to explain every implementation detail, but to define the major layers of the system and how they relate to one another.

> **Current implementation checkpoint after Stage 4C PR0:** The repository has
> durable PostgreSQL write-side and read-side baselines, exact-next per-order
> projection progress under ADR 0020, completed bounded trace and measurement
> evidence, `SemanticOutcome`, a `DecisionReceipt` serialization and persistence
> foundation, and the completed Order Correctness Contract v0. Projection
> snapshots remain optional derived reference infrastructure for the current
> Order workload. Receipt materialization is not automatic. Stage 4C PR0
> completed documentation and responsibility alignment; production Runtime
> Decision Authority is next but not yet frozen or implemented. Stage 4D
> Strategy Selection Authority and Stage 4E Retry / Attempt Authorization are
> future responsibilities.

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
chaos_engine/      # failure-scenario documentation / placeholder infrastructure
experiments/       # isolated demos and prototypes
docs/              # architecture notes, roadmaps, postmortems
tests/             # verification across levels, including executable adversarial tests
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
- how per-order projection progress and legacy checkpoints are tracked
- how versioned DecisionReceipt envelopes are persisted

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
- how bounded producer evidence is interpreted as `SemanticOutcome` and may be
  preserved as governance evidence

Compass is the semantic checking layer of the system.

At the current baseline, write-side transition truth remains the enforcement
layer. Stage 4A and Stage 4B implement semantic-outcome and receipt-evidence
contracts for bounded write-side, read-side, and snapshot producers. Stage
4B.1, Stage 4B.2, and Stage 4B.5 add bounded trace, measurement, and exact-rule
evidence. Stage 4C production Runtime Decision Authority is next; Stage 4D
strategy selection, conditional Stage 4E retry / attempt authorization, and
action execution remain later, separately owned responsibilities.

---

### `chaos_engine/`

Preserves failure-scenario documentation and placeholder infrastructure.

Executable adversarial correctness tests currently live under
`tests/adversarial/`. The `chaos_engine/` directory records possible pressure
such as:

- duplicates
- out-of-order events
- poison messages
- partial commits
- timing distortions
- load pressure

These scenarios do not define correctness, and their presence does not claim an
implemented general chaos runtime.

---

## Runtime View

At a high level, the system evolves in this order:

1. define transactional domain semantics
2. define how accepted history is persisted and replayed
3. define how commands flow through the transactional pipeline
4. define how Compass validates event truth before persistence
5. define projection and read-side runtime execution
6. map bounded technical evidence into `SemanticOutcome`
7. explicitly preserve selected evidence in `DecisionReceipt`, trace, or
   measurement contracts when the relevant caller chooses to do so
8. use live semantic evidence for Stage 4C current-response authority without
   requiring prior receipt persistence
9. later hand authorized responses to Stage 4D strategy selection, and enter
   Stage 4E only when another attempt is considered
10. validate selected failure scenarios through executable adversarial tests

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

- `core` defines domain semantics
- `storage` preserves authoritative and derived data according to their boundaries
- `pipeline` orchestrates candidate, admission, persistence, and derivation flows
- `compass` validates semantic claims and interprets bounded evidence
- adversarial tests pressure the truth-preserving boundaries

This separation is essential to keeping the project understandable as it evolves from a semantic prototype into a failure-aware streaming system.
