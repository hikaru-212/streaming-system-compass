# DecisionReceipt Boundary

[← Back to Boundary Notes](README.md)

## Purpose

This note defines the conceptual boundary for Stage 4B `DecisionReceipt`.

Stage 4A introduced `SemanticOutcome` as the semantic interpretation of technical runtime evidence.
Stage 4B introduces `DecisionReceipt` as the durable governance evidence record for selected semantic outcomes.

```text
technical runtime evidence
→ SemanticOutcome
→ DecisionReceipt
```

The purpose of this note is to clarify what a receipt is responsible for, what it must not absorb, and why durable governance evidence is narrower than ordinary logging.

---

## Core Boundary

A `SemanticOutcome` answers:

```text
What does this technical result mean semantically?
```

A `DecisionReceipt` answers:

```text
What selected summary evidence should be preserved so future governance can review, query, and act on that semantic meaning?
```

Therefore:

```text
SemanticOutcome
= semantic interpretation

DecisionReceipt
= durable governance evidence record for selected semantic interpretation
```

A system may stop at `SemanticOutcome` if it only needs immediate runtime classification.
A system that needs auditability, reviewability, operator investigation, policy-linked recovery, strategy selection, retry governance, or future agent workflow governance needs receipts.

A receipt provides evidence for those later governance layers.
It does not execute them.

---

## What DecisionReceipt Is

A `DecisionReceipt` is:

```text
durable
compact
reviewable
machine-readable
policy-consumable
safe to reference later
```

It preserves selected governance evidence such as:

```text
semantic_code
category
boundary
severity
risk_level
reversibility
reason
evidence_source
subject
identity / lineage correlation
write-side admission fate when applicable
snapshot identity when relevant
source global position when relevant
summary cost fields when relevant
flags such as fallback_required, rebuild_required, or operator_review_required
```

The key phrase is **selected governance evidence**.

A receipt should not persist arbitrary operational detail merely because that detail exists in runtime context.

---

## What DecisionReceipt Is Not

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
persistence state
```

This means:

```text
DecisionReceipt
≠
application log

DecisionReceipt
≠
DiagnosticTrace

DecisionReceipt
≠
AttemptLog

DecisionReceipt
≠
RuntimeDecisionPolicy
```

Operational logs may still exist in ELK, Loki, CloudWatch, local files, or another observability system.
DecisionReceipt is narrower: it preserves semantic governance evidence that future runtime governance may need to reference.

---

## Separate Semantic Axes

Stage 4B keeps the following questions separate:

```text
SemanticOutcome
= what the runtime evidence means semantically

DecisionReceiptEvidenceSource
= which runtime evidence path produced the receipt evidence

DecisionReceiptIdentitySource
= the primary provenance of correlation evidence

EventAdmissionDisposition
= what happened to an event attempt at write-side admission
```

These axes must not be inferred from one another.

For example:

```text
evidence_source = WRITE_SIDE_ADMISSION
technical_status = LOCK_TIMEOUT
```

preserves two independent facts:

```text
where the evidence came from
what condition was observed within that path
```

Likewise:

```text
candidate_event_id is present
```

does not prove:

```text
the event entered accepted history
```

Admission fate must remain explicit.

---

## Evidence Path vs Technical Status

`DecisionReceiptEvidenceSource` records the runtime path that produced the receipt evidence.

Current values are:

```text
WRITE_SIDE_ADMISSION
READ_SIDE_PATH
SNAPSHOT_TRUST_PATH
SNAPSHOT_ASSISTED_PATH
RUNTIME_OBSERVATION
UNKNOWN
```

Technical status remains a separate evidence detail and may be preserved inside `evidence_summary`.

The governing distinction is:

```text
evidence_source
= where the evidence came from

technical_status
= what condition was observed within that path
```

A status name alone must not determine the evidence source.

Concrete adapter ownership should decide the path:

```text
write-side receipt adapter
→ WRITE_SIDE_ADMISSION

read-side receipt adapter
→ READ_SIDE_PATH

snapshot trust receipt adapter
→ SNAPSHOT_TRUST_PATH

snapshot-assisted receipt adapter
→ SNAPSHOT_ASSISTED_PATH
```

---

## Receipt vs Diagnostic Trace

A receipt stores summary-level governance evidence.

A diagnostic trace stores detailed path evidence.

```text
DecisionReceipt
= compact summary evidence

