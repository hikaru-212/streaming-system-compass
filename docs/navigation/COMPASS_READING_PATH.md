# Compass Reading Path

## 1. What Compass Is

Agent-generated actions are candidates, not accepted facts. Tool permission, valid JSON, database access, successful execution, and multi-agent agreement may establish technical capability or coordination; they do not establish business authority.

Compass places semantic validation and concurrency admission between a proposal and durable mutation. A candidate becomes an accepted fact only through admission into accepted history under the relevant domain, semantic, and concurrency boundaries. Identifier existence alone does not grant that status.

The surrounding artifacts have narrower responsibilities. Accepted history preserves admitted facts. Projection state is derived read state. Per-order projection progress records current completeness; `global_position` remains lineage and scheduling evidence. A snapshot is derived fast-path evidence. An idempotency record preserves a request-to-accepted-result relation. `SemanticOutcome` interprets bounded technical evidence. `DecisionReceipt` preserves selected governance evidence through explicit mapping, serialization, and caller-owned persistence boundaries. Producer-specific `DiagnosticTrace` / `ResolutionTrace` contracts preserve bounded one-execution topology without becoming primary results, receipts, retry authority, or measurement evidence.

These artifacts must not impersonate one another. In particular, semantic meaning is not yet policy, retry permission, strategy, or executable action.

## 2. Choose One Orientation Document

| Document | Why start here | What remains uncovered |
|---|---|---|
| [Project README](../../README.md) | Gives the repository purpose, current implementation baseline, and documentation entry points. | Detailed responsibility boundaries and implementation chronology. |
| [Compass Agent-Era Overview](../overview/compass_agent_era_overview.md) | Offers a public, non-authoritative orientation to the broader agent-era architecture. | Exact runtime behavior, which remains owned by source, accepted decisions, boundaries, and closeouts. |
| [Semantic Admission manifesto](../semantic_admission/manifesto.md) | Gives the clearest agent-era explanation of candidate action, admission before mutation, and accepted truth without requiring event-sourcing knowledge. | Concrete identity, concurrency, derived-state, and Stage 4 contracts. |

## 3. Read Three Documents

This is the shortest complete conceptual arc: **problem → executable authority path → semantic interpretation**.

| Order | Document | What it contributes |
|---:|---|---|
| 1 | [Semantic Admission manifesto](../semantic_admission/manifesto.md) | Explains why successful agent execution does not establish that an action should become reality. |
| 2 | [Transactional Core](../architecture/transactional_core.md) | Shows the executable path from command to candidate, validation, concurrency admission, accepted history, and replay. |
| 3 | [Runtime SemanticOutcome Boundary](../boundary_notes/runtime_semantic_outcome_boundary.md) | Separates technical evidence, semantic meaning, later runtime decision, strategy, and retry governance. |

## 4. Read Five Documents

| Order | Document | Core question answered | What it defers |
|---:|---|---|---|
| 1 | [Semantic Admission manifesto](../semantic_admission/manifesto.md) | Why must an agent action remain a candidate before mutation? Candidate action is broader than the current candidate-event implementation. | Runtime mechanics and evidence contracts. |
| 2 | [Transactional Core](../architecture/transactional_core.md) | How does the current candidate-event implementation separate domain decision, semantic validation, concurrency admission, and accepted append? | Durable implementation detail and later governance. |
| 3 | [ADR 0008 — Candidate/Accepted Identity](../adr/0008_pre_allocated_event_identity_and_candidate_accepted_boundary.md) | Why does identifier existence not establish accepted authority? | Cross-attempt candidate identity policy. |
| 4 | [Snapshot Trust Contract](../architecture/snapshot_trust_contract.md) | Why are projection and snapshot state derived evidence rather than accepted authority? | Store, hashing, and resolver details. |
| 5 | [Runtime SemanticOutcome Boundary](../boundary_notes/runtime_semantic_outcome_boundary.md) | How does bounded evidence acquire semantic meaning without becoming action? | Policy, strategy, retry, receipt materialization, and execution. |

## 5. Deep Architecture Path

