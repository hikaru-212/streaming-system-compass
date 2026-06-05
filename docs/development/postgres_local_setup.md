# Local PostgreSQL Setup

[← Back to Development Setup](README.md)

## Purpose

This document explains how to start the local PostgreSQL environment and run the PostgreSQL-backed integration tests for **Streaming System + Compass** at the end of **Stage 3.5B** and **Stage 3.5C PR0**.

The local PostgreSQL environment is used for:

- durable write-side schema migration checks
- `PostgresEventStore` integration tests
- `PostgresIdempotencyStore` integration tests
- PostgreSQL-backed transactional write-side tests
- PostgreSQL-backed concurrency admission tests
- durable order-event vocabulary / schema-constraint tests

At the current stage, PostgreSQL is used for the durable write-side baseline.

Durable read-side tables are not part of this setup yet.

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
TRUNCATE idempotency_records, order_events RESTART IDENTITY CASCADE;
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

At the end of Stage 3.5B / Stage 3.5C PR0, the current durable write-side migration is:

```text
db/migrations/001_create_write_side_tables.sql
```

Apply it to the development database when you want to inspect tables manually:

```bash
psql "$DATABASE_URL" -f db/migrations/001_create_write_side_tables.sql
```

Apply it to the test database before running PostgreSQL integration tests:

```bash
psql "$TEST_DATABASE_URL" -f db/migrations/001_create_write_side_tables.sql
```

The current migration creates the durable write-side tables:

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

Expected tables after migration:

```text
order_events
idempotency_records
```

---

## Run PostgreSQL Integration Tests

After setting `TEST_DATABASE_URL` and applying the migration to `compass_test`, run:

```bash
pytest tests/integration -v
```

Or run only PostgreSQL storage / transactional integration tests if needed:

```bash
pytest tests/integration/storage -v
pytest tests/integration/pipeline -v
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
```

It supports:

- durable accepted history through `order_events`
- durable idempotency memory through `idempotency_records`
- PostgreSQL-backed transactional write-side execution
- PostgreSQL-backed concurrency admission
- durable event vocabulary and proof-status schema constraints
- destructive integration tests isolated through `TEST_DATABASE_URL`

It does not yet include:

- durable read-side tables
- `projection_states`
- `projection_checkpoints`
- `PostgresProjectionStore`
- `PostgresCheckpointStore`
- PostgreSQL-backed projection worker
- production-grade DB roles / permissions
- append-only trigger enforcement

Those belong to later stages.

---

## Future Stage 3.5C Note

When Stage 3.5C adds durable read-side tables, this setup document should be updated again.

The likely update will be small:

- add the new read-side migration command, for example `002_create_read_side_tables.sql`
- mention the new tables, such as `projection_states` and `projection_checkpoints`
- update the expected schema inspection output
- update test instructions if new integration test directories or migration steps are added

The core separation should remain the same:

```text
DATABASE_URL      → compass_dev  → local development / manual inspection
TEST_DATABASE_URL → compass_test → destructive integration tests
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

# 4. Apply migration to the test database
psql "$TEST_DATABASE_URL" -f db/migrations/001_create_write_side_tables.sql

# 5. Run tests
pytest tests/integration -v
```
