# In-Memory Integration Tests

[← Back to Tests README](../../README.md)

This directory contains in-memory integration tests for the transactional write-side baseline.

These tests verify semantic composition without PostgreSQL durability.

They are intentionally separated from PostgreSQL-backed integration tests because they do not exercise:

- physical database persistence
- PostgreSQL transactions
- `TEST_DATABASE_URL`
- migration readiness
- durable event-store behavior
- durable idempotency-store behavior

---

## Purpose

The purpose of these tests is to verify that the in-memory write-side components preserve the original semantic boundaries of the system.

They focus on how the transactional registry composes:

- idempotency classification
- aggregate rehydration
- candidate event creation
- Compass Layer 1 validation
- replay consistency
- admission behavior
- in-memory accepted-history updates

These tests protect the semantic baseline that later PostgreSQL-backed implementations must preserve.

---

## Current Scope

This directory currently includes tests for:

- registry behavior with Compass enabled
- registry behavior without Compass
- request replay and conflict classification
- transaction flow for create / pay
- replay consistency
- in-memory concurrency admission behavior

---

## What These Tests Prove

These tests prove that the original in-memory write-side flow preserves key semantic claims:

1. request replay is classified correctly
2. conflicting requests do not overwrite accepted history
3. Compass validation can block invalid candidate events
4. accepted history can be replayed consistently
5. create / pay flows preserve domain transition rules
6. admission logic rejects stale candidate events in the in-memory baseline

---

## What These Tests Do Not Prove

These tests do not prove PostgreSQL durability.

They do not verify:

- database schema correctness
- physical transaction atomicity
- `order_events` persistence
- `idempotency_records` persistence
- rollback behavior in PostgreSQL
- migration readiness
- test database isolation
- multi-connection behavior

Those responsibilities belong to PostgreSQL-backed integration tests under:

- `tests/integration/storage/`
- `tests/integration/pipeline/transactional/`

---

## Relationship to PostgreSQL Tests

The in-memory tests preserve the original semantic model.

The PostgreSQL-backed tests prove that the same semantic model can be preserved after introducing durable persistence and transaction boundaries.

In other words:

```text
in_memory/
= semantic composition baseline

storage/
= physical persistence boundary

pipeline/transactional/
= durable transactional write-side composition
```

---

## Non-Goals

This directory does not test:

- PostgreSQL-backed concurrency admission
- durable write-side transaction rollback
- validation result persistence
- Stage 4 SemanticOutcome / Error Model
- Stage 5 governance metrics
- production database hardening

These are handled in later stages or more specific integration test directories.

---

## Reading Guide

Start with these tests when you want to understand the original in-memory write-side behavior before PostgreSQL durability was introduced.

Read these tests as semantic composition tests, not as physical persistence tests.

The important question is:

> Does the original write-side semantic flow still preserve idempotency, Compass validation, replay safety, and admission behavior when composed through the registry?
