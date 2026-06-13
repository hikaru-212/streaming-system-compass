# Projection Snapshot Schema Baseline

[← Back to Implementation Notes](README.md)

## Purpose

This note defines the intended schema boundary for **Stage 3.5D PR2 — Projection Snapshot Schema Baseline**.

Stage 3.5D PR1 defined the Snapshot Trust Contract as a boundary problem.

PR2 introduces the first durable schema for projection snapshots.

The goal is to create a physical PostgreSQL table that can persist snapshot payload and lineage evidence for future snapshot-assisted replay, without making snapshots the source of truth.

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
* uniqueness rules for snapshot boundaries
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

Suggested columns:

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

## Source Boundary Fields

Projection snapshots should be traceable to accepted history.

The source boundary is represented by:

* `source_event_id`
* `source_event_sequence`
* `source_global_position`

These fields do not make the snapshot authoritative.

They provide lineage evidence that a later trust validator can check against accepted history.

## State Payload Fields

The initial projection snapshot stores the current `OrderState` payload directly:

* `state_status`
* `total_amount`
* `paid_amount`
* `state_version`

This follows the current minimal order projection model.

Future projection schema versions may change this shape.

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

## Snapshot Status Values

The first projection snapshot schema supports snapshots after accepted events exist.

Therefore valid snapshot statuses are:

* `CREATED`
* `PAID`

`INIT` is intentionally not included in PR2 because an empty stream does not need a snapshot.

If a future use case requires empty-stream snapshots, the status constraint can be revisited with a schema migration.

## Payload Hash Boundary

`payload_hash` stores a canonical hash of the snapshot payload.

The table only enforces that the field is non-empty.

It does not compute or validate the hash.

Hash construction belongs to future Python code following the canonical payload hashing rules defined in:

`docs/implementation_notes/snapshot_payload_hashing.md`

## Reducer Version Boundary

`reducer_version` identifies the reducer logic version that produced the snapshot.

The table only enforces that it is non-empty.

A future trust validator may reject snapshots produced by unsupported or known-bad reducer versions.

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

## Uniqueness Boundary

PR2 defines two uniqueness rules:

* `UNIQUE(order_id, source_event_sequence)`
* `UNIQUE(order_id, source_global_position)`

The purpose is to prevent multiple conflicting snapshots from occupying the same order-local or global source boundary.

Future `PostgresProjectionSnapshotStore` behavior should handle benign races as:

* same boundary + same payload_hash = idempotent success
* same boundary + different payload_hash = `SnapshotWriteCollisionError`

PR2 only establishes the physical uniqueness boundary.

It does not implement store-level collision handling.

## Constraint Summary

The table should enforce:

* `source_event_sequence > 0`
* `source_global_position > 0`
* `state_version >= 0`
* `state_version <= source_event_sequence`
* `total_amount >= 0`
* `paid_amount >= 0`
* `paid_amount <= total_amount`
* `snapshot_schema_version > 0`
* `reducer_version` is not empty
* `payload_hash` is not empty
* `metadata_json` is a JSON object
* `state_status IN ('CREATED', 'PAID')`

## Relationship to PR3

PR3 should implement `PostgresProjectionSnapshotStore`.

It should not redefine the schema.

It should make this schema usable through Python storage APIs.

Expected PR3 behavior:

* `save_snapshot(snapshot)`
* `load_latest_snapshot(order_id)`
* `clear_snapshots(order_id)`

Store-level collision behavior belongs to PR3, not PR2.

## Relationship to PR4

PR4 should implement snapshot-assisted projection replay validation.

It should use this schema as the durable snapshot source.

PR4 should verify snapshot trust evidence before using the snapshot as a fast-path replay starting point.

## Summary

PR2 introduces the durable physical shape for projection snapshots.

It preserves the Stage 3.5D trust contract:

```text
accepted history = authority
snapshot = derived fast-path artifact
```

The table may support efficient replay later, but it must not make snapshots authoritative.
