# Test Suite Guide

[← Back to Project README](../README.md)

## Purpose

This directory contains the executable test suite for **Streaming System + Compass**.

The goal of these tests is not only to check whether the code runs.

They also exist to defend the semantic boundaries of the system, including:

- transactional legality
- replay safety
- transition-truth validation
- idempotency behavior
- admission / concurrency protection
- projection sequencing behavior
- projection replay / rebuild consistency at the Stage 3 baseline
- durable accepted-history behavior through PostgreSQL-backed storage
- durable idempotency behavior through PostgreSQL-backed storage
- transactionally safe PostgreSQL-backed write-side composition
- PostgreSQL-backed concurrency admission
- validation placement strategy
- destructive PostgreSQL test database isolation

In this project, tests are part of the architecture argument.

They do not merely verify implementation details.
They help prove that the intended semantic boundaries are actually executable.

---

## Current Testing Focus

At the current baseline, the strongest test coverage spans:

- the in-memory write-side semantic baseline
- the Stage 3 in-memory projection runtime baseline
- the Stage 3.5B PostgreSQL-backed storage baseline
- the completed Stage 3.5B transactional write-side baseline through PR6
- the Stage 3.5C PR0 durable order-event vocabulary hardening pass

This currently includes:

- transactional semantic core behavior
- accepted-history replay behavior
- request-level idempotency and replay / conflict distinction
- optimistic admission / stale-write rejection in the in-memory baseline
- Compass Layer 1 transition-truth validation
- semantic-case and adversarial-history scenarios
- projection reducer correctness
- checkpoint-aware worker sequencing behavior
- replay / rebuild behavior for the in-memory Stage 3 projection baseline
- PostgreSQL-backed `PostgresEventStore` append / load / latest-event behavior
- PostgreSQL-backed `PostgresIdempotencyStore` MISS / REPLAY / CONFLICT behavior
- UUID, Decimal, proof-status, JSONB, and schema-version persistence checks for the durable event-store baseline
- durable event vocabulary and proof-status schema-constraint tests
- PostgreSQL write-side UnitOfWork commit / rollback behavior
- Compass-guarded transactional write-side create / pay flows
- validation-before-admission behavior
- append + idempotency record physical transaction atomicity
- optimistic PostgreSQL admission
- pessimistic PostgreSQL admission
- lock-timeout mapping
- autocommit guard for transaction-scoped pessimistic admission
- validation placement through `IN_TRANSACTION` and minimal `PRE_TRANSACTION`
- destructive PostgreSQL integration test isolation through `TEST_DATABASE_URL`

The test suite is therefore no longer only write-side focused.
It now also defends durable storage, projection runtime, transactional PostgreSQL-backed write-side behavior, PostgreSQL admission, and validation placement boundaries.

---

## Test Structure

The test suite is organized by responsibility rather than by raw code coverage alone.

Current test categories include:

- `tests/unit/`
- `tests/integration/`
- `tests/integration/in_memory/`
- `tests/integration/storage/`
- `tests/integration/pipeline/transactional/`
- `tests/semantic_cases/`
- `tests/adversarial/`
- `tests/fixtures/`

The exact layout may continue to evolve as the repository grows, but the guiding idea remains stable:

> each test layer should defend a different semantic boundary.

---

## What Each Layer Is Trying to Prove

### `tests/unit/`

Unit tests check local module behavior in isolation.

Typical goals:

- verify aggregate transition logic
- verify validator behavior
- verify reducer behavior
- verify local invariants at one module boundary
- verify helper boundaries such as exact money handling, identity generation, and PostgreSQL connection configuration

These tests answer:

- is this module locally correct?
- does it reject invalid inputs in the expected way?
- does it preserve its own invariants?

---

### `tests/integration/`

Integration tests check how multiple modules behave together.

Typical goals:

- command handling through the transactional path
- interaction between registry, aggregate, store, idempotency, and Compass
- admission behavior under stale-write or retry conditions
- projection worker behavior across reducer + stores + checkpoint boundary
- replay behavior across module boundaries
- durable PostgreSQL write-side composition

These tests answer:

- do the boundaries still behave correctly when composed?
- does semantic validation remain distinct from persistence admission?
- does idempotency remain distinct from concurrency control?
- does the Stage 3 projection runtime preserve reducer / worker / store separation in practice?
- does the PostgreSQL-backed write side preserve the semantic claims of the original in-memory baseline?

---

### [tests/integration/in_memory/](integration/in_memory/README.md)

In-memory integration tests check the original semantic write-side composition without PostgreSQL durability.

Typical goals:

