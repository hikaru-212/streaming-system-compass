# Retry Reason Classification

[← Back to Architecture Notes](README.md)

## Status

Current classification reference with historical Stage 4 planning material.

This document preserves useful retry taxonomy and intent-consistency reasoning
for **Streaming System + Compass**.

It is not an implementation contract or ADR. Current authority comes from
[ADR 0027](../adr/0027_separate_runtime_decision_strategy_and_retry_authority.md):
Stage 4C owns generic current-response decisions, Stage 4D owns strategy inside
prior authorization, and Stage 4E owns another-attempt authorization and its
constraints. Candidate vocabulary below remains subject to source-grounded
Stage 4E design.

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

These cases may require different current-response decisions and different
attempt-authorization decisions. Those are separate authorities.

The goal is to preserve this distinction after the completed `SemanticOutcome`
and evidence foundation and before Stage 4E introduces retry/attempt
authorization.

---

## 2. Core Boundary

Retry classification belongs to runtime outcome / attempt evidence.

It does not belong directly inside `idempotency_records`.

```text
idempotency_records
= successful request-result memory

live SemanticOutcome and eligible refinement
= current semantic evidence

future attempt evidence
= retry reason, intent consistency, and cross-attempt governance
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

### 4.4 Current SemanticOutcome and Later Attempt Governance

Stage 4A already turns bounded producer evidence into machine-readable
`SemanticOutcome` values. `SemanticOutcome` does not authorize another attempt.

Retry-relevant semantic evidence may inform later Stage 4E classification, but
the classification and authorization boundary must remain separate from the
outcome contract.

---

## 5. Classification Dimensions

Stage 4E should classify retry-like situations using at least three dimensions.

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

`retry_safety` describes what Stage 4E may authorize or require for another
attempt. It is not Stage 4C current-response authority, and the candidate values
below are classification vocabulary rather than executable actions.

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

The examples in this section preserve candidate classification reasoning. A
classification does not itself authorize another attempt, perform a retry, or
permit reuse of the same candidate.

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
Stage 4C may map the current observation to REBUILD, QUARANTINE, or ESCALATE
```

If another attempt is later considered, Stage 4E must authorize it separately
and define any rebuild or revalidation prerequisite.

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

## 7. Historical Candidate Outcome Shape

The following shape is retained as historical planning context. The implemented
`SemanticOutcome` contract is now the Stage 4A authority and does not acquire
retry authorization merely because retry-relevant evidence appears in its
context or evidence mappings.

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

Future Stage 4E classification may consume source-legitimate values such as:

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

## 8. Deferred Attempt-Persistence Boundary

Do not add `retry_reason` to `idempotency_records`.

Reason:

```text
idempotency_records stores successful request-to-accepted-event results
retry reason is attempt-level evidence
```

The first Stage 4C–4E delivery is live and in memory. It does not require a new
table or persisted `DecisionReceipt` before making a live in-process decision.

Historical planning considered separate `request_attempts` and
`semantic_outcomes` tables. Neither is an accepted schema.

The current Stage 4B architecture intentionally does not persist
`SemanticOutcome` as a separate durable governance record. `DecisionReceipt`
owns the current durable governance-evidence boundary. Any future proposal for
separate `SemanticOutcome` persistence would require new evidence, a concrete
consumer, and explicit architectural reconsideration of that boundary.

`request_attempts` remains only a historical/future candidate for a concrete
Stage 4E cross-attempt or restart-recovery consumer. This note does not approve
that table or introduce an `AttemptLog` schema.

```text
historical candidate
!= accepted schema

restart recovery
!= live Retry / Attempt Authorization
```

Restart recovery, durable attempt evidence, and cross-runtime continuation
remain deferred. `DecisionReceipt` remains durable governance evidence, but an
old receipt must not become permanent retry or action authorization.

---

## 9. Current-Response and Attempt-Authorization Mapping

`SemanticOutcome` describes what happened.

It should not directly execute the final control action.

Stage 4C may map a current semantic observation to a generic current response.
Stage 4E separately decides whether another attempt is authorized and under
which constraints.

Example mappings:

```text
IDEMPOTENT_REPLAY
→ Stage 4C may permit replay of the prior accepted result

SEMANTIC_CONFLICT
→ Stage 4C may BLOCK

CONCURRENCY_RETRY
→ Stage 4C decides the current response
→ Stage 4E may separately authorize another attempt with reload/revalidation constraints

INFRASTRUCTURE_RETRY
→ Stage 4C may ESCALATE the current condition
→ Stage 4E may separately authorize another attempt with backoff/timing constraints

REBUILD_REQUIRED
→ Stage 4C may permit or require REBUILD or QUARANTINE
→ Stage 4E governs any later attempt after that response

SEMANTIC_DRIFT / AGENT_INTENT_DRIFT
→ Stage 4C may BLOCK or ESCALATE
→ Stage 4E may deny another attempt
```

These are responsibility examples, not frozen action names or an approved
retry algorithm. Current-attempt failure is not another-attempt authorization,
and retry authorization is not retry execution.

---

## 10. What This Note Owns

This note owns:

- retry-like situation classification
- intent consistency vocabulary
- separation between idempotency memory and attempt evidence
- candidate evidence vocabulary for later Stage 4E design
- future bridge to agent intent drift

---

## 11. What This Note Does Not Own

This note does not implement:

- Stage 4C current-response authority
- Stage 4D strategy selection
- Stage 4E attempt authorization or retry execution
- separate durable `SemanticOutcome` record
- durable request-attempt schema
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

Stage 4A:
SemanticOutcome — COMPLETE / CLOSED.

Stage 4C:
Runtime Decision Authority for the generic current response.

Stage 4D:
Strategy Selection Authority inside an already-permitted action.

Stage 4E:
Retry / Attempt Authorization, including classification, safety, reload,
revalidation, timing, limits, budget, candidate constraints, intent, and lineage.

Stage 5:
Extend intent consistency and retry classification toward agent-facing governance.
```

For a later authorized attempt, the conceptual handoff may be:

```text
current execution evidence
→ Stage 4C current-response decision
→ Stage 4E attempt authorization and constraints
→ Stage 4D strategy selection for the authorized attempt
→ execution
```

Normal executions that do not consider another attempt do not need to pass
through Stage 4E.

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

This distinction is required before Compass can safely authorize another
attempt.

The core boundary is:

```text
idempotency_records
= successful result memory

SemanticOutcome
= runtime semantic interpretation artifact

DecisionReceipt
= current durable governance evidence

request_attempts
= historical candidate only for a concrete Stage 4E cross-attempt or
  restart-recovery consumer; no schema is approved here
```
