# Stage 4B PR Breakdown

[← Back to Stage 4B](README.md)

## Purpose

This note proposes the implementation sequence for:

```text
Stage 4B — DecisionReceipt / Runtime Evidence Record
```

Stage 4B builds on Stage 4A.

Stage 4A turned technical runtime evidence into `SemanticOutcome`.

Stage 4B should turn selected `SemanticOutcome` values into compact, durable, reviewable runtime governance evidence.

It should not collapse receipts, diagnostic traces, measurement, policy, strategy, and retry governance into one layer.

---

## Stage Principle

```text
technical evidence
→ semantic interpretation
→ durable evidence
→ diagnostic trace when needed
→ cost evidence vocabulary
→ policy-linked recovery
→ runtime decision
→ strategy selection
→ retry governance
```

For Stage 4B specifically:

```text
SemanticOutcome
→ DecisionReceipt
→ future governance evidence
```

This means:

```text
SemanticOutcome
should not be treated as a durable receipt

DecisionReceipt
should not be treated as a diagnostic trace

DecisionReceipt
should not be treated as a runtime decision

DecisionReceipt
should not execute recovery

DecisionReceipt
should not select strategy

DecisionReceipt
should not govern retry attempts
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
= one integration branch for a coherent Stage 4 sub-stage such as Stage 4B

one PRx branch
= one coherent semantic delivery unit inside the sub-stage

one PRx branch may contain multiple commits
= each commit preserves a smaller documentation, schema, code, or test boundary
```

For Stage 4, the integration branch is:

```text
feat/stage4-runtime-semantic-governance
```

Recommended Stage 4B sub-stage branch name:

```text
feat/stage4b-decision-receipt-runtime-evidence
```

If the existing Stage 4B branch is still named:

```text
feat/stage4b-decision-receipt-diagnostic-trace
```

it may still be used, but the cleaner conceptual name is `decision-receipt-runtime-evidence` because DiagnosticTrace is deferred to Stage 4B.1.

Individual PR branches should be created from the current Stage 4B sub-stage branch:

```text
feat/stage4b-pr1-decision-receipt-boundary
feat/stage4b-pr2-decision-receipt-contract
feat/stage4b-pr3-outcome-to-receipt-adapter
feat/stage4b-pr4-write-side-receipt-mapping
feat/stage4b-pr5-read-side-snapshot-receipt-mapping
feat/stage4b-pr6-decision-receipt-persistence
feat/stage4b-pr7-closeout
```

Each Stage 4B PR branch should be merged back into the Stage 4B sub-stage branch.

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

For example, Stage 4B PR1 may contain:

```text
docs: add ADR for DecisionReceipt governance evidence
docs: define Stage 4B DecisionReceipt boundary
```

These commits may belong to the same PR if they serve the same PR-level semantic goal.

---

## Documentation-First Implementation Pattern

When a PR introduces a new semantic or infrastructure boundary, the preferred order is:

```text
1. define the boundary in documentation
2. implement the minimum mechanism
3. add or defer tests according to the PR scope
4. align README / roadmap / breakdown notes if needed
```

Stage 4B PR1 follows this pattern.

It should define the DecisionReceipt boundary before code introduces a runtime contract.

---

## Proposed Stage 4B PR Sequence

```text
PR1 — DecisionReceipt / Runtime Evidence Boundary
PR2 — DecisionReceipt Runtime Contract
PR3 — SemanticOutcome to DecisionReceipt Adapter
PR4 — Write-Side Admission DecisionReceipt Mapping
PR5 — Read-Side Snapshot DecisionReceipt Mapping
PR6 — DecisionReceipt Durable Persistence
PR7 — Stage 4B Closeout
```

After PR7, Stage 4B should provide a stable DecisionReceipt evidence layer for later DiagnosticTrace, Measurement Matrix, Policy Contract, RuntimeDecisionPolicy, StrategySelector, and RetryGovernance work.

---

# PR1 — DecisionReceipt / Runtime Evidence Boundary

## Goal

Define the Stage 4B boundary before implementation begins.

PR1 establishes why `DecisionReceipt` exists and how it differs from ordinary logs, `SemanticOutcome`, `DiagnosticTrace`, `AttemptLog`, `RuntimeDecisionPolicy`, strategy selection, and retry governance.

## Status

Planned.

Recommended branch:

