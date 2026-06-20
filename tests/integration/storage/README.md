# Storage Integration Tests

[← Back to Integration Tests](../README.md)

This directory contains PostgreSQL-backed storage integration tests for **Streaming System + Compass**.

These tests are not general database examples.
They are executable architecture claims for the durable storage boundary established during **Stage 3.5B**, hardened by **Stage 3.5C PR0**, and extended by **Stage 3.5C PR1**, **Stage 3.5C PR2**, **Stage 3.5C PR3**, the storage-side part of **Stage 3.5C PR4**, **Stage 3.5D PR2**, and **Stage 3.5D PR3**.

At the current baseline, this directory covers the completed durable write-side storage foundation, the first durable read-side schema checkpoint, the first projection snapshot schema checkpoint, and the first projection snapshot store boundary:

```text
Stage 3.5B PR2 — PostgresEventStore Baseline
Stage 3.5B PR3 — PostgresIdempotencyStore Baseline
Stage 3.5C PR0 — Durable Order Event Vocabulary Hardening
Stage 3.5C PR1 — Durable Read-Side Schema Baseline
Stage 3.5C PR2 — PostgresProjectionStore Baseline
Stage 3.5C PR3 — PostgresCheckpointStore Baseline
Stage 3.5C PR4 — Global-Position Projection Event Source Baseline
Stage 3.5D PR2 — Projection Snapshot Schema Baseline
Stage 3.5D PR3 — PostgresProjectionSnapshotStore Baseline
```

It also verifies the local PostgreSQL test-database guardrail used by destructive integration tests.

---

## Purpose

The purpose of these tests is to verify that PostgreSQL preserves the durable storage semantics required by the transactional write-side and future read-side projection work.

The production code under test includes:

- `src/storage/postgres_event_store.py`
- `src/storage/postgres_idempotency_store.py`
- `src/storage/postgres_connection.py`
- `src/storage/postgres_projection_store.py`
- `src/storage/postgres_checkpoint_store.py`
- `src/storage/postgres_projection_event_source.py`
- `src/storage/order_event_hydration.py`
- `src/storage/postgres_projection_snapshot_store.py`

The related schema objects include:

- `order_events`
- `idempotency_records`
- `projection_states`
- `projection_checkpoints`
- `projection_snapshots`

Together, these tests protect the Stage 3.5B storage claim and the Stage 3.5C PR1 read-side schema claim:

> Accepted history and idempotency memory are not merely in-memory behavior anymore. They are durable PostgreSQL-backed facts with explicit identity, sequence, exact-money, schema, and replay semantics.

> Durable read-side projection state and checkpoint progress have explicit database shape constraints, but they remain derived state and operational metadata rather than accepted-history truth.

> Projection snapshots have explicit source-boundary and shape constraints, and `PostgresProjectionSnapshotStore` makes them usable through a Python storage boundary. They remain derived snapshot artifacts rather than accepted-history truth.

---

## Current Scope

The current storage integration tests cover:

- PostgreSQL connection through `TEST_DATABASE_URL`
- destructive-test isolation against `compass_test`
- required write-side tables exist after migration
- `PostgresEventStore.append()`
- `PostgresEventStore.load()`
- `PostgresEventStore.last_event()`
- accepted-history ordering by stream sequence
- stale expected-version rejection
- append-time continuity rejection
- UUID identity round-trip
- Decimal money round-trip
- proof-status round-trip
- JSONB evidence fields
- `event_schema_version` persistence
- `PostgresIdempotencyStore.check()`
- `PostgresIdempotencyStore.record()`
- durable MISS / REPLAY / CONFLICT classification
- idempotency record survival across new database connections
- foreign-key protection from idempotency records to accepted events
- semantic fingerprint behavior
- durable event vocabulary constraints
- durable proof-status constraints
- `projection_states` schema constraints
- `projection_checkpoints`
- `projection_snapshots` schema constraints
- checkpoint `cursor_kind` / `cursor_value` alignment
- physically valid but semantically suspicious projection-state rows reserved for future Layer 2 drift detection
- `PostgresProjectionStore.load_state()` missing-state behavior
- `PostgresProjectionStore.save_state()` insert and update behavior
- projection-state Decimal / status / version round-trip
- `projection_states.last_sequence` persisted from `OrderState.version`
- `PostgresProjectionStore.clear()` behavior
- multiple projection states remain independent by `order_id`
- caller-owned rollback restores connection usability after constraint failure
- `PostgresCheckpointStore.load_checkpoint()` missing-checkpoint behavior
- `PostgresCheckpointStore.save_checkpoint()` insert and update behavior
- checkpoint `cursor_kind` / `cursor_value` round-trip
- worker-specific checkpoint isolation
- `PostgresCheckpointStore.clear()` behavior
- invalid checkpoint cursor shape rejection through the store
- checkpoint store transaction ownership remains caller-controlled
- `order_events.global_position` exists as the durable global event-log position
- inserted events receive ordered global positions
- global positions remain unique
- `PostgresProjectionEventSource.load_after()` returns accepted events ordered by `global_position`
- projection event records preserve event identity while keeping `global_position` outside `OrderEvent`
- `projection_snapshots` schema constraints
- projection snapshot valid-row insertion
- projection snapshot invalid shape rejection through `CHECK` constraints
- `state_version <= source_event_sequence` physical rule
- globally unique `source_event_id`
- order-local unique `(order_id, source_event_sequence)`
- globally unique `source_global_position`
- same `source_event_sequence` allowed across different orders
- projection snapshot uniqueness rules:
  - `UNIQUE(source_event_id)`
  - `UNIQUE(order_id, source_event_sequence)`
  - `UNIQUE(source_global_position)`
- `PostgresProjectionSnapshotStore.load_latest_snapshot()` missing-snapshot behavior
- `PostgresProjectionSnapshotStore.save_snapshot()` insert behavior
- `PostgresProjectionSnapshotStore.load_latest_snapshot()` selection by highest `source_global_position`
- projection snapshot Decimal amount round-trip
- projection snapshot metadata JSON round-trip
- projection snapshot database-created `created_at` load behavior
- `PostgresProjectionSnapshotStore.clear_snapshots()` scoped order cleanup behavior
- same complete source boundary + same snapshot evidence treated as idempotent success
- inconsistent lineage or payload evidence rejected through `SnapshotWriteCollisionError`
- same `source_event_id` with different evidence rejected
- same `source_global_position` with different evidence rejected
- same `(order_id, source_event_sequence)` with different evidence rejected
- same `payload_hash` with different lineage rejected
- same complete source boundary with different reducer version rejected
- same complete source boundary with different snapshot schema version rejected
- caller-owned rollback behavior for projection snapshot store writes
- connection usability after idempotent collision handling

This directory currently focuses on the PostgreSQL-backed storage baseline, storage-side accepted-history loading for projection workers, the physical schema boundary for projection snapshots, and the storage boundary for projection snapshot records.

It does not test the full transactional write-side orchestration; that belongs to `tests/integration/pipeline/transactional/`.

It also does not test the PostgreSQL-backed projection worker transaction boundary; that belongs to `tests/integration/pipeline/projection/`.

---

## Test Database Boundary

These tests are destructive integration tests.

They may truncate write-side and read-side persistence tables such as:

- `projection_checkpoints`
- `projection_snapshots`
- `projection_states`
- `idempotency_records`
- `order_events`

For that reason, they must run against the test database connection, not the development database connection.

The intended environment split is:

```text
DATABASE_URL
= development / manual inspection / local demo database

TEST_DATABASE_URL
= pytest / destructive PostgreSQL integration test database
```

The shared integration fixture is expected to guard against accidental destructive execution against a non-test database.
It should refuse to run destructive PostgreSQL integration tests unless the connected database name ends with `_test`.

At the current baseline, the expected test database is:

```text
compass_test
```

---

## Test Categories

### 1. Test Database Guardrail

These tests verify that the physical PostgreSQL test environment is correctly isolated.

They prove:

- tests connect to `compass_test`
- required write-side tables exist after migration
- required read-side schema tables exist after migration
- required projection snapshot schema table exists after migration
- destructive cleanup leaves the test database empty before each test

