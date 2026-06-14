# Postgres Projection Snapshot Store

[← Back to Implementation Notes](README.md)

## Purpose

This note defines the storage boundary for **Stage 3.5D PR3 — PostgresProjectionSnapshotStore**.

Stage 3.5D PR1 defined the general Snapshot Trust Contract.

Stage 3.5D PR2 introduced the durable PostgreSQL schema for projection snapshots.

PR3 makes the `projection_snapshots` table usable through a Python storage boundary.

The goal is to persist and load projection snapshot records without making the store responsible for snapshot trust, snapshot generation, or snapshot-assisted replay validation.

---

## Scope

PR3 introduces:

- `ProjectionSnapshot` model
- `PostgresProjectionSnapshotStore`
- `SnapshotWriteCollisionError`
- `save_snapshot(snapshot)`
- `load_latest_snapshot(order_id)`
- `clear_snapshots(order_id)`
- PostgreSQL integration tests for snapshot store behavior
- idempotent snapshot write collision handling
- caller-owned transaction behavior

---

## Non-goals

PR3 does not implement:

- snapshot trust validator
- snapshot-assisted replay validator
- canonical payload hash computation
- snapshot builder
- snapshot generation policy runtime
- aggregate snapshots
- write-side snapshot-assisted rehydration
- Compass Layer 2 validation
- `SemanticOutcome`
- runtime decision policy
- automatic snapshot repair
- snapshot quarantine behavior

---

## Store Responsibility

`PostgresProjectionSnapshotStore` owns durable persistence behavior for projection snapshot records.

It should answer storage questions such as:

```text
Can this projection snapshot row be saved?
What is the latest stored snapshot for this order?
Can all snapshots for an order be cleared?
Did a write collide with an existing snapshot boundary?
```

It should not answer trust questions such as:

```text
Is this snapshot safe to use?
Does this snapshot match accepted history?
Is this reducer version supported?
Does the payload hash match canonical state?
Can replay start from this snapshot?
```

Those questions belong to future snapshot trust validation and snapshot-assisted replay validation.

---

## Table Dependency

PR3 depends on the PR2 table:

```text
projection_snapshots
```

The table stores:

```text
snapshot_id
order_id

source_event_id
source_event_sequence
source_global_position

state_status
total_amount
paid_amount
state_version

snapshot_schema_version
reducer_version
payload_hash

metadata_json
created_at
created_by
```

The source boundary constraints are:

```text
UNIQUE(source_event_id)
UNIQUE(order_id, source_event_sequence)
UNIQUE(source_global_position)
```

These constraints are physical collision boundaries.

The store should translate collision outcomes into explicit storage behavior.

---

## ProjectionSnapshot Model

The initial Python model should preserve the database evidence fields directly.

Suggested shape:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class ProjectionSnapshot:
    snapshot_id: UUID
    order_id: str

    source_event_id: UUID
    source_event_sequence: int
    source_global_position: int

    state_status: str
    total_amount: Decimal
    paid_amount: Decimal
    state_version: int

    snapshot_schema_version: int
    reducer_version: str
    payload_hash: str

    metadata: dict[str, Any]
    created_by: str
    created_at: datetime | None = None
```

`created_at` is loaded from the database when available.

It is not part of snapshot trust by itself.

It records when the derived snapshot artifact row was created.

---

## Save Behavior

`save_snapshot(snapshot)` should persist a complete snapshot record.

The store should not compute:

```text
snapshot_id
payload_hash
source_event_id
source_event_sequence
source_global_position
state payload
```

Those values should be supplied by the caller.

This keeps the store as a persistence boundary rather than a snapshot builder.

---

## Load Latest Behavior

`load_latest_snapshot(order_id)` should return the latest stored snapshot for an order.

Latest means the highest accepted-history source boundary, not the newest row creation time.

The intended ordering is:

```sql
ORDER BY source_global_position DESC
LIMIT 1
```

This matters because `created_at` is an artifact creation timestamp.

`created_at` answers:

```text
When was this derived snapshot row written?
```

`source_global_position` answers:

```text
How far into accepted history was this snapshot computed?
```

The latest usable snapshot is therefore determined by accepted-history progress, not row recency.

This boundary is recorded in:

- [From `created_at` Freshness to Committed-History Boundaries](../postmortems/from_created_at_freshness_to_committed_history_boundaries.md)

---

## Clear Behavior

`clear_snapshots(order_id)` should delete projection snapshots for a single order only.

It should not clear snapshots for other orders.

This preserves order-level isolation for derived snapshot artifacts.

---

## Collision Behavior

PR2 established physical uniqueness constraints for source boundaries:

```text
UNIQUE(source_event_id)
UNIQUE(order_id, source_event_sequence)
UNIQUE(source_global_position)
```

PR3 should define store-level collision behavior against the **complete source boundary**, not against any single column in isolation.

The complete projection snapshot source boundary is:

```text
source_event_id
+ order_id
+ source_event_sequence
+ source_global_position
```

Store-level collision behavior should be:

```text
same complete source boundary + same payload_hash
= idempotent success

