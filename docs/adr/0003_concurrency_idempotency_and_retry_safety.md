# ADR 0003: Concurrency Control, Idempotency, and Retry Safety

[← Back to Architecture Decision Records Index](README.md)


## Status

Accepted

---

## Implementation Status

Accepted and implemented at baseline level across the Stage 3.5B durable write-side path.

Implemented by:

- Stage 3.5B PR3 — `PostgresIdempotencyStore`
- Stage 3.5B PR4 — Transactional Semantic Write-Side Boundary
- Stage 3.5B PR5 — PostgreSQL Concurrency Admission Boundary
- Stage 3.5B PR6 — Validation Placement Strategy Boundary / Stage 4 Prelude

Related implementation notes:

- [Stage 3.5B Implementation Notes](../implementation_notes/stage_3_5b/)
- [Stage 3.5B PR Breakdown](../implementation_notes/stage_3_5b/pr_breakdown.md)

Related source files:

- `src/storage/postgres_event_store.py`
- `src/storage/postgres_idempotency_store.py`
- `src/storage/postgres_optimistic_admission_gate.py`
- `src/storage/postgres_pessimistic_admission_gate.py`
- `src/pipeline/postgres_transactional_write_side.py`

Related tests:

- `tests/integration/storage/test_postgres_event_store.py`
- `tests/integration/storage/test_postgres_idempotency_store.py`
- `tests/integration/storage/test_postgres_admission_gate.py`
- `tests/integration/pipeline/test_postgres_transactional_write_side.py`

The current implementation does not yet implement the future outbox boundary discussed in this ADR. The accepted baseline covers request identity, durable idempotency, stale-write rejection, explicit concurrency admission, and transactionally coordinated accepted-event / idempotency persistence.

---

## Context

The transactional path of this project must handle command execution under realistic failure conditions.

A command may be processed while:

- multiple workers operate on the same order
- the same request is retried or redelivered
- a worker reads stale state
- a database commit succeeds but the worker does not receive the response
- one worker updates state while another worker is still acting on an older view

The project therefore needs a clear distinction between two related but different concerns:

1. **Concurrency control**
   - determines whether an operation is allowed to write based on the current authoritative state
   - protects the system from stale reads becoming successful stale writes

2. **Idempotency / retry safety**
   - determines whether an incoming request is the same external operation being retried
   - protects the system from executing the same external intent more than once

These concerns often appear together in production systems, but they should not be treated as the same mechanism.

---

## Problem

A typical command flow looks like this:

```text
read current state
→ check whether the transition is allowed
→ write new state
```

The problem is that this sequence is not atomic as a whole.

For example, suppose the current order state is:

```text
order_A
status = CREATED
version = 1
```

Two workers may both read this same state:

```text
Worker A reads: CREATED / version 1
Worker B reads: CREATED / version 1
```

Both workers may then believe they are allowed to perform the same transition:

```text
CREATED -> PAID
```

or competing transitions:

```text
Worker A: CREATED -> PAID
Worker B: CREATED -> CANCELLED
```

The core danger is not merely that a worker can read stale state.

The real danger is:

> a worker reads stale state, makes a decision from that stale state, and still successfully writes based on it.

The system must allow stale reads to be harmless while preventing stale writes from succeeding.

---

## Decision

The project will separate concurrency control from idempotency.

### 1. Concurrency control uses version-based conditional writes

The first concrete concurrency strategy is optimistic version-based control.

A write must include the expected current state and version:

```sql
UPDATE orders
SET status = :new_status,
    version = version + 1
WHERE order_id = :order_id
  AND status = :expected_status
  AND version = :expected_version;
```

The write succeeds only if the authoritative storage still matches the worker's expected state.

A stale read is therefore allowed, but a stale write must not succeed.

### 2. Idempotency uses request identity

Idempotency is handled through a request-level identity such as:

```text
request_id
operation_id
command_id
```

The request ID answers a different question:

> Is this the same external operation being retried or redelivered?

If the same request ID is seen again, the system should return the previous result or safely continue recovery without executing the same external intent twice.

### 3. Failed conditional writes must trigger latest-state reload

If a conditional write affects zero rows, the worker must not blindly retry from the old state.

Instead, it must reload the latest authoritative state and classify the result:

1. **Already achieved**
   - the requested goal has already been reached by another worker

2. **Retryable under latest state**
   - the command can still be applied using the new version and status

3. **Conflict / reject**
   - the latest state no longer allows the requested operation

---

## Core Concepts

### Concurrency

Concurrency means multiple execution units operate over overlapping time on the same shared state.

The operations may be different:

```text
Worker A: CREATED -> PAID
Worker B: CREATED -> CANCELLED
```

or the same:

```text
Worker A: CREATED -> PAID
Worker B: CREATED -> PAID
```

The important point is not whether the actions are identical.

The important point is that multiple workers may make decisions from overlapping or stale views of the same entity state.

### Idempotency

Idempotency means the same external operation can be retried or redelivered without creating duplicate semantic effects.

For example:

```text
request_id = req_123
action = PAY
order_id = order_A
```

If the same request is delivered again, it should not create a second payment effect.

### Worker vs Request Identity

A worker is the executor.

A request ID is the identity of the external operation.

Different workers may process the same request ID if a queue redelivers a message after crash, timeout, or missing acknowledgement.

Therefore:

```text
Different worker + same request_id
= same external operation retried or redelivered
= idempotency / retry safety
```

But:

```text
Different worker + different request_id
= different external operations competing over the same state
= concurrency control
```

---

## Runtime Flow

The intended command-handling flow is:

```text
1. Receive command with request_id, order_id, and action
2. Check request_id in the idempotency store
3. If request_id was already completed, return the previous result
4. Load the current authoritative order state
5. Check domain transition legality
6. Attempt a version-based conditional write
7. If the write succeeds, record the request result and return success
8. If the write fails, reload the latest authoritative state
9. Classify the latest state as already-achieved, retryable, or conflicting
10. Return the appropriate result
```

Conceptually:

```text
command
→ idempotency check
→ load current state
→ domain transition check
→ conditional write with expected version
→ success OR reload latest state
→ already achieved / retry / conflict
```

---

## Example: Same Action, Different Requests

Initial state:

```text
order_A
status = CREATED
version = 1
```

Two different requests arrive:

```text
Worker A: request_id = req_A, action = PAY
Worker B: request_id = req_B, action = PAY
```

Both workers may read:

```text
CREATED / version 1
```

Worker A attempts:

```sql
UPDATE orders
SET status = 'PAID',
    version = version + 1
WHERE order_id = 'order_A'
  AND status = 'CREATED'
  AND version = 1;
```

If Worker A succeeds:

```text
affected rows = 1
order_A = PAID / version 2
```

Worker B then attempts the same conditional update:

```sql
UPDATE orders
SET status = 'PAID',
    version = version + 1
WHERE order_id = 'order_A'
  AND status = 'CREATED'
  AND version = 1;
```

Because the authoritative state is now:

```text
PAID / version 2
```

Worker B receives:

```text
affected rows = 0
```

Worker B must reload the latest state.

If it sees:

```text
PAID / version 2
```

then the requested goal has already been achieved.

The worker may return a success-like response such as:

```text
already paid
```

This is still a concurrency case because the request IDs are different, even though the action is the same.

---

## Example: Different Actions, Conflicting Requests

Initial state:

```text
order_A
status = CREATED
version = 1
```

Two requests arrive:

```text
Worker A: request_id = req_A, action = PAY
Worker B: request_id = req_B, action = CANCEL
```

Worker A succeeds first:

```text
order_A = PAID / version 2
```

Worker B's stale conditional update fails:

```text
affected rows = 0
```

Worker B reloads the latest state:

```text
PAID / version 2
```

The worker must then ask the domain model:

