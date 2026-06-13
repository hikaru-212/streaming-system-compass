# Local PostgreSQL Setup

[← Back to Development Setup](README.md)

## Purpose

This document explains how to start the local PostgreSQL environment and run the PostgreSQL-backed integration tests for **Streaming System + Compass** through **Stage 3.5D PR2 — Projection Snapshot Schema Baseline**.

The local PostgreSQL environment is used for:

- durable write-side schema migration checks
- durable read-side schema migration checks
- projection snapshot schema migration checks
- `PostgresEventStore` integration tests
- `PostgresIdempotencyStore` integration tests
- PostgreSQL-backed transactional write-side tests
- PostgreSQL-backed concurrency admission tests
- durable order-event vocabulary / schema-constraint tests
- durable read-side schema-constraint tests
- projection snapshot schema-constraint tests
- `PostgresProjectionStore` integration tests
- `PostgresCheckpointStore` integration tests
- PostgreSQL-backed projection worker integration tests
- durable replay / rebuild validation integration tests

At the current stage, PostgreSQL is used for:

- the durable write-side baseline
- the durable read-side baseline
- global-position projection worker execution
- durable replay / rebuild validation
- the projection snapshot schema baseline

PostgreSQL-backed read-side stores, checkpoint stores, projection worker orchestration, replay validation, and projection snapshot schema constraints are now part of the local setup.

---

## Database Separation

This project uses two local PostgreSQL databases with different purposes:

```text
compass_dev
= local development / manual inspection / non-destructive experiments

compass_test
= destructive PostgreSQL integration tests
```

The distinction is important because integration tests may run destructive cleanup such as:

```sql
TRUNCATE
    projection_snapshots,
    projection_checkpoints,
    projection_states,
    idempotency_records,
    order_events
RESTART IDENTITY CASCADE;
```

Those tests must never run against the development database.

---

## Start PostgreSQL

From the repository root:

```bash
docker compose up -d
```

Check container status:

```bash
docker compose ps
```

Expected service:

```text
streaming_compass_postgres
```

The service may take a few seconds to become healthy because PostgreSQL needs time to initialize.

---

## Connection Settings

The local development settings are:

```text
host: localhost
port: 5433
database: compass_dev
user: compass_user
password: compass_password
```

Development connection URL:

```text
postgresql://compass_user:compass_password@localhost:5433/compass_dev
```

Test connection URL:

```text
postgresql://compass_user:compass_password@localhost:5433/compass_test
```

---

## Environment Variables

For normal local development or manual inspection, use:

```bash
export DATABASE_URL="postgresql://compass_user:compass_password@localhost:5433/compass_dev"
```

For destructive PostgreSQL integration tests, use:

```bash
export TEST_DATABASE_URL="postgresql://compass_user:compass_password@localhost:5433/compass_test"
```

`TEST_DATABASE_URL` is required for PostgreSQL integration tests.

The test fixtures connect through `TEST_DATABASE_URL` and refuse to run destructive PostgreSQL tests unless the current database name ends with `_test`.

This protects `compass_dev` from accidental truncation.

---

## Create the Test Database

Docker Compose creates the default development database from the container environment.

If `compass_test` does not exist yet, create it manually:

```bash
docker exec -it streaming_compass_postgres \
  psql -U compass_user -d postgres \
  -c "CREATE DATABASE compass_test;"
```

If the database already exists, PostgreSQL will report that it already exists. That is fine.

To check available databases:

```bash
docker exec -it streaming_compass_postgres \
  psql -U compass_user -d postgres \
  -c "SELECT datname FROM pg_database ORDER BY datname;"
```

You should see both:

```text
compass_dev
compass_test
```

---

## Run Migrations

Through Stage 3.5D PR2, the local PostgreSQL setup uses four baseline migrations:

```text
db/migrations/001_create_write_side_tables.sql
db/migrations/002_create_read_side_tables.sql
db/migrations/003_add_order_events_global_position.sql
db/migrations/004_create_projection_snapshots.sql
```