| Order | Document | Role | Why read it |
|---:|---|---|---|
| 1 | [Semantic Admission manifesto](../semantic_admission/manifesto.md) | Public conceptual framing | Establish the agent-era problem before implementation vocabulary. |
| 2 | [Transactional Core](../architecture/transactional_core.md) | Architecture | Learn the minimal semantic Write-side loop and accepted-history foundation. |
| 3 | [ADR 0008](../adr/0008_pre_allocated_event_identity_and_candidate_accepted_boundary.md) | Accepted ADR | Separate candidate identity, accepted identity, and accepted-history membership. |
| 4 | [ADR 0010](../adr/0010_transaction_atomicity_vs_concurrency_admission.md) | Accepted ADR | Separate all-or-nothing persistence from competing-writer admission. |
| 5 | [ADR 0011](../adr/0011_validation_mode_vs_validation_placement.md) | Accepted, baseline-implemented ADR | Learn the supported validation-placement and admission-strategy combinations. |
| 6 | [Projection Module Boundary](../boundary_notes/projection_module.md) | Boundary note | Establish projection as deterministic derivation, not truth ownership. |
| 7 | [Snapshot Trust Contract](../architecture/snapshot_trust_contract.md) | Architecture | Extend the authority model through snapshot qualification and replay fallback. |
| 8 | [Runtime SemanticOutcome Boundary](../boundary_notes/runtime_semantic_outcome_boundary.md) | Boundary note | Establish technical evidence → semantic meaning and protect later-layer separation. |
| 9 | [SemanticOutcome Result Contract](../implementation_notes/stage_4a/semantic_outcome_result_contract.md) | Completed Stage 4A implementation boundary | See the typed internal meaning/evidence contract without executable authorization. |
| 10 | [ADR 0016 — DecisionReceipt](../adr/0016_decision_receipt_is_governance_evidence.md) | Accepted responsibility boundary | Establish DecisionReceipt as governance evidence rather than policy, trace, or action. |
| 11 | [DecisionReceipt Boundary](../boundary_notes/decision_receipt_boundary.md) | Canonical cross-stage boundary | Learn the current receipt contract, authority, responsibilities, and non-goals. |
| 12 | [SemanticOutcome to DecisionReceipt](../implementation_notes/stage_4b/semantic_outcome_to_decision_receipt.md) | Completed Stage 4B mapping record | Follow explicit generic construction without producer execution or persistence. |
| 13 | [DecisionReceipt Durable Persistence](../implementation_notes/stage_4b/decision_receipt_persistence.md) | Completed Stage 4B persistence record | Separate strict serialization and storage-neutral envelopes from caller-owned PostgreSQL transaction completion. |
| 14 | [Stage 4B Closeout](../implementation_notes/stage_4b/stage_4b_closeout.md) | Stage closeout | Confirm the complete mapping, tri-state flag, serializer-v1, persistence, and explicit non-goal baseline. |
| 15 | [ADR 0022 — Traced Write-Side Execution Fails Closed](../adr/0022_traced_write_side_execution_fails_closed_before_business_commit.md) | Accepted producer-specific decision | Understand why the current PostgreSQL traced APIs synchronously construct valid Result + Trace before clean business-UOW exit. |
| 16 | [Stage 4B.1 Closeout](../implementation_notes/stage_4b_1/stage_4b_1_closeout.md) | Stage closeout | Confirm completed producer-specific traces, intentional non-integrations, and the Stage 4B.2 handoff. |
| 17 | [Stage 4B.2 Closeout](../implementation_notes/stage_4b_2/stage_4b_2_closeout.md) | Stage closeout | Confirm producer-specific measurement, valid Level-B and Level-C evidence, bounded explanation, limitations, and the no-policy handoff. |
| 18 | [Why Stage 4B.5 Exists](../implementation_notes/stage_4b_5/why_stage_4b_5_exists.md) | Completed stage rationale | Follow coarse semantic rejection into stable exact rule evidence, same-invocation propagation, terminal refinement, and the separate future Retry Governance boundary. |

Stage 4B, Stage 4B.1, Stage 4B.2, and Stage 4B.5 are complete, but mapping does not
automatically materialize or persist a receipt, and measurement evidence does
not create production policy. Stage 4B.5 exact rule evidence does not authorize
retry. Stage 4B.3 remains separately owned and not started; policy, strategy,
retry, action authorization, and execution remain later work.

