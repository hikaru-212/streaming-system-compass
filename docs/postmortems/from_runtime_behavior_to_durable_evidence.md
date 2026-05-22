# Postmortem: From Runtime Behavior to Durable Evidence

[← Back to Postmortems Index](README.md)

**Recorded on:** 2026-05-22

## Summary

This note records an important boundary clarification during Stage 3.5B.

The project had already established several runtime behaviors in Python:

- candidate event creation
- idempotency classification
- Compass transition-truth validation
- allow / block decisions
- possible validation timing and runtime-stage timing measurements

At first, it is tempting to think:

> If Python performed a behavior, then the system "knows" it happened.

The corrected model is more precise:

> Runtime behavior affects the current execution.  
> Durable evidence is what the system explicitly preserves for replay, audit, debugging, and long-term analysis.

This distinction matters because a decision made inside Python may disappear when the request ends, the process exits, or the service restarts.

If the result is not written into a durable evidence channel, then the system may have acted correctly at runtime, but there may be no durable record for later analysis.

Possible evidence channels include:

- PostgreSQL tables
- JSONB metadata fields
- application logs
- metrics
- distributed traces
- audit tables

The main lesson is:

> Application code expresses what the system does and how it decides.  
> Database schema expresses what the system considers important enough to persist.

---

## 1. Trigger Question

The trigger was a Stage 3.5B design question:

> If Python can calculate validation time, idempotency classification, and allow / block decisions, should those values be stored in the database?

This question appeared while considering future fields such as:

- `validator_name`
- `logic_validation_time_ms`
- `accepted_at`
- registry-stage timing
- idempotency attempt history
- replay / conflict / block attempt records

The immediate implementation focus of Stage 3.5B is still the durable write-side baseline.

However, this question exposed a deeper architectural boundary:

```text
runtime behavior
  is not the same as
durable evidence
```

That boundary is important for future observability, debugging, auditability, and governance.

---

## 2. Initial Intuition

The initial intuition was simple:

If Python already performs the logic, perhaps that is enough.

For example, Python can decide:

- whether a request is `MISS`, `REPLAY`, or `CONFLICT`
- whether a candidate event passes Compass validation
- whether the runtime should allow or block an operation
- how long validation took
- how long the full write-side flow took

During the current request, this information exists.

The runtime can use it to make the correct decision.

However, this is not the same as preserving that information.

Once the request ends, temporary Python variables disappear unless the system explicitly writes them somewhere.

This means:

> A runtime decision can be real during execution but invisible during later analysis.

That is the source of the boundary.

---

## 3. Corrected Model

The corrected model separates two responsibilities:

```text
Python / application layer
  defines behavior, decision, and flow

Database / evidence layer
  preserves selected facts for future use
```

The Python application answers questions such as:

- How should a candidate event be created?
- How should idempotency be classified?
- How should Compass transition truth be validated?
- Should the candidate event be allowed or blocked?
- How should validation time or I/O time be measured?
- Which store or transaction boundary should be called?

The database answers different questions:

- Which accepted events are part of durable history?
- Which requests successfully mapped to accepted events?
- Which invariants must be physically protected?
- Which values are important enough to query later?
- Which evidence should survive restart?
- Which facts are needed for replay, audit, debugging, and long-term analysis?

This distinction prevents a common mistake:

> Do not confuse "the runtime did it" with "the system preserved evidence of it."

---

## 4. Python as the Behavior Layer

Python is the behavior layer.

It is where the system expresses how to think, decide, and act.

In this project, Python is responsible for the active runtime flow:

```text
command
  → idempotency classification
  → aggregate rehydration
  → validation context build
  → candidate event creation
  → Compass validation
  → admission / append
  → idempotency record write
  → response
```

This flow includes decisions.

For example:

```text
same request_id + same semantic fingerprint
  → REPLAY

same request_id + different semantic fingerprint
  → CONFLICT

candidate event violates transition truth
  → BLOCK

candidate event passes validation
  → ALLOW
```

These behaviors are real.

They affect execution.

But they are not automatically durable.

Unless the system writes the result to a table, metadata field, log, metric, or trace, later investigation may not be able to prove that the behavior happened.

---

## 5. Database as the Durable Fact Layer

The database is not primarily where the application flow should be written.

The database is where important facts become durable.

For Stage 3.5B, the most important durable facts are:

- accepted events
- successful request-to-accepted-event idempotency mappings

That is why the first durable write-side tables are:

- `order_events`
- `idempotency_records`