```text
feat/stage4b-pr1-decision-receipt-boundary
```

## Scope

PR1 adds or updates:

```text
docs/adrs/0016_decision_receipt_is_governance_evidence.md
docs/adrs/README.md
docs/boundary_notes/README.md
docs/boundary_notes/decision_receipt_boundary.md
docs/implementation_notes/README.md
docs/implementation_notes/stage_4b/README.md
docs/implementation_notes/stage_4b/pr_breakdown.md
docs/implementation_notes/stage_4b/decision_receipt_boundary.md
```

PR1 clarifies:

```text
why Stage 4B exists
why DecisionReceipt is governance evidence, not application logging
why SemanticOutcome is not yet durable evidence
why DecisionReceipt should preserve summary evidence only
why DiagnosticTrace is deferred to Stage 4B.1
why Measurement Matrix is deferred to Stage 4B.2
why Order Domain Policy Contract is deferred to Stage 4B.5
why RuntimeDecisionPolicy is deferred to Stage 4C
why StrategySelector is deferred to Stage 4D
why RetryGovernance is deferred to Stage 4E
which evidence is receipt-safe
which evidence is trace-only
which evidence is non-authoritative
which identity lineage rules must carry over from Stage 4A PR5
which Java / Rust portability rules apply to new Stage 4B contracts
```

## Java / Rust Portability Rule

PR1 should document the Stage 4B portability constraint:

```text
DecisionReceipt is a future-portable runtime evidence contract.
Stable fields should be explicit and typed.
Flexible evidence should remain JSON-safe.
Do not store Python runtime objects, database connections, validator instances, callbacks, exception objects, or arbitrary dict[str, Any] inside receipt evidence.
```

This rule applies to new Stage 4B contracts.

It should not trigger a retroactive refactor of stable earlier code.

## Non-goals

PR1 does not add:

```text
production code
unit tests
SQL migrations
DecisionReceipt runtime contract
DecisionReceipt mapper
PostgresDecisionReceiptStore
DiagnosticTrace
Measurement Matrix
policy contract YAML
RuntimeDecisionPolicy
StrategySelector
RetryGovernance
benchmark suite
LLM token accounting
model routing policy
Stage 5 action safety gate
```

---

# PR2 — DecisionReceipt Runtime Contract

## Goal

Introduce the minimal in-code runtime evidence contract for `DecisionReceipt`.

PR2 translates the Stage 4B boundary into a small code-level contract.

## Status

Planned.

Recommended branch:

```text
feat/stage4b-pr2-decision-receipt-contract
```

## Scope

PR2 may add:

```text
src/compass/runtime/json_types.py
src/compass/runtime/decision_receipt.py
tests/unit/compass/runtime/test_decision_receipt.py
docs/implementation_notes/stage_4b/decision_receipt_contract.md
```

PR2 may introduce:

```text
JsonValue
JsonObject
DecisionReceipt
DecisionReceiptEvidenceSource
DecisionReceiptSubject
DecisionReceiptCorrelation
DecisionReceiptActor
DecisionReceiptEvidenceSummary
DecisionReceiptCostSummary
DecisionReceiptFlags
```

## Important Boundary

PR2 defines the receipt contract only.

It does not yet implement:

```text
SemanticOutcome → DecisionReceipt mapping
write-side receipt mapping
read-side / snapshot receipt mapping
SQL persistence
DiagnosticTrace
RuntimeDecisionPolicy
```

---

# PR3 — SemanticOutcome to DecisionReceipt Adapter

## Goal

Map `SemanticOutcome` into `DecisionReceipt` through a receipt-safe evidence boundary.

The adapter should preserve semantic summary while preventing arbitrary context / evidence from becoming durable governance evidence.

## Status

Planned.

Recommended branch:

```text
feat/stage4b-pr3-outcome-to-receipt-adapter
```

## Scope

PR3 may add:

```text
src/compass/runtime/decision_receipt_mapping.py
tests/unit/compass/runtime/test_decision_receipt_mapping.py
docs/implementation_notes/stage_4b/semantic_outcome_to_decision_receipt.md
```

Important boundary:

```text
SemanticOutcome.context / evidence
≠
automatically receipt-safe evidence
```

---

# PR4 — Write-Side Admission DecisionReceipt Mapping

## Goal

