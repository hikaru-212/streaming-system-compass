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

Commit subjects should remain short and consistent with the existing history:

```text
type(scope): concise change
```

A longer commit body is optional and should be used selectively when the commit
introduces or hardens an important runtime contract, identity rule,
transaction boundary, or fail-closed invariant. Small wording-only, navigation,
or closeout commits should normally keep a short subject and no extended body.

Recommended pattern:

```text
small wording / documentation alignment
→ short subject only

core production contract + focused tests
→ short subject + explanatory body when useful

closeout documentation
→ short subject, with body only when the closeout records material deferrals
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
Interlude — Read-Side Canonical Context Protection
PR3 — SemanticOutcome to DecisionReceipt Adapter
Interlude — DecisionReceipt Flag Evaluation State
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

Complete.

Recommended branch:

```text
feat/stage4b-pr1-decision-receipt-boundary
```

## Scope

PR1 adds or updates:

```text
docs/adr/0016_decision_receipt_is_governance_evidence.md
docs/adr/README.md
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

Complete.

## Scope

PR2 adds or updates:

```text
src/compass/runtime/json_types.py
src/compass/runtime/decision_receipt.py
src/compass/runtime/semantic_outcome.py
tests/unit/compass/runtime/test_decision_receipt.py
tests/unit/compass/runtime/test_semantic_outcome.py
docs/implementation_notes/stage_4b/decision_receipt_contract.md
docs/implementation_notes/stage_4b/
  decision_receipt_evidence_source_alignment_note.md
docs/adr/0017_separate_evidence_path_identity_provenance_and_admission_fate.md
docs/postmortems/
  stage_4b_semantic_level_mismatch_in_ai_assisted_runtime_contract.md
```

The `semantic_outcome.py` change is narrow primitive hardening and does not
reopen Stage 4A mapping scope.

PR2 may introduce:

```text
JsonValue
JsonObject
DecisionReceipt
DecisionReceiptEvidenceSource
DecisionReceiptSubject
DecisionReceiptCorrelation
DecisionReceiptIdentitySource
DecisionReceiptAdmissionEvidence
EventAdmissionDisposition
DecisionReceiptActor
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

# Interlude — Read-Side Canonical Context Protection

## Goal

Prevent caller-provided context from contradicting adapter-derived canonical
read-side identity and lineage context before PR3 converts `SemanticOutcome`
values into durable `DecisionReceipt` evidence.

## Status

Complete.

## Scope

The Interlude updates:

```text
src/compass/runtime/read_side_outcome_mapping.py
tests/unit/compass/runtime/test_read_side_outcome_mapping.py
docs/implementation_notes/stage_4b/pr_breakdown.md
docs/implementation_notes/stage_4b/README.md
```

The read-side adapters now preserve this rule:

```text
caller-provided context
may add non-canonical context

caller-provided context
must not contradict adapter-derived canonical context
```

Canonical context remains producer-owned.

Current protected context is supplied separately by each concrete adapter:

```text
ReplayValidationResult
→ order_id

ProjectionSnapshotReplayValidationResult
→ order_id
→ snapshot_id
→ source_global_position

ProjectionSnapshotAssistedResolutionResult
→ order_id
→ snapshot_id
→ source_global_position
```

The Interlude does not:

```text
change SemanticOutcome evidence merging
add DecisionReceipt mapping
select receipt subjects or correlations
map receipt flags
map admission disposition
serialize or persist receipts
refactor the Stage 4A mapping framework
```

---

# PR3 — SemanticOutcome to DecisionReceipt Adapter

## Goal

Introduce a thin generic adapter that constructs `DecisionReceipt` from an
existing `SemanticOutcome` without reinterpreting semantic meaning or inferring
producer-specific authority.

The intended relationship is:

```text
SemanticOutcome
+ explicit receipt identity
+ explicit evidence path
+ explicit supporting receipt evidence
→ DecisionReceipt
```

PR3 establishes a receipt-construction boundary.

It does not establish write-side, read-side, snapshot, persistence, policy,
strategy, or retry behavior.

## Status

Complete.

Recommended branch:

```text
feat/stage4b-pr3-outcome-to-receipt-adapter
```

## Completed Scope

PR3 adds or updates:

```text
src/compass/runtime/decision_receipt_mapping.py
tests/unit/compass/runtime/test_decision_receipt_mapping.py
src/compass/runtime/__init__.py
docs/implementation_notes/stage_4b/
  semantic_outcome_to_decision_receipt.md
docs/implementation_notes/stage_4b/pr_breakdown.md
docs/implementation_notes/stage_4b/README.md
```

The production module introduces only:

```text
map_semantic_outcome_to_decision_receipt
```

The implementation remains a thin generic constructor adapter.

## Required Semantic Preservation

The generic adapter must preserve the existing `SemanticOutcome` tuple exactly:

```text
outcome_id
ok
boundary
category
semantic_code
severity
risk_level
reversibility
reason
```

PR3 must not perform a second semantic interpretation.

```text
SemanticOutcome → DecisionReceipt
= semantic preservation