The database schema expresses what the system considers important enough to preserve.

For example:

```text
order_events
  preserves accepted history

idempotency_records
  preserves successful idempotency results

metadata_json
  can preserve selected runtime metadata

constraints
  preserve minimum physical invariants

transactions
  preserve consistency across multiple durable writes
```

This does not mean every runtime detail belongs in a relational column.

It means the system must deliberately decide which runtime details need durable evidence.

---

## 6. Behavior Without Evidence

A behavior can happen at runtime without leaving durable evidence.

For example, Python may calculate:

```text
logic_validation_time_ms = 2.4
```

If that value is only kept in a local variable, then it can be used during the request but cannot be queried later.

After the request ends, the value is gone.

Similarly, Python may classify a request as `CONFLICT`.

If the current Stage 3.5B schema only stores successful request-to-accepted-event mappings, then the database can later answer:

> Which requests successfully produced accepted events?

But it cannot answer:

- Which requests conflicted?
- How many conflict attempts occurred?
- Which requests were replayed?
- How many replay attempts happened?
- Which validations failed before event append?
- Which validator was slowest?
- Which event type most often failed validation?

This is not necessarily a flaw.

It is a scope decision.

The important point is to make the scope explicit.

---

## 7. Idempotency Boundary Example

Idempotency is a useful example.

At runtime, Python can distinguish:

- `MISS`
- `REPLAY`
- `CONFLICT`

But if the durable table only records successful request mappings, then only successful mappings become durable facts.

A minimal `idempotency_records` table may preserve:

- `request_id`
- `order_id`
- `command_type`
- `semantic_fingerprint`
- `accepted_event_id`
- `result_sequence`
- `status`
- `created_at`

This is enough to support:

- retry safety
- replay of successful prior requests
- conflict detection against a stored semantic fingerprint
- durable request-to-result mapping

However, it does not necessarily preserve every attempt.

For example, if a conflict attempt is rejected and no attempt log is written, then the system may correctly reject the request at runtime, but later analysis may not know the conflict happened.

To preserve conflict attempts, the system would need an additional evidence channel such as:

- `idempotency_attempts`
- `request_audit_log`
- structured application logs
- metrics counters
- traces

This does not need to happen in Stage 3.5B.

For the current stage, storing successful mappings is reasonable because the goal is to establish the durable closed loop:

```text
accepted event
  +
successful idempotency record
  +
transactional consistency
```

Full attempt analytics can come later.

---

## 8. Validation Boundary Example

Compass validation creates another important example.

At runtime, Compass can decide whether a candidate event is semantically valid.

For example:

```text
candidate event claims previous status = CREATED
actual replayed previous status = INIT
  → transition-truth violation
  → BLOCK
```

If the event is blocked before append, then the invalid event should not enter accepted history.

That is correct.

But there is a second question:

> Should the blocked validation attempt itself be preserved?

The answer depends on the purpose.

### If the purpose is accepted history correctness

Then the important fact is:

> The invalid event did not enter `order_events`.

No additional table is required for the minimal correctness loop.

### If the purpose is debugging

Then it may be useful to log:

- validator name
- failure reason
- expected previous state
- claimed previous state
- command type
- request id
- validation time

### If the purpose is governance analytics

Then it may be useful to persist:

- structured semantic outcome
- severity
- reversibility
- decision
- evidence
- action safety verdict

These belong more naturally to later Stage 4 / Stage 5 work.

Therefore, Stage 3.5B does not need to preserve every validation attempt.

But it should leave a clear path for future evidence channels.

---

## 9. Timing Boundary Example

Timing is another useful example.

Python can measure runtime duration at many points:

- idempotency check time
- aggregate rehydration time
- validation context build time
- candidate event creation time
- Compass validation time
- admission append time
- idempotency record write time
- transaction total time

These measurements are runtime behavior.

They can help future debugging and performance analysis.

But timing values do not become durable unless they are written somewhere.

Possible locations include:

### `metadata_json`

Useful for event-attached runtime metadata:

```json
{
  "registry_timing": {
    "idempotency_check_ms": 0.3,
    "rehydrate_ms": 1.2,
    "context_build_ms": 0.1,
    "candidate_creation_ms": 0.2,
    "compass_validation_ms": 2.4,
    "admission_append_ms": 1.1,
    "idempotency_record_ms": 0.4,
    "transaction_total_ms": 5.7
  }
}
```

### Logs

Useful for high-volume operational debugging.

### Metrics

Useful for dashboards, alerts, and aggregate performance trends.

