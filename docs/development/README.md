# Development Setup

[← Back to Docs Home](../README.md)

This directory contains local development setup notes for **Streaming System + Compass**.

These documents explain how to run local infrastructure needed for development and testing.
They are practical setup notes, not architecture decisions.

---

## Purpose

The purpose of this directory is to document the local development environment clearly enough that the project can be reproduced and tested locally.

At the current baseline, the main local infrastructure dependency is PostgreSQL.
PostgreSQL is used to support the Stage 3.5B durable write-side baseline and the Stage 3.5C PR0 durable order-event vocabulary hardening pass.

---

## Current Development Setup Notes

| Document | Purpose |
|---|---|
| [Local PostgreSQL Setup](postgres_local_setup.md) | Explains how to start the local Docker-based PostgreSQL environment, create the development and test databases, apply migrations, and run PostgreSQL integration tests. |

---

## Current Scope

This directory currently covers:

- local PostgreSQL startup through Docker Compose
- Docker container health check expectations
- local database connection settings
- localhost-only port binding
- development database vs test database separation
- `DATABASE_URL` vs `TEST_DATABASE_URL`
- local migration commands
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
TRUNCATE idempotency_records, order_events RESTART IDENTITY CASCADE;
```

The test fixture also verifies that the connected database name ends with `_test` before allowing destructive integration tests to run.

---

## Current Stage Boundary

This setup is current through:

```text
Stage 3.5B — Durable Write-Side Baseline
Stage 3.5C PR0 — Durable Order Event Vocabulary Hardening
```

The current durable write-side tables are:

```text
order_events
idempotency_records
```

Stage 3.5C PR0 has hardened the durable write-side vocabulary:

```text
event_type: CREATED / PAID
proof_prev_status: INIT / CREATED / PAID
unique constraint: uq_order_events_order_id_sequence
```

---

## Future Stage 3.5C Note

When Stage 3.5C durable read-side work begins, this setup document may need a small update to include the next read-side migration and tables.

Expected future read-side tables may include:

```text
projection_states
projection_checkpoints
```

The environment split should not change:

```text
DATABASE_URL      → compass_dev
TEST_DATABASE_URL → compass_test
```

Only the migration instructions and expected table list should be extended.

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
Stage 3.5C = durable read-side baseline
Stage 3.5D = snapshot trust / replay-efficiency work
Stage 3.5E = durable history and permission hardening
```

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

Then continue with the Stage 3.5B architecture and boundary notes:

1. [Write-Side Schema Baseline](../architecture/write_side_schema_baseline.md)
2. [Stage 3.5B Write-Side Schema Translation Note](../boundary_notes/stage3.5B_write_side_schema_translation_note.md)
3. [Implementation Roadmap](../roadmap/implementation_roadmap.md)

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

migrations / code / tests
→ executable implementation
```

This separation keeps local setup useful without confusing it with production architecture.
