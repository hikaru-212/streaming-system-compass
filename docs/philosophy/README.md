# Design Philosophy

[← Back to Docs Home](../README.md)

This directory contains the design philosophy behind **Streaming System + Compass**.

These notes are not ADRs, architecture specifications, or implementation documents. They explain the mental models and working methodology that guide how the project separates meaning, execution, validation, reliability, recovery, and implementation sequencing.

The philosophy in this repository did not begin as a formal software-design theory.
It grew from practical debugging, self-directed system design, and repeated attempts to clarify what each layer should and should not own before implementation.

---

## Philosophy Notes

| Document                                                                            | Purpose                                                                                                                                                                                       |
| ----------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [Learning and Design Methodology](00_learning_and_design_methodology.md)            | Explains the working method behind the project, including definition alignment, boundary clarification, documentation-first thinking, and AI-assisted defensive review before implementation. |
| [IBO and Core/Enabler Origin](01_ibo_core_enabler_origin.md)                        | Records the original engineering insight behind Input–Bridge–Output and Core vs Enablers, starting from debugging and Airflow experience.                                                     |
| [Unified Design Philosophy](02_unified_design_philosophy.md)                        | Extends IBO and Core/Enabler into a broader model of static blueprint, dynamic navigation, and disturbance recovery.                                                                          |
| [Core/Enabler as Semantic Fusion of SoC and DIP](03_core_enabler_soc_dip_fusion.md) | Connects the Core/Enabler model to traditional software architecture principles such as Separation of Concerns and Dependency Inversion.                                                      |
| [Data Infrastructure vs Semantic Infrastructure](04_data_infra_vs_semantic_infra.md)   | Records the future-oriented philosophy that physical infrastructure preserves facts, while Semantic Infrastructure evaluates whether those facts still preserve meaning.                      |

---

## Recommended Reading Order

1. [Learning and Design Methodology](00_learning_and_design_methodology.md)
2. [IBO and Core/Enabler Origin](01_ibo_core_enabler_origin.md)
3. [Unified Design Philosophy](02_unified_design_philosophy.md)
4. [Core/Enabler as Semantic Fusion of SoC and DIP](03_core_enabler_soc_dip_fusion.md)
5. [Data Infrastructure vs Semantic Infrastructure](04_data_infra_vs_semantic_infra.md)

This order matters because the philosophy in this repository has two layers:

* first, how the project is actually learned, clarified, and implemented
* second, the conceptual models that emerged from that process

The methodology note comes first because it explains how unclear concepts are stabilized before implementation.
The later notes explain the philosophy that grew out of that discipline.

The Data Infrastructure vs Semantic Infrastructure note comes last because it extends the earlier Core/Enabler and dependency-inversion thinking into a future architecture direction:

```text
physical correctness
does not automatically imply
semantic correctness
```

---

## How These Notes Relate to the Project

| Philosophy Concept                         | Project Expression                                                                                                                               |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Definition alignment before implementation | Boundary notes, ADRs, and staged implementation before code expansion                                                                            |
| Input → Bridge → Output                    | Command → Transactional Pipeline → Accepted Event / Derived State                                                                                |
| Core                                       | Domain rules, aggregate legality, event semantics, pure state transition logic                                                                   |
| Enablers                                   | Idempotency, validation, concurrency gate, projection worker, checkpointing, recovery mechanisms                                                 |
| Static Blueprint                           | README, architecture notes, ADRs, domain specifications                                                                                          |
| Dynamic Navigation                         | retry safety, reload, projection verification, chaos hardening                                                                                   |
| Compass                                    | Runtime semantic correction and validation                                                                                                       |
| Data Infrastructure                        | PostgreSQL persistence, transaction atomicity, event-store append behavior, idempotency memory, checkpoint storage, projection-state persistence |
| Semantic Infrastructure                    | Compass Layer 1 / Layer 2 validation, SemanticOutcome, RuntimeDecisionPolicy, retry classification, snapshot trust, action safety                |

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
* future separation between physical infrastructure and semantic governance

The executable realization belongs in `src/`, and the formal architecture / decision records belong in the other `docs/` directories.