- verify registry behavior with Compass enabled
- verify registry behavior without Compass
- verify request replay and conflict classification
- verify create / pay transactional flow
- verify replay consistency
- verify in-memory admission / stale-write behavior

These tests answer:

- does the original in-memory write-side preserve the intended semantic model?
- does request replay remain distinct from request conflict?
- does Compass validation still block invalid candidate events before accepted history is mutated?
- does in-memory admission reject stale candidate events?

These tests do not prove physical database persistence or PostgreSQL transaction behavior.

---

### [tests/integration/storage/](integration/storage/README.md)

Storage integration tests verify PostgreSQL-backed durable storage behavior.

Typical goals:

- verify `PostgresEventStore.append()`
- verify `PostgresEventStore.load()`
- verify `PostgresEventStore.last_event()`
- verify stale expected-version rejection
- verify append-time sequence continuity rejection
- verify UUID / Decimal / proof-status round-trip behavior
- verify JSONB evidence fields and `event_schema_version` persistence
- verify `PostgresIdempotencyStore` MISS / REPLAY / CONFLICT behavior
- verify idempotency records survive a new database connection
- verify idempotency records must reference existing accepted events
- verify semantic fingerprint behavior
- verify durable order-event vocabulary constraints
- verify PostgreSQL integration tests run against `TEST_DATABASE_URL`

These tests answer:

- does the durable accepted-history boundary behave like the in-memory baseline where required?
- can PostgreSQL preserve the event identity, money value, proof status, and sequence semantics needed for replay?
- does the durable store reject stale or broken append attempts before accepted history is polluted?
- does durable idempotency memory survive beyond one process / connection?
- are destructive PostgreSQL tests isolated from the development database?

These tests require a PostgreSQL-backed test environment in CI or local development.

---

### [tests/integration/pipeline/transactional/](integration/pipeline/transactional/README.md)

Transactional pipeline integration tests verify the completed Stage 3.5B PostgreSQL-backed write-side composition through PR6.

Typical goals:

- verify `PostgresWriteSideUnitOfWork` commit / rollback behavior
- verify accepted event append and idempotency record persistence share one transaction
- verify durable `create_order` and `pay_order` command flows
- verify Compass Layer 1 validation happens before accepted history mutation
- verify validation `BLOCK` does not write `order_events`
- verify validation `BLOCK` does not write `idempotency_records`
- verify physical rollback when append succeeds but idempotency recording fails
- verify domain legality failures leave no partial durable writes
- verify optimistic PostgreSQL admission
- verify pessimistic PostgreSQL admission
- verify stale-write rejection and lock-timeout mapping
- verify `IN_TRANSACTION` and minimal `PRE_TRANSACTION` validation placement
- verify stale pre-validated candidates remain guarded by append-time admission

These tests answer:

- does the PostgreSQL-backed write side preserve the canonical semantic flow?
- do accepted event append and idempotency record persistence commit or roll back together?
- does Compass validation remain before durable accepted-history mutation?
- are validation-before-admission and physical transaction atomicity tested as separate boundaries?
- does PostgreSQL-backed admission reject stale or unprepared writers?
- can validation placement move without weakening accepted-history admission?

---

### `tests/semantic_cases/`

Semantic-case tests focus on meaningful correctness scenarios.

They are less about raw unit isolation and more about:

- whether an important system rule remains true
- whether a semantic distinction is preserved
- whether the project’s stated invariants are reflected in executable behavior

These tests answer:

- does the system still behave according to its intended meaning?
- are key architecture claims actually testable?

---

### `tests/adversarial/`

Adversarial-history tests deliberately use malformed, inconsistent, or hostile histories and event patterns.

Typical goals:

- expose replay fragility
- detect malformed sequence progression
- reveal semantic mismatch between claimed and actual history
- confirm that invalid histories are not silently normalized into trusted behavior

These tests answer:

- what happens when history itself is suspicious?
- does the system preserve its semantic defenses under hostile conditions?

---

### `tests/fixtures/`

Shared fixtures and semantic test-data builders exist to reduce noise in the test suite while preserving semantic readability.

Current fixture areas include:

- order event builders
- request signature builders
- validation context builders
- accepted-history builders

These helpers are used to construct meaningful domain states without forcing every test to manually rebuild the same setup.

They should support clarity, not hide important meaning.

Good fixture usage should make the test easier to read:

```text
created_event
created_and_paid_history
create_signature
empty_history_validation_context
```

Bad fixture usage would hide the semantic condition being tested.

If abstraction makes the test less semantically readable, the abstraction should be avoided.

Fixtures in this project should remain close to domain meaning.
They should not become generic object factories detached from the system’s semantic rules.