DiagnosticTrace
= detailed failure path, partial progress, replay cursor, resolver path, and debugging trace
```

Trace-only evidence includes details such as:

```text
partial replay progress
last cursor before failure
validator internal branch path
resolver internal branch path
tail event parsing detail
fallback path exploration detail
exception stack trace
large intermediate state payload
```

Those details may be useful, but they belong to Stage 4B.1 `DiagnosticTrace` / `ResolutionTrace`, not the Stage 4B receipt boundary.

---

## Receipt vs Runtime Decision

A receipt records evidence.

A policy decides action.

```text
DecisionReceipt
= evidence

RuntimeDecisionPolicy
= decision rule over evidence
```

A receipt may preserve:

```text
operator_review_required = true
fallback_required = true
rebuild_required = true
retry_candidate = true
```

but Stage 4B does not execute operator review, fallback, rebuild, quarantine, retry, or strategy selection.
Those belong to later runtime policy and strategy layers.

In particular:

```text
retry_candidate
≠
retry_allowed
```

A receipt may preserve retry-relevant evidence.
It does not authorize a retry.

---

## Receipt-Safe Evidence

Receipt-safe evidence should be:

```text
compact
stable
serializable
reviewable
safe to query
safe to reference later
not overly implementation-specific
not dependent on live runtime objects
```

Examples include explicit IDs and typed summary fields:

```text
order_id
request_id
candidate_event_id
accepted_event_id
snapshot_id
source_global_position
actor_id
actor_role
runtime_role
elapsed_ms
validation_elapsed_ms
replay_elapsed_ms
transaction_elapsed_ms
lock_wait_ms
accepted_event_count
tail_event_count
```

The full `SemanticOutcome.context` or `SemanticOutcome.evidence` should not automatically become receipt evidence.
The receipt mapping boundary decides what is safe to preserve.

---

## JSON-Safe Evidence Boundary

Flexible receipt evidence must be JSON-safe.

The current contract accepts:

```text
str
int
finite float
bool
None
list / tuple of JSON-safe values
mapping with non-empty string keys and JSON-safe values
```

It rejects:

```text
UUID objects
Decimal values
datetime values
sets
callbacks
exception objects
database connections
validator instances
arbitrary Python objects
non-finite floats
overly deep or cyclic object graphs
```

Useful runtime objects must be converted to stable representations first.

For example:

```text
UUID object
→ string identifier

Exception object
→ exception_type / exception_message
```

Receipt evidence is recursively frozen after validation.

A JSON boolean remains valid JSON evidence, but it must not be accepted as an integer counter, elapsed-time value, or global position.

---

## Non-Authoritative Evidence

Some evidence may help review but should not become authority.

Examples:

```text
caller-provided context
metadata_json values not promoted to schema-level contract
debug labels
producer metadata
created_by-style fields
runtime role labels
```

Non-authoritative evidence may enrich a receipt.
It must not override protected identity fields.

For example, `ValidationResult.metadata["order_id"]` should not be treated as authoritative identity unless `order_id` is later promoted to a first-class `ValidationResult` field.

---

## Contradictory Evidence

A normal `DecisionReceipt` must not be built on contradictory protected identity evidence.

For example:

```text
stream_admission_result.order_id = order-001
idempotency_record.signature.order_id = evil-order
→ normal receipt mapping refused
```

or:

```text
idempotency_record.accepted_event.request_id = request-001
idempotency_record.signature.request_id = evil-request
→ normal receipt mapping refused
```

Stage 4B should not silently choose one identity source and proceed.
If protected identity evidence contradicts itself, the system should preserve that as an abnormal mapping condition rather than pretending the lineage is clean.

---

## Candidate Identity vs Accepted-History Identity

Stage 4B must preserve the distinction between candidate evidence and accepted truth.

```text
candidate_event_id
= identifies a proposed event attempt

