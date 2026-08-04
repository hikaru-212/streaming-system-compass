# DecisionReceipt PostgreSQL Transaction Safety and Liveness Boundary

[← Back to Boundary Notes Index](README.md)

> **Authority:** This is the current specialized transaction safety and
> liveness boundary for `DecisionReceipt` PostgreSQL persistence. It is
> subordinate to the canonical cross-stage
> [DecisionReceipt Boundary](decision_receipt_boundary.md).

*Why statement success, transaction completion, lock arbitration, and bounded progress must remain separate contracts.*

**Recorded on:** 2026-08-04

**Context:** Stage 4B PR6 — DecisionReceipt PostgreSQL persistence

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

It does not implement a production policy for an owner session that remains
alive but idle indefinitely, nor for bounded contender wait, statement
execution, connection-pool cleanup, or deadlock retry.

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

### Bounded abnormal-path liveness

Bounded abnormal-path liveness would require the owner to resolve within an
explicit time bound.

The repository does not implement that guarantee. No universal owner timeout
or waiter timeout exists in this scope. The finite waits used by test helpers
are test-harness failure bounds, not runtime policy.

The repository does not establish:

```text
owner remains alive but idle indefinitely
→ owner is eventually terminated

contender waits too long
→ contender receives a bounded lock timeout

statement runs too long
→ statement is terminated

pool receives an open transaction
→ connection is reset before reuse
```

Those are separate operational contracts.

---

## 7. Possible Future Waiter and Owner Protections

A crucial distinction is:

```text
protecting B from waiting forever
≠ cleaning up A
```

The mechanisms below are external PostgreSQL context for possible future work.
None is currently selected, configured, or guaranteed by the repository's
`DecisionReceipt` persistence scope.

### `lock_timeout`

If configured in future work, this could protect the contender's lock wait.

```text
B waits for a lock
→ wait exceeds configured bound
→ B's statement fails
```

It does not commit, roll back, or terminate A.

### `idle_in_transaction_session_timeout`

This could be considered in future work for a session that:

```text
has an open transaction
holds resources
sends no further statements
does not commit or roll back
```

As external PostgreSQL behavior, a configured timeout can terminate the idle
session and cause its open transaction to be rolled back. The current
repository does not configure or test this mechanism.

### `statement_timeout`

If configured in future work, this could bound an actively executing
statement. It is not current runtime policy.

### Transaction-owner code

The primary defense should still be application-owned completion:

```python
try:
    perform_database_work()
    connection.commit()
except Exception:
    connection.rollback()
    raise
```

or an equivalent transaction context manager.

Possible future timeouts would be operational safety nets, not replacements
for correct transaction ownership.

The current scope also has no general connection-pool reset or discard policy.
Pool cleanup and deadlock handling remain later operational responsibilities.

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

## 9. What Remains Deferred

The following are not PR6 foundational-store guarantees:

- production `lock_timeout` ownership and value;
- `statement_timeout`;
- `idle_in_transaction_session_timeout`;
- future whole-transaction timeout policy;
- receipt transaction-owning service;
- exception-safe Receipt + RetryIntent atomicity;
- connection-pool rollback/reset;
- blocker monitoring and administrative termination;
- genuine circular deadlock tests;
- retry policy for deadlock, serialization failure, lock timeout, and ambiguous connection loss;
- transactional outbox or retry dispatcher.

These require separately scoped transaction-liveness and operational-hardening
work.

---

## 10. Review Checklist

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

## 11. Final Rule

The final boundary is:

```text
statement success
does not prove transaction completion

transaction safety
does not prove bounded progress

waiter timeout
does not clean up the owner

connection-loss cleanup
does not cover a live idle session
```

A trustworthy transaction design must assign separate owners to:

- statement execution;
- transaction completion;
- contender wait bounds;
- abandoned-owner cleanup;
- post-failure rollback;
- and external action delivery.

Only then can durable evidence safely participate in later retry or governance decisions.
