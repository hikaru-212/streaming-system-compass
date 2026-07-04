# Derived-State Mutation Permission Tests

[← Back to Stage 3.5E](README.md)

## Purpose

This note records the implementation result for:

```text
Stage 3.5E PR4 — Derived-State Mutation Permission Tests
```

PR4 verifies that Stage 3.5E does not accidentally make every durable table behave like accepted-history authority.

The goal is to prove two things at the same time:

```text
accepted history should be mutation-restricted

derived runtime artifacts must remain operationally mutable or insertable through intended roles
```

---

## Implementation Status

Completed at baseline permission-test level.

PR4 adds isolated PostgreSQL permission-boundary integration tests under:

```text
tests/integration/security/
```

The tests cover:

```text
projection_states
projection_checkpoints
projection_snapshots
```

They use the same layered permission-probe model introduced in PR3:

```text
compass_user
= high-privilege test owner for setup, cleanup, fixture insertion, and deterministic reset

compass_* runtime roles
= effective PostgreSQL permission probes through SET ROLE
```

This confirms the database role / privilege matrix without replacing existing storage, replay, projection, snapshot, or mechanism tests.

---

## Implemented Test Files

PR4 adds or aligns the following security tests:

```text
tests/integration/security/conftest.py
tests/integration/security/test_projection_state_permissions.py
tests/integration/security/test_projection_checkpoint_permissions.py
tests/integration/security/test_projection_snapshot_permissions.py
```

The shared `conftest.py` centralizes the test database connection, destructive reset, runtime-role grant setup, and best-effort role reset behavior for the Stage 3.5E security tests.

This keeps individual permission test files focused on their table-specific privilege matrices instead of duplicating setup / cleanup infrastructure.

---

## Permission Matrix Verified

### `projection_states`

```text
compass_projection_worker
= SELECT / INSERT / UPDATE / DELETE allowed

compass_snapshot_worker
= SELECT allowed
= INSERT / UPDATE / DELETE rejected

compass_readonly
= SELECT allowed
= INSERT / UPDATE / DELETE rejected

compass_app_writer
= SELECT / INSERT / UPDATE / DELETE rejected
```

`projection_states` is derived read-side state.

It must remain mutable by the projection worker because it is rebuildable from accepted history.

The write-side application role must not read or mutate it because command admission must not depend on read-side projection state.

---

### `projection_checkpoints`

```text
compass_projection_worker
= SELECT / INSERT / UPDATE / DELETE allowed

compass_snapshot_worker
= SELECT allowed
= INSERT / UPDATE / DELETE rejected

compass_readonly
= SELECT allowed
= INSERT / UPDATE / DELETE rejected

compass_app_writer
= SELECT / INSERT / UPDATE / DELETE rejected
```

`projection_checkpoints` is operational progress metadata.

It is not business truth.

It must remain mutable by projection workers because workers need to advance, repair, or reset progress during controlled replay / rebuild flows.

Snapshot workers may observe checkpoint state, but they should not advance or reset projection progress.

---

### `projection_snapshots`

```text
compass_snapshot_worker
= SELECT / INSERT allowed
= UPDATE / DELETE rejected

compass_projection_worker
= SELECT allowed
= INSERT / UPDATE / DELETE rejected

compass_readonly
= SELECT allowed
= INSERT / UPDATE / DELETE rejected

compass_app_writer
= SELECT / INSERT / UPDATE / DELETE rejected
```

`projection_snapshots` is derived state compression / evidence.

A snapshot worker may insert snapshot artifacts, but normal runtime roles should not rewrite or delete snapshot evidence in place.

Snapshot cleanup, rebuild reset, or emergency repair remains a higher-privilege maintenance concern, not normal snapshot-worker authority.

---

## Assertion Fidelity Lesson

During PR4 snapshot permission tests, exact evidence assertions exposed a useful UUID type mismatch:

```text
PostgreSQL UUID
→ psycopg Python UUID
≠ string UUID
```

A row-count-only assertion such as:

```python
assert len(rows) == 1
```

would have passed while hiding the mismatch.

PR4 therefore reinforces the Stage 3.5E testing rule:

```text
If a permission probe uses RETURNING, assert the returned evidence directly.
```

For example:

```python
assert rows == [(snapshot_id,)]
```

This checks row count, row shape, value identity, and driver-returned type behavior together.

The broader lesson is recorded separately in:

```text
docs/postmortems/from_row_count_assertions_to_evidence_assertions.md
```

---

## SET ROLE Boundary

PR4 continues to use `SET ROLE` as a test-time permission probing mechanism.

This proves:

```text
when a runtime responsibility role is active,
PostgreSQL grants and rejects the intended table operations
```

It does not prove:

```text
production services use separate login identities
production connection pools are role-isolated
runtime credentials are deployed through a secret manager
connection reuse cannot leak role state
```

That boundary is recorded separately in:

```text
docs/adr/0015_permission_probing_with_set_role.md
```

---

## Deferred: Production-Like Chaos and Concurrency Hardening

PR4 verifies the baseline PostgreSQL permission matrix through isolated single-role probes.

It does not attempt to prove behavior under:

```text
concurrent workers
independent runtime connections
role-specific production login identities
connection-pool reuse
rollback failure
worker crash windows
snapshot write races
checkpoint advancement races
derived-state corruption recovery
permission bypass attempts during active workflows
```

Those scenarios belong to a later production-hardening / chaos-test layer after runtime governance, structured outcomes, retry classification, and decision receipts are more complete.

The current boundary is:

```text
Stage 3.5E PR4
= permission matrix correctness

future production-hardening / chaos tests
= behavior under concurrent, faulty, or adversarial runtime conditions
```

This deferral prevents PR4 from expanding into full production runtime simulation while preserving the future test direction.

---

## Non-goals

PR4 does not add:

```text
new projection reducer behavior
new snapshot trust decision logic
new replay validator behavior
new runtime state resolver policy
new accepted-history mutation tests
new actor metadata schema
new production login identities
new connection-pool policy
chaos tests
SemanticOutcome
DecisionReceipt
RuntimeDecisionPolicy
Compass Layer 2
```

Accepted-history mutation hardening remains PR3 scope.

Actor metadata remains PR5 scope unless explicitly deferred.

Runtime semantic governance remains Stage 4 scope.

---

## Completion Criteria

PR4 is complete when:

```text
projection_states permissions are tested
projection_checkpoints permissions are tested
projection_snapshots permissions are tested
security test setup is centralized
intended roles can perform required derived-state operations
unintended roles cannot mutate derived runtime artifacts
snapshot evidence cannot be casually rewritten or deleted by normal runtime roles
SET ROLE probing is documented as a test-time mechanism
production-like chaos / concurrency testing is explicitly deferred
```

---

## Summary

PR4 confirms that Stage 3.5E preserves the difference between authority and derived runtime artifacts.

```text
accepted history
= authority
= mutation-restricted

derived projection state
= rebuildable read-side state
= mutable by projection worker

projection checkpoints
= operational progress metadata
= mutable by projection worker

projection snapshots
= derived evidence / replay-efficiency artifact
= insertable by snapshot worker, not rewritable by normal runtime roles
```

This completes the derived-state side of the Stage 3.5E permission matrix.