same source boundary evidence + different payload_hash
= SnapshotWriteCollisionError

partial boundary match
= SnapshotWriteCollisionError

mixed boundary match across multiple existing rows
= SnapshotWriteCollisionError
```

This allows benign duplicate writers to converge while still detecting non-deterministic snapshot generation, corrupted writer behavior, or inconsistent lineage evidence.

The important rule is:

```text
same payload_hash alone is not enough
```

A duplicate write is idempotent only when both the lineage evidence and payload evidence match.

---

## Why Blind `ON CONFLICT DO NOTHING` Is Not Enough

Blind conflict ignore behavior is unsafe.

This is unsafe:

```sql
INSERT ... ON CONFLICT DO NOTHING
```

if the store does not inspect the existing row.

A conflict may mean:

```text
same complete source boundary + same payload_hash
```

or:

```text
same source boundary evidence + different payload_hash
```

or:

```text
partial / mixed source-boundary collision
```

The first case is a benign duplicate write.

The other cases are correctness problems.

Therefore PR3 should verify stored lineage evidence after a conflict before deciding whether the write is idempotent.

---

## Collision Detection Strategy

PR3 should avoid relying on PostgreSQL exceptions as the normal collision path.

The preferred implementation strategy is:

```sql
INSERT ... ON CONFLICT DO NOTHING
```

Then inspect `rowcount`.

```text
rowcount == 1
= insert succeeded

rowcount == 0
= a source-boundary collision may have occurred
```

After a no-op conflict, the store should query all existing snapshots matching any physical source boundary:

```text
source_event_id
OR source_global_position
OR (order_id, source_event_sequence)
```

The store should treat the write as idempotent success only when the matching stored evidence represents the same complete source boundary and the same `payload_hash`.

```text
same complete source boundary + same payload_hash
= idempotent success
```

The store should raise `SnapshotWriteCollisionError` when it finds:

```text
same source boundary + different payload_hash
partial boundary match
mixed boundary match across multiple existing rows
same payload_hash but different source-boundary evidence
```

This prevents benign duplicate writes from failing while still detecting inconsistent lineage evidence.

This strategy avoids putting the caller-owned transaction into a failed state through expected `UniqueViolation` exceptions.

A savepoint-based implementation is still possible, but PR3 prefers `ON CONFLICT DO NOTHING` followed by explicit source-boundary inspection.

---

## Caller-Owned Transaction Boundary

Like other PostgreSQL storage classes in this project, `PostgresProjectionSnapshotStore` should not own commit / rollback for normal operations.

The caller owns the transaction.

The store should issue SQL statements through the provided connection.

Tests should verify that rollback behavior remains caller-controlled.

---

## Payload Hash Boundary

`payload_hash` is persisted by the store.

The store does not define or compute it.

Hash generation belongs to future snapshot builder / canonical payload hashing code.

This preserves the responsibility split:

```text
SnapshotBuilder
= creates canonical snapshot payload and hash

PostgresProjectionSnapshotStore
= persists supplied snapshot evidence

SnapshotTrustValidator
= decides whether existing snapshot evidence can be trusted
```

---

## Metadata Boundary

`metadata_json` should be persisted and loaded as a JSON object.

The store should preserve metadata round-trip behavior.

Metadata should not replace typed source-boundary fields.

The typed fields remain:

```text
source_event_id
source_event_sequence
source_global_position
snapshot_schema_version
reducer_version
payload_hash
```

---

## Expected Tests

PR3 should include integration tests for:

- loading a missing snapshot returns `None`
- saving and loading a projection snapshot
- Decimal amount round-trip
- metadata JSON round-trip
- `created_at` is populated on loaded snapshots
- latest snapshot is selected by highest `source_global_position`
- clearing snapshots removes only one order's snapshots
- snapshots for different orders remain isolated
- same source boundary + same `payload_hash` is idempotent success
- same `source_event_id` + different `payload_hash` raises `SnapshotWriteCollisionError`
- same `source_global_position` + different `payload_hash` raises `SnapshotWriteCollisionError`
- same `(order_id, source_event_sequence)` + different `payload_hash` raises `SnapshotWriteCollisionError`
- invalid row shape is still rejected by database constraints
- caller-owned rollback remains usable after failed writes

---

## Relationship to PR4

PR4 should implement snapshot-assisted projection replay validation.

PR4 may use `PostgresProjectionSnapshotStore` to load a candidate snapshot.

However, PR4 must still verify trust evidence before using that snapshot as a replay fast path.

PR3 makes snapshots loadable.

PR4 decides whether loaded snapshots are trustworthy.

---

## Summary

PR3 turns the PR2 schema into a usable storage boundary.

The key rule remains:

```text
projection snapshot store
= persistence and collision behavior

snapshot trust validator
= trust decision

accepted history
= authority
```

The store should make snapshot persistence reliable without letting snapshots become source of truth.