SemanticOutcome → DecisionReceipt
≠ semantic remapping
```

## Explicit Inputs

The generic adapter should require explicit:

```text
receipt_id
outcome
evidence_source
```

It may accept the existing receipt supporting contracts explicitly:

```text
subject
correlation
actor
cost_summary
flags
admission_evidence
evidence_summary
metadata
```

When optional supporting contracts are omitted, the adapter should preserve the
current `DecisionReceipt` defaults.

## Receipt-Safe Evidence Boundary

Important boundary:

```text
SemanticOutcome.context / evidence
≠ automatically receipt-safe evidence
```

The generic adapter must not inspect, flatten, namespace, allowlist, convert, or
wholesale-copy `SemanticOutcome.context` or `SemanticOutcome.evidence`.

Only explicitly preselected:

```text
evidence_summary
metadata
```

may enter the receipt flexible evidence fields.

The existing `DecisionReceipt` JSON-safe boundary remains responsible for
rejecting unsupported values.

Identity and lineage evidence should use typed receipt fields whenever possible,
rather than being duplicated in flexible JSON.

## Ownership Boundary

PR3 owns:

```text
exact semantic tuple preservation
explicit receipt construction
existing DecisionReceipt default application
pass-through of explicitly supplied typed supporting contracts
JSON-safe validation through the DecisionReceipt contract
```

PR3 does not own:

```text
receipt_id generation
evidence_source inference
subject inference
correlation inference
identity-provenance inference
actor discovery
cost measurement
flag derivation
admission-disposition inference
producer-specific evidence selection
serialization
persistence
policy
strategy
retry authorization
```

`receipt_id` is supplied by caller / orchestration.

Concrete evidence-source, subject, correlation, identity, admission, and
producer-specific evidence choices belong to PR4 and PR5.

## Flags Boundary

PR3 should accept explicit `DecisionReceiptFlags`.

It should not derive flags from:

```text
ok
category
semantic_code
severity
risk_level
reversibility
boundary
technical_status
```

No complete authoritative `SemanticOutcome → DecisionReceiptFlags` mapping
currently exists.

When PR3 was initially completed, omitted flags used the then-current all-false
`DecisionReceiptFlags()` default. After the Flag Evaluation State Interlude,
omitted flags use the shared all-`NOT_EVALUATED` default.

This default means no flag evidence was supplied through this adapter. Future
consumers must not treat the default as proof that fallback, rebuild, operator
review, or retry relevance was fully evaluated and ruled out.

## Admission Evidence Boundary

PR3 may pass through explicitly supplied `DecisionReceiptAdmissionEvidence`.

It must not infer admission fate from:

```text
SemanticOutcome boundary
SemanticOutcome category
SemanticOutcome code
identifier presence
technical status
```

Concrete admission-disposition mapping belongs to PR4.

## Non-goals

PR3 does not implement:

```text
write-side evidence-source selection
write-side subject / correlation mapping
event-ID string-to-UUID conversion
write-side admission disposition mapping
idempotent replay receipt mapping
read-side evidence-source selection
snapshot evidence-source selection
snapshot subject / lineage mapping
producer-specific receipt evidence selection
automatic flag derivation
serialization
schema versioning
SQL migrations
PostgresDecisionReceiptStore
receipt query APIs
DiagnosticTrace
RuntimeDecisionPolicy
StrategySelector
RetryGovernance
automatic retry
automatic fallback
automatic rebuild
operator-review execution
```

## Validation Expectations

PR3 unit tests should cover:

```text
exact semantic tuple preservation
explicit receipt_id preservation
explicit evidence_source preservation
default supporting contracts
explicit supporting contracts
receipt-safe evidence acceptance
non-JSON-safe evidence rejection
no wholesale context copying
no wholesale evidence copying
no write-side admission inference
no read-side / snapshot path inference
no flag / policy / retry inference
no persistence behavior
```

---

# Interlude — DecisionReceipt Flag Evaluation State

## Goal

Stabilize the shared `DecisionReceiptFlags` evaluation-state contract before
PR4 and PR5 begin producing producer-specific receipt flags.

The pre-Interlude boolean fields were:

```text
fallback_required
rebuild_required
operator_review_required
retry_candidate
```

The prior default value `False` was ambiguous because it could mean:

```text
evaluated and explicitly false
not evaluated
not supplied
not applicable
incomplete flag evidence
```

The Interlude distinguishes explicit positive evidence, explicit negative
evidence, and absence of evaluation.

## Status

Complete.

Recommended branch:

```text
feat/stage4b-decision-receipt-flag-evaluation-state
```

## Completed Scope

The Interlude began with a read-only contract audit.

The completed scope includes:

```text
DecisionReceiptFlagState enum
DecisionReceiptFlags field migration
NOT_EVALUATED defaults
strict state validation
runtime package export
removal of boolean convenience properties
DecisionReceipt contract tests
PR3 mapper compatibility tests
```

The audit selected:

```text
TRUE
FALSE
NOT_EVALUATED
```

`FALSE` means evaluated and explicitly negated.

`NOT_EVALUATED` means the receipt contains no completed evaluation for the
condition. It is the default and must not be interpreted as `FALSE`.

No current producer, consumer, invariant, or test justifies
`NOT_APPLICABLE`. A new ADR is not required for this narrow refinement of the
existing DecisionReceipt evidence contract.

The complete ownership, consumer, retry, portability, and migration decision is
recorded in:

```text
decision_receipt_flag_evaluation_state.md
```

## Boundary

The Interlude owns the shared:

```text
DecisionReceiptFlags contract
```

It does not belong only to the PR3 mapper.

PR3 correctly performs:

```text
explicit flags supplied
→ pass through

