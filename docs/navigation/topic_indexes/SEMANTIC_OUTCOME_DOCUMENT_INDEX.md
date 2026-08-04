# SemanticOutcome Documentation Index

[← Back to Topic_Indexes Index](README.md)

## How to Use This Index

This is topic-based navigation for the completed Stage 4A `SemanticOutcome` core. Existing `docs/` folders remain the source of each document's role and chronology. A document appears under multiple topics only when it makes a substantial contribution to each.

Technical evidence is not semantic meaning. `SemanticOutcome` describes the semantic meaning of bounded evidence but does not authorize action. Stage 4A completed the typed interpretation boundary. Stage 4B then completed the `DecisionReceipt` contract, generic and producer mappings, tri-state flags, strict serializer v1, storage-neutral persistence contracts, and explicit caller-owned PostgreSQL persistence. Mapping remains explicit rather than automatic. `DiagnosticTrace` / `ResolutionTrace` remain the unimplemented Stage 4B.1 boundary; policy, strategy, retry, and action remain later work.

This index does not override Stage 4A contracts or establish semantic, runtime-policy, retry, strategy, receipt, trace, or public-serialization authority.

## SemanticOutcome Reading Path

| Order | Document | Role | Why read here |
|---:|---|---|---|
| 1 | [Stage 4A README](../../implementation_notes/stage_4a/README.md) | Stage navigation/status | Start with the completed Stage 4A scope, PR sequence, and explicit later-stage deferrals. |
| 2 | [Stage 4A closeout](../../implementation_notes/stage_4a/stage_4a_closeout.md) | Stage closeout | Confirm the final supported outcome areas, preserved boundaries, and Stage 4B checkpoints. |
| 3 | [Runtime SemanticOutcome boundary](../../boundary_notes/runtime_semantic_outcome_boundary.md) | Boundary note | Establish why technical status, semantic meaning, runtime decision, strategy, and retry remain separate. |
| 4 | [PR1 SemanticOutcome implementation boundary](../../implementation_notes/stage_4a/semantic_outcome_boundary.md) | Design/implementation note | See the initial implementation responsibility boundary and candidate vocabulary before the concrete contract. |
| 5 | [SemanticOutcome result contract](../../implementation_notes/stage_4a/semantic_outcome_result_contract.md) | Implementation boundary | Learn the internal fields, vocabularies, identity, and evidence constraints established by PR2. |
| 6 | [Runtime technical-status mapping](../../implementation_notes/stage_4a/runtime_technical_status_mapping.md) | Implementation boundary | Understand the generic normalized-status-to-semantic-fields mapper. |
| 7 | [Read-side outcome mapping](../../implementation_notes/stage_4a/read_side_outcome_mapping.md) | Implementation boundary | Follow projection-validation and Snapshot Trust result objects into the generic mapper. |
| 8 | [Write-side admission outcome mapping](../../implementation_notes/stage_4a/write_side_admission_outcome_mapping.md) | Implementation boundary | Follow write-side orchestration evidence into `SemanticOutcome` without changing admission. |
| 9 | [Semantic mapping stability](../../implementation_notes/stage_4a/agent_rule_bypass_risk_semantic_mapping_stability.md) | Governance/stability note | Understand why mapping changes must be explicit, test-visible, and reviewed. |
| 10 | [Drift validation cost boundary](../../implementation_notes/stage_4a/drift_validation_cost_boundary.md) | Design/implementation note | Separate semantic drift meaning from validation frequency, replay scope, and strategy. |
| 11 | [PR4 closeout](../../implementation_notes/stage_4a/pr4_closeout.md) | PR closeout | Review the completed Read-side/Snapshot adapter boundary and its chronology. |
| 12 | [PR5 closeout](../../implementation_notes/stage_4a/pr5_closeout.md) | PR closeout | Review the completed Write-side adapter and identity-lineage checkpoints. |
| 13 | [Stage 4A PR breakdown](../../implementation_notes/stage_4a/pr_breakdown.md) | Implementation history | Read the PR1–PR6 planning and delivery chronology after the completed contracts. |
| 14 | [SemanticOutcome versus JSON](../../boundary_notes/semantic_outcome_vs_json_public_boundary_note.md) | Conceptual boundary note | Keep semantic meaning, governance evidence, and serialization format distinct. |
| 15 | [DecisionReceipt Boundary](../../boundary_notes/decision_receipt_boundary.md) | Canonical cross-stage boundary | Continue from semantic interpretation into the completed governance-evidence contract without equating the two. |
| 16 | [Stage 4B Closeout](../../implementation_notes/stage_4b/stage_4b_closeout.md) | Stage closeout | Confirm completed generic/producer mapping, tri-state flags, serializer v1, explicit persistence, and current non-goals. |
| 17 | [From Exception Strings to Governable Outcomes](../../reasoning_notes/from_exception_strings_to_governable_outcomes.md) | Reasoning note | Trace why structured meaning is needed before later runtime control. |
| 18 | [From Replay/Rebuild Validation to Layer 2 Governance](../../reasoning_notes/from_replay_rebuild_validation_to_layer2_governance.md) | Reasoning note | Trace why a correctness oracle is evidence substrate rather than a governance engine. |

