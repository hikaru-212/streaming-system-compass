# Documentation Guide

[← Back to Project README](../README.md)

This directory contains the design documentation for **Streaming System + Compass**.

The goal of this documentation set is not only to describe what the system does, but also to preserve the reasoning behind major architectural decisions, implementation sequencing, domain boundaries, module responsibilities, design philosophy, local development setup, and lessons learned during development.

At the current stage, the documentation no longer represents only intended architecture.
It now also serves as the reference frame for an executable baseline covering:

- transactional write-side semantics
- Compass Layer 1 transition-truth validation
- write-side replay and admission boundaries
- Stage 3 baseline projection runtime in deterministic in-memory form
- Stage 3.5A exact-money hardening before durable persistence
- Stage 3.5B durable write-side schema reasoning
- PostgreSQL-backed accepted-history and idempotency persistence
- PostgreSQL-backed transactional write-side execution
- PostgreSQL-backed two-phase concurrency admission
- validation placement strategy for `IN_TRANSACTION` and `PRE_TRANSACTION` write-side orchestration
- local PostgreSQL development setup for durable write-side work
- executable failure-path tests for selected invariants and adversarial cases
- Stage 3.5C durable read-side baseline
- Stage 3.5D Snapshot Trust Contract and replay-efficiency planning

---

## Current Position

The repository currently has an implemented baseline for:

- transactional semantic core
- accepted-history persistence and replay in the original in-memory baseline
- request-level idempotency and replay/conflict distinction
- optimistic admission for stale-write rejection
- Compass Layer 1 validation before persistence
- Stage 3 baseline projection runtime with reducer / worker separation
- in-memory projection state and checkpoint persistence boundaries
- Stage 3.5A decimal / money hardening before durable persistence
- formal projection reducer path as the only replay-reduction truth path
- Stage 3.5B durable write-side schema and local PostgreSQL setup
- PostgreSQL-backed accepted-history persistence through `PostgresEventStore`
- PostgreSQL-backed idempotency memory through `PostgresIdempotencyStore`
- PostgreSQL-backed transactional semantic write-side execution
- PostgreSQL-backed two-phase concurrency admission through `prepare_stream(order_id)` and `append_if_admitted(candidate_event, expected_current_version)`
- validation placement strategy for `IN_TRANSACTION` and `PRE_TRANSACTION` write-side orchestration
- executable tests across unit, integration, semantic-case, adversarial-baseline, Stage 3 projection-baseline, storage integration, transactional PostgreSQL-backed write-side, and admission-boundary layers
- Stage 3.5C durable read-side baseline, including durable order-event vocabulary hardening, read-side schema, `PostgresProjectionStore`, `PostgresCheckpointStore`, global-position projection worker orchestration, and durable replay / rebuild validation

The repository has completed **Stage 3.5B — Durable Write-Side Baseline** and **Stage 3.5C — Durable Read-Side Baseline**.

Stage 3.5C is now complete at the durable read-side baseline level.

The current focus is now:

- preparing **Stage 3.5D — Snapshot Trust Contract / replay-efficiency work**
- keeping Stage 3.5E durable history hardening and Stage 4 Compass Layer 2 governance deferred to their proper stages
- preserving the completed Stage 3.5C durable read-side baseline as the stable foundation for the next stage

The next major implementation steps are:

- Stage 3.5D Snapshot Trust Contract / persistence optimization / replay efficiency
- Stage 3.5E durable history and permission hardening
- Stage 4 runtime semantic validation, semantic outcome structuring, retry reason classification, runtime decision policy, and action safety

---

## How to Read These Docs

Recommended reading order:

1. [High-Level Architecture](architecture/high_level_architecture.md)
2. [Learning and Design Methodology](philosophy/00_learning_and_design_methodology.md)
3. [Transactional Core](architecture/transactional_core.md)
4. [Order Domain v1 Rules](domain/order_domain_v1_rules.md)
5. [Stateless Registry and Concurrency Strategy Boundary](adr/0001_registry_stateless_and_concurrency_strategy.md)
6. [Concurrency Control, Idempotency, and Retry Safety](adr/0003_concurrency_idempotency_and_retry_safety.md)
7. [Separate Transaction Atomicity from Concurrency Admission](adr/0010_transaction_atomicity_vs_concurrency_admission.md)
8. [Separate Validation Mode from Validation Placement Strategy](adr/0011_validation_mode_vs_validation_placement.md)
9. [Two-Phase Concurrency Admission for PostgreSQL Write-Side](adr/0012_two_phase_concurrency_admission.md)
10. [Intent-Aware Validation Dispatch for Compass Runtime](adr/0002_intent_aware_validation_dispatch.md)
11. [Why Compass Split into Two Layers](adr/0004_why_compass_split_into_two_layers.md)
12. [Compass Layers](architecture/compass_layers.md)
13. [Projection Pipeline](architecture/projection_pipeline.md)
14. [Implementation Roadmap](roadmap/implementation_roadmap.md)
15. [Compass Runtime Roadmap](roadmap/compass_runtime_roadmap.md)
16. [Implementation Notes](implementation_notes/README.md)
17. [Boundary Notes](boundary_notes/README.md)
18. [Development Setup](development/README.md)
19. [Postmortems](postmortems/README.md)

This order starts from the system-level architecture, then moves into the working methodology behind the repository, the transactional write-side baseline, domain semantics, architecture decisions, Compass validation design, projection runtime evolution, implementation sequencing, stage / PR implementation details, module-boundary notes, local development setup, and finally postmortems.

For the mental models and working methodology behind the architecture, see [Design Philosophy](philosophy/README.md), especially the notes on learning/design methodology, IBO, and Core / Enabler separation.

The key progression is:

```text
top-level system structure
→ learning/design methodology
→ transactional semantic core
→ domain rules
→ stateless registry boundary
→ concurrency / retry safety
→ validation dispatch mechanism
→ Compass layer evolution
→ projection runtime baseline
→ exact-money hardening before durable persistence
→ durable write-side schema and local PostgreSQL setup
→ durable write-side baseline
→ validation placement strategy
→ completed durable read-side baseline
→ snapshot trust / replay efficiency
→ implementation notes for stage / PR execution
→ durable history hardening
→ runtime semantic validation and outcome structuring
→ runtime decision policy and action safety
→ boundary clarification
→ postmortem lessons
```

---

## Directory Structure

```text
docs/
├── philosophy/             # Design philosophy and mental models
├── architecture/           # Subsystem-level architecture notes
├── adr/                    # Architecture Decision Records
├── boundary_notes/         # Module ownership and responsibility boundaries
├── implementation_notes/   # Stage-level and PR-level implementation planning notes
├── development/            # Local development setup and environment notes
├── domain/                 # Versioned domain specifications and domain decision notes
├── roadmap/                # Implementation sequencing and evolution plans
└── postmortems/            # Design lessons, mistakes, and boundary reflections
```

---

## Directory Purposes

### [philosophy/](philosophy/README.md)

Design philosophy and working methodology behind the project.

Use these documents when you want to understand:

- how the project reasons about systems across different scales
- how the repository is learned, clarified, and implemented
- why Input / Bridge / Output is used as a recurring mental model
- why Core / Enabler separation matters
- why Compass is treated as a semantic correction layer
- how boundary clarity informs architecture, implementation, and debugging

These notes are not implementation proof. They explain the reasoning model and working method behind the architecture.

---

### [architecture/](architecture/README.md)

Long-form architecture notes describing subsystem roles, boundaries, and intended evolution.

Use these documents when you want to understand:

- what a subsystem is responsible for
- what it intentionally does not own
- how it relates to the rest of the system
- what future evolution is expected
- how durable write-side schema decisions should be shaped before implementation grows larger

