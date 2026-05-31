# Pre-Transaction Read Cleanup Boundary

[← Back to Postmortems Index](README.md)

**Recorded on:** 2026-05-31

## Context

Stage 3.5B PR6 introduces validation placement strategy.

One goal of PR6 is to support a second write-side orchestration mode:

```text
PRE_TRANSACTION validation
```

In this mode, Compass validation runs before the PostgreSQL write-side unit of work.

The intended shape is:

```text
preliminary read phase
→ aggregate rehydration
→ candidate event creation
→ Compass validation

BEGIN / write-side UoW
→ authoritative idempotency re-check
→ stream preparation
→ append-time admission
→ idempotency record persistence
→ COMMIT
```

This is different from the existing `IN_TRANSACTION` baseline, where accepted-history loading, candidate-event creation, Compass validation, admission, append, and idempotency recording all happen inside the PostgreSQL unit-of-work boundary.

---

## Problem

`PRE_TRANSACTION` sounds like validation happens outside the database transaction.

Logically, that is the goal.

Physically, however, a PostgreSQL driver connection may still open an implicit transaction even for read-only `SELECT` operations when the connection is not in autocommit mode.

That means a preliminary read phase such as:

```text
idempotency check
→ accepted-history load
```

can still leave the connection inside an open PostgreSQL transaction unless the connection state is explicitly cleaned up.

This creates a subtle mismatch:

```text
architecture claim:
validation runs before the write transaction

physical reality without cleanup:
the same connection may still carry an implicit read transaction
while validation runs
```

The issue is not that business writes are being committed too early.

The issue is that connection transaction state can leak across a boundary that the architecture intends to keep separate.

---

## Why This Is Dangerous

If the preliminary read phase does not guarantee cleanup, several production-class failures can appear.

### 1. Connection returned to a pool with dirty transaction state

In a production service, connections are often reused through a connection pool.

Without cleanup, the sequence could become:

```text
request A
→ gets connection from pool
→ starts preliminary read
→ read fails or returns early
→ implicit transaction remains open or failed
→ connection is returned to pool

request B
→ receives the same connection
→ attempts unrelated SQL
→ inherits stale / failed transaction state
→ receives confusing database errors
```

The second request may fail even though its own logic is correct.

This creates a cross-request infrastructure leak.

The bug is difficult to diagnose because the failure appears in request B, while the cause happened in request A.

---

### 2. Failed transaction state blocks later SQL

If a PostgreSQL statement fails inside an open transaction, the transaction can remain in an aborted state until rollback.

If the code does not explicitly rollback, later statements on the same connection may fail with errors that are unrelated to their own SQL.

The system then appears unstable:

```text
one failed read
→ connection remains in failed transaction state
→ later commands fail
→ failures look non-deterministic
```

This is especially dangerous when the connection is reused.

---

### 3. Long-running implicit read transactions

Even when reads succeed, leaving an implicit transaction open during CPU-side validation can extend transaction lifetime.

For example:

```text
load accepted history
→ implicit read transaction remains open
→ Compass validation runs for 500ms / 2s / 10s
→ transaction is still open during validation
```

This weakens the purpose of `PRE_TRANSACTION`.

The system claims to keep validation outside the PostgreSQL transaction, but the connection may still hold transaction resources during validation.

In larger deployments, this can increase:

- connection pool pressure
- transaction duration
- snapshot lifetime
- lock visibility complexity
- operational confusion during debugging

---

### 4. Validation placement becomes physically misleading

`PRE_TRANSACTION` is not just a logical placement label.

It makes a physical promise:

```text
Compass validation should not run while the PostgreSQL write transaction is open.
```

If the preliminary read transaction is not explicitly closed, then the code may appear placement-aware while still carrying database transaction state across the validation boundary.

This makes future timing and observability misleading.

For example, Stage 4 may later measure:

```text
validation_time_ms
transaction_total_ms
lock_duration_ms
```

Without cleanup, those numbers could be interpreted incorrectly because the system may still hold transaction state during the supposed non-transaction validation phase.

---

## Corrected Model

`PRE_TRANSACTION` validation requires two separate guarantees:

```text
1. Validation must run outside the write-side Unit of Work.
2. Preliminary read transactions must be explicitly closed before validation starts.
```

Therefore the preliminary read phase should use a cleanup boundary:

```python
try:
    preliminary_idempotency_decision = read_idempotency_store.check(signature)

    if preliminary_idempotency_decision.verdict == IdempotencyVerdict.REPLAY:
        return PostgresWriteSideResult(...)

    if preliminary_idempotency_decision.verdict == IdempotencyVerdict.CONFLICT:
        return PostgresWriteSideResult(...)

    history = read_event_store.load(order_id)
finally:
    connection.rollback()
```

