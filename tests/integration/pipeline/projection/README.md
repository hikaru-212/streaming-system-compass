# Projection Pipeline Integration Tests

[← Back to Pipeline Integration Tests](../README.md)

This directory contains integration tests for the projection pipeline.

These tests are executable architecture claims for the read-side runtime boundary.

At the current Stage 3.5C PR5 baseline, the tests cover both the PostgreSQL-backed projection worker path and durable replay / rebuild validation:

```text
order_events
→ PostgresProjectionEventSource
→ PostgresProjectionWorker
→ canonical reducer
→ PostgresProjectionStore
→ PostgresCheckpointStore
```

---

## Purpose

The purpose of these tests is to verify that accepted history can be consumed by a durable projection worker and that persisted read-side state can be checked against accepted-history replay.

The key invariant is:

```text
projection state
+
checkpoint progress
```

must be persisted inside one read-side transaction boundary.

---

## Responsible For

These tests verify:

- PostgreSQL-backed projection worker behavior
- accepted-history consumption after `GLOBAL_POSITION`
- canonical reducer integration
- projection state persistence through `PostgresProjectionStore`
- checkpoint progress persistence through `PostgresCheckpointStore`
- worker resume from existing checkpoint
- no-event behavior after checkpoint reaches the latest accepted event
- rollback behavior when checkpoint saving fails after projection state save
- fail-fast behavior for unsupported checkpoint cursor kinds
- fail-fast behavior when projection state is ahead of checkpoint progress

---

## Not Responsible For

These tests do **not** verify:

- write-side command orchestration
- idempotency replay / conflict behavior
- write-side admission gates
- storage store-level round-trip behavior
- database schema constraints
- Compass Layer 2 validation
- durable replay / rebuild validation
- Snapshot Trust Contract
- out-of-order buffering
- DLQ
- watermark semantics
- worker leasing
- checkpoint row locking
- distributed multi-worker coordination

Those belong to other test directories or later stages.

---

## Current Test File

### `test_postgres_projection_worker.py`

This file verifies the Stage 3.5C PR4 PostgreSQL-backed projection worker baseline.

It covers:

- empty accepted history returns `no_event`
- one `CREATED` event is applied to durable projection state
- one `PAID` event is applied after `CREATED`
- checkpoint progress advances to the processed `global_position`
- a new worker instance resumes from existing checkpoint progress
- no event is processed after checkpoint reaches the latest event
- non-`GLOBAL_POSITION` checkpoints are rejected
- projection-state / checkpoint mismatch fails fast
- projection state and checkpoint progress roll back together when checkpoint persistence fails

### `test_durable_replay_validation.py`

This file verifies the Stage 3.5C PR5 durable replay / rebuild validation baseline.

It covers:

- `MATCH` when persisted projection state equals replay-derived state
- `MISSING_PROJECTION` when accepted history exists but projection state is missing
- `DRIFT` when persisted projection state differs from replay-derived state
- `DRIFT` when persisted projection state is ahead of accepted-history replay
- `NO_ACCEPTED_HISTORY` when no accepted events exist for the order
- validation does not mutate `order_events`
- validation does not advance `projection_checkpoints`
- replay uses aggregate-local sequence order instead of global worker cursor order
- Decimal round-trip differences do not create false drift

---

## Transaction Boundary Claim

The most important test boundary is rollback behavior.

The worker must not leave behind:

```text
projection state updated
checkpoint not advanced
```

or:

```text
checkpoint advanced
projection state not updated
```

The rollback test simulates checkpoint persistence failure after projection state saving.

The expected result is:

```text
no projection state
no checkpoint progress
```

after the failed transaction.

---

## Cursor Boundary Claim

The worker only accepts:

```text
cursor_kind = GLOBAL_POSITION
```

because Stage 3.5C PR4 explicitly chooses `order_events.global_position` as the first durable accepted-history consumption cursor.

Other cursor kinds may exist in the schema for future strategies, but this worker must fail fast if loaded checkpoint progress does not use `GLOBAL_POSITION`.

---

## Fail-Fast Boundary Claim

The PostgreSQL-backed worker intentionally does not silently repair projection-state / checkpoint mismatch.

If durable projection state is already ahead of checkpoint progress, the worker fails fast instead of silently skipping and advancing the checkpoint.

Repair, rebuild, and recovery policy belong to later stages.

---

## Replay Validation Boundary Claim

Durable replay validation compares accepted-history replay through the canonical reducer with persisted projection state.

It does not mutate accepted history.

It does not advance checkpoint progress.

It does not decide Compass Layer 2 runtime policy.

The validation result remains a minimal physical correctness signal, not a Stage 4 `SemanticOutcome`.

---

## Test Database Boundary

These tests are destructive PostgreSQL integration tests.

They require:

```text
TEST_DATABASE_URL
```

and must run against the test database, not the development database.

At the current baseline, the expected test database is:

```text
compass_test
```

---

## Expected Commands

Run only the projection worker integration tests:

```bash
pytest tests/integration/pipeline/projection -v
```

Run all pipeline integration tests:

```bash
pytest tests/integration/pipeline -v
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

## Current Stage Status

```text
Stage 3.5C PR4 — Global-Position Projection Worker Baseline ✅
Stage 3.5C PR5 — Durable Replay / Rebuild Validation Baseline ✅
```

---

## Summary

These tests prove that the PostgreSQL-backed projection worker can consume accepted history, derive durable read-side state, and advance checkpoint progress without violating the read-side transaction boundary.
