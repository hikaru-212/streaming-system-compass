# DecisionReceipt PostgreSQL Transaction Safety and Liveness Boundary

[← Back to Boundary Notes Index](README.md)

> **Authority:** This is the current specialized transaction safety and
> liveness boundary for `DecisionReceipt` PostgreSQL persistence. It is
> subordinate to the canonical cross-stage
> [DecisionReceipt Boundary](decision_receipt_boundary.md).

*Why statement success, transaction completion, lock arbitration, and bounded progress must remain separate contracts.*

**Recorded on:** 2026-08-04

**Context:** Stage 4B PR6 — DecisionReceipt PostgreSQL persistence

## Status

```text
Stage 4B
= complete

Level 1 owner-liveness mechanism
= experimentally verified

production transaction-owner component
= implemented, tested, and merged

automatic production materialization runtime
= not implemented

production timeout value
= not selected

Stage 4B.1 DiagnosticTrace / ResolutionTrace
= current formal development stage; implementation not started
```

## Summary

Stage 4B PR6 introduced PostgreSQL persistence for `DecisionReceipt`. This note
is limited to that store, schema, and their verified transaction behavior. It
does not define a general PostgreSQL transaction contract.

The storage path uses:

```sql
INSERT ... ON CONFLICT DO NOTHING
```

together with primary-key and scoped unique-index enforcement.

The initial question appeared narrow:

> What does `DecisionReceiptInsertStatus.INSERTED` actually prove if the caller has not committed yet?

That question exposed a broader boundary:

```text
statement success
≠ transaction commit
≠ committed visibility
≠ external action completion
```

The concurrency tests then exposed a second distinction:

```text
correct uniqueness arbitration
≠ bounded transaction progress
```

The PR6 integration tests establish conditional progress in tested
`READ COMMITTED` schedules when the owner transaction explicitly:

- commits;
- rolls back;
- or loses its database connection.

A post-Stage 4B Level 1 experiment additionally verifies one physical cleanup
mechanism for a live-but-idle owner: a transaction-local
`idle_in_transaction_session_timeout` can terminate that owner, roll back its
transaction, and release a uniqueness-conflicting contender. This evidence
did not itself implement a production owner-liveness runtime or timeout value.
The approved first-version contract recorded below is now implemented by
`PostgresDecisionReceiptTransactionOwner`. The component does not establish an
automatic production caller, a calibrated production timeout, bounded contender
wait, bounded statement execution, connection-pool cleanup, or deadlock retry.

The governing rule is:

> A database safety guarantee must not be mistaken for a liveness guarantee.

---

## 1. The Core Actors

The concurrency model contains two different roles.

```text
Transaction A
= current unique-identity owner
= inserted a pending receipt row
= has not completed its transaction

Transaction B
= contender
= attempts to insert the same receipt identity
  or the same scoped admitted-producer identity
```

The `PostgresDecisionReceiptStore` is not the transaction owner.

```text
application / orchestration caller
    ↓ owns completion
PostgreSQL connection
    ↓ owns current transaction
PostgresDecisionReceiptStore
    ↓ executes statements only
```

The injected connection must have `autocommit=False`; the store rejects an
autocommit connection. The store does not commit or roll back.

---

## 2. Statement-Level `INSERTED`

`INSERTED` means:

```text
this INSERT statement created a new row
inside the caller-owned transaction
```

It proves that:

1. serialization and pre-SQL validation succeeded;
2. PostgreSQL accepted the row;
3. relevant schema constraints succeeded;
4. this statement won the current uniqueness arbitration;
5. the row is visible in the caller's current transaction view.

It does not prove that:

```text
the transaction committed
the row is visible to another transaction
the row will survive rollback
the row has become durable action authority
```

The correct timeline is:

```text
store.insert(...)
→ INSERTED
→ caller commit()
→ committed transaction
```

If the caller instead rolls back, the database row disappears.

The returned Python `record` may remain in memory, but it is not a commit certificate.

---

## 3. What `.record` Represents

`DecisionReceiptInsertResult.record` is a hydrated `PersistedDecisionReceipt`.

It represents the database row observed in the current transaction view.
`load()` reads that same caller-owned transaction view and does not commit.

For a newly inserted row:

```text
INSERT ... RETURNING
→ hydrate row
→ result.record
```

For an identical duplicate:

```text
INSERT ... ON CONFLICT DO NOTHING
→ no returned row
→ load existing row
→ compare versioned semantic payload
→ ALREADY_PRESENT + existing record
```

