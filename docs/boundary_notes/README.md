# Boundary Notes

[← Back to Docs Home](../README.md)

## Purpose

This folder contains boundary notes for the core modules and cross-cutting boundaries of the project.

These notes are not meant to replace implementation or architecture documents.  
Their purpose is narrower and more practical:

- clarify what each module or boundary is responsible for
- clarify what each module or boundary is **not** responsible for
- reduce semantic confusion during implementation
- preserve design intent as the codebase grows

---

## Why This Folder Exists

As the project evolved, it became clear that many implementation questions were not caused by syntax alone.

They were often caused by **boundary confusion**, such as:

- which module owns a given value
- whether a function should decide something or only carry it
- whether a layer validates meaning, stores it, or derives it
- whether a component belongs to write-side truth, read-side derivation, or runtime governance

Because of that, these notes exist as a middle layer between:

- high-level architecture documents
- low-level code implementation

They help keep the project readable at the module-boundary level.

---

## What These Notes Are For

Boundary notes are especially useful when asking questions such as:

- Why does this parameter get passed in rather than computed here?
- Why is this module not allowed to decide that value?
- Why does this layer validate but not persist?
- Why does projection ignore some event metadata?
- Why is proof used in transition validation but not in projection logic?
- Why does concurrency control not replace Compass validation?
- Why does Compass validation not replace persistence admission?
- Why is projection split into reducer and worker rather than one mixed component?
- Why does transactional consistency not mean boundary merge?
- Why does a projection worker need a global cursor instead of aggregate-local sequence?
- Why does replay validation compare against projection state without making projection state the source of truth?

These are not merely coding-style questions.  
They are boundary questions.

---

## What These Notes Are NOT

These notes are **not** intended to be:

- full architecture specifications
- user-facing documentation
- API references
- implementation details for every function

Those concerns belong elsewhere:

- architecture → [`docs/architecture/`](../architecture/README.md)
- ADRs → [`docs/adr/`](../adr/README.md)
- roadmap → [`docs/roadmap/`](../roadmap/README.md)
- code → `src/`
- tests → `tests/`

---

## Current Notes

This folder currently includes notes for the most important module and cross-cutting boundaries of the project:

- [Event Module Boundary](event_module.md)
- [Proof Module Boundary](proof_module.md)
- [Aggregate Module Boundary](aggregate_module.md)
- [Event Store Module Boundary](event_store_module.md)
- [Idempotency Module Boundary](idempotency_module.md)
- [Registry Module Boundary](registry_module.md)
- [Concurrency Boundary](concurrency_boundary.md)
- [PostgreSQL Concurrency Admission Boundary](postgres_concurrency_admission_boundary.md)
- [Validation Placement Strategy Boundary](validation_placement_strategy_boundary.md)
- [Projection Module Boundary](projection_module.md)
- [Projection Runtime Boundary](projection_boundary.md)
- [Checkpoint Module Boundary](checkpoint_module.md)
- [Global-Position Projection Worker Boundary](global_position_projection_worker_boundary.md)
- [Durable Replay / Rebuild Validation Boundary](durable_replay_rebuild_validation_boundary.md)
- [Compass Layer Boundary](compass_layer_boundary.md)
- [Persistence Boundary](persistence_boundary.md)
- [Stage 3.5B Write-Side Schema Translation Note](stage3.5B_write_side_schema_translation_note.md)
- [Read-Side Persistence Boundary](read_side_persistence_boundary.md)

These were prioritized because they directly affect the main implementation stages of the project.

The PostgreSQL concurrency admission note is intentionally separate from the older concurrency boundary note. The older note explains the conceptual distinction between idempotency, retry safety, and concurrency control. The PostgreSQL concurrency admission note records the Stage 3.5B PR5 implementation boundary: translating writer competition into stable admission results without leaking raw database exceptions upward.

The validation placement strategy note builds on ADR 0011 and PR5 admission. It records the Stage 3.5B PR6 / Stage 4 Prelude boundary for comparing `IN_TRANSACTION` Compass validation against `PRE_TRANSACTION` validation plus append-time concurrency admission.

Two projection-related notes are intentionally preserved:

- **Projection Module Boundary** describes the external role of projection as a whole.
- **Projection Runtime Boundary** describes the internal Stage 3 boundary between reducer, worker, projection store, and checkpoint store.

The global-position projection worker note extends the projection runtime boundary for Stage 3.5C PR4. It clarifies why a durable PostgreSQL-backed projection worker needs a global event-log cursor instead of using aggregate-local `order_events.sequence`.

The durable replay / rebuild validation note extends the projection boundary for Stage 3.5C PR5. It clarifies how accepted history should be replayed through the canonical reducer and compared with durable projection state without turning projection state into the source of truth or prematurely introducing Compass Layer 2.

The persistence-related notes are also intentionally separate:

