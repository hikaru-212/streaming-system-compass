# Development Setup

[← Back to Docs Home](../README.md)

This directory contains local development setup notes for **Streaming System + Compass**.

These documents explain how to run local infrastructure needed for development and testing.
They are practical setup notes, not architecture decisions.

---

## Purpose

The purpose of this directory is to document the local development environment clearly enough that the project can be reproduced and tested locally.

At the current baseline, the main local infrastructure dependency is PostgreSQL.

PostgreSQL is used to support:

- the Stage 3.5B durable write-side baseline
- the Stage 3.5C durable read-side baseline
- the Stage 3.5D PR2 projection snapshot schema baseline

---

## Current Development Setup Notes

| Document | Purpose |
|---|---|
| [Local PostgreSQL Setup](postgres_local_setup.md) | Explains how to start the local Docker-based PostgreSQL environment, create the development and test databases, apply migrations through the projection snapshot schema baseline, and run PostgreSQL integration tests. |

---

## Current Scope

This directory currently covers:

- local PostgreSQL startup through Docker Compose
- Docker container health check expectations
- local database connection settings
- localhost-only port binding
- development database vs test database separation
- `DATABASE_URL` vs `TEST_DATABASE_URL`
- local write-side and read-side migration commands
- global-position migration command
- projection snapshot schema migration command
- destructive PostgreSQL integration test guardrails
- development-only infrastructure boundaries

---

## Development Database vs Test Database

The project intentionally separates local development and destructive integration testing:

```text
compass_dev
= local development / manual inspection / local demo database

compass_test
= destructive PostgreSQL integration test database
```

The intended environment variables are:

```text
DATABASE_URL
= points to compass_dev

TEST_DATABASE_URL
= points to compass_test
```

Destructive PostgreSQL integration tests must use `TEST_DATABASE_URL`.
They should not run against `DATABASE_URL` directly.

This matters because the integration test fixture may reset durable tables through destructive cleanup such as:

```sql
TRUNCATE
    projection_snapshots,
    projection_checkpoints,
    projection_states,
    idempotency_records,
    order_events
RESTART IDENTITY CASCADE;
```

The test fixture also verifies that the connected database name ends with `_test` before allowing destructive integration tests to run.

---

## Current Stage Boundary

This setup is current through:

```text
Stage 3.5B — Durable Write-Side Baseline
Stage 3.5C PR0 — Durable Order Event Vocabulary Hardening
Stage 3.5C PR1 — Durable Read-Side Schema Baseline
Stage 3.5C PR2 — PostgresProjectionStore
Stage 3.5C PR3 — PostgresCheckpointStore
Stage 3.5C PR4 — Global-Position Projection Worker Baseline
Stage 3.5C PR5 — Durable Replay / Rebuild Validation Baseline
Stage 3.5D PR1 — Snapshot Trust Contract Boundary
Stage 3.5D PR1.5 — CI Stage Branch Checks
Stage 3.5D PR2 — Projection Snapshot Schema Baseline
```

The current durable write-side tables are:

```text
order_events
idempotency_records
```

Stage 3.5C PR0 hardened the durable write-side vocabulary:

```text
event_type: CREATED / PAID
proof_prev_status: INIT / CREATED / PAID
unique constraint: uq_order_events_order_id_sequence
```

Stage 3.5C PR1 added the durable read-side schema baseline:

```text
projection_states
projection_checkpoints
```

The read-side schema baseline supports:

```text
projection_states
= durable derived read-side state

projection_checkpoints
= durable projection worker progress metadata
```

Stage 3.5C PR4 added:

```text
order_events.global_position
= durable accepted-history consumption cursor
```

Stage 3.5D PR2 adds the durable projection snapshot schema baseline:

```text
projection_snapshots
= derived projection snapshot artifacts with source-boundary evidence
```

At this stage, the local PostgreSQL setup includes durable accepted history, durable idempotency memory, durable projection state, durable checkpoint progress, global-position accepted-history consumption, durable replay / rebuild validation, and the initial projection snapshot schema.

---

## Current Migrations

Through Stage 3.5D PR2, local PostgreSQL setup requires four migrations:

```text
db/migrations/001_create_write_side_tables.sql
db/migrations/002_create_read_side_tables.sql
db/migrations/003_add_order_events_global_position.sql
db/migrations/004_create_projection_snapshots.sql
```

