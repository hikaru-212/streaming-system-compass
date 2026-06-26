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
| 0009 | [Write-Side Persistence Driver and Identity Generation Boundary](0009_write_side_persistence_driver_and_identity_boundary.md) | Proposed | Defines why the Stage 3.5B write-side persistence baseline uses explicit PostgreSQL driver access and centralized event ID generation instead of ORM-driven persistence or immediate UUIDv7 migration. |
| 0010 | [Separate Transaction Atomicity from Concurrency Admission](0010_transaction_atomicity_vs_concurrency_admission.md) | Proposed | Separates PR4 transaction atomicity from PR5 PostgreSQL concurrency admission. |
| 0011 | [Separate Validation Mode from Validation Placement Strategy](0011_validation_mode_vs_validation_placement.md) | Proposed | Separates validation strength from where validation runs relative to the database transaction boundary. |
| 0012 | [Two-Phase Concurrency Admission for PostgreSQL Write-Side](0012_two_phase_concurrency_admission.md) | Proposed | Evolves PR5 admission from append-time-only admission into two-phase stream preparation plus append-time admission. |
| 0013 | [Snapshot Runtime Eligibility and Validation Receipt Boundary](0013_snapshot_runtime_eligibility_and_validation_receipt_boundary.md) | Proposed | Separates PR4.5 snapshot-assisted state resolution from future runtime eligibility policy and persisted validation receipts. |

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
9. [Write-Side Persistence Driver and Identity Generation Boundary](0009_write_side_persistence_driver_and_identity_boundary.md) — explains why the Stage 3.5B write-side persistence baseline uses explicit PostgreSQL driver access and centralizes event identity generation before deeper durable write-side code is added.
10. [Separate Transaction Atomicity from Concurrency Admission](0010_transaction_atomicity_vs_concurrency_admission.md) — explains why PR4 transaction atomicity does not eliminate the need for PR5 PostgreSQL concurrency admission.
11. [Separate Validation Mode from Validation Placement Strategy](0011_validation_mode_vs_validation_placement.md) — explains why validation strength and validation placement should be modeled as separate design axes before future validation placement strategies are introduced.
12. [Two-Phase Concurrency Admission for PostgreSQL Write-Side](0012_two_phase_concurrency_admission.md) — explains why PR5 evolves from append-time-only admission into two-phase stream preparation plus append-time admission.
13. [Separate Semantic Correctness from Operational Trust](0007_separate_semantic_correctness_from_operational_trust.md) — explains why future trust evaluation should not collapse semantic correctness, projection correctness, operational trust, and action safety into one boolean.
14. [Snapshot Runtime Eligibility and Validation Receipt Boundary](0013_snapshot_runtime_eligibility_and_validation_receipt_boundary.md) — explains why PR4.5 resolver usage must stay separate from future runtime eligibility policy, fallback decisions, and persisted validation receipts.

---

## Boundary Relationship Notes

ADR 0001 and ADR 0003 are closely related because both concern the transactional write-side path.

ADR 0002 is related to Compass runtime validation and should be read after the transactional baseline is understood.

ADR 0004 is related to the evolution from event-level validation to state-level validation.

ADR 0005 is related to the transition from the current in-memory baseline into durable persistence-backed execution.

ADR 0006 is related to money representation hardening before the write-side durable baseline grows larger.

ADR 0008 is related to the transition into Stage 3.5B. It records the event identity lifecycle rule used before durable persistence: pre-allocated `event_id` values may exist before append, but only event-log membership grants accepted-history status. This ADR should be read before modifying admission, event-store, validation-result, or future outcome schemas.

ADR 0009 is related to the first Stage 3.5B write-side code path after the schema baseline. It records why the project uses explicit `psycopg`-based PostgreSQL access for the write-side event store, why ORM-driven persistence is deferred for this boundary, and why event ID generation is centralized while UUIDv7 adoption is deferred.

ADR 0010 and ADR 0011 are Stage 3.5B PR4 boundary-separation decisions. ADR 0012 is a Stage 3.5B PR5 admission-interface evolution decision.

ADR 0010 records that transaction atomicity is not the same as concurrency admission. It explains why PR5 is needed after the PR4 transactional write-side boundary.

ADR 0011 records that validation mode is not the same as validation placement. It explains why future write-side flows may support both in-transaction validation and pre-transaction validation with OCC after PR5 admission exists.

ADR 0012 records why PR5 evolves from single-phase append-time admission into two-phase concurrency admission. It explains why `prepare_stream(order_id)` is needed for early pessimistic stream protection, why `append_if_admitted(candidate_event, expected_current_version)` remains necessary as the append-time accepted-history continuity check, and why separate optimistic / pessimistic write-side command flows were rejected.

Both ADR 0010 and ADR 0011 are related to the postmortem [From Durable Persistence to Semantic Gate Preservation](../postmortems/from_durable_persistence_to_semantic_gate_preservation.md), which records the PR4 implementation lesson that durable persistence hardening must preserve Compass semantic gates.

ADR 0007 is related to the future evolution from structured semantic outcomes into layered trust verdicts. It should be read after ADR 0004, ADR 0005, ADR 0006, ADR 0008, ADR 0009, ADR 0010, ADR 0011, and ADR 0012 because it assumes the reader already understands the Compass layering, persistent-storage direction, event identity boundary, concurrency boundary, validation placement boundary, and two-phase admission evolution.

ADR 0013 is related to Stage 3.5D PR4 / PR4.5. It records why projection snapshots are not trusted merely because they exist, why PR4.5 should remain a snapshot-assisted state resolver rather than a full trust-gate or fallback-policy engine, and why persisted validation receipts are deferred to a future hardening step.

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
0009_write_side_persistence_driver_and_identity_boundary.md
0010_transaction_atomicity_vs_concurrency_admission.md
0011_validation_mode_vs_validation_placement.md
0012_two_phase_concurrency_admission.md
0013_snapshot_runtime_eligibility_and_validation_receipt_boundary.md
```

Evolution or supporting notes may be kept as separate files:

```text
0002_evolution_note.md
```

This keeps formal decisions stable while preserving design history when needed.
