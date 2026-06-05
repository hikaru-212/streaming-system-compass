# Retry Reason Classification

[← Back to Architecture Notes](README.md)

## Status

Future architecture note / Stage 4 planning reference.

This document records the intended architecture boundary for retry-like situations in **Streaming System + Compass**.

It is not an implemented Stage 3.5C requirement, and it is not an ADR. The exact data model may change when Stage 4 begins.

---

## 1. Purpose

This note explains why the project should not treat every retry as the same kind of event.

A retry-like situation may mean very different things:

- the same request was safely replayed
- the same request identity was reused with different command meaning
- two writers competed for the same aggregate stream
- infrastructure failed temporarily
- derived state needs rebuild
- a future agent claims to retry the same task but changes the intended meaning

These cases require different runtime decisions.

The goal is to preserve this distinction before Stage 4 introduces structured `SemanticOutcome`, runtime decision policy, action safety, and later agent-facing governance.

---

## 2. Core Boundary

Retry classification belongs to runtime outcome / attempt evidence.

It does not belong directly inside `idempotency_records`.

```text
idempotency_records
= successful request-result memory

SemanticOutcome / request_attempts / runtime_outcomes
= attempt-level evidence, retry reason, intent consistency, and runtime decision support
```

The current `idempotency_records` table should remain narrow:

```text
request_id
semantic_fingerprint
accepted_event_id / result
```

It records a successful mapping from request identity to accepted history.

It should not become a general retry audit table.

---

## 3. Why This Boundary Matters

If retry reasons are collapsed into a single category such as `retry`, `failed`, or `conflict`, the runtime cannot know what to do next.

For example:

```text
same request_id + same fingerprint
→ safe replay
```

is not the same as:

```text
same request_id + different fingerprint
→ same identity carrying different meaning
```

The first case may be safely replayed.

The second case may indicate semantic conflict or, in a future agent setting, intent drift.

These two cases must not be handled by the same runtime decision.

---

## 4. Existing Foundations

The current system already has the foundations needed for this separation.

### 4.1 Idempotency

Idempotency distinguishes:

```text
MISS
REPLAY
CONFLICT
```

The important identity pair is:

```text
request_id + semantic_fingerprint
```

### 4.2 Concurrency Admission

PostgreSQL-backed admission distinguishes:

```text
ADMITTED
STALE_WRITE
LOCK_TIMEOUT
INFRASTRUCTURE_ERROR
```

This handles writer competition over the same aggregate stream.

### 4.3 Compass Validation

Compass Layer 1 validates candidate event truth before accepted-history mutation.

Later Compass Layer 2 will validate whether derived runtime state remains faithful to accepted history.

### 4.4 Future SemanticOutcome

Stage 4 will turn validation results, semantic failures, and runtime trust problems into machine-readable outcomes.

Retry reason classification should be expressed through this future outcome channel.

---

## 5. Classification Dimensions

Stage 4 should classify retry-like situations using at least three dimensions.

### 5.1 retry_class

`retry_class` describes the broad cause.

Candidate values:

```text
IDEMPOTENT_REPLAY
CONCURRENCY_RETRY
INFRASTRUCTURE_RETRY
SEMANTIC_CONFLICT
SEMANTIC_DRIFT
REBUILD_REQUIRED
UNKNOWN
```

### 5.2 retry_safety

`retry_safety` describes what the runtime is allowed to do next.

Candidate values:

```text
SAFE_TO_REPLAY
SAFE_TO_RETRY_AFTER_RELOAD
RETRY_WITH_BACKOFF
REBUILD_REQUIRED
NOT_RETRYABLE
BLOCK_AND_ESCALATE
UNKNOWN
```

### 5.3 intent_consistency

`intent_consistency` describes whether the retried attempt preserves the original meaning.

Candidate values:

```text
SAME_INTENT
SAME_IDENTITY_DIFFERENT_MEANING
NOT_AN_IDEMPOTENCY_REPLAY
AGENT_INTENT_DRIFT
NOT_APPLICABLE
UNKNOWN
```

---

## 6. Classification Rules

## 6.1 Same request_id + same semantic_fingerprint

Meaning:

```text
same external request identity
same command meaning
```

Classification:

```text
retry_class = IDEMPOTENT_REPLAY
retry_safety = SAFE_TO_REPLAY
intent_consistency = SAME_INTENT
```

Runtime meaning:

```text
return previous accepted result
create no new candidate event
mutate no accepted history
```

This is a safe physical retry / replay case.

---

## 6.2 Same request_id + different semantic_fingerprint

Meaning:

```text
same external request identity
different command meaning
```

Classification:

```text
retry_class = SEMANTIC_CONFLICT
retry_safety = NOT_RETRYABLE
intent_consistency = SAME_IDENTITY_DIFFERENT_MEANING
```

Runtime meaning:

```text
block the attempt
do not mutate accepted history
do not overwrite the existing idempotency record
record structured evidence in Stage 4 outcome / attempt storage if persistence exists
```

Future agent-governance interpretation:

```text
the caller claims continuity of identity,
but the meaning changed
```

This is the minimal non-agent version of intent drift.

---

## 6.3 Different request_id + same semantic_fingerprint

Meaning:

```text
different external request identity
same command meaning
```

This is not an idempotency replay because the request identity is different.

Runtime path:

```text
treat as a new command
run domain legality
run Compass validation
run concurrency admission
```

If it competes on the same aggregate stream and loses admission:

```text
retry_class = CONCURRENCY_RETRY
retry_safety = SAFE_TO_RETRY_AFTER_RELOAD
intent_consistency = NOT_AN_IDEMPOTENCY_REPLAY
```

---

## 6.4 Different request_id + different semantic_fingerprint