## Overview and Responsibility Map

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Stage 4A README](../../implementation_notes/stage_4a/README.md) | Stage navigation/status | Start here | Summarizes the completed generic, Read-side, Snapshot, and Write-side semantic mapping baseline. | Stage 4A is closed after PR6; navigation is not the low-level contract. |
| [Stage 4A closeout](../../implementation_notes/stage_4a/stage_4a_closeout.md) | Stage closeout | Start here | Records final supported areas, identity safeguards, and later-stage checkpoints. | Current maturity summary. |
| [Runtime SemanticOutcome boundary](../../boundary_notes/runtime_semantic_outcome_boundary.md) | Boundary note | Core | Defines `SemanticOutcome` as meaning rather than decision, strategy, retry, or receipt. | Stage 4A conceptual boundary. |
| [SemanticOutcome result contract](../../implementation_notes/stage_4a/semantic_outcome_result_contract.md) | Implementation boundary | Core | Defines the concrete internal runtime contract and initial vocabulary. | Implemented PR2 contract governs earlier candidate vocabulary. |
| [Runtime technical-status mapping](../../implementation_notes/stage_4a/runtime_technical_status_mapping.md) | Implementation boundary | Core | Defines the reusable generic mapping layer. | Implemented PR3 baseline. |
| [Stage 4A PR breakdown](../../implementation_notes/stage_4a/pr_breakdown.md) | Implementation history | Historical/supporting | Records the PR1–PR6 sequence and evolving scope. | Planning chronology must be read with later completed contracts. |

## Technical Evidence versus Semantic Meaning

Technical execution success, technical failure, adapter status, and semantic correctness are distinct. Stage 4A consumes bounded technical or adapter evidence and produces a semantic interpretation. It does not change the evidence producer's responsibility, alter accepted-history authority, or retroactively redefine earlier-stage validation and admission boundaries.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Runtime SemanticOutcome boundary](../../boundary_notes/runtime_semantic_outcome_boundary.md) | Boundary note | Start here | Establishes the core rule that a technical status is not a semantic outcome. | Conceptual Stage 4A entry point. |
| [PR1 SemanticOutcome implementation boundary](../../implementation_notes/stage_4a/semantic_outcome_boundary.md) | Design/implementation note | Core | Defines semantic interpretation as distinct from technical completion and action. | PR1 boundary; candidate names are refined by later implementation. |
| [Runtime technical-status mapping](../../implementation_notes/stage_4a/runtime_technical_status_mapping.md) | Implementation boundary | Core | Converts normalized evidence into semantic fields while preserving the source status. | Implemented PR3 mapper. |
| [From Replay/Rebuild Validation to Layer 2 Governance](../../reasoning_notes/from_replay_rebuild_validation_to_layer2_governance.md) | Reasoning note | Historical/supporting | Explains why replay comparison produces evidence but does not choose recovery. | Non-authoritative Stage 3.5C derivation. |

