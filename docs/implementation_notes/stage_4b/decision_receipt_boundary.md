# DecisionReceipt Boundary

[← Back to Stage 4B](README.md)

## Purpose

This note defines the Stage 4B `DecisionReceipt` boundary.

Stage 4A introduced `SemanticOutcome`.

Stage 4B introduces `DecisionReceipt`.

The core relationship is:

```text
technical runtime evidence
→ SemanticOutcome
→ DecisionReceipt
```

Stage 4A answers:

```text
What does this technical result mean semantically?
```

Stage 4B answers:

```text
What summary evidence should be preserved so future governance can review, query, and act on that semantic meaning?
```

---

## Core Decision

A `DecisionReceipt` is:

```text
durable
compact
reviewable
machine-readable
policy-consumable
safe to reference later
```

A `DecisionReceipt` is not:

```text
application logging
generic error logging
full diagnostic tracing
retry attempt logging
runtime decision execution
strategy selection
observability event stream
metrics backend
```

This boundary is formalized by:

```text
ADR 0016 — DecisionReceipt Is Governance Evidence, Not Application Logging
```

---

## Why DecisionReceipt Exists

A runtime may produce many logs.

Most logs are not governance evidence.

For example:

```text
database timeout
validator exception
network failure
snapshot replay failure
lock timeout
```

may all be useful operational logs.

However, Stage 4B is interested in a narrower question:

```text
Has the runtime produced a structured semantic conclusion that future governance may need to inspect?
```

If yes, selected evidence may be preserved as a `DecisionReceipt`.

The goal is not to persist every error.

The goal is to persist selected semantic conclusions and the evidence that makes them safe to reference later.

---

## DecisionReceipt vs Application Logs

Application logs answer:

```text
What happened operationally?
```

DecisionReceipt answers:

```text
What semantic outcome was concluded,
from which evidence,
at which boundary,
for which identity / lineage,
and why is this conclusion safe to reference later?
```

Operational logs may remain in ELK, Loki, CloudWatch, local files, or another observability backend.

DecisionReceipt is not a replacement for those systems.

It is a durable runtime governance record.

---

## DecisionReceipt vs SemanticOutcome

`SemanticOutcome` describes semantic meaning.

`DecisionReceipt` preserves selected evidence of that meaning.

```text
SemanticOutcome
= semantic interpretation

DecisionReceipt
= durable governance evidence record for that interpretation
```

A `SemanticOutcome` may exist without a durable receipt.

A system that only needs immediate classification may stop at `SemanticOutcome`.

A system that needs auditability, reviewability, policy-linked recovery, later strategy selection, or retry governance should preserve receipts.

---

## DecisionReceipt vs DiagnosticTrace

`DecisionReceipt` stores summary-level governance evidence.

`DiagnosticTrace` stores detailed path evidence.

```text
DecisionReceipt
= compact summary evidence

DiagnosticTrace
= detailed failure path, partial progress, replay cursor, and debugging trace
```

Receipt-level evidence may include:

```text
semantic_code
boundary
evidence_source
identity lineage
snapshot identity
source global position
summary cost fields
flags such as fallback_required or operator_review_required
```

Trace-level evidence may include:

```text
validator step sequence
resolver step sequence
tail replay cursor
last successfully replayed global position
partial progress
failure stage
failure reason
fallback path details
internal adapter path
discarded evidence
```

Stage 4B should not implement the full DiagnosticTrace model.

That belongs to Stage 4B.1.

---

## DecisionReceipt vs AttemptLog

A `DecisionReceipt` records semantic evidence for a conclusion.

An `AttemptLog` records retry / replay / operational attempt sequence.

```text
DecisionReceipt
= what conclusion was reached and why it is governance-relevant

AttemptLog
= which attempts happened and whether intent was preserved
```

Attempt sequence belongs to later retry governance.

Stage 4B should not classify retry safety or preserve full attempt history.

That belongs to Stage 4E.

---

## DecisionReceipt vs RuntimeDecisionPolicy

`DecisionReceipt` records evidence.

`RuntimeDecisionPolicy` decides allowed action.

```text
DecisionReceipt
= evidence

RuntimeDecisionPolicy
= decision rule over evidence
```

A receipt may say:

```text
operator_review_required = true
```

but Stage 4B does not execute operator review.

A receipt may say:

```text
fallback_required = true
```

but Stage 4B does not execute fallback.

A receipt may say:

```text
rebuild_required = true
```

but Stage 4B does not rebuild projections.

Those decisions belong to later runtime policy and strategy layers.

---

## Receipt-Safe Evidence

Receipt-safe evidence is evidence that is:

```text
compact
stable
serializable
reviewable
safe to query
safe to reference later
not overly implementation-specific
not dependent on live Python objects
```

Examples:

