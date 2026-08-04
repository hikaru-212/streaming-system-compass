# Security Integration Tests

[← Back to Integration Tests](../README.md)

This directory contains PostgreSQL-backed permission-boundary integration tests for **Streaming System + Compass**.

These tests are not general security examples.
They are executable architecture claims for the durable history and permission
boundary established during **Stage 3.5E** and extended by foundational
**Stage 4B PR6** receipt grants.

At the current baseline, this directory covers:

```text
Stage 3.5E PR3 — Accepted-History Mutation Hardening Tests
Stage 3.5E PR4 — Derived-State Mutation Permission Tests
Stage 3.5E PR5 — Minimal Actor Metadata Boundary
Stage 4B PR6 — DecisionReceipt Initial Permission Boundary
```

---

## Purpose

The purpose of these tests is to verify that PostgreSQL privileges reflect the semantic authority level of each durable artifact.

The core rule is:

```text
accepted history should be harder to mutate than derived runtime state
```

The runtime roles under test are:

```text
compass_app_writer
compass_projection_worker
compass_snapshot_worker
compass_readonly
```

The high-privilege test owner connection is still used for setup, cleanup, fixture insertion, and deterministic reset.
Runtime roles are then probed through `SET ROLE`.

---

## Current Scope

These tests cover:

- `order_events`
- `idempotency_records`
- `order_events_global_position_seq`
- `projection_states`
- `projection_order_progress`
- `projection_checkpoints`
- `projection_snapshots`
- `decision_receipts`

They verify the Stage 3.5E boundary and the foundational PR6 extension:

```text
PR3
= accepted-history and authority-adjacent mutation hardening

PR4
= derived-state controlled mutation and snapshot evidence protection

PR6
= insert-oriented DecisionReceipt evidence with narrowly scoped readers
```

---

## Testing Model

The testing model is intentionally layered:

```text
compass_user
= test-owner setup / cleanup / fixture authority

compass_* runtime roles
= permission-boundary probes through SET ROLE
```

This keeps ordinary storage / mechanism integration tests separate from permission-boundary tests.

The tests prove:

```text
when a runtime role is active,
its effective PostgreSQL privileges match the intended permission matrix
```

They do not prove:

```text
production services use separate database login identities
production connection pools are isolated by role
runtime authentication / session management is implemented
cloud IAM or secret management is configured
```

That boundary is recorded separately in ADR 0015.

---

## Test Categories

### 1. Accepted-History Permission Boundary

These tests verify `order_events`.

They prove:

- `compass_app_writer` can read and append accepted events through the intended path
- normal runtime roles cannot update or delete accepted history
- projection, snapshot, and read-only roles cannot insert accepted events

This boundary answers:

> Can normal runtime roles mutate accepted history outside their intended paths?

The answer should be no.

---

### 2. Successful Idempotency Receipt Boundary

These tests verify `idempotency_records`.

They prove:

- `compass_app_writer` can read and insert successful request-effect receipts
- normal runtime roles cannot update or delete successful idempotency receipts
- projection and snapshot workers do not read or mutate idempotency records under the current schema
- `compass_readonly` may read successful request-effect receipts

At the current schema level, `idempotency_records` stores only:

```text
request_id → accepted_event_id
status = SUCCEEDED
```

It does not store failed attempts, rejected candidates, retry lifecycle state, failure reasons, or runtime decision traces.

---

### 3. Accepted-History Sequence Boundary

These tests verify `order_events_global_position_seq`.

They prove:

- `compass_app_writer` can consume the accepted-history global-position sequence
- projection, snapshot, and read-only roles cannot consume that sequence

This directly protects the accepted-history cursor boundary.

Because PostgreSQL `nextval()` is non-transactional, these tests must run only against `TEST_DATABASE_URL` and rely on destructive cleanup with `TRUNCATE ... RESTART IDENTITY CASCADE`.

---

### 4. Derived Projection State Permission Boundary

These tests verify `projection_states`.

They prove:

- `compass_projection_worker` can select, insert, update, and delete projection state
- `compass_snapshot_worker` and `compass_readonly` can select projection state
- `compass_app_writer` cannot depend on or mutate projection state by default

This preserves the rule:

```text
projection_states
= derived read-side state
= rebuildable / controlled mutable artifact
```

---

### 5. Projection Checkpoint Permission Boundary

These tests verify `projection_checkpoints`.