## SemanticOutcome Vocabulary and Contract

The reviewed internal contract contains:

- `outcome_id`: native semantic-outcome identity, not event, request, or receipt identity;
- `ok`: coarse semantic property, not executable authorization;
- `boundary`: observation/interpretation boundary, not proven root cause;
- `category`: broad semantic family;
- `semantic_code`: precise machine-readable meaning;
- `severity`, `risk_level`, and `reversibility`: evidence for later consumers, not decisions;
- `reason`: explanation supported by the observation, without invented cross-boundary causality;
- `context` and `evidence`: defensively copied/frozen bounded internal mappings, not durable traces or public schemas.

There is no separate reviewed `detail` field. Adapter-specific detail belongs in supported reason, context, or evidence.

The Stage 4A contract is an internal runtime semantic contract. Stage 4B's strict serializer v1 is a separate internal serialization contract; it does not make `SemanticOutcome`, `DecisionReceipt`, and JSON equivalent or establish indefinite external API compatibility.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [SemanticOutcome result contract](../../implementation_notes/stage_4a/semantic_outcome_result_contract.md) | Implementation boundary | Start here | Defines the frozen contract, fields, categories, codes, boundaries, and evidence semantics. | Implemented PR2 internal runtime contract. |
| [PR1 SemanticOutcome implementation boundary](../../implementation_notes/stage_4a/semantic_outcome_boundary.md) | Design/implementation note | Core | Explains the intended semantic responsibilities and evidence boundary. | Earlier candidate vocabulary is subordinate to PR2. |
| [Stage 4A closeout](../../implementation_notes/stage_4a/stage_4a_closeout.md) | Stage closeout | Core | Confirms the final contract and preserved identity/evidence boundaries. | Stage closed after PR6. |
| [Semantic mapping stability](../../implementation_notes/stage_4a/agent_rule_bypass_risk_semantic_mapping_stability.md) | Governance/stability note | Deep dive | Explains why enum and mapping changes alter governance meaning. | Supporting stability analysis, not a new vocabulary source. |

## Generic Runtime Technical-status Mapping

The generic mapper consumes normalized status plus boundary, reason, context, and evidence. Its static mapping determines `ok`, category, semantic code, severity, risk, and reversibility. It preserves the normalized technical status in evidence and rejects contradictory status evidence.

Concrete adapters extract evidence from result objects, preserve their observation boundary, and add noncontradictory context/evidence. They must not turn every adapter-specific status into universal vocabulary or select policy/action.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Runtime technical-status mapping](../../implementation_notes/stage_4a/runtime_technical_status_mapping.md) | Implementation boundary | Start here | Defines supported statuses, mapping families, evidence preservation, and generic-mapper non-goals. | Implemented PR3 baseline; later PR5 expanded Write-side status support. |
| [SemanticOutcome result contract](../../implementation_notes/stage_4a/semantic_outcome_result_contract.md) | Implementation boundary | Core | Supplies the stable fields populated by the mapper. | Implemented PR2 dependency. |
| [Read-side outcome mapping](../../implementation_notes/stage_4a/read_side_outcome_mapping.md) | Implementation boundary | Core | Demonstrates adapter extraction and delegation to the generic mapper. | Completed PR4 adapter. |
| [Write-side admission outcome mapping](../../implementation_notes/stage_4a/write_side_admission_outcome_mapping.md) | Implementation boundary | Core | Demonstrates protected identity context and storage-neutral Write-side status normalization. | Completed PR5 adapter. |

## Write-side Admission Mapping

The documented mapping preserves:

- accepted → `WRITE_SIDE_ACCEPTED` → `VALID / SEMANTICALLY_VALID`;
- validation blocked → `COMPASS_VALIDATION_BLOCKED` → `BLOCK_REQUIRED / SEMANTIC_CONFLICT_DETECTED`;
- stale write → `CONCURRENT_STATE_STALENESS` → `CONCURRENCY_UNCERTAIN`;
- lock timeout → `LOCK_TIMEOUT` → `CONCURRENCY_UNCERTAIN`;
- infrastructure error → `WRITE_SIDE_INFRASTRUCTURE_ERROR` → `ESCALATION_REQUIRED / REQUIRES_OPERATOR_REVIEW`;
- idempotent replay → `IDEMPOTENT_REPLAY` → `RETRY_CLASSIFIED / IDEMPOTENT_REPLAY_ALLOWED`;
- idempotency conflict → `IDEMPOTENCY_CONFLICT` → `BLOCK_REQUIRED / SEMANTIC_CONFLICT_DETECTED`.

No separate domain-rejection mapping is established in the reviewed batch. `IDEMPOTENT_REPLAY_ALLOWED` means an existing accepted result may be replayed safely; it does not authorize a new command execution or general retry. `REQUIRES_OPERATOR_REVIEW` expresses escalation meaning but does not send an alert, page an operator, create a ticket, quarantine data, or execute policy.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Write-side admission outcome mapping](../../implementation_notes/stage_4a/write_side_admission_outcome_mapping.md) | Implementation boundary | Start here | Defines the concrete adapter, mappings, identity-lineage protection, and non-goals. | Completed PR5 mapping. |
| [PR5 closeout](../../implementation_notes/stage_4a/pr5_closeout.md) | PR closeout | Historical/supporting | Confirms mapped statuses and the completed Write-side adapter boundary. | Closeout chronology; detailed mapping note remains core. |
| [Runtime technical-status mapping](../../implementation_notes/stage_4a/runtime_technical_status_mapping.md) | Implementation boundary | Core | Supplies generic idempotency and concurrency mappings reused by PR5. | PR3 baseline updated during PR5. |
| [Stage 4A closeout](../../implementation_notes/stage_4a/stage_4a_closeout.md) | Stage closeout | Core | Confirms Write-side mapping without changing admission or accepted-history behavior. | Current stage summary. |

## Read-side Replay-validation Mapping

The durable replay adapter preserves:

- `MATCH` → `VALID / SEMANTICALLY_VALID` at `LAYER_2_READ_SIDE`;
- `DRIFT` → `DRIFT / DRIFT_DETECTED` at `LAYER_2_READ_SIDE`;
- `NO_ACCEPTED_HISTORY` → `UNRESOLVED / RUNTIME_UNRESOLVED` at `LAYER_2_READ_SIDE`.

`MISSING_PROJECTION` maps to `REBUILD_REQUIRED / REQUIRES_REBUILD` at `LAYER_2_READ_SIDE`. This is semantic evidence for later consumers, not automatic rebuild authorization or execution.

Read-side observation does not prove Write-side root cause. Ordinary projection-worker execution and freshness remain separate from semantic replay-validation evidence.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Read-side outcome mapping](../../implementation_notes/stage_4a/read_side_outcome_mapping.md) | Implementation boundary | Start here | Maps `ReplayValidationResult`, preserves observation boundary, and forbids root-cause inference. | Completed PR4 adapter. |
| [Runtime technical-status mapping](../../implementation_notes/stage_4a/runtime_technical_status_mapping.md) | Implementation boundary | Core | Defines documented mappings for match, drift, missing projection, and unavailable authority evidence. | Implemented mapping; it does not execute rebuild. |
| [PR4 closeout](../../implementation_notes/stage_4a/pr4_closeout.md) | PR closeout | Historical/supporting | Confirms completed Read-side mapping and deferred worker-freshness semantics. | PR4 closeout. |
| [From Replay/Rebuild Validation to Layer 2 Governance](../../reasoning_notes/from_replay_rebuild_validation_to_layer2_governance.md) | Reasoning note | Historical/supporting | Explains why comparison evidence is substrate rather than recovery governance. | Non-authoritative design evolution. |

