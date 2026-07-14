# Postmortems

[← Back to Docs Home](../README.md)

This directory contains postmortems for **Streaming System + Compass**.

Postmortems are used to preserve design mistakes, confusion points, debugging lessons, and architectural learning moments encountered during the project.

They are not ADRs.

A postmortem does not necessarily record a formal architecture decision. Instead, it explains what went wrong, why it was confusing, and what reusable lesson should be preserved.

---

## Postmortem Purpose

Postmortems help preserve:

- boundary misunderstandings
- scale mismatch in code reading
- mistaken ownership assumptions
- implementation confusion
- debugging lessons
- reusable design heuristics
- explicit differences between current project scope and enterprise-style documentation expectations
- key learning transitions between architecture stages
- transitions where a previously "natural" guarantee turns out to require explicit design
- reasoning bridges between current implementation and later roadmap stages
- distinctions between runtime behavior, durable evidence, and future governance signals
- cases where infrastructure hardening risks bypassing semantic governance
- cases where logical orchestration boundaries require explicit physical connection-state cleanup
- cases where database uniqueness scope must match the semantic scope of the source boundary
- cases where logical cursors must be distinguished from committed-history boundaries
- cases where protocol-level correctness must be distinguished from production wiring proof
- cases where generic validation intuition must be corrected by authority-based semantic reasoning
- cases where weak row-count assertions must be replaced by exact evidence assertions

---

## Current Postmortems

| Document | Impact Area | Purpose |
|---|---|---|
| [function_boundary_scale_mismatch](function_boundary_scale_mismatch.md) | Code Reading / Boundary Understanding | Explains a recurring confusion caused by reading function parameters before identifying module roles, ownership boundaries, and architectural scale. |
| [from_projection_concerns_to_event_truth](from_projection_concerns_to_event_truth.md) | Event Truth / Source of Truth | Records the design shift from focusing mainly on projection/runtime problems to treating event-source correctness and accepted-history entry as a more foundational concern. |
| [docs_vs_enterprise_design_docs](docs_vs_enterprise_design_docs.md) | Documentation Scope / Project Positioning | Clarifies why the current repository documents emphasize semantic completeness and boundary clarity first, rather than pretending to already be a full enterprise operational design doc. |
| [from_in_memory_correctness_to_durable_consistency](from_in_memory_correctness_to_durable_consistency.md) | Durable Persistence / Consistency | Explains why durable persistence is not just a backend replacement: once state must survive across time and restart, guarantees that felt natural in the in-memory world are no longer free. |
| [from_git_sync_to_db_immutability](from_git_sync_to_db_immutability.md) | Database Boundary / Immutability | Records how a Git local/remote synchronization confusion exposed a deeper distributed-systems lesson: Python-side guarantees such as `frozen=True` and append-only history must be explicitly re-declared at the database boundary. |
| [from_local_postgres_to_defense_in_depth](from_local_postgres_to_defense_in_depth.md) | Security / Defense in Depth | Explains why local PostgreSQL setup, `.env`, least privilege, SQL migrations, Compass validation, and transactions protect different system boundaries instead of one mechanism protecting everything. |
| [from_runtime_behavior_to_durable_evidence](from_runtime_behavior_to_durable_evidence.md) | Runtime Evidence / Observability | Explains why Python runtime behavior is not durable evidence unless selected facts are persisted into PostgreSQL, metadata fields, logs, metrics, traces, or audit records. |
| [from_exception_strings_to_governable_outcomes](from_exception_strings_to_governable_outcomes.md) | Error Model / Governance | Explains why raw exception strings are not enough for semantic governance, and why structured semantic outcomes must later feed runtime decision policy, action safety, and layered trust. |
| [from_durable_persistence_to_semantic_gate_preservation](from_durable_persistence_to_semantic_gate_preservation.md) | Semantic Gate / Validation Preservation | Records the PR4 lesson that durable persistence hardening can preserve physical transaction correctness while accidentally bypassing Compass semantic gates. |
| [autocommit_boundary_and_partial_write_risk](autocommit_boundary_and_partial_write_risk.md) | Transaction Boundary / Concurrency | Explains why `autocommit`, transaction-scoped advisory locks, and partial-write risks must be treated as physical transaction-boundary concerns in the durable write-side pipeline. |
| [pre_transaction_read_cleanup_boundary](pre_transaction_read_cleanup_boundary.md) | Connection Reliability / Infrastructure | Explains why `PRE_TRANSACTION` validation must explicitly clean up implicit read transactions before CPU-side validation, and why cleanup failure handling is deferred to Stage 4 / production hardening. |
| [from_snapshot_as_fast_state_to_snapshot_trust_contract](from_snapshot_as_fast_state_to_snapshot_trust_contract.md) | Snapshot Trust / Derived State | Records the reasoning shift from treating snapshots as replay optimization to treating them as derived-state artifacts that need a trust contract before being used on the fast path. |
| [from_replay_rebuild_validation_to_layer2_governance](from_replay_rebuild_validation_to_layer2_governance.md) | Replay / Layer 2 Boundary | Clarifies why Stage 3.5C PR5 replay / rebuild validation is the durable correctness substrate for derived state, while Compass Layer 2 remains the later semantic governance and runtime decision layer. |
| [from_per_order_global_position_to_global_source_boundary](from_per_order_global_position_to_global_source_boundary.md) | Snapshot Schema / Source Boundary | Records the PR2 correction from per-order global-position uniqueness to true global accepted-history boundary uniqueness. |
| [from_created_at_freshness_to_committed_history_boundaries](from_created_at_freshness_to_committed_history_boundaries.md) | Snapshot Freshness / Event-Log Cursor Semantics | Explains why projection snapshots should be ordered by accepted-history lineage instead of row creation time, and why `global_position` must be defined against commit, visibility, rollback, and recovery boundaries. |
| [from_protocol_satisfaction_to_production_wiring_proof](from_protocol_satisfaction_to_production_wiring_proof.md) | Production Wiring / AI-Assisted Implementation | Explains why protocol-satisfying unit tests do not prove that a production adapter exists or that the real PostgreSQL assembly path works. |
| [from_generic_validation_to_authority_based_reasoning](from_generic_validation_to_authority_based_reasoning.md) | Snapshot Trust / Authority-Based Validation | Records the PR4 correction from generic input-validation ordering to authority-first reasoning: accepted history must exist before snapshot trust can be evaluated. |
| [stage_3_5d_local_correctness_global_premise_drift](stage_3_5d_local_correctness_global_premise_drift.md) | Stage Scope / AI-Assisted Engineering | Records the Stage 3.5D correction where locally coherent snapshot PRs remained technically valid, but the stage-level premise had to be re-audited after distinguishing write-side aggregate admission risk from read-side derived-state evidence. |
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