### Traces

Useful for request-path analysis across multiple services.

The same runtime value can be recorded in different evidence channels depending on its purpose.

The key design rule is:

> Do not add durable fields merely because Python can calculate them.  
> Add durable evidence when there is a clear replay, audit, debugging, governance, or operational need.

---

## 10. System Responsibility Table

The boundary can be summarized as follows:

| Layer | Responsibility | Examples |
|---|---|---|
| Python / Application | define logic, decisions, and flow | candidate event creation, Compass validation, idempotency classification |
| PostgreSQL Schema | define durable facts | `order_events`, `idempotency_records` |
| PostgreSQL Constraints | protect minimum invariants | primary key, foreign key, unique, check constraints |
| PostgreSQL Indexes | make important queries efficient | query by `order_id`, sequence, request id |
| PostgreSQL Transactions | make related durable writes atomic | event append + idempotency record commit together |
| Logs | preserve operational narratives | validation failed, retry occurred, conflict detected |
| Metrics | preserve aggregate operational signals | conflict count, validation latency, replay count |
| Traces | preserve request-path execution evidence | stage-by-stage timing across services |
| Audit Tables | preserve structured historical attempts | blocked request, conflict attempt, governance decision |

This table prevents boundary confusion.

The database is not the only evidence channel.

But the database is the strongest durable fact layer for replay and consistency-critical state.

---

## 11. Storage Priority

Not all runtime information should be stored in the same way.

A useful priority model is:

### 11.1 Must Persist: Core State

These facts are required for correctness:

- accepted events
- successful idempotency mappings
- durable event identity
- durable sequence / stream identity
- exact money values
- transactionally coordinated writes

These belong in the core PostgreSQL schema.

### 11.2 Can Persist in `metadata_json`: Runtime Metadata

These facts are useful but not always part of core domain state:

- validation timing
- validator name
- validation mode
- runtime trace id
- registry-stage timing
- schema interpretation metadata

These can initially live in `metadata_json` if they are event-related and do not require first-class relational querying yet.

### 11.3 Can Persist in Logs / Metrics / Traces: Operational Evidence

These are useful for observability:

- retry count
- conflict count
- validation latency distribution
- request path duration
- store I/O duration
- worker lag

These may be better handled through logs, metrics, or traces rather than relational tables.

### 11.4 Defer: Full Attempt History

These are valuable but not required for the Stage 3.5B durable closed loop:

- every rejected request
- every replay attempt
- every conflict attempt
- every block decision
- every semantic validation failure

These may belong to later stages:

- Stage 4 structured semantic outcomes
- Stage 5 governance analytics
- audit trail expansion
- action safety reporting

The key is to avoid overloading Stage 3.5B with future observability scope.

---

## 12. Relation to Stage 3.5B

Stage 3.5B focuses on durable write-side persistence.

The immediate goal is not to preserve every runtime behavior.

The immediate goal is:

> accepted event history and successful idempotency mappings should survive restart and remain transactionally consistent.

This means PR2, PR3, and PR4 should remain focused:

### PR2: `PostgresEventStore`

Preserve accepted events in `order_events`.

Key durable facts include:

- accepted event identity
- order id
- sequence
- event type
- amount
- proof fields
- payload / proof / metadata JSON
- database append time

### PR3: `PostgresIdempotencyStore`

Preserve successful idempotency mappings in `idempotency_records`.

Key durable facts include:

- request id
- semantic fingerprint
- accepted event id
- result sequence
- command type
- status

### PR4: Transactional Write-Side Boundary

Ensure event append and idempotency record write commit or roll back together.

This is the first natural place where registry-stage timing may become meaningful, because the full write-side flow exists.

However, timing can still be kept as metadata-path support or deferred to a follow-up observability PR.

The project should not let observability expansion block the durable closed loop.

---

## 13. Relation to Other Postmortems

This note complements several existing Stage 3.5B learning notes.

### From In-Memory Correctness to Durable Consistency

That postmortem explains that persistence is not a backend swap.

It focuses on cross-time consistency, restart behavior, partial failure, and transaction boundaries.

This note adds a different distinction:

> Even if runtime behavior happens correctly, it is not durable evidence unless preserved.

### From Git Local-Remote Drift to Database Immutability Boundaries

That postmortem explains that guarantees do not cross boundaries automatically.

It focuses on translating Python-side immutability and append-only rules into database-side constraints and permissions.

This note adds:

> runtime decisions also do not become durable facts automatically.

