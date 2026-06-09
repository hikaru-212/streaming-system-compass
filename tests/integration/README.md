# Integration Tests

[← Back to Tests README](../README.md)

This directory contains integration tests for **Streaming System + Compass**.

Integration tests verify behavior across module boundaries, especially where runtime orchestration meets persistence, transaction control, replay, projection, checkpointing, and destructive PostgreSQL test setup.

These tests are not general pytest examples.
They are executable architecture claims.

---

## Purpose

The purpose of this directory is to verify that independently designed components still preserve the intended system boundaries when they are wired together.

The integration test layer focuses on questions such as:

- Does runtime orchestration call the correct components in the correct order?
- Do PostgreSQL-backed stores preserve durable facts across transactions?
- Do destructive database tests run only against the test database?
- Do write-side and read-side transaction boundaries prevent partial durable state?
- Do in-memory baselines and PostgreSQL-backed baselines preserve the same conceptual semantics?

---

## Test Areas

### [pipeline/](pipeline/)

Contains integration tests for pipeline-level runtime orchestration.

Current subdirectories include:

- [transactional/](pipeline/transactional/)
- [projection/](pipeline/projection/)

The pipeline tests verify executable runtime flows.

The transactional pipeline tests protect the write-side boundary:

```text
accepted event append
+
idempotency record write
```

The projection pipeline tests protect the read-side boundary:

```text
projection state
+
checkpoint progress
```

See:

- [Pipeline Integration Tests](pipeline/README.md)

---

### [storage/](storage/)

Contains PostgreSQL-backed storage integration tests.

The storage tests verify durable persistence boundaries for:

- accepted event history
- idempotency records
- projection state
- projection checkpoints
- global-position event loading
- schema constraints
- test database isolation

These tests focus on store-level and schema-level behavior.

They do not own pipeline orchestration.

See:

- [Storage Integration Tests](storage/README.md)

---

### [in_memory/](in_memory/)

Contains integration tests for in-memory baselines.

The in-memory tests are useful for verifying the original semantic and runtime shape before PostgreSQL-backed durability is introduced.

They help preserve continuity between:

```text
in-memory baseline semantics
→ PostgreSQL-backed durable semantics
```

Use this area to understand the earlier executable model before reading the durable storage and pipeline integration tests.

See:

- [In-Memory Integration Tests](in_memory/README.md)

---

## Shared PostgreSQL Test Boundary

This directory uses shared PostgreSQL fixtures for destructive integration tests.

The shared `conftest.py` enforces a hard separation between:

```text
DATABASE_URL
= development / manual inspection / local demo database

TEST_DATABASE_URL
= pytest / destructive PostgreSQL integration test database
```

PostgreSQL integration tests must connect through:

```text
TEST_DATABASE_URL
```

The test fixture refuses to run destructive database tests unless the connected database name ends with:

```text
_test
```

At the current baseline, the expected test database is:

```text
compass_test
```

---

## Why the Test Database Guardrail Exists

Integration tests may truncate durable tables such as:

```text
projection_checkpoints
projection_states
idempotency_records
order_events
```

The cleanup fixture resets these tables before each database integration test:

```text
TRUNCATE
    projection_checkpoints,
    projection_states,
    idempotency_records,
    order_events
RESTART IDENTITY CASCADE
```

This is intentionally destructive.

Therefore, these tests must never run against the development database.

The guardrail answers:

> Are destructive PostgreSQL tests physically isolated from the database used for manual development and inspection?

---

## Current Stage Coverage

At the current baseline, this directory covers:

```text
Stage 3 — In-memory Projection Runtime Baseline
Stage 3.5B PR4 — Transactional Semantic Write-Side Boundary
Stage 3.5B PR5 — PostgreSQL Concurrency Admission Boundary
Stage 3.5B PR6 — Validation Placement Strategy Boundary / Stage 4 Prelude
Stage 3.5C PR1 — Durable Read-Side Schema Baseline
Stage 3.5C PR2 — PostgresProjectionStore
Stage 3.5C PR3 — PostgresCheckpointStore
Stage 3.5C PR4 — Global-Position Projection Worker Baseline
```

The next planned Stage 3.5C integration direction is:

```text
Stage 3.5C PR5 — Durable Replay / Rebuild Validation
```

---

## What These Tests Prove

Together, the integration tests prove that:

1. PostgreSQL destructive tests use `TEST_DATABASE_URL`, not `DATABASE_URL`.
2. Accepted history can be persisted and loaded from PostgreSQL.
3. Idempotency memory can distinguish `MISS`, `REPLAY`, and `CONFLICT`.
4. Write-side event append and idempotency record persistence can share one transaction.
5. PostgreSQL-backed admission rejects stale or unprepared writers through stable application-level results.
6. Validation placement can move validation before the write transaction while append-time admission remains authoritative.
7. Durable projection state and checkpoint progress can be persisted through PostgreSQL stores.
8. The projection worker can consume accepted history through `GLOBAL_POSITION`.
9. Projection state and checkpoint progress are persisted atomically by the PostgreSQL-backed projection worker.
10. In-memory baselines still explain the conceptual runtime model that the durable paths extend.

---

## What These Tests Do Not Prove Yet

These tests do not yet prove:

- durable replay / rebuild validation
- Compass Layer 2 projection-drift validation
- Snapshot Trust Contract
- structured `SemanticOutcome`
- runtime decision policy
- action safety
- out-of-order buffering
- DLQ
- watermark semantics
- worker leasing
- checkpoint row locking
- distributed multi-worker coordination
- production database role hardening
- append-only trigger enforcement

Those belong to later stages or future test directories.

---

## Expected Commands

Run all integration tests:

```bash
pytest tests/integration -v
```

Run pipeline integration tests:

```bash
pytest tests/integration/pipeline -v
```

Run transactional pipeline integration tests:

```bash
pytest tests/integration/pipeline/transactional -v
```

Run projection pipeline integration tests:

```bash
pytest tests/integration/pipeline/projection -v
```

Run storage integration tests:

```bash
pytest tests/integration/storage -v
```

Run in-memory integration tests:

```bash
pytest tests/integration/in_memory -v
```

Run the full suite:

```bash
pytest -v --durations=10 --cov=src --cov-report=term-missing --cov-fail-under=80
```

---

## Recommended Reading Order

For the full integration-test story, read:

1. [In-Memory Integration Tests](in_memory/README.md)
2. [Storage Integration Tests](storage/README.md)
3. [Pipeline Integration Tests](pipeline/README.md)
4. [Transactional Pipeline Integration Tests](pipeline/transactional/README.md)
5. [Projection Pipeline Integration Tests](pipeline/projection/README.md)

This order shows how the system evolves from simple executable semantics into durable PostgreSQL-backed runtime boundaries.

---

## Summary

Integration tests protect the seams between modules.

They verify not only that rows are inserted or functions return values, but that the system preserves its intended boundaries:

```text
semantic meaning
+ durable storage
+ transaction control
+ admission
+ projection
+ checkpointing
```

without collapsing those responsibilities into one layer.