Apply them to the development database when you want to inspect tables manually:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/001_create_write_side_tables.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/002_create_read_side_tables.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/003_add_order_events_global_position.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/004_create_projection_snapshots.sql
```

Apply them to the test database before running PostgreSQL integration tests:

```bash
psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/001_create_write_side_tables.sql
psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/002_create_read_side_tables.sql
psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/003_add_order_events_global_position.sql
psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/004_create_projection_snapshots.sql
```

The CI workflow may also apply migrations automatically by iterating through `db/migrations/*.sql` in filename order:

```bash
for migration in db/migrations/*.sql; do
  echo "Applying ${migration}..."
  psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f "$migration"
done
```

The write-side migration creates:

```text
order_events
idempotency_records
```

It also includes the Stage 3.5C PR0 durable vocabulary hardening:

```text
event_type IN ('CREATED', 'PAID')
proof_prev_status IN ('INIT', 'CREATED', 'PAID')
uq_order_events_order_id_sequence
```

The read-side migration creates:

```text
projection_states
projection_checkpoints
```

The global-position migration adds:

```text
order_events.global_position
```

This column is used by the PostgreSQL-backed projection worker as the durable accepted-history consumption cursor.

The projection snapshot migration creates:

```text
projection_snapshots
```

This table stores derived projection snapshot artifacts with accepted-history source-boundary evidence.

---

## Projection Snapshot Source Boundaries

`projection_snapshots` records three source-boundary fields:

```text
source_event_id
source_event_sequence
source_global_position
```

Their meanings are intentionally different:

```text
source_event_id
= accepted event identity
= globally unique source boundary

source_event_sequence
= aggregate-local accepted event sequence
= unique only within one order stream

source_global_position
= global accepted-history cursor
= globally unique source boundary
```

Therefore Stage 3.5D PR2 enforces:

```text
UNIQUE(source_event_id)
UNIQUE(order_id, source_event_sequence)
UNIQUE(source_global_position)
```

It intentionally does not enforce:

```text
UNIQUE(order_id, source_global_position)
```

because `source_global_position` is already global by definition.

It also intentionally avoids enforcing:

```text
state_version = source_event_sequence
```

as a permanent database law.

The physical rule is:

```text
state_version <= source_event_sequence
```

Current-domain equality, if needed, belongs to future Python trust validation.

---

## Verify the Test Database Schema

To inspect the test database tables:

```bash
docker exec -it streaming_compass_postgres \
  psql -U compass_user -d compass_test
```

Inside `psql`:

```sql
SELECT current_database();
\dt
\q
```

Expected database:

```text
compass_test
```

Expected tables after migrations:

```text
order_events
idempotency_records
projection_states
projection_checkpoints
projection_snapshots
```

Expected additional event-log column after migration 003:

```text
order_events.global_position
```

To inspect the event-log position and read-side table constraints:

```bash
psql "$TEST_DATABASE_URL" -c "\d order_events"
psql "$TEST_DATABASE_URL" -c "\d projection_states"
psql "$TEST_DATABASE_URL" -c "\d projection_checkpoints"
psql "$TEST_DATABASE_URL" -c "\d projection_snapshots"
```

Expected projection snapshot constraints include:

```text
ck_projection_snapshots_order_id_not_empty
ck_projection_snapshots_source_event_sequence_positive
ck_projection_snapshots_source_global_position_positive
ck_projection_snapshots_state_status_valid
ck_projection_snapshots_total_amount_non_negative
ck_projection_snapshots_paid_amount_non_negative
ck_projection_snapshots_paid_amount_not_greater_than_total
ck_projection_snapshots_state_version_non_negative
ck_projection_snapshots_state_version_not_ahead_of_source_sequence
ck_projection_snapshots_schema_version_positive
ck_projection_snapshots_reducer_version_not_empty
ck_projection_snapshots_payload_hash_not_empty
ck_projection_snapshots_created_by_not_empty
ck_projection_snapshots_metadata_is_object
uq_projection_snapshots_source_event_id
uq_projection_snapshots_order_id_source_event_sequence
uq_projection_snapshots_source_global_position
```

Expected projection snapshot indexes include:

```text
idx_projection_snapshots_order_id_source_global_position_desc
idx_projection_snapshots_order_id_created_at_desc
```

---

## Run PostgreSQL Integration Tests

After setting `TEST_DATABASE_URL` and applying all migrations to `compass_test`, run:

```bash
pytest tests/integration -v
```

Or run only PostgreSQL storage / pipeline integration tests if needed:

```bash
pytest tests/integration/storage -v
pytest tests/integration/pipeline -v
pytest tests/integration/pipeline/projection -v
```

To run projection snapshot schema constraint tests only:

```bash
pytest tests/integration/storage/test_projection_snapshot_schema_constraints.py -v
```

To run durable replay / rebuild validation tests only:

```bash
pytest tests/integration/pipeline/projection/test_durable_replay_validation.py -v
```

To run only the durable read-side schema constraint tests:

```bash
pytest tests/integration/storage/test_read_side_schema_constraints.py -v
```

The exact test directories may evolve, but destructive PostgreSQL tests should continue to use `TEST_DATABASE_URL` rather than `DATABASE_URL`.

---

## Reset Local Database Data

To clear only the test data through tests, prefer using the existing test fixtures.

To completely reset the local PostgreSQL volume:

```bash
docker compose down -v
```

Use this carefully.

It deletes the local PostgreSQL volume, including both `compass_dev` and `compass_test`.

After resetting the volume, restart PostgreSQL, recreate `compass_test`, and rerun migrations.

---

## Stop PostgreSQL

```bash
docker compose down
```

This stops the container but keeps the database volume.

---

## Security Note

The local PostgreSQL container should bind host port `5433` to container port `5432` on `127.0.0.1` only:

```yaml
ports:
  - "127.0.0.1:5433:5432"
```

The host port uses `5433` to avoid conflicts with an existing local PostgreSQL service that may already be using `5432`.

Binding to `127.0.0.1` prevents the development database from being exposed to the local network.

Do not change this to:

```yaml
ports:
  - "5433:5432"
```

unless you intentionally want the database to listen on all host interfaces.

For local development, binding to localhost is the safer default.

---

## Environment Files

`.env.example` may be committed because it documents the expected local development variables.

A real `.env` file should not be committed.

The repository should ignore local environment files such as:

```gitignore
.env
.env.*
!.env.example
```

This keeps real local secrets out of Git while still preserving a usable example configuration.

A local `.env.example` may include placeholders such as:

```text
DATABASE_URL=postgresql://compass_user:compass_password@localhost:5433/compass_dev
TEST_DATABASE_URL=postgresql://compass_user:compass_password@localhost:5433/compass_test
```

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

It supports:

- durable accepted history through `order_events`
- durable idempotency memory through `idempotency_records`
- durable projection state schema through `projection_states`
- durable checkpoint schema through `projection_checkpoints`
- durable projection snapshot schema through `projection_snapshots`
- durable projection state persistence through `PostgresProjectionStore`
- durable checkpoint progress persistence through `PostgresCheckpointStore`
- global-position accepted-history consumption through `order_events.global_position`
- PostgreSQL-backed projection worker orchestration
- durable replay / rebuild validation against accepted history
- PostgreSQL-backed transactional write-side execution
- PostgreSQL-backed concurrency admission
- durable event vocabulary and proof-status schema constraints
- durable read-side schema constraints
- projection snapshot schema constraints
- destructive integration tests isolated through `TEST_DATABASE_URL`

It does not yet include:

- `PostgresProjectionSnapshotStore`
- snapshot trust validator
- snapshot-assisted replay validator
- aggregate snapshots
- write-side snapshot-assisted rehydration
- Compass Layer 2 validation
- production-grade DB roles / permissions
- append-only trigger enforcement

Those belong to later stages.

The next local setup expansion is expected during Stage 3.5D PR3 if snapshot store integration tests introduce new setup details.

---

## Stage 3.5D PR2 Completion Note

Stage 3.5D PR2 now includes the projection snapshot schema baseline:

- `projection_snapshots`
- snapshot identity
- order identity
- accepted-history source boundary fields
- projected state payload fields
- snapshot trust metadata fields
- physical shape constraints
- globally unique `source_event_id`
- order-local unique `(order_id, source_event_sequence)`
- globally unique `source_global_position`
- projection snapshot schema constraint tests

The core separation remains the same:

```text
accepted history
= source of truth

projection_snapshots
= derived snapshot artifacts

DATABASE_URL
= compass_dev
= local development / manual inspection

TEST_DATABASE_URL
= compass_test
= destructive integration tests
```

---

## Expected First-Time Flow

From the repository root:

```bash
# 1. Start PostgreSQL
docker compose up -d

docker compose ps

# 2. Create the test database if needed
docker exec -it streaming_compass_postgres \
  psql -U compass_user -d postgres \
  -c "CREATE DATABASE compass_test;"

# 3. Export local URLs
export DATABASE_URL="postgresql://compass_user:compass_password@localhost:5433/compass_dev"
export TEST_DATABASE_URL="postgresql://compass_user:compass_password@localhost:5433/compass_test"

# 4. Apply migrations to the test database
psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/001_create_write_side_tables.sql
psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/002_create_read_side_tables.sql
psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/003_add_order_events_global_position.sql
psql "$TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/004_create_projection_snapshots.sql

# 5. Inspect the projection snapshot schema if needed
psql "$TEST_DATABASE_URL" -c "\d projection_snapshots"

# 6. Run tests
pytest tests/integration -v
```