## Snapshot-assisted Evidence Mapping

Snapshot validation and resolution retain different assurance histories even when statuses share semantic fields:

- `MATCH` may map to `VALID / SEMANTICALLY_VALID` after a completed authority comparison;
- `RESOLVED_FROM_SNAPSHOT` may map to `VALID / SEMANTICALLY_VALID` after qualified snapshot-plus-tail resolution without performing full authority comparison itself;
- `MISSING_SNAPSHOT` and `TAIL_REPLAY_FAILED` map to `FALLBACK_REQUIRED / FAST_PATH_UNAVAILABLE`;
- invalid boundary, precondition, or compatibility maps to `UNTRUSTED / DERIVED_STATE_UNTRUSTED`;
- tail source-contract violation maps to `UNRESOLVED / RUNTIME_UNRESOLVED`, not drift;
- `SNAPSHOT_ASSISTED_DRIFT` maps to `DRIFT / DRIFT_DETECTED` only after a completed comparison;
- missing accepted history remains conservatively unresolved at `SNAPSHOT_TRUST`.

`MATCH` and `RESOLVED_FROM_SNAPSHOT` must retain different observation boundaries/statuses, evidence, reasons/context, and assurance histories. They do not prove the same thing.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Read-side outcome mapping](../../implementation_notes/stage_4a/read_side_outcome_mapping.md) | Implementation boundary | Start here | Separates full Snapshot Trust validation evidence from assisted-resolution evidence. | Completed PR4 adapter. |
| [Runtime technical-status mapping](../../implementation_notes/stage_4a/runtime_technical_status_mapping.md) | Implementation boundary | Core | Defines fast-path, untrusted, unresolved, valid, and drift mapping families. | Implemented generic mapping. |
| [PR4 closeout](../../implementation_notes/stage_4a/pr4_closeout.md) | PR closeout | Historical/supporting | Confirms validator/resolver evidence-shape and tail-contract distinctions. | PR4 closeout. |
| [Drift validation cost boundary](../../implementation_notes/stage_4a/drift_validation_cost_boundary.md) | Design/implementation note | Deep dive | Explains why authority comparison and assisted resolution have different runtime costs and purposes. | Cost evidence does not choose policy. |

## SemanticOutcome versus Runtime Decision

`SemanticOutcome` describes meaning. A future runtime decision chooses action. Stage 4A does not allow or block a mutation, order a rebuild, create a quarantine, execute escalation, or authorize downstream activity. Outcome categories such as `BLOCK_REQUIRED`, `ESCALATION_REQUIRED`, or `FALLBACK_REQUIRED` are semantic classifications for later policy consumers, not executable commands.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Runtime SemanticOutcome boundary](../../boundary_notes/runtime_semantic_outcome_boundary.md) | Boundary note | Start here | Defines meaning and decision as separate responsibilities. | Stage 4A boundary. |
| [PR1 SemanticOutcome implementation boundary](../../implementation_notes/stage_4a/semantic_outcome_boundary.md) | Design/implementation note | Core | Shows how one semantic meaning may support several later decisions. | PR1 conceptual boundary. |
| [SemanticOutcome result contract](../../implementation_notes/stage_4a/semantic_outcome_result_contract.md) | Implementation boundary | Core | Makes severity, risk, and reversibility policy inputs rather than action fields. | Implemented PR2 contract. |
| [From Exception Strings to Governable Outcomes](../../reasoning_notes/from_exception_strings_to_governable_outcomes.md) | Reasoning note | Historical/supporting | Explains the derivation from outcomes toward later control. | Reasoning record is not the current decision-policy contract. |

## SemanticOutcome versus Strategy and Fallback

