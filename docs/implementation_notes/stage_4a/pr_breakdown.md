# Stage 4A PR Breakdown

[← Back to Stage 4A](README.md)

## Purpose

This note proposes the implementation sequence for:

```text
Stage 4 — Runtime Semantic Governance
```

The goal of Stage 4 is to turn runtime correctness evidence into governable semantic meaning without collapsing validation, evidence, decisions, strategy, and retry governance into one layer.

Stage 4 should not become a pile of validators, logs, and retry labels.

It should define a staged runtime semantic pipeline.

---

## Stage Principle

```text
technical evidence
→ semantic interpretation
→ durable evidence
→ policy-linked decision
→ strategy selection
→ retry governance
```

This means:

```text
technical status
should not be treated as semantic outcome

semantic outcome
should not be treated as runtime decision

runtime decision
should not be treated as execution strategy

retry attempt
should not be treated as preserved intent
```

Additional implementation principles:

```text
accepted history remains authority
derived state remains rebuildable
snapshot remains derived state compression
permission roles are not actor evidence
actor metadata is not governance receipt
SemanticOutcome should describe meaning, not execute recovery
DecisionReceipt should preserve summary evidence, not full diagnostic trace
DiagnosticTrace should preserve failure path and partial progress
StrategySelector should choose among semantically allowed options
RetryGovernance should classify attempts after semantic outcome exists
```

---

## Stage Branch / PR Branch Workflow

Stage 4 follows the staged delivery workflow used in earlier implementation phases.

The project should not treat one PR as necessarily equal to one commit.

Instead, the intended workflow is:

```text
one stage integration branch
= one integration branch for the whole Stage 4 runtime governance phase

one sub-stage branch
= one integration branch for a coherent Stage 4 sub-stage such as Stage 4A

one PRx branch
= one coherent semantic delivery unit inside the sub-stage

one PRx branch may contain multiple commits
= each commit preserves a smaller documentation, schema, code, or test boundary
```

For Stage 4, the integration branch is:

```text
feat/stage4-runtime-semantic-governance
```

For Stage 4A, the sub-stage branch is:

```text
feat/stage4a-semantic-outcome-core
```

Individual PR branches should be created from the current Stage 4A sub-stage branch, for example:

```text
feat/stage4a-pr1-semantic-outcome-boundary
feat/stage4a-pr2-semantic-outcome-result-contract
feat/stage4a-pr3-runtime-technical-status-mapping
feat/stage4a-pr4-read-side-outcome-mapping
feat/stage4a-pr5-write-side-admission-outcome-mapping
```

Each Stage 4A PR branch should be merged back into the Stage 4A sub-stage branch.

The Stage 4A sub-stage branch should be merged back into the Stage 4 integration branch only after Stage 4A reaches a coherent milestone or is intentionally closed.

The Stage 4 integration branch should be merged back to `main` only after a coherent Stage 4 milestone is complete or intentionally closed.

---

## Commit Discipline

A PR may contain more than one commit.

The important rule is not:

```text
one PR = one commit
```

The important rule is:

```text
one PR = one coherent semantic delivery unit
one commit = one smaller boundary-preserving change
```

For example, a Stage 4A PR may contain:

```text
feat: add runtime technical status mapping
docs: document runtime technical status mapping
```

These commits may belong to the same PR if they serve the same PR-level semantic goal.

The commit boundary should remain small enough to explain what changed and why.

The PR boundary should remain large enough to deliver one meaningful stage sub-goal.

---

## Documentation-First Implementation Pattern

When a PR introduces a new semantic or infrastructure boundary, the preferred order is:

```text
1. define the boundary in documentation
2. implement the minimum mechanism
3. add or defer tests according to the PR scope
4. align README / roadmap / breakdown notes if needed
```

This does not mean documentation and implementation must always be split into separate PRs.

It means the PR should make the semantic contract clear before or alongside the implementation.

Detailed commit planning should happen when entering each PRx.

This breakdown records the PR-level sequence, not the exact commit-level sequence.

---

## Proposed Stage 4A PR Sequence

```text
PR1 — Runtime SemanticOutcome Boundary
PR2 — SemanticOutcome Vocabulary / Result Contract
PR3 — Runtime Technical Status Mapping
PR4 — Snapshot / Projection Outcome Mapping
PR5 — Write-Side Admission Outcome Mapping
PR6 — Stage 4A Closeout
```

