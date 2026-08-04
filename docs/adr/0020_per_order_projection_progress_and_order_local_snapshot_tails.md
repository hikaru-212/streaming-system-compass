# ADR 0020: Per-Order Projection Progress and Order-Local Snapshot Tails

## Status

Accepted

## Implementation Status

Implemented and verified by the Stage 3.5C–3.5E unit and PostgreSQL integration
test suites.

## Context

The Stage 3.5C PostgreSQL worker originally treated
`order_events.global_position` as a complete accepted-history frontier:

```text
WHERE global_position > checkpoint
ORDER BY global_position
```

A real PostgreSQL characterization reproduced a commit-order inversion:

```text
T1 allocates lower P1 and remains uncommitted
T2 allocates higher P2 and commits
worker processes P2 and checkpoints P2
T1 commits P1
future query excludes P1 permanently
```

PostgreSQL sequence allocation is behaving as designed. Allocation order is
not transaction commit order. A permanent integer gap from rollback is also
different from a temporarily invisible lower allocation that later commits.

The implemented order-state projection is aggregate-local:

- projection state is keyed by `order_id`;
- the reducer advances by `OrderEvent.sequence`;
- replay reads one order by sequence;
- no implemented projection requires a total order across different orders.

Accepted business authority remains `order_events`. Projection states,
projection progress, checkpoints, and snapshots remain derived evidence.

## Identity, Ordering, and Completeness Are Different Boundaries

This decision does not revert the earlier correction that made
`global_position` globally unique.

The following contracts remain distinct:

```text
global_position
= globally unique coordinate for one accepted event

order_id + sequence
= aggregate-local causal event order

projection_name + projection_epoch + order_id
= aggregate-local projection progress identity
```

Two different accepted events must not share one `global_position`, even when
they belong to different orders.

However, global coordinate uniqueness does not prove that processing a visible
higher coordinate has completed every lower coordinate. The repaired worker
therefore preserves global uniqueness while removing the unsupported global
completeness inference.

After this decision:

```text
global_position
= accepted-event identity and lineage coordinate
= deterministic scheduling metadata among eligible events
!= committed-history completeness frontier
```

The uniqueness correction recorded in
[From Per-Order Global Position to Global Source Boundary](../postmortems/from_per_order_global_position_to_global_source_boundary.md)
remains valid. What changes here is the meaning of durable projection progress,
not the uniqueness scope of `global_position`.

## From Architectural Warning to Reproduced Defect

This decision has an earlier reasoning lineage.

The reasoning note
[From `created_at` Freshness to Committed-History Boundaries](../reasoning_notes/from_created_at_freshness_to_committed_history_boundaries.md),
recorded during Stage 3.5D, had already distinguished:

- PostgreSQL sequence allocation order from transaction commit order;
- temporarily invisible lower positions from permanent rollback gaps;
- per-order causal sequence from cross-order global ordering;
- missing positions from visible but unprocessable events.

That reasoning correctly identified the architectural risk before the active
failure was experimentally reproduced.

However, the warning had not yet been converted into:

- an executable projection-worker invariant;
- a multi-connection PostgreSQL commit-inversion test;
- a production cursor contract that prevented the worker from advancing past a
  later-committing lower position.

The original implementation, its existing tests, human review, and multiple
AI-assisted reviews remained locally coherent because they primarily exercised
already-committed history and serial transaction order. They did not construct
the specific interleaving in which a lower allocated position remained
uncommitted while a higher position became visible and advanced durable worker
progress.

The later source-grounded audit and real PostgreSQL characterization test
converted the earlier architectural warning into demonstrated repository
evidence:

```text
correct architectural concern
-> missing executable invariant
-> adversarial transaction interleaving
-> reproduced active correctness defect
-> repaired production contract
```

The lesson is not that the earlier reasoning was absent or incorrect. The
lesson is that architectural understanding, review consensus, and passing
ordinary tests do not by themselves prove that a concurrency invariant is
enforced.

For a database-visibility guarantee, the failure mode must also be expressed as
an executable test against the real transaction boundary.

## Decision

### Projection definition

The current immutable production identity is:

```text
projection_name = order_state_projection
projection_epoch = 1
```

`projection_name` identifies reducer semantics. Positive `projection_epoch`
distinguishes an incompatible progress lineage. Epoch 1 is the initial repaired
epoch and the only currently supported production epoch. `worker_name` remains
operational identity only.

The schema includes the epoch in progress identity so pre-repair evidence
cannot be reinterpreted as repaired progress. The current
`projection_states` table is keyed only by `order_id`, so this decision does
not provide concurrent or general multi-epoch execution. A future epoch change
requires a human-controlled derived-state rebuild or a separately designed
versioned state store. Parallel epoch rebuilds are not implemented.

Repaired progress is not seeded from pre-repair global checkpoints.

### Per-order progress

Persist progress by:

```text
(projection_name, projection_epoch, order_id)
```

Each row records the last durably applied `last_sequence`, `last_event_id`,
`last_global_position`, and `updated_at`. No row means local sequence zero. An
accepted event is eligible only when:

```text
event.sequence = COALESCE(last_sequence, 0) + 1
```

Progress identity is immutable. A persisted row starts at sequence 1 and
updates by exactly one sequence. Accepted-event lineage must match the cited
event ID, order, sequence, and global position.

### Event discovery and worker transaction

The PostgreSQL worker discovers currently visible exact-next events by joining
`order_events` to repaired per-order progress. `global_position` is retained
only as a globally unique coordinate, lineage field, and deterministic
scheduling tie-breaker among currently eligible events.

Processing order B cannot exclude a later-visible event for order A because
each order has independent progress. A rolled-back insertion creates no
accepted row and no progress obligation. An order-local gap fails closed.

