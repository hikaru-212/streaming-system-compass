# ADR 0016: DecisionReceipt Is Governance Evidence, Not Application Logging

[← Back to ADR Index](README.md)

## Status

Accepted

---

## Implementation Status

Accepted as the Stage 4B runtime-evidence boundary decision.

Stage 4A introduced `SemanticOutcome` as the structured semantic interpretation of technical runtime evidence.

Stage 4B will introduce `DecisionReceipt` as the durable, compact, reviewable evidence record derived from selected `SemanticOutcome` values.

This ADR is not yet fully implemented.

The expected implementation path is:

```text
Stage 4A
technical runtime evidence
→ SemanticOutcome

Stage 4B
SemanticOutcome
→ DecisionReceipt
→ durable runtime governance evidence
```

Related implementation notes:

- [Stage 4A Implementation Notes](../implementation_notes/stage_4a/)
- Stage 4B implementation notes, once created under `../implementation_notes/stage_4b/`

This ADR should be implemented by Stage 4B PRs that define:

- the `DecisionReceipt` boundary
- the `DecisionReceipt` runtime contract
- `SemanticOutcome` to `DecisionReceipt` mapping
- write-side receipt mapping
- read-side / snapshot receipt mapping
- optional durable receipt storage after the receipt contract stabilizes

---

## Context

Stage 4A completed the `SemanticOutcome` core.

`SemanticOutcome` converts technical runtime evidence into structured semantic meaning. Examples include:

```text
SEMANTICALLY_VALID
RUNTIME_UNRESOLVED
DERIVED_STATE_UNTRUSTED
DRIFT_DETECTED
REQUIRES_AUTHORITY_FALLBACK
REQUIRES_REBUILD
REQUIRES_OPERATOR_REVIEW
SEMANTIC_CONFLICT_DETECTED
IDEMPOTENT_REPLAY_ALLOWED
CONCURRENCY_UNCERTAIN
```

However, Stage 4A does not persist those outcomes as durable records.

At the Stage 4B boundary, the project must decide whether semantic outcomes should be treated as ordinary logs, observability events, audit records, diagnostic traces, retry attempts, or a separate kind of runtime governance evidence.

A common approach in production systems is to send errors and runtime information to log infrastructure such as structured logs, ELK, Loki, CloudWatch, or similar systems.

Those systems are useful, but they answer a different question.

Operational logs primarily answer:

```text
What happened operationally?
```

Stage 4B needs to answer:

```text
What semantic outcome was concluded,
from which evidence,
at which boundary,
for which subject,
and why is this conclusion safe to reference later?
```

That is a governance-evidence question, not merely a logging question.

---

## Decision

Introduce `DecisionReceipt` as a distinct runtime governance evidence record.

A `DecisionReceipt` is not:

- application logging
- a generic error log
- a full diagnostic trace
- a retry attempt log
- an observability event
- a metrics record
- a runtime decision policy
- an execution strategy
- an action-safety decision

A `DecisionReceipt` is:

- derived from `SemanticOutcome`
- compact
- durable
- reviewable
- machine-readable
- safe for later runtime governance layers to reference
- limited to receipt-safe evidence
- separated from detailed diagnostic traces and retry attempt sequences

The Stage 4B boundary is therefore:

```text
SemanticOutcome
→ receipt-safe evidence extraction
→ DecisionReceipt
```

Future durable persistence may store `DecisionReceipt` records in PostgreSQL or another durable store, but the first Stage 4B decision is the evidence boundary, not the physical schema.

---

## Rationale

### Why `SemanticOutcome` alone is not enough

`SemanticOutcome` explains what a technical runtime result means semantically.

It does not by itself answer:

- whether the result should be preserved for future review
- which identity / lineage fields are safe to persist
- which evidence is receipt-safe
- which evidence belongs only in a diagnostic trace
- which evidence is non-authoritative
- whether the outcome is queryable by order, request, candidate event, accepted event, snapshot, or boundary
- whether later runtime policy, strategy selection, or retry governance can safely reference the result

Stage 4B exists to make those preservation boundaries explicit.

### Why not just use logs

Logs are necessary for debugging, monitoring, aggregation, and operational search.

But logs are usually too broad, too noisy, and too operationally shaped to serve as stable governance evidence.

For example, this is an operational log:

```text
ERROR: snapshot-assisted replay failed while reading tail events
```

A `DecisionReceipt` would instead preserve a compact semantic conclusion such as:

```text
semantic_code = FAST_PATH_UNAVAILABLE
category = FALLBACK_REQUIRED
boundary = SNAPSHOT_TRUST
evidence_source = projection_snapshot_assisted_resolution
snapshot_id = ...
source_global_position = ...
fallback_required = true
operator_review_required = false
```

