# Postmortems

[← Back to Docs Home](../README.md)

This directory contains postmortems for **Streaming System + Compass**.

A postmortem records a concrete engineering episode and preserves its diagnosis,
repair, and reusable lesson. It does not require a production outage.

Postmortems include actual incidents and preventive engineering discoveries
where a real unsafe path, failed test, regression, broken migration,
source-grounded inconsistency, or missing guarantee was found and concretely
repaired before production impact. They also include concrete
architectural-model corrections, recurring engineering-learning failures, and
stage-premise drift when one identifiable episode actually occurred.

The limiting rule is that a postmortem must reconstruct one identifiable
episode through its context, problem, correction, and lesson. A general
personal realization or reusable derivation without one dominant concrete
episode belongs in [Reasoning Notes](../reasoning_notes/README.md).

Postmortems are historical engineering records. They are not ADRs and do not
replace current source, tests, migrations, accepted decisions, or boundary
notes.

---

## Postmortem Purpose

Postmortems preserve concrete episodes such as:

- actual incidents and operational failures;
- failed tests and regressions;
- broken migrations;
- source-grounded inconsistencies;
- unsafe paths discovered before merge;
- missing guarantees that were concretely repaired;
- architectural models that were concretely corrected;
- recurring engineering-learning failures tied to an identifiable episode;
- stage-premise drift that caused an actual direction correction;
- production-wiring gaps found through audit; and
- preventive engineering discoveries resolved before production impact.

When the reusable derivation or inference path is the dominant value rather
than a concrete episode, use [Reasoning Notes](../reasoning_notes/README.md).

---

## Current Postmortems

| Document | Impact Area | Purpose |
|---|---|---|
| [function_boundary_scale_mismatch](function_boundary_scale_mismatch.md) | Code Reading / Boundary Understanding | Records a recurring engineering-learning failure caused by reading function parameters before identifying module roles, ownership boundaries, and architectural scale. |
| [from_durable_persistence_to_semantic_gate_preservation](from_durable_persistence_to_semantic_gate_preservation.md) | Semantic Gate / Validation Preservation | Records the PR4 lesson that durable persistence hardening can preserve physical transaction correctness while accidentally bypassing Compass semantic gates. |
| [pre_transaction_read_cleanup_boundary](pre_transaction_read_cleanup_boundary.md) | Connection Reliability / Infrastructure | Explains why `PRE_TRANSACTION` validation must explicitly clean up implicit read transactions before CPU-side validation, and why cleanup failure handling is deferred to Stage 4 / production hardening. |
| [from_snapshot_as_fast_state_to_snapshot_trust_contract](from_snapshot_as_fast_state_to_snapshot_trust_contract.md) | Snapshot Trust / Derived State | Records the preventive architectural correction from treating snapshots mainly as replay optimization to separating production, consumption, policy, and trust responsibilities. |
| [from_per_order_global_position_to_global_source_boundary](from_per_order_global_position_to_global_source_boundary.md) | Snapshot Schema / Source Boundary | Records the PR2 correction from per-order global-position uniqueness to true global accepted-history boundary uniqueness. |
| [from_architectural_warning_to_executable_invariant](from_architectural_warning_to_executable_invariant.md) | Verification Workflow / Concurrency Invariants | Compares a schema defect that was immediately found and repaired with a correctly predicted commit-visibility risk that remained active until a deterministic multi-connection PostgreSQL test converted the warning into an executable invariant. |
| [from_protocol_satisfaction_to_production_wiring_proof](from_protocol_satisfaction_to_production_wiring_proof.md) | Production Wiring / AI-Assisted Implementation | Explains why protocol-satisfying unit tests do not prove that a production adapter exists or that the real PostgreSQL assembly path works. |
| [from_generic_validation_to_authority_based_reasoning](from_generic_validation_to_authority_based_reasoning.md) | Snapshot Trust / Authority-Based Validation | Records the PR4 correction from generic input-validation ordering to authority-first reasoning: accepted history must exist before snapshot trust can be evaluated. |
| [stage_3_5d_local_correctness_global_premise_drift](stage_3_5d_local_correctness_global_premise_drift.md) | Stage Scope / AI-Assisted Engineering | Records the preventive architectural correction where locally coherent snapshot work remained useful while the stage-level cost and risk premise required correction and deferral. |
| [from_row_count_assertions_to_evidence_assertions](from_row_count_assertions_to_evidence_assertions.md) | Testing / Assertion Fidelity | Records the Stage 3.5E PR4 near miss where exact evidence assertions exposed a PostgreSQL UUID return-type mismatch that row-count-only assertions would have hidden. |
| [airflow_failure_and_boundary_thinking](airflow_failure_and_boundary_thinking.md) | Debugging / Boundary Thinking | Records how an early Airflow debugging failure exposed the cost of operating a system without first identifying the boundary responsible for the failure. |
| [stage_4b_semantic_level_mismatch_in_ai_assisted_runtime_contract](stage_4b_semantic_level_mismatch_in_ai_assisted_runtime_contract.md) | Runtime Contract / AI-Assisted Engineering | Records the Stage 4B PR2 correction where a locally strong `DecisionReceipt` contract mixed evidence-source paths with operation/status vocabulary, and preserves the rule that AI-generated contracts require semantic-level admission review. |

