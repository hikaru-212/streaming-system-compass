# Postmortem: From `created_at` Freshness to Committed-History Boundaries

*Why projection snapshots should trust accepted-history lineage, not row creation time or naive sequence allocation.*

[← Back to Postmortems Index](README.md)

**Recorded on:** 2026-06-14

## Summary

This note records a shift in understanding during Stage 3.5D.

The original question looked like a snapshot loading concern:

> When loading the latest projection snapshot, should the system use `created_at` or `source_global_position`?

At first, the answer seemed simple:

> `created_at` is only the row creation time.
> `source_global_position` is the accepted-history boundary.

That conclusion is correct, but incomplete.

The deeper lesson is:

> A logical cursor is only safe if the system clearly defines what moment it represents.

If `global_position` is assigned before commit, it may represent allocation order, not committed-history order.

That distinction matters because a position may be allocated but never committed.

A projection worker must therefore distinguish:

* temporary visibility gaps,
* permanent allocation gaps,
* visible but unprocessable poison events,
* and valid committed events.

This note explains how the reasoning moved from local PostgreSQL ordering to distributed event-log ordering, and why the system should treat snapshot lineage as a committed-history boundary rather than a wall-clock timestamp or a naive sequence number.

---

## 1. Trigger Question

The trigger was a practical Stage 3.5D snapshot question:

> What does “latest snapshot” mean?

A naive implementation might load the newest snapshot row by creation time:

```sql
ORDER BY created_at DESC
LIMIT 1
```

But this is unsafe.

A snapshot row may be created later even if it represents an older point in event history.

This can happen during:

* offline rebuild,
* snapshot repair,
* reducer migration,
* replay from older history,
* backfill,
* or manual regeneration.

Therefore, the correct ordering is not row creation time.

The intended ordering is:

```sql
ORDER BY source_global_position DESC
LIMIT 1
```

This means:

> Latest means the highest accepted-history source boundary, not the newest snapshot row.

---

## 2. Initial Confusion

The first confusion was:

> Why can `source_global_position` be trusted more than `created_at`?

The answer is that these two fields represent different kinds of time.

```text
created_at
  = physical row creation time

source_global_position
  = logical event-history boundary
```

`created_at` answers:

> When was this derived row written?

`source_global_position` answers:

> How far into accepted history was this derived state computed?

For projection snapshots, the second question is the important one.

A snapshot is not authoritative because it was recently written.
It is useful only because it can prove which accepted event-log boundary it represents.

---

## 3. Boundary Clarification

The next question was deeper:

> If global_position is assigned by the database, does it represent the true order?

The corrected answer is:

> It depends on where the position is assigned.

There are at least two different meanings:

```text
allocation-order position
  = the order in which numbers were assigned

committed-history position
  = the order in which accepted events became durable history
```

If `global_position` is assigned before the transaction commits, then the system can observe this situation:

```text
Transaction A receives global_position = 10.
Transaction B receives global_position = 11.

Transaction B commits first.
Transaction A commits later.
```

A projection worker reading committed rows may temporarily see position 11 before position 10.

This does not necessarily mean the event log is corrupted.

It means the read side is observing committed visibility, while the position may have been assigned earlier.

The worker must not blindly advance from 9 to 11.

It must recognize the missing 10 as a gap.

---

## 4. Temporary Visibility Gap

A temporary visibility gap happens when a lower position exists in an in-flight transaction but is not yet visible to the worker.

Example:

```text
last checkpoint = 9

position 10:
  allocated but not committed yet

position 11:
  allocated and committed

worker query:
  SELECT events WHERE global_position > 9
  returns [11]
```

The worker sees:

```text
expected_next_position = 10
actual_first_position  = 11
```

The safe behavior is:

* do not process 11 yet,
* do not advance the checkpoint,
* wait or retry,
* allow position 10 to become visible.

This protects the read side from skipping an event that may still commit.

---

## 5. Permanent Allocation Gap

The harder case is:

> What if position 10 never commits?

This can happen if a transaction receives a position but later aborts, crashes, disconnects, or loses its host before the row becomes committed history.

Then position 10 is not temporarily invisible.

It is permanently absent.

This creates a different problem:

```text
last checkpoint = 9
visible event = 11
missing position = 10
position 10 will never appear
```

The worker cannot wait forever.

But it also cannot silently skip 10 without a policy.

This means a mature design needs a permanent gap resolution mechanism.

Possible strategies include:

1. avoid pre-commit position allocation for committed-history cursors,
2. assign global positions only through a committed event-log sequencer,
3. use a CDC / WAL-backed committed log,
4. maintain an explicit skipped-position registry,
5. or treat this as an operational incident requiring manual or automated resolution.

The important lesson is:

> A missing position is not the same thing as a bad event.

If the row does not exist, DLQ is not the first concept.
There is no event payload to move into a dead-letter queue.

This is a cursor / sequencing problem.

---

## 6. DLQ Is a Different Boundary

A dead-letter queue handles a different failure mode.

DLQ applies when the event is visible but cannot be processed.

Example:

```text
position 10 exists
position 10 is committed
worker can read it
but the payload is invalid or unsupported
```

For example:

```json
{
  "amount": "one-hundred-dollars"
}
```

The worker can see the event, but cannot safely reduce it into projection state.

