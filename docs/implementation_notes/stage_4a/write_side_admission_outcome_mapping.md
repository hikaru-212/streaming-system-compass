# Write-Side Admission Outcome Mapping

[← Back to Stage 4A](README.md)

## Purpose

This note records the implementation boundary for:

```text
Stage 4A PR5 — Write-Side Admission Outcome Mapping
```

PR5 connects concrete write-side admission and orchestration evidence to the Stage 4A `SemanticOutcome` contract.

The core question is:

```text
How should Layer 1 write-side acceptance, replay, rejection, validation block,
concurrency uncertainty, and infrastructure abnormality be translated into
SemanticOutcome without changing accepted-history admission behavior?
```

The answer is:

```text
PR5 maps write-side result evidence into observation-level semantic outcomes.
It does not persist rejected candidates, execute retry policy, choose strategy,
or mutate accepted history.
```

---

## Mapping Direction

```text
PostgresWriteSideResult
→ write-side technical status
→ map_runtime_technical_status(...)
→ SemanticOutcome
```

The concrete adapter is:

```text
map_postgres_write_side_result_to_semantic_outcome(...)
```

It pins the observation boundary to:

```text
SemanticBoundary.LAYER_1_WRITE_SIDE
```

The lower-level helper is:

```text
map_write_side_admission_status_to_semantic_outcome(...)
```

It exists for write-side technical statuses that already have a stable status name and should be mapped at the Layer 1 write-side boundary.

---

## Mapped Result Object

PR5 maps:

```text
PostgresWriteSideResult
```

which carries:

```text
outcome
accepted_event
idempotency_decision
stream_admission_result
validation_decision
admission_result
```

This result object is the correct PR5 adapter boundary because it is the write-side orchestration exit point.

The adapter does not map aggregate internals directly.

The adapter does not parse validation reason strings.

The adapter does not infer root cause from read-side observations.

---

## Outcome Mapping

```text
PostgresWriteSideOutcome.ACCEPTED
→ WRITE_SIDE_ACCEPTED
→ VALID / SEMANTICALLY_VALID
```

Accepted means the candidate event passed the write-side flow and entered accepted history.

```text
PostgresWriteSideOutcome.REPLAY
→ IDEMPOTENT_REPLAY
→ RETRY_CLASSIFIED / IDEMPOTENT_REPLAY_ALLOWED
```

Replay means the request matches a prior accepted request signature and can refer back to the prior accepted event.

Replay is not a newly accepted candidate.

```text
PostgresWriteSideOutcome.CONFLICT
→ IDEMPOTENCY_CONFLICT
→ BLOCK_REQUIRED / SEMANTIC_CONFLICT_DETECTED
```

Conflict means the same request identity was reused with a semantically different payload.

```text
PostgresWriteSideOutcome.VALIDATION_BLOCKED
→ COMPASS_VALIDATION_BLOCKED
→ BLOCK_REQUIRED / SEMANTIC_CONFLICT_DETECTED
```

Validation blocked means Compass Layer 1 rejected the candidate event before accepted-history admission.

The adapter preserves validation evidence such as `candidate_event_id`, validation action, validation verdict, validation reason, validation mode, and validator name.

```text
AdmissionVerdict.STALE_WRITE
→ CONCURRENT_STATE_STALENESS
→ CONCURRENCY_UNCERTAIN / CONCURRENCY_UNCERTAIN
```

Stale write means the write-side state changed before append-time admission completed.

This is intentionally more abstract than `OCC_CONFLICT_AFTER_VALIDATION`.

`OCC_CONFLICT_AFTER_VALIDATION` remains supported as a generic technical status, but PR5 uses the storage-neutral `CONCURRENT_STATE_STALENESS` for `AdmissionVerdict.STALE_WRITE`.

```text
AdmissionVerdict.LOCK_TIMEOUT
→ LOCK_TIMEOUT
→ CONCURRENCY_UNCERTAIN / CONCURRENCY_UNCERTAIN
```

Lock timeout indicates concurrency uncertainty, not semantic domain invalidity.

```text
AdmissionVerdict.INFRASTRUCTURE_ERROR
→ WRITE_SIDE_INFRASTRUCTURE_ERROR
→ ESCALATION_REQUIRED / REQUIRES_OPERATOR_REVIEW
```

Write-side infrastructure failure is not treated as ordinary runtime unresolved evidence because it occurs near the accepted-history admission path.

This mapping does not execute operator review.

It only preserves a stronger semantic classification for later policy and receipt layers.

---

## Identity Lineage Protection

PR5 protects core write-side identity fields:

```text
write_side_outcome
order_id
request_id
candidate_event_id
accepted_event_id
```

Caller-supplied context may enrich the outcome.

Caller-supplied context must not contradict adapter-derived protected identity.

For example:

```text
mapped order_id = order-001
caller context order_id = evil-order
→ reject mapping
```

PR5 also checks internal write-side evidence lineage.

If multiple sources inside `PostgresWriteSideResult` provide `order_id`, they must agree.

If multiple sources inside `PostgresWriteSideResult` provide `request_id`, they must agree.

This prevents later receipts, traces, and action-safety decisions from being built on ambiguous or contradictory identity evidence.

---

## Accepted Event Boundary

PR5 preserves the rule:

```text
accepted_event_id
must only refer to accepted history
```

A rejected append-time admission result must not carry `accepted_event_id`.

An idempotency conflict may expose a previous accepted event through the stored idempotency record.

In that case, the `accepted_event_id` belongs to the prior accepted result, not to the current rejected candidate.

---

## ValidationResult Identity Checkpoint

PR5 does not promote `order_id` or `request_id` into `ValidationResult`.

Current `ValidationResult` provides:

```text
candidate_event_id
validator_name
validation_mode
reason
timing fields
metadata
```

It does not provide first-class:

```text
order_id
request_id
```

This is acceptable for PR5 because write-side orchestration can provide `order_id` through stronger outer sources:

```text
accepted_event.order_id
stream_admission_result.order_id
idempotency_record.signature.order_id
```

`ValidationResult.metadata["order_id"]` is not used as authoritative identity evidence in PR5.

The Stage 4B design question is:

```text
Should ValidationResult promote order_id to a first-class field?
```

The answer should be revisited before DecisionReceipt / DiagnosticTrace if rejected validation outcomes must be directly queryable by `order_id`.

---

## Non-goals

PR5 does not implement:

```text
accepted-history changes
Layer 1 validator rewrite
ValidationResult schema changes
rejected candidate persistence
admission_rejection_records
DecisionReceipt
DiagnosticTrace
RuntimeDecisionPolicy
StrategySelector
RetryGovernance
automatic retry
operator review execution
SQL migrations
```

---

## Completion Result

After PR5, Stage 4A can map both:

```text
read-side / snapshot validation outcomes
write-side admission / orchestration outcomes
```

into `SemanticOutcome` while preserving boundary identity and deferring receipts, traces, policy, strategy, and retry governance to later stages.
