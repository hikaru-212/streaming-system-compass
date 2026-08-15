# Aggregate-Local Progress, Partition-Local Logs, and Commit-Consistent Boundaries

## Purpose

This note compares three progress and observation models that can look similar
when described only as "local order instead of global order":

1. the repaired PostgreSQL order-state projection introduced by
   [ADR 0020](../adr/0020_per_order_projection_progress_and_order_local_snapshot_tails.md);
2. Kafka key-based routing, partition-local offsets, and transactional
   `read_committed` visibility;
3. WAL / LSN-based committed observation as described by Databricks Lakebase
   and LTAP.

The comparison exists to preserve both the useful analogy and its limits.

The systems share one architectural rule:

> A durable progress marker must not claim a wider completeness boundary than
> its source can actually prove.

They do not implement the same physical mechanism.

ADR 0020 does not implement Kafka partitions inside PostgreSQL. Kafka does not
replace aggregate-local domain sequence. LTAP does not validate an application
reducer or prove that a derived order state is semantically correct.

This is an architecture comparison note, not a new repository decision. The
accepted repository decision remains ADR 0020.

---

## Repository Trigger

The original Stage 3.5C PostgreSQL projection worker persisted one global
scalar checkpoint and resumed with:

```text
WHERE global_position > checkpoint
ORDER BY global_position
```

`order_events.global_position` was allocated by a PostgreSQL sequence during
`INSERT`. PostgreSQL sequence allocation is intentionally not rolled back and
does not wait for earlier transactions to commit.

A deterministic multi-connection PostgreSQL test reproduced this schedule:

```text
T1 inserts order A and allocates P1
T1 remains uncommitted

T2 inserts order B and allocates P2
P1 < P2
T2 commits

worker sees only B/P2
worker applies B and checkpoints P2

T1 commits A/P1
future global-cursor queries exclude A/P1 permanently
```

The defect did not arise because `global_position` values were duplicated.
They remained globally unique.

The defect arose because the worker interpreted:

```text
largest processed visible allocation coordinate
```

as:

```text
complete committed-history frontier
```

PostgreSQL did not provide that implication.

The repaired implementation therefore preserved global uniqueness while
narrowing projection completeness to the domain boundary the current reducer
actually requires: one order stream.

---

## Three Dimensions That Must Remain Separate

The words `global`, `local`, `position`, and `progress` can otherwise collapse
several independent questions into one.

### 1. Event identity and coordinate uniqueness

Question:

> Can two different accepted events use the same `global_position`?

Current answer:

```text
No.
```

`global_position` remains one globally unique coordinate for one accepted row.
This preserves the schema correction recorded in
[From Per-Order Global Position to Global Source Boundary](../postmortems/from_per_order_global_position_to_global_source_boundary.md).

Global uniqueness does not prove global committed completeness.

### 2. Aggregate-local causal order

Question:

> In which order must events for one order be reduced?

Current answer:

```text
(order_id, sequence)
```

For one order:

```text
A1 -> A2 -> A3
```

must be preserved.

Different orders do not currently have a business requirement for one total
causal order:

```text
A1 before B1
```

is not an implemented invariant unless a separate domain relationship says so.

### 3. Projection completeness

Question:

> After applying an event, what other work may the worker permanently consider
> complete?

The old answer was too broad:

```text
processed P2
=> all positions <= P2 are complete
```

The repaired answer is deliberately narrow:

```text
processed order B sequence 1
=> order B is complete through sequence 1
```

Processing B says nothing about A's completion.

---

## Current Compass Projection Model

The repaired order-state projection uses the following roles.

```text
global_position
= globally unique accepted-event coordinate
= lineage evidence
= deterministic tie-breaker among currently eligible events
!= committed-history completeness frontier

(order_id, sequence)
= aggregate-local accepted-event order
= reducer causal order

(projection_name, projection_epoch, order_id)
= projection progress identity

last_sequence
= durable aggregate-local projection frontier
```