Map concrete write-side admission and orchestration outcomes into `DecisionReceipt` through the existing Stage 4A write-side `SemanticOutcome` adapter.

The intended path is:

```text
PostgresWriteSideResult
→ SemanticOutcome
→ DecisionReceipt
```

## Status

Planned.

Recommended branch:

```text
feat/stage4b-pr4-write-side-receipt-mapping
```

## Scope

PR4 may add:

```text
src/compass/runtime/write_side_decision_receipt_mapping.py
tests/unit/compass/runtime/test_write_side_decision_receipt_mapping.py
docs/implementation_notes/stage_4b/write_side_decision_receipt_mapping.md
```

PR4 should carry over Stage 4A PR5 identity hardening:

```text
write_side_outcome
order_id
request_id
candidate_event_id
accepted_event_id
```

---

# PR5 — Read-Side Snapshot DecisionReceipt Mapping

## Goal

Map read-side and snapshot-trust outcomes into `DecisionReceipt` through existing Stage 4A read-side `SemanticOutcome` adapters.

The intended path is:

```text
ReplayValidationResult
ProjectionSnapshotReplayValidationResult
ProjectionSnapshotAssistedResolutionResult
→ SemanticOutcome
→ DecisionReceipt
```

## Status

Planned.

Recommended branch:

```text
feat/stage4b-pr5-read-side-snapshot-receipt-mapping
```

## Scope

PR5 may add:

```text
src/compass/runtime/read_side_decision_receipt_mapping.py
tests/unit/compass/runtime/test_read_side_decision_receipt_mapping.py
docs/implementation_notes/stage_4b/read_side_snapshot_decision_receipt_mapping.md
```

Important boundary:

```text
observed boundary
≠
root cause claim
```

---

# PR6 — DecisionReceipt Durable Persistence

## Goal

Persist `DecisionReceipt` as durable runtime governance evidence after the receipt contract and mapping shape have stabilized.

PR6 turns the in-code receipt layer into a queryable persistence boundary without collapsing receipts into generic application logs, diagnostic traces, retry attempt logs, or runtime policy decisions.

## Status

Planned.

Recommended branch:

```text
feat/stage4b-pr6-decision-receipt-persistence
```

## Scope

PR6 may add:

```text
migrations/00x_create_decision_receipts.sql
src/storage/postgres_decision_receipt_store.py
tests/integration/storage/test_postgres_decision_receipt_store.py
docs/implementation_notes/stage_4b/decision_receipt_persistence.md
```

PR6 should clarify:

```text
DecisionReceipt persistence is not generic logging.
DecisionReceipt persistence is not DiagnosticTrace storage.
DecisionReceipt persistence is not AttemptLog storage.
DecisionReceipt persistence is not RuntimeDecisionPolicy storage.
```

The persistence shape should follow the Stage 4B evidence boundary:

```text
stable identity / correlation fields
→ explicit first-class columns where useful for query and review

flexible summary evidence
→ JSON-safe evidence_summary / cost_summary / metadata_json

full diagnostic path detail
→ deferred to DiagnosticTrace / ResolutionTrace, not stored inside decision_receipts

retry attempt sequence
→ deferred to AttemptLog / RetryGovernance, not stored inside decision_receipts
```

PR6 may introduce a durable receipt table only after PR2–PR5 stabilize the receipt contract and mapping evidence shape.

---

# PR7 — Stage 4B Closeout

## Goal

Close Stage 4B by aligning documentation, exports, tests, roadmap notes, and follow-up checkpoints.

PR7 confirms that Stage 4B has a coherent DecisionReceipt runtime evidence layer before Stage 4B.1 / 4B.2 / 4B.5 begins.

## Status

Planned.

Recommended branch:

```text
feat/stage4b-pr7-closeout
```

## Scope

PR7 may add:

```text
docs/implementation_notes/stage_4b/stage_4b_closeout.md
```

Closeout should confirm:

```text
DecisionReceipt boundary
DecisionReceipt runtime contract
SemanticOutcome → DecisionReceipt mapping
write-side receipt mapping
read-side / snapshot receipt mapping
DecisionReceipt durable persistence
Stage 4B closeout notes
```

Closeout should also confirm that detailed traces, measurement matrix, domain policy contract, runtime decisions, strategy selection, and retry governance remain deferred to later Stage 4 follow-up stages.