This boundary answers:

> Are destructive PostgreSQL integration tests physically isolated from the development database?

---

### 2. PostgresEventStore Boundary

These tests verify that `PostgresEventStore` preserves accepted-history semantics.

They prove:

- appending CREATED then PAID events produces ordered history
- `load(order_id)` returns accepted events ordered by sequence
- `last_event(order_id)` returns the latest accepted event
- stale expected versions are rejected
- broken stream sequence continuity is rejected
- UUID identity survives write / read
- Decimal amount survives write / read
- proof status, previous version, and previous event identity survive write / read
- JSONB evidence fields and `event_schema_version` are persisted

This boundary answers:

> Can PostgreSQL preserve the accepted-history facts required for replay?

---

### 3. PostgresIdempotencyStore Boundary

These tests verify durable request-result memory.

They prove:

- unseen requests return `MISS`
- same `request_id` + same semantic fingerprint returns `REPLAY`
- same `request_id` + different semantic meaning returns `CONFLICT`
- conflicts do not overwrite existing idempotency records
- idempotency records survive a new database connection
- idempotency records must reference existing accepted events
- semantic fingerprints exclude physical request identity
- semantic fingerprints change when command meaning changes
- semantic fingerprints carry the current fingerprint version prefix

This boundary answers:

> Can PostgreSQL preserve durable idempotency memory without confusing replay, conflict, and new requests?

---

### 4. Durable Schema Constraint Boundary

These tests verify selected database-side schema constraints.

They prove:

- lowercase durable event types are rejected
- invalid `proof_prev_status` values are rejected

This boundary protects the Stage 3.5C PR0 hardening claim:

```text
event_type: CREATED / PAID
proof_prev_status: INIT / CREATED / PAID
```

This boundary answers:

> Does the database reject stored event vocabulary that no longer matches the durable accepted-history contract?

---

### 5. Durable Read-Side Schema Constraint Boundary

These tests verify selected database-side schema constraints for durable read-side state and checkpoint progress.

They prove:

- valid `projection_states` rows can be inserted
- empty `order_id` values are rejected
- invalid projection status values are rejected
- negative money values are rejected
- `paid_amount > total_amount` is rejected
- negative projection version and sequence values are rejected
- valid `projection_checkpoints` rows can be inserted
- empty `worker_name` values are rejected
- invalid checkpoint cursor kinds are rejected
- invalid `cursor_kind` / `cursor_value` combinations are rejected
- physically valid but semantically suspicious projection-state rows are allowed so that future Compass Layer 2 can detect projection drift rather than having PR1 database constraints hide it

This boundary protects the Stage 3.5C PR1 schema claim:

```text
projection_states = derived runtime view
projection_checkpoints = worker progress metadata
order_events = accepted-history truth
```

This boundary answers:

> Does the database protect the physical shape and cursor consistency of durable read-side state without turning read-side tables into source-of-truth domain validators?

---

### 6. PostgresProjectionStore Boundary

These tests verify that `PostgresProjectionStore` makes durable projection state usable through the Python storage boundary.

They prove:

- missing projection state returns `None`
- CREATED projection state can be saved and loaded
- PAID projection state can be saved and loaded
- saving the same `order_id` performs an upsert rather than creating a second row
- Decimal money values survive PostgreSQL round-trip
- order status and version survive PostgreSQL round-trip
- `projection_states.last_sequence` is persisted from `OrderState.version`
- `clear()` removes projection states
- multiple orders do not overwrite each other
- after a database constraint error, caller-owned rollback restores connection usability

This boundary protects the Stage 3.5C PR2 storage claim:

```text
PostgresProjectionStore
= durable persistence boundary for derived projection state
```

This boundary answers:

> Can PostgreSQL persist and restore derived projection state without giving the store ownership of reducer semantics, checkpoint progress, transaction commit / rollback, or Compass Layer 2 validation?

---


---

### 7. PostgresCheckpointStore Boundary

These tests verify that `PostgresCheckpointStore` makes durable checkpoint progress usable through the Python storage boundary.