The existing row may be:

- a row committed by an earlier transaction; or
- a pending row created earlier in the same transaction.

Therefore:

```text
record exists
≠ record committed
```

### `materialization_provenance`

This field records the path that created the stored row, such as:

```text
LIVE_RESULT
ACCEPTED_HISTORY_RECONCILIATION
```

A later duplicate attempt with a different provenance does not replace the original envelope.

### `materialized_at`

This is the database-generated row materialization timestamp.

It is not:

- commit time;
- duplicate-attempt time;
- load time.

If the transaction rolls back, no durable row remains for that timestamp.

---

## 4. MVCC Visibility and Unique-Index Arbitration

This section uses external PostgreSQL behavior to explain the current test
observations. The repository establishes the behavior of the tested
`DecisionReceipt` schedules; it does not claim a general application-level
liveness guarantee from PostgreSQL lock behavior alone.

A normal `SELECT` in Transaction B does not see Transaction A's uncommitted row.

However:

```text
MVCC read invisibility
≠ unique-index arbitration invisibility
```

When B attempts to insert the same unique identity, PostgreSQL must consider A's in-progress index entry.

B cannot yet know whether:

```text
A commits
→ the identity is occupied

A rolls back
→ the identity becomes available
```

In the tested `READ COMMITTED` collision schedules, B's `INSERT` statement
waits until A's outcome is known.

This is not application-level pessimistic locking.

The application did not first execute:

```sql
SELECT ... FOR UPDATE
```

The strategy remains optimistic:

```text
attempt insert immediately
→ arbitrate only if collision occurs
```

The underlying database still uses lock and transaction-state machinery to resolve the real collision.

---

## 5. Blocking Is Not Deadlock

The distinction below is external PostgreSQL context, not a repository-proven
deadlock-handling policy.

The normal receipt contention schedule is:

```text
A holds pending unique identity
B waits for A
```

This is one-directional blocking.

A deadlock requires a cycle:

```text
A waits for a resource held by B
B waits for a resource held by A
```

For example:

```text
A inserts identity R1, then waits for R2
B inserts identity R2, then waits for R1
```

The current single-receipt foundational store normally competes over one identity per call, so its current tests exercise blocking rather than a circular deadlock schedule.

Future multi-resource orchestration involving:

- DecisionReceipt;
- RetryIntent;
- AttemptLog;
- outbox rows;
- or additional locked aggregates

could introduce genuine deadlock risk if different transactions acquired
resources in inconsistent order. This is an illustrative future scenario, not
a current contract for those artifacts.

---

## 6. Safety and Liveness

### Safety

Within the current `DecisionReceipt` persistence scope, safety means:

```text
conflicting durable receipt facts are not both preserved
```

That safety boundary is implemented and tested through schema constraints,
typed conflict handling, and integration tests. The current evidence establishes
that:

- two conflicting rows are not both preserved;
- identical retries become `ALREADY_PRESENT`;
- same receipt identity with different content becomes a typed content conflict;
- competing admitted-producer identities become a typed producer conflict;
- the first persisted materialization is not overwritten;
- caller rollback removes pending work;
- uncommitted rows are not visible to another connection.

### Conditional progress

The current concurrency tests establish that the contender resumes in the
tested `READ COMMITTED` schedules when the owner explicitly:

- commits;
- rolls back;
- or closes its database connection without committing.

This is conditional progress:

```text
owner reaches a recognized completion path
→ contender resumes
```

### Repository-supported bounded live-but-idle abnormal-path cleanup

Bounded live-but-idle abnormal-path cleanup means:

```text
an owner becomes idle in an open transaction
→ the owner is forced to resolve within the configured idle bound
```

The Level 1 experiment verifies that one transaction-local timeout can resolve
one tested live-but-idle owner schedule. The implemented transaction owner now
applies that mechanism for each explicitly invoked receipt governance
transaction. This does not create automatic production materialization or a
general runtime guarantee. The mechanism does not bound connection acquisition,
actively executing statements, total transaction wall-clock duration,
contender lock wait, commit invocation or response, deadlock resolution, or the
complete transaction lifecycle. The owner still owns that complete lifecycle
as a responsibility boundary.

No calibrated production owner-timeout duration or waiter timeout exists in this
scope. The finite waits used by test helpers are test-harness failure bounds,
not runtime policy.

The repository does not establish:

```text
automatic production DecisionReceipt materialization
→ invokes the owner with a calibrated environment timeout

contender waits too long
→ contender receives a bounded lock timeout

statement runs too long
→ statement is terminated

pool receives an open transaction
→ connection is reset before reuse
```

Those are separate operational contracts.

---

## 7. Waiter Protections and Implemented Owner Boundary

A crucial distinction is:

```text
protecting B from waiting forever
≠ cleaning up A
```

The mechanisms below separate possible future waiter protections from the
implemented first-version owner boundary. No waiter timeout is selected,
configured, or guaranteed by the repository's production `DecisionReceipt`
persistence scope. Transaction-local `idle_in_transaction_session_timeout` is
the implemented owner mechanism, but no automatic production caller,
configuration wiring, or calibrated duration is implemented. The Level 1 test
configuration remains experiment evidence only.

### `lock_timeout`

If configured in future work, this could protect the contender's lock wait.

```text
B waits for a lock
→ wait exceeds configured bound
→ B's statement fails
```

It does not commit, roll back, or terminate A.

### `idle_in_transaction_session_timeout`

This setting applies to a session that:

```text
has an open transaction
holds resources
sends no further statements
does not commit or roll back
```

The Level 1 experiment verifies that, when explicitly applied
transaction-locally, this timeout can terminate the idle owner session, roll
back its open transaction, and release a conflicting receipt contender. The
implemented transaction owner applies the required value transaction-locally
when explicitly invoked, but the repository does not provide an automatic
runtime caller or establish a calibrated production timeout value. See the
[post-Stage 4B owner-liveness implementation note](../implementation_notes/stage_4b/decision_receipt_owner_liveness_runtime_hardening.md).

### `statement_timeout`

If configured in future work, this could bound an actively executing
statement. It is not current runtime policy.

### Implemented transaction-owner boundary

The implemented owner is:

```text
PostgresDecisionReceiptTransactionOwner
→ src/storage/postgres_decision_receipt_transaction_owner.py
```

It owns one dedicated governance connection and one governance transaction with
transaction-local idle-owner protection. The public owner API accepts an
already-complete `DecisionReceipt` plus the required storage-envelope
provenance; it does not accept an arbitrary caller-owned PostgreSQL connection.

Application-owned commit, rollback, and connection cleanup remain the primary
defense. The transaction-local timeout is an owner safety net, not a substitute
for correct completion.

The first version has no connection-pool lease contract. Healthy pool release
versus broken-connection invalidation remains a separate future design, as do
waiter timeout and deadlock handling.

---

## 8. Current Executable Evidence

The PR6 PostgreSQL integration tests now establish:

### Explicit commit

A winner inserts and remains uncommitted.

A contender is observed through `pg_stat_activity` in:

```text
wait_event_type = 'Lock'
```

After winner commit, the contender resumes and becomes:

- `ALREADY_PRESENT`;
- `RECEIPT_ID_CONTENT_CONFLICT`; or
- `ACCEPTED_PRODUCER_IDENTITY_CONFLICT`.

### Explicit rollback

After winner rollback, the contender resumes and receives statement-level:

```text
INSERTED
```

### Connection loss

A dedicated winner connection inserts without commit.

A contender is observed in a real lock wait.

The winner connection closes without explicit commit or rollback.

PostgreSQL rolls back the abandoned owner transaction and releases the pending unique identity.

The contender then:

```text
returns INSERTED
commits
becomes visible through a third connection
```

### Transaction-local idle-owner cleanup — Level 1

The focused live PostgreSQL experiment verifies:

- transaction-local timeout scope;
- restoration of the previous session value after rollback;
- observation of a uniqueness-conflicting contender in a real PostgreSQL
  `Lock` wait;
- termination of the live-but-idle owner backend;
- server-side rollback of the owner's uncommitted receipt transaction;
- contender resumption with statement-level `INSERTED`;
- successful contender commit;
- fresh-connection verification that only the contender receipt is durable;
- `psycopg.errors.IdleInTransactionSessionTimeout`;
- SQLSTATE `25P03`;
- owner transaction status `TransactionStatus.UNKNOWN`;
- `connection.closed == True`;
- `connection.broken == True`.

The focused result was:

```text
2 passed
48 deselected
```

The test-only timeout value is evidence-fixture configuration. It is not a
production recommendation.

The terminated owner connection is unusable and must be discarded rather than
rolled back or returned for reuse.

