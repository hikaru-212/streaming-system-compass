# ADR 0008: Pre-Allocated Event Identity and Candidate/Accepted Event Naming Boundary

[← Back to ADR Index](README.md)

## Status

Accepted

---

## Implementation Status

Accepted and implemented at baseline level.

This decision is reflected in the current event model, Compass Layer 1 validation result shape, and durable write-side schema naming.

Implemented by:

- Stage 3.5B event identity boundary cleanup
- Stage 3.5B PR1 — Physical Schema + Local PostgreSQL + Migration Skeleton
- Stage 3.5B PR2 — PostgresEventStore
- Stage 3.5B PR4 — Transactional Semantic Write-Side Boundary
- Compass Layer 1 validation result naming cleanup

Related implementation notes:

- [Stage 3.5B Implementation Notes](../implementation_notes/stage_3_5b/)
- [Stage 3.5B PR Breakdown](../implementation_notes/stage_3_5b/pr_breakdown.md)

Related source files:

- `src/core/order/events.py`
- `src/compass/transition/types.py`
- `src/compass/transition/validators.py`
- `db/migrations/001_create_write_side_tables.sql`

Related tests:

- `tests/unit/compass/transition/test_predecessor_mismatch_cases.py`
- `tests/unit/compass/transition/test_prev_status_mismatch_cases.py`
- `tests/unit/compass/transition/test_prev_version_mismatch_cases.py`
- `tests/unit/compass/transition/test_stale_candidate_cases.py`
- `tests/integration/storage/test_postgres_event_store.py`
- `tests/integration/pipeline/test_postgres_transactional_write_side.py`

Implemented baseline behavior:

- candidate events receive an `event_id` before append
- `ValidationResult` refers to this value as `candidate_event_id`
- durable accepted history stores the accepted identity as `accepted_event_id`
- rejected candidates may have candidate identity, but do not become accepted history unless appended to the event log
- event-log membership, not UUID existence, grants accepted-event status

Future work may still introduce separate `CandidateEvent` and `AcceptedEvent` types if the project grows into a reusable protocol-grade framework. That is not required for the current baseline.

---

## Context

The project is currently moving from the in-memory semantic baseline toward the durable persistence baseline.

Completed stages include:

```text
Stage 1 — Transactional Semantic Core
Stage 2 — Compass Layer 1 / Write-side Transition Truth Validation
Stage 3 — Projection Runtime Baseline
Stage 3.5A — Decimal / Money Semantics Hardening
```

The immediate next direction is:

```text
Stage 3.5B — Durable Write-side Baseline
Stage 3.5C — Durable Read-side Baseline
Stage 4 — Layer 2 validation and structured semantic outcomes
```

Before entering durable persistence, we reviewed whether the current event identity model is semantically clear enough to support:

```text
event persistence
idempotency persistence
Compass Layer 1 validation outcomes
Compass Layer 2 projection validation outcomes
future structured error model
future retry / conflict analysis
```

During this review, one subtle issue appeared:

> The current `OrderEvent` receives an `event_id` when the candidate event object is created, before Compass Layer 1 validation and before append to the event log.

In the current implementation, `OrderEvent.create()` assigns `event_id` immediately by generating a UUID.

However, the registry flow creates a `new_event`, sends it through Compass Layer 1 validation, and only allows it to continue to admission if the validation decision is `ALLOW`. If validation blocks the event, the event does not reach the admission gate and does not enter accepted history.

This creates a naming and lifecycle question:

```text
If a rejected candidate event already has event_id,
does event_id mean accepted event identity?
```

The answer should be no.

The current code also has `ValidationResult.event_id`, but this validation result is produced for a candidate event before append, so the field name may be ambiguous when later evolving toward a structured error model.

---

## Problem

The project’s core invariant is:

```text
event log = accepted history
```

Compass Layer 1 exists to prevent invalid semantic history from entering the event log.

Therefore, a rejected candidate event must not be treated as an accepted event.

However, because the current implementation assigns `event_id` before persistence, a rejected candidate event can still have an ID.

This is not necessarily wrong, but it creates a semantic risk:

```text
event_id exists
```

could be mistakenly interpreted as:

```text
event is accepted history
```

That interpretation would be wrong.

The event log, not the UUID itself, grants accepted-history status.

This matters because the project is about to add durable persistence and later structured semantic outcomes. If the identity boundary remains vague, future tables such as `compass_outcomes`, `validation_outcomes`, or `attempt_records` may accidentally mix:

```text
candidate event identity
accepted event identity
projection validation anchor
retry / attempt identity
```

This would weaken the clarity of the later error model.

---

## Decision

We will keep the current pre-allocated event identity model for now.

That means:

```text
OrderEvent.event_id is generated when the event-shaped candidate object is created.
```

However, we will explicitly define its lifecycle meaning:

```text
Before append:
  event.event_id should be referenced as candidate_event_id.

After successful append to the event log:
  the same value may be referenced as accepted_event_id.

Rejected candidates:
  may have candidate_event_id,
  but must never appear in the event log,
  and therefore never become accepted_event_id.
```

The key rule is:

