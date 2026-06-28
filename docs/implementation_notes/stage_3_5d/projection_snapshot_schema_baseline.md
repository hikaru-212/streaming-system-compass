# Projection Snapshot Schema Baseline

[← Back to Stage 3.5D Notes](README.md)

## Purpose

This note records the schema boundary for **Stage 3.5D PR2 — Projection Snapshot Schema Baseline**.

Stage 3.5D PR1 defined the Snapshot Trust Contract as a boundary problem.

PR2 introduces the first durable PostgreSQL schema for projection snapshots.

The goal is to persist projection snapshot payload and lineage evidence for future snapshot-assisted replay, without making snapshots the source of truth.

---

## PR2 Status

PR2 establishes the durable table shape and schema constraint tests for projection snapshots.

At this stage, projection snapshots are still **derived artifacts**.

The table can preserve snapshot evidence, but it does not make any snapshot authoritative.

```text
accepted history = authority
projection snapshot = derived fast-path artifact
```

---

## Scope

PR2 introduces:

* `projection_snapshots` table
* snapshot identity
* projection target identity
* accepted-history source boundary fields
* projected state payload fields
* snapshot schema version
* reducer version
* canonical payload hash field
* metadata JSON field
* physical constraints for valid row shape
* uniqueness rules for snapshot source boundaries
* schema constraint tests

---

## Non-goals

PR2 does not implement:

* `PostgresProjectionSnapshotStore`
* snapshot save / load Python API
* snapshot trust validator
* snapshot-assisted replay validator
* snapshot generation runtime
* snapshot builder
* automatic snapshot repair
* aggregate snapshots
* write-side snapshot-assisted rehydration
* Compass Layer 2 validation
* `SemanticOutcome`
* runtime decision policy

---

## Table: `projection_snapshots`

A projection snapshot is a derived state-compression artifact.

It records a projected order state at a specific accepted-history boundary.

Columns:

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

---

## Source Boundary Fields

Projection snapshots must be traceable to accepted history.

The source boundary is represented by:

* `source_event_id`
* `source_event_sequence`
* `source_global_position`

These fields do not make the snapshot authoritative.

They provide lineage evidence that a later trust validator can check against accepted history.

The fields have different scopes:

```text
source_event_id
= accepted event identity
= globally unique event boundary

source_event_sequence
= order-local stream sequence
= unique only together with order_id

source_global_position
= global accepted-history cursor
= globally unique event-log boundary
```

This distinction matters.

Different orders may both have `source_event_sequence = 1`.

Different accepted events must not share the same `source_global_position`.

---

## State Payload Fields

The initial projection snapshot stores the current `OrderState` payload directly:

* `state_status`
* `total_amount`
* `paid_amount`
* `state_version`

This follows the current minimal order projection model.

Future projection schema versions may change this shape.

---

## Version vs Sequence Boundary

In the current order domain v1, every accepted event is state-changing.

Therefore:

```text
OrderState.version
= last aggregate-local accepted event sequence reflected by this state
```

This is a valid simplification for the current domain.

It is not a universal event-sourcing law.

Projection snapshot schema should avoid making database-level equality assumptions such as:

```text
state_version = source_event_sequence
```

The more future-safe physical rule is:

```text
state_version <= source_event_sequence
```

Stricter current-domain compatibility checks, if needed, belong in the Python trust validator rather than as a permanent database constraint.

---

## Snapshot Status Values

The first projection snapshot schema supports snapshots after accepted events exist.

Therefore valid snapshot statuses are:

* `CREATED`
* `PAID`

`INIT` is intentionally not included in PR2 because an empty stream does not need a snapshot.

If a future use case requires empty-stream snapshots, the status constraint can be revisited with a schema migration.

---

## Payload Hash Boundary

`payload_hash` stores a canonical hash of the snapshot payload.

The table only enforces that the field is non-empty.

It does not compute or validate the hash.

Hash construction belongs to future Python code following the canonical payload hashing rules defined in:

`docs/implementation_notes/snapshot_payload_hashing.md`

---

## Reducer Version Boundary

`reducer_version` identifies the reducer logic version that produced the snapshot.

The table only enforces that it is non-empty.

A future trust validator may reject snapshots produced by unsupported or known-bad reducer versions.

---

## Metadata Boundary

`metadata_json` is reserved for non-domain snapshot metadata.

It must be a JSON object.

It should not replace typed lineage fields such as:

* `source_event_id`
* `source_event_sequence`
* `source_global_position`
* `snapshot_schema_version`
* `reducer_version`
* `payload_hash`

---

## Uniqueness Boundary

PR2 uses a **single-active-version projection snapshot baseline**.

For this baseline, the table enforces:

```text
UNIQUE(source_event_id)
UNIQUE(order_id, source_event_sequence)
UNIQUE(source_global_position)
```

