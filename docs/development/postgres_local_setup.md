# Local PostgreSQL Setup

[← Back to Docs Home](../README.md)

## Purpose

This document explains how to start the local PostgreSQL environment for Stage 3.5B durable write-side development.

The local database is used for:

- write-side schema migration experiments
- `PostgresEventStore` development
- `PostgresIdempotencyStore` development
- durable replay / retry / conflict tests

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

## Connect to PostgreSQL

Use:

```bash
docker exec -it streaming_compass_postgres psql -U compass_user -d compass_dev
```

Inside `psql`, check the current database:

```sql
SELECT current_database();
```

Expected result:

```text
compass_dev
```

List tables:

```sql
\dt
```

At this stage, no tables are expected yet because the write-side migration has not been added.

Exit:

```sql
\q
```

---

## Stop PostgreSQL

```bash
docker compose down
```

This stops the container but keeps the database volume.

---

## Reset Local Database Data

If you need to remove local database data completely:

```bash
docker compose down -v
```

Use this carefully.

It deletes the local PostgreSQL volume.

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

Example connection URL:

```text
postgresql://compass_user:compass_password@localhost:5433/compass_dev
```

---

## Security Note

The local PostgreSQL container binds host port `5433` to container port `5432` on `127.0.0.1` only:

```yaml
ports:
  - "127.0.0.1:5433:5432"
```

The host port uses `5433` to avoid conflicts with an existing local PostgreSQL service that may already be using `5432`.

This prevents the development database from being exposed to the local network.

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

---

## Stage 3.5B Boundary

This local PostgreSQL setup is only the development environment.

It does not yet implement:

- write-side migrations
- `PostgresEventStore`
- `PostgresIdempotencyStore`
- transactional append + idempotency write
- production-grade DB roles / permissions
- append-only trigger enforcement

Those belong to later Stage 3.5B commits.

---

## Expected First-Time Flow

From the repository root:

```bash
docker compose up -d
docker compose ps
docker exec -it streaming_compass_postgres psql -U compass_user -d compass_dev
```

Inside `psql`:

```sql
SELECT current_database();
\dt
\q
```

At this point, seeing no relations is expected.

The next Stage 3.5B step is to add the initial write-side schema migration.