```text
semantic_code
category
boundary
severity
risk_level
reversibility
reason
evidence_source
order_id
request_id
candidate_event_id
accepted_event_id
snapshot_id
source_global_position
actor_id
actor_role
elapsed_ms
validation_elapsed_ms
replay_elapsed_ms
transaction_elapsed_ms
lock_wait_ms
accepted_event_count
tail_event_count
fallback_required
rebuild_required
operator_review_required
```

Receipt-safe evidence does not automatically include the full `SemanticOutcome.context` or `SemanticOutcome.evidence`.

---

## Trace-Only Evidence

Trace-only evidence belongs to future `DiagnosticTrace` or `ResolutionTrace`.

Examples:

```text
partial replay progress
last cursor before failure
validator internal branch path
resolver internal branch path
tail event parsing detail
fallback path exploration detail
debug-only adapter context
exception stack trace
large intermediate state payload
```

Stage 4B may note that trace-only evidence exists.

It should not store full trace detail inside the receipt.

---

## Non-Authoritative Evidence

Some evidence may be useful but not authoritative.

Examples:

```text
caller-provided context
metadata_json values not promoted to schema-level contract
debug labels
producer metadata
created_by-style fields
runtime role labels
```

Non-authoritative evidence must not override protected identity fields.

For example:

```text
ValidationResult.metadata["order_id"]
```

must not be treated as authoritative identity evidence unless `order_id` is later promoted to a schema-level `ValidationResult` field.

---

## Contradictory Evidence

A normal `DecisionReceipt` must not be built on contradictory protected identity evidence.

Examples:

```text
stream_admission_result.order_id = order-001
idempotency_record.signature.order_id = evil-order
→ mapping refused
```

```text
idempotency_record.accepted_event.request_id = request-001
idempotency_record.signature.request_id = evil-request
→ mapping refused
```

Stage 4B should not silently choose one identity source and proceed.

Do not pretend the identity lineage is clean.

---

## Identity Lineage Carry-over from Stage 4A PR5

Stage 4A PR5 established protected write-side context:

```text
write_side_outcome
order_id
request_id
candidate_event_id
accepted_event_id
```

Stage 4B must preserve this rule.

Caller-provided context may enrich a receipt.

Caller-provided context must not contradict protected identity.

A rejected append-time admission result must not carry `accepted_event_id`.

An idempotency conflict may expose a prior `accepted_event_id`, but that identifier belongs to the previous accepted request, not to the current rejected candidate.

---

## Infrastructure Error Boundary

Stage 4A PR5 maps write-side infrastructure failure to:

```text
ESCALATION_REQUIRED
REQUIRES_OPERATOR_REVIEW
```

rather than ordinary:

```text
UNRESOLVED
RUNTIME_UNRESOLVED
```

Stage 4B should preserve this as receipt-level evidence:

```text
operator_review_required = true
boundary = LAYER_1_WRITE_SIDE
evidence_source = write_side_admission
```

Stage 4B does not execute operator review.

It only preserves the evidence that later policy may need to escalate.

---

## ValidationResult Identity Checkpoint

Current `ValidationResult` formally carries:

```text id="jj1ffx"
candidate_event_id
validator_name
validation_mode
reason
timing fields
metadata
```

It does not formally carry:

```text id="rbvy2t"
order_id
request_id
```

Stage 4A PR5 correctly avoided treating:

```python id="gd8txf"
validation_result.metadata["order_id"]
```

as authoritative identity evidence.

This matters for Stage 4B because `DecisionReceipt` may need to preserve identity lineage for validation-blocked candidates.

For accepted, replayed, stale-write, lock-timeout, or idempotency-conflict cases, order and request identity may be available from write-side orchestration evidence such as:

```text id="dmqzh5"
accepted event
stream admission result
idempotency record
append-time admission result
```

However, for validation-only blocked candidates, the system may not yet have:

```text id="g1d0ay"
stream_admission_result
accepted_event_id
idempotency_record
```

In that case, Stage 4B must not pretend that identity evidence came from accepted history.

If a receipt is produced from a validation-blocked candidate before admission, any `order_id` should be classified as:

```text id="klbjpi"
pre-admission candidate identity
```

not:

```text id="9dnc4h"
accepted-history identity
```

This means:

```text id="iqyx9r"
candidate_event.order_id
= candidate-derived correlation evidence

accepted_event.order_id
= accepted-history identity
```

A candidate-derived `order_id` may be useful for review, query, and correlation.

It is not proof that the candidate became accepted business truth.

Stage 4B should document the checkpoint:

```text id="jt5paz"
Should ValidationResult promote order_id to a first-class field?
```

Promotion may be useful if Stage 4B needs:

```text id="hda65a"
rejected candidate receipts queryable by order_id
validation-only blocked outcomes without stream_admission_result
candidate_event_id-to-order correlation
read-side unresolved observations correlated back to write-side validation failures
rejected candidate evidence persisted independently
```

Possible future handling:

```text id="gv3nwb"
1. Keep ValidationResult unchanged and derive order_id from the candidate event when the candidate is available.
2. Promote order_id to a first-class ValidationResult field only if receipt mapping requires validation-only receipts to be queryable by order_id without carrying the candidate event.
3. Preserve order_id only as non-authoritative metadata when no candidate event is available.
4. Refuse to produce a normal DecisionReceipt if protected identity evidence is contradictory.
```

Do not add `accepted_event_id` to `ValidationResult`.

Reason:

```text id="p85jpb"
Validation failure means the candidate did not become accepted history.
```

Whether `request_id` should become first-class is a separate question.

Reason:

```text id="hmt6us"
request identity belongs more directly to idempotency / request orchestration
than semantic transition validation
```

Stage 4B PR1 records this checkpoint only.

It does not change `ValidationResult`.

---

## Java / Rust Portability and Evidence Shape Boundary

DecisionReceipt is a core runtime evidence contract.

The current implementation is Python, but the contract should remain portable to future Java / JVM or Rust implementations.

Stage 4B should therefore follow these rules for new runtime contracts:

```text
stable fields should be explicit and typed
evidence payloads should be JSON-safe
identity relationships should use IDs rather than object ownership graphs
core runtime logic should not rely on dynamic attribute lookup
mapping should not execute recovery
receipt evidence should not invent authority
```

Avoid receipt evidence such as:

```text
validator_instance
resolver_instance
postgres_connection
exception_object
callback
lambda
live OrderEvent object graph
live ProjectionSnapshot object
arbitrary dict[str, Any]
```

Prefer receipt evidence such as:

```text
validator_name
resolver_name
exception_type
exception_message
order_id
candidate_event_id
accepted_event_id
snapshot_id
source_global_position
technical_status
semantic_code
```

Suggested direction for PR2:

```text
JsonValue
JsonObject
```

for stored or serializable evidence containers.

Future portable equivalents:

```text
Python: dict[str, JsonValue]
Java: Map<String, JsonNode> or typed record/class
Rust: HashMap<String, serde_json::Value> or typed struct
```

This rule applies to new Stage 4B contracts.

It should not trigger a large retroactive refactor of already stable code.

---

## LLM Execution Telemetry Boundary

LLM token usage and reasoning budget are future execution-cost telemetry.

They may become relevant when the runtime includes LLM-backed candidate generation or agent workflow execution.

However:

```text
token usage
≠
semantic correctness

token usage
≠
accepted truth authority
```

Token usage is governance telemetry, not semantic authority.

Future examples may include:

```text
input_tokens
output_tokens
reasoning_tokens
total_tokens
model_name
tool_call_count
cost_estimate
budget_exceeded
```

These fields may later belong to:

```text
cost_summary
LLM execution receipt
Measurement Matrix
StrategySelector
RetryGovernance
agent workflow governance
```

They do not belong to Stage 4B PR1 implementation.

PR1 should only preserve the extension point.

---

## Cost Evidence Path Boundary

Future cost evidence should preserve which runtime evidence path produced the cost.

This matters because a governance system may need to understand not only how much a workflow cost, but which semantic path produced that cost.

A future measurement layer may distinguish:

```text
admitted_path_cost
rejected_path_cost
unresolved_path_cost
diagnostic_path_cost
total_observed_cost
```

This boundary is especially important for future LLM or agent-backed workflows.

Token usage attached to an admitted path may help explain the execution cost of producing, validating, or admitting a result.

Token usage attached to a rejected path may help explain the execution cost of blocking an invalid, stale, contradictory, or unsafe candidate.

Token usage attached to an unresolved or diagnostic-only path may help explain why the runtime could not safely produce a normal receipt.

However, cost evidence must not change semantic authority.

```text
high cost
≠
stronger semantic truth

low cost
≠
weaker semantic truth
```

The admission boundary remains authoritative:

```text
candidate evidence
≠
accepted fact

rejected evidence
≠
accepted-history truth

cost evidence
≠
semantic authority
```

Stage 4B PR1 records this as a future extension point only.

Concrete cost categories belong to Stage 4B.2 Measurement Matrix / Cost Evidence Inventory.

LLM-specific token accounting belongs to a later LLM / agent governance extension.

---

## Stage 4B PR1 Non-goals

PR1 does not implement:

```text
DecisionReceipt runtime contract
SemanticOutcome → DecisionReceipt adapter
write-side receipt mapping
read-side / snapshot receipt mapping
PostgresDecisionReceiptStore
SQL migrations
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
quarantine execution
LLM token accounting
model routing policy
cost dashboard
observability platform
```

---

## Summary

Stage 4B introduces:

```text
SemanticOutcome
→ DecisionReceipt
```

The receipt is not a log.

The receipt is not a trace.

The receipt is not a policy decision.

The receipt is compact durable governance evidence.

The key design rule is:

```text
persist selected semantic governance evidence,
not arbitrary operational detail
```