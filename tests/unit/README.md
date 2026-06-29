# Unit Tests

[← Back to Tests README](../README.md)

This directory contains unit tests for **Streaming System + Compass**.

Unit tests verify local behavior at one module boundary. They should be small, deterministic, and explicit about which invariant they protect.

They are not meant to prove full PostgreSQL transaction behavior or multi-module orchestration. Those belong to integration tests.

---

## Purpose

The purpose of unit tests is to defend local semantic contracts before those contracts are composed into larger flows.

Unit tests should answer questions such as:

- Does the aggregate enforce its own transition rules?
- Does a validator reject the exact semantic mismatch it is responsible for?
- Does a reducer produce deterministic state from one event at a time?
- Does a result model expose stable machine-readable status?
- Does a helper preserve exact money, event identity, or payload hashing semantics?
- Does a snapshot validator / resolver classify one boundary condition without needing a database?

In this repository, unit tests are not only low-level checks. They are the first executable form of boundary claims.

---

## Main Unit Test Areas

The exact folder layout may evolve, but the current unit-test responsibilities can be understood through these areas:

```text
tests/unit/
├── core/          # domain-local behavior
├── compass/       # validation result and transition-proof behavior
├── pipeline/      # local pipeline validators / reducers / resolvers
├── storage/       # local storage helpers and error/result contracts
└── ...            # additional small module-level boundaries
```

Some unit tests may live close to the package they protect, depending on the current project layout. The guiding principle is more important than the exact folder name:

```text
unit test = one boundary, one local claim, no physical database requirement
```

---

## Current Stage Coverage

At the current baseline, unit tests cover or support:

- order aggregate transition rules
- order state replay behavior
- event identity and request identity helpers
- exact Decimal / money semantics
- transition validator result contracts
- predecessor identity mismatch cases
- previous status mismatch cases
- previous version mismatch cases
- stale candidate cases
- validation dispatcher and validation policy behavior
- projection reducer behavior
- projection replay / rebuild result semantics where isolated from database concerns
- snapshot-assisted replay validation result contracts
- snapshot boundary and tail replay edge cases
- snapshot-assisted state resolver result contracts
- compatibility checks for schema version, reducer version, state hydration, and tail source boundaries

Stage 3.5D adds an important cluster of unit-level concerns:

```text
projection snapshot evidence
→ replay validator classification
→ resolver eligibility / unresolved status
→ derived state reconstruction contract
```

These tests support the broader Stage 3.5D rule:

```text
accepted history = authority
snapshot = derived state compression
```

---

## Snapshot-Related Unit Test Intent

Stage 3.5D snapshot unit tests should remain clear about what they prove.

They may prove:

- a missing snapshot is classified explicitly
- a snapshot boundary ahead of accepted history is rejected
- a snapshot-assisted state mismatch becomes drift
- a tail event source contract violation is detected
- unsupported reducer version or schema version prevents fast-path use
- a resolver returns unresolved instead of silently falling back
- a qualified snapshot plus tail events can reconstruct the expected projection state

They do **not** prove:

- PostgreSQL persistence behavior
- database constraints for `projection_snapshots`
- transaction ownership
- runtime fallback policy
- persisted validation receipts
- full Compass Layer 2 governance

Those belong to integration tests or future stages.

---

## Compass Transition Unit Tests

Compass Layer 1 unit tests protect write-side transition truth.

Typical cases include:

- candidate predecessor identity does not match accepted history
- candidate previous status claim is false
- candidate previous version claim is false
- candidate sequence is stale or ahead of expected history
- candidate transition violates domain legality
- validation result exposes stable `candidate_event_id`, verdict, reason, validator name, and depth

These tests support the rule:

```text
candidate event ≠ accepted fact
```

A candidate may carry an event ID before append, but it is not accepted history unless it passes validation and admission and is persisted in the event log.

---

## Projection Reducer Unit Tests

Projection reducer unit tests protect deterministic read-side derivation.

They should prove that:

- `CREATED` events produce created projection state
- `PAID` events update the correct payment fields
- replay order matters where aggregate-local sequence matters
- reducer behavior does not require database state
- reducer output is deterministic for the same input history

These tests support the Stage 3 and Stage 3.5C projection principle:

```text
accepted history
→ canonical reducer
→ derived projection state
```

---

## Result Model Unit Tests

Many modules in this project expose structured result objects rather than only raising generic exceptions.

Unit tests should protect those result contracts because later runtime governance depends on machine-readable meaning.

Examples include:

- validation verdicts
- enforcement actions
- admission results
- projection replay validation statuses
- snapshot replay validation statuses
- resolver statuses

A result model test should usually assert:

- the exact enum value
- whether the result is considered successful
- which state fields are present or absent
- whether evidence fields are preserved
- whether the reason is stable enough to debug without becoming the only machine-readable contract

---

## What Unit Tests Should Avoid

Unit tests should avoid:

- requiring PostgreSQL
- relying on table cleanup
- depending on transaction commit / rollback behavior
- testing multiple layers at once
- asserting implementation noise that is not part of the boundary contract
- using broad mocks that hide the meaning being tested

When a test needs real database behavior, it should move to:

```text
tests/integration/storage/
tests/integration/pipeline/
```

When a test needs a full command or projection flow, it should usually be an integration test.

---

## Relationship to Integration Tests

Unit tests and integration tests answer different questions.

Unit tests ask:

```text
Is this local boundary correct by itself?
```

Integration tests ask:

```text
Do separately correct boundaries still preserve the system invariant when composed?
```

For example:

- a unit test can prove `ProjectionSnapshotAssistedReplayValidator` returns `SNAPSHOT_ASSISTED_DRIFT` for a specific constructed mismatch
- an integration test can prove PostgreSQL-backed snapshot rows, event rows, and replay logic interact correctly through stores and pipeline code

Both are useful, but they should not be collapsed.

---

## Current Non-Coverage

Unit tests do not yet fully cover:

- Stage 3.5E database role / permission behavior
- append-only trigger enforcement
- production deployment security
- full Compass Layer 2 runtime governance
- structured `SemanticOutcome`
- runtime decision policy
- action safety gate
- persisted validation receipts
- worker leasing or multi-worker coordination

Those belong to later stages or integration-level testing.

---

## Expected Commands

Run all unit tests:

```bash
pytest tests/unit -v
```

Run only Compass transition unit tests:

```bash
pytest tests/unit/compass -v
```

Run only pipeline unit tests:

```bash
pytest tests/unit/pipeline -v
```

Run the full suite after unit tests pass:

```bash
pytest -v --durations=10 --cov=src --cov-report=term-missing --cov-fail-under=80
```

---

## Practical Reading Order

If you are reading unit tests to understand the system, a useful order is:

1. core domain tests
2. Compass transition validator tests
3. projection reducer tests
4. projection replay validation result tests
5. snapshot-assisted replay validator tests
6. snapshot-assisted state resolver tests
7. helper / result-model tests

This mirrors the project evolution:

```text
meaning
→ validation
→ projection derivation
→ replay comparison
→ snapshot-assisted fast path
→ future governance substrate
```

---

## Summary

Unit tests protect local meaning.

They keep each boundary honest before the boundary is composed into a larger runtime flow.

After Stage 3.5D, the unit test layer should clearly distinguish:

```text
accepted-history authority checks
snapshot eligibility checks
snapshot-assisted reconstruction
future runtime governance
```

The current goal is not to test every future governance behavior early. It is to make the existing semantic, projection, replay, and snapshot boundaries precise enough that Stage 3.5E and Stage 4 can build on them safely.
