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
feat/stage4a-pr3-technical-status-mapping
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
docs: add stage 4 implementation notes baseline
docs: define runtime semantic outcome boundary
docs: align stage 4 roadmap with semantic outcome boundary
```

These commits may all belong to the same PR if they serve the same PR-level semantic goal.

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

Planned.

## Scope

PR1 should add:

```text
docs/implementation_notes/stage_4a/README.md
docs/implementation_notes/stage_4a/pr_breakdown.md
docs/implementation_notes/stage_4a/semantic_outcome_boundary.md
docs/boundary_notes/runtime_semantic_outcome_boundary.md
```

PR1 should clarify:

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

Map existing runtime technical statuses into SemanticOutcome.

PR3 begins converting raw validator / resolver outputs into structured semantic interpretation.

## Status

Planned after PR2.

## Scope

PR3 may include mappings from existing technical statuses such as:

```text
MATCH
MISSING_SNAPSHOT
NO_ACCEPTED_HISTORY_FOR_ORDER
INVALID_SNAPSHOT_BOUNDARY
SNAPSHOT_ASSISTED_DRIFT
RESOLVED_FROM_SNAPSHOT
INVALID_SNAPSHOT_PRECONDITION
INVALID_SNAPSHOT_COMPATIBILITY
TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
TAIL_REPLAY_FAILED
```

into semantic outcomes such as:

```text
SEMANTICALLY_VALID
RUNTIME_UNRESOLVED
DERIVED_STATE_UNTRUSTED
DRIFT_DETECTED
FAST_PATH_UNAVAILABLE
REQUIRES_AUTHORITY_FALLBACK
REQUIRES_REBUILD
REQUIRES_OPERATOR_REVIEW
REJECT_DOWNSTREAM_USAGE
```

The mapping should preserve context and evidence without making policy decisions.

PR3 must also preserve the distinction between semantic drift and fast-path failure.
In particular, `TAIL_REPLAY_FAILED` should not automatically imply snapshot corruption.
A tail replay failure means the current resolution path failed or became unavailable.
It should usually map toward fast-path unavailability, unresolved runtime state, or authority fallback.

By contrast, `SNAPSHOT_ASSISTED_DRIFT` means snapshot-assisted reconstruction diverged from what accepted history implies.
That is a semantic drift signal and may require rebuild, quarantine, or operator review in later stages.

This distinction prevents Stage 4A from collapsing infrastructure / replay-path failure into semantic corruption.

## Non-goals

PR3 does not implement:

```text
runtime action selection
fallback execution
rebuild orchestration
quarantine mechanism
receipt persistence
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

## Status

Planned after read-side outcome mapping is stable.

## Scope

PR5 may include mappings for:

```text
domain transition violation
idempotent replay
idempotency conflict
OCC conflict after validation
concurrency uncertainty
Compass Layer 1 block
```

The goal is compatibility, not replacement.

Layer 1 still protects:

```text
candidate event
→ accepted history
```

Layer 2 protects:

```text
accepted history
→ derived runtime state / runtime interpretation
```

## Non-goals

PR5 does not implement the full Stage 4C.5 alignment.

It should only prepare compatible vocabulary where straightforward.

---

# PR6 — Stage 4A Closeout

## Goal

Close Stage 4A after SemanticOutcome has a stable boundary, vocabulary, and initial mappings.

PR6 should update documentation and confirm that later Stage 4 stages can safely build on SemanticOutcome.

## Status

Planned.

## Scope

PR6 may include:

```text
README alignment
roadmap alignment
Stage 4A closeout notes
summary of implemented outcome mappings
deferred items for Stage 4B / 4C / 4D / 4E
```

## Completion Criteria

Stage 4A is complete when:

```text
technical validator / resolver results can be mapped into SemanticOutcome
projection drift produces a structured SemanticOutcome
snapshot trust failure produces a structured SemanticOutcome
runtime unresolved states produce structured outcomes
idempotency / concurrency cases have compatible outcome vocabulary or explicit deferral
tests assert structured fields instead of exception strings
no runtime decision is made directly from raw technical status
```

---

## Later Stage 4 Sequence

After Stage 4A, later work may proceed as:

```text
Stage 4B — DecisionReceipt / Runtime Evidence Record
Stage 4B.1 — DiagnosticTrace / ResolutionTrace
Stage 4B.2 — Measurement Matrix / Cost Evidence Inventory
Stage 4B.5 — Order Domain Policy Contract v0
Stage 4C — RuntimeDecisionPolicy
Stage 4C.5 — Layer 1 / Layer 2 Outcome Alignment
Stage 4D — StrategySelector / Fast-Path Health Policy
Stage 4E — Retry Governance / Attempt Classification
```

Those stages should consume SemanticOutcome rather than bypass it.