```text
event_id alone does not imply accepted history.
Only presence in the event log grants accepted-event status.
```

In other words:

```text
UUID identity is not acceptance.
Event-log membership is acceptance.
```

---

## Chosen Approach: Option A

We choose **Option A: Pre-allocated Event ID + Lifecycle Naming Boundary**.

Under this approach:

```text
same underlying UUID value
different lifecycle role names
```

Example:

```text
event.event_id = evt_abc
```

Before append:

```text
candidate_event_id = evt_abc
accepted_event_id = null
```

After successful append:

```text
candidate_event_id = evt_abc
accepted_event_id = evt_abc
```

If Compass Layer 1 rejects it:

```text
candidate_event_id = evt_abc
accepted_event_id = null
```

The same underlying ID value can be used for traceability, but the semantic name depends on whether the event crossed the append boundary.

---

## Alternatives Considered

### Option A — Pre-allocated Event ID + Lifecycle Naming

This is the selected option.

The current event object keeps its existing `event_id`.

The system distinguishes lifecycle roles by naming:

```text
candidate_event_id
accepted_event_id
```

#### Benefits

```text
- Minimal refactor
- Compatible with current code
- Keeps tracing simple
- Rejected validation outcomes can still reference candidate events
- Does not pollute the event log
- Preserves the core invariant that only appended events are accepted history
- Sufficient for current portfolio/demo goals
```

#### Risks

```text
- Requires disciplined naming
- event_id by itself may remain ambiguous if used carelessly
- Future outcome/error tables must not use a single generic event_id as the universal anchor
```

#### Risk Control

The risk is controlled by documentation and future schema naming:

```text
- Do not use event_id as a universal outcome anchor.
- Use candidate_event_id for pre-append candidates.
- Use accepted_event_id for events that have entered accepted history.
- For Layer 2, use accepted_event_id, checkpoint_sequence, projection_name, or replay range.
```

---

### Option B — Split CandidateEvent and AcceptedEvent

This option would introduce separate types:

```text
CandidateOrderEvent
AcceptedOrderEvent
```

A candidate event would be produced by the aggregate.  
After successful validation and append, it would be transformed into an accepted event.

Example:

```python
accepted_event = AcceptedOrderEvent.from_candidate(candidate_event)
```

#### Benefits

```text
- Stronger semantic clarity
- Type-level boundary between candidate and accepted facts
- Lower chance of accidentally treating rejected candidates as accepted events
- More suitable for long-term production-grade framework design
```

#### Costs

```text
- Significant refactor
- Requires changes to OrderEvent, EventStore, AdmissionResult, ValidationResult, tests, and possibly idempotency records
- Adds complexity before Stage 3.5B durable persistence
- May slow down the current demo-ready roadmap
```

#### Why Not Now

Option B is not rejected forever.

It is deferred because the current project goal is not to build a fully generalized event protocol framework yet.

The current goal is:

```text
deliver a strong, understandable, domain-specific project
that demonstrates Compass-style semantic validation,
durable persistence,
Layer 2 validation,
structured semantic outcomes,
and layered trust reasoning.
```

For this goal, Option A is sufficient.

Option B may become appropriate later if:

```text
- the project becomes a reusable protocol/framework
- multiple domains are added
- external contributors maintain the system
- event identity and audit semantics become production-critical
- type-level distinction becomes necessary to prevent misuse
```

---

### Option C — Generate Accepted Event ID Only at Append Time

This option would mean candidate events have no `event_id`.

The event store would generate `accepted_event_id` only when append succeeds.

#### Benefits

```text
- event_id naturally means accepted event identity
- event log identity is very pure
```

#### Costs

```text
- Rejected candidates still need another identity, such as attempt_id or candidate_id
- Compass Layer 1 outcomes cannot reference event_id
- Attempt tracing becomes less direct
- The problem moves from event_id to candidate_id / attempt_id
```

#### Why Not Now

This option is not simpler in practice.

It makes event log identity pure, but forces the system to introduce a separate candidate identity immediately.

Since the current implementation already has pre-allocated event identity, Option C would create unnecessary churn without clear short-term benefit.

---

## Consequences

### Positive Consequences

This decision preserves the current architecture while clarifying the semantic boundary.

It allows the project to continue toward Stage 3.5B without a large event-type refactor.

It supports future structured outcomes by making the distinction explicit:

```text
Layer 1 outcome:
  candidate_event_id exists
  accepted_event_id = null

Layer 2 outcome:
  accepted_event_id / replay range / checkpoint anchor exists
  candidate_event_id usually null
```

It also supports future retry and conflict analysis because attempt records can refer to both candidate and accepted identities:

```text
attempt_id
request_id
semantic_fingerprint
candidate_event_id
accepted_event_id
expected_version
observed_version
result_class
```

---

### Negative Consequences

The system still requires discipline.

If future code casually uses `event_id` without distinguishing lifecycle role, ambiguity can return.

This decision also means type-level protection is weaker than Option B.

The boundary is protected primarily through:

```text
naming
documentation
schema design
tests
review discipline
```

rather than through separate Python types.

---

## Impact on Error Model / SemanticOutcome

