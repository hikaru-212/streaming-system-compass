# Transactional Pipeline Integration Tests

[← Back to Tests README](../../../README.md)

This directory contains integration tests for the PostgreSQL-backed transactional write-side pipeline.

These tests are not general pytest examples.
They are executable architecture claims for the completed **Stage 3.5B durable write-side baseline**.

At the current baseline, Stage 3.5B PR4, PR5, and PR6 are complete and covered here:

```text
PR4 — Transactional Semantic Write-Side Boundary
PR5 — PostgreSQL Concurrency Admission Boundary
PR6 — Validation Placement Strategy Boundary / Stage 4 Prelude
```

This means the transactional integration test suite now covers the full PostgreSQL-backed write-side baseline:

```text
transaction atomicity
+ durable accepted history
+ durable idempotency memory
+ PostgreSQL-backed concurrency admission
+ validation placement strategy
```

---

## Purpose

The purpose of these tests is to verify that the PostgreSQL-backed write side preserves the intended boundaries between:

- semantic validation
- durable event persistence
- durable idempotency memory
- physical transaction atomicity
- domain legality
- request replay / conflict classification
- PostgreSQL concurrency admission
- validation placement strategy
- test database isolation

The production code under test includes:

- `src/pipeline/transactional/postgres_unit_of_work.py`
- `src/pipeline/transactional/postgres_write_side.py`
- `src/pipeline/transactional/postgres_admission.py`
- `src/pipeline/transactional/postgres_write_side_config.py`

The related storage components include:

- `PostgresEventStore`
- `PostgresIdempotencyStore`

Together, these tests protect the Stage 3.5B claim:

> Accepted event append, idempotency result persistence, Compass Layer 1 validation, PostgreSQL-backed admission, and validation placement must remain separated but correctly coordinated before accepted history is mutated.

---

## Current Scope

The current transactional integration tests cover:

- PostgreSQL write-side unit-of-work behavior
- commit / rollback behavior
- durable create and pay command flows
- idempotency replay / conflict behavior
- Compass validation-before-admission behavior
- physical transaction atomicity between `order_events` and `idempotency_records`
- domain legality failures and rollback safety
- optimistic PostgreSQL admission
- pessimistic PostgreSQL admission
- stale-write rejection
- lock-timeout mapping
- autocommit guard for transaction-scoped pessimistic admission
- default / explicit `IN_TRANSACTION` validation placement
- minimal `PRE_TRANSACTION` validation placement guarded by append-time admission
- destructive test cleanup through the PostgreSQL test database boundary

This directory currently focuses on the completed Stage 3.5B PostgreSQL-backed transactional write-side baseline.

It does not attempt to model the full future governance system.

---

## Test Database Boundary

These tests are destructive integration tests.

They may truncate write-side persistence tables such as:

- `order_events`
- `idempotency_records`

For that reason, they must run against the test database connection, not the development database connection.

The intended environment split is:

```text
DATABASE_URL
= development / manual inspection / local demo database

TEST_DATABASE_URL
= pytest / destructive PostgreSQL integration test database
```

The shared integration fixture is expected to guard against accidental destructive execution against a non-test database.

The fixture should refuse to run destructive PostgreSQL integration tests unless the connected database name ends with `_test`.

This matters because transactional tests are allowed to reset database state in order to verify rollback, replay, conflict, admission rejection, validation-block, and cleanup behavior.

---

## Test Categories

### 1. UnitOfWork Transaction Boundary

These tests verify that `PostgresWriteSideUnitOfWork` coordinates PostgreSQL-backed stores through one shared transaction.

They prove:

- successful exit from the `with` block commits
- exception exit rolls back
- explicit rollback discards pending writes
- `_finished` prevents duplicate commit / rollback behavior
- rollback does not swallow the original exception
- `PostgresEventStore` and `PostgresIdempotencyStore` participate in the same transaction

This boundary is physical, not semantic.

It answers:

> Do related durable writes commit or roll back together?

---

