# Stage 3.5D PR Breakdown

[← Back to Implementation Notes](README.md)

## Purpose

This note proposes the implementation sequence for:

```text
Stage 3.5D — Snapshot Trust Contract / Replay Efficiency
```

The goal is to add snapshot-assisted replay / rehydration without treating snapshot as source of truth.

---

## Stage Principle

```text
accepted history = authority
snapshot = derived state compression
fast path = snapshot + tail replay + trust checks
authority path = full accepted-history replay
```

Additional implementation principles:

```text
canonical hash must be deterministic
snapshot write must be idempotent for benign races
snapshot generation policy must be separate from trust validation
database constraints should not over-assume reducer version semantics
store collision handling must distinguish benign duplicate writes from inconsistent evidence
```

---

## Proposed PR Sequence

```text
PR1 — General Snapshot Trust Contract Boundary
PR2 — Projection Snapshot Schema Baseline
PR3 — PostgresProjectionSnapshotStore
PR4 — Projection Snapshot-Assisted Replay Validator
PR4.5 — Projection Snapshot-Assisted State Resolver
PR5 — Aggregate Snapshot Trust Extension
PR6 — Aggregate Snapshot Schema / Store
PR7 — Snapshot-Assisted Write-Side Rehydration
```

A later PR may close out Stage 3.5D after PR7.

---

## PR1 — General Snapshot Trust Contract Boundary

### Goal

Define snapshot as a general derived-state trust boundary.

### Status

Completed.

### Scope

- add snapshot trust postmortem
- add snapshot trust boundary note
- add snapshot trust architecture note
- add Stage 3.5D PR breakdown note
- define read-side first implementation
- recognize write-side aggregate snapshot as a stricter extension
- define canonical hashing as required implementation boundary
- define snapshot write collision policy
- define snapshot generation policy separation

### Non-goals

- no production code
- no schema
- no store
- no validator
- no write-side command path changes

---

## PR2 — Projection Snapshot Schema Baseline

### Goal

Create the physical shape for projection snapshots.

### Status

Completed.

### Scope

- add migration for `projection_snapshots`
- define projection snapshot lineage columns
- define snapshot schema version
- define reducer version
- define payload hash
- add schema constraint tests
- avoid over-strict `state_version = source_event_sequence` constraint
- enforce `source_event_id` as a globally unique accepted-event boundary
- enforce `source_global_position` as a globally unique accepted-history cursor
- preserve `source_event_sequence` as order-local through `UNIQUE(order_id, source_event_sequence)`

### Non-goals

- no Python store
- no replay validator
- no aggregate snapshot table
- no write-side rehydration

---

## PR3 — PostgresProjectionSnapshotStore

### Goal

Make `projection_snapshots` usable through a Python storage boundary.

### Status

Completed.

### Scope

- add `ProjectionSnapshot` model
- add `PostgresProjectionSnapshotStore`
- add `SnapshotWriteCollisionError`
- support `save_snapshot(snapshot)`
- support `load_latest_snapshot(order_id)`
- support `clear_snapshots(order_id)`
- load latest snapshots by highest `source_global_position`, not by `created_at`
- preserve Decimal amount round-trip
- preserve metadata JSON round-trip
- load database-created `created_at`
- preserve caller-owned transaction boundary
- implement duplicate-write idempotency for same complete source boundary and same snapshot evidence
- detect inconsistent lineage or payload evidence as `SnapshotWriteCollisionError`
- use `INSERT ... ON CONFLICT DO NOTHING` followed by explicit source-boundary inspection
- add PostgreSQL integration tests

### Collision Policy

The complete projection snapshot source boundary is:

```text
source_event_id
+ order_id
+ source_event_sequence
+ source_global_position
```

PR3 treats duplicate writes as idempotent only when the existing row matches the incoming snapshot across:

```text
complete source boundary
+ snapshot_schema_version
+ reducer_version
+ payload_hash
```

PR3 raises `SnapshotWriteCollisionError` for:

```text
same complete source boundary + different payload_hash
same complete source boundary + different reducer_version
same complete source boundary + different snapshot_schema_version
partial boundary match
mixed boundary match across existing source-boundary evidence
same payload_hash but different lineage evidence
```

### Non-goals