They prove:

- missing checkpoint state returns `None`
- `UNSPECIFIED` checkpoint state can be saved and loaded
- `GLOBAL_POSITION` checkpoint state can be saved and loaded
- `EVENT_ID` checkpoint state can be saved and loaded
- `APPENDED_AT` checkpoint state can be saved and loaded
- saving the same `worker_name` performs an upsert rather than creating a second row
- multiple workers do not overwrite each other
- `clear()` removes checkpoints
- invalid `cursor_kind` / `cursor_value` combinations are rejected
- empty `worker_name` values are rejected
- `save_checkpoint()` does not commit the transaction
- after a database constraint error, caller-owned rollback restores connection usability

This boundary protects the Stage 3.5C PR3 storage claim:

```text
PostgresCheckpointStore
= durable persistence boundary for projection worker progress metadata
```

This boundary answers:

> Can PostgreSQL persist and restore worker checkpoint progress without giving the store ownership of event scanning, projection state, worker orchestration, transaction commit / rollback, or Compass Layer 2 validation?


### 8. Projection Snapshot Schema Constraint Boundary

These tests verify the Stage 3.5D PR2 projection snapshot schema baseline.

They prove:

- a valid projection snapshot row can be inserted
- empty `order_id` values are rejected
- non-positive `source_event_sequence` values are rejected
- non-positive `source_global_position` values are rejected
- invalid snapshot statuses such as `INIT` or `UNKNOWN` are rejected
- negative money values are rejected
- `paid_amount > total_amount` is rejected
- negative `state_version` is rejected
- `state_version > source_event_sequence` is rejected
- `state_version < source_event_sequence` is allowed
- non-positive `snapshot_schema_version` values are rejected
- empty `reducer_version`, `payload_hash`, and `created_by` values are rejected
- non-object `metadata_json` is rejected
- duplicate `(order_id, source_event_sequence)` is rejected
- duplicate `source_global_position` is rejected across orders
- duplicate `source_event_id` is rejected across rows
- the same `source_event_sequence` is allowed for different orders

This boundary protects the Stage 3.5D PR2 schema claim:

```text
projection_snapshots
= derived projection snapshot artifacts with accepted-history source-boundary evidence
```

This boundary answers:

> Does the database preserve projection snapshot source-boundary evidence and physical shape without making snapshots the source of truth?

---

## What These Tests Prove

These tests prove that the PostgreSQL-backed storage layer preserves the following claims:

1. Accepted history can be persisted and loaded back from `order_events`.
2. Accepted event ordering is preserved by stream sequence.
3. The latest accepted event can be queried.
4. Stale or broken append attempts are rejected before accepted history is polluted.
5. UUID event identity survives PostgreSQL round-trip.
6. Decimal money values remain exact across persistence.
7. Proof status and previous-history claims survive persistence.
8. JSONB evidence fields and `event_schema_version` are present at the durable boundary.
9. Idempotency memory distinguishes MISS, REPLAY, and CONFLICT.
10. Idempotency records survive beyond one connection.
11. Idempotency records cannot reference non-existent accepted events.
12. Durable schema constraints reject invalid accepted-event vocabulary.
13. Durable read-side schema constraints reject malformed projection state and checkpoint cursor rows.
14. Physically valid but semantically suspicious projection rows remain available for future Layer 2 drift detection.
15. `PostgresProjectionStore` can save, load, upsert, and clear derived projection state.
16. `projection_states.last_sequence` is intentionally persisted from `OrderState.version` in the current projection model.
17. `PostgresCheckpointStore` can save, load, upsert, and clear checkpoint progress metadata.
18. `projection_checkpoints` preserves explicit `cursor_kind` / `cursor_value` progress evidence.
19. Store methods preserve caller-owned transaction boundaries.
20. Destructive PostgreSQL tests are isolated from the development database.
21. `projection_snapshots` can store derived snapshot artifacts with source-boundary evidence.
22. `source_event_id` is globally unique.
23. `(order_id, source_event_sequence)` preserves order-local snapshot boundaries.
24. `source_global_position` is globally unique.
25. `state_version <= source_event_sequence` is enforced without requiring equality.