### 2. Durable Write-Side Accepted Flow

These tests verify the successful PostgreSQL-backed write-side path.

They prove:

- `create_order` writes one accepted event to `order_events`
- `create_order` writes the corresponding idempotency record
- `pay_order` writes the second accepted event
- `pay_order` writes the corresponding idempotency record
- accepted history can be loaded back through `PostgresEventStore.load()`

This boundary proves that the durable write-side can persist accepted command results and replay them from PostgreSQL.

---

### 3. Idempotency Boundary

These tests verify request replay and request conflict classification.

They prove:

- same `request_id` + same semantic payload returns `REPLAY`
- same `request_id` + different semantic payload returns `CONFLICT`
- `REPLAY` does not create a new event
- `REPLAY` does not create a new idempotency row
- `CONFLICT` does not create a new event
- `CONFLICT` does not create a new idempotency row
- replay / conflict paths do not build or use the admission gate

This boundary is not domain legality.

This boundary is not concurrency control.

It answers:

> Is this request a safe replay, a semantic conflict, or a new request?

---

### 4. Validation-Before-Admission Boundary

These tests verify that Compass Layer 1 validation happens before accepted history mutation.

They prove:

- validation `BLOCK` happens before accepted-history mutation
- blocked candidate events do not enter `order_events`
- blocked requests do not enter `idempotency_records`
- validation failure does not pollute accepted history
- validation failure does not pollute idempotency memory

Important distinction:

These tests do not primarily prove physical rollback atomicity.

In the validation-block path, the event append should never happen in the first place.

These tests prove:

> A blocked candidate event never reaches accepted history.

---

### 5. Physical Transaction Atomicity

These tests verify the physical atomicity between event append and idempotency record persistence.

They cover failure cases such as:

- `event_store.append()` succeeds
- `idempotency_store.record()` fails
- the transaction rolls back
- no partial durable write remains

Expected outcomes:

- create path: if idempotency record fails after append, `order_events` remains empty
- pay path: if PAID append succeeds but idempotency record fails, rollback restores the database to the previous accepted history

This is the true append + idempotency atomicity boundary.

It answers:

> Can the system prevent half-persisted write-side results?

---

### 6. Domain Legality Boundary

These tests verify that aggregate / domain rules still protect illegal command flows.

Examples:

- creating an order that already has accepted history is rejected
- paying an order before it is created is rejected
- paying an already paid order is rejected

At Stage 3.5B, domain errors may still propagate as `ValueError`.

This is intentional.

Stage 3.5B does not introduce the Stage 4 `SemanticOutcome` or Error Model mapping.

The current requirement is simpler:

> Domain rejection must not leave partial durable writes.

---

### 7. PostgreSQL Concurrency Admission Boundary

These tests verify PostgreSQL-backed admission control.

They prove:

- optimistic admission uses append-time expected-version checks
- optimistic `prepare_stream(order_id)` is a no-op that does not mutate durable state
- stale expected versions map to `STALE_WRITE`
- competing append attempts do not both occupy the next stream sequence
- pessimistic admission acquires transaction-scoped advisory locks during `prepare_stream(order_id)`
- pessimistic admission rejects append attempts that did not prepare the stream
- lock contention maps to `LOCK_TIMEOUT`
- autocommit connections are rejected for transaction-scoped pessimistic admission

This boundary is not idempotency.

This boundary is not Compass semantic validation.

It answers:

> Can this writer still be admitted to append the next accepted fact for this aggregate stream?

---

### 8. Validation Placement Strategy Boundary

These tests verify that validation placement is configurable without collapsing validation mode, transaction atomicity, and admission control.

They prove:

- default / explicit `IN_TRANSACTION` behavior preserves the durable write-side path
- minimal `PRE_TRANSACTION` validation can validate before the write transaction
- `PRE_TRANSACTION` replay / conflict paths do not run validation or build admission gates
- `PRE_TRANSACTION` validation block creates no durable rows
- `PRE_TRANSACTION` append-time admission rejection does not record idempotency
- stale pre-validated candidates still cannot enter accepted history because append-time admission remains authoritative