- no snapshot trust decision
- no snapshot-assisted replay
- no canonical payload hash computation
- no snapshot builder
- no snapshot generation policy runtime
- no aggregate snapshot store
- no write-side rehydration
- no Compass Layer 2 validation
- no `SemanticOutcome`

---

## PR4 — Projection Snapshot-Assisted Replay Validator

### Goal

Validate projection snapshot-assisted reconstruction against authority-path replay behavior.

### Status

Completed after Commit 6 documentation closeout.

### Scope

- add `ProjectionSnapshotReplayValidationStatus`
- add `ProjectionSnapshotReplayValidationResult`
- add `ProjectionSnapshotReplayValidator`
- load projection snapshots through `PostgresProjectionSnapshotStore`
- load accepted history through `PostgresAcceptedHistoryEventSource`
- load tail records through `PostgresProjectionEventSource`
- hydrate projection snapshots into `OrderState`
- replay accepted history through the canonical projection reducer as the authority path
- replay tail events after `snapshot.source_global_position`
- load tail events across pages
- detect non-advancing / out-of-order tail source cursor behavior as `TAIL_EVENT_SOURCE_CONTRACT_VIOLATION`
- compare snapshot-assisted state against authority state
- enforce current reducer compatibility with `snapshot.state_version == snapshot.source_event_sequence`
- reject snapshots whose source sequence is ahead of accepted history
- return structured result / reason / evidence fields
- add unit tests for validator behavior
- add PostgreSQL-backed tests for `PostgresAcceptedHistoryEventSource`
- add PostgreSQL integration tests for validator assembly

### Validation Statuses

```text
MATCH
MISSING_SNAPSHOT
NO_ACCEPTED_HISTORY_FOR_ORDER
INVALID_SNAPSHOT_BOUNDARY
TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
SNAPSHOT_ASSISTED_DRIFT
```

### Non-goals

- no canonical payload hash verification
- no reducer version compatibility matrix
- no snapshot schema migration policy
- no `SemanticOutcome`
- no runtime decision policy
- no automatic fallback / repair / quarantine
- no write-side command path changes
- no hot-path snapshot-assisted state resolver

PR4 is validation / audit evidence.

It is not the runtime fast path.

---

## PR4.5 — Projection Snapshot-Assisted State Resolver

### Goal

Use trusted projection snapshot evidence to resolve read-side projection state through snapshot + tail replay without full accepted-history replay on every read.

### Scope

- load latest trusted projection snapshot
- validate minimal local structural compatibility
- hydrate snapshot state
- load tail events after `snapshot.source_global_position`
- replay tail through canonical reducer
- return resolved projection state
- avoid full authority replay in the normal resolver path
- document how PR4 validation evidence can qualify PR4.5 usage

### Non-goals

- no authority full replay comparison in the hot path
- no `SemanticOutcome`
- no runtime policy engine
- no automatic snapshot quarantine
- no write-side aggregate rehydration
- no command admission changes

PR4.5 should consume trust evidence.

It should not recreate PR4 validation on every read.

---

## PR5 — Aggregate Snapshot Trust Extension

### Goal

Extend the general Snapshot Trust Contract to write-side aggregate rehydration.

### Scope

- document why write-side snapshot is stricter
- define aggregate snapshot trust evidence
- define admission-path constraints
- define fallback behavior
- add implementation plan for aggregate snapshot schema / store

### Non-goals

- no aggregate snapshot table yet
- no store yet
- no command path modification yet

---

## PR6 — Aggregate Snapshot Schema / Store

### Goal

Add durable aggregate snapshot storage.

### Scope

- add `aggregate_snapshots` migration
- add `AggregateSnapshot` model
- add `PostgresAggregateSnapshotStore`
- implement idempotent collision policy
- add schema and integration tests

### Non-goals

- no command path integration yet
- no relaxation of admission
- no automatic repair policy

---

## PR7 — Snapshot-Assisted Write-Side Rehydration

### Goal

Use trusted aggregate snapshots to accelerate write-side aggregate rehydration.

### Scope

- add snapshot-aware rehydration path
- fallback to full accepted-history replay when snapshot trust fails
- preserve idempotency behavior
- preserve Compass Layer 1 validation
- preserve append-time admission
- add write-side tests for snapshot fast path and fallback path

### Non-goals

- no bypass of accepted history
- no bypass of concurrency admission
- no bypass of Compass Layer 1
- no `SemanticOutcome`
- no action safety behavior