### From Local PostgreSQL Setup to Defense-in-Depth Boundaries

That postmortem explains that Docker Compose, `.env`, least privilege, migrations, validation, and transactions each protect different boundaries.

This note adds:

> evidence channels also have boundaries: database tables, metadata, logs, metrics, traces, and audit records each preserve different kinds of facts.

Together, these notes form a consistent Stage 3.5B learning series.

---

## 14. Why This Matters for Stage 4 and Stage 5

This boundary becomes more important after Stage 3.5B.

Stage 4 introduces structured semantic outcomes and runtime decisions.

At that point, the system may produce objects such as:

- `SemanticOutcome`
- `RuntimeDecision`
- `RuntimeAction`
- `ActionSafetyGate` result

But the same question will return:

> Which of these should remain runtime-only?  
> Which should become durable evidence?

For example:

- A projection drift outcome may need to be recorded for debugging.
- A `BLOCK` decision before an irreversible action may need an audit trail.
- A `REBUILD` decision may need an operational log.
- A governance decision may need structured evidence for later review.

Stage 5 introduces dual-dimension governance:

```text
semantic correctness × operational freshness
```

That stage will likely require explicit evidence for:

- semantic correctness
- operational freshness
- action safety verdicts
- blocked downstream actions
- stale-but-semantically-valid cases
- fresh-but-semantically-incorrect cases

Therefore, this postmortem prepares a key design principle:

> Governance requires evidence, not only runtime judgment.

The system can only analyze what it preserves.

---

## 15. Practical Design Rules

This postmortem produces several practical rules.

### Rule 1: Do not confuse runtime behavior with durable evidence

If Python makes a decision but does not record it, the decision may be unavailable later.

### Rule 2: Persist only what has a clear purpose

Do not store every temporary value just because it exists.

Choose evidence based on replay, audit, debugging, governance, or operational needs.

### Rule 3: Core state belongs in core tables

Accepted events and successful idempotency mappings are correctness-critical.

They belong in durable PostgreSQL tables.

### Rule 4: Runtime metadata can start in JSONB

Timing, validator identity, validation mode, and trace metadata can initially live in `metadata_json` if they do not need first-class relational structure yet.

### Rule 5: Attempts and failures can be deferred

Replay attempts, conflict attempts, blocked validations, and full semantic outcomes do not need to be fully persisted in Stage 3.5B unless they are required for the minimal durable closed loop.

### Rule 6: Evidence channel should match query purpose

Use tables for durable facts, logs for narratives, metrics for aggregates, and traces for request paths.

### Rule 7: Future governance should not depend on invisible decisions

If a future system needs to explain or audit a decision, that decision must be preserved somewhere.

---

## 16. Updated Mental Model

The old mental model was:

```text
Python did the work
  → the system knows what happened
```

The corrected model is:

```text
Python did the work
  → runtime behavior existed during execution

Python recorded selected evidence
  → the system can later analyze what happened
```

This leads to a sharper architecture:

```text
behavior layer
  decides what should happen

fact layer
  preserves what must remain true

evidence layer
  preserves what must be explainable later
```

In the current Stage 3.5B scope:

```text
behavior layer
  Python application flow

fact layer
  order_events + idempotency_records

evidence layer
  metadata_json now
  logs / metrics / traces / audit tables later
```

---

## 17. Final Lesson

The final lesson is:

> A system does not automatically remember everything it did.  
> It only remembers what it explicitly preserves.

For this project, that means:

- Python can define validation behavior.
- Python can classify idempotency.
- Python can decide allow or block.
- Python can measure timing.
- PostgreSQL can preserve selected durable facts.
- Logs, metrics, traces, and audit tables can preserve additional evidence.

Stage 3.5B should not try to preserve everything.

But it should be clear about what is preserved now and what is intentionally deferred.

The immediate durable truth is:

```text
accepted event history
+
successful idempotency mapping
+
transactional consistency
```

Everything else should be added only when it has a clear role in debugging, observability, audit, or governance.

That is the main insight this postmortem preserves.

---

## Suggested Follow-Up

Use this postmortem as a Stage 3.5B companion note.

Possible follow-up work:

- reference this note from `docs/postmortems/README.md`
- keep `metadata_json` as the initial container for event-related runtime metadata
- avoid adding first-class timing columns before the full write-side flow exists
- defer full idempotency attempt history until audit or governance scope is explicit
- revisit evidence persistence during Stage 4 structured semantic outcomes
- revisit action-safety evidence during Stage 5 dual-dimension governance