Stage 4A may express that a fast path is unavailable or that authority fallback is semantically relevant. It does not select fallback, choose among replay/resolver/rebuild paths, evaluate strategy health, or execute any recovery. Strategy selection must occur only after semantic meaning and later policy permission are established.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Runtime SemanticOutcome boundary](../../boundary_notes/runtime_semantic_outcome_boundary.md) | Boundary note | Start here | Separates outcome, runtime decision, and execution strategy. | Conceptual Stage 4A boundary. |
| [SemanticOutcome result contract](../../implementation_notes/stage_4a/semantic_outcome_result_contract.md) | Implementation boundary | Core | Defines `FAST_PATH_UNAVAILABLE` and related meaning without recovery execution. | Implemented PR2 contract. |
| [Runtime technical-status mapping](../../implementation_notes/stage_4a/runtime_technical_status_mapping.md) | Implementation boundary | Core | Maps missing snapshot/tail failure into semantic fast-path unavailability. | Generic mapper does not choose fallback. |
| [Drift validation cost boundary](../../implementation_notes/stage_4a/drift_validation_cost_boundary.md) | Design/implementation note | Deep dive | Preserves cost differences future selectors may use. | Stage 4D is the stated later strategy consumer. |

## SemanticOutcome versus Retry Governance

Stage 4A may preserve retry-relevant meaning such as idempotent replay classification, concurrency uncertainty, fast-path unavailability, and unresolved evidence. It does not decide whether to retry, whether intent remains valid, retry budget, attempt count, backoff/jitter, irreversible-action safety, or attempt lineage.

`IDEMPOTENT_REPLAY_ALLOWED` means a prior accepted result can be used for the same stored request effect. It is not general retry authorization and does not create another accepted event.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Runtime SemanticOutcome boundary](../../boundary_notes/runtime_semantic_outcome_boundary.md) | Boundary note | Start here | Separates retry attempts, preserved intent, and outcome meaning. | Retry governance deferred beyond Stage 4A. |
| [Runtime technical-status mapping](../../implementation_notes/stage_4a/runtime_technical_status_mapping.md) | Implementation boundary | Core | Maps idempotency and concurrency evidence without deciding another attempt. | Implemented PR3 baseline. |
| [Write-side admission outcome mapping](../../implementation_notes/stage_4a/write_side_admission_outcome_mapping.md) | Implementation boundary | Core | Preserves replay/conflict and stale/timeout evidence at the Write-side boundary. | Completed PR5 adapter. |
| [Stage 4A closeout](../../implementation_notes/stage_4a/stage_4a_closeout.md) | Stage closeout | Core | Confirms retry governance, automatic retry blocking, and attempt records remain deferred. | Current stage maturity. |

## SemanticOutcome versus DecisionReceipt and DiagnosticTrace

Stage 4A produces semantic meaning. Completed Stage 4B can explicitly map that meaning into a typed `DecisionReceipt`, preserve producer-specific evidence, serialize the receipt through strict serializer v1, and persist it through an explicit caller-owned storage operation. `SemanticOutcome`, `DecisionReceipt`, the serialized JSON envelope, and the persisted row remain separate responsibilities. `outcome_id` is not a receipt identity.