The receipt is not trying to replace the log.

The receipt records the semantic conclusion that future governance may need to query, review, or reference.

### Why not store every error in the database

Stage 4B should not become an error-log table.

A database-backed receipt store is appropriate for small-volume, high-value governance evidence.

It is not appropriate for high-volume operational logs.

The intended split is:

```text
high-volume operational detail
→ log / observability system

compact semantic governance evidence
→ DecisionReceipt
```

### Why this is optional for some systems

Not every system needs Stage 4B.

A system that only needs local transactional correctness may stop earlier.

For example, the project already establishes strong correctness boundaries before Stage 4B:

- candidate event is not accepted fact
- Compass Layer 1 semantic admission
- idempotency replay / conflict classification
- concurrency admission
- durable accepted history
- durable write-side and read-side persistence
- replay / rebuild validation
- snapshot trust boundary
- permission hardening
- structured `SemanticOutcome`

If a deployment does not require audit, review, durable semantic evidence, policy-linked recovery, or runtime governance, it may not need `DecisionReceipt` persistence.

Stage 4B exists because this project targets explainable runtime governance and future policy / strategy / retry safety, not only local event-sourcing correctness.

---

## DecisionReceipt Boundary

A `DecisionReceipt` should preserve summary-level evidence such as:

```text
receipt_id
outcome_id
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
fallback_required
rebuild_required
operator_review_required
retry_candidate
cost summary fields
receipt-safe evidence summary
```

A `DecisionReceipt` should not preserve full diagnostic detail such as:

```text
partial replay progress
large debug payloads
unbounded log messages
full stack traces
full validator internals
all adapter-specific context
retry attempt sequence
full failure-path trace
```

Those belong to other boundaries.

---

## DecisionReceipt vs DiagnosticTrace

`DecisionReceipt` stores compact governance evidence.

`DiagnosticTrace` stores detailed failure path, partial progress, replay cursor, and debugging trace.

The Stage 4B / Stage 4B.1 split is:

```text
Stage 4B
DecisionReceipt
= durable semantic evidence summary

Stage 4B.1
DiagnosticTrace / ResolutionTrace
= detailed path and partial-progress evidence
```

The core rule is:

```text
summary conclusion belongs in DecisionReceipt
partial failure path belongs in DiagnosticTrace
```

---

## DecisionReceipt vs AttemptLog

`DecisionReceipt` records the semantic evidence for a conclusion.

`AttemptLog` records retry, replay, reload, rebuild, or operational attempt sequence.

Retry governance is deferred until after semantic outcomes and decision receipts exist.

The boundary is:

```text
DecisionReceipt
= what semantic conclusion was reached and why

AttemptLog
= what attempts happened and whether intent remained consistent
```

---

## DecisionReceipt vs RuntimeDecisionPolicy

`DecisionReceipt` does not decide what the runtime should do.

It only preserves evidence that later policy may consume.

The boundary is:

```text
SemanticOutcome
→ DecisionReceipt
→ RuntimeDecisionPolicy
```

Stage 4B should not execute:

- fallback
- rebuild
- quarantine
- retry
- operator review
- policy decision
- strategy selection

It may preserve evidence that those actions are later required or possible.

---

## Evidence Safety Rules

Stage 4B must distinguish:

```text
receipt-safe evidence
trace-only evidence
non-authoritative evidence
contradictory evidence
```

`SemanticOutcome.context` and `SemanticOutcome.evidence` must not be copied blindly into a receipt.

The mapping layer must decide what is safe to preserve.

This matters especially for identity lineage.

For write-side outcomes, protected identity may include:

```text
write_side_outcome
order_id
request_id
candidate_event_id
accepted_event_id
```

A receipt built on contradictory identity evidence should not be produced as a normal governance record.

For example:

```text
stream_admission_result.order_id = order-001
idempotency_record.signature.order_id = evil-order
→ no normal DecisionReceipt
```

The runtime may raise a mapping error, defer to DiagnosticTrace, or produce a special operator-review evidence record only if the contradiction can be represented safely.

It must not pretend the identity lineage is clean.

---

## Relationship to Operational Logging Infrastructure

This ADR does not reject log infrastructure.

Operational logs remain useful for:

- debugging
- monitoring
- aggregation
- searching runtime failures
- infrastructure diagnosis
- incident response
- short-term operational visibility

`DecisionReceipt` exists for a different purpose:

- durable semantic evidence
- governance review
- policy input
- strategy input
- retry-governance input
- audit-like queryability
- lineage-preserving runtime explanation

The intended relationship is:

```text
logs
= operational observability

DecisionReceipt
= semantic governance evidence

DiagnosticTrace
= detailed failure-path evidence

AttemptLog
= retry / attempt sequence evidence
```