After PR6, Stage 4A should provide a stable SemanticOutcome core for later Stage 4B receipts and Stage 4C runtime decisions.

---

# PR1 — Runtime SemanticOutcome Boundary

## Goal

Define the Stage 4A boundary before implementation begins.

PR1 establishes why SemanticOutcome exists and how it differs from raw technical status, runtime decision, execution strategy, and retry governance.

## Status

Implemented by:

```text
feat/stage4a-pr1-semantic-outcome-boundary
```

## Scope

PR1 adds:

```text
docs/implementation_notes/stage_4a/README.md
docs/implementation_notes/stage_4a/pr_breakdown.md
docs/implementation_notes/stage_4a/semantic_outcome_boundary.md
docs/boundary_notes/runtime_semantic_outcome_boundary.md
```

PR1 clarifies:

```text
why Stage 4A exists
why technical status is not semantic outcome
why semantic outcome is not runtime decision
why runtime decision is not execution strategy
why retry attempt is not same intent
which later Stage 4 concepts are explicitly deferred
how SemanticOutcome relates to Layer 1 and Layer 2 without rewriting Layer 1
```

## Non-goals

PR1 does not add:

```text
production code
unit tests
SQL migrations
DecisionReceipt
DiagnosticTrace
Measurement Matrix
policy contract YAML
RuntimeDecisionPolicy
StrategySelector
RetryGovernance
benchmark suite
Stage 5 action safety gate
```

---

# PR2 — SemanticOutcome Vocabulary / Result Contract

## Goal

Introduce the minimal in-code vocabulary and result contract for runtime semantic outcomes.

PR2 translates the Stage 4A boundary into a small code-level contract.

It defines how runtime correctness evidence can be represented as semantic meaning without deciding recovery, strategy, retry, or durable receipt behavior.

## Status

Implemented by:

```text
feat/stage4a-pr2-semantic-outcome-result-contract
```

## Scope

PR2 adds:

```text
src/compass/runtime/__init__.py
src/compass/runtime/semantic_outcome.py
tests/unit/compass/runtime/test_semantic_outcome.py
docs/implementation_notes/stage_4a/semantic_outcome_result_contract.md
```

PR2 introduces:

```text
SemanticOutcome
SemanticOutcomeCategory
SemanticOutcomeCode
SemanticBoundary
SemanticSeverity
SemanticRiskLevel
SemanticReversibility
```

The contract preserves:

```text
outcome identity
boundary identity
semantic category
semantic code
severity
risk level
reversibility
reason
context evidence
runtime evidence
```

PR2 also establishes that `context` and `evidence` are defensively copied and frozen for common container types.

This prevents semantic outcome evidence from being mutated after construction through the original input objects.

## Important Boundary

PR2 defines semantic interpretation only.

It does not map existing technical statuses into outcomes yet.

For example, PR2 defines that these meanings can exist:

```text
FAST_PATH_UNAVAILABLE
DRIFT_DETECTED
```

But PR2 does not yet implement the mapper from:

```text
TAIL_REPLAY_FAILED
→ FAST_PATH_UNAVAILABLE

SNAPSHOT_ASSISTED_DRIFT
→ DRIFT_DETECTED
```

That mapping belongs to PR3 / PR4.

## Non-goals

PR2 does not implement:

```text
technical status mapping
ProjectionSnapshotReplayValidationStatus mapping
ProjectionSnapshotAssistedResolutionStatus mapping
write-side admission mapping
DecisionReceipt
DiagnosticTrace
Measurement Matrix
policy contract YAML
RuntimeDecisionPolicy
StrategySelector
RetryGovernance
SQL migrations
durable receipt store
```

---

# PR3 — Runtime Technical Status Mapping

## Goal

Introduce a generic mapper from raw runtime technical status names into `SemanticOutcome`.

PR3 begins converting raw validator / resolver / runtime statuses into structured semantic interpretation without coupling the mapper to specific validator result objects.

## Status

Implemented by:

```text
feat/stage4a-pr3-runtime-technical-status-mapping
```

## Scope

PR3 adds:

```text
src/compass/runtime/technical_status_mapping.py
tests/unit/compass/runtime/test_technical_status_mapping.py
docs/implementation_notes/stage_4a/runtime_technical_status_mapping.md
docs/implementation_notes/stage_4a/drift_validation_cost_boundary.md
```