An event is eligible when:

```text
event.sequence = COALESCE(progress.last_sequence, 0) + 1
```

The worker may use ascending `global_position` to choose among several events
that are already eligible for their own orders. That scheduling choice does not
advance unrelated orders.

Example:

```text
eligible A3 / P20
eligible B6 / P17
eligible C1 / P25
```

The worker may choose B6 first because P17 is the smallest coordinate. After a
successful transaction, only B's progress advances.

This model provides:

- exact-next application for each order;
- isolation of one order's progress from another order;
- safe handling of a later-visible lower `global_position` belonging to another
  order;
- no obligation for a rolled-back sequence allocation that produced no
  accepted row;
- atomic projection-state and progress persistence.

It does not provide one global committed projection watermark.

---

## Kafka's Partition-Local Model

Kafka divides a topic into a finite set of physical partition logs.

A producer can associate a key with a record. A partitioning strategy uses that
key to choose a partition, commonly by a stable hash. Using `order_id` as the
key is a common way to keep events for one order in one partition.

Conceptually:

```text
order A, order C, order F -> partition 0
order B, order D          -> partition 1
```

Each partition has its own offsets:

```text
partition 0: offset 10, 11, 12, ...
partition 1: offset 90, 91, 92, ...
```

An offset is unique within one partition, not across the whole topic. Consumer
position and committed consumer progress are also partition-local.

Kafka uses partitioning for two related purposes:

- distribute storage, broker request load, and consumer work;
- preserve order and local state within a chosen semantic partition.

Kafka therefore does not need one topic-wide scalar offset that proves progress
across every partition.

### Transactional visibility and Last Stable Offset

Kafka partition offset order must not be simplified to transaction commit
order.

Transactional records can occupy earlier partition offsets while their
transaction remains open. A later record may belong to a transaction that has
already completed.

A `read_committed` consumer does not simply return every individually committed
record it can currently identify. It reads only below the partition's Last
Stable Offset, the boundary before the first open transaction. Records after an
ongoing transaction are withheld until that transaction is committed or
aborted.

Conceptually:

```text
offset 10 / T1 OPEN
offset 11 / T2 COMMITTED
```

A `read_committed` consumer does not deliver offset 11 and permanently move past
10. It waits for T1 to become decided.

If T1 commits:

```text
10 and 11 become consumable in partition order
```

If T1 aborts:

```text
T1's records are excluded
11 can become consumable
```

Kafka converts a possible omission into partition-level waiting. The cost is
transactional head-of-line blocking: one open transaction can delay later
records in the same partition.

### What Kafka partitioning does not prove

Kafka does not provide a total order across partitions.

It also does not prove that an application's domain sequence is valid. If an
application incorrectly writes order A sequence 3 without sequence 2, Kafka can
faithfully retain and deliver that record. Aggregate validation remains an
application responsibility.

Kafka consumer offsets also do not make arbitrary external side effects
exactly once. Processing, state writes, and offset commits still need an
appropriate transactional or idempotent design.

---

## Relationship Between Kafka and ADR 0020

Kafka and ADR 0020 share a boundary-scoping principle:

```text
progress for one ordering scope
must not advance another independent ordering scope
```

The analogy is useful:

| Kafka | Current PostgreSQL projection |
|---|---|
| Record key such as `order_id` identifies related data | `order_id` identifies one aggregate stream |
| Partition preserves a physical local log order | `(order_id, sequence)` preserves logical domain order |
| Consumer progress is partition-local | Projection progress is order-local |
| One partition can lag while another proceeds | One order can have a gap while another proceeds |
| No topic-wide offset proves all partitions complete | No global checkpoint proves all orders complete |

The analogy stops at the physical implementation:

| Kafka partition system | Current PostgreSQL projection |
|---|---|
| Finite number of replicated physical logs | One relational accepted-event table |
| Many keys share one partition | Each order has its own logical progress row |
| Broker assigns partition offsets | PostgreSQL stores global coordinates and order-local sequences |
| Consumer reads an append log | Worker executes an eligible-event relational query |
| LSO controls transactional visibility | PostgreSQL MVCC plus exact-next eligibility controls application |
| Partition leadership and replication | One supported active projection worker |
| Consumer-group assignment and rebalance | No lease, heartbeat, or rebalance protocol |

ADR 0020 therefore resembles Kafka's semantic partitioning at the level of
ordering scope. It does not reproduce Kafka's broker, partition, replication,
transaction, or consumer-group model.

The current progress granularity is also finer than a Kafka partition. A Kafka
partition may contain many unrelated order keys, so one open transaction can
withhold later records for those keys in the same partition. The PostgreSQL
repair allows an order-local gap to block only that order, although the
eligible-event query and progress-table cardinality are the corresponding
costs.

---

## Databricks Lakebase and LTAP

Lakebase and LTAP address a different boundary.

The problem is not primarily:

```text
Which order-local reducer event is next?
```

It is:

```text
How can an analytical query observe one complete, current database state while
most data is already materialized in object storage and the newest committed
changes are still in the log/materialization path?
```

Lakebase externalizes PostgreSQL WAL durability and page materialization into
separate services. LTAP then uses a WAL / LSN-derived observation boundary. An
analytical query obtains a current LSN, reads the large already-materialized
base from object storage, obtains the recent changes not yet materialized, and
merges them into one snapshot-consistent view as of that LSN.

The important distinction is that the boundary is commit-aware database
infrastructure. It is not an application-assigned sequence allocated before
commit.

LTAP preserves a stronger capability than ADR 0020 currently provides:

```text
one commit-consistent database observation boundary
```

That capability has a much larger implementation cost:

- WAL-aware durable storage;
- replication and failure handling;
- MVCC-compatible versions;
- page and columnar materialization;
- recent-tail merge;
- analytical storage and compute isolation.

LTAP still does not prove application reducer correctness. If an order-state
reducer applies the wrong transition, a shared storage lineage can faithfully
serve the wrong derived row. Accepted-history replay and projection validation
remain separate concerns.

---

## Relationship Between LTAP and the Stage 3.5C Defect

The systems share a warning:

```text
an allocation or materialization coordinate
must not be mistaken for a complete committed observation
```

The solutions differ.

### LTAP solution

Preserve a global commit-consistent observation by using a database log
boundary and merging the not-yet-materialized tail.

### ADR 0020 solution

Recognize that the implemented order-state projection does not require a total
cross-order history frontier. Remove the unsafe global completeness claim and
persist exact-next progress for each order.

This leads to a useful design rule:

> When global committed observation is a real requirement, use a commit-aware
> authority such as WAL / LSN, CDC, or another durable log contract. When the
> domain only requires aggregate-local causality, do not manufacture a global
> completeness dependency that the source cannot prove.

---

## Comparison Summary

| Dimension | ADR 0020 PostgreSQL projection | Kafka partition model | Lakebase / LTAP model |
|---|---|---|---|
| Primary question | How far has one order projection safely advanced? | How far has one partition consumer advanced? | What committed database state should an analytical query observe? |
| Boundary identity | Projection + epoch + order | Topic + partition | Database WAL / LSN observation |
| Ordering scope | Aggregate-local | Partition-local | Database transaction / MVCC snapshot |
| Progress value | `last_sequence` per order | Consumer offset per partition | LSN plus materialized-base/tail coverage |
| Global coordinate | `global_position` retained as lineage | No single topic-wide offset | LSN is a global database log coordinate |
| Commit inversion response | Unrelated orders have independent progress | `read_committed` waits at LSO within partition | Read resolves one committed boundary and merges recent tail |
| Rollback / abort | No accepted row, no progress obligation | Aborted transactional records are excluded | Aborted database changes do not become committed state |
| Local gap | That order fails closed | Later partition records may be withheld | Not an aggregate-sequence validator |
| Global completeness watermark | Not provided | Not provided across partitions | Provided for the selected database observation |
| Reducer semantics | Explicit application reducer | Application / stream processor responsibility | Not provided by storage architecture |
| Main cost | Progress rows and eligible-event SQL | Broker, partitions, replication, consumer operations | Distributed storage, WAL, MVCC, materialization, merge |