This experiment verifies a physical PostgreSQL cleanup mechanism. It does not
establish repository-supported runtime policy or a production operational
guarantee.

The repository now implements that bounded component contract in
`src/storage/postgres_decision_receipt_transaction_owner.py`, with focused unit,
PostgreSQL integration, and test-only write-side composition evidence. Those
tests establish the transaction-owner component; they do not implement an
automatic production materialization caller.

ADR 0019 already defines the split target materialization model:

```text
accepted result
→ authoritative business transaction commits first
→ accepted-result DecisionReceipt is materialized separately
→ a missing accepted receipt may later be reconstructed from accepted history

typed non-ACCEPTED observation
→ DecisionReceipt is persisted through a separate governance transaction
→ receipt persistence is reported separately
→ original business result remains unchanged
```

The Level 1 experiment characterizes owner cleanup for those separate
governance-persistence transactions, including future:

- accepted live-result materialization;
- typed non-`ACCEPTED` observation persistence;
- accepted-history reconciliation.

It does not reopen or replace ADR 0019's accepted materialization boundary.

The repository still has no:

- automatic receipt-materialization orchestrator;
- configured production timeout policy;
- immediate typed non-`ACCEPTED` persistence orchestration;
- accepted-history reconciliation scheduler;
- reconstruction-version owner;
- connection-pool discard integration.

The rollback also preserves the self-recording limitation:

```text
receipt transaction rolls back
→ that same transaction cannot durably record its own timeout failure
```
### Stronger isolation

Under the tested `REPEATABLE READ` and `SERIALIZABLE` schedules, PostgreSQL can
raise native `psycopg.errors.SerializationFailure` instead of producing the
`READ COMMITTED` duplicate-or-conflict classification path.

The failed transaction remains unusable until the caller rolls it back. The
store does not classify or retry that failure. Retry classification remains
later policy work.

### Producer-conflict preservation

After concurrent admitted-producer conflict:

- the first row remains unchanged;
- the second receipt ID is absent;
- the receipt count remains one;
- accepted-event producer lookup still returns the first materialization.

---

## 9. Approved Production Transaction-Owner Contract

This section records the first-version production contract now implemented by
`PostgresDecisionReceiptTransactionOwner`. The implemented component does not
imply that any automatic materialization caller exists.

### Identity, placement, and input

The approved responsibility-oriented identity is:

```text
class responsibility
= PostgresDecisionReceiptTransactionOwner

module
= src/storage/postgres_decision_receipt_transaction_owner.py
```

The owner persists an already-complete `DecisionReceipt` together with the
required storage-envelope provenance, including
`DecisionReceiptMaterializationProvenance`.

It does not construct or semantically map the receipt. Its name does not imply
ownership of:

- `SemanticOutcome` mapping;
- `DecisionReceipt` construction;
- receipt or outcome identity allocation;
- materialization scheduling;
- reconciliation discovery;
- retry or policy;
- `DiagnosticTrace`;
- `AttemptLog`;
- accepted-event transaction ownership.

### Dedicated connection ownership

The first production version uses a purpose-specific dedicated connection
factory. The public owner API must not accept an arbitrary caller-owned
PostgreSQL connection.

The owner owns the complete lifecycle:

```text
acquire dedicated governance connection
→ use it for one governance transaction
  with transaction-local idle-owner protection
→ commit or roll back
→ close or discard
```

This structurally prevents accidental reuse of the accepted-event business
transaction connection.

The first version does not support or define connection-pool lease semantics.
Healthy pool release versus invalidation remains a separate future design; no
pool abstraction is part of this contract.

### Mandatory timeout configuration

The first-version application-level configuration shape is conceptually:

```text
idle_in_transaction_session_timeout_ms: int
```

The value is:

- explicit and mandatory;
- expressed only in milliseconds at the application boundary;
- greater than zero;
- validated before connection acquisition;
- invalid when it is a boolean, even though Python booleans are integers;
- applied through transaction-local PostgreSQL configuration.

There is no production default, and zero or an explicitly disabled value is not
part of the first-version owner-liveness contract. The test-only `3s` value is
not a production recommendation. This contract does not select a production
duration or hard-code an application-side PostgreSQL maximum without repository
evidence.

Role-wide, database-wide, migration-level, and persistent session settings are
not permitted. If PostgreSQL rejects the value while the owner applies the
transaction-local setting, the owner fails closed before receipt insertion.

### Transaction ordering and entry invariants

The approved order is:

```text
validate configuration
→ acquire a dedicated PostgreSQL connection
→ require autocommit=False
→ require clean TransactionStatus.IDLE
→ apply transaction-local idle_in_transaction_session_timeout
→ call statement-only PostgresDecisionReceiptStore.insert(...)
→ attempt commit
→ classify a commit-aware technical outcome
→ close or discard the connection
```

The contract does not require a new explicit `BEGIN` abstraction. The first
transaction-local PostgreSQL statement may open the top-level transaction under
normal psycopg behavior. The entry invariant is a clean `IDLE` connection owned
exclusively by the governance transaction owner.

### Statement-only store boundary

`PostgresDecisionReceiptStore` remains statement-only, and
`DecisionReceiptInsertResult` remains statement-level evidence.

```text
INSERTED
≠ committed

ALREADY_PRESENT
≠ owner transaction completed
```

The store does not:

- acquire connections;
- set timeout values;
- commit;
- roll back;
- discard broken connections;
- report durable completion;
- authorize retry.

The transaction owner adds the outer lifecycle contract without weakening or
redefining the existing store result.

### Commit-aware outer technical result

The implemented outer result carries these meanings:

```text
durability
= COMMITTED | NOT_COMMITTED | UNKNOWN

statement_result
= DecisionReceiptInsertResult | none

failure category
= stable technical category | none

typed conflict evidence
= preserved DecisionReceiptConflictError evidence | none

rollback disposition
= NOT_REQUIRED | CONFIRMED | FAILED | NOT_POSSIBLE

connection disposition
= CLOSED | DISCARDED | CLEANUP_FAILED
```

Connection disposition applies when a connection was acquired. A generic
failure category must not erase existing safe typed conflict category or
evidence. The implemented public symbols and fields preserve these meanings and
must not be weakened by later orchestration.

Expected operational PostgreSQL and connection outcomes are typed technical
evidence. Constructor, configuration, and programmer-invariant violations may
remain exceptions. SQLSTATE may be retained as technical diagnostic metadata
when available, but it does not become semantic or retry authority.

No outer result may infer:

- semantic invalidity;
- retry candidacy;
- retry authorization;
- business-command failure.

### Conservative durability rules

Acknowledged commit establishes:

```text
commit acknowledgement received
→ COMMITTED
```

A later close or cleanup failure adds cleanup evidence but does not overwrite
an established `COMMITTED` result.

When commit has not been invoked:

```text
known pre-commit failure
→ NOT_COMMITTED
```

This includes connection-acquisition failure, transaction-local configuration
failure, INSERT or lookup failure, typed `DecisionReceiptConflictError`,
ordinary pre-commit exception, rollback failure, and the experimentally
characterized `IdleInTransactionSessionTimeout` when their phase is known.
Rollback failure forces discard and adds cleanup evidence, but it does not
create commit ambiguity when no commit request was sent.

Once commit invocation begins:

```text
commit did not return acknowledged success
→ UNKNOWN
```

The first version conservatively classifies every commit-phase exception,
connection loss, and response ambiguity as `UNKNOWN`. It does not classify a
commit exception as confirmed non-commit without a later executable contract
that supplies authoritative evidence.

For `UNKNOWN`, the owner must not claim that rollback proves non-commit. It
discards the connection, preserves technical evidence, and leaves later
resolution to reconciliation or another authorized evidence layer.

### Conflict and timeout termination

The owner may catch the existing typed `DecisionReceiptConflictError` to:

```text
preserve typed conflict evidence
→ roll back the governance transaction
→ report NOT_COMMITTED
→ close or discard according to connection health
```

Conflict does not imply semantic invalidity, retry candidacy, retry
authorization, or business-command failure. The existing conflict contract
remains unchanged.

An identical duplicate that returns `ALREADY_PRESENT` is not a conflict.
`DecisionReceiptConflictError` represents the supported conflicting-content or
producer-identity path, and the outer result must preserve its existing safe
typed evidence separately from any generic failure category.

For the experimentally characterized timeout:

```text
IdleInTransactionSessionTimeout
→ PostgreSQL terminates and rolls back the owner transaction
→ blocked contender may progress
→ owner connection is closed, broken, and unusable
→ durability = NOT_COMMITTED
→ rollback disposition = NOT_POSSIBLE
→ connection disposition = DISCARDED
```

The owner must not attempt client rollback as though it could repair or reuse
that terminated connection. The failed transaction cannot durably write a
receipt describing its own termination.