Future structured semantic outcomes should not use a single generic `event_id` as the universal anchor.

Instead, the outcome model should support:

```text
candidate_event_id: Optional[str]
accepted_event_id: Optional[str]
```

A Layer 1 rejected candidate should look like:

```json
{
  "layer": "COMPASS_LAYER_1",
  "subject_type": "CANDIDATE_EVENT",
  "candidate_event_id": "evt_abc",
  "accepted_event_id": null,
  "governance_action": "BLOCK_APPEND"
}
```

A Layer 2 projection drift outcome should look like:

```json
{
  "layer": "COMPASS_LAYER_2",
  "subject_type": "PROJECTION_STATE",
  "candidate_event_id": null,
  "accepted_event_id": "evt_abc",
  "projection_name": "order_summary",
  "checkpoint_sequence": 2,
  "governance_action": "BLOCK_READ_ACTION"
}
```

Therefore, the shared abstraction is:

```text
SemanticOutcome family
```

not necessarily:

```text
one universal event_id field
```

---

## Impact on Outcome Persistence

If the project later persists Compass outcomes, the table should not be designed as:

```sql
CREATE TABLE compass_outcomes (
    outcome_id UUID PRIMARY KEY,
    event_id TEXT NOT NULL
);
```

That would incorrectly assume all outcomes anchor to the same kind of event identity.

A better future shape is:

```sql
CREATE TABLE compass_outcomes (
    outcome_id UUID PRIMARY KEY,

    layer TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,

    candidate_event_id TEXT NULL,
    accepted_event_id TEXT NULL,

    aggregate_id TEXT NULL,
    request_id TEXT NULL,

    projection_name TEXT NULL,
    checkpoint_sequence BIGINT NULL,
    replay_start_sequence BIGINT NULL,
    replay_end_sequence BIGINT NULL,

    context JSONB NOT NULL,
    evidence JSONB NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

This allows Layer 1 and Layer 2 to share an outcome family while preserving their different anchors.

---

## Impact on Retry / Conflict Analysis

This decision also affects future retry analysis.

The project may later want to answer questions such as:

```text
For the same aggregate or request chain,
how many repeated attempts were true retries,
how many were idempotency conflicts,
how many were concurrency conflicts,
and how many were repeated semantic rejections?
```

This cannot be answered reliably with only a generic `event_id`.

A future `attempt_records` model should track:

```text
attempt_id
request_id
semantic_fingerprint
aggregate_id
candidate_event_id
accepted_event_id
expected_version
observed_version
attempt_status
result_class
occurred_at
```

This allows classification such as:

```text
same request_id + same semantic_fingerprint + accepted_event_id replayed
= true retry / idempotent replay

same request_id + different semantic_fingerprint
= idempotency conflict

different request_id + same aggregate_id + same expected_version + one accepted and one stale
= concurrency conflict

same request_id + same semantic_fingerprint + repeated Layer 1 rejection
= repeated invalid attempt
```

This is another reason to distinguish `candidate_event_id` and `accepted_event_id`.

---

## Decision Rationale

Option A is selected because it is the best fit for the current project stage.

The project’s immediate goal is not to perfect every type boundary.

The goal is to demonstrate:

```text
- accepted-history protection
- write-side semantic validation
- durable event/idempotency baseline
- read-side projection validation
- structured semantic outcomes
- layered trust reasoning
```

Option A supports these goals with minimal disruption.

Option B would improve type-level purity, but it would consume time and attention that are better spent on the remaining Stage 3.5B → Stage 5 roadmap.

This is an intentional engineering trade-off:

```text
Prefer explicit lifecycle naming and documentation now.
Defer type-level event split until the project has a real need for reusable protocol-grade event modeling.
```

---

## Final Rule

The project adopts the following rule:

```text
event_id alone does not imply accepted history.
Only presence in the event log grants accepted-event status.
```

And:

```text
Before append, event.event_id is referenced as candidate_event_id.
After successful append, the same value may be referenced as accepted_event_id.
Rejected candidates never appear in the event log and therefore never become accepted_event_id.
```

---

## Future Work

Potential future improvements:

```text
- Rename ValidationResult.event_id to candidate_event_id for Layer 1 outcomes.
- Introduce SemanticOutcome with candidate_event_id / accepted_event_id fields.
- Add documentation explaining event identity lifecycle before durable persistence.
- Add tests ensuring rejected candidates do not appear in event store.
- Add tests ensuring Layer 1 outcomes have candidate_event_id but no accepted_event_id.
- Add tests ensuring accepted events can be referenced as accepted_event_id after append.
- Consider CandidateOrderEvent / AcceptedOrderEvent split only if the project evolves into a reusable protocol/framework.
```

---

## Summary

This ADR records a pre-persistence architecture review.

The review found that the current event identity model is usable but needs clearer lifecycle semantics.

The selected approach keeps pre-allocated event IDs, but prevents semantic confusion through explicit naming:

```text
candidate_event_id before append
accepted_event_id after append
```

This preserves the central invariant:

```text
event log = accepted history
```

while avoiding an unnecessary refactor before the durable persistence and demo-ready roadmap are complete.