---

## Alternatives Considered

### Alternative 1: Use application logs only

Rejected as the Stage 4B governance baseline.

Application logs are useful, but they do not provide a stable, compact, typed, policy-consumable evidence contract.

They may contain the raw facts needed to debug a case, but they do not define which semantic conclusion the runtime reached and whether that conclusion is safe for future governance layers to reference.

### Alternative 2: Store all runtime errors in a database table

Rejected.

This would collapse operational logging into durable governance evidence.

It would likely produce noisy, high-volume, hard-to-query storage that mixes debug detail, infrastructure failures, semantic outcomes, and retry attempts.

Stage 4B should persist selected semantic evidence, not every runtime event.

### Alternative 3: Treat `SemanticOutcome` itself as the durable record

Rejected as the primary Stage 4B design.

`SemanticOutcome` is the semantic interpretation result.

`DecisionReceipt` is the durable evidence record built from that result.

Keeping them separate allows the project to define receipt-safe evidence, actor metadata, identity correlation, cost summaries, and future storage boundaries without overloading the `SemanticOutcome` contract.

### Alternative 4: Delay all evidence persistence until RuntimeDecisionPolicy exists

Rejected.

Runtime policy should consume stable semantic evidence rather than define the evidence shape itself.

Persisting receipt boundaries before policy avoids mixing:

```text
semantic evidence
≠
runtime decision
```

### Alternative 5: Make Stage 4B mandatory for all deployments

Rejected.

`DecisionReceipt` is valuable when auditability, reviewability, policy-linked recovery, strategy selection, retry governance, or semantic runtime explanation is needed.

It is not mandatory for systems that only need local correctness and do not need durable governance evidence.

---

## Consequences

### Positive Consequences

- Semantic outcomes can become queryable and reviewable.
- Runtime governance can reference durable semantic evidence instead of raw logs.
- Future `RuntimeDecisionPolicy`, `StrategySelector`, and `RetryGovernance` can consume stable evidence.
- Logs, traces, receipts, and attempts remain separate.
- Stage 4B can support audit-heavy, review-heavy, or agent-facing governance scenarios.
- The system can explain why a runtime path was accepted, blocked, escalated, or forced into fallback.

### Negative Consequences

- Adds another runtime contract.
- Adds future persistence schema responsibility.
- Requires careful evidence filtering.
- Requires identity-lineage hardening.
- Requires deciding which fields are first-class columns and which fields remain JSON evidence summaries.
- Can create storage and migration overhead if introduced before the receipt contract stabilizes.

### Neutral but Important Consequences

`DecisionReceipt` should be introduced in stages.

The recommended order is:

```text
1. document the evidence boundary
2. define the runtime contract
3. map SemanticOutcome to DecisionReceipt
4. map write-side and read-side adapters to receipts
5. introduce durable storage only after the receipt shape stabilizes
```

The physical store should not drive the semantic evidence contract.

---

## Future Trigger Conditions

Revisit or extend this ADR when one or more of the following become true:

```text
1. DecisionReceipt persistence is implemented in PostgreSQL or another durable store.
2. RuntimeDecisionPolicy begins consuming DecisionReceipt records.
3. StrategySelector depends on receipt-backed cost or trust evidence.
4. RetryGovernance requires request-attempt evidence linked to prior receipts.
5. DiagnosticTrace is implemented and must reference receipts.
6. Operator review workflows require receipt queryability.
7. Agent-facing action safety requires durable semantic governance evidence.
8. Receipt retention, archival, or deletion policy becomes necessary.
9. A deployment needs formal audit-log compliance beyond the current prototype scope.
```

---

## Relationship to Compass

In Compass terms:

```text
technical status
= raw runtime observation

SemanticOutcome
= semantic interpretation

DecisionReceipt
= durable governance evidence for that interpretation

RuntimeDecisionPolicy
= later decision about what the runtime may do

StrategySelector
= later choice among semantically acceptable execution paths

RetryGovernance
= later classification of whether another attempt preserves intent
```

This ADR preserves the distinction between:

```text
recording what happened
```

and:

```text
recording what the runtime concluded semantically and why that conclusion is safe to govern later
```

---

## Current Decision Summary

Stage 4B will not treat `DecisionReceipt` as application logging.

Current model:

```text
SemanticOutcome
= structured semantic meaning

DecisionReceipt
= compact durable governance evidence derived from SemanticOutcome

DiagnosticTrace
= later detailed failure-path evidence

AttemptLog
= later retry / attempt sequence evidence
```

`DecisionReceipt` is optional for systems that do not require durable governance evidence.

It is introduced in this project because the Stage 4 direction targets explainable runtime governance, future policy-linked recovery, strategy selection, retry classification, and action-safety preparation.