That is a poison event.

In that case, the system may:

* retry a limited number of times,
* record the failure,
* move the event to a dead-letter table or queue,
* alert operators,
* and decide whether projection progress may continue.

This is different from an invisible missing position.

```text
Missing position:
  no committed event exists at that position

Poison event:
  committed event exists, but processing fails
```

These two failures need different mechanisms.

---

## 7. Relation to Kafka Partition Ordering

The same reasoning appears in distributed event streams.

Kafka provides ordering within a partition.

It does not provide a natural total order across all partitions.

Therefore, if the system needs causal ordering for one aggregate, all events for that aggregate must use the same partition key.

For orders:

```text
partition_key = order_id
```

This protects per-order causal order:

```text
OrderCreated
  -> OrderPaid
  -> OrderCancelled
```

If events for the same order are randomly routed to different partitions, a later event may arrive before an earlier one.

That creates causal inversion.

Therefore, `order_id` is not only an identifier.

It is also the ordering key for the aggregate.

---

## 8. Global Order Is Expensive

There are two different goals:

```text
per-entity order
  = events for the same order are ordered correctly

global order
  = all events across all orders are placed on one total order
```

Per-entity order can scale by partitioning on the entity key.

Global order requires stronger coordination.

Possible implementations include:

* a single writer,
* a single Kafka partition,
* a global sequencer,
* a consensus log,
* a distributed SQL ordering mechanism,
* or CDC from a committed write-ahead log.

Each option has a cost.

A global order is not free.

It usually trades throughput, availability, latency, or operational complexity for stronger ordering semantics.

---

## 9. Relation to Stage 3.5C and Stage 3.5D

Stage 3.5C introduced the durable read-side baseline and projection worker.

The worker should not treat visible rows as automatically safe progress.

It should preserve checkpoint safety.

Stage 3.5D introduces projection snapshots.

A snapshot should store lineage evidence such as:

```text
source_event_id
source_event_sequence
source_global_position
```

These fields say:

> This snapshot was derived from accepted history up to this boundary.

But Stage 3.5D should avoid overclaiming.

A snapshot source boundary is safe only if the underlying event-log cursor represents committed accepted history, or if the system has a clear policy for missing positions.

---

## 10. Updated Mental Model

The old mental model was too simple:

```text
created_at is bad
global_position is good
```

The corrected model is:

```text
created_at
  tells when a derived row was written

global_position
  should represent accepted-history progress

but the safety of global_position depends on
  when it is assigned,
  whether it can have permanent gaps,
  and how the worker handles missing positions
```

The mature rule is:

> Do not confuse a monotonic number with committed history.

A monotonic number is only a safe event-log cursor when the system defines how it relates to commit, visibility, rollback, and recovery.

---

## 11. Practical Rules Going Forward

### Rule 1: Do not use row creation time as snapshot freshness

Snapshot freshness should be based on the accepted-history boundary the snapshot represents.

### Rule 2: Define what `global_position` means

A `global_position` field must have a precise meaning.

It should not be described vaguely as “real time.”

Better definitions include:

```text
allocation-order cursor
committed-history cursor
event-log append cursor
CDC commit cursor
```

### Rule 3: The worker must not skip unexplained gaps

If the worker expects 10 and sees 11, it should not immediately advance to 11.

It must first determine whether 10 is temporarily invisible, permanently absent, or officially skipped.

### Rule 4: Permanent gaps need an explicit policy

If a position can be allocated but never committed, the system needs one of:

* committed-only position assignment,
* a sequencer that emits only committed events,
* a skipped-position registry,
* CDC/WAL-backed ordering,
* or an operational incident workflow.

### Rule 5: DLQ is for visible poison events, not invisible missing positions

Use DLQ when an event exists but cannot be processed.

Do not use DLQ as the primary explanation for a position that never became committed history.

### Rule 6: Per-entity order and global order are different guarantees

Use `order_id` as the partition key to preserve order-level causal transitions.

Do not assume this automatically creates total global order across all orders.

### Rule 7: A guarantee must exist where the failure can happen

If the failure can happen at commit visibility, the worker must participate.

If the failure can happen at sequence allocation, the sequencing strategy must participate.

If the failure can happen during event processing, DLQ or recovery logs must participate.

If the failure can happen before event admission, Compass validation must participate.

---

## 12. Final Lesson

The final lesson is:

> A derived state is not safe because it is recent.
> It is safe only when it can prove which committed accepted-history boundary it represents.

`created_at` is not enough because it only describes when the derived row was written.

`global_position` is better because it can describe event-log progress.

But `global_position` must be defined carefully.

If it is assigned before commit, then the system must handle temporary visibility gaps and permanent allocation gaps.

If it is assigned only after commit through a committed event-log mechanism, then it better matches the meaning of accepted-history progress.

This postmortem preserves the reasoning path:

```text
created_at freshness failed
  -> source boundary became necessary
  -> global_position required a precise meaning
  -> worker checkpoint safety required gap detection
  -> permanent gaps required recovery policy
  -> DLQ was separated from missing-position handling
  -> distributed ordering required partition-key discipline
```

This is the architectural boundary behind Stage 3.5D snapshot trust.

A snapshot is derived, discardable, and subordinate to accepted history.

Therefore, its trust must come from lineage evidence, not from row recency.