This boundary answers:

> Where does Compass validation run relative to the physical write transaction, and what still guards accepted-history mutation?

---

## What These Tests Prove

These tests prove that the PostgreSQL-backed transactional write side preserves the following claims:

1. Accepted event append and idempotency record write can share one transaction.
2. Successful create / pay flows produce durable accepted history.
3. Replay and conflict paths do not mutate accepted history.
4. Compass validation happens before accepted-history mutation.
5. Validation-blocked candidates do not pollute `order_events`.
6. Validation-blocked candidates do not pollute `idempotency_records`.
7. Physical append + idempotency failures roll back together.
8. Domain legality failures do not leave partial database state.
9. PostgreSQL-backed admission rejects stale or unprepared writers explicitly.
10. Pessimistic admission lock contention maps to a stable application verdict.
11. Validation placement can move validation before the write transaction while preserving append-time admission.
12. Destructive PostgreSQL integration tests are isolated from the development database.

Together, these tests make the completed Stage 3.5B claim executable:

> The durable write-side is transactionally safe, admission-aware, and semantically guarded before accepted history is mutated.

---

## What These Tests Do Not Prove

These tests do not prove durable read-side correctness.

The current tests do not yet prove:

- durable projection state
- durable checkpoint state
- PostgreSQL-backed projection worker behavior
- replay / rebuild against durable read-side state
- Compass Layer 2 state-level validation
- projection drift detection
- snapshot trust validation
- structured `SemanticOutcome`
- runtime decision policy
- action safety gate
- dual-dimension governance

Those belong to later stages.

---

## Non-Goals

This directory does not currently test:

- Stage 3.5C durable read-side stores
- Stage 3.5D Snapshot Trust Contract
- Stage 3.5E database role hardening
- Stage 4 structured `SemanticOutcome`
- Stage 4 retry reason classification persistence
- Stage 4 Error Model mapping
- write-side attempt audit tables
- validation result persistence
- retry attempt history
- Stage 5 governance metrics
- async audit / outbox patterns
- full DLQ / buffering / watermark behavior
- distributed multi-worker coordination
- production-grade database role hardening
- append-only trigger enforcement

These may become future integration or system-level tests, but they are intentionally outside the completed Stage 3.5B transactional write-side baseline.

---

## Future Expansion

Future test expansion may add:

### Stage 3.5C — Durable Read-Side Baseline

Expected coverage:

- `projection_states` schema constraints
- `projection_checkpoints` schema constraints
- `PostgresProjectionStore`
- `PostgresCheckpointStore`
- PostgreSQL-backed projection worker
- durable replay / rebuild against accepted history

### Stage 3.5D — Snapshot Trust Contract / Replay Efficiency

Expected coverage:

- snapshot lineage checks
- tail continuity checks
- reducer version checks
- payload hash / checksum checks
- invalid snapshot fallback to full replay
- snapshot-assisted replay equals full accepted-history replay

### Stage 3.5E — Durable History and Permission Hardening

Expected coverage:

- write-side runtime role cannot update or delete `order_events`
- projection worker can read accepted history but cannot mutate it
- read-side tables remain mutable for upsert / reset / rebuild
- optional trigger-based append-only enforcement

### Stage 4 — Structured Outcomes

Expected coverage:

- `SemanticOutcome`
- runtime decision mapping
- structured error categories
- validation result persistence
- domain / validation / admission outcome separation
- retry reason classification and intent consistency

---

## Reading Guide

Start with:

1. `test_postgres_unit_of_work.py`
2. `test_postgres_write_side.py`
3. `test_postgres_optimistic_admission.py`
4. `test_postgres_pessimistic_admission.py`

Read them as boundary tests, not as CRUD tests.

The important question is not only:

> Did the row get inserted?

The important question is:

> Which boundary allowed or rejected this state transition, and did the database reflect that decision correctly?