They prove:

- `compass_projection_worker` can select, insert, update, and delete checkpoint progress
- `compass_snapshot_worker` and `compass_readonly` can select checkpoint progress
- `compass_app_writer` cannot read or mutate checkpoint progress by default

This preserves the rule:

```text
projection_checkpoints
= operational progress metadata
= controlled mutable artifact
```

---

### 6. Projection Order Progress Permission Boundary

These tests verify `projection_order_progress`.

They prove that the projection worker can select, insert, and update repaired
per-order progress but cannot delete it; snapshot and read-only roles can
inspect it; and unauthorized roles cannot mutate it. Progress remains derived
processing evidence, not accepted-history authority. Deletion for a
human-controlled rebuild is an owner, migration, or administrative operation.

---

### 7. Projection Snapshot Permission Boundary

These tests verify `projection_snapshots`.

They prove:

- `compass_snapshot_worker` can select and insert snapshot artifacts
- `compass_snapshot_worker` cannot update or delete snapshot artifacts by default
- `compass_projection_worker` and `compass_readonly` can select snapshots
- `compass_app_writer` cannot read or mutate snapshots by default

This preserves the rule:

```text
projection_snapshots
= derived state compression / evidence artifact
= insert-oriented by default
= not accepted-history authority
```

Snapshot existence does not imply snapshot trust.
Trust still depends on accepted history, lineage, payload evidence, validation, and future receipt-backed trust selection.

---

### 8. DecisionReceipt Permission Boundary

These tests verify that `compass_app_writer` can select and insert foundational
receipt evidence, while `compass_readonly` can select it. Neither role may
update or delete receipt rows. Projection and snapshot workers receive no
initial access. These grants establish a storage permission boundary only; they
do not implement receipt materialization or reconciliation.

---

## What These Tests Prove

These tests prove that the PostgreSQL role / privilege baseline preserves the following claims:

1. Accepted history cannot be casually updated or deleted by normal runtime roles.
2. Successful idempotency receipts cannot be casually rewritten by normal runtime roles.
3. Only the intended writer role can consume accepted-history global-position sequence values.
4. Derived projection state remains operationally mutable through the projection worker role.
5. Projection checkpoint progress remains operationally mutable through the projection worker role.
6. Repaired per-order progress is mutable only through its intended worker boundary.
7. Projection snapshots remain insert-oriented evidence artifacts through the snapshot worker role.
8. Read-only observation does not imply mutation permission.
9. Permission-boundary tests are separate from ordinary storage / mechanism integration tests.
10. DecisionReceipt rows are insert-oriented evidence: the application writer
    can select and insert, read-only can select, and the other normal runtime
    roles cannot update or delete them.

---

## What These Tests Do Not Prove

These tests do not prove:

- full RBAC
- login / session authentication
- JWT behavior
- cloud IAM mapping
- production credential wiring
- role-specific production database URLs
- connection-pool isolation
- multi-worker causal runtime behavior
- chaos / concurrency survival
- Compass Layer 2 governance decisions
- `SemanticOutcome`
- DecisionReceipt semantic correctness, serialization, storage API, or runtime
  materialization
- `RuntimeDecisionPolicy`
- `StrategySelector`
- `RetryGovernance`

Those belong to later runtime governance or production-hardening stages.

---

## How To Run

From the repository root:

```bash
pytest tests/integration/security -v
```

These tests require:

```text
TEST_DATABASE_URL
```

and the Stage 3.5E plus foundational Stage 4B PostgreSQL migrations, including:

```text
db/migrations/005_create_durable_state_permission_roles.sql
db/migrations/007_create_decision_receipts.sql
```

---

## Relationship to Storage Tests

Storage integration tests verify that PostgreSQL-backed stores preserve durable storage behavior.

Security integration tests verify that PostgreSQL runtime roles are allowed to perform only the mutations that match their responsibility boundaries.

In short:

```text
storage tests
= can this durable mechanism work correctly?

security tests
= is this runtime role allowed to use this durable path?
```

Both are needed, but they prove different things.

---

## Summary

Stage 3.5E establishes the minimum durable-history permission hardening layer,
and foundational Stage 4B PR6 extends it to durable receipt evidence.

The tests in this directory prove that accepted history, successful idempotency
receipts, DecisionReceipt evidence, derived state, checkpoints, and snapshots
do not share the same mutation authority.
