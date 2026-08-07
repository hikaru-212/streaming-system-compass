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
| 0002 | [Intent-Aware Validation Dispatch for Compass Runtime](0002_intent_aware_validation_dispatch.md) | Accepted | Defines the future Compass validation dispatch model. |
| 0003 | [Concurrency Control, Idempotency, and Retry Safety](0003_concurrency_idempotency_and_retry_safety.md) | Accepted | Defines write-side safety under concurrency, retries, and ambiguous commits. |
| 0004 | [Why Compass Split into Two Layers](0004_why_compass_split_into_two_layers.md) | Accepted | Records why the project evolved from a single runtime-verification idea into layered Compass validation. |
| 0005 | [Persistent Storage Baseline Strategy](0005_persistent_storage_baseline_strategy.md) | Accepted | Defines why the next stage after the in-memory Stage 3 baseline should be a PostgreSQL-backed persistent storage baseline. |
| 0006 | [Use Decimal for Money Values Before Durable Persistence](0006_use_decimal_for_money_values_before_durable_persistence.md) | Accepted | Defines why money-like values should move from `float` to `Decimal` before the durable write-side baseline grows larger. |
| 0007 | [Separate Semantic Correctness from Operational Trust](0007_separate_semantic_correctness_from_operational_trust.md) | Proposed | Defines why future trust evaluation should separate semantic correctness, projection correctness, operational trust, and action safety. |
| 0008 | [Pre-Allocated Event Identity and Candidate/Accepted Event Naming Boundary](0008_pre_allocated_event_identity_and_candidate_accepted_boundary.md) | Accepted | Defines the lifecycle naming boundary for pre-allocated event IDs before durable write-side persistence. |
| 0009 | [Write-Side Persistence Driver and Identity Generation Boundary](0009_write_side_persistence_driver_and_identity_boundary.md) | Accepted | Defines why the Stage 3.5B write-side persistence baseline uses explicit PostgreSQL driver access and centralized event ID generation instead of ORM-driven persistence or immediate UUIDv7 migration. |
| 0010 | [Separate Transaction Atomicity from Concurrency Admission](0010_transaction_atomicity_vs_concurrency_admission.md) | Accepted | Separates PR4 transaction atomicity from PR5 PostgreSQL concurrency admission. |
| 0011 | [Separate Validation Mode from Validation Placement Strategy](0011_validation_mode_vs_validation_placement.md) | Accepted | Separates validation strength from validation placement and records the two supported baseline compositions: `PRE_TRANSACTION + OPTIMISTIC` and `IN_TRANSACTION + PESSIMISTIC`. |
| 0012 | [Two-Phase Concurrency Admission for PostgreSQL Write-Side](0012_two_phase_concurrency_admission.md) | Accepted | Evolves PR5 admission from append-time-only admission into two-phase stream preparation plus append-time admission. |
| 0013 | [Snapshot Runtime Eligibility and Validation Receipt Boundary](0013_snapshot_runtime_eligibility_and_validation_receipt_boundary.md) | Accepted | Separates PR4.5 snapshot-assisted state resolution from future runtime eligibility policy and persisted validation receipts. |
| 0014 | [Defer Separate Projection Event Model](0014_defer_projection_events_as_delivery_layer.md) | Accepted | Records why the project defers a separate projection-event / projection-delivery-log model until delivery, fanout, retry, DLQ, or operational-freshness needs become concrete. |
| 0015 | [Permission Probing with SET ROLE](0015_permission_probing_with_set_role.md) | Accepted | Records why Stage 3.5E uses test-time `SET ROLE` permission probes instead of introducing production-style login identities and role-specific connection pools. |
| 0016 | [DecisionReceipt Is Governance Evidence, Not Application Logging](0016_decision_receipt_is_governance_evidence.md) | Accepted | Records why Stage 4B introduces DecisionReceipt as durable semantic governance evidence rather than application logging or a generic error table. |
| 0017 | [Separate Evidence Path, Identity Provenance, and Event Admission Fate in DecisionReceipt](0017_separate_evidence_path_identity_provenance_and_admission_fate.md) | Accepted | Separates receipt evidence path, primary identity provenance, and typed write-side admission fate, including early idempotent replay and candidate / accepted-event invariants. |
| 0018 | [Producer Receipt Adapters Preserve Evidence but Do Not Evaluate Governance Flags](0018_producer_receipt_adapters_preserve_evidence_but_do_not_evaluate_governance_flags.md) | Accepted | Separates producer evidence preservation from governance-flag evaluation and keeps `TRUE`, `FALSE`, and `NOT_EVALUATED` distinct. |
| 0019 | [Separate Accepted-Result Receipt Reconstruction from Immediate Typed-Observation Evidence Persistence](0019_separate_accepted_receipt_reconstruction_from_failed_attempt_persistence.md) | Accepted | Separates reconstructible accepted-result receipts from non-reconstructible failed-attempt and observation evidence, records implemented foundational persistence, and defers reconciliation orchestration. |
| 0020 | [Per-Order Projection Progress and Order-Local Snapshot Tails](0020_per_order_projection_progress_and_order_local_snapshot_tails.md) | Accepted | Uses per-order progress and order-local snapshot tails because global-position gaps do not prove missing order history. |
| 0021 | [Projection Snapshots Are Optional for the Current Order Workload](0021_projection_snapshots_are_optional_for_current_order_workload.md) | Accepted | Retains the Snapshot Trust Contract while classifying projection snapshots as optional reference infrastructure for the current shallow Order workload. |

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
15. [Defer Separate Projection Event Model](0014_defer_projection_events_as_delivery_layer.md) — explains why a separate projection-event / projection-delivery-log model is deferred until delivery and fanout complexity becomes concrete.
16. [Permission Probing with SET ROLE](0015_permission_probing_with_set_role.md) — explains why Stage 3.5E validates effective database privileges through test-time `SET ROLE` probes instead of simulating production login identity topology.
17. [DecisionReceipt Is Governance Evidence, Not Application Logging](0016_decision_receipt_is_governance_evidence.md) — explains why Stage 4B persists selected semantic outcomes as durable governance evidence instead of treating them as ordinary application logs, error logs, diagnostic traces, or retry attempt records.
18. [Separate Evidence Path, Identity Provenance, and Event Admission Fate in DecisionReceipt](0017_separate_evidence_path_identity_provenance_and_admission_fate.md) — refines the Stage 4B receipt contract by separating evidence-path ownership, primary correlation provenance, and typed event-admission fate, including early idempotent replay and cross-field identity invariants.
19. [Producer Receipt Adapters Preserve Evidence but Do Not Evaluate Governance Flags](0018_producer_receipt_adapters_preserve_evidence_but_do_not_evaluate_governance_flags.md) — explains why producer adapters preserve typed evidence while `TRUE`, `FALSE`, and `NOT_EVALUATED` remain distinct and absence of evaluation is not false.
20. [Separate Accepted-Result Receipt Reconstruction from Immediate Typed-Observation Evidence Persistence](0019_separate_accepted_receipt_reconstruction_from_failed_attempt_persistence.md) — explains why accepted-result reconstruction and non-reconstructible failed-attempt or observation persistence require separate paths, with foundational persistence implemented and reconciliation orchestration deferred.
21. [Per-Order Projection Progress and Order-Local Snapshot Tails](0020_per_order_projection_progress_and_order_local_snapshot_tails.md) — explains why aggregate-local progress and snapshot tails use order-local sequence instead of treating global-position gaps as missing order history.
22. [Projection Snapshots Are Optional for the Current Order Workload](0021_projection_snapshots_are_optional_for_current_order_workload.md) — explains why the Snapshot Trust Contract remains valid while further snapshot-specific runtime expansion is evidence-gated for the current shallow Order workload.

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