PR3 updates:

```text
src/compass/runtime/__init__.py
docs/implementation_notes/stage_4a/README.md
docs/implementation_notes/stage_4a/pr_breakdown.md
```

PR3 introduces:

```text
RuntimeTechnicalStatusMapping
map_runtime_technical_status
supported_runtime_technical_statuses
```

PR3 supports an initial generic status set, including:

```text
MATCH
RESOLVED_FROM_SNAPSHOT
MISSING_SNAPSHOT
MISSING_PROJECTION
NO_ACCEPTED_HISTORY
NO_ACCEPTED_HISTORY_FOR_ORDER
INVALID_SNAPSHOT_BOUNDARY
INVALID_SNAPSHOT_PRECONDITION
INVALID_SNAPSHOT_COMPATIBILITY
TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
TAIL_REPLAY_FAILED
DRIFT
SNAPSHOT_ASSISTED_DRIFT
CONCURRENT_STATE_STALENESS
OCC_CONFLICT_AFTER_VALIDATION
LOCK_TIMEOUT
WRITE_SIDE_ACCEPTED
COMPASS_VALIDATION_BLOCKED
WRITE_SIDE_INFRASTRUCTURE_ERROR
IDEMPOTENT_REPLAY
IDEMPOTENCY_CONFLICT
```

The mapping preserves context and evidence without making policy decisions.

## Important Boundary

PR3 defines generic status-to-outcome mapping only.

It does not inspect adapter-specific result objects.

For example, PR3 may map:

```text
TAIL_REPLAY_FAILED
→ FAST_PATH_UNAVAILABLE

SNAPSHOT_ASSISTED_DRIFT
→ DRIFT_DETECTED
```

But PR3 does not yet convert:

```text
ProjectionSnapshotReplayValidationResult
ProjectionSnapshotAssistedResolutionResult
DurableReplayValidationResult
```

into `SemanticOutcome`.

That adapter work belongs to PR4.

PR3 also does not convert explicit Layer 1 admission rejection results into `SemanticOutcome`.

That line belongs to PR5.

## Drift / Fast-Path Boundary

PR3 preserves the distinction between semantic drift and fast-path failure.

`TAIL_REPLAY_FAILED` should not automatically imply snapshot corruption.

A tail replay failure means the current resolution path failed or became unavailable.

It maps toward fast-path unavailability.

By contrast, `SNAPSHOT_ASSISTED_DRIFT` means snapshot-assisted reconstruction diverged from accepted-history authority.

It maps toward semantic drift.

This distinction prevents Stage 4A from collapsing infrastructure / replay-path failure into semantic corruption.

## Idempotency Boundary

`IDEMPOTENCY_CONFLICT` is intentionally mapped conservatively in PR3.

PR3 does not inspect operation mismatch, fingerprint mismatch, stored request evidence, or incoming request evidence.

Later write-side admission / idempotency adapters may split this into more precise statuses such as:

```text
IDEMPOTENCY_OPERATION_MISMATCH
→ INTENT_INCONSISTENT / INTENT_DRIFT_DETECTED

IDEMPOTENCY_FINGERPRINT_MISMATCH
→ INTENT_INCONSISTENT / SEMANTIC_CONFLICT_DETECTED
```

This split belongs to PR5 or Stage 4E, not this generic mapper.

## Cost Boundary

PR3 documents a cost boundary for drift validation.

Projection state drift validation may be cheap when scoped by aggregate identity, such as `order_id`.

Snapshot trust validation is different because repeated full authority comparison before every fast-path request can defeat the purpose of the snapshot path.

Global projection consistency validation is different again and may require global or partition-wide checks.

See:

```text
docs/implementation_notes/stage_4a/drift_validation_cost_boundary.md
```

## Non-goals

PR3 does not implement:

```text
ProjectionSnapshotReplayValidationResult adapter
ProjectionSnapshotAssistedResolutionResult adapter
DurableReplayValidationResult adapter
write-side admission rejection adapter
runtime action selection
fallback execution
rebuild orchestration
quarantine mechanism
DecisionReceipt
DiagnosticTrace
Measurement Matrix
RuntimeDecisionPolicy
StrategySelector
RetryGovernance
SQL migrations
durable receipt store
```

---

# PR4 — Snapshot / Projection Outcome Mapping

