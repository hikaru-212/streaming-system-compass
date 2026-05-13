# Architecture Notes

[← Back to Docs Home](../README.md)

This directory contains subsystem-level architecture notes for **Streaming System + Compass**.

Unlike ADRs, these documents do not primarily record one-time decisions. They describe the role, boundary, and intended evolution of major system components.

Use these documents to understand how the system is structured and why each subsystem exists.

---

## Architecture Document Index

| Document | Purpose |
|---|---|
| [High-Level Architecture](high_level_architecture.md) | Defines the top-level system structure and major layer responsibilities. |
| [Transactional Core](transactional_core.md) | Defines the write-side semantic baseline and transactional flow. |
| [Compass Layers](compass_layers.md) | Defines Compass as layered semantic validation and governance. |
| [Projection Pipeline](projection_pipeline.md) | Defines the evolution from a replay helper to a Stage 3 baseline projection runtime built around reducer, worker, state persistence, and checkpoint progression. |
| [Persistent Storage Baseline](persistent_storage_baseline.md) | Defines Stage 3.5 as the durable persistence extension of the current in-memory baseline, including write-side-first and read-side-second evolution. |
| [Write-Side Schema Baseline](write_side_schema_baseline.md) | Defines the first durable write-side schema baseline for `events` and `idempotency_records`, including semantic fingerprint evolution and transaction grouping rationale. |

---

## Recommended Reading Order

1. [High-Level Architecture](high_level_architecture.md)
2. [Transactional Core](transactional_core.md)
3. [Compass Layers](compass_layers.md)
4. [Projection Pipeline](projection_pipeline.md)
5. [Persistent Storage Baseline](persistent_storage_baseline.md)
6. [Write-Side Schema Baseline](write_side_schema_baseline.md)

This order reflects the dependency structure of the project:

```text
top-level system structure
→ transactional truth
→ write-side transition-truth validation
→ projected runtime state
→ durable persistence evolution
→ durable write-side schema hardening
→ later state-level runtime validation
```

---

## Architecture Notes vs ADRs

Architecture notes describe the shape of a subsystem.

ADRs explain why a specific decision was made.

For example:

- `high_level_architecture.md` explains how the major system layers relate to one another.
- `transactional_core.md` explains what the transactional core is.
- `compass_layers.md` explains what the layered Compass architecture is.
- `projection_pipeline.md` explains how projection evolved into a Stage 3 baseline runtime path.
- `persistent_storage_baseline.md` explains how the project should move from in-memory correctness into durable persistence-backed execution.
- `write_side_schema_baseline.md` explains how the durable write-side schema should be shaped before implementation grows larger.
- `adr/0003_concurrency_idempotency_and_retry_safety.md` explains a specific decision inside the transactional write-side path.
- `adr/0004_why_compass_split_into_two_layers.md` explains why Compass evolved from a single runtime-verification idea into two layers.
- `adr/0005_persistent_storage_baseline_strategy.md` explains why Stage 3.5 should prioritize PostgreSQL-backed durable persistence before more advanced runtime concerns.
- `adr/0006_use_decimal_for_money_values_before_durable_persistence.md` explains why exact decimal money representation should be introduced before durable persistence grows larger.

Both are important, but they answer different questions.

---

## Architecture Documentation Principle

Every architecture note should make these boundaries clear:

- what this subsystem owns
- what this subsystem does not own
- what inputs it consumes
- what outputs it produces
- what invariants it must preserve
- what future evolution is expected
