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

---

## Recommended Reading Order

1. [High-Level Architecture](high_level_architecture.md)
2. [Transactional Core](transactional_core.md)
3. [Compass Layers](compass_layers.md)
4. [Projection Pipeline](projection_pipeline.md)

This order reflects the dependency structure of the project:

```text
top-level system structure
→ transactional truth
→ write-side transition-truth validation
→ projected runtime state
→ state-level runtime validation
```

---

## Architecture Notes vs ADRs

Architecture notes describe the shape of a subsystem.

ADRs explain why a specific decision was made.

For example:

- `high_level_architecture.md` explains how the major system layers relate to one another.
- `transactional_core.md` explains what the transactional core is.
- `compass_layers.md` explains what the layered Compass architecture is.
- `adr/0003_concurrency_idempotency_and_retry_safety.md` explains a specific decision inside the transactional write-side path.
- `adr/0004_why_compass_split_into_two_layers.md` explains why Compass evolved from a single runtime-verification idea into two layers.

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