---

### [adr/](adr/README.md)

Architecture Decision Records.

Use these documents when you want to understand:

- what decision was made
- why the decision was chosen
- what alternatives were considered
- what trade-offs were accepted
- what future consequences the decision creates

ADRs are decision records, not general tutorials.

---

### [boundary_notes/](boundary_notes/README.md)

Module-level and cross-boundary responsibility notes.

Use these documents when you want to understand:

- what one module owns
- what one module must not own
- where a value is decided
- which layer validates, persists, derives, or governs meaning
- how to avoid semantic confusion during implementation
- how Python-side guarantees should be translated into database-side boundaries
- why validation placement and append-time admission must remain separate

---

### [implementation_notes/](implementation_notes/README.md)

Stage-level and PR-level implementation planning notes.

Use these documents when you want to understand:

- how a stage should be implemented
- how a PR sequence is intended to unfold
- which schema, store, validator, or runtime behavior belongs to a specific PR
- what detailed scope / non-goals / validation plan should guide implementation
- which implementation hazards have already been identified
- how roadmap-level sequencing should become concrete work without overloading the roadmap

Implementation notes sit between roadmaps and code.

They are more concrete than roadmaps, but they should not become source-code comments or API references.

---

### [development/](development/README.md)

Local development setup notes.

Use these documents when you want to understand:

- how to start local development infrastructure
- how to run the local PostgreSQL environment
- which ports, credentials, and connection URLs are used for local development
- which setup choices are local-only and not production-grade
- which development environment boundaries must remain explicit

These documents are not architecture decisions.
They are practical setup notes for running and testing the project locally.

---

### [domain/](domain/README.md)

Domain-level specifications and domain decision notes.

Use these documents when you want to understand:

- what a business state or event means
- which domain rules the aggregate must enforce
- which domain constraints are in scope for the current version
- which semantic limitations are intentionally deferred
- how the domain model is expected to evolve over time

---

### [roadmap/](roadmap/README.md)

Sequencing documents that describe implementation order and dependency structure.

Use these documents when you want to understand:

- what has already been established
- what should be built next
- what depends on what
- how the system should evolve across stages
- which features are intentionally deferred

Roadmaps should preserve stage-level direction and dependency logic.

Detailed PR execution notes should gradually move into `implementation_notes/` as stages grow larger.

---

### [postmortems/](postmortems/README.md)

Reflection documents that preserve design mistakes, confusion points, and lessons learned.

Use these documents when you want to understand:

- why a previous interpretation was confusing
- what boundary mistake occurred
- what reusable lesson should be preserved
- how future implementation should avoid similar mistakes

---

## Documentation Type Guide

| Question | Read |
|---|---|
| What mental models and working method guide the project? | [Design Philosophy](philosophy/README.md) |
| What is the whole system trying to become? | [Architecture Notes](architecture/README.md) and [Roadmaps](roadmap/README.md) |
| What does this business state or event mean? | [Domain Specifications](domain/README.md) |
| Why was this architecture direction chosen? | [ADRs](adr/README.md) |
| Which module owns this responsibility? | [Boundary Notes](boundary_notes/README.md) |
| How should this stage or PR be executed? | [Implementation Notes](implementation_notes/README.md) |
| How do I run local development infrastructure? | [Development Setup](development/README.md) |
| What has already been built and what comes next? | [Roadmaps](roadmap/README.md) |
| What mistake or confusion should not be repeated? | [Postmortems](postmortems/README.md) |

---

## Documentation Principle

The documentation follows one main principle:

> Explain the boundary before explaining the implementation.

This project is built around semantic correctness, replayability, failure awareness, durable truth, and runtime validation.

The documentation should therefore make ownership, invariants, environment boundaries, and trade-offs explicit before code becomes too large to reason about.

In short:

```text
first define meaning
then define ownership
then define runtime flow
then define local execution boundary
then write implementation
```
