# Architecture Decision Records

[← Back to Docs Home](../README.md)

This directory contains Architecture Decision Records (ADRs) for **Streaming System + Compass**.

ADRs are used to record important architecture decisions, including the context, decision, trade-offs, alternatives, and consequences.

They are not general notes or tutorials. Each ADR should answer:

- What decision was made?
- Why was it made?
- What alternatives were considered?
- What trade-offs were accepted?
- What future consequences does this create?

---

## ADR Index

| ADR | Title | Status | Purpose |
|---|---|---|---|
| 0001 | [Stateless Registry and Concurrency Strategy Boundary](0001_registry_stateless_and_concurrency_strategy.md) | Accepted | Defines the stateless registry baseline and concurrency strategy boundary. |
| 0002 | [Intent-Aware Validation Dispatch for Compass Runtime](0002_intent_aware_validation_dispatch.md) | Proposed | Defines the future Compass validation dispatch model. |
| 0003 | [Concurrency Control, Idempotency, and Retry Safety](0003_concurrency_idempotency_and_retry_safety.md) | Proposed | Defines write-side safety under concurrency, retries, and ambiguous commits. |

---

## Supporting Notes

| Note | Related ADR | Purpose |
|---|---|---|
| [ADR 0002 Evolution Note](0002_evolution_note.md) | [Intent-Aware Validation Dispatch for Compass Runtime](0002_intent_aware_validation_dispatch.md) | Records the design evolution behind ADR 0002. |

---

## How to Read ADRs

Recommended order:

1. [Stateless Registry and Concurrency Strategy Boundary](0001_registry_stateless_and_concurrency_strategy.md) — establishes the stateless registry and future concurrency-strategy boundary.
2. [Concurrency Control, Idempotency, and Retry Safety](0003_concurrency_idempotency_and_retry_safety.md) — expands the transactional safety model around concurrency, idempotency, retry behavior, reload, high-contention trade-offs, and future side-effect boundaries.
3. [Intent-Aware Validation Dispatch for Compass Runtime](0002_intent_aware_validation_dispatch.md) — explains the future Compass runtime validation dispatch model.
4. [ADR 0002 Evolution Note](0002_evolution_note.md) — optional supporting note that preserves how ADR 0002 evolved before reaching its current form.

ADR 0001 and ADR 0003 are closely related because both concern the transactional write-side path.

ADR 0002 is related to Compass runtime validation and should be read after the transactional baseline is understood.

The ADR 0002 evolution note is not a standalone decision. It is a supporting trace for understanding how ADR 0002 was refined.

---

## ADR Status Meaning

### Proposed

The decision is directionally accepted as a design candidate, but implementation may still be incomplete.

### Accepted

The decision has been adopted as the current project direction.

### Superseded

The decision has been replaced by a newer ADR.

---

## ADR Writing Rule

An ADR should not become a large tutorial.

If a topic requires a broader explanation, create a separate architecture note or reference note and link to it from the ADR.

---

## Naming Convention

Formal ADR files should use stable names without draft suffixes such as `v2`, `v3`, or `final`.

Recommended pattern:

```text
0001_registry_stateless_and_concurrency_strategy.md
0002_intent_aware_validation_dispatch.md
0003_concurrency_idempotency_and_retry_safety.md
```

Evolution or supporting notes may be kept as separate files:

```text
0002_evolution_note.md
```

This keeps formal decisions stable while preserving design history when needed.