flags omitted
→ use the shared all-NOT_EVALUATED default
```

The ambiguity must not be fixed only in PR3 because direct
`DecisionReceipt` construction and later specialized adapters must share one
flag interpretation.

## Timing

The Interlude completed before:

```text
PR4 — Write-Side Admission DecisionReceipt Mapping
PR5 — Read-Side Snapshot DecisionReceipt Mapping
PR6 — DecisionReceipt Durable Persistence
```

PR4 and PR5 will be the first producer-specific flag evidence producers.

PR6 must not persist `False` where the true meaning was not evaluated or not
provided.

## Non-goals

The Interlude does not implement:

```text
write-side receipt mapping
read-side / snapshot receipt mapping
runtime policy
retry authorization
fallback execution
rebuild execution
operator-review execution
persistence schema
```

## Verification

Focused DecisionReceipt tests and the runtime unit suite passed. The full
repository suite was attempted, but PostgreSQL integration tests could not
start because `TEST_DATABASE_URL` was unavailable. The exact reviewed results
are recorded in `decision_receipt_flag_evaluation_state.md`.

The PR4 and PR5 producer-specific adapters are now implemented. Their
completed mappings preserve typed producer evidence, keep all governance flags
`NOT_EVALUATED`, and remain separate from persistence, trace, policy, strategy,
and retry work.

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

Complete.

Recommended branch:

```text
feat/stage4b-pr4-write-side-receipt-mapping
```

## Completed Scope

PR4 adds:

```text
src/compass/runtime/write_side_decision_receipt_mapping.py
tests/unit/compass/runtime/test_write_side_decision_receipt_mapping.py
docs/implementation_notes/stage_4b/write_side_decision_receipt_mapping.md
```

PR4 preserves the Stage 4A semantic tuple and selects producer-owned:

```text
evidence source
subject
order / request / candidate / accepted-event correlation
primary identity provenance
current-attempt admission disposition
compact evidence summary
all-NOT_EVALUATED governance flags
```

It carries forward the Stage 4A write-side identity hardening:

```text
write_side_outcome
order_id
request_id
candidate_event_id
accepted_event_id
```

PR4 does not implement runtime invocation, persistence, policy, strategy,
retry authorization, or action execution.

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

Complete.

Recommended branch:

```text
feat/stage4b-pr5-read-side-snapshot-receipt-mapping
```

## Completed Scope

PR5 adds:

```text
src/compass/runtime/read_side_decision_receipt_mapping.py
tests/unit/compass/runtime/test_read_side_decision_receipt_mapping.py
docs/implementation_notes/stage_4b/read_side_snapshot_decision_receipt_mapping.md
```

PR5 maps all current statuses from:

```text
ReplayValidationResult
ProjectionSnapshotReplayValidationResult
ProjectionSnapshotAssistedResolutionResult
```

through the existing Stage 4A adapters and the PR3 generic receipt mapper.

It preserves:

```text
exact Stage 4A semantic tuples
producer-specific evidence paths
ORDER / PROJECTION / SNAPSHOT / RUNTIME subjects
READ_SIDE_OBSERVATION / SNAPSHOT_LINEAGE correlation provenance
compact state-presence and snapshot-artifact summaries
all-NOT_EVALUATED governance flags
```

Completed fail-closed hardening requires every present state to be an
`OrderState` for the same `order_id`, and requires a positive
`source_global_position` only for snapshot statuses reached after successful
producer boundary or compatibility validation. Invalid-boundary and
invalid-compatibility results may still preserve zero as rejected evidence.

Important boundary:

```text
observed boundary
≠
root cause claim
```

Deferred semantic precision remains outside PR5:

```text
NO_ACCEPTED_HISTORY + persisted projection
NO_ACCEPTED_HISTORY_FOR_ORDER + loaded snapshot lineage
SNAPSHOT_ASSISTED_DRIFT combining completed inequality and reducer failure
```

PR5 does not implement runtime invocation, persistence, continuous trust,
policy, action, retry, trace, or trust continuation.

Focused closeout verification:

```text
157 focused tests passed
74 PR5 tests collected
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