## 6. Choose by Professional Background

### AI governance / agent safety

| Order | Document | Why read it |
|---:|---|---|
| 1 | [Semantic Admission manifesto](../semantic_admission/manifesto.md) | Learn why execution permission is not admission authority. |
| 2 | [Shared Workflow Is Not Shared Authority](../semantic_admission/shared_workflow_is_not_shared_authority.md) | See how authority can be laundered through cooperating agents. |
| 3 | [Action Path Admission](../semantic_admission/action_path_admission.md) | Learn why a correct-looking final state does not prove an admissible path. |
| 4 | [Model Autonomy Is Not Business Authority](../semantic_admission/model_autonomy_vs_business_authority.public.md) | Connect model autonomy, institutional responsibility, and progressive authority. |
| 5 | [Runtime SemanticOutcome Boundary](../boundary_notes/runtime_semantic_outcome_boundary.md) | Separate semantic interpretation from executable governance. |

### Backend / transactional systems

| Order | Document | Why read it |
|---:|---|---|
| 1 | [Transactional Core](../architecture/transactional_core.md) | Start with the complete conceptual Write-side loop. |
| 2 | [Idempotency Module Boundary](../boundary_notes/idempotency_module.md) | Separate `MISS`, `REPLAY`, and `CONFLICT` from command legality. |
| 3 | [ADR 0008](../adr/0008_pre_allocated_event_identity_and_candidate_accepted_boundary.md) | Distinguish physical event identity from accepted membership. |
| 4 | [ADR 0010](../adr/0010_transaction_atomicity_vs_concurrency_admission.md) | Separate atomicity from admission. |
| 5 | [ADR 0011](../adr/0011_validation_mode_vs_validation_placement.md) | Learn the current validation/admission composition contract. |
| 6 | [Write-side Schema Baseline](../architecture/write_side_schema_baseline.md) | Follow accepted history, versions, idempotency evidence, and exact values into durable storage. |

### Data platform

| Order | Document | Why read it |
|---:|---|---|
| 1 | [Projection Module Boundary](../boundary_notes/projection_module.md) | Establish projection as derived state. |
| 2 | [Read-side Persistence Boundary](../boundary_notes/read_side_persistence_boundary.md) | Separate accepted events, projection state, checkpoints, and cursor coordinates. |
| 3 | [ADR 0020 — Per-Order Projection Progress](../adr/0020_per_order_projection_progress_and_order_local_snapshot_tails.md) | Learn why exact-next per-order progress owns current completeness while `global_position` remains lineage and scheduling evidence. |
| 4 | [Durable Replay/Rebuild Validation Boundary](../boundary_notes/durable_replay_rebuild_validation_boundary.md) | Compare derived state with accepted-history replay. |
| 5 | [Snapshot Trust Contract](../architecture/snapshot_trust_contract.md) | Learn why snapshot existence is not trust. |
| 6 | [Snapshot Trust Boundary](../boundary_notes/snapshot_trust_contract_boundary.md) | Review bounded qualification checks and deferred hardening. |

### Runtime reliability / semantic control

| Order | Document | Why read it |
|---:|---|---|
| 1 | [Runtime SemanticOutcome Boundary](../boundary_notes/runtime_semantic_outcome_boundary.md) | Start with technical status versus meaning, decision, strategy, and retry. |
| 2 | [SemanticOutcome Result Contract](../implementation_notes/stage_4a/semantic_outcome_result_contract.md) | Learn the internal semantic fields and evidence boundaries. |
| 3 | [Runtime Technical-status Mapping](../implementation_notes/stage_4a/runtime_technical_status_mapping.md) | Follow normalized technical evidence into stable semantic fields. |
| 4 | [Stage 4A Closeout](../implementation_notes/stage_4a/stage_4a_closeout.md) | Confirm the completed scope and explicit deferrals. |
| 5 | [Drift Validation Cost Boundary](../implementation_notes/stage_4a/drift_validation_cost_boundary.md) | Keep descriptive cost evidence separate from policy and strategy. |
| 6 | [DecisionReceipt Boundary](../boundary_notes/decision_receipt_boundary.md) | Continue into the completed Stage 4B governance-evidence contract. |
| 7 | [Stage 4B Closeout](../implementation_notes/stage_4b/stage_4b_closeout.md) | Confirm generic and producer mapping, tri-state flags, strict serializer v1, explicit persistence, and the historical Stage 4B.1 transition. |
| 8 | [Stage 4B.1 Closeout](../implementation_notes/stage_4b_1/stage_4b_1_closeout.md) | Confirm the trace/result boundary, completed producer slices, and deferred consumer/provenance questions. |

