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

In this project, tests are part of the architecture argument.

They do not merely verify implementation details.
They help prove that the intended semantic boundaries are actually executable.

---

## Current Testing Focus

At the current stage, the strongest test coverage spans:

- the write-side transactional baseline
- the Stage 3 baseline projection runtime
- the Stage 3.5B PR2 PostgreSQL-backed accepted-history baseline

This currently includes:

- transactional semantic core behavior
- accepted-history replay behavior
- request-level idempotency and replay/conflict distinction
- optimistic admission / stale-write rejection
- Compass Layer 1 transition-truth validation
- semantic-case and adversarial-history scenarios
- projection reducer correctness
- checkpoint-aware worker sequencing behavior
- replay / rebuild behavior for the in-memory Stage 3 projection baseline
- PostgreSQL-backed `PostgresEventStore` append / load / latest-event behavior
- UUID, Decimal, proof-status, JSONB, and schema-version persistence checks for the durable event-store baseline

The test suite is therefore no longer only write-side focused.
It now also defends the first durable storage-backed accepted-history boundary.

---

## Test Structure

The test suite is organized by responsibility rather than by raw code coverage alone.

Current test categories may include:

- `tests/unit/`
- `tests/integration/`
- `tests/integration/storage/`
- `tests/semantic_cases/`
- `tests/adversarial/`
- `tests/shared/`

The exact layout may continue to evolve as the repository grows, but the guiding idea remains stable:

> each test layer should defend a different semantic boundary.

The new `tests/integration/storage/` area is currently used for database-backed storage integration tests.
Older integration tests may still live directly under `tests/integration/`; broader test directory reorganization is intentionally deferred until Stage 3.5B boundaries are clearer.

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

These tests answer:

- do the boundaries still behave correctly when composed?
- does semantic validation remain distinct from persistence admission?
- does idempotency remain distinct from concurrency control?
- does the Stage 3 projection runtime preserve reducer / worker / store separation in practice?

---

### `tests/integration/storage/`

Storage integration tests verify persistence-backed behavior against a real database boundary.

Current goals:

- verify `PostgresEventStore.append()`
- verify `PostgresEventStore.load()`
- verify `PostgresEventStore.last_event()`
- verify stale expected-version rejection
- verify append-time sequence continuity rejection
- verify UUID / Decimal / proof-status round-trip behavior
- verify JSONB evidence fields and `event_schema_version` are persisted as expected

These tests answer:

- does the durable accepted-history boundary behave like the in-memory baseline where required?
- can PostgreSQL preserve the event identity, money value, proof status, and sequence semantics needed for replay?
- does the durable store reject stale or broken append attempts before accepted history is polluted?

These tests require a PostgreSQL-backed test environment in CI or local development.

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

### `tests/shared/`

Shared test helpers exist to reduce noise in the test suite while preserving semantic readability.

Typical contents may include:

- fixtures
- accepted-history builders
- replay helpers
- common test data constructors

These helpers should support clarity, not hide important meaning.

If abstraction makes the test less semantically readable, the abstraction should be avoided.

---

## Database-Backed Integration Tests

Stage 3.5B introduces tests that require PostgreSQL.

The local expected setup is:

```text
docker compose up -d
export DATABASE_URL=postgresql://compass_user:compass_password@localhost:5433/compass_dev
psql "$DATABASE_URL" -f db/migrations/001_create_write_side_tables.sql
pytest tests/integration/storage/test_postgres_event_store.py -q
```

The CI workflow should provide the same physical requirements:

- PostgreSQL service
- `DATABASE_URL`
- migration application before tests
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

---

## What These Tests Are Not

These tests are not primarily designed to maximize superficial line coverage.

They are also not meant to be a framework tutorial.

The main purpose of the suite is to make architectural claims executable.

That means a smaller number of semantically meaningful tests is often more valuable than a larger number of mechanically repetitive ones.

---

## Current Boundary

At the current stage, the test suite is strongest on:

- write-side semantic correctness
- replay safety
- transition-truth validation
- Stage 3 baseline projection sequencing and replay behavior
- Stage 3.5B PR2 PostgreSQL-backed accepted-history behavior

However, the current suite does **not yet** fully cover:

- durable idempotency storage
- same-transaction event append + idempotency record write
- persistence-backed restart semantics for the full write-side flow
- durable read-side projection / checkpoint behavior
- state-level Compass Layer 2 validation
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

integration tests
→ boundary composition correctness

storage integration tests
→ physical persistence-boundary correctness

semantic-case tests
→ executable semantic claims

adversarial-history tests
→ defensive behavior under hostile conditions
```

As the project evolves beyond the Stage 3.5B durable write-side baseline, the test suite should continue to grow in the same spirit:

- not only testing whether the system runs
- but testing whether the system remains semantically trustworthy
