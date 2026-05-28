# Transactional Pipeline Integration Tests

[← Back to Tests README](../../../README.md)

This directory contains integration tests for the PostgreSQL-backed transactional write-side pipeline.

These tests are not general pytest examples.
They are executable architecture claims for the Stage 3.5B durable write-side baseline.

At this stage, the goal is to prove that the transactional write-side preserves the intended boundaries between:

- semantic validation
- durable event persistence
- durable idempotency memory
- physical transaction atomicity
- domain legality
- request replay classification
- test database isolation

---

## Purpose

The purpose of these tests is to verify the transactional composition of the PostgreSQL-backed write side.

The production code under test includes:

- `src/pipeline/transactional/postgres_unit_of_work.py`
- `src/pipeline/transactional/postgres_write_side.py`

The related storage components include:

- `PostgresEventStore`
- `PostgresIdempotencyStore`

Together, these tests protect the Stage 3.5B PR4 boundary:

> Accepted event append and idempotency result persistence must participate in one durable write-side transaction, while Compass Layer 1 validation must happen before accepted history is mutated.

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
- destructive test cleanup through the PostgreSQL test database boundary

This directory currently focuses on the transactional write-side baseline.

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

This matters because transactional tests are allowed to reset database state in order to verify rollback, replay, conflict, and validation-block behavior.

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

This boundary is not domain legality.

This boundary is not concurrency control.

It answers:

> Is this request a safe replay, a semantic conflict, or a new request?

---

### 4. Validation-Before-Admission Boundary

These tests verify that Compass Layer 1 validation happens before accepted history mutation.

They prove:

- validation `BLOCK` happens before append
- blocked candidate events do not enter `order_events`
- blocked requests do not enter `idempotency_records`
- validation failure does not pollute accepted history
- validation failure does not pollute idempotency memory

Important distinction:

These tests do not primarily prove physical rollback atomicity.

In the validation-block path, the event append should never happen in the first place.

These tests prove:

> A blocked candidate event never reaches admission.

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

At Stage 3.5B PR4, domain errors may still propagate as `ValueError`.

This is intentional.

Stage 3.5B PR4 does not introduce the Stage 4 `SemanticOutcome` or Error Model mapping.

The current requirement is simpler:

> Domain rejection must not leave partial durable writes.

---

## What These Tests Prove

These tests prove that the PostgreSQL-backed transactional write side preserves the following claims:

1. Accepted event append and idempotency record write can share one transaction.
2. Successful create / pay flows produce durable accepted history.
3. Replay and conflict paths do not mutate accepted history.
4. Compass validation happens before admission.
5. Validation-blocked candidates do not pollute `order_events`.
6. Validation-blocked candidates do not pollute `idempotency_records`.
7. Physical append + idempotency failures roll back together.
8. Domain legality failures do not leave partial database state.
9. Destructive PostgreSQL integration tests are isolated from the development database.

Together, these tests make the Stage 3.5B PR4 claim executable:

> The durable write-side is transactionally safe and semantically guarded before accepted history is mutated.

---

## What These Tests Do Not Prove

These tests do not prove PostgreSQL-backed concurrency safety.

Concurrency admission is a separate boundary.

The current tests do not yet prove:

- stale writer rejection
- optimistic PostgreSQL admission
- pessimistic PostgreSQL admission
- concurrent workers racing for the same stream position
- admission result mapping
- retry policy after concurrency conflict

Those are deferred to PR5.

---

## Non-Goals

This directory does not currently test:

- PostgreSQL-backed concurrency admission
- Stage 4 structured `SemanticOutcome`
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

These may become future integration or system-level tests, but they are intentionally outside Stage 3.5B PR4.

---

## Future Expansion

Future test expansion may add:

### PR5 — PostgreSQL Concurrency Admission

Expected coverage:

- optimistic admission gate
- pessimistic admission gate
- stale write rejection
- only one writer occupying the next stream sequence
- admission result mapping
- direct append replaced by admission gate in the transactional write-side flow

### Stage 4 — Structured Outcomes

Expected coverage:

- `SemanticOutcome`
- runtime decision mapping
- structured error categories
- validation result persistence
- domain / validation / admission outcome separation

### Validation Placement Strategy

Expected coverage:

- in-transaction Compass validation
- pre-transaction Compass validation + OCC
- validation mode vs validation placement
- latency comparison foundation
- selective validation placement for DAG / agent workflows

---

## Reading Guide

Start with:

1. `test_postgres_unit_of_work.py`
2. `test_postgres_write_side.py`

Read them as boundary tests, not as CRUD tests.

The important question is not only:

> Did the row get inserted?

The important question is:

> Which boundary allowed or rejected this state transition, and did the database reflect that decision correctly?
