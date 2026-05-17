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
| 0004 | [Why Compass Split into Two Layers](0004_why_compass_split_into_two_layers.md) | Accepted | Records why the project evolved from a single runtime-verification idea into layered Compass validation. |
| 0005 | [Persistent Storage Baseline Strategy](0005_persistent_storage_baseline_strategy.md) | Proposed | Defines why the next stage after the in-memory Stage 3 baseline should be a PostgreSQL-backed persistent storage baseline. |
| 0006 | [Use Decimal for Money Values Before Durable Persistence](0006_use_decimal_for_money_values_before_durable_persistence.md) | Proposed | Defines why money-like values should move from `float` to `Decimal` before the durable write-side baseline grows larger. |
| 0007 | [Separate Semantic Correctness from Operational Trust](0007_separate_semantic_correctness_from_operational_trust.md) | Proposed | Defines why future trust evaluation should separate semantic correctness, projection correctness, operational trust, and action safety. |
| 0008 | [Pre-Allocated Event Identity and Candidate/Accepted Event Naming Boundary](0008_pre_allocated_event_identity_and_candidate_accepted_boundary.md) | Proposed | Defines the lifecycle naming boundary for pre-allocated event IDs before durable write-side persistence. |

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
5. [Why Compass Split into Two Layers](0004_why_compass_split_into_two_layers.md) — explains why the project moved from one runtime-verification intuition to a layered Compass structure.
6. [Persistent Storage Baseline Strategy](0005_persistent_storage_baseline_strategy.md) — explains why the next stage should prioritize durable persistence before advanced runtime complexity.
7. [Use Decimal for Money Values Before Durable Persistence](0006_use_decimal_for_money_values_before_durable_persistence.md) — explains why exact money representation should be corrected before durable persistence expands further.
8. [Pre-Allocated Event Identity and Candidate/Accepted Event Naming Boundary](0008_pre_allocated_event_identity_and_candidate_accepted_boundary.md) — explains why pre-allocated event IDs remain acceptable, while candidate and accepted event identities must be named explicitly before durable write-side persistence.
9. [Separate Semantic Correctness from Operational Trust](0007_separate_semantic_correctness_from_operational_trust.md) — explains why future trust evaluation should not collapse semantic correctness, projection correctness, operational trust, and action safety into one boolean.

ADR 0001 and ADR 0003 are closely related because both concern the transactional write-side path.

ADR 0002 is related to Compass runtime validation and should be read after the transactional baseline is understood.

ADR 0004 is related to the evolution from event-level validation to state-level validation.

ADR 0005 is related to the transition from the current in-memory baseline into durable persistence-backed execution.

ADR 0006 is related to money representation hardening before the write-side durable baseline grows larger.

ADR 0008 is related to the transition into Stage 3.5B. It records the event identity lifecycle rule used before durable persistence: pre-allocated `event_id` values may exist before append, but only event-log membership grants accepted-history status. This ADR should be read before modifying admission, event-store, validation-result, or future outcome schemas.

ADR 0007 is related to the future evolution from structured semantic outcomes into layered trust verdicts. It should be read after ADR 0004, ADR 0005, and ADR 0006 because it assumes the reader already understands the Compass layering, persistent-storage direction, and current Stage 3.5 implementation priority.

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
0004_why_compass_split_into_two_layers.md
0005_persistent_storage_baseline_strategy.md
0006_use_decimal_for_money_values_before_durable_persistence.md
0007_separate_semantic_correctness_from_operational_trust.md
0008_pre_allocated_event_identity_and_candidate_accepted_boundary.md
```

Evolution or supporting notes may be kept as separate files:

```text
0002_evolution_note.md
```

This keeps formal decisions stable while preserving design history when needed.
