# Source Tree

[← Back to Project README](../README.md)

This directory contains the main implementation modules for **Streaming System + Compass**.

If the project README explains the system at a portfolio / repository level, `src/` is where that design becomes executable.

The purpose of this layer is not to repeat the full top-level README. Instead, it explains how the implementation is organized inside the source tree and how the main runtime layers relate to one another.

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

The core should remain independent of PostgreSQL, worker orchestration, projection snapshots, runtime decisions, and future governance policy. It defines the meaning that the rest of the system must preserve.

---

### [storage/](storage/README.md)

Persistence boundaries for accepted history, idempotency memory, projection state, checkpoint progress, and projection snapshots.

Use this directory when you want to understand:

- how accepted history is persisted
- how idempotency records are stored
- how projection state is stored
- how checkpoint progress is tracked
- how projection snapshots are persisted
- how PostgreSQL-backed durable storage is introduced without making storage own business meaning
- how accepted history is loaded for durable projection workers and snapshot-assisted replay paths

At the current baseline, storage includes:

- PostgreSQL-backed accepted-history persistence through `PostgresEventStore`
- PostgreSQL-backed idempotency memory through `PostgresIdempotencyStore`
- PostgreSQL-backed projection state through `PostgresProjectionStore`
- PostgreSQL-backed checkpoint progress through `PostgresCheckpointStore`
- global-position accepted-history loading through `PostgresProjectionEventSource`
- projection snapshot persistence through `PostgresProjectionSnapshotStore`
- shared database-row-to-domain-event hydration through `order_event_hydration.py`

Storage preserves durable facts and durable runtime progress. It does not decide whether those facts are semantically valid.

---

### [pipeline/](pipeline/README.md)

Runtime execution flow around domain meaning and persistence.

Use this directory when you want to understand:

- transactional command handling
- replay / rehydration flow
- projection runtime execution
- PostgreSQL-backed write-side orchestration
- PostgreSQL-backed read-side projection worker orchestration
- durable replay / rebuild validation
- snapshot-assisted replay validation and state resolution
- later analytical pipeline evolution

At the current baseline, pipeline includes:

- the durable transactional write-side path completed in Stage 3.5B
- the deterministic in-memory projection baseline from Stage 3
- the PostgreSQL-backed projection worker baseline completed in Stage 3.5C PR4
- the durable replay / rebuild validation baseline completed in Stage 3.5C PR5
- the projection snapshot-assisted replay validator completed in Stage 3.5D PR4
- the projection snapshot-assisted state resolver completed in Stage 3.5D PR4.5
- the aggregate snapshot trust deferral boundary completed in Stage 3.5D PR5

Pipeline defines movement. It should coordinate storage, core, and Compass, but it should not collapse their responsibilities.

---

### [compass/](compass/README.md)

Semantic validation and later governance behavior.

Use this directory when you want to understand:

- write-side transition-truth validation
- later state-level validation
- how semantic trust is checked separately from persistence and flow
- how future structured outcomes and runtime decisions may be produced

At the current baseline, Compass Layer 1 protects accepted-history admission on the write side.

Stage 3.5D does not implement full Compass Layer 2. However, the snapshot-assisted replay validator and resolver provide important read-side evidence substrates for future Layer 2 validation:

```text
accepted history
→ projection reducer
→ projection snapshot / projection state
→ validator / resolver evidence
→ future Layer 2 outcome
```

Future Compass layers will validate derived read-side state, structured semantic outcomes, runtime decisions, action safety, and dual-dimension governance.

---

### [bootstrap/](bootstrap/README.md)

Composition roots and runtime wiring.

Use this directory when you want to understand:

- how concrete implementations are instantiated
- how runtime objects are connected
- why wiring is kept separate from business meaning

Bootstrap should assemble concrete storage, pipeline, and Compass objects. It should not define domain legality, persistence semantics, projection correctness, or governance policy.

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

At the current stage, after Stage 3.5D completion, `src/` contains an executable baseline across:

- transactional write-side semantics
- accepted-history persistence and replay
- request-level idempotency handling
- optimistic and pessimistic PostgreSQL-backed admission
- Compass Layer 1 transition-truth validation
- validation placement strategy
- Stage 3 baseline projection runtime in deterministic in-memory form
- Stage 3.5A exact-money hardening
- Stage 3.5B durable write-side baseline through PostgreSQL
- Stage 3.5C durable read-side schema baseline
- PostgreSQL-backed projection state persistence
- PostgreSQL-backed checkpoint progress persistence
- PostgreSQL-backed global-position projection worker baseline
- durable replay / rebuild validation against accepted history
- Stage 3.5D projection snapshot schema and store baseline
- Stage 3.5D projection snapshot-assisted replay validation
- Stage 3.5D projection snapshot-assisted state resolution
- explicit aggregate snapshot trust deferral

This means `src/` is no longer only a semantic skeleton.

It now contains durable executable loops for both:

- write-side accepted-history mutation
- read-side projection-state derivation
- accepted-history replay validation against persisted projection state
- projection snapshot-assisted replay / resolution without treating snapshots as authority

---

## Current Durable Persistence Position

The durable write-side path is complete at the Stage 3.5B baseline level:

```text
Stage 3.5B PR1 — PostgreSQL schema / local setup / migration ✅
Stage 3.5B PR2 — PostgresEventStore baseline ✅
Stage 3.5B PR3 — PostgresIdempotencyStore ✅
Stage 3.5B PR4 — Transactional Semantic Write-Side Boundary ✅
Stage 3.5B PR5 — PostgreSQL Concurrency Admission Boundary ✅
Stage 3.5B PR6 — Validation Placement Strategy Boundary / Stage 4 Prelude ✅
```

The durable read-side path is complete through the Stage 3.5C baseline:

```text
Stage 3.5C PR1 — Durable Read-Side Schema Baseline ✅
Stage 3.5C PR2 — PostgresProjectionStore ✅
Stage 3.5C PR3 — PostgresCheckpointStore ✅
Stage 3.5C PR4 — Global-Position Projection Worker Baseline ✅
Stage 3.5C PR5 — Durable Replay / Rebuild Validation Baseline ✅
```

The snapshot trust / replay-efficiency path is complete through the Stage 3.5D baseline:

```text
Stage 3.5D PR1 — General Snapshot Trust Contract Boundary ✅
Stage 3.5D PR2 — Projection Snapshot Schema Baseline ✅
Stage 3.5D PR3 — PostgresProjectionSnapshotStore ✅
Stage 3.5D PR4 — Projection Snapshot-Assisted Replay Validator ✅
Stage 3.5D PR4.5 — Projection Snapshot-Assisted State Resolver ✅
Stage 3.5D PR5 — Aggregate Snapshot Trust Boundary / Deferral Decision ✅
```

The current read-side durable worker path is:

```text
order_events
→ PostgresProjectionEventSource
→ canonical reducer
→ PostgresProjectionStore
→ PostgresCheckpointStore

accepted history
→ durable replay validator
→ expected projection state
→ persisted projection state comparison
```

The current snapshot-assisted read-side path is:

```text
accepted history
→ projection snapshot
→ snapshot-assisted replay validator
→ authority comparison evidence

qualified projection snapshot
→ snapshot-assisted state resolver
→ tail replay
→ resolved projection state
```

The worker persists:

```text
projection state
+
checkpoint progress
```

inside one PostgreSQL transaction boundary.

Snapshots remain derived artifacts:

```text
accepted history = authority
projection state = derived runtime state
projection snapshot = derived state compression
```

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
- keep projection state as derived state, not accepted-history truth
- keep checkpoint state as operational progress metadata, not business truth
- keep snapshots as derived compression, not authority
- keep aggregate snapshot trust separate from projection snapshot trust because aggregate snapshots may later affect command validation

This separation is especially important because the project is concerned with correctness under failure, not just successful execution.

---

## What `src/` Does Not Yet Fully Solve

After the completed Stage 3.5D snapshot trust / replay-efficiency baseline, the source tree does **not yet** fully solve:

- Stage 3.5E durable history / permission hardening
- database role separation for accepted-history protection
- production-grade append-only enforcement at the database permission / trigger layer
- state-level Compass Layer 2 validation as a general runtime subsystem
- structured `SemanticOutcome`
- runtime decision policy
- action safety
- advanced runtime concerns such as DLQ, buffering, watermarking, worker leasing, checkpoint row locking, or multi-worker coordination
- full analytical pipeline implementation
- governance behavior beyond the current validation / enforcement boundary

Those remain later stages of the repository.

Stage 3.5D specifically closed the projection snapshot trust baseline. It did not turn snapshots into authority, did not implement write-side aggregate snapshot rehydration, and did not introduce full runtime governance.

---

## Current Boundary Summary

The current source-tree boundaries can be summarized as:

```text
core/
= domain meaning and transition legality

storage/
= durable accepted history, idempotency memory, projection state, checkpoint progress, snapshot rows, and accepted-history loading

pipeline/
= runtime orchestration for write-side commands, read-side projection workers, replay validation, and snapshot-assisted read-side resolution

compass/
= semantic validation and future governance

bootstrap/
= concrete runtime wiring
```

The most important current source-of-truth distinction is:

```text
order_events
= accepted-history truth

projection_states
= derived runtime view

projection_checkpoints
= operational worker progress

projection_snapshots
= derived state compression / replay-efficiency artifact
```

If there is disagreement between accepted history and any derived artifact, accepted history wins.

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

After Stage 3.5D, the source tree has durable write-side, durable read-side, and snapshot-assisted read-side replay / resolution baselines. The next implementation stage is Stage 3.5E, which should harden durable accepted-history authority through minimal actor / permission boundaries without turning the project into a full access-control platform.
