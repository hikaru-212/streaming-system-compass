# Postmortem: Autocommit, Transaction Boundaries, and Partial-Write Risk

[← Back to Postmortems Index](README.md)

**Recorded on:** 2026-05-30

## Summary

This note records a design-learning moment during Stage 3.5B / PR5 planning.

The trigger was a small PostgreSQL configuration question:

> If `autocommit` is enabled, does that explain why some systems can end up with partial writes, such as expecting 100 rows but only persisting 80?

The deeper lesson is:

> A multi-step write flow is only atomic if the relevant steps are protected by the same transaction boundary.

This matters for **Streaming System + Compass** because the durable write-side flow is not a single SQL statement.

It may include:

- request-level idempotency checks
- stream admission preparation
- accepted-history loading
- aggregate rehydration
- candidate-event creation
- Compass validation
- accepted event append
- idempotency record persistence
- commit / rollback

If the transaction boundary does not cover the correct physical and semantic scope, the system may preserve only part of the intended state transition.

This postmortem is not a production incident report.

It is a design-learning postmortem documenting why `autocommit`, transaction-scoped locks, partial writes, and write-side admission must be treated as one boundary problem.

---

## 1. Trigger Question

The trigger question was:

> In simple CRUD or ETL-like flows, if a system expects to insert 100 rows but only 80 rows appear, is that related to `autocommit`?

The initial intuition was correct, but incomplete.

`autocommit` is one possible reason partial writes can happen.

However, the broader issue is not only `autocommit`.

The broader issue is:

> The intended unit of work was larger than the actual transaction boundary.

If the application considers 100 rows to be one logical unit, but the database commits every row or every small batch independently, a mid-process failure can leave a partial durable result.

---

## 2. Initial Confusion

The confusion came from mixing three different ideas:

1. executing SQL statements
2. committing database state
3. preserving a logical unit of work

A program may run many statements successfully before failing.

But successful execution of individual statements does not automatically mean the full logical operation is safe.

For example:

```text
expected logical operation:
  insert 100 rows as one complete batch

actual physical behavior:
  first 80 rows committed
  row 81 fails
  remaining rows never inserted
```

The database now contains a partial result.

This is not necessarily because the database is broken.

It usually means the transaction boundary did not match the logical boundary.

The corrected model is:

> A transaction boundary must cover the exact unit of work that must succeed or fail together.

---

## 3. Autocommit as a Boundary Collapse

When `autocommit` is enabled, each SQL statement may be committed as its own transaction.

That means the physical model becomes:

```text
INSERT row 1
  → committed

INSERT row 2
  → committed

INSERT row 3
  → committed
```

If the process fails halfway, earlier committed rows remain durable.

This can create the familiar partial-write state:

```text
expected: 100 rows
actual:   80 rows
```

The important lesson is not:

> Every partial write is caused by `autocommit`.

The better lesson is:

> `autocommit` is one way the physical transaction boundary can become smaller than the logical operation.

Other causes can produce similar partial results:

- batch commit after every N rows
- chunked ETL writes
- bad-row skipping
- distributed worker partial failure
- retry logic that is not idempotent
- load tools configured to continue after errors
- missing staging / swap / validation pattern

So the reusable rule is:

> Partial success indicates that the system needs a clearer unit-of-work boundary, not merely better exception handling.

---

## 4. Why This Matters for the Write-Side Pipeline

The PostgreSQL-backed write-side is not just inserting one row.

At Stage 3.5B / PR4, the durable write-side already needs to make accepted event append and idempotency record persistence succeed or fail together.

The intended invariant is:

```text
accepted event append
+
idempotency record persistence
=
one atomic write-side unit
```

If accepted event append succeeds but idempotency record persistence fails, the database must not keep only the accepted event.

Otherwise, the system may create this broken durable state:

```text
order_events:
  contains accepted event

idempotency_records:
  missing request-to-event replay memory
```

That would make future retries ambiguous or unsafe.

The UnitOfWork boundary exists to prevent this.

The corrected model is:

```text
append accepted event
record idempotency result
commit

or

append accepted event
record idempotency result fails
rollback appended event
```

This is transaction atomicity.

It is separate from domain legality, Compass validation, idempotency classification, and concurrency admission.

---

## 5. Relation to Pessimistic Admission

The same lesson becomes even more important for pessimistic admission.

The PostgreSQL pessimistic admission gate uses a transaction-scoped advisory lock.

