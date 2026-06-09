# Pipeline Integration Tests

[← Back to Integration Tests](../README.md)

This directory contains integration tests for pipeline-level runtime orchestration.

These tests are not general pytest examples.
They are executable architecture claims for how write-side and read-side runtime flows coordinate domain logic, storage boundaries, validation, admission, projection, checkpointing, and transaction control.

At the current baseline, this directory covers two major pipeline areas:

```text
transactional/
projection/
```

---

## Purpose

The purpose of this directory is to verify pipeline behavior across component boundaries.

The pipeline layer is where the system becomes a runtime:

```text
core meaning
+ storage durability
+ Compass validation
+ admission / checkpoint policy
→ executable flow
```

These tests focus on whether the orchestration layer calls the right components in the right order and preserves the intended transaction boundaries.

---

## Test Directories

### [transactional/](transactional/)

Contains integration tests for the PostgreSQL-backed transactional write-side pipeline.

This directory covers the completed Stage 3.5B durable write-side baseline:

```text
Stage 3.5B PR4 — Transactional Semantic Write-Side Boundary
Stage 3.5B PR5 — PostgreSQL Concurrency Admission Boundary
Stage 3.5B PR6 — Validation Placement Strategy Boundary / Stage 4 Prelude
```

The transactional tests verify:

- PostgreSQL write-side unit-of-work behavior
- accepted event append + idempotency record atomicity
- durable create / pay command flows
- idempotency replay / conflict behavior
- Compass validation-before-admission behavior
- optimistic PostgreSQL admission
- pessimistic PostgreSQL admission
- stale-write rejection
- lock-timeout mapping
- validation placement strategy
- destructive test isolation through `TEST_DATABASE_URL`

The main claim is:

```text
accepted event append
+
idempotency record write
```

must be coordinated transactionally while preserving Compass validation and admission boundaries.

See:

- [Transactional Pipeline Integration Tests](transactional/README.md)

---

### [projection/](projection/)

Contains integration tests for the PostgreSQL-backed projection pipeline.

This directory covers the Stage 3.5C PR4 durable read-side projection worker baseline:

```text
Stage 3.5C PR4 — Global-Position Projection Worker Baseline
```

The projection tests verify:

- PostgreSQL-backed projection worker behavior
- accepted-history consumption through `GLOBAL_POSITION`
- canonical reducer integration
- durable projection state persistence
- durable checkpoint progress persistence
- worker resume from checkpoint
- no-event behavior after checkpoint reaches the latest accepted event
- rollback behavior when checkpoint persistence fails
- fail-fast behavior for unsupported checkpoint cursor kinds
- fail-fast behavior when projection state is ahead of checkpoint progress

The main claim is:

```text
projection state
+
checkpoint progress
```

must be persisted inside one read-side transaction boundary.

See:

- [Projection Pipeline Integration Tests](projection/README.md)

---

## Boundary Distinction

The two test directories protect different runtime boundaries.

### Write-side boundary

```text
command
→ idempotency
→ aggregate rehydration
→ candidate event
→ Compass validation
→ admission
→ accepted history
→ idempotency record
```

The write-side boundary is about whether a candidate event may become accepted history.

### Read-side boundary

```text
accepted history
→ projection event source
→ reducer
→ projection state
→ checkpoint progress
```

The read-side boundary is about whether accepted history can be consumed into derived state without splitting state progress from checkpoint progress.

---

## What These Tests Prove

Together, the pipeline integration tests prove:

1. Write-side orchestration preserves transaction atomicity.
2. Write-side orchestration preserves Compass validation before accepted-history mutation.
3. Write-side orchestration separates idempotency, admission, validation, and domain legality.
4. PostgreSQL-backed admission rejects stale or unprepared writers through stable application results.
5. Validation placement can move validation before the write transaction while append-time admission remains authoritative.
6. Read-side orchestration consumes accepted history through the explicit `GLOBAL_POSITION` cursor.
7. Read-side orchestration derives projection state through the canonical reducer.
8. Read-side orchestration persists projection state and checkpoint progress atomically.
9. Read-side fail-fast behavior protects durable mismatch from being silently repaired.
10. Destructive PostgreSQL integration tests are isolated from the development database.

---

## What These Tests Do Not Prove

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

Those belong to later stages or other test directories.

---

## Test Database Boundary

Pipeline integration tests are destructive PostgreSQL integration tests.

They may mutate or truncate tables such as:

- `order_events`
- `idempotency_records`
- `projection_states`
- `projection_checkpoints`

They must run against:

```text
TEST_DATABASE_URL
```

not:

```text
DATABASE_URL
```

The expected test database is:

```text
compass_test
```

The shared fixtures should prevent destructive tests from running against a non-test database.

---

## Expected Commands

Run all pipeline integration tests:

```bash
pytest tests/integration/pipeline -v
```

Run transactional pipeline integration tests only:

```bash
pytest tests/integration/pipeline/transactional -v
```

Run projection pipeline integration tests only:

```bash
pytest tests/integration/pipeline/projection -v
```

Run storage integration tests as a regression check:

```bash
pytest tests/integration/storage -v
```

Run the full suite:

```bash
pytest -v --durations=10 --cov=src --cov-report=term-missing --cov-fail-under=80
```

---

## Recommended Reading Order

For write-side runtime behavior:

1. `transactional/README.md`
2. `transactional/test_postgres_unit_of_work.py`
3. `transactional/test_postgres_write_side.py`
4. `transactional/test_postgres_optimistic_admission.py`
5. `transactional/test_postgres_pessimistic_admission.py`

For read-side runtime behavior:

1. `projection/README.md`
2. `projection/test_postgres_projection_worker.py`

---

## Current Stage Status

```text
Stage 3.5B PR4 — Transactional Semantic Write-Side Boundary ✅
Stage 3.5B PR5 — PostgreSQL Concurrency Admission Boundary ✅
Stage 3.5B PR6 — Validation Placement Strategy Boundary / Stage 4 Prelude ✅
Stage 3.5C PR4 — Global-Position Projection Worker Baseline ✅
Stage 3.5C PR5 — Durable Replay / Rebuild Validation planned
```

---

## Summary

This directory verifies pipeline orchestration.

The transactional tests protect the write-side boundary:

```text
accepted event append
+
idempotency record write
```

The projection tests protect the read-side boundary:

```text
projection state
+
checkpoint progress
```

Both boundaries are required before the project can safely move toward durable replay / rebuild validation and future Compass Layer 2 projection-drift validation.
