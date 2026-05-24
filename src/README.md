# Source Tree

[← Back to Project README](../README.md)

This directory contains the main implementation modules for **Streaming System + Compass**.

If the project README explains the system at a portfolio / repository level, `src/` is where that design becomes executable.

The purpose of this layer is not to repeat the full top-level README.
Instead, it explains how the implementation is organized inside the source tree and how the main runtime layers relate to one another.

---

## Purpose

The purpose of `src/` is to hold the executable system boundaries for:

- domain meaning
- persistence boundaries
- runtime execution flow
- semantic validation
- composition / runtime assembly

This is the implementation center of the repository.

---

## Top-Level Structure

```text
src/
├── core/       # semantic truth of the domain
├── storage/    # persistence boundaries
├── pipeline/   # runtime execution flow
├── compass/    # semantic validation and governance
└── bootstrap/  # composition roots / runtime wiring
```

---

## Directory Guide

### [core/](core/README.md)

Semantic source of truth for the domain.

Use this directory when you want to understand:

- what an event means
- what an aggregate means
- what a legal transition is
- which invariants belong to domain semantics
- which shared semantic primitives support the domain

Current shared semantic primitives include exact money handling and centralized event identity generation under `core/common/`.

---

### [storage/](storage/README.md)

Persistence boundaries for accepted history and runtime progress.

Use this directory when you want to understand:

- how accepted history is persisted
- how idempotency records are stored
- how projection state is stored
- how checkpoint progress is tracked
- how PostgreSQL-backed durable storage is being introduced

At the current Stage 3.5B PR2 checkpoint, storage includes the first PostgreSQL-backed accepted-history implementation through `PostgresEventStore`.

---

### [pipeline/](pipeline/README.md)

Runtime execution flow around domain meaning and persistence.

Use this directory when you want to understand:

- transactional command handling
- replay / rehydration flow
- projection runtime execution
- later analytical pipeline evolution

---

### [compass/](compass/README.md)

Semantic validation and later governance behavior.

Use this directory when you want to understand:

- write-side transition-truth validation
- later state-level validation
- how semantic trust is checked separately from persistence and flow

---

### [bootstrap/](bootstrap/README.md)

Composition roots and runtime wiring.

Use this directory when you want to understand:

- how concrete implementations are instantiated
- how runtime objects are connected
- why wiring is kept separate from business meaning

---

## Reading Order

If you are reading the implementation from scratch, the recommended order is:

1. [core/](core/README.md)
2. [storage/](storage/README.md)
3. [pipeline/](pipeline/README.md)
4. [compass/](compass/README.md)
5. [bootstrap/](bootstrap/README.md)

This reflects the logic of the project:

```text
meaning
→ persistence boundary
→ runtime movement
→ semantic validation
→ concrete wiring
```

Another useful way to think about it is:

- `core/` defines what the system means
- `storage/` preserves accepted history and runtime progress
- `pipeline/` defines how meaning moves through the system
- `compass/` checks whether that movement remains semantically trustworthy
- `bootstrap/` decides how concrete implementations are wired together

---

## Current Baseline

At the current stage, `src/` already contains an executable baseline across:

- transactional write-side semantics
- accepted-history persistence and replay
- request-level idempotency handling
- optimistic admission / stale-write rejection
- Compass Layer 1 transition-truth validation
- Stage 3 baseline projection runtime in deterministic in-memory form
- Stage 3.5A exact-money hardening
- Stage 3.5B PR1 PostgreSQL schema / local setup / migration baseline
- Stage 3.5B PR2 PostgreSQL-backed accepted-history baseline through `PostgresEventStore`

This means `src/` is no longer only a semantic skeleton.
It already contains the first closed executable loop for both:

- write-side admission
- read-side projection baseline

It is also now beginning to support durable write-side persistence.

---

## Current Durable Persistence Position

The current durable write-side path is intentionally staged:

```text
Stage 3.5B PR1 — PostgreSQL schema / local setup / migration ✅
Stage 3.5B PR2 — PostgresEventStore baseline ✅
Stage 3.5B PR3 — PostgresIdempotencyStore planned
Stage 3.5B PR4 — transactional write-side boundary planned
```

The current durable baseline means accepted event history can now be persisted through PostgreSQL-backed storage.

However, the full durable write-side flow is not complete until idempotency persistence and transaction coordination are also implemented.

---

## Current Implementation Philosophy

The source tree follows the same philosophy as the documentation:

> explain the boundary before enlarging the implementation

That means:

- keep meaning separate from movement
- keep storage separate from domain rules
- keep semantic validation separate from persistence admission
- keep composition separate from business logic
- keep durable persistence separate from domain meaning

This separation is especially important because the project is concerned with correctness under failure, not just successful execution.

---

## What `src/` Does Not Yet Fully Solve

At the current stage, the source tree does **not yet** fully solve:

- fully transactionally coordinated durable write-side behavior
- durable idempotency storage
- durable read-side projection / checkpoint storage
- state-level Compass Layer 2 validation
- advanced runtime concerns such as DLQ, buffering, watermarking, or multi-worker coordination
- full analytical pipeline implementation
- governance behavior beyond the earlier validation / enforcement boundary

Those remain later stages of the repository.

---

## Summary

`src/` is the executable heart of the repository.

If the top-level README explains what the project is about, `src/` shows how that design is actually partitioned into:

- meaning
- persistence
- movement
- validation
- wiring

That partition is the main reason the project can evolve without collapsing its own boundaries.