accepted_event_id
= identifies an event proven to belong to accepted history
```

A rejected or conflicted candidate must not carry an `accepted_event_id` as if it became accepted history.

An idempotency conflict may expose a prior `accepted_event_id`, but that identifier belongs to the previous accepted request, not the current rejected candidate.

For validation-only blocked candidates, an `order_id` may be useful for review and query, but it should be classified as candidate-derived correlation evidence unless it comes from accepted-history authority.

---

## Event Admission Fate

`DecisionReceiptAdmissionEvidence` records typed write-side admission fate through `EventAdmissionDisposition`.

Current values are:

```text
ADMITTED_TO_ACCEPTED_HISTORY
MATCHED_EXISTING_ACCEPTED_EVENT
SEMANTIC_ADMISSION_REJECTED
APPEND_CONCURRENCY_CONFLICT
COMMIT_OUTCOME_UNRESOLVED
ADMISSION_NOT_REACHED
UNKNOWN
```

Event identifiers remain owned by `DecisionReceiptCorrelation`.
Admission evidence owns only the disposition.

This avoids duplicating candidate and accepted event IDs across two contract objects.

### Newly admitted event

```text
candidate_event_id is present
accepted_event_id is present
candidate_event_id == accepted_event_id
disposition = ADMITTED_TO_ACCEPTED_HISTORY
```

The event identity remains the same.
Its authority role changes when accepted-history membership is established.

### Idempotent replay

An idempotent replay must identify the existing accepted event:

```text
accepted_event_id is present
disposition = MATCHED_EXISTING_ACCEPTED_EVENT
```

`candidate_event_id` is optional.

It may be absent when an early idempotency lookup returns the existing accepted event before a new candidate is constructed:

```text
candidate_event_id = None
accepted_event_id = existing accepted event
disposition = MATCHED_EXISTING_ACCEPTED_EVENT
```

If a candidate was already constructed, its identifier may also be preserved and may differ from the existing accepted event identifier.

### Non-accepted candidate

For:

```text
SEMANTIC_ADMISSION_REJECTED
APPEND_CONCURRENCY_CONFLICT
COMMIT_OUTCOME_UNRESOLVED
```

the current contract requires:

```text
candidate_event_id is present
accepted_event_id is absent
```

This means the receipt has evidence for a candidate event but does not have authoritative evidence that permits it to name an accepted event.

For `COMMIT_OUTCOME_UNRESOLVED`, the absent accepted ID does not prove rollback.

`COMMIT_OUTCOME_UNRESOLVED` is currently reserved contract vocabulary.
No current production producer is established for it, and generic infrastructure failures must not be mapped to it automatically.

### Admission not reached

For:

```text
ADMISSION_NOT_REACHED
```

the current contract requires:

```text
candidate_event_id is absent
accepted_event_id is absent
```

This prevents request-level or pre-candidate failure from being misrepresented as candidate-level admission evidence.

---

## Identity Provenance Boundary

`DecisionReceiptCorrelation.identity_source` records the primary provenance of the correlation block.

Current values are:

```text
ACCEPTED_HISTORY
CANDIDATE_EVENT_IDENTITY
WRITE_SIDE_CORRELATION
READ_SIDE_OBSERVATION
SNAPSHOT_LINEAGE
CALLER_CONTEXT
UNKNOWN
```

The field is not yet field-level provenance.

A receipt may contain fields that originated at different boundaries.
The current primary-source model is an explicit limitation, not a claim that every field shares exactly one source.

Field-level identity provenance should be introduced only when future adapters, persistence queries, operator tooling, or runtime policy require authority decisions for individual correlation fields.

---

## Durable Persistence Boundary

Stage 4B should eventually persist receipts as durable governance records.

However, persistence should not be introduced before the receipt contract and mapping shape are clear.

The durable table should store receipt-level evidence, not every log, trace, retry attempt, or policy decision.

A useful direction is:

```text
stable identity / correlation fields
→ first-class columns where useful for query and review

flexible summary evidence
→ JSON-safe evidence_summary / cost_summary / metadata_json

full diagnostic paths
→ DiagnosticTrace / ResolutionTrace, not decision_receipts

retry attempt sequences
→ AttemptLog / RetryGovernance, not decision_receipts
```

This keeps the persistence layer aligned with the receipt boundary instead of becoming a generic observability table.

---

## Java / Rust Portability

DecisionReceipt is a core runtime governance contract.

Even if the current implementation is Python, the contract should remain portable to future Java / JVM or Rust implementations.

Prefer:

```text
explicit typed fields
JSON-safe evidence payloads
IDs instead of live object graphs
stable mapping behavior
no recovery execution inside mapping
```

Avoid receipt evidence such as:

```text
validator instances
resolver instances
database connections
exception objects
callbacks
lambdas
live OrderEvent object graphs
live ProjectionSnapshot objects
arbitrary dict[str, Any]
```

The receipt should preserve evidence, not runtime object ownership.

---

## Current Stage 4B Responsibility Split

```text
PR2
= runtime contract and contract invariants

PR3
= generic SemanticOutcome → DecisionReceipt adapter

PR4
= concrete write-side admission receipt mapping

PR5
= concrete read-side and snapshot receipt mapping

PR6
= serialization and durable persistence
```

PR2 defines which receipt states are constructable.

It does not claim that concrete runtime adapters already produce every state in the vocabulary.

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

The key rule is:

```text
persist selected semantic governance evidence,
not arbitrary operational detail
```

The additional Stage 4B contract rule is:

```text
semantic meaning,
evidence path,
identity provenance,
and accepted-history admission fate
must remain separate concepts
```
