# Documentation Guide

[← Back to Project README](../README.md)

This directory contains the design documentation for **Streaming System + Compass**.

The goal of this documentation set is not only to describe what the system does, but also to preserve the reasoning behind major architectural decisions, implementation sequencing, domain boundaries, module responsibilities, design philosophy, and lessons learned during development.

At the current stage, the documentation no longer represents only intended architecture.
It now also serves as the reference frame for an initial executable baseline covering:

- transactional write-side semantics
- Compass Layer 1 transition-truth validation
- write-side replay and admission boundaries
- executable failure-path tests for selected invariants and adversarial cases

---

## Current Position

The repository currently has an implemented baseline for:

- transactional semantic core
- accepted-history persistence and replay
- request-level idempotency and replay/conflict distinction
- optimistic admission for stale-write rejection
- Compass Layer 1 validation before persistence
- executable tests across unit, integration, semantic-case, and adversarial-baseline layers

The next major implementation step is:

- projection runtime
- projection state storage
- replay / rebuild flow
- checkpoint semantics
- eventual state-level Compass validation

---

## How to Read These Docs

Recommended reading order:

1. [High-Level Architecture](architecture/high_level_architecture.md)
2. [Learning and Design Methodology](philosophy/00_learning_and_design_methodology.md)
3. [Transactional Core](architecture/transactional_core.md)
4. [Order Domain v1 Rules](domain/order_domain_v1_rules.md)
5. [Stateless Registry and Concurrency Strategy Boundary](adr/0001_registry_stateless_and_concurrency_strategy.md)
6. [Concurrency Control, Idempotency, and Retry Safety](adr/0003_concurrency_idempotency_and_retry_safety.md)
7. [Intent-Aware Validation Dispatch for Compass Runtime](adr/0002_intent_aware_validation_dispatch.md)
8. [Why Compass Split into Two Layers](adr/0004_why_compass_split_into_two_layers.md)
9. [Compass Layers](architecture/compass_layers.md)
10. [Projection Pipeline](architecture/projection_pipeline.md)
11. [Implementation Roadmap](roadmap/implementation_roadmap.md)
12. [Compass Runtime Roadmap](roadmap/compass_runtime_roadmap.md)
13. [Boundary Notes](boundary_notes/README.md)
14. [Postmortems](postmortems/README.md)

This order starts from the system-level architecture, then moves into the working methodology behind the repository, the transactional write-side baseline, domain semantics, architecture decisions, Compass validation design, projection runtime evolution, implementation sequencing, and finally module-boundary notes and postmortems.

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
→ projection runtime
→ implementation sequencing
→ boundary clarification
→ postmortem lessons
```

---

## Directory Structure

```text
docs/
├── philosophy/        # Design philosophy and mental models
├── architecture/      # Subsystem-level architecture notes
├── adr/               # Architecture Decision Records
├── boundary_notes/    # Module ownership and responsibility boundaries
├── domain/            # Versioned domain specifications and domain decision notes
├── roadmap/           # Implementation sequencing and evolution plans
└── postmortems/       # Design lessons, mistakes, and boundary reflections
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

### [domain/](domain/README.md)

Domain-level specifications and domain decision notes.

Use these documents when you want to understand:

- what a business state or event means
- which domain rules the aggregate must enforce
- which domain constraints are in scope for the current version
- which semantic limitations are intentionally deferred
- how the domain model is expected to evolve over time

---

### [boundary_notes/](boundary_notes/README.md)

Module-level and cross-boundary responsibility notes.

Use these documents when you want to understand:

- what one module owns
- what one module must not own
- where a value is decided
- which layer validates, persists, derives, or governs meaning
- how to avoid semantic confusion during implementation

---

### [roadmap/](roadmap/README.md)

Sequencing documents that describe implementation order and dependency structure.

Use these documents when you want to understand:

- what has already been established
- what should be built next
- what depends on what
- how the system should evolve across stages
- which features are intentionally deferred

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
| What has already been built and what comes next? | [Roadmaps](roadmap/README.md) |
| What mistake or confusion should not be repeated? | [Postmortems](postmortems/README.md) |

---

## Documentation Principle

The documentation follows one main principle:

> Explain the boundary before explaining the implementation.

This project is built around semantic correctness, replayability, failure awareness, and runtime validation.

The documentation should therefore make ownership, invariants, and trade-offs explicit before code becomes too large to reason about.

In short:

```text
first define meaning
then define ownership
then define runtime flow
then write implementation
```
