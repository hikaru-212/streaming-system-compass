# Design Philosophy

[← Back to Docs Home](../README.md)

This directory contains the design philosophy behind **Streaming System + Compass**.

These notes are not ADRs, architecture specifications, or implementation documents. They explain the mental models and working methodology that guide how the project separates meaning, execution, validation, reliability, recovery, and implementation sequencing.

The philosophy in this repository did not begin as a formal software-design theory.
It grew from practical debugging, self-directed system design, and repeated attempts to clarify what each layer should and should not own before implementation.

---

## Philosophy Notes

| Document | Purpose |
|---|---|
| [Learning and Design Methodology](00_learning_and_design_methodology.md) | Explains the working method behind the project, including definition alignment, boundary clarification, documentation-first thinking, and AI-assisted defensive review before implementation. |
| [IBO and Core/Enabler Origin](01_ibo_core_enabler_origin.md) | Records the original engineering insight behind Input–Bridge–Output and Core vs Enablers, starting from debugging and Airflow experience. |
| [Unified Design Philosophy](02_unified_design_philosophy.md) | Extends IBO and Core/Enabler into a broader model of static blueprint, dynamic navigation, and disturbance recovery. |
| [Core/Enabler as Semantic Fusion of SoC and DIP](03_core_enabler_soc_dip_fusion.md) | Connects the Core/Enabler model to traditional software architecture principles such as Separation of Concerns and Dependency Inversion. |
| [Data Infrastructure vs Semantic Infrastructure](04_data_infra_vs_semantic_infra.md) | Records the future-oriented philosophy that physical infrastructure preserves facts, while Semantic Infrastructure evaluates whether those facts still preserve meaning. |
| [Policy Evolution to Runtime Truth](05_policy_evolution_to_runtime_truth.md) | Records the future direction where machine-readable policy contracts, Compass runtime admission, and structured semantic outcomes connect into a governance loop. |
| [AI Suggestions Are Candidate Actions](06_ai_suggestions_are_candidate_actions.md) | Records a methodology case study showing why AI-generated explanations and designs are treated as candidate actions that must pass repository-specific admission before becoming accepted documentation or implementation. |
| [From Local ETL to Streaming System + Compass](07_from_local_etl_to_streaming_system_compass.md) | Records the project-origin path from local ETL friction and Airflow debugging into Core vs Enablers, semantic correctness, and streaming / event sourcing as the runtime body for Compass. |

---

## Recommended Reading Order

1. [Learning and Design Methodology](00_learning_and_design_methodology.md)
2. [IBO and Core/Enabler Origin](01_ibo_core_enabler_origin.md)
3. [From Local ETL to Streaming System + Compass](from_local_etl_to_streaming_system_compass.md)
4. [Unified Design Philosophy](02_unified_design_philosophy.md)
5. [Core/Enabler as Semantic Fusion of SoC and DIP](03_core_enabler_soc_dip_fusion.md)
6. [Data Infrastructure vs Semantic Infrastructure](04_data_infra_vs_semantic_infra.md)
7. [Policy Evolution to Runtime Truth](05_policy_evolution_to_runtime_truth.md)
8. [AI Suggestions Are Candidate Actions](06_ai_suggestions_are_candidate_actions.md)

This order matters because the philosophy in this repository has two layers:

* first, how the project is actually learned, clarified, and implemented
* second, the conceptual models that emerged from that process

The methodology note comes first because it explains how unclear concepts are stabilized before implementation.
The IBO and Core/Enabler note records the first compact mental model.
The project-origin note then explains how those early debugging and ETL insights evolved into Streaming System + Compass.
The later notes explain the philosophy that grew out of that discipline.

The Data Infrastructure vs Semantic Infrastructure note extends the earlier Core/Enabler and dependency-inversion thinking into a future architecture direction:

```text
physical correctness
does not automatically imply
semantic correctness
```

The Policy Evolution to Runtime Truth note comes after that because it extends Semantic Infrastructure into a broader governance loop:

```text
intended correctness
→ runtime truth
→ semantic outcome
→ recovery evidence
→ policy evolution
```

The AI Suggestions Are Candidate Actions note is a concrete methodology case study. It shows how the same candidate-vs-accepted discipline used by Compass also applies to AI-assisted design work:

```text
AI-generated suggestion
→ repository-specific review
→ accepted documentation / implementation
```

---

## How These Notes Relate to the Project

| Philosophy Concept | Project Expression |
|---|---|
| Definition alignment before implementation | Boundary notes, ADRs, and staged implementation before code expansion |
| AI suggestions as candidate actions | AI-generated explanations are reviewed against actual schema, dependency direction, and repository boundaries before becoming accepted docs or code |
| Input → Bridge → Output | Command → Transactional Pipeline → Accepted Event / Derived State |
| Core | Domain rules, aggregate legality, event semantics, pure state transition logic |
| Enablers | Idempotency, validation, concurrency gate, projection worker, checkpointing, recovery mechanisms |
| Local ETL friction | Early source of the project’s boundary-first debugging discipline |
| Airflow as an enabler | Example of separating operational orchestration from core business transformation |
| Streaming / event sourcing as Compass body | Concrete runtime where candidate actions, accepted history, replay, projection, and trust boundaries can be tested |
| Static Blueprint | README, architecture notes, ADRs, domain specifications |
| Dynamic Navigation | retry safety, reload, projection verification, chaos hardening |
| Compass | Runtime semantic correction and validation |
| Data Infrastructure | PostgreSQL persistence, transaction atomicity, event-store append behavior, idempotency memory, checkpoint storage, projection-state persistence |
| Semantic Infrastructure | Compass Layer 1 / Layer 2 validation, SemanticOutcome, RuntimeDecisionPolicy, retry classification, snapshot trust, action safety |
| Policy Contract | Future machine-readable representation of domain rules, rule evolution, recovery strategies, replay requirements, and policy-guided retry |
| Runtime Truth Boundary | Compass admission check that decides whether a concrete candidate action can enter accepted system truth |
| Semantic Evidence and Recovery | Structured outcomes that connect rejection evidence back to policy rules, runtime decisions, replay, recovery, or escalation |

---

## Boundary

These philosophy notes are not implementation proof.

They explain why the project emphasizes:

* boundary clarity
* Core vs Enabler separation
* semantic validation
* failure-aware design
* documentation before implementation
* defensive review before coding
* AI-assisted design review without surrendering architectural ownership
* future separation between physical infrastructure and semantic governance
* future connection between policy evolution, runtime admission, structured outcomes, and recovery evidence

The executable realization belongs in `src/`, and the formal architecture / decision records belong in the other `docs/` directories.
