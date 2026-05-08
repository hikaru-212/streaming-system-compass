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

In this project, tests are part of the architecture argument.

They do not merely verify implementation details.
They help prove that the intended semantic boundaries are actually executable.

---

## Current Testing Focus

At the current stage, the strongest test coverage spans both:

- the write-side transactional baseline
- the Stage 3 baseline projection runtime

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

The test suite is therefore no longer only write-side focused.
It now also begins to defend the read-side runtime baseline in executable form.

---

## Test Structure

The test suite is organized by responsibility rather than by raw code coverage alone.

Current test categories may include:

- `tests/unit/`
- `tests/integration/`
- `tests/semantic_cases/`
- `tests/adversarial_histories/`
- `tests/shared/`

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

### `tests/adversarial_histories/`

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

## Testing Philosophy

This repository does not treat tests as an afterthought.

The test suite is part of the project’s broader design philosophy:

- define meaning first
- define ownership second
- make the behavior executable
- preserve the distinction between semantic truth and runtime mechanics

This is especially important because the project is concerned with correctness under failure, not just successful execution.

A green pipeline is not enough.

Tests in this repository therefore aim to defend questions such as:

- did an invalid event get blocked before polluting accepted history?
- did replay reconstruct the same meaning deterministically?
- did retry safety remain distinct from stale-write protection?
- did semantic validation remain separate from admission logic?
- did the projection reducer remain pure?
- did the projection worker preserve sequencing and checkpoint semantics at the baseline level?

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

However, the current suite does **not yet** fully cover:

- persistence-backed restart semantics
- PostgreSQL-backed write-side / read-side storage behavior
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

semantic-case tests
→ executable semantic claims

adversarial-history tests
→ defensive behavior under hostile conditions
```

As the project evolves beyond the Stage 3 baseline, the test suite should continue to grow in the same spirit:

- not only testing whether the system runs
- but testing whether the system remains semantically trustworthy
