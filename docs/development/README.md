# Development Setup

[← Back to Docs Home](../README.md)

This directory contains local development setup notes for **Streaming System + Compass**.

These documents explain how to run local infrastructure needed for development and testing.

They are practical setup notes, not architecture decisions.

---

## Purpose

The purpose of this directory is to document development environment setup clearly enough that the project can be reproduced locally.

As the project moves into Stage 3.5B durable persistence, local infrastructure becomes part of the development workflow.

The first focus is PostgreSQL because Stage 3.5B introduces durable write-side persistence.

---

## Current Development Setup Notes

| Document | Purpose |
|---|---|
| [Local PostgreSQL Setup](postgres_local_setup.md) | Explains how to start the local Docker-based PostgreSQL environment for Stage 3.5B durable write-side development. |

---

## Current Scope

This directory currently covers:

- local PostgreSQL startup
- Docker Compose usage
- local database connection settings
- localhost-only port binding
- local environment file conventions
- development-only infrastructure boundaries

---

## What This Directory Is Not

This directory is not:

- an ADR directory
- a production deployment guide
- a security hardening guide
- a replacement for architecture notes
- a migration history directory
- a place for runtime business rules

Production-grade concerns such as role-based database permissions, managed secrets, deployment topology, observability integration, and infrastructure-as-code should be documented separately when they become relevant.

---

## Stage 3.5B Context

Stage 3.5B focuses on the durable write-side baseline.

The local PostgreSQL setup is introduced to support:

- write-side schema migration experiments
- `PostgresEventStore` development
- `PostgresIdempotencyStore` development
- durable replay / retry / conflict tests
- later transactional append + idempotency record tests

The local database setup does not itself implement durable write-side behavior.

It only provides the environment needed to build and test that behavior.

---

## Recommended Reading

Start with:

1. [Local PostgreSQL Setup](postgres_local_setup.md)

Then continue with the Stage 3.5B architecture and boundary notes:

1. [Write-Side Schema Baseline](../architecture/write_side_schema_baseline.md)
2. [Stage 3.5B Write-Side Schema Translation Note](../boundary_notes/stage3.5B_write_side_schema_translation_note.md)

---

## Development Principle

Local infrastructure should be easy to start, easy to reset, and clearly separated from production assumptions.

For this project:

```text
local setup
→ reproducible development environment

architecture notes
→ why the system is shaped this way

boundary notes
→ what each layer owns

migrations / code
→ executable implementation
```

This separation keeps local setup useful without confusing it with production architecture.