## Goal

Apply SemanticOutcome mapping to read-side correctness and snapshot-trust boundaries.

PR4 connects concrete validator / resolver result objects to the Stage 4A `SemanticOutcome` contract.

The core direction is:

```text
read-side validator / resolver result
→ technical_status + boundary + reason + context + evidence
→ map_runtime_technical_status(...)
→ SemanticOutcome
```

PR4 is the adapter layer between Stage 3.5 read-side result objects and Stage 4A semantic outcomes.

## Status

Implemented by:

```text
feat/stage4a-pr4-read-side-outcome-mapping
feat/stage4a-pr5-write-side-admission-outcome-mapping
```

## Scope

PR4 adds:

```text
src/compass/runtime/read_side_outcome_mapping.py
tests/unit/compass/runtime/test_read_side_outcome_mapping.py
docs/implementation_notes/stage_4a/read_side_outcome_mapping.md
docs/implementation_notes/stage_4a/pr4_closeout.md
```

PR4 updates:

```text
src/compass/runtime/__init__.py
docs/implementation_notes/stage_4a/README.md
docs/implementation_notes/stage_4a/pr_breakdown.md
```

PR4 maps:

```text
ReplayValidationResult
ProjectionSnapshotReplayValidationResult
ProjectionSnapshotAssistedResolutionResult
```

into `SemanticOutcome`.

## Implemented Mapping Functions

PR4 introduces:

```text
map_replay_validation_result_to_semantic_outcome
map_projection_snapshot_replay_validation_result_to_semantic_outcome
map_projection_snapshot_assisted_resolution_result_to_semantic_outcome
```

These functions do not own semantic status mapping tables directly.

They delegate normalized technical statuses to the PR3 mapper:

```text
map_runtime_technical_status(...)
```

## Boundary Mapping

The observation boundary is determined by where the result was produced.

```text
ReplayValidationResult
→ LAYER_2_READ_SIDE
```

because durable replay validation observes whether persisted projection state matches accepted-history replay.

```text
ProjectionSnapshotReplayValidationResult
→ SNAPSHOT_TRUST
```

because snapshot replay validation observes whether snapshot-assisted replay can be trusted against accepted-history authority replay.

```text
ProjectionSnapshotAssistedResolutionResult
→ SNAPSHOT_TRUST
```

because snapshot-assisted resolution consumes a pre-qualified snapshot identity and attempts snapshot + tail reconstruction.

## Observation Boundary vs Root Cause Boundary

PR4 establishes an important rule:

```text
SemanticBoundary records where the condition was observed.
It does not prove the original root cause.
```

For example:

```text
NO_ACCEPTED_HISTORY
observed by DurableReplayValidator
→ boundary = LAYER_2_READ_SIDE
```

and:

```text
NO_ACCEPTED_HISTORY_FOR_ORDER
observed by ProjectionSnapshotReplayValidator
→ boundary = SNAPSHOT_TRUST
```

These outcomes do not claim that Layer 1 write-side admission failed.

They only claim that the current read-side or snapshot-trust boundary cannot establish authority-backed validation because accepted-history evidence is unavailable for the requested order.

Future write-side admission outcomes may explain why no accepted event exists.

That correlation belongs to later `DecisionReceipt`, `DiagnosticTrace`, or `ResolutionTrace` layers.

PR4 must remain conservative:

```text
read-side / snapshot observation
→ RUNTIME_UNRESOLVED
```

It must not infer:

```text
read-side missing authority evidence
→ write-side failure
```

## Tail Source Contract Violation Boundary

PR4 preserves the distinction:

```text
TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
≠
SNAPSHOT_ASSISTED_DRIFT
```

A tail source contract violation means the snapshot-assisted path did not complete safely.

The validator may already have:

```text
snapshot boundary state
authority state
```

but if tail replay cannot safely advance, the system does not have completed drift evidence.

Therefore the semantic result is:

```text
RUNTIME_UNRESOLVED
```

not:

```text
DRIFT_DETECTED
```

Drift requires a completed comparison:

```text
completed snapshot-assisted state
vs
authority_state
```

## Resolver vs Validator Boundary

PR4 distinguishes:

```text
ProjectionSnapshotReplayValidator
= full authority replay validator
```

from:

```text
ProjectionSnapshotAssistedStateResolver
= snapshot-assisted resolver / fast-path reconstruction primitive
```