---

## Why the Current Repository Chooses ADR 0020

The current order-state projection has these properties:

- state is keyed by `order_id`;
- the reducer advances by order-local `sequence`;
- replay authority is one order's accepted history;
- snapshots are one order's derived compression;
- no implemented consumer requires a total order across different orders;
- the current repository does not require a shared OLTP/OLAP storage engine;
- one active projection worker is the supported topology.

Under those requirements, per-order exact-next progress is the smallest
correct contract.

Introducing Kafka solely to fix the reproduced defect would add physical
partitioning, broker operations, consumer offsets, replication, retention, and
transactional-consumption concerns without eliminating the need for
`order_id + sequence` validation.

Introducing WAL / LSN logical decoding solely for this projection would add
replication slots, WAL retention, consumer offset recovery, schema evolution,
failover, and delivery semantics. It could provide a committed global source
stream, but the current projection does not require that stronger boundary.

The decision is therefore not:

```text
Kafka or WAL are inferior.
```

It is:

```text
Their stronger infrastructure contracts are not currently required to prove
this aggregate-local projection correct.
```

---

## Costs and Limitations of Aggregate-Local Progress

The repaired model closes the reproduced omission, but it introduces or retains
important limits.

### No global committed projection watermark

The runtime cannot claim:

```text
all events committed through database point X are projected
```

It can claim only per-order progress.

This matters for future cross-order reporting, global reconciliation, and
analytics freshness guarantees.

### Progress cardinality

Each projection definition and epoch may require one row per encountered
order. With many projections and many aggregates, the progress table becomes a
material storage and index concern.

### Eligible-event query cost

The worker discovers exact-next rows by joining accepted history with per-order
progress. Correctness tests do not prove that this query remains efficient at
production scale. Index review and `EXPLAIN (ANALYZE, BUFFERS)` evidence are
future operational obligations.

### No cross-table transaction delivery boundary

A database transaction may modify several tables or domains. The current
per-order progress model does not automatically preserve that transaction as
one projection-consumption unit.

### Fail-closed gaps require diagnostics

An order-local sequence gap prevents later events for that order from becoming
eligible. This is correct, but `no_event` alone does not distinguish an idle
system from a stalled order. A future gap detector, reconciliation job, or
operator-visible diagnostic is still required.

### Current progress is not a complete processing history

The row records only the latest durable boundary. It does not preserve every
attempt, failure, restart, or transition. Stage 4 runtime trace and attempt
evidence may later provide that diagnostic history.

---

## Future Decision Triggers

The repository should reconsider Kafka, PostgreSQL logical decoding, or another
commit-aware stream when one or more of these requirements become real:

1. many independent downstream consumers require the same committed event
   stream;
2. table polling or eligible-event discovery becomes a demonstrated throughput
   bottleneck;
3. the system requires a global source-to-projection lag watermark;
4. projection work must preserve a transaction spanning several tables or
   aggregates;
5. accepted changes must be delivered to Kafka, a lakehouse, or another
   database;
6. replaying from relational accepted history no longer meets recovery or
   retention needs;
7. analytical readers require a consistent global view as of one database
   commit boundary;
8. multi-worker distribution requires physical ownership, leases, or
   partition assignment.

Even after such an evolution, aggregate-local sequence remains relevant. A
commit-aware delivery stream answers which transaction became durable; it does
not by itself prove that one order's domain transitions are exact-next.

A possible future composition is:

```text
WAL / logical decoding or Kafka
    -> committed delivery boundary
    -> key by order_id
    -> aggregate-local exact-next validation
    -> projection state and durable progress
```

This would combine a global committed source offset with local causal safety,
at the cost of operating both contracts.

---

## Verification Implications

The comparison also implies different proof obligations.

### Current PostgreSQL projection

Must test:

- allocation order versus commit order;
- visibility through independent connections;
- late commit after another order advances;
- rollback allocation gaps;
- exact-next local sequence;
- state/progress atomicity;
- restart and rebuild;
- quiescent replay reconciliation.

### Kafka-based projection

Would additionally need to test:

- stable key-to-partition routing;
- partition-count changes;
- offset commit versus state commit;
- consumer rebalance;
- duplicate delivery;
- transactional `read_committed` and LSO behavior;
- retention and offset reset;
- poison-record policy.

### WAL / LSN-based projection or analytics

Would additionally need to test:

- replication-slot retention and recovery;
- transaction-boundary decoding;
- failover and source-offset continuity;
- schema evolution;
- snapshot plus streamed-tail consistency;
- backfill and bootstrap boundary;
- materialization lag and reconciliation.

The common rule remains:

> Architectural similarity does not transfer proof. Each physical mechanism
> needs adversarial evidence at its own transaction, visibility, and recovery
> boundaries.

---

## Relationship to Existing Documentation

- [ADR 0020](../adr/0020_per_order_projection_progress_and_order_local_snapshot_tails.md)
  records the accepted repository decision.
- [From `created_at` Freshness to Committed-History Boundaries](../reasoning_notes/from_created_at_freshness_to_committed_history_boundaries.md)
  records the earlier distinction between allocation, commit, visibility,
  rollback gaps, and global ordering cost.
- [From Per-Order Global Position to Global Source Boundary](../postmortems/from_per_order_global_position_to_global_source_boundary.md)
  records why `global_position` remains globally unique. Its global uniqueness
  conclusion remains valid; the coordinate is no longer interpreted as a
  committed-history completeness frontier.
- [From Architectural Warning to Executable Invariant](../postmortems/from_architectural_warning_to_executable_invariant.md)
  records why the warning required a deterministic PostgreSQL transaction test.
- [Snapshot Trust Contract](snapshot_trust_contract.md) defines why snapshots
  remain derived and subordinate to accepted history.

---

## Reusable Architecture Rule

The final rule is:

> Match durable progress to the narrowest ordering and completeness boundary
> required by the consumer and actually guaranteed by the source.

Applied here:

```text
global_position
= globally unique lineage coordinate

order_id + sequence
= aggregate-local causal order

per-order progress
= aggregate-local projection completeness

Kafka partition offset
= partition-local delivery progress

WAL / LSN
= commit-aware database observation coordinate
```

None of these values should be allowed to authorize a stronger conclusion than
its production mechanism can prove.

---

## External References

- [PostgreSQL sequence functions](https://www.postgresql.org/docs/current/functions-sequence.html)
  explain why `nextval()` values are not reclaimed after transaction abort and
  why allocated sequences may contain gaps.
- [Apache Kafka protocol design — partitioning strategies](https://kafka.apache.org/42/design/protocol/)
  describes key-based semantic partitioning and order preservation within a
  partition.
- [Apache Kafka consumer configuration](https://kafka.apache.org/42/configuration/consumer-configs/)
  defines `read_committed`, Last Stable Offset, and withholding records after
  an open transaction.
- [Apache Kafka consumer API](https://kafka.apache.org/42/javadoc/org/apache/kafka/clients/consumer/KafkaConsumer.html)
  distinguishes partition-local consumer position from committed position.
- [Databricks: From monolith to Lakebase to LTAP](https://www.databricks.com/blog/lakebase-ltap-rethinking-database-storage)
  describes SafeKeeper, PageServer, WAL / LSN observation, and merging recent
  changes over materialized object-storage data.