Projection state and per-order progress commit or roll back in the same
top-level transaction. All worker stores must share the exact worker
connection. `process_next()` rejects an active outer transaction so an inner
savepoint cannot be mistaken for a durable commit.

The supported topology remains one active worker for this projection
definition and epoch. No lease or heartbeat protocol is introduced.

`no_event` means:

> No currently visible accepted event is eligible as the next order-local
> event for this projection definition and epoch.

It does not prove that no accepted event can commit later.

### Existing checkpoints

Generic `projection_checkpoints` infrastructure remains. The repaired
PostgreSQL order-state worker does not read or advance it. Existing global
checkpoint rows are pre-repair evidence of the largest processed visible
allocation position, not proof of a complete committed-history frontier.

### Snapshot tails

For an order snapshot, validator and resolver tails are loaded using:

```text
same order_id
event.sequence > snapshot.source_event_sequence
ORDER BY event.sequence ASC
```

Each returned event must be the exact next local sequence. A gap fails
explicitly. `snapshot.source_global_position` remains a globally unique lineage
coordinate only; it is not used as an order-snapshot completeness frontier.

Snapshot existence remains distinct from snapshot trust. Snapshots are derived
compression or acceleration evidence and never replace accepted history.

### Consistent PostgreSQL observation

PostgreSQL replay validation, snapshot validation, and snapshot-assisted
resolution use one exact connection and one explicit top-level transaction
at `REPEATABLE READ READ ONLY` when their result is described as one database
observation. Mixed connections or an outer transaction fail fast at the
PostgreSQL boundary. Generic in-memory validators remain storage-agnostic.

## Related Progress Models

The accepted decision has a structural relationship to partition-local stream
processing, but it does not implement Kafka inside PostgreSQL.

Kafka normally scopes record order and consumer progress to a physical
partition. Key-based routing can keep records for the same entity in one
partition. Transactional `read_committed` consumption uses a Last Stable Offset
to avoid delivering records beyond an unresolved earlier transaction in that
partition.

This ADR instead scopes application projection completeness directly to one
aggregate:

```text
Kafka
= physical partition-local log and consumer progress

ADR 0020
= logical aggregate-local reducer progress in PostgreSQL
```

Databricks Lakebase / LTAP represents another alternative. It uses WAL / LSN
and MVCC-aware storage to provide a commit-consistent database observation,
including recent changes not yet materialized into analytical object storage.
That is a stronger global observation contract with a substantially larger
storage and operational architecture.

The current repository does not require either Kafka infrastructure or a
WAL-derived global projection watermark to make the implemented order-state
projection correct.

The detailed comparison, trade-offs, and future decision triggers are recorded
in
[Aggregate-Local Progress, Partition-Local Logs, and Commit-Consistent Boundaries](../architecture/aggregate_local_progress_partition_logs_and_commit_boundaries.md).

## Compatibility

The repair is additive:

- existing accepted events and global positions are unchanged;
- global-position uniqueness remains unchanged;
- a new progress table begins empty at repaired epoch 1;
- old global checkpoints are neither deleted nor used to bootstrap progress;
- snapshots keep `source_global_position` as lineage but tail by local sequence.

## Human-Controlled Cutover and Rebuild

`order_events` must be preserved because it is accepted business authority.
Repaired progress must not be seeded from legacy global checkpoints.

The supported cutover for the current pre-production, single-developer
baseline is:

1. Stop the old projection worker.
2. Do not run old and repaired workers concurrently against the same
   projection state.
3. Treat pre-repair derived evidence as unqualified until replayed or rebuilt.
4. Perform a human-controlled reset of affected derived read-side data,
   including, as applicable:
   - `projection_states`;
   - `projection_order_progress`;
   - legacy `projection_checkpoints` for the affected worker;
   - `projection_snapshots`.
5. Do not delete or rewrite `order_events`, accepted-history identity, or any
   business authority.
6. Replay accepted history through the repaired worker.
7. Rebuild or revalidate projection snapshots.

This is an operational contract, not automatic startup or migration behavior.
Migration 006 performs no cutover deletion. A future production migration that
retains existing projection rows requires a separately verified per-order
bootstrap procedure; that procedure is not implemented here.

## Consequences

The aggregate-local projection can resume safely across commit-order inversion
without waiting on rolled-back global integers. The write path gains no
serialization hot row. Eligible-event discovery adds a join to per-order
progress and may require future operational tuning as accepted history grows.

The permission boundary grants the projection worker normal runtime
`SELECT`/`INSERT`/`UPDATE` access to repaired progress, grants snapshot and
read-only roles observation, and denies runtime deletion and unauthorized
mutation. Human-controlled reset remains an owner, migration, or administrative
operation.

The repair deliberately gives up one claim:

```text
projection is globally complete through database or global_position boundary P
```

The implemented runtime can instead prove:

```text
order A is projected through local sequence N
```

A future requirement for a global committed projection watermark, cross-table
transaction delivery, or many downstream consumers would require a separate
commit-aware source design such as WAL / logical decoding, Kafka, or another
durable log contract. Such a source would complement rather than replace the
aggregate-local domain sequence invariant.

## Explicit non-goals

This decision does not provide:

- exactly-once or effectively-once processing;
- multi-worker leases, heartbeats, or orchestration;
- a globally ordered projection contract;
- a global committed projection watermark;
- Kafka partitions, consumer groups, rebalancing, or transactional LSO
  semantics;
- a WAL / LSN-derived event-delivery or analytical observation contract;
- automatic snapshot fallback, trust policy, or runtime action;
- accepted-history rewriting;
- concurrent or general multi-epoch projection-state execution;
- parallel epoch rebuilds or automatic cutover/reset;
- a distributed or cross-database snapshot protocol;
- a Stage 4 typed producer-result change.