- **Persistence Boundary** explains how durable storage should be introduced without collapsing the boundaries between event store, idempotency store, projection state, and checkpoint progress.
- **Read-Side Persistence Boundary** explains how `projection_states` and `projection_checkpoints` should be treated as derived state and operational metadata rather than accepted-history truth.
- **Stage 3.5B Write-Side Schema Translation Note** explains how Python-side guarantees such as `frozen=True`, append-only accepted history, and exact money semantics should be translated into database-side physical constraints before durable write-side implementation begins.

---

## How to Use These Notes

A practical reading order is:

1. [Event Module Boundary](event_module.md)
2. [Proof Module Boundary](proof_module.md)
3. [Aggregate Module Boundary](aggregate_module.md)
4. [Event Store Module Boundary](event_store_module.md)
5. [Idempotency Module Boundary](idempotency_module.md)
6. [Registry Module Boundary](registry_module.md)
7. [Concurrency Boundary](concurrency_boundary.md)
8. [PostgreSQL Concurrency Admission Boundary](postgres_concurrency_admission_boundary.md)
9. [Validation Placement Strategy Boundary](validation_placement_strategy_boundary.md)
10. [Projection Module Boundary](projection_module.md)
11. [Projection Runtime Boundary](projection_boundary.md)
12. [Checkpoint Module Boundary](checkpoint_module.md)
13. [Global-Position Projection Worker Boundary](global_position_projection_worker_boundary.md)
14. [Durable Replay / Rebuild Validation Boundary](durable_replay_rebuild_validation_boundary.md)
15. [Compass Layer Boundary](compass_layer_boundary.md)
16. [Persistence Boundary](persistence_boundary.md)
17. [Read-Side Persistence Boundary](read_side_persistence_boundary.md)
18. [Stage 3.5B Write-Side Schema Translation Note](stage3.5B_write_side_schema_translation_note.md)

This roughly follows the intended semantic development order of the project:

- define event meaning
- define proof meaning
- define aggregate decision logic
- define persistence boundaries
- define request safety boundaries
- define orchestration boundaries
- define concurrency / admission boundaries
- define PostgreSQL admission results
- define validation placement strategy after admission exists
- define projection as read-side derivation
- define projection runtime internals
- define runtime progress boundaries
- define durable worker cursor strategy
- define durable replay / rebuild validation against accepted history
- define semantic validation layers
- define durable-world persistence discipline
- define read-side persistence semantics
- define how Python-side semantic guarantees are restated at the database boundary

---

## Relationship to the Rest of the Project

These notes should be read together with:

- [Order Core README](../../src/core/order/README.md)
- [Storage README](../../src/storage/README.md)
- [Pipeline README](../../src/pipeline/README.md)
- [Projection Pipeline README](../../src/pipeline/projection/README.md)
- [Compass README](../../src/compass/README.md)
- [Transactional Core](../architecture/transactional_core.md)
- [Compass Layers](../architecture/compass_layers.md)
- [Projection Pipeline](../architecture/projection_pipeline.md)
- [Persistent Storage Baseline](../architecture/persistent_storage_baseline.md)
- [Write-Side Schema Baseline](../architecture/write_side_schema_baseline.md)
- [Read-Side Schema Baseline](../architecture/read_side_schema_baseline.md)
- [Implementation Roadmap](../roadmap/implementation_roadmap.md)
- [Compass Runtime Roadmap](../roadmap/compass_runtime_roadmap.md)
- [Deferred Architecture Backlog](../roadmap/deferred_architecture_backlog.md)
- [Concurrency Control, Idempotency, and Retry Safety](../adr/0003_concurrency_idempotency_and_retry_safety.md)
- [Persistent Storage Baseline Strategy](../adr/0005_persistent_storage_baseline_strategy.md)
- [Separate Transaction Atomicity from Concurrency Admission](../adr/0010_transaction_atomicity_vs_concurrency_admission.md)
- [Separate Validation Mode from Validation Placement Strategy](../adr/0011_validation_mode_vs_validation_placement.md)
- [Two-Phase Concurrency Admission for PostgreSQL Write-Side](../adr/0012_two_phase_concurrency_admission.md)

A good rule of thumb is:

- if you are confused about **what the system is trying to become**, read the roadmap
- if you are confused about **how the major layers relate**, read the architecture docs
- if you are confused about **why a decision was made**, read the ADRs
- if you are confused about **what one module or boundary should or should not do**, read the boundary notes

---

## Guiding Principle

The main purpose of this folder is to prevent this kind of failure:

> entering code-level detail before module-level responsibility is clear

In other words:

- first set the scale
- then identify the role
- then inspect the detail

This keeps implementation aligned with the system’s semantic design rather than letting local code decisions drift into architectural confusion.

---

## Summary

This folder is a practical design aid.

It exists to make module and cross-cutting boundaries explicit before they become accidental.
