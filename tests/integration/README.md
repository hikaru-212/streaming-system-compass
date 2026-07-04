# Integration Tests

[← Back to Tests README](../README.md)

This directory contains integration tests for **Streaming System + Compass**.

Integration tests verify behavior across module boundaries, especially where runtime orchestration meets persistence, transaction control, replay, projection, checkpointing, snapshot persistence, snapshot-assisted replay, database role / privilege boundaries, and destructive PostgreSQL test setup.

These tests are not general pytest examples. They are executable architecture claims.

---

## Purpose

The purpose of this directory is to verify that independently designed components still preserve the intended system boundaries when they are wired together.

The integration test layer focuses on questions such as:

- Does runtime orchestration call the correct components in the correct order?
- Do PostgreSQL-backed stores preserve durable facts across transactions?
- Do destructive database tests run only against the test database?
- Do write-side and read-side transaction boundaries prevent partial durable state?
- Do in-memory baselines and PostgreSQL-backed baselines preserve the same conceptual semantics?
- Does durable projection state remain derived from accepted history?
- Does snapshot persistence preserve derived evidence without becoming authority?
- Does snapshot-assisted replay compare against accepted-history authority?
- Does snapshot-assisted state resolution replay tail events through the canonical reducer?
- Do runtime database roles have only the durable-table privileges intended by Stage 3.5E?

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

Stage 3.5D also adds snapshot-assisted projection boundaries:

```text
projection snapshot
+
tail replay
+
authority comparison / resolver evidence
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
- projection snapshots
- global-position event loading
- schema constraints
- test database isolation

These tests focus on store-level and schema-level behavior.

They do not own pipeline orchestration.

See:

- [Storage Integration Tests](storage/README.md)

---

### [security/](security/)

Contains PostgreSQL-backed permission-boundary integration tests.

The security tests verify the Stage 3.5E durable-history and permission-hardening boundary for:

- accepted history mutation restrictions
- successful idempotency receipt rewrite restrictions
- accepted-history global-position sequence access
- derived-state controlled mutation through intended roles
- projection snapshot insert-oriented evidence protection

These tests focus on effective PostgreSQL role privileges.

They do not own storage mechanics, production login identity wiring, connection-pool isolation, full RBAC, or Stage 4 runtime governance.

See:

- [Security Integration Tests](security/README.md)

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
projection_snapshots
projection_checkpoints
projection_states
idempotency_records
order_events
```

The cleanup fixture resets these tables before each database integration test:

```text
TRUNCATE
    projection_snapshots,
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
Stage 3.5C PR5 — Durable Replay / Rebuild Validation Baseline
Stage 3.5D PR2 — Projection Snapshot Schema Baseline
Stage 3.5D PR3 — PostgresProjectionSnapshotStore
Stage 3.5D PR4 — Projection Snapshot-Assisted Replay Validator
Stage 3.5D PR4.5 — Projection Snapshot-Assisted State Resolver
Stage 3.5E PR3 — Accepted-History Mutation Hardening Tests
Stage 3.5E PR4 — Derived-State Mutation Permission Tests
Stage 3.5E PR5 — Minimal Actor Metadata Boundary
Stage 3.5E PR6 — Stage 3.5E Closeout
```

The Stage 3.5C integration direction includes durable replay / rebuild validation:

```text
Stage 3.5C PR5 — Durable Replay / Rebuild Validation Baseline
```

The Stage 3.5D integration direction adds projection snapshot trust / replay-efficiency boundaries:

```text
Stage 3.5D PR4 — snapshot-assisted replay validator
Stage 3.5D PR4.5 — snapshot-assisted state resolver
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
10. Durable replay validation can compare accepted-history replay with persisted projection state.
11. Durable replay validation can detect `MATCH`, `MISSING_PROJECTION`, `DRIFT`, and `NO_ACCEPTED_HISTORY`.
12. Durable replay validation does not mutate accepted history, projection state, or checkpoint progress.
13. Projection snapshots can be persisted and loaded as derived state-compression artifacts.
14. Projection snapshot duplicate writes can be classified as benign idempotent writes or inconsistent evidence collisions.
15. Snapshot-assisted replay validation can compare snapshot + tail replay against full accepted-history replay.
16. Snapshot-assisted state resolution can reconstruct state from a qualified snapshot and tail events without deciding broader fallback policy.
17. Stage 3.5E permission tests verify that accepted history and successful idempotency receipts are protected differently from derived runtime artifacts.
18. Runtime roles can be probed through `SET ROLE` without converting ordinary storage / mechanism integration tests into low-privilege tests.
19. In-memory baselines still explain the conceptual runtime model that the durable paths extend.

---

## What These Tests Do Not Prove Yet

These tests do not yet prove:

- full Compass Layer 2 runtime governance
- structured `SemanticOutcome`
- runtime decision policy
- action safety
- persisted snapshot validation receipts
- automatic snapshot quarantine or repair
- production login identity wiring
- production connection-pool role isolation
- full RBAC / authentication infrastructure
- append-only trigger enforcement
- out-of-order buffering
- DLQ
- watermark semantics
- worker leasing
- checkpoint row locking
- distributed multi-worker coordination

Those belong to later stages or future test directories.

Stage 3.5D proves snapshot trust and replay-efficiency baselines, not full runtime governance.

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

Run security permission-boundary integration tests:

```bash
pytest tests/integration/security -v
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

## Required Migration Baseline

PostgreSQL-backed integration tests currently assume the write-side, read-side, global-position, and snapshot migrations have been applied to the test database:

```bash
psql "$TEST_DATABASE_URL" -f db/migrations/001_create_write_side_tables.sql
psql "$TEST_DATABASE_URL" -f db/migrations/002_create_read_side_tables.sql
psql "$TEST_DATABASE_URL" -f db/migrations/003_add_order_events_global_position.sql
psql "$TEST_DATABASE_URL" -f db/migrations/004_create_projection_snapshots.sql
psql "$TEST_DATABASE_URL" -f db/migrations/005_create_durable_state_permission_roles.sql
```

This requirement matters because Stage 3.5D tests depend on `projection_snapshots` and snapshot source-boundary fields, while Stage 3.5E security tests depend on runtime responsibility roles and table-level grants.

---

## Recommended Reading Order

For the full integration-test story, read:

1. [In-Memory Integration Tests](in_memory/README.md)
2. [Storage Integration Tests](storage/README.md)
3. [Pipeline Integration Tests](pipeline/README.md)
4. [Transactional Pipeline Integration Tests](pipeline/transactional/README.md)
5. [Projection Pipeline Integration Tests](pipeline/projection/README.md)
6. [Security Integration Tests](security/README.md)

This order shows how the system evolves from simple executable semantics into durable PostgreSQL-backed runtime boundaries, and then into snapshot-assisted read-side replay / resolution.

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
+ snapshot trust
+ permission boundary
```

without collapsing those responsibilities into one layer.
