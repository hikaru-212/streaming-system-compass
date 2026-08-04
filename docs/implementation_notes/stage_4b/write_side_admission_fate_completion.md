# Write-Side Admission Fate Completion

## Status

Experimental sandbox proposal.

This note records a prototype shared-contract refinement for human review. It
is not a completed formal Interlude and does not implement the Stage 4B PR4
write-side `DecisionReceipt` adapter.

## 1. Problem

The original `EventAdmissionDisposition` contract could not represent three
write-side lifecycle shapes without overloading an existing disposition or
discarding known evidence:

```text
candidate exists
+ append admission was not reached

current request conflicts with an accepted idempotency record
+ prior accepted event is evidence of the conflict
+ current candidate may or may not exist

append admission was reached
+ known technical failure
+ rollback before return
+ no authoritative accepted event
```

`UNKNOWN` or omitted admission evidence would preserve uncertainty but lose
known lifecycle meaning. Flexible evidence would not provide the typed
cross-field invariants required for governance evidence.

## 2. Candidate creation versus admission reach

The pre-transaction write-side path performs:

```text
candidate creation
→ Compass validation
→ authoritative idempotency re-check
→ stream admission
→ append admission
```

Candidate identity can therefore exist when stream preparation prevents append
admission from being reached. A post-validation idempotency replay or conflict
uses its own distinct disposition rather than
`APPEND_ADMISSION_NOT_REACHED`.

The prototype uses `APPEND_ADMISSION_NOT_REACHED` to mean:

```text
append_if_admitted(...) was not invoked
AdmissionResult is absent
accepted_event_id is absent
```

This is candidate-level append-admission fate, not a claim that the broader
idempotency, history-read, Compass-validation, or stream-preparation pipeline
was never entered.

Candidate construction and append-admission reach are separate lifecycle axes.
In the preferred `IN_TRANSACTION + PESSIMISTIC` path, a rejecting
`prepare_stream(...)` result occurs before candidate construction. A candidate
may nevertheless exist in an explicitly selected non-default or custom
composition, such as `PRE_TRANSACTION + PESSIMISTIC`, because the current
write side does not prohibit that ordering. Accepted-history authority remains
separate from both axes.

## 3. New disposition meanings

### `IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY`

The current request conflicted with an existing accepted idempotency record.

The accepted event identifies the prior accepted event that proves the
conflict. It is not proof that the current attempt was accepted.

A candidate is optional:

```text
early conflict
→ no current candidate

post-validation conflict
→ current candidate exists
```

This disposition is distinct from
`MATCHED_EXISTING_ACCEPTED_EVENT`. Replay means the request matched the prior
semantic request; conflict means it did not.

### `APPEND_TECHNICAL_FAILURE`

Append admission was reached for a real candidate, but a known technical
failure completed with rollback and no authoritative accepted event.

The concrete technical reason remains separate evidence such as:

```text
LOCK_TIMEOUT
WRITE_SIDE_INFRASTRUCTURE_ERROR
```

The disposition does not encode another technical-status taxonomy.

## 4. Exact cross-field invariants

| Disposition | `candidate_event_id` | `accepted_event_id` |
|---|---|---|
| `ADMITTED_TO_ACCEPTED_HISTORY` | required | required and equal to candidate |
| `MATCHED_EXISTING_ACCEPTED_EVENT` | optional | required |
| `IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY` | optional | required; identifies prior accepted event |
| `SEMANTIC_ADMISSION_REJECTED` | required | absent |
| `APPEND_CONCURRENCY_CONFLICT` | required | absent |
| `APPEND_TECHNICAL_FAILURE` | required | absent |
| `COMMIT_OUTCOME_UNRESOLVED` | required | absent |
| `APPEND_ADMISSION_NOT_REACHED` | optional | absent |
| `UNKNOWN` | no additional cross-field invariant | no additional cross-field invariant |

For idempotency conflict, candidate and prior accepted IDs may differ. They
represent different event roles.

For `APPEND_ADMISSION_NOT_REACHED`, an accepted ID remains invalid because
candidate-level append admission was never invoked and no event from the
current attempt obtained accepted-history membership.

## 5. Why `UNKNOWN` or omission is too lossy

The producer knows more than an unknown disposition would preserve:

```text
whether a candidate was constructed
whether authoritative idempotency rejected the request
whether stream admission was reached
whether append admission was reached
whether rollback completed before return
whether a prior accepted event proves an idempotency conflict
```

Using `UNKNOWN` would force later reviewers to recover known meaning from
technical-status strings or nullable identifiers. Omitting admission evidence
would discard the typed fate entirely.

These dispositions keep known lifecycle evidence machine-readable without
turning it into runtime policy or action.

## 6. Why `LOCK_TIMEOUT` is not automatically append concurrency conflict

`LOCK_TIMEOUT` is a technical status. Its lifecycle meaning depends on where it
was produced:

```text
stream preparation timeout
→ APPEND_ADMISSION_NOT_REACHED

append-time timeout
→ append admission reached, known technical failure
```

Therefore:

```text
LOCK_TIMEOUT
≠ automatically APPEND_CONCURRENCY_CONFLICT
```

`APPEND_CONCURRENCY_CONFLICT` remains reserved for stale/OCC-style append
conflict. An append-time lock timeout may later map to
`APPEND_TECHNICAL_FAILURE`, while a stream-preparation timeout maps according
to whether admission was reached, not according to the status name alone.

## 7. Why `COMMIT_OUTCOME_UNRESOLVED` remains reserved

`COMMIT_OUTCOME_UNRESOLVED` represents genuine ambiguity about whether a commit
became durable. It requires a producer and reconciliation evidence capable of
preserving that ambiguity.

The current write-side path explicitly rolls back before returning a rejected
append result. A known rolled-back technical failure is therefore not an
ambiguous commit.

```text
known rollback
→ APPEND_TECHNICAL_FAILURE

ambiguous durable outcome
→ COMMIT_OUTCOME_UNRESOLVED
```

The prototype does not create an ambiguous-commit producer.

## 8. PR4 impact

If approved and copied into the canonical repository, this shared contract
would allow the later PR4 adapter to map:

```text
stream-preparation rejection before candidate-level append admission
→ APPEND_ADMISSION_NOT_REACHED

early or post-validation idempotency conflict
→ IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY

known append-time LOCK_TIMEOUT or INFRASTRUCTURE_ERROR with rollback
→ APPEND_TECHNICAL_FAILURE
```

PR4 must still derive disposition from typed producer lifecycle evidence.
Technical status, semantic outcome, nullable identifiers, and identifier
presence alone remain insufficient.

## 9. Explicit non-goals

This experimental proposal does not implement or design:

```text
the PR4 write-side DecisionReceipt adapter
status-to-disposition mapping code
subject compatibility rules
identity-source compatibility rules
field-level identity provenance
runtime policy
retry classification or authorization
serialization
persistence
SQL migrations
PR5
PR6
ambiguous-commit production or reconciliation
```

The new and existing dispositions remain governance evidence. They execute no
runtime action.