---

## Relationship to ADRs

Some postmortems directly motivate later ADRs.

The PR4 postmortem [From Durable Persistence to Semantic Gate Preservation](from_durable_persistence_to_semantic_gate_preservation.md) is directly related to:

- [ADR 0010 — Separate Transaction Atomicity from Concurrency Admission](../adr/0010_transaction_atomicity_vs_concurrency_admission.md)
- [ADR 0011 — Separate Validation Mode from Validation Placement Strategy](../adr/0011_validation_mode_vs_validation_placement.md)

The postmortem records the implementation lesson.

The ADRs record the follow-up architecture decisions.

---

The postmortem [Pre-Transaction Read Cleanup Boundary](pre_transaction_read_cleanup_boundary.md) is related to the Stage 3.5B / PR6 validation placement transition:

- PR6 introduces configurable validation placement between `IN_TRANSACTION` and `PRE_TRANSACTION`.
- `PRE_TRANSACTION` validation requires more than moving Compass validation outside the write-side UoW.
- Preliminary PostgreSQL reads may still open implicit transactions.
- The postmortem explains why a `try/finally` cleanup boundary is required to rollback the implicit read transaction before CPU-side Compass validation begins.
- This directly supports the [Validation Placement Strategy Boundary](../boundary_notes/validation_placement_strategy_boundary.md), especially the physical connection-state requirement behind `PRE_TRANSACTION` validation.

---

The postmortem [From Per-Order Global Position to Global Source Boundary](from_per_order_global_position_to_global_source_boundary.md) is related to the Stage 3.5D PR2 projection snapshot schema baseline:

- PR2 introduces `projection_snapshots` and accepted-history lineage fields.
- `source_event_sequence` is order-local, while `source_global_position` is global.
- The postmortem records why `UNIQUE(order_id, source_global_position)` was the wrong physical boundary.
- The corrected schema uses `UNIQUE(source_global_position)` and `UNIQUE(source_event_id)` while preserving `UNIQUE(order_id, source_event_sequence)`.
- This supports later snapshot store and trust-validator work by keeping source-boundary evidence aligned with accepted-history semantics.

---

The postmortem [From Architectural Warning to Executable Invariant](from_architectural_warning_to_executable_invariant.md) relates the Stage 3.5D source-boundary discovery to the later Stage 3.5C cursor repair:

- [From Per-Order Global Position to Global Source Boundary](from_per_order_global_position_to_global_source_boundary.md) records a concrete schema contradiction that was found and repaired immediately.
- The reasoning note [From `created_at` Freshness to Committed-History Boundaries](../reasoning_notes/from_created_at_freshness_to_committed_history_boundaries.md) predicted allocation/commit visibility risk but did not yet prove that the current worker suffered the failure.
- The later multi-connection PostgreSQL characterization test demonstrated that the warning was already an active correctness defect.
- [ADR 0020 — Per-Order Projection Progress and Order-Local Snapshot Tails](../adr/0020_per_order_projection_progress_and_order_local_snapshot_tails.md) records the repaired production contract.
- The postmortem preserves the workflow lesson that architectural warnings must become tracked proof obligations, executable invariants, or explicit accepted risks.

---

The postmortem [From Protocol Satisfaction to Production Wiring Proof](from_protocol_satisfaction_to_production_wiring_proof.md) is related to Stage 3.5D PR4 projection snapshot replay validation:

- PR4 introduces protocol-shaped dependencies so the validator can be tested independently from PostgreSQL.
- Fake-based unit tests prove validator logic, but they do not prove that every protocol has a production adapter.
- The postmortem records why `PostgresAcceptedHistoryEventSource` and PostgreSQL-backed validator integration tests are required before PR4 can be considered production-wired.
- This supports future PR4.5 resolver work by preserving the rule that protocol satisfaction, adapter existence, and production wiring proof are separate claims.

---

The postmortem [From Generic Validation to Authority-Based Reasoning](from_generic_validation_to_authority_based_reasoning.md) is related to Stage 3.5D PR4 and the Snapshot Trust Contract:

- PR4 is not a generic snapshot input validator. It is an authority-based replay validator.
- The postmortem records why `NO_ACCEPTED_HISTORY_FOR_ORDER` should be returned when accepted history is missing, even if a snapshot row exists.
- Snapshot boundary invalidity can be evaluated only after the accepted-history authority foundation exists.
- This reinforces the Stage 3.5D invariant that snapshots are derived, discardable, and subordinate to accepted history.

---

The postmortem [From Row-Count Assertions to Evidence Assertions](from_row_count_assertions_to_evidence_assertions.md) is related to Stage 3.5E PR4 derived-state permission tests:

- PR4 uses PostgreSQL role probes to verify derived-state table permissions.
- The projection snapshot tests exposed that PostgreSQL `UUID` columns are returned by `psycopg` as Python `UUID` objects, not strings.
- The postmortem records why `len(rows) == 1` is too weak when a returned row is part of the evidence.
- This supports the Stage 3.5E testing rule that permission probes with `RETURNING` or `SELECT` evidence should assert exact returned rows, not only row count.

---

The postmortem [Airflow Failure and Boundary Thinking](airflow_failure_and_boundary_thinking.md) records an earlier learning transition before Streaming System + Compass existed:

- a local ETL / Airflow debugging failure exposed the cost of operating a system without a boundary model;
- copy-paste debugging with AI could produce candidate fixes, but it did not by itself explain which system layer owned the failure;
- the corrected habit became `boundary first, implementation second`;
- this supports the later project discipline around Core vs Enablers, semantic admission, accepted history, and runtime governance.

This postmortem is also related to the philosophy note [From Local ETL to Streaming System + Compass](../philosophy/07_from_local_etl_to_streaming_system_compass.md), which records how the same early friction evolved into the project’s broader semantic-correctness direction.

---

## How to Use These Notes

Use postmortems when you want to understand:

- what concrete engineering episode occurred;
- what evidence exposed the problem;
- what unsafe path, inconsistency, regression, failed test, or missing guarantee
  was repaired;
- what repository effect resulted; and
- what reusable engineering lesson should be retained.

---

## Postmortem Principle

A good postmortem identifies both the concrete episode and the reusable lesson:

```text
trigger or observed evidence
→ root cause
→ concrete repair or accepted resolution
→ verification
→ reusable engineering lesson
```