No mapper automatically invokes the store or reconciles accepted history into receipts. Stage 4B.1 `DiagnosticTrace` / `ResolutionTrace` remains unimplemented, as do policy, retry governance, strategy selection, and action execution.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Runtime SemanticOutcome boundary](../../boundary_notes/runtime_semantic_outcome_boundary.md) | Boundary note | Start here | Separates semantic meaning, durable summary evidence, and detailed failure-path traces. | Stage 4A conceptual boundary; later completed boundaries govern current receipt behavior. |
| [SemanticOutcome versus JSON](../../boundary_notes/semantic_outcome_vs_json_public_boundary_note.md) | Conceptual boundary note | Core | Separates semantic interpretation, governance evidence, serialization, and persistence. | Not an external API compatibility contract. |
| [DecisionReceipt Boundary](../../boundary_notes/decision_receipt_boundary.md) | Canonical boundary note | Core | Owns the current cross-stage receipt responsibility and non-goals. | DecisionReceipt is governance evidence, not action or trace. |
| [SemanticOutcome to DecisionReceipt](../../implementation_notes/stage_4b/semantic_outcome_to_decision_receipt.md) | Implementation boundary | Core | Defines explicit generic construction without producer execution or persistence. | Completed Stage 4B mapping. |
| [DecisionReceipt Durable Persistence](../../implementation_notes/stage_4b/decision_receipt_persistence.md) | Implementation boundary | Deep dive | Defines strict serialization, persistence envelopes, and caller-owned PostgreSQL persistence. | No automatic materialization or transaction completion. |
| [Stage 4B Closeout](../../implementation_notes/stage_4b/stage_4b_closeout.md) | Stage closeout | Core | Records final Stage 4B completion and the Stage 4B.1 transition. | Current completion authority. |

## Mapping Stability and Extension Boundaries

Semantic mappings may evolve only through explicit, test-visible review. Silent reinterpretation, weakening a mapping merely to let an agent action pass, adapter refactors that invisibly alter meaning, and unreviewed mapping-policy coupling violate the documented boundary.

A stable core is not a permanently closed vocabulary. Future additions must preserve explicit compatibility, semantic review, and downstream-impact boundaries.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Semantic mapping stability](../../implementation_notes/stage_4a/agent_rule_bypass_risk_semantic_mapping_stability.md) | Governance/stability note | Start here | Defines silent semantic contract drift and agent rule-bypass risk. | Supporting Stage 4A threat/stability analysis. |
| [SemanticOutcome result contract](../../implementation_notes/stage_4a/semantic_outcome_result_contract.md) | Implementation boundary | Core | Defines the stable internal vocabularies consumed by mappings. | Implemented PR2 core. |
| [Runtime technical-status mapping](../../implementation_notes/stage_4a/runtime_technical_status_mapping.md) | Implementation boundary | Core | Makes mappings explicit, enumerable, and evidence-preserving. | Implemented PR3 baseline. |
| [Stage 4A PR breakdown](../../implementation_notes/stage_4a/pr_breakdown.md) | Implementation history | Historical/supporting | Shows controlled vocabulary/mapping expansion across PR2–PR5. | Historical delivery chronology. |

## Drift and Validation-cost Evidence

Validation cost, replay counts, snapshot use, timing, and global scope are descriptive evidence. They do not determine validation frequency, sampling, whether validation should run, fallback selection, strategy, or policy.

Order-scoped projection validation, Snapshot Trust authority comparison, and global projection consistency have different scopes and costs. `DRIFT_DETECTED` names completed divergence; it does not require full replay on every read.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Drift validation cost boundary](../../implementation_notes/stage_4a/drift_validation_cost_boundary.md) | Design/implementation note | Start here | Separates order-scoped, snapshot-authority, and global validation costs and purposes. | PR3 supporting boundary; not a benchmark or policy matrix. |
| [Runtime technical-status mapping](../../implementation_notes/stage_4a/runtime_technical_status_mapping.md) | Implementation boundary | Core | Gives projection and snapshot divergence a stable semantic name. | Mapping does not select validation cadence. |
| [Read-side outcome mapping](../../implementation_notes/stage_4a/read_side_outcome_mapping.md) | Implementation boundary | Core | Preserves completed-comparison evidence and excludes ordinary worker freshness. | Completed PR4 adapter. |
| [Stage 4A closeout](../../implementation_notes/stage_4a/stage_4a_closeout.md) | Stage closeout | Core | Defers measurement matrices, strategy, and worker-freshness governance. | Current maturity statement. |

## Stage 4A / Stage 4B Baseline and Limitations

Stage 4A completed the `SemanticOutcome` core and its generic, Read-side, Snapshot, and Write-side mapping baseline.

