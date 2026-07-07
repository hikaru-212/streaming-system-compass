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
OCC_CONFLICT_AFTER_VALIDATION
LOCK_TIMEOUT
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

Apply SemanticOutcome mapping to read-side correctness boundaries.

PR4 should connect SemanticOutcome to projection replay validation, snapshot-assisted replay validation, and snapshot-assisted resolution.

## Status

Planned after PR3.

## Scope

PR4 may include:

```text
projection drift outcome mapping
snapshot trust failure outcome mapping
snapshot fast-path unavailable mapping
resolver unresolved-state mapping
authority fallback required mapping
read-side tests asserting semantic outcomes
```

PR4 should preserve the existing authority model:

```text
accepted history = authority
projection = derived state
snapshot = derived compression
```

## Non-goals

PR4 does not make StrategySelector decisions.

It may say that authority fallback is semantically required.

It should not choose the cheapest authority fallback path.

---

# PR5 — Write-Side Admission Outcome Mapping

## Goal

Prepare write-side Compass Layer 1 outcomes to use compatible SemanticOutcome vocabulary.

PR5 should not rewrite Layer 1.

It should begin aligning the representation of write-side admission results with the runtime semantic outcome family.

PR5 should include the explicit line:

```text
Layer 1 write-side admission rejection
→ SemanticOutcome
```

This line should make Layer 1 rejection semantics machine-readable without allowing rejected candidates to enter accepted history.

## Status

Planned after read-side outcome mapping is stable.

## Scope

PR5 may include mappings for:

```text
domain transition violation
undefined event transition
domain invariant violation
missing required proof
proof-candidate mismatch
candidate payload invalid
candidate conflicts with accepted state
idempotent replay
idempotency conflict
OCC conflict after validation
concurrency uncertainty
Compass Layer 1 block
```

PR5 should preserve:

```text
accepted history = admitted facts only
rejected candidate = outside accepted history
Layer 1 protects accepted history
Stage 4A mapping explains why a candidate was rejected
```

## Non-goals

PR5 does not implement:

```text
rejected candidate table
admission_rejection_records
candidate_attempts table
rejected_event_log
durable receipt writing
retry governance
agent policy decision
automatic retry blocking
strategy selection
accepted history changes
Layer 1 validator rewrite
```

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