Together, these tests make the Stage 3.5B, Stage 3.5C, and Stage 3.5D PR2 storage claims executable:

> The durable storage layer can preserve accepted history and idempotency memory strongly enough for the transactional write-side and future read-side projection work to rely on it.

> The durable read-side schema can preserve derived projection state and checkpoint progress strongly enough for stores, workers, rebuild logic, and Layer 2 drift validation to rely on its physical shape.

> `PostgresProjectionStore` makes `projection_states` usable through a Python storage boundary while preserving projection state as derived and rebuildable.

> `projection_snapshots` preserves derived snapshot payload and source-boundary evidence without making snapshots authoritative.

---

## What These Tests Do Not Prove

These tests do not prove full transactional write-side behavior.

They do not prove:

- event append and idempotency record persistence happen in the same transaction
- Compass Layer 1 validation happens before accepted-history mutation
- validation block prevents append
- domain legality failures roll back durable writes
- optimistic or pessimistic PostgreSQL admission behavior
- validation placement strategy
- PostgreSQL-backed projection snapshot store behavior
- PostgreSQL-backed durable read-side store behavior
- PostgreSQL-backed projection worker behavior
- Compass Layer 2 state-level validation

Those belong to other test layers.

For transactional write-side orchestration, see:

```text
tests/integration/pipeline/transactional/
```

---

## Non-Goals

This directory does not currently test:

- `PostgresWriteSideUnitOfWork`
- `PostgresTransactionalWriteSide`
- PostgreSQL-backed admission gates
- `PostgresProjectionStore`
- `PostgresCheckpointStore`
- PostgreSQL-backed projection worker
- Stage 3.5D snapshot trust validator
- Stage 3.5D snapshot-assisted replay validator
- Stage 3.5E database role hardening
- Stage 4 `SemanticOutcome`
- retry reason classification persistence
- runtime decision policy
- action safety gate
- dual-dimension governance

These may become future integration or system-level tests, but they are intentionally outside the current storage baseline.

---

## Future Expansion

Future storage integration tests may add:

### Stage 3.5C — Durable Read-Side Baseline

Current PR1 coverage:

- `projection_states` schema constraints
- `projection_checkpoints`
- `projection_snapshots` schema constraints
- checkpoint `cursor_kind` / `cursor_value` alignment
- shape constraints vs future Layer 2 semantic-drift boundary

Remaining expected coverage:

- `PostgresProjectionStore`
- `PostgresCheckpointStore`
- restart survival for projection state
- restart survival for checkpoint state

### Stage 3.5D — Snapshot Trust Contract / Replay Efficiency

Current PR2 coverage:

- snapshot schema constraints
- projection snapshot source-boundary uniqueness constraints
- physical shape constraints for projection snapshot rows

Remaining expected coverage:

- snapshot lineage checks
- tail continuity checks
- reducer version checks
- payload hash / checksum checks
- invalid snapshot fallback to full replay
- snapshot-assisted replay equals full accepted-history replay

### Stage 3.5E — Durable History and Permission Hardening

Expected coverage:

- runtime role cannot update or delete `order_events`
- projection worker can read accepted history but cannot mutate it
- read-side tables remain mutable for upsert / reset / rebuild
- optional trigger-based append-only enforcement

### Stage 4 — Evidence and Outcomes

Expected coverage:

- stored event evidence hydration
- runtime metadata persistence
- validation result persistence
- request attempt / retry evidence
- structured `SemanticOutcome` persistence if introduced

---

## Reading Guide

Start with:

1. `test_postgres_test_database.py`
2. `test_postgres_event_store.py`
3. `test_postgres_idempotency_store.py`
4. `test_write_side_schema_constraints.py`
5. `test_read_side_schema_constraints.py`
6. `test_projection_snapshot_schema_constraints.py`

Read them as storage-boundary tests, not as CRUD tests.

The important question is not only:

> Did PostgreSQL store a row?

The important question is:

> Did PostgreSQL preserve the durable fact, identity, sequence, checkpoint, and constraint semantics required by the rest of the system?