ADR 0014 is related to Stage 3.5C / Stage 3.5D read-side boundaries. It records why accepted history remains the authoritative projection input and why a separate projection-event or projection-delivery-log model is deferred until delivery, fanout, retry, DLQ, or operational-freshness requirements become concrete.

ADR 0015 is related to Stage 3.5E database role and permission hardening. It records why the project validates runtime responsibility-role privileges through test-owner `SET ROLE` probes, while deferring production login identities, role-specific database URLs, and connection-pool topology to future deployment hardening.

ADR 0016 is related to Stage 4B DecisionReceipt / runtime evidence design. It records why selected `SemanticOutcome` values should become compact, durable, reviewable governance evidence, while ordinary logs, detailed diagnostic traces, retry attempt logs, runtime policy decisions, and execution strategies remain separate boundaries.

ADR 0017 refines the Stage 4B DecisionReceipt runtime contract established after ADR 0016. It records why evidence path, primary identity provenance, and event admission fate must remain separate; why nullable candidate / accepted event identifiers cannot safely encode admission meaning by themselves; why early idempotent replay may reference an accepted event without a newly constructed candidate; and why field-level identity provenance remains deferred until future adapters, persistence, audit, or policy consumers require it.

ADR 0018 keeps producer-specific receipt adapters responsible for typed evidence rather than governance-flag evaluation. It preserves `TRUE`, `FALSE`, and `NOT_EVALUATED` as distinct states so absence of evaluation is not interpreted as false.

ADR 0019 separates reconstructible accepted-result receipts from failed-attempt and typed-observation evidence that accepted history cannot reconstruct. Foundational persistence contracts are implemented, while materialization and reconciliation orchestration remain deferred.

ADR 0020 records why the order-state projection uses per-order progress and order-local snapshot tails. Global positions remain unique lineage and scheduling coordinates, but gaps do not prove missing order history or global committed-history completeness.

ADR 0021 retains ADR 0013's Snapshot Trust Contract while separating trust correctness from workload necessity. It classifies projection snapshots as optional derived reconstruction and trust-reference infrastructure for the current Order workload and requires concrete consumer or workload evidence before further snapshot-specific expansion.

The ADR 0002 evolution note is not a standalone decision. It is a supporting trace for understanding how ADR 0002 was refined.

---

## ADR Status Meaning

### Proposed

The decision is a design candidate or future direction, but it has not yet been adopted as the current architecture decision.

### Accepted

The decision has been adopted as the current project direction.

Accepted does not always mean fully implemented. Implementation progress should be recorded separately in each ADR under `Implementation Status`.

### Superseded

The decision has been replaced by a newer ADR.

### Implementation Status

Each formal ADR should place `Implementation Status` immediately after `Status`.

Recommended values include:

```text
Not implemented yet.
Accepted as a deferral decision.
Implemented at baseline level.
Partially implemented at baseline level.
Superseded by ADR XXXX.
```

This keeps decision status separate from implementation progress.

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
0014_defer_projection_events_as_delivery_layer.md
0015_permission_probing_with_set_role.md
0016_decision_receipt_is_governance_evidence.md
0017_separate_evidence_path_identity_provenance_and_admission_fate.md
0018_producer_receipt_adapters_preserve_evidence_but_do_not_evaluate_governance_flags.md
0019_separate_accepted_receipt_reconstruction_from_failed_attempt_persistence.md
0020_per_order_projection_progress_and_order_local_snapshot_tails.md
0021_projection_snapshots_are_optional_for_current_order_workload.md
```

Evolution or supporting notes may be kept as separate files:

```text
0002_evolution_note.md
```

This keeps formal decisions stable while preserving design history when needed.
