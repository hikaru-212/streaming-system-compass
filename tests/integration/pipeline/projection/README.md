# Projection Pipeline Integration Tests

[← Back to Pipeline Integration Tests](../README.md)

This directory contains integration tests for the projection pipeline.

These tests are executable architecture claims for the read-side runtime boundary.

At the current Stage 3.5C PR5 baseline, the tests cover both the PostgreSQL-backed projection worker path and durable replay / rebuild validation:

```text
order_events
→ PostgresProjectionEligibleEventSource
→ PostgresProjectionWorker
→ canonical reducer
→ PostgresProjectionStore
→ PostgresProjectionProgressStore
```

---

## Purpose

The purpose of these tests is to verify that accepted history can be consumed by a durable projection worker and that persisted read-side state can be checked against accepted-history replay.

The key invariant is:

```text
projection state
+
per-order projection progress
```

must be persisted inside one read-side transaction boundary.

---

## Responsible For

These tests verify:

- PostgreSQL-backed projection worker behavior
- exact-next per-order accepted-event eligibility
- canonical reducer integration
- projection state persistence through `PostgresProjectionStore`
- progress persistence through `PostgresProjectionProgressStore`
- safe resume from repaired per-order progress
- commit-inversion and rollback-gap behavior
- rollback behavior when progress saving fails after projection state save
- fail-fast behavior for mixed connections and outer transactions
- legacy checkpoints not bootstrapping repaired progress

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
- exact-next per-order progress advances with accepted-event lineage
- a new worker instance resumes from repaired progress
- late lower-position commits remain eligible for their own order
- rollback sequence gaps do not block unrelated orders
- projection-state / progress mismatch fails fast
- projection state and progress roll back together on progress failure

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
progress not advanced
```

or:

```text
progress advanced
projection state not updated
```

The rollback test simulates progress persistence failure after projection state saving.

The expected result is:

```text
no projection state
no per-order progress
```

after the failed transaction.

---

## Progress Boundary Claim

The repaired worker uses `(projection_name, projection_epoch, order_id)` and
advances only the exact next order-local sequence. Generic checkpoint rows
remain available but are not a correctness cursor or repaired-progress seed.
The production worker is fixed to `order_state_projection`, epoch 1; the
current `projection_states` table does not support concurrent epochs.

---

## Fail-Fast Boundary Claim

The PostgreSQL-backed worker intentionally does not silently repair
projection-state / per-order-progress mismatch.

If projection state cannot apply the exact-next event selected by repaired
progress, the worker fails fast rather than silently skipping.

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
Stage 3.5C repaired per-order projection progress ✅
Stage 3.5C PR5 — Durable Replay / Rebuild Validation Baseline ✅
```

---

## Summary

These tests prove that the PostgreSQL-backed projection worker can consume
exact-next per-order accepted history and atomically persist derived state with
repaired progress.
