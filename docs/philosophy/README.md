# Design Philosophy

[← Back to Docs Home](../README.md)

This directory contains the design philosophy behind **Streaming System + Compass**.

These notes are not ADRs, architecture specifications, or implementation documents. They explain the mental models that guide how the project separates meaning, execution, validation, reliability, and recovery.

The philosophy grew from practical debugging and data-engineering experience, then evolved into a broader system-design model.

---

## Philosophy Notes

| Document | Purpose |
|---|---|
| [IBO and Core/Enabler Origin](01_ibo_core_enabler_origin.md) | Records the original engineering insight behind Input–Bridge–Output and Core vs Enablers, starting from debugging and Airflow experience. |
| [Unified Design Philosophy](02_unified_design_philosophy.md) | Extends IBO and Core/Enabler into a broader model of static blueprint, dynamic navigation, and disturbance recovery. |
| [Core/Enabler as Semantic Fusion of SoC and DIP](03_core_enabler_soc_dip_fusion.md) | Connects the Core/Enabler model to traditional software architecture principles such as Separation of Concerns and Dependency Inversion. |

---

## Recommended Reading Order

1. [IBO and Core/Enabler Origin](01_ibo_core_enabler_origin.md)
2. [Unified Design Philosophy](02_unified_design_philosophy.md)
3. [Core/Enabler as Semantic Fusion of SoC and DIP](03_core_enabler_soc_dip_fusion.md)

This order matters because the philosophy did not begin as a formal software-design theory. It began from debugging, workflow friction, and the need to distinguish the work itself from the tools that protect or enable the work.

---

## How These Notes Relate to the Project

| Philosophy Concept | Project Expression |
|---|---|
| Input → Bridge → Output | Command → Transactional Pipeline → Accepted Event / Derived State |
| Core | Domain rules, aggregate legality, event semantics |
| Enablers | Idempotency, validation, concurrency gate, projection, checkpointing |
| Static Blueprint | README, architecture notes, ADRs, domain specifications |
| Dynamic Navigation | retry safety, reload, projection verification, chaos hardening |
| Compass | Runtime semantic correction and validation |

---

## Boundary

These philosophy notes are not implementation proof.

They explain why the project emphasizes:

- boundary clarity
- Core vs Enabler separation
- semantic validation
- failure-aware design
- documentation before implementation

The executable realization belongs in `src/`, and the formal architecture / decision records belong in the other `docs/` directories.
