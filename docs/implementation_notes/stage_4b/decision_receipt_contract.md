# DecisionReceipt Runtime Contract

[← Back to Stage 4B](README.md)

## Purpose

This note records the Stage 4B PR2 runtime contract for:

```text
DecisionReceipt
```

PR2 translates the Stage 4B boundary into a minimal code-level contract.

The contract preserves selected semantic governance evidence after Stage 4A has produced a `SemanticOutcome`.

---

## Core Relationship

```text
technical runtime evidence
→ SemanticOutcome
→ DecisionReceipt
```

Stage 4A answers:

```text
What does this technical runtime result mean semantically?
```

Stage 4B PR2 answers:

```text
What typed runtime contract can preserve selected evidence of that semantic meaning?
```

PR2 does not yet map `SemanticOutcome` into `DecisionReceipt`.

That belongs to Stage 4B PR3.

---

## Contract Shape

PR2 introduces:

```text
src/compass/runtime/json_types.py
src/compass/runtime/decision_receipt.py
tests/unit/compass/runtime/test_decision_receipt.py
```

The main contract is:

```text
DecisionReceipt
```

It contains:

```text
receipt_id
outcome_id
ok
boundary
category
semantic_code
severity
risk_level
reversibility
reason
evidence_source
subject
correlation
actor
cost_summary
flags
evidence_summary
metadata
```

The contract intentionally reuses Stage 4A semantic vocabulary:

```text
SemanticBoundary
SemanticOutcomeCategory
SemanticOutcomeCode
SemanticSeverity
SemanticRiskLevel
SemanticReversibility
```

This keeps `DecisionReceipt` anchored to the already-defined semantic meaning instead of inventing a second outcome vocabulary.

---

## JSON-Safe Evidence Boundary

PR2 introduces:

```text
JsonScalar
JsonValue
JsonObject
ensure_json_value
ensure_json_object
```

This reflects the Stage 4B portability rule:

```text
typed outer contract
+ JSON-safe flexible evidence
```

Receipt evidence may contain:

```text
str
int
finite float
bool
None
list / tuple of JSON-safe values
mapping with string keys and JSON-safe values
```

Receipt evidence must not contain:

```text
Python runtime objects
validator instances
database connections
callbacks
exception objects
UUID objects
Decimal values
datetime values
sets
arbitrary object instances
non-finite floats
```

If such information is useful, the caller must convert it into a stable JSON-safe representation first.

For example:

```text
UUID object
→ string identifier

Exception object
→ exception_type / exception_message

database connection
→ component name or connection role label
```

---

## Evidence Source

`DecisionReceiptEvidenceSource` records the evidence path that produced the receipt.

Initial values:

```text
RUNTIME_TECHNICAL_STATUS
READ_SIDE_REPLAY
SNAPSHOT_REPLAY
SNAPSHOT_ASSISTED_RESOLUTION
WRITE_SIDE_ADMISSION
UNKNOWN
```

This vocabulary records where receipt evidence came from.

It does not execute recovery, choose strategy, or authorize retry.

---

## Subject

`DecisionReceiptSubject` identifies what the receipt is about.

It contains:

```text
subject_type
subject_id
```

Initial subject types:

```text
ORDER
REQUEST
CANDIDATE_EVENT
ACCEPTED_EVENT
SNAPSHOT
RUNTIME_OBSERVATION
UNKNOWN
```

Detailed identity lineage belongs in `DecisionReceiptCorrelation`.

---

## Correlation and Identity Lineage

`DecisionReceiptCorrelation` stores receipt-safe identity and lineage evidence:

```text
order_id
request_id
candidate_event_id
accepted_event_id
snapshot_id
source_global_position
identity_source
```

Initial identity sources:

```text
ACCEPTED_HISTORY
PRE_ADMISSION_CANDIDATE
WRITE_SIDE_ORCHESTRATION
READ_SIDE_OBSERVATION
SNAPSHOT_LINEAGE
CALLER_CONTEXT
UNKNOWN
```

The important rule is:

```text
correlation evidence
≠
accepted-history authority
```

For example:

```text
order_id from candidate_event
= pre-admission candidate identity

order_id from accepted_event
= accepted-history identity
```

PR2 only provides the contract for preserving this distinction.

PR3 and later adapter PRs decide how concrete runtime evidence maps into this contract.

---

## Actor Evidence

`DecisionReceiptActor` records optional actor metadata:

```text
actor_id
actor_role
runtime_role
```

Actor metadata is evidence.

It is not database role authority.

It is not runtime policy approval.

---

## Cost Summary

`DecisionReceiptCostSummary` records compact cost evidence:

```text
elapsed_ms
validation_elapsed_ms
replay_elapsed_ms
transaction_elapsed_ms
lock_wait_ms
```

PR2 does not implement Measurement Matrix, benchmark suites, LLM token accounting, routing policy, or cost dashboards.

Those belong to later stages.

---

## Flags

`DecisionReceiptFlags` records governance evidence flags:

```text
fallback_required
rebuild_required
operator_review_required
retry_candidate
```

These flags are evidence only.

They do not execute fallback.

They do not rebuild projections.

They do not perform operator review.

They do not authorize retry.

Runtime decisions belong to later policy layers.

---

## Non-goals

PR2 does not implement:

```text
SemanticOutcome → DecisionReceipt mapping
write-side receipt mapping
read-side / snapshot receipt mapping
SQL persistence
PostgresDecisionReceiptStore
DiagnosticTrace
ResolutionTrace
Measurement Matrix
Order Domain Policy Contract
RuntimeDecisionPolicy
StrategySelector
RetryGovernance
operator review execution
fallback execution
rebuild orchestration
quarantine mechanism
```

---

## Test Coverage

PR2 tests cover:

```text
required semantic summary fields
default optional receipt sections
frozen dataclass behavior
JSON-safe evidence acceptance
non-JSON-safe evidence rejection
non-finite float rejection
string-key JSON object enforcement
correlation identity source classification
invalid identity field rejection
non-negative cost fields
boolean governance flags
absence of runtime action / strategy / retry fields
stable enum member sets
```

---

## Next PR

Stage 4B PR3 should add:

```text
SemanticOutcome → DecisionReceipt adapter
```

PR3 should decide which parts of `SemanticOutcome.context` and `SemanticOutcome.evidence` are receipt-safe.

It should not blindly copy arbitrary context or evidence into durable governance evidence.