```text
Can the requested cancellation still be applied from PAID?
```

Possible outcomes:

- if `PAID -> CANCELLED` is allowed, retry with expected version 2
- if cancellation is no longer allowed, reject as conflict
- if the domain requires refund instead of cancellation, return a domain-specific rejection or alternative action

---

## Example: Same Request Redelivered to a Different Worker

A user submits one payment request:

```text
request_id = req_123
action = PAY
order_id = order_A
```

The message is delivered to Worker A:

```text
Worker A handles req_123
```

Worker A may successfully commit the order update but crash before acknowledging the queue.

The queue cannot know whether Worker A completed the operation, so it redelivers the same message:

```text
Worker B handles req_123
```

This is not a new external operation.

Worker B must first check the idempotency store:

```text
Has req_123 already been processed?
```

If the request was already completed, Worker B returns the existing result and does not execute the semantic effect again.

This is an idempotency / retry-safety case, not a normal concurrency conflict.

---

## Ambiguous Commit Handling

A worker may send a commit to the database, the database may commit successfully, but the worker may fail to receive the response because of a network issue.

This creates an ambiguous commit:

```text
The database may have succeeded,
but the worker does not know the result.
```

The system must not blindly repeat the operation as if it certainly failed.

Instead, the request ID or operation ID must allow the worker to recover the result:

```sql
SELECT result_status
FROM operations
WHERE request_id = :request_id;
```

If the operation is recorded as successful, the retry should return that result.

If there is no committed operation record, the request may be safely retried according to the idempotency protocol.

---

## Classification After Conditional Write Failure

When a conditional write fails, the worker must reload the latest authoritative state.

After reload, it should classify the situation as one of the following.

### 1. Already achieved

The requested target state already exists.

Example:

```text
Requested: PAY
Latest: PAID / version 2
```

Result:

```text
return already paid or success-like response
```

### 2. Retryable under latest state

The requested operation can still be applied, but only from the latest version.

Example:

```text
Requested: SHIP
Old read: CREATED / version 1
Latest: PAID / version 2
```

If the domain allows:

```text
PAID -> SHIPPED
```

then retry using:

```text
expected_version = 2
expected_status = PAID
```

### 3. Conflict / reject

The latest state no longer allows the requested operation.

Example:

```text
Requested: CANCEL
Latest: SHIPPED / version 3
```

If the domain does not allow cancellation after shipment, return a conflict or domain rejection.

---

## Reload Source and Cost

Reload means obtaining the latest authoritative state after a failed conditional write.

It does not necessarily mean replaying the full event stream from the beginning on every conflict.

Possible reload sources include:

- full event-history rehydration
- snapshot-assisted rehydration
- a transactionally maintained current-state table
- an aggregate state record maintained at the persistence boundary

The baseline implementation may use full rehydration for semantic clarity.

As event streams grow, snapshot-assisted rehydration may be introduced to reduce replay cost.

However, snapshotting is not a concurrency-control mechanism.

It is a replay / reload performance optimization.

The concurrency invariant remains unchanged:

> stale writes must not become accepted writes.

---

## High Contention Trade-offs

The baseline strategy uses optimistic concurrency control because it keeps the low-contention path simple and efficient.

In the common case, a worker reads the latest state, validates the transition, and the conditional write succeeds without waiting for explicit locks.

However, under high contention, many workers may read the same version while only one conditional write succeeds.

For example:

```text
Worker A reads version 10 → update succeeds to version 11
Worker B reads version 10 → update fails
Worker C reads version 10 → update fails
Worker D reads version 10 → update fails
```

The failed workers must reload latest state and classify their results.

This can increase:

- database read/write pressure
- reload cost
- retry cost
- tail latency
- conflict-handling complexity

If contention becomes a bottleneck, future strategies may include:

- pessimistic locking for stronger serialization of hot entities
- single-writer or actor-style processing per entity key
- partitioning or sharding by entity ID to improve overall throughput
- retry backoff and jitter to reduce retry storms
- snapshot-assisted reload to reduce the cost after conflicts occur