---

## Database-Backed Integration Tests

Stage 3.5B introduced PostgreSQL-backed tests.

The local expected setup separates development and destructive test databases:

```text
DATABASE_URL
→ development / manual inspection / local demo

TEST_DATABASE_URL
→ pytest / destructive integration tests / TRUNCATE-based cleanup
```

Recommended local setup:

```bash
docker compose up -d

export DATABASE_URL=postgresql://compass_user:compass_password@localhost:5433/compass_dev
export TEST_DATABASE_URL=postgresql://compass_user:compass_password@localhost:5433/compass_test

psql "$TEST_DATABASE_URL" -f db/migrations/001_create_write_side_tables.sql

pytest tests/integration/storage -q
pytest tests/integration/pipeline/transactional -q
```

The test suite should never run destructive PostgreSQL integration tests directly against `DATABASE_URL`.

The integration test fixture enforces this by requiring `TEST_DATABASE_URL` and checking that the connected database name ends with `_test`.

The CI workflow should provide the same physical requirements:

- PostgreSQL service
- `DATABASE_URL` for development-style connection or database bootstrap if needed
- `TEST_DATABASE_URL` for destructive integration tests
- migration application against the test database before tests
- full pytest execution after database setup

These tests intentionally validate the physical persistence boundary rather than only mocking database behavior.

---

## Testing Philosophy

This repository does not treat tests as an afterthought.

The test suite is part of the project’s broader design philosophy:

- define meaning first
- define ownership second
- make the behavior executable
- preserve the distinction between semantic truth and runtime mechanics
- verify durable persistence only after the physical boundary is actually exercised

This is especially important because the project is concerned with correctness under failure, not just successful execution.

A green pipeline is not enough.

Tests in this repository therefore aim to defend questions such as:

- did an invalid event get blocked before polluting accepted history?
- did replay reconstruct the same meaning deterministically?
- did retry safety remain distinct from stale-write protection?
- did semantic validation remain separate from admission logic?
- did the projection reducer remain pure?
- did the projection worker preserve sequencing and checkpoint semantics at the baseline level?
- did the durable event store preserve the accepted-history facts required for replay?
- did durable idempotency memory survive across connections?
- did event append and idempotency record persistence commit or roll back together?
- did PostgreSQL-backed admission reject stale or unprepared writers?
- did validation placement preserve append-time admission as the final accepted-history guard?
- did destructive integration tests run only against the test database?

---

## What These Tests Are Not

These tests are not primarily designed to maximize superficial line coverage.

They are also not meant to be a framework tutorial.

The main purpose of the suite is to make architectural claims executable.

That means a smaller number of semantically meaningful tests is often more valuable than a larger number of mechanically repetitive ones.

---

## Current Boundary

At the current baseline, the test suite is strongest on:

- write-side semantic correctness
- replay safety
- transition-truth validation
- Stage 3 baseline projection sequencing and replay behavior
- Stage 3.5B PostgreSQL-backed accepted-history behavior
- Stage 3.5B durable idempotency behavior
- Stage 3.5B transactional write-side commit / rollback behavior
- Stage 3.5B Compass-guarded durable write-side flow
- Stage 3.5B PostgreSQL-backed optimistic / pessimistic admission
- Stage 3.5B validation placement strategy
- Stage 3.5C PR0 durable order-event vocabulary hardening

However, the current suite does **not yet** fully cover:

- Stage 3.5C durable read-side projection / checkpoint behavior
- PostgreSQL-backed projection worker behavior
- state-level Compass Layer 2 validation
- Stage 3.5D Snapshot Trust Contract
- Stage 3.5E durable history / permission hardening
- Stage 4 structured `SemanticOutcome`
- retry reason classification persistence
- validation result persistence
- advanced runtime concerns such as DLQ, buffering, watermark semantics, or multi-worker coordination

These belong to later stages of the project.

---

## Summary

The test suite in this project exists to do more than verify code execution.

It exists to defend the semantic structure of the repository.

In short:

```text
unit tests
→ local module correctness

integration/in_memory tests
→ original semantic composition baseline

integration/storage tests
→ physical persistence-boundary correctness

integration/pipeline/transactional tests
→ durable transactional write-side composition, admission, and validation placement

semantic-case tests
→ executable semantic claims

adversarial-history tests
→ defensive behavior under hostile conditions

fixtures
→ semantic test-data construction
```

As the project evolves beyond the Stage 3.5B durable write-side baseline, the test suite should continue to grow in the same spirit:

- not only testing whether the system runs
- but testing whether the system remains semantically trustworthy