These rules mean:

```text
source_event_id
→ one accepted event identity may not produce competing snapshot rows

order_id + source_event_sequence
→ one order-local source boundary may not produce competing snapshot rows

source_global_position
→ one global event-log boundary may not produce competing snapshot rows
```

This preserves the intended event-sourcing semantics:

```text
source_event_sequence is order-local
source_global_position is global
source_event_id is global
```

The previous weaker form:

```text
UNIQUE(order_id, source_global_position)
```

is intentionally avoided because it would allow different orders to share the same global cursor value, which would weaken `source_global_position` as accepted-history lineage evidence.

---

## Deferred Decision: Versioned Snapshot Boundary

PR2 intentionally uses single-boundary uniqueness:

```text
UNIQUE(source_event_id)
UNIQUE(order_id, source_event_sequence)
UNIQUE(source_global_position)
```

This is the correct baseline while projection snapshots are produced under a single active reducer version and a single active snapshot schema version.

The benefit is fail-fast behavior:

```text
same accepted event boundary
→ one projection snapshot row
```

This prevents accidental competing snapshots before the project has implemented version-aware store and validator behavior.

If a future stage supports multiple reducer versions or multiple snapshot schema versions for the same accepted-history boundary, this uniqueness model should be revisited through an explicit migration.

A future versioned boundary may look like:

```text
UNIQUE(source_event_id, reducer_version, snapshot_schema_version)
UNIQUE(order_id, source_event_sequence, reducer_version, snapshot_schema_version)
UNIQUE(source_global_position, reducer_version, snapshot_schema_version)
```

That future model would allow multiple compatible snapshot rows for the same accepted event boundary, but only when they differ by reducer version or snapshot schema version.

Such a migration must be paired with store and validator changes.

Future snapshot loading must not query only by `order_id` or source boundary.

It must also qualify snapshots by the reducer version and snapshot schema version supported by the current runtime:

```text
load snapshot
WHERE order_id = ?
  AND reducer_version = supported reducer version
  AND snapshot_schema_version = supported schema version
ORDER BY source_global_position DESC
LIMIT 1
```

PR2 does not implement versioned snapshot coexistence.

It records the deferred migration path while keeping the current baseline strict and simple.

See also:

```text
docs/postmortems/from_per_order_global_position_to_global_source_boundary.md
```

---

## Snapshot Write Collision Policy

Future `PostgresProjectionSnapshotStore` behavior should handle benign races as:

```text
same boundary + same payload_hash = idempotent success
same boundary + different payload_hash = SnapshotWriteCollisionError
```

In PR2, the database only establishes the physical uniqueness boundary.

It does not implement store-level collision handling.

PR3 should translate unique-boundary conflicts into explicit store behavior.

---

## Constraint Summary

The table enforces:

* `order_id` is not empty
* `source_event_sequence > 0`
* `source_global_position > 0`
* `state_status IN ('CREATED', 'PAID')`
* `total_amount >= 0`
* `paid_amount >= 0`
* `paid_amount <= total_amount`
* `state_version >= 0`
* `state_version <= source_event_sequence`
* `snapshot_schema_version > 0`
* `reducer_version` is not empty
* `payload_hash` is not empty
* `created_by` is not empty
* `metadata_json` is a JSON object
* `source_event_id` is globally unique
* `(order_id, source_event_sequence)` is unique
* `source_global_position` is globally unique

---

## Schema Constraint Tests

PR2 schema tests should verify:

* a valid projection snapshot can be inserted
* invalid row shape is rejected by `CHECK` constraints
* `state_version < source_event_sequence` is allowed
* duplicate `(order_id, source_event_sequence)` is rejected
* duplicate `source_global_position` is rejected across orders
* duplicate `source_event_id` is rejected across rows
* the same `source_event_sequence` is allowed for different orders

These tests document the physical boundary directly.

---

## Relationship to PR3

PR3 should implement `PostgresProjectionSnapshotStore`.

It should not redefine the schema.

It should make this schema usable through Python storage APIs.

Expected PR3 behavior:

* `save_snapshot(snapshot)`
* `load_latest_snapshot(order_id)`
* `clear_snapshots(order_id)`

Store-level collision behavior belongs to PR3, not PR2.

---

## Relationship to PR4

PR4 should implement snapshot-assisted projection replay validation.

It should use this schema as the durable snapshot source.

PR4 should verify snapshot trust evidence before using the snapshot as a fast-path replay starting point.

---

## Summary

PR2 introduces the durable physical shape for projection snapshots.

It preserves the Stage 3.5D trust contract:

```text
accepted history = authority
snapshot = derived fast-path artifact
```

The table may support efficient replay later, but it must not make snapshots authoritative.