## 7. Current Implementation Maturity

Completion below means the repository's bounded baseline, not production completeness.

| Area | Current maturity | Important limitation |
|---|---|---|
| Write-side durable baseline | Completed | Not complete distributed production hardening or later retry governance. |
| Read-side durable baseline | Completed | Exact-next per-order progress owns current completeness; multi-worker coordination and a global committed watermark remain deferred. |
| Snapshot Trust bounded baseline | Completed | Projection snapshots only; aggregate snapshots and broader reusable eligibility remain deferred. |
| Durable permission baseline | Completed | Not complete IAM, business authorization, or emergency repair governance. |
| Stage 4A `SemanticOutcome` | Completed | Interprets evidence; does not execute policy, strategy, retry, or action. |
| Stage 4B `DecisionReceipt` | Completed | Generic and producer mapping, tri-state flags, strict serializer v1, storage-neutral contracts, and explicit caller-owned PostgreSQL persistence exist; automatic materialization does not. |
| Stage 4B.1 `DiagnosticTrace` / `ResolutionTrace` | Completed | Producer-specific contracts exist and PostgreSQL write-side tracing is integrated; snapshot runtime integration, projection-worker tracing, persistence, and a generic abstraction remain deferred. |
| Stage 4B.2 measurement / cost evidence | Completed | Producer-specific measurement and bounded Level-B/Level-C evidence exist; they remain distinct from Stage 4B.1 execution topology and later policy. |
| Policy / strategy / retry / action authorization and execution | Future | Must not be projected backward into current runtime behavior. |

## 8. What Not to Assume

- Permission is not business authority.
- Transaction commit is not semantic correctness.
- Identifier existence is not accepted membership.
- Projection freshness is not projection correctness.
- Snapshot existence is not trust.
- Idempotent replay is not general retry permission.
- `SemanticOutcome.ok` is not executable authorization.
- `DecisionReceipt` is not `DiagnosticTrace`, `AttemptLog`, policy, or action.
- Multi-agent consensus is not truth.

## 9. Detailed Topic Indexes

- [Write-side Documentation Index](topic_indexes/WRITE_SIDE_DOCUMENT_INDEX.md) — domain legality, identity, idempotency, validation, admission, and durable append.
- [Read-side Documentation Index](topic_indexes/READ_SIDE_DOCUMENT_INDEX.md) — projections, accepted-history consumption, per-order progress, replay, and drift evidence.
- [Snapshot Trust Documentation Index](topic_indexes/SNAPSHOT_DOCUMENT_INDEX.md) — qualification, lineage, hashing, replay, resolution, and fallback.
- [Durable History and Permission Documentation Index](topic_indexes/DURABLE_HISTORY_PERMISSION_DOCUMENT_INDEX.md) — accepted-history protection, roles, mutation boundaries, and actor metadata.
- [SemanticOutcome Documentation Index](topic_indexes/SEMANTIC_OUTCOME_DOCUMENT_INDEX.md) — Stage 4A contract, mappings, stability, and later-layer separation.
- [Mathematical Structure Documentation Index](optional_lenses/MATHEMATICAL_STRUCTURE_DOCUMENT_INDEX.md) — optional mathematical reading lens, not a Compass system area or architecture taxonomy.

For optional context beyond the core sequence, [Reasoning Notes](../reasoning_notes/README.md) preserve non-authoritative derivation paths, while [Postmortems](../postmortems/README.md) reconstruct concrete engineering, architectural, learning, or preventive episodes.

This file routes readers into existing authority-bearing and implementation documents. It does not override them.