Stage 4B completes `DecisionReceipt`, its generic and producer mappings, tri-state flags, strict serializer v1, storage-neutral persistence contracts, and explicit caller-owned PostgreSQL persistence. It does not implement automatic materialization, accepted-history reconciliation, `DiagnosticTrace` / `ResolutionTrace`, runtime policy, strategy selection, retry governance, attempt logging, fallback execution, rebuild, quarantine, operator-review execution, or action safety.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Stage 4A README](../../implementation_notes/stage_4a/README.md) | Stage navigation/status | Start here | States the completed PR1–PR6 scope and its historical transition checkpoints. | Stage 4A closed after PR6; Stage 4B later completed. |
| [Stage 4A closeout](../../implementation_notes/stage_4a/stage_4a_closeout.md) | Stage closeout | Start here | Records final supported outcome areas and deferred governance layers. | Current maturity authority for navigation. |
| [Runtime SemanticOutcome boundary](../../boundary_notes/runtime_semantic_outcome_boundary.md) | Boundary note | Core | Defines the narrow semantic-meaning responsibility. | Does not authorize later actions. |
| [Read-side outcome mapping](../../implementation_notes/stage_4a/read_side_outcome_mapping.md) | Implementation boundary | Core | Defines the completed Read-side/Snapshot adapter baseline. | Ordinary worker freshness remains outside scope. |
| [Write-side admission outcome mapping](../../implementation_notes/stage_4a/write_side_admission_outcome_mapping.md) | Implementation boundary | Core | Defines the completed Write-side adapter baseline. | Domain rejection and later receipt policy remain outside the explicit mapping. |
| [Stage 4B Closeout](../../implementation_notes/stage_4b/stage_4b_closeout.md) | Stage closeout | Start here | Records the completed receipt boundary, mappings, serialization, persistence, and explicit non-goals. | Stage 4B is complete; Stage 4B.1 is next. |

## Implementation History and Design Evolution

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Stage 4A PR breakdown](../../implementation_notes/stage_4a/pr_breakdown.md) | Implementation history | Historical/supporting | Records PR1 boundary through PR6 closeout and the staged addition of adapters. | Read later completed contracts for current meaning. |
| [PR4 closeout](../../implementation_notes/stage_4a/pr4_closeout.md) | PR closeout | Historical/supporting | Records the completed Read-side/Snapshot adapter milestone. | PR4 chronology. |
| [PR5 closeout](../../implementation_notes/stage_4a/pr5_closeout.md) | PR closeout | Historical/supporting | Records the completed Write-side adapter and identity checkpoint. | PR5 chronology. |
| [From Exception Strings to Governable Outcomes](../../reasoning_notes/from_exception_strings_to_governable_outcomes.md) | Reasoning note | Historical/supporting | Traces the move from local failure strings to structured meaning and later control. | Predates completed contracts and discusses future governance. |
| [From Replay/Rebuild Validation to Layer 2 Governance](../../reasoning_notes/from_replay_rebuild_validation_to_layer2_governance.md) | Reasoning note | Historical/supporting | Traces the separation of correctness evidence from governance behavior. | Non-authoritative Stage 3.5C perspective. |

## Open Questions and Important Reading Notes

- Domain rejection has no separate explicit Stage 4A mapping in the reviewed batch.
- The strict serializer v1 remains separate from semantic meaning and does not create an indefinite external API compatibility promise.
- `DiagnosticTrace` / `ResolutionTrace` identity and lineage remain Stage 4B.1 work.
- Idempotency conflict may later require more precise intent/fingerprint vocabulary.
- Mapping versioning, deprecation, and backward-compatibility rules remain undefined.
- Unsupported dependency/adapter failures require boundary-specific mapping decisions.
- Validation frequency and cost policy remain later-stage work.
- Ordinary projection-worker freshness remains separate from semantic correctness and is not fully mapped here.