This rollback is not rolling back accepted business writes.

It closes the implicit read transaction and returns the connection to a clean state before CPU-side Compass validation begins.

---

## Why `try/finally` Matters

The cleanup must happen whether the read phase:

- succeeds
- returns early due to replay
- returns early due to conflict
- raises an exception during idempotency lookup
- raises an exception during accepted-history loading

The reusable rule is:

```text
Every preliminary database read phase that intentionally precedes non-transaction CPU work must leave the connection clean before that CPU work starts.
```

This is a resource-lifecycle guarantee.

It is similar in spirit to transaction atomicity because both prevent the system from being left in a half-finished state.

But it is not the same as data transaction atomicity.

A more precise name is:

```text
connection-state cleanup guarantee
```

or:

```text
pre-transaction read cleanup boundary
```

---

## Relationship to Transaction Atomicity

Transaction atomicity protects durable data:

```text
accepted event append
+
idempotency record persistence
→ commit together or rollback together
```

The pre-transaction read cleanup boundary protects connection state:

```text
preliminary read transaction
→ always closed before validation
```

These are different guarantees.

However, both enforce the same design habit:

```text
do not allow the system to remain in an ambiguous intermediate state
```

---

## Relationship to PR6

This lesson directly supports Stage 3.5B PR6.

PR6 is not only about adding an enum:

```text
ValidationPlacement.IN_TRANSACTION
ValidationPlacement.PRE_TRANSACTION
```

It also has to ensure that the physical execution behavior matches the placement label.

For `PRE_TRANSACTION`, this means:

```text
preliminary reads may touch PostgreSQL
but Compass validation must not accidentally run while the connection
still holds an implicit read transaction
```

The `try/finally` cleanup pattern is therefore part of the physical boundary behind validation placement strategy.

---

## Relationship to Future Stage 4

Stage 4 may later introduce:

- structured semantic outcomes
- runtime decision policy
- validation timing evidence
- registry-stage timing
- runtime evidence persistence
- action safety gates

Those later layers depend on the runtime path being physically meaningful.

If the system records `PRE_TRANSACTION` as the placement, the actual connection behavior must support that claim.

Otherwise, future evidence could say:

```text
validation_placement = PRE_TRANSACTION
```

while the connection still carried transaction state during validation.

That would make timing and operational evidence less trustworthy.

---

## Deferred Follow-up: Cleanup Failure Handling

This postmortem records the need to guarantee cleanup of implicit read transactions before CPU-side validation starts.

The current PR6 baseline can use a simple cleanup pattern:

```python
try:
    ...
finally:
    connection.rollback()
```

This is sufficient for the current local PostgreSQL and non-pooled connection baseline because it guarantees that cleanup is attempted before validation, early return, or exception propagation.

However, this does not fully solve future production-grade cleanup failure handling.

A future Stage 4 error model or connection-pool hardening pass should distinguish:

```text
primary read failure
vs
cleanup rollback failure
```

The reason is that rollback itself may fail if the connection is already closed, aborted, or physically broken.

If a primary read failure and a rollback cleanup failure happen together, the cleanup failure may mask the original error.

If rollback fails without any primary error, the system should not silently continue as if the connection state were clean.

A future hardened version may need to:

- preserve the primary error when cleanup also fails
- attach cleanup failure as diagnostic context
- map cleanup failure into a structured infrastructure error
- mark the connection as unsafe for reuse
- discard or invalidate the connection when connection pooling exists
- emit logs, metrics, or traces for cleanup failure

This is intentionally deferred because the current project does not yet own:

- a connection pool abstraction
- connection invalidation policy
- production observability
- Stage 4 structured error model
- durable infrastructure-error evidence

Future rule:

```text
simple try/finally cleanup is enough for PR6 placement correctness;
structured cleanup failure handling belongs to Stage 4 / production hardening.
```

---

## Non-Goals

This postmortem does not introduce:

- a new database schema
- a connection pool implementation
- `SemanticOutcome`
- `RuntimeDecisionPolicy`
- registry-stage timing persistence
- production observability integration
- automatic validation placement selection
- production-grade cleanup failure recovery
- connection invalidation policy

It only records the cleanup boundary required for safe pre-transaction validation.

---

## Future Rule

When a flow claims to run outside a transaction, verify both layers:

```text
logical orchestration boundary
+
physical connection state boundary
```

For PR6, that means:

```text
PRE_TRANSACTION validation
= validation outside the write-side UoW
+ preliminary read transaction cleaned up before validation starts
```

The corrected mental model is:

```text
pre-transaction validation is not safe merely because validation is outside `with UoW`.

It is safe only when the connection is also returned to a clean state
between preliminary reads and CPU-side validation.
```