That means the lock is meaningful only while the surrounding transaction remains open.

The intended flow is:

```text
prepare_stream(order_id)
  → acquire transaction-scoped stream lock

load accepted history
rehydrate aggregate
create candidate event
run Compass validation
append accepted event
record idempotency result

commit / rollback
  → release transaction-scoped lock
```

If `autocommit` is enabled, the lock can be acquired and released within the single SQL statement that requested it.

That would collapse the intended protection:

```text
prepare_stream(order_id)
  → lock acquired
  → statement ends
  → transaction ends
  → lock released immediately

later:
  load history
  validate
  append
  without the intended stream lock protection
```

This would make the pessimistic gate look correct at the API level while failing at the physical database boundary.

That is why the PostgreSQL pessimistic admission gate must reject `autocommit=True`.

The check is not cosmetic.

It preserves the physical meaning of a transaction-scoped lock.

---

## 6. Corrected Boundary Model

The corrected model separates several boundaries:

| Boundary | Question Answered |
|---|---|
| Domain legality | Can this command produce a candidate event in the aggregate's current state? |
| Compass validation | Does the candidate event's transition claim match accepted-history truth? |
| Idempotency | Is this request new, replayed, or conflicting? |
| Admission | Can this candidate event occupy the next accepted-history stream position? |
| UnitOfWork / transaction | Do the durable writes commit or roll back together? |
| Autocommit setting | Is the application actually controlling the transaction boundary? |

The mistake would be to expect one layer to do another layer's job.

Examples:

- Compass validation does not replace transaction atomicity.
- Idempotency does not replace concurrency admission.
- Pessimistic locking does not work if the lock's transaction scope is accidentally collapsed.
- Raising a Python exception does not automatically make a database transaction clean.
- A successful `INSERT` is not the same as a committed logical unit of work.

---

## 7. Relation to Traditional ETL Partial Loads

The same pattern appears in traditional ETL.

A partial load can happen when the intended logical batch is larger than the actual commit boundary.

Examples:

```text
ETL intended unit:
  load one complete file

physical commit behavior:
  commit every 10,000 rows
```

If the load fails after 80,000 rows, the target table may contain only the committed chunks.

This is not always wrong.

Some ETL systems intentionally choose partial progress for throughput or restartability.

But then they need additional design patterns:

- staging tables
- load batch IDs
- checkpoint metadata
- idempotent upserts
- quarantine / bad-row tables
- final validation before publishing
- atomic table swap
- reconciliation queries

Without those patterns, partial loads become silent semantic debt.

The lesson for this project is not that ETL is bad.

The lesson is:

> When a system allows partial physical progress, it must also preserve enough durable evidence to make recovery, replay, or reconciliation safe.

---

## 8. Why "Just Throw an Error" Is Not Enough

A Python exception reports that the application flow failed.

It does not by itself decide what happens to the database transaction.

These are different layers:

| Action | Layer | Purpose |
|---|---|---|
| `raise` | Python runtime | notify the caller that the flow failed |
| `rollback()` | PostgreSQL transaction | undo uncommitted durable changes and clean transaction state |
| `commit()` | PostgreSQL transaction | make the transaction's durable changes visible and permanent |

A correct failure path usually needs both:

```text
rollback database state
then propagate the error or structured result
```

For Stage 3.5B, the write-side UnitOfWork should ensure:

```text
exception leaves with-block
  → rollback

normal completion leaves with-block
  → commit
```

For Stage 4, the project may later map some domain or semantic failures into structured outcomes instead of raw exceptions.

But that future error model does not remove the need for rollback at the physical transaction boundary.

---

## 9. Practical Rule for `autocommit`

The practical rule is:

> Any flow that relies on transaction-scoped behavior must require `autocommit=False`.

This includes:

- transaction-scoped advisory locks
- multi-step durable writes
- append + idempotency atomicity
- rollback-based cleanup
- any write-side flow where several operations must succeed or fail together

For pessimistic admission, the rule is stricter:

> A transaction-scoped stream lock is not meaningful unless the same transaction also covers the protected work.

Therefore:

```text
pg_try_advisory_xact_lock
requires
an explicit transaction boundary
```

If `autocommit=True`, the gate should return an infrastructure-level admission failure rather than pretending the lock is active.

---

## 10. What This Postmortem Does Not Claim

This postmortem does not claim:

- every CRUD project is unsafe
- every ETL partial load is a bug
- every partial write is caused by `autocommit`
- all bulk loads should be one giant transaction
- PostgreSQL transactions alone solve semantic correctness
- pessimistic locking should always be preferred over optimistic admission

The point is narrower:

> The physical transaction boundary must match the correctness guarantee the system claims to provide.

If the project claims that several durable writes form one semantic state transition, those writes must share one transaction boundary.

If the project claims that a pessimistic lock protects a stream-critical section, the lock lifetime must actually cover that section.

---

## 11. Relation to Stage 3.5B and PR5

This lesson fits the Stage 3.5B durable write-side sequence:

```text
PR2:
  durable accepted event storage

PR3:
  durable idempotency storage

PR4:
  transactional write-side composition

PR5:
  PostgreSQL-backed concurrency admission
```

PR4 introduced the need to commit or roll back accepted event append and idempotency record persistence together.

PR5 introduces the need to preserve stream admission meaning across PostgreSQL's physical lock and transaction behavior.

During PR5, this lesson directly leads to a concrete implementation rule:

```text
PostgresPessimisticAdmissionGate
→ must reject autocommit=True
→ before relying on transaction-scoped advisory locks
```

This guardrail is not cosmetic.

It prevents the system from pretending that a transaction-scoped stream lock is protecting the write-side critical section when the physical transaction boundary has already collapsed.


Therefore this postmortem is a bridge between PR4 and PR5:

```text
PR4:
  transaction atomicity for durable writes

PR5:
  admission correctness under concurrent writers

shared lesson:
  physical database boundaries must preserve semantic intent
```

---

## 12. Practical Rules Going Forward

### Rule 1: Do not confuse statement success with transaction success

A successful `INSERT` means the statement executed.

It does not mean the full logical operation has committed.

### Rule 2: The UnitOfWork boundary must match the intended durable unit

If event append and idempotency record must succeed together, they must share the same transaction.

### Rule 3: Transaction-scoped locks require explicit transaction control

A transaction-scoped advisory lock is meaningless if the transaction ends immediately after lock acquisition.

### Rule 4: `autocommit=True` must be treated as incompatible with pessimistic admission

The gate should reject this configuration instead of silently weakening the lock boundary.

### Rule 5: Partial writes require either atomicity or durable recovery evidence

If the system intentionally permits partial progress, it must also preserve enough metadata to resume, reconcile, or quarantine safely.

### Rule 6: A Python exception is not a database cleanup policy

Errors should be propagated or mapped intentionally, but database state must still be committed or rolled back explicitly.

---

## 13. Updated Mental Model

The old mental model was:

```text
run SQL
if it fails, throw an error
```

The corrected model is:

```text
define the logical unit of work
open a transaction boundary around that unit
execute the required statements
commit if the unit succeeds
rollback if the unit fails
ensure any lock lifetime covers the work it claims to protect
```

For this project, the model becomes:

```text
candidate event creation
  is not accepted history

Compass validation
  is not persistence admission

admission
  is the right to occupy the next stream position

append
  is the physical write attempt

commit
  makes the accepted fact durable

rollback
  removes partial uncommitted writes

autocommit=True
  can collapse the intended transaction boundary
```

---

## 14. Final Lesson

The final lesson is:

> `autocommit` is not just a convenience setting.  
> It changes the physical size of the transaction boundary.

For simple independent CRUD operations, small transaction boundaries may be acceptable.

For a semantic write-side pipeline, the transaction boundary is part of the correctness model.

In **Streaming System + Compass**, this means:

- accepted event append and idempotency record persistence must commit or roll back together
- transaction-scoped admission locks must live long enough to protect the stream-critical section
- failure should not leave half-written durable state
- physical transaction behavior must preserve semantic intent

That is the main insight this postmortem preserves.

---

## Suggested Follow-Up

Use this postmortem as a bridge note between Stage 3.5B PR4 and PR5.

Possible follow-up work:

- reference this note from `docs/postmortems/README.md`
- keep tests proving pessimistic admission rejects `autocommit=True`
- document `autocommit=False` as a requirement for transaction-scoped admission
- link this note from ADR 0012 and PR5 roadmap documentation
- keep structured domain error mapping deferred to Stage 4
- keep write-side attempt audit and partial-progress recovery modeling deferred to Stage 5
- avoid treating transaction atomicity, semantic validation, and concurrency admission as interchangeable guarantees