Meaning:

```text
different external request identity
different command meaning
```

Runtime path:

```text
treat as a normal new command
run domain legality
run Compass validation
run concurrency admission
```

If it competes on the same aggregate stream and loses admission:

```text
retry_class = CONCURRENCY_RETRY
retry_safety = SAFE_TO_RETRY_AFTER_RELOAD
```

---

## 6.5 Infrastructure or cleanup failure

Examples:

```text
database timeout
lock timeout
connection failure
rollback cleanup failure
unsafe pooled connection state
```

Classification:

```text
retry_class = INFRASTRUCTURE_RETRY
retry_safety = RETRY_WITH_BACKOFF or BLOCK_AND_ESCALATE
intent_consistency = UNKNOWN or NOT_APPLICABLE
```

Runtime meaning:

```text
do not confuse infrastructure retry with semantic retry
preserve diagnostic evidence
mark unsafe connection state if needed
```

---

## 6.6 Projection drift / rebuild retry

Meaning:

```text
accepted history replay does not match persisted derived state
```

Classification:

```text
retry_class = REBUILD_REQUIRED
retry_safety = REBUILD_REQUIRED
intent_consistency = NOT_APPLICABLE
```

Runtime meaning:

```text
do not treat this as a request retry
treat it as derived-state correction
map to REBUILD, QUARANTINE, or ESCALATE through RuntimeDecisionPolicy
```

---

## 6.7 Future agent intent drift

Meaning:

```text
same task_id / intent_id
different intent_fingerprint
```

Classification:

```text
retry_class = SEMANTIC_DRIFT
retry_safety = BLOCK_AND_ESCALATE
intent_consistency = AGENT_INTENT_DRIFT
```

Runtime meaning:

```text
the agent is not safely retrying the same intent
block or escalate before any irreversible action
```

---

## 7. Proposed SemanticOutcome Extension

Stage 4 `SemanticOutcome` should support retry classification either through explicit fields or through structured `context` / `evidence`.

Minimal conceptual shape:

```python
@dataclass(frozen=True)
class SemanticOutcome:
    outcome_id: str
    ok: bool
    layer: str
    error_code: str | None
    error_type: str | None
    severity: str
    reversibility: str
    risk_level: str
    context: dict
    evidence: dict
    message: str
```

Retry-related context may include:

```text
retry_observed
retry_class
retry_cause
retry_safety
intent_consistency
request_id
semantic_fingerprint
stored_fingerprint
incoming_fingerprint
expected_version
actual_version
idempotency_verdict
admission_verdict
validation_verdict
```

---

## 8. Future Persistence Boundary

Do not add `retry_reason` to `idempotency_records`.

Reason:

```text
idempotency_records stores successful request-to-accepted-event results
retry reason is attempt-level evidence
```

If Stage 4 needs durable retry evidence, introduce a separate table such as:

```text
request_attempts
```

or:

```text
semantic_outcomes
```

Possible future `request_attempts` shape:

```text
attempt_id
request_id
command_type
semantic_fingerprint
layer
outcome_type
retry_class
retry_safety
intent_consistency
error_type
evidence_json
created_at
```

Possible future `semantic_outcomes` shape:

```text
outcome_id
attempt_id
request_id
layer
ok
error_code
error_type
severity
reversibility
risk_level
context_json
evidence_json
created_at
```

The exact schema should be decided during Stage 4 evidence / outcome persistence design.

---

## 9. Runtime Decision Mapping

`SemanticOutcome` describes what happened.

It should not directly execute the final control action.

`RuntimeDecisionPolicy` maps retry-related outcomes to decisions.

Example mappings:

```text
IDEMPOTENT_REPLAY
→ ALLOW_REPLAY

SEMANTIC_CONFLICT
→ BLOCK

CONCURRENCY_RETRY
→ RETRY_AFTER_RELOAD or BLOCK

INFRASTRUCTURE_RETRY
→ RETRY_WITH_BACKOFF or ESCALATE

REBUILD_REQUIRED
→ REBUILD or QUARANTINE

SEMANTIC_DRIFT / AGENT_INTENT_DRIFT
→ BLOCK_AND_ESCALATE
```

---

## 10. What This Note Owns

This note owns:

- retry-like situation classification
- intent consistency vocabulary
- separation between idempotency memory and attempt evidence
- future Stage 4 direction for retry-related `SemanticOutcome`
- future bridge to agent intent drift

---

## 11. What This Note Does Not Own

This note does not implement:

- Stage 4 `SemanticOutcome`
- durable `semantic_outcomes` table
- durable `request_attempts` table
- agent protocol
- risk scoring
- async audit pipeline
- Stage 5 governance metrics

It also does not change:

- `order_events`
- `idempotency_records`
- Stage 3.5C durable read-side baseline

---

## 12. Stage Alignment

```text
Stage 3.5C:
No schema change for retry reason.
Complete durable read-side baseline.

Stage 4B:
Introduce retry classification into SemanticOutcome / Error Model v1.

Stage 4C:
Map retry classifications into RuntimeDecisionPolicy.

Stage 4D / 4E:
Align Layer 1 / Layer 2 outcomes and action safety behavior.

Stage 5:
Extend intent consistency and retry classification toward agent-facing governance.
```

---

## 13. Summary

Retry is not a single category.

The system must distinguish whether a retry:

- preserves intent
- replays a previous accepted result
- competes on stale state
- arises from infrastructure failure
- requires derived-state rebuild
- or indicates semantic / agent intent drift

This distinction is required before Compass can become a runtime governance layer.

The core boundary is:

```text
idempotency_records
= successful result memory

request_attempts / semantic_outcomes
= retry reason and governance evidence
```