These strategies are not required for the current baseline.

They are documented as future options if observed contention patterns justify them.

They do not replace the semantic requirement that stale writes must not succeed.

They only change how the system manages contention, waiting, retries, and recovery cost.

---

## Boundary Clarification: Snapshot, Contention, and Retry

The mechanisms discussed in this ADR solve different parts of the problem.

| Mechanism | Primary Concern | What It Does Not Solve |
|---|---|---|
| Version-based conditional write | Prevent stale writes | Does not prevent stale reads |
| Request ID / operation ID | Safe retry and redelivery | Does not serialize competing requests |
| Latest-state reload | Recover after stale write rejection | Does not reduce conflict frequency by itself |
| Snapshot-assisted rehydration | Reduce reload / replay cost | Is not a concurrency-control mechanism |
| Pessimistic locking | Serialize hot writes | May reduce throughput and increase waiting |
| Single-writer per key | Turn same-key concurrency into ordered processing | Does not distribute one hot key across many writers |
| Sharding / partitioning | Improve throughput across many keys | Does not remove contention inside one hot key |
| Backoff and jitter | Reduce retry storms | Does not decide semantic correctness |

This ADR only commits to the baseline mechanism:

```text
request identity + version-based conditional write + latest-state reload + result classification
```

Other mechanisms remain future optimization or strategy-selection options.

---

## Relationship to Existing Architecture

This decision extends the earlier stateless registry decision.

The registry remains an orchestration boundary.

It should coordinate:

- idempotency lookup
- aggregate rehydration or state loading
- candidate event production
- transition validation
- conditional persistence
- latest-state reload after failed writes
- response classification

However, the registry should not treat local memory as authoritative truth.

The authoritative write decision belongs at the persistence boundary through version-based conditional writes or equivalent event-store append checks.

---

## Relationship to Event Sourcing

For an event-sourced implementation, the same idea can be expressed as an atomic append with an expected version.

Instead of updating an order row, the event store may enforce:

```text
append event only if current stream version == expected_version
```

A relational table can enforce this with a uniqueness constraint such as:

```sql
UNIQUE(order_id, version)
```

The principle is the same:

> only one event can become the next accepted version for a given aggregate stream.

Snapshots may later accelerate aggregate rehydration, but they should not become an unverified independent truth source.

The event history remains the durable semantic history.

---

## Relationship to Compass

This ADR does not define Compass validation semantics.

Compass remains responsible for semantic validation, such as:

- transition truth
- claimed predecessor correctness
- proof / provenance consistency
- later state-level invariant checks

This ADR defines the transactional runtime safety boundary that prevents stale or duplicated execution from corrupting the accepted event history.

Compass validation can run before persistence, but accepted persistence still needs concurrency protection.

In other words:

```text
Compass decides whether a candidate event is semantically trustworthy.
Concurrency control decides whether that candidate can still be written as the next accepted fact.
Idempotency decides whether the external operation has already been processed.
```

---

## Relationship to Projection

Projection should consume only accepted event history.

This ADR focuses on the write-side admission and persistence boundary.

Projection worker retry, checkpoint recovery, and duplicate event consumption are separate projection-layer concerns and should be documented separately.

---

## Future Consideration: External Side Effects and Outbox

This ADR focuses on transactional state admission, concurrency control, and retry safety.

It does not yet define the full delivery mechanism for external side effects such as:

- downstream event publication
- notification delivery
- warehouse integration
- payment-provider calls
- refund-provider calls
- email or webhook delivery

If accepted commands later trigger external side effects, the system should avoid executing those side effects directly inside the request handler without a durable coordination record.

A future implementation may use the Outbox Pattern:

```text
BEGIN
  persist accepted state change or accepted event
  persist operation result for request_id / operation_id
  persist outbox record for downstream publication
COMMIT

background publisher reads outbox
→ publishes downstream event or side effect request
→ marks outbox record as delivered or retryable
```