### First-version non-goals

The approved transaction-owner infrastructure does not include:

- connection pooling;
- production caller wiring;
- accepted live-result orchestration;
- typed non-`ACCEPTED` orchestration;
- accepted-history reconciliation;
- retry policy or retry execution;
- `SemanticOutcome` mapping;
- `DecisionReceipt` construction;
- receipt identity allocation;
- `DiagnosticTrace` creation;
- `AttemptLog` creation;
- metrics infrastructure;
- durable self-recording of owner failure;
- schema or migration changes;
- production timeout-value selection.

Accepted live materialization, typed non-`ACCEPTED` persistence, and
accepted-history reconciliation may all use this owner later. It owns only
their final separately owned governance-persistence transaction.

---

## 10. What Remains Deferred

The following remain deferred beyond the PR6 foundational store, the completed
Level 1 mechanism experiment, and the approved production contract.

### Production owner composition and operational policy

- automatic production composition of the implemented
  `PostgresDecisionReceiptTransactionOwner`;
- production sourcing and calibration of
  `idle_in_transaction_session_timeout_ms`;
- production `lock_timeout` ownership and value;
- `statement_timeout`;
- future whole-transaction timeout policy;
- blocker monitoring and administrative termination;
- connection-pool lease, healthy release, and invalidation semantics;
- genuine circular-deadlock tests;
- deadlock-recovery policy.

### ADR 0019 materialization orchestration

ADR 0019 already defines the split target model. The following implementation
work remains deferred:

- accepted live-result materialization orchestration;
- immediate typed non-`ACCEPTED` observation persistence orchestration;
- accepted-history missing-receipt discovery;
- accepted-history reconciliation scheduling;
- canonical reconstruction-version ownership;
- deterministic reconciliation identity generation;
- runtime bootstrap and composition;
- reporting receipt-persistence outcomes separately from business outcomes.

These are orchestration and operational gaps. They are not an unresolved
same-transaction-versus-separate-transaction architecture decision.

### Failure evidence and later governance

- retry policy for deadlock, serialization failure, lock timeout, and ambiguous
  connection loss;
- retry candidacy or authorization for idle-owner termination;
- `SemanticOutcome` interpretation of transaction-owner failure;
- `DiagnosticTrace` or `AttemptLog` recording;
- durable evidence for an unsuccessful receipt-persistence attempt;
- commit-ambiguity reconciliation;
- exception-safe future Receipt + RetryIntent coordination.

### Delivery and operational hardening

- transactional outbox;
- governance publication workflow;
- retry dispatcher;
- production monitoring and alerting;
- deployment configuration;
- operational recovery runbooks;
- load, soak, and chaos evidence.

### Contracts that remain unchanged

The Level 1 experiment and implemented transaction-owner component do not
require changes to:

- `SemanticOutcome`;
- `DecisionReceipt`;
- DecisionReceipt flags;
- strict serializer v1;
- persistence-envelope contracts;
- migration 007;
- the `decision_receipts` schema;
- accepted-history authority;
- ADR 0019's split materialization model.

These deferred concerns require separately scoped implementation,
transaction-liveness, materialization, and operational-hardening work.

## 11. Review Checklist

For any caller-owned PostgreSQL transaction, ask:

1. Which component owns commit and rollback?
2. What does the returned status prove before commit?
3. Can another transaction see the row yet?
4. Can a unique-index contender wait on an invisible pending row?
5. What releases the owner in the normal path?
6. What happens when the connection disappears?
7. What happens when the session remains alive but idle?
8. Is contender waiting bounded?
9. Does a timeout leave the transaction in `INERROR`?
10. Who rolls back before retry or connection reuse?
11. Is the current guarantee safety, liveness, or both?
12. Which deterministic PostgreSQL test proves the claim?

---

## 12. Final Rule

The final boundary is:

```text
statement success
does not prove transaction completion

transaction safety
does not prove bounded progress

waiter timeout
does not clean up the owner

connection-loss cleanup
alone does not cover a live idle session

experimentally verified transaction-local cleanup
does not create production runtime policy

implemented production transaction-owner component
does not prove automatic production materialization or calibrated runtime policy
```

A trustworthy transaction design must assign separate owners to:

- statement execution;
- transaction completion;
- contender wait bounds;
- abandoned-owner cleanup;
- post-failure rollback;
- and external action delivery.

Only then can durable evidence safely participate in later retry or governance decisions.
