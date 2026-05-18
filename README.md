# 🧭 Streaming System + Compass

> ⚠️ This project is under active development. See [Current Status](#-current-status) for progress.

A failure-aware streaming system with invariant-driven correctness,  
validated through executable tests and later extended toward durable persistence, runtime semantic outcomes, and governance-oriented system reasoning.

---

## TL;DR

This is **not** a CRUD or ETL portfolio demo.

It is a production-inspired streaming-system project focused on:

- **accepted-history-first correctness**
- **semantic validation before persistence**
- **orthogonal idempotency / concurrency boundaries**
- **replay-safe projection runtime design**
- **exact-money hardening before durable persistence**

The project currently has:

- a completed write-side transactional baseline
- Compass Layer 1 transition-truth validation
- a Stage 3 baseline projection runtime with reducer / worker separation
- a completed Stage 3.5A decimal / money hardening step before durable persistence
- executable tests defending both write-side and read-side baseline semantics

The next major steps are:

- **Stage 3.5B — durable write-side baseline**
- **Stage 3.5C — durable read-side baseline**
- followed later by **runtime semantic validation and outcome structuring**

---

## Guide for Reviewers

If you only have a short amount of time:

- **1 minute**
  - read [Current Status](#-current-status)
  - scan the [High-Level Architecture](docs/architecture/high_level_architecture.md)

- **3 minutes**
  - read [Why Compass Split into Two Layers](docs/adr/0004_why_compass_split_into_two_layers.md)
  - read [Projection Pipeline](docs/architecture/projection_pipeline.md)

- **5 minutes**
  - read [Projection Boundary](docs/boundary_notes/projection_boundary.md)
  - read [Transactional Core](docs/architecture/transactional_core.md)
  - scan `tests/` and the Stage 3 projection worker / reducer path

If you want to understand how the repository thinks rather than only what it implements:

- read [Learning and Design Methodology](docs/philosophy/00_learning_and_design_methodology.md)
- read [Postmortems](docs/postmortems/README.md)

---

## Sharp Project Highlights

- **Accepted-history-first design**  
  Candidate events are not trusted merely because they can be written. Accepted history is protected by semantic validation and admission boundaries.

- **Layered semantic defense**  
  Compass is intentionally split into write-side transition-truth validation and later runtime state validation.

- **Orthogonal idempotency and concurrency boundaries**  
  Retry safety and stale-write protection are treated as different problems, not collapsed into one mechanism.

- **Replay-safe projection baseline**  
  The Stage 3 projection runtime uses reducer / worker separation and replay / rebuild through the same runtime path.

- **Exact-money pre-persistence hardening**  
  Stage 3.5A completed the migration from float-based money handling to Decimal-based semantics before durable persistence work expands.

- **Structured failure reasoning before governance**  
  The project now preserves the transition from generic exception-based failures toward structured semantic outcomes as the bridge to later layered trust and action-safety reasoning.

- **Documentation as architecture memory**  
  ADRs, boundary notes, postmortems, and philosophy notes are used to preserve why the system is shaped this way.

---

## 🔥 Project Positioning

This project is a production-inspired streaming system designed to solve three fundamental problems:

1. **Transactional Correctness**  
   Ensure state transitions are logically valid.

2. **Runtime Semantic Integrity**  
   Ensure derived runtime state remains faithful to accepted history.

3. **Failure Resilience under Adversarial Conditions**  
   Maintain correctness even under failures.

---

## 🧠 Core Insight

> One event stream, two semantic worlds  
> The same data, interpreted under different system semantics

- Transactional Pipeline → state transition
- Read-Side / Runtime Pipeline → derived runtime truth

---

## 🏗️ High-Level Architecture

```mermaid
flowchart TD
    A[Commands / Requests] --> B[Transactional Pipeline]
    B --> C[Compass Layer 1<br/>Transition Truth Validation]
    C --> D{Concurrency / Admission Gate}

    D -- Accepted --> E[(Event Log / Immutable History)]
    D -- Rejected / Conflict --> R[Reject / Retry Flow]

    E --> F[Projection Pipeline]
    F --> H[Derived Runtime State]
    H --> I[Compass Layer 2<br/>Runtime State Validation]
```

This architecture separates:

- **write-side admission**, where candidate events must pass semantic validation and concurrency-safe persistence
- **accepted immutable history**, where admitted events become the durable source of truth
- **read-side derivation**, where projection interprets accepted history into runtime state
- **runtime verification**, where Compass later validates whether projected state remains semantically correct

---

## ⚙️ Core Concepts

- Event-driven architecture
- Immutable event log as accepted history
- State as derived projection
- Invariant-driven validation through Compass
- Version-based admission and deterministic replay
- Clear separation between idempotency, concurrency control, and semantic validation

---

## 🔐 Compass: Semantic Validation and Governance

> Invariant = State Compression + Contract

Compass is the semantic validation layer of the system.

It begins with event-level transition truth validation and evolves toward runtime state verification, structured semantic outcomes, and later governance-oriented decisions.

At a high level:

- **Compass Layer 1** validates whether a candidate event truthfully follows accepted history.
- **Compass Layer 2** validates whether projected runtime state remains semantically correct.
- **Structured semantic outcomes** are the later bridge from raw failure detection toward reusable governance meaning.
- **Compass governance** later decides how the system should respond to violations.

Compass does not replace concurrency control.

Instead:

- Compass decides whether a candidate event is semantically trustworthy.
- The admission gate decides whether that candidate can still become the next accepted fact.
- Idempotency decides whether the external request has already been processed.

---

## 💣 Chaos Engineering

This system is intended to be validated through failure injection, including:

- poison messages
- partial commit failures
- duplicate events
- out-of-order events
- race conditions
- network jitter
- backpressure

Chaos scenarios do not define correctness.

They test whether the correctness mechanisms inside `src/` survive adversarial runtime conditions.

---

## 🎯 Key Principle

> A system is not correct because it works.  
> A system is correct because it preserves truth under failure.

---

## 🧪 What This Project Demonstrates

- Deterministic state recovery from accepted history
- Idempotent request handling with replay/conflict distinction
- Concurrency-safe event admission
- Candidate-event semantic validation before persistence
- Executable write-side invariants through tests
- Stage 3 baseline read-side projection runtime with reducer / worker separation
- Replay-safe projection state derivation with checkpoint-aware sequencing
- Decimal-based money semantics before durable persistence
- Clear separation between domain legality, transition truth, admission continuity, retry safety, and read-side derivation

---

## ❌ This is NOT

- A CRUD system
- A simple ETL pipeline
- An AWS deployment demo
- A dashboard-first analytics project

---

## 🚀 This IS

A production-inspired streaming system focused on:

- correctness
- reliability
- failure modeling
- semantic validation
- replayable state reconstruction
- durable-boundary design before broader runtime complexity

---

## 📂 Project Structure

```text
streaming-system-compass/
├── src/                # Semantic core and execution logic
│   ├── core/           # Transactional domain core
│   ├── pipeline/       # Transactional / projection / analytical flows
│   ├── storage/        # Persistence abstractions
│   ├── compass/        # Semantic validation and governance
│   └── bootstrap/      # Composition roots / runtime assembly
├── chaos_engine/       # Failure injection and adversarial testing
├── experiments/        # Demo scripts and isolated experiments
├── docs/               # Philosophy, architecture notes, ADRs, domain specs, boundary notes, roadmaps, postmortems
├── tests/              # Unit, integration, replay, semantic-case, and adversarial baseline tests
├── README.md
└── .gitignore
```

### How to Run Tests

From the repository root:

```bash
pip install -r requirements.txt
pytest -v
```

Run a specific test directory:

```bash
pytest tests/integration -v
```

---

## 📚 Documentation

The full documentation index starts at [docs/README.md](docs/README.md).

Key documentation areas:

- [Design Philosophy](docs/philosophy/README.md) — working methodology and mental models behind IBO, Core / Enabler separation, and Compass-style semantic alignment
- [Architecture Notes](docs/architecture/README.md) — subsystem architecture and runtime boundaries
- [Architecture Decision Records](docs/adr/README.md) — major design decisions and trade-offs
- [Domain Specifications](docs/domain/README.md) — versioned business rules and domain semantics
- [Boundary Notes](docs/boundary_notes/README.md) — module ownership and responsibility boundaries
- [Roadmaps](docs/roadmap/README.md) — implementation sequencing and system evolution
- [Postmortems](docs/postmortems/README.md) — design lessons and boundary reflections

### Design Philosophy

This project is guided by a small set of mental models:

- **Input / Bridge / Output (IBO)** for reasoning across function, pipeline, and system scales
- **Core / Enabler separation** for distinguishing business meaning from reliability mechanisms
- **Map / Compass alignment** for adapting static design to runtime disturbance

These notes are collected in [Design Philosophy](docs/philosophy/README.md).

They are not implementation proof. They explain the reasoning model behind the architecture, while executable correctness belongs in `src/` and `tests/`.

### Recommended Reading Order

1. [High-Level Architecture](docs/architecture/high_level_architecture.md)
2. [Learning and Design Methodology](docs/philosophy/00_learning_and_design_methodology.md)
3. [Transactional Core](docs/architecture/transactional_core.md)
4. [Order Domain v1 Rules](docs/domain/order_domain_v1_rules.md)
5. [Stateless Registry and Concurrency Strategy Boundary](docs/adr/0001_registry_stateless_and_concurrency_strategy.md)
6. [Concurrency Control, Idempotency, and Retry Safety](docs/adr/0003_concurrency_idempotency_and_retry_safety.md)
7. [Intent-Aware Validation Dispatch for Compass Runtime](docs/adr/0002_intent_aware_validation_dispatch.md)
8. [Why Compass Split into Two Layers](docs/adr/0004_why_compass_split_into_two_layers.md)
9. [Compass Layers](docs/architecture/compass_layers.md)
10. [Projection Pipeline](docs/architecture/projection_pipeline.md)
11. [Implementation Roadmap](docs/roadmap/implementation_roadmap.md)
12. [Compass Runtime Roadmap](docs/roadmap/compass_runtime_roadmap.md)
13. [Boundary Notes](docs/boundary_notes/README.md)
14. [Postmortems](docs/postmortems/README.md)

This order starts from the top-level system shape, then moves into working methodology, write-side semantics, domain rules, transactional safety decisions, Compass validation architecture, projection evolution, and implementation sequencing.

For the mental models behind the architecture, see [Design Philosophy](docs/philosophy/README.md), especially the notes on learning/design methodology, IBO, and Core / Enabler separation.

---

## 🧩 Implementation Strategy

The implementation begins from the **transactional semantic core** under `src/core/order/`.

This means the project does **not** start from chaos injection, dashboards, analytics, or cloud deployment.

Instead, it starts by defining and implementing:

- domain event semantics
- aggregate rules
- state transitions
- proof / provenance structure
- idempotency boundary
- concurrency-safe admission boundary
- core transactional invariants

Everything else grows around this core:

- `storage/` persists accepted history and protects version continuity
- `pipeline/` executes transactional and projection flows
- `compass/` validates semantic correctness
- `bootstrap/` assembles concrete runtime wiring
- `chaos_engine/` stress-tests whether mechanisms inside `src/` survive adversarial conditions

---

## 🧭 Roadmap

### Phase 1 — Deterministic Transactional Core

- transactional domain core
- event generation and replay
- idempotent request handling
- concurrency-safe admission / conditional persistence
- write-side consistency baseline

### Phase 2 — Event Truth Validation

- proof-carrying event structure
- event-level Compass validation
- transition truth checking before persistence
- validation dispatch and basic `ALLOW` / `BLOCK` policy

### Phase 3 — Projection Runtime + Exact-Money Hardening

- pure reducer
- checkpoint-aware projection worker
- projection state store
- checkpoint / offset handling
- replay and rebuild flow
- Decimal hardening before durable persistence

### Phase 3.5B / 3.5C — Durable Persistence Baseline

- durable write-side baseline
- durable read-side baseline
- persistence-backed replay / rebuild validation
- exact money durability
- append-only durable history and idempotency evolution

### Phase 4 — Runtime Semantic Validation and Outcome Structuring

- projected state invariants
- replay vs incremental consistency checks
- Layer 2 minimal validator
- structured semantic outcomes
- future Layer 1 / Layer 2 outcome-family alignment

### Phase 5 — Demo, Packaging, and Reviewer-Facing Story

- reviewer-friendly demo packaging
- documentation alignment
- clear implementation vs future-work boundary
- portfolio / open-source-ready milestone

### Phase 6 — Governance and Chaos Hardening

- advanced governance policy actions
- warning / quarantine / audit behavior
- evidence logging
- semantic alerts
- adversarial failure validation through chaos scenarios

---

## 🚧 Current Status

This repository is being built incrementally toward the full system design described above.

Current baseline completed:

- transactional semantic core under `src/core/order/`
- minimal `INIT -> CREATED -> PAID` write-side model
- accepted-history event store and replay baseline
- request-level idempotency with replay/conflict distinction
- optimistic admission gate for append-time continuity protection
- optimistic concurrency collision coverage for stale-write rejection
- Compass Layer 1 transition-truth validation
- runtime assembly through `src/bootstrap/`
- Stage 3 baseline projection runtime:
  - pure reducer
  - checkpoint-aware worker
  - in-memory projection state store
  - in-memory checkpoint store
  - replay / rebuild baseline
- Stage 3.5A exact-money hardening before durable persistence:
  - Decimal-based money semantics
  - aligned fixtures / unit / integration / semantic / adversarial / demo paths
  - formal projection reducer path as the only replay-reduction truth path
- executable tests across transactional legality, replay safety, transition-truth checks, semantic-case scenarios, adversarial histories, and Stage 3 baseline projection behavior

Current boundary of completion:

- write-side transactional baseline is established
- read-side projection baseline now exists in a deterministic in-memory form
- exact-money semantics are now stabilized before deeper durable persistence work
- failure-path reasoning is meaningfully executable across both write-side and Stage 3 baseline read-side paths
- persistent storage-backed runtime behavior is not yet implemented
- state-level Compass Layer 2 validation is not yet implemented

Next implementation milestone:

- Stage 3.5B durable write-side baseline
- Stage 3.5C durable read-side baseline
- later Stage 4 runtime semantic validation and outcome structuring, including the transition from exception-based failures toward structured semantic outcomes
- defer advanced runtime concerns such as DLQ, buffering, watermark semantics, and multi-worker coordination until after durable baseline semantics are clear

---

## 🧪 Development Note

This repository began with a documentation-first development approach.

The architecture, ADRs, domain rules, and boundary notes were written before the main transactional implementation to make ownership, invariants, and failure boundaries explicit.

That documentation-first phase has now been translated into an executable baseline across:

- `src/core/order/`
- `src/storage/`
- `src/pipeline/transactional/`
- `src/pipeline/projection/`
- `src/compass/transition/`
- `src/bootstrap/`
- `tests/`

The repository remains intentionally conservative:

- documentation defines semantic intent and ownership boundaries
- `src/` implements runtime logic
- `tests/` make selected invariants and failure paths executable
- the current Stage 3 baseline remains intentionally minimal and in-memory
- Stage 3.5A has hardened exact-money semantics before persistence expands
- later phases will extend this baseline toward durable persistence, runtime semantic outcomes, and adversarial hardening

---

## 📄 Notice and Usage

This repository is shared as a personal design research project and professional portfolio.

No open-source license has been granted yet. All rights are reserved unless a license is added later.

For usage, redistribution, attribution, and permission details, see [NOTICE.md](NOTICE.md).

---

## 📌 Author Note

This project focuses on system correctness under failure, not just successful execution under ideal conditions.

The main logic of correctness lives in `src/`.

`chaos_engine/` exists to test whether those correctness mechanisms can survive real failure conditions.

The documentation follows one main principle:

> Explain the boundary before explaining the implementation.