The validator may expose:

```text
authority_state
snapshot_assisted_state
```

The resolver exposes:

```text
resolved_state
```

because it does not perform full accepted-history replay.

PR4 tests preserve this difference through evidence flags such as:

```text
authority_state_present
snapshot_assisted_state_present
resolved_state_present
```

## Reason Fallback Boundary

PR4 preserves result reasons when present.

If a result reason is missing or blank, the adapter records the result source type:

```text
Missing explicit reason from ReplayValidationResult.
Missing explicit reason from ProjectionSnapshotReplayValidationResult.
Missing explicit reason from ProjectionSnapshotAssistedResolutionResult.
```

This prevents blank reasons from being normalized into a source-less generic message.

## Deferred Projection Worker Mapping

PR4 intentionally does not include ordinary projection worker execution mapping.

Projection validation answers:

```text
Does derived read-side state match accepted-history authority?
```

Projection worker execution answers:

```text
Is the projection runtime currently processing accepted events successfully and freshly?
```

These are related, but they are not the same.

```text
projection worker failure ≠ projection drift
projection lag ≠ semantic corruption
projection freshness ≠ accepted-history authority
```

Projection worker freshness evidence belongs to Stage 5+ / later dual-dimension governance, where action safety may require both:

```text
semantic correctness
×
operational freshness / runtime trust
```

## Non-goals

PR4 does not implement:

```text
write-side admission rejection adapter
root-cause inference
ProjectionWorker execution mapping
projection delivery log
projection inbox
worker governance
runtime action selection
fallback execution
rebuild orchestration
quarantine mechanism
DecisionReceipt
DiagnosticTrace
Measurement Matrix
RuntimeDecisionPolicy
StrategySelector
RetryGovernance
SQL migrations
durable receipt store
```

## Relationship to PR5

PR5 should add the explicit write-side line:

```text
Layer 1 write-side admission rejection
→ SemanticOutcome
```

PR5 should not retroactively change PR4 read-side or snapshot outcomes into Layer 1 outcomes.

The intended relationship is:

```text
PR4:
read-side / snapshot observation
→ SemanticOutcome

PR5:
write-side admission rejection
→ SemanticOutcome
```

Later receipt and trace layers may correlate PR4 observations with PR5 write-side causes.

Stage 4A itself should not perform root-cause inference.

---

# PR5 — Write-Side Admission Outcome Mapping

## Goal

Map concrete write-side admission and orchestration results into `SemanticOutcome` without changing Layer 1 admission behavior.

PR5 adds the explicit line:

```text
Layer 1 write-side admission / orchestration evidence
→ SemanticOutcome
```

This makes write-side acceptance, replay, rejection, validation block, concurrency uncertainty, and infrastructure abnormality machine-readable without allowing rejected candidates to enter accepted history.

## Status

Implemented by:

```text
feat/stage4a-pr5-write-side-admission-outcome-mapping
```

## Scope

PR5 adds:

```text
src/compass/runtime/write_side_outcome_mapping.py
tests/unit/compass/runtime/test_write_side_outcome_mapping.py
docs/implementation_notes/stage_4a/write_side_admission_outcome_mapping.md
docs/implementation_notes/stage_4a/pr5_closeout.md
```

PR5 updates:

```text
src/compass/runtime/__init__.py
src/compass/runtime/technical_status_mapping.py
tests/unit/compass/runtime/test_technical_status_mapping.py
docs/implementation_notes/stage_4a/README.md
docs/implementation_notes/stage_4a/pr_breakdown.md
```

## Concrete Adapter Boundary

PR5 introduces two write-side adapter functions:

```text
map_write_side_admission_status_to_semantic_outcome(...)
map_postgres_write_side_result_to_semantic_outcome(...)
```

The first adapter pins generic write-side technical status mapping to:

```text
SemanticBoundary.LAYER_1_WRITE_SIDE
```

The second adapter maps:

```text
PostgresWriteSideResult
→ write-side technical status
→ SemanticOutcome
```

## Mapped Write-Side Result Shape

PR5 maps `PostgresWriteSideOutcome` values as follows:

```text
ACCEPTED
→ WRITE_SIDE_ACCEPTED
→ SEMANTICALLY_VALID

REPLAY
→ IDEMPOTENT_REPLAY
→ IDEMPOTENT_REPLAY_ALLOWED

CONFLICT
→ IDEMPOTENCY_CONFLICT
→ SEMANTIC_CONFLICT_DETECTED

VALIDATION_BLOCKED
→ COMPASS_VALIDATION_BLOCKED
→ SEMANTIC_CONFLICT_DETECTED

ADMISSION_REJECTED + STALE_WRITE
→ CONCURRENT_STATE_STALENESS
→ CONCURRENCY_UNCERTAIN

ADMISSION_REJECTED + LOCK_TIMEOUT
→ LOCK_TIMEOUT
→ CONCURRENCY_UNCERTAIN

ADMISSION_REJECTED + INFRASTRUCTURE_ERROR
→ WRITE_SIDE_INFRASTRUCTURE_ERROR
→ REQUIRES_OPERATOR_REVIEW
```

`OCC_CONFLICT_AFTER_VALIDATION` remains supported as a generic technical status from PR3, but PR5 maps the write-side admission verdict `STALE_WRITE` to the more storage-neutral `CONCURRENT_STATE_STALENESS`.

## Identity Lineage Hardening

PR5 treats write-side identity fields as protected context:

```text
write_side_outcome
order_id
request_id
candidate_event_id
accepted_event_id
```

Caller-provided context may enrich the outcome, but it must not contradict adapter-derived protected context.

PR5 also rejects contradictory identity evidence inside the write-side result itself.

For example, if multiple write-side evidence sources produce different `order_id` or `request_id` values, the adapter refuses to produce a `SemanticOutcome` instead of silently choosing one source.

This protects later Stage 4B / Stage 4C layers from building receipts, traces, or decisions on ambiguous identity lineage.

## Accepted Event Boundary

PR5 preserves the boundary:

```text
accepted_event_id
exists only for accepted history or replay of a prior accepted event
```

A rejected append-time admission result must not carry `accepted_event_id`.

An idempotency conflict may expose a prior `accepted_event_id` from the stored idempotency record, but that identifier belongs to the previous accepted result, not to the current rejected candidate.

## Infrastructure Error Boundary

PR5 deliberately maps write-side infrastructure failure to:

```text
ESCALATION_REQUIRED
REQUIRES_OPERATOR_REVIEW
```

rather than ordinary:

```text
UNRESOLVED
RUNTIME_UNRESOLVED
```

This does not execute operator review or fail-closed policy.

It only preserves the semantic distinction that write-side infrastructure abnormality occurs near the accepted-history admission path and should not be treated as a generic retry-friendly unresolved observation by later governance layers.

## ValidationResult Identity Checkpoint

PR5 does not change `ValidationResult`.

`ValidationResult` currently provides formal validation evidence such as:

```text
candidate_event_id
validator_name
validation_mode
reason
timing fields
metadata
```

It does not provide first-class `order_id` or `request_id`.

For PR5, this is acceptable because write-side mapping obtains core `order_id` evidence from outer write-side orchestration sources such as accepted events, stream admission results, and idempotency records.

`ValidationResult.metadata["order_id"]` must not be treated as authoritative identity evidence unless it is later promoted into the schema-level contract.

This is recorded as a Stage 4B design checkpoint.

## Non-goals

PR5 does not implement:

```text
rejected candidate table
admission_rejection_records
candidate_attempts table
rejected_event_log
DecisionReceipt persistence
DiagnosticTrace
Measurement Matrix
RuntimeDecisionPolicy
StrategySelector
RetryGovernance
agent policy decision
automatic retry blocking
strategy selection
accepted history changes
Layer 1 validator rewrite
ValidationResult schema changes
```

## Relationship to PR6

After PR5, PR6 should close Stage 4A by aligning stage-level documentation, final follow-up notes, and any remaining cleanup before Stage 4B begins.

---

# PR6 — Stage 4A Closeout

## Goal

Close Stage 4A by aligning documentation, exports, tests, and follow-up notes.

PR6 should confirm that Stage 4A has a coherent SemanticOutcome core before Stage 4B begins.

## Status

Planned after PR5.

## Scope

PR6 may include:

```text
Stage 4A README alignment
PR breakdown closeout
follow-up notes for Stage 4B / 4C / 4D / 4E
cleanup of temporary wording
final test run notes
```

## Non-goals

PR6 should not introduce new runtime governance features.

It should close the stage, not expand it.
