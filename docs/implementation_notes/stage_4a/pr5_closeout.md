# PR5 Closeout — Write-Side Admission Outcome Mapping

[← Back to Stage 4A](README.md)

## Status

Stage 4A PR5 is complete at the write-side outcome mapping level.

PR5 adds a concrete adapter from:

```text
PostgresWriteSideResult
```

to:

```text
SemanticOutcome
```

through write-side technical statuses and the generic runtime technical status mapper.

---

## Implemented Boundary

PR5 implements:

```text
src/compass/runtime/write_side_outcome_mapping.py
tests/unit/compass/runtime/test_write_side_outcome_mapping.py
docs/implementation_notes/stage_4a/write_side_admission_outcome_mapping.md
```

and updates:

```text
src/compass/runtime/__init__.py
src/compass/runtime/technical_status_mapping.py
tests/unit/compass/runtime/test_technical_status_mapping.py
docs/implementation_notes/stage_4a/README.md
docs/implementation_notes/stage_4a/pr_breakdown.md
```

The adapter boundary is:

```text
PostgresWriteSideResult
→ SemanticBoundary.LAYER_1_WRITE_SIDE
→ SemanticOutcome
```

---

## Technical Statuses Added / Used

PR5 adds or uses these write-side technical statuses:

```text
WRITE_SIDE_ACCEPTED
COMPASS_VALIDATION_BLOCKED
CONCURRENT_STATE_STALENESS
WRITE_SIDE_INFRASTRUCTURE_ERROR
IDEMPOTENT_REPLAY
IDEMPOTENCY_CONFLICT
LOCK_TIMEOUT
```

`OCC_CONFLICT_AFTER_VALIDATION` remains supported as a generic status, but write-side `AdmissionVerdict.STALE_WRITE` maps to:

```text
CONCURRENT_STATE_STALENESS
```

This avoids over-binding the semantic layer to a specific optimistic-concurrency implementation detail.

---

## What PR5 Proves

PR5 proves that existing write-side orchestration results can be translated into SemanticOutcome while preserving:

```text
write-side outcome
technical status
Layer 1 write-side boundary
reason
context
evidence
idempotency classification
validation evidence
stream admission evidence
append-time admission evidence
identity lineage
```

It also proves that the adapter does not add:

```text
runtime_action
decision
strategy
retry_allowed
recovery_action
```

---

## Identity Lineage Hardening

PR5 treats these fields as protected write-side context:

```text
write_side_outcome
order_id
request_id
candidate_event_id
accepted_event_id
```

Caller context may add additional information, but it may not contradict protected identity.

PR5 also refuses to map a `PostgresWriteSideResult` when internal identity evidence contradicts itself.

For example:

```text
stream_admission_result.order_id = order-001
idempotency_record.signature.order_id = evil-order
→ mapping refused
```

and:

```text
idempotency_record.accepted_event.request_id = request-001
idempotency_record.signature.request_id = evil-request
→ mapping refused
```

The goal is not to compensate for normal production flow.

The goal is to prevent later DecisionReceipt, DiagnosticTrace, or ActionSafetyGate logic from receiving a SemanticOutcome built on contradictory identity evidence.

---

## Accepted Event Boundary

PR5 preserves:

```text
candidate_event_id identifies the rejected candidate
order_id identifies the aggregate / business entity affected by the candidate
accepted_event_id must only exist after accepted-history admission succeeds
```

A rejected append-time admission result must not carry `accepted_event_id`.

An idempotency conflict may expose a prior `accepted_event_id` from the stored idempotency record.

That prior accepted event belongs to the previous accepted request, not to the current rejected candidate.

---

## Infrastructure Error Boundary

PR5 maps write-side infrastructure failure to:

```text
ESCALATION_REQUIRED
REQUIRES_OPERATOR_REVIEW
```

not:

```text
UNRESOLVED
RUNTIME_UNRESOLVED
```

This does not execute operator review or fail-closed policy.

It preserves a stronger semantic signal for later Stage 4B / Stage 4C governance layers.

Write-side infrastructure abnormality occurs near accepted-history admission and should not be collapsed into ordinary read-side unresolved observations.

---

## Stage 4B Design Checkpoint — ValidationResult Identity Contract

PR5 intentionally does not change `ValidationResult`.

Current `ValidationResult` formally carries:

```text
candidate_event_id
validator_name
validation_mode
reason
timing fields
metadata
```

It does not formally carry:

```text
order_id
request_id
```

This is acceptable in PR5 because write-side outcome mapping obtains `order_id` from stronger outer orchestration evidence:

```text
accepted_event.order_id
stream_admission_result.order_id
idempotency_record.signature.order_id
```

PR5 does not use:

```text
validation_result.metadata["order_id"]
```

as authoritative identity.

Before Stage 4B / DecisionReceipt / DiagnosticTrace, revisit:

```text
Should ValidationResult promote order_id to a first-class field?
```

Consider promotion if Stage 4B needs:

```text
rejected candidate receipt queryable by order_id
validation-only blocked outcomes without stream_admission_result
candidate_event_id-to-order correlation
read-side unresolved observations correlated back to write-side validation failures
rejected candidate evidence persisted independently
```

Do not add `accepted_event_id` to `ValidationResult`.

Validation failure means the candidate did not become accepted history.

Whether `request_id` should become first-class in `ValidationResult` remains a separate decision because request identity belongs more directly to idempotency / request orchestration than semantic transition validation.

---

## Non-goals Preserved

PR5 does not implement:

```text
DecisionReceipt
DiagnosticTrace
RuntimeDecisionPolicy
StrategySelector
RetryGovernance
rejected candidate table
admission_rejection_records
automatic retry policy
operator review execution
Layer 1 validator rewrite
accepted-history mutation changes
ValidationResult schema changes
```

---

## Follow-up Work

After PR5 merges, the next planned PR is:

```text
PR6 — Stage 4A Closeout
```

PR6 should align remaining Stage 4A documentation, exports, test notes, and Stage 4B checkpoints before Stage 4B begins.

PR6 should not introduce DecisionReceipt, DiagnosticTrace, RuntimeDecisionPolicy, StrategySelector, RetryGovernance, or ActionSafetyGate.

---

## Related Issues

Related to Stage 4A PR5 — Write-Side Admission Outcome Mapping.