The goal is to make the state change and the intent to publish a side effect atomic within the local database transaction.

This helps avoid situations such as:

```text
state update succeeded, but downstream message was lost
```

or:

```text
downstream message was published, but local state did not commit
```

Outbox is not treated as a concurrency-control mechanism in this ADR.

It is documented as a future reliability boundary for side-effect consistency.

The key distinction is:

```text
Concurrency control protects accepted state history.
Idempotency protects repeated external intent.
Outbox protects reliable side-effect publication after accepted state change.
```

---

## Consequences

### Positive Consequences

- stale reads cannot become successful stale writes
- idempotency is clearly separated from concurrency control
- worker retry and queue redelivery become easier to reason about
- ambiguous commits can be resolved using request identity
- the registry remains an orchestration layer rather than a local truth store
- event admission becomes safer under multi-worker execution
- the design aligns with future database-backed or event-store-backed persistence
- high-contention trade-offs are explicitly acknowledged
- reload cost is separated from concurrency-control semantics
- external side-effect delivery is documented as a separate future boundary

### Negative Consequences

- command handling becomes more complex
- failed writes require latest-state reload and classification
- request result storage must be designed carefully
- ambiguous commit handling requires explicit operation records
- the system must distinguish success, already-achieved, retryable, and conflict outcomes
- optimistic concurrency may cause repeated reloads and retries under high contention
- future side-effect delivery may require an outbox table and publisher worker

These costs are accepted because they make the transactional path safer and more production-realistic.

---

## Implementation Guidance

The initial implementation should stay small.

Recommended minimum behavior:

1. represent every external command with a `request_id`
2. store request processing result in an idempotency store
3. use version-based conditional writes at the persistence boundary
4. treat `affected rows = 0` or expected-version mismatch as a concurrency conflict
5. reload latest authoritative state after conflict
6. classify the outcome as already-achieved, retryable, or rejected
7. keep worker identity separate from request identity
8. keep snapshotting optional and treat it as replay-performance optimization
9. document high-contention strategy options without implementing them prematurely
10. keep external side-effect delivery outside the core request handler until an outbox boundary is introduced

For in-memory prototypes, the same principle should be modeled explicitly even if true database isolation is not yet present.

For database-backed implementations, use:

- transactions
- conditional updates
- unique constraints
- request result records
- authoritative reads from primary storage when resolving conflicts

For later production-grade extensions, consider:

- snapshot-assisted rehydration when replay cost becomes significant
- pessimistic locking or single-writer processing when same-key contention becomes significant
- partitioning or sharding when many different entities need higher throughput
- retry backoff and jitter when retry storms appear
- outbox-based side-effect delivery when accepted commands must publish downstream effects

---

## Non-Goals

This ADR does not define:

- the full snapshot strategy
- the projection worker recovery protocol
- the detailed outbox publisher design
- Kafka exactly-once semantics
- distributed transaction / two-phase commit design
- complete sharding or actor-model implementation
- Compass validation semantics

Those concerns should be documented separately if and when they become part of the implementation roadmap.

---

## Summary

This project separates concurrency control from idempotency.

Concurrency control answers:

> Can this operation still write based on the current authoritative state?

Idempotency answers:

> Is this the same external operation being retried or redelivered?

Outbox, if introduced later, answers:

> How do we reliably publish side effects after an accepted state change?

The first concrete strategy is:

- use `request_id` for idempotency and retry safety
- use version-based conditional writes for concurrency control
- reload latest state after failed conditional writes
- classify the latest state as already achieved, retryable, or conflicting
- treat snapshots as reload / replay optimization, not concurrency control
- treat pessimistic locking, single-writer processing, sharding, and backoff as future contention-management strategies
- treat outbox as a future side-effect consistency boundary

The central invariant is:

> A stale read may happen, but a stale write must not succeed.