The expected migration order is:

```bash
psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/001_create_write_side_tables.sql
psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/002_create_read_side_tables.sql
psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/003_add_order_events_global_position.sql
psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/004_create_projection_snapshots.sql
```

Use `DATABASE_URL` instead of `TEST_DATABASE_URL` only when applying migrations to the local development database for manual inspection.

If running migrations through the same automatic loop used by CI, the expected local command is:

```bash
for migration in db/migrations/*.sql; do
  echo "Applying ${migration}..."
  psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f "$migration"
done
```

---

## Projection Snapshot Schema Boundary

Stage 3.5D PR2 introduces `projection_snapshots`.

The table records a derived projection snapshot at a specific accepted-history boundary.

The source-boundary uniqueness rules are:

```text
source_event_id
= globally unique accepted-event boundary

(order_id, source_event_sequence)
= order-local accepted-event sequence boundary

source_global_position
= globally unique accepted-history cursor boundary
```

The physical uniqueness constraints are therefore:

```text
UNIQUE(source_event_id)
UNIQUE(order_id, source_event_sequence)
UNIQUE(source_global_position)
```

This preserves the distinction between:

```text
source_event_sequence
= aggregate-local sequence

source_global_position
= global accepted-history cursor

source_event_id
= accepted event identity
```

Projection snapshots remain derived, discardable artifacts.

They do not replace accepted history.

---

## What This Directory Is Not

This directory is not:

- an ADR directory
- a production deployment guide
- a production security hardening guide
- a replacement for architecture notes
- a migration history directory
- a place for runtime business rules

Production-grade concerns such as database role hardening, managed secrets, deployment topology, observability integration, infrastructure-as-code, and append-only trigger enforcement should be documented separately when they become relevant.

Current roadmap alignment:

```text
Stage 3.5C = durable read-side baseline completed
Stage 3.5D = snapshot trust / replay-efficiency work in progress
Stage 3.5E = durable history and permission hardening
```

The next expected development setup expansion is Stage 3.5D PR3 if `PostgresProjectionSnapshotStore` introduces new local testing instructions.

---

## Docker Compose Boundary

The current Docker Compose service creates the local PostgreSQL server and initializes the default development database:

```text
POSTGRES_DB=compass_dev
```

This is enough for local development.

The test database `compass_test` is created manually once, as documented in [Local PostgreSQL Setup](postgres_local_setup.md).

Keeping `compass_test` as an explicit setup step is acceptable at this stage because it makes the destructive-test boundary visible instead of hiding it inside container startup behavior.

---

## Recommended Reading

Start with:

1. [Local PostgreSQL Setup](postgres_local_setup.md)

Then continue with the current architecture and boundary notes:

1. [Write-Side Schema Baseline](../architecture/write_side_schema_baseline.md)
2. [Read-Side Schema Baseline](../architecture/read_side_schema_baseline.md)
3. [Snapshot Trust Contract](../architecture/snapshot_trust_contract.md)
4. [Stage 3.5B Write-Side Schema Translation Note](../boundary_notes/stage3.5B_write_side_schema_translation_note.md)
5. [Read-Side Persistence Boundary](../boundary_notes/read_side_persistence_boundary.md)
6. [Global-Position Projection Worker Boundary](../boundary_notes/global_position_projection_worker_boundary.md)
7. [Durable Replay / Rebuild Validation Boundary](../boundary_notes/durable_replay_rebuild_validation_boundary.md)
8. [Snapshot Trust Contract Boundary](../boundary_notes/snapshot_trust_contract_boundary.md)
9. [Projection Snapshot Schema Baseline](../implementation_notes/projection_snapshot_schema_baseline.md)
10. [Implementation Roadmap](../roadmap/implementation_roadmap.md)

---

## Development Principle

Local infrastructure should be easy to start, easy to reset, and clearly separated from production assumptions.

For this project:

```text
local setup
→ reproducible development and test environment

DATABASE_URL
→ local development database

TEST_DATABASE_URL
→ destructive integration test database

architecture notes
→ why the system is shaped this way

boundary notes
→ what each layer owns

implementation notes
→ how stage-level and PR-level execution details are planned

migrations / code / tests
→ executable implementation
```

This separation keeps local setup useful without confusing it with production architecture.