The postmortem [Autocommit, Transaction Boundaries, and Partial-Write Risk](autocommit_boundary_and_partial_write_risk.md) is related to the Stage 3.5B / PR5 transition:

- PR4 establishes transaction atomicity for accepted event append + idempotency record persistence.
- PR5 introduces PostgreSQL-backed admission and transaction-scoped lock semantics.
- The postmortem explains why `autocommit=False` is a physical requirement for transaction-scoped pessimistic admission.
- This directly supports [ADR 0012 — Two-Phase Concurrency Admission for PostgreSQL Write-Side](../adr/0012_two_phase_concurrency_admission.md), especially the physical transaction-boundary requirement behind `prepare_stream(order_id)`.

---

The postmortem [From Snapshot as Fast State to Snapshot Trust Contract](from_snapshot_as_fast_state_to_snapshot_trust_contract.md) is related to the Stage 3.5D / Stage 4 transition:

- Stage 3.5D may introduce snapshots as replay-efficiency artifacts after the durable read-side baseline exists.
- Snapshot support creates a trust-boundary problem because derived state may be fast but not automatically trustworthy.
- The postmortem explains why snapshots need lineage, tail continuity, schema / reducer version checks, payload integrity checks, and fallback-to-replay behavior.
- This directly supports future Stage 4 Layer 2 and `SemanticOutcome` work for snapshot / projection trust failures.

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


The postmortem [From `created_at` Freshness to Committed-History Boundaries](from_created_at_freshness_to_committed_history_boundaries.md) is related to Stage 3.5D snapshot trust and later distributed ordering work:

- Stage 3.5D snapshots should not treat row creation time as freshness.
- `source_global_position` is useful only when its meaning is tied to an accepted-history boundary.
- The postmortem records the distinction between allocation-order cursors and committed-history cursors.
- It also separates temporary visibility gaps, permanent allocation gaps, and visible poison events, so later worker / validator design can avoid mixing gap recovery with DLQ handling.
- This supports future snapshot trust validation, projection worker hardening, and distributed event-log design by making cursor semantics explicit instead of assuming that a monotonic number automatically equals committed history.

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


---

The postmortem [Airflow Failure and Boundary Thinking](airflow_failure_and_boundary_thinking.md) records an earlier learning transition before Streaming System + Compass existed:

- a local ETL / Airflow debugging failure exposed the cost of operating a system without a boundary model;
- copy-paste debugging with AI could produce candidate fixes, but it did not by itself explain which system layer owned the failure;
- the corrected habit became `boundary first, implementation second`;
- this supports the later project discipline around Core vs Enablers, semantic admission, accepted history, and runtime governance.

This postmortem is also related to the philosophy note [From Local ETL to Streaming System + Compass](../philosophy/from_local_etl_to_streaming_system_compass.md), which records how the same early friction evolved into the project’s broader semantic-correctness direction.

---

## How to Use These Notes

Use postmortems when you want to understand:

- why a previous implementation or interpretation was confusing
- how a boundary should be read in the future
- what design habit should be avoided
- what reusable reading or debugging method emerged from the mistake
- why the current repository intentionally documents some things in greater semantic depth while still deferring full enterprise-operational realism
- how one architectural stage exposed the need for the next stage
- why a future roadmap direction exists before its implementation begins

---

## Postmortem Principle

A good postmortem should not only say what happened.

It should identify the reusable lesson:

```text
confusion
→ root cause
→ corrected model
→ future rule
```

For roadmap bridge documents, the useful pattern is:

```text
current limitation
→ missing semantic boundary
→ corrected model
→ future implementation stage
```
