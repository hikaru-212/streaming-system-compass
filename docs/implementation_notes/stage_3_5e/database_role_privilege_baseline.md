# Database Role / Privilege Baseline

[← Back to Stage 3.5E](README.md)

## Purpose

This note defines the implementation boundary for:

```text
Stage 3.5E PR2 — Database Role / Privilege Baseline
```

Stage 3.5E introduces the minimum database-level mutation boundary needed before the project enters broader Stage 4 runtime semantic governance.

The goal is not to build a full security subsystem.

The goal is to make the system's durable authority model visible in PostgreSQL privileges.

---

## Core Rule

```text
accepted history should be harder to mutate than derived runtime state
```

This follows from the project authority model:

```text
accepted history = authority
successful idempotency receipt = request-to-accepted-event evidence
projection state = derived runtime view
checkpoint = operational progress metadata
snapshot = derived state compression
```

If these durable artifacts have different semantic authority levels, then runtime roles should not have identical mutation rights over all of them.

---

## Current Durable Artifact Model

Stage 3.5E should reflect the current database schema, not a future retry lifecycle model.

The current durable artifacts are:

```text
order_events
= accepted fact log
= source of truth

idempotency_records
= successful request-effect receipt
= request_id to accepted_event_id mapping
= insert-once / restricted rewrite under the current schema

projection_states
= current materialized read model
= derived from accepted history
= rebuildable

projection_checkpoints
= projection worker progress metadata
= operational cursor

projection_snapshots
= derived state compression / evidence artifact
= insert-oriented by default
```

The current `idempotency_records` schema records only successful request-to-accepted-event mappings.

It does not store:

```text
pending requests
failed attempts
retry lifecycle state
rejected candidates
runtime decision receipts
```

Those concerns may be introduced later, likely as separate Stage 4 attempt / governance records.

---

## Scope

PR2 introduces a minimal PostgreSQL role / privilege baseline.

It may add:

```text
compass_migration_owner
compass_app_writer
compass_projection_worker
compass_snapshot_worker
compass_readonly
```

The exact names are less important than the boundary they express.

The important distinction is:

```text
runtime components should receive table-specific privileges
based on the semantic authority level of each durable table
```

---

## Non-goals

PR2 does not implement:

```text
full RBAC
login
JWT
session management
multi-tenant auth
cloud IAM
secret manager integration
user account management
UI permissions
actor registry
retry lifecycle table
failed attempt table
DecisionReceipt
RuntimeDecisionPolicy
Compass Layer 2
Stage 4 governance logic
```

PR2 also does not replace existing integration tests with low-privilege runtime-role tests.

Existing tests may continue using a high-privilege test owner connection for setup, cleanup, fixture insertion, and deterministic reset.

---

## Role Model

### `compass_migration_owner`

```text
responsibility: schema management / migrations
mutation posture: high privilege, not a runtime role
```

This role represents the migration / setup authority.

It may own tables, run migrations, and perform test setup or teardown.

It should not be confused with normal runtime components.

---

### `compass_app_writer`

```text
responsibility: write-side runtime
mutation posture: append accepted events and insert successful idempotency receipts
```

This role represents the application write-side path.

It may:

```text
SELECT order_events
INSERT order_events
SELECT idempotency_records
INSERT idempotency_records
```

It should not:

```text
UPDATE order_events
DELETE order_events
UPDATE idempotency_records
DELETE idempotency_records
SELECT or mutate projection_states by default
SELECT or mutate projection_checkpoints by default
SELECT or mutate projection_snapshots by default
```

The write side rehydrates aggregate state from accepted history / event log.

It must not depend on read-side projection state for command admission.

The point is that the application writer may append accepted facts through the intended path, but it may not rewrite accepted history or rewrite successful request-effect receipts.

---

### `compass_projection_worker`

```text
responsibility: read-side projection runtime
mutation posture: controlled mutation of derived state and operational progress
```

This role represents projection worker behavior.

It may:

```text
SELECT order_events
SELECT / INSERT / UPDATE / DELETE projection_states
SELECT / INSERT / UPDATE / DELETE projection_checkpoints
```

It should not:

```text
INSERT order_events
UPDATE order_events
DELETE order_events
mutate idempotency_records
mutate projection_snapshots by default
```

Projection workers consume accepted history.

They do not create accepted history.

Projection state and checkpoints are controlled mutable because they are derived / operational artifacts.

---

### `compass_snapshot_worker`

```text
responsibility: snapshot artifact production / inspection
mutation posture: evidence-oriented insertion
```

This role represents snapshot-related runtime work.

It may:

```text
SELECT order_events
SELECT projection_states
SELECT projection_checkpoints
SELECT projection_snapshots
INSERT projection_snapshots
```

It should not:

```text
INSERT order_events
UPDATE order_events
DELETE order_events
mutate idempotency_records
UPDATE projection_states
DELETE projection_states
UPDATE projection_checkpoints
DELETE projection_checkpoints
UPDATE projection_snapshots by default
DELETE projection_snapshots by default
```

A snapshot is derived evidence.

Snapshot insertion may be allowed, but snapshot existence must not imply trust.

---

### `compass_readonly`

```text
responsibility: observation
mutation posture: read-only
```

This role may inspect durable state.

It should not mutate durable state.

It may:

```text
SELECT order_events
SELECT idempotency_records
SELECT projection_states
SELECT projection_checkpoints
SELECT projection_snapshots
```

It should not:

```text
INSERT
UPDATE
DELETE
TRUNCATE
```

---

## Table Permission Direction

### `order_events`

```text
authority level: accepted history
mutation posture: append-oriented / restricted
```

Baseline direction:

```text
app_writer: SELECT, INSERT
projection_worker: SELECT
snapshot_worker: SELECT
readonly: SELECT
```

No normal runtime role should receive `UPDATE` or `DELETE` on `order_events`.

`order_events` defines accepted facts. If an accepted fact must be corrected, the correction should be represented by a new accepted event, not by rewriting the old event row.

---

### `idempotency_records`

```text
authority level: successful request-effect receipt
mutation posture: insert-once / restricted rewrite
```

Baseline direction:

```text
app_writer: SELECT, INSERT
readonly: SELECT
```

No normal runtime role should receive `UPDATE` or `DELETE` on `idempotency_records` under the current schema.

`idempotency_records` participates in the same write-side transaction as `order_events`, but transaction coupling does not imply semantic equivalence.

The current schema stores only successful request-to-accepted-event mappings.

It does not store pending request state, failed attempts, retry lifecycle state, or rejected candidates.

Therefore, `idempotency_records` should be treated as insert-once successful request-effect memory under the current design.

A later retry / attempt lifecycle table may be introduced separately in Stage 4 if failed attempts, retry reasons, or runtime decision receipts need to be preserved.

---

### `projection_states`

```text
authority level: derived read-side state
mutation posture: controlled but mutable
```

Baseline direction:

```text
projection_worker: SELECT, INSERT, UPDATE, DELETE
snapshot_worker: SELECT
readonly: SELECT
```

`projection_states` is a derived read model, not accepted history.

It is maintained by `compass_projection_worker` from `order_events`.

Normal reads may query `projection_states` for efficiency, but command admission must not depend on projection state.

If projection state is wrong, stale, or manually altered, the failure is read-side drift, not accepted-history corruption.

The recovery path is to validate, clear, or rebuild projection state from `order_events`.

`DELETE` is intended for controlled rebuild / reset flows, not ordinary business-state mutation.

---

### `projection_checkpoints`

```text
authority level: operational progress metadata
mutation posture: controlled but mutable
```

Baseline direction:

```text
projection_worker: SELECT, INSERT, UPDATE, DELETE
snapshot_worker: SELECT
readonly: SELECT
```

Checkpoint state records worker progress.

It is not business truth.

`projection_checkpoints` must remain mutable because workers need to advance, reset, or repair operational progress.

However, checkpoint mutation should remain limited to controlled projection runtime paths because a bad checkpoint can cause skipped replay, repeated replay, or confusing recovery behavior.

---

### `projection_snapshots`

```text
authority level: derived state compression
mutation posture: evidence-oriented insertion / controlled selection
```

Baseline direction:

```text
snapshot_worker: SELECT, INSERT
projection_worker: SELECT
readonly: SELECT
```

Snapshot records are derived artifacts.

They may support replay efficiency, but they do not replace accepted history.

A snapshot may be inserted by a snapshot worker, but snapshot existence does not imply trust.

No normal runtime role should receive `UPDATE` or `DELETE` on `projection_snapshots` by default because snapshot lineage and payload evidence should not be rewritten in place.

---


## Implemented SQL Migration

PR2 implements the baseline through:

```text
db/migrations/005_create_durable_state_permission_roles.sql
```

The migration creates the following PostgreSQL roles if they do not already exist:

```text
compass_migration_owner
compass_app_writer
compass_projection_worker
compass_snapshot_worker
compass_readonly
```

It grants `USAGE` on schema `public` to runtime roles so table privileges are usable.

It then applies explicit table-level `REVOKE` / `GRANT` rules for:

```text
order_events
idempotency_records
projection_states
projection_checkpoints
projection_snapshots
```

The migration intentionally does not revoke privileges from the existing `compass_user` test owner connection.

Existing mechanism integration tests may continue to use `compass_user` for setup, cleanup, fixture insertion, and deterministic reset.

Runtime-role permission tests are added separately in later Stage 3.5E PRs.

### Sequence Boundary

`order_events.global_position` uses:

```text
order_events_global_position_seq
```

Only `compass_app_writer` receives `USAGE` on this sequence because it is the only runtime role allowed to insert into `order_events` in the PR2 baseline.

Projection and snapshot workers may read accepted history, but they should not be able to consume accepted-history cursor values by calling `nextval(...)`.

Therefore, PR2 avoids broad sequence grants.

## Permission Tests Boundary

PR2 may introduce roles and grants.

Detailed test matrices should remain staged.

The intended later split is:

```text
PR3 — accepted-history mutation hardening tests
PR4 — derived-state mutation permission tests
```

Existing integration tests should not be rewritten to use low-privilege roles.

Instead:

```text
existing integration tests
= storage / runtime behavior tests

Stage 3.5E security tests
= database role / privilege boundary tests
```

A likely future location is:

```text
tests/integration/security/
```

---

## Why Not Make Every Table Append-Only?

Only accepted history has authority-level append-only semantics.

Other tables have different needs.

```text
idempotency_records
= successful request-effect receipts
= insert-once / restricted rewrite under the current schema

projection_states
= derived read-side state
= must be upsertable / clearable / rebuildable

projection_checkpoints
= operational progress metadata
= must be updateable by workers

projection_snapshots
= derived state compression
= may be inserted and selected under explicit evidence boundaries
= should not be rewritten in place by normal runtime roles
```

Making every table append-only would confuse semantic authority with operational durability.

Making every table freely mutable would collapse the authority boundary.

Stage 3.5E should avoid both mistakes.

---

## Why This Is Not Full RBAC

This stage does not model human users.

It does not model product permissions.

It does not implement authentication.

The roles are runtime responsibility boundaries, not user-facing access-control roles.

The question is not:

```text
Which user can do which product action?
```

The question is:

```text
Which runtime component is allowed to mutate which durable artifact?
```

---

## Completion Criteria

PR2 is complete when:

```text
minimal PostgreSQL roles exist
table grants reflect durable authority levels
order_events does not grant UPDATE / DELETE to normal runtime roles
idempotency_records does not grant UPDATE / DELETE under the current successful-receipt design
derived runtime tables remain mutable by intended roles
snapshot records are insert-oriented by default
read-only role has no mutation privileges
the role model is documented
future permission tests have a clear location and boundary
```

---

## Summary

PR2 translates the Stage 3.5E boundary into PostgreSQL privilege structure.

It does not finish all permission hardening.

It establishes the first durable-state role baseline:

```text
accepted history is not just another mutable table
successful request-effect receipts should not be rewritten by normal runtime roles
derived runtime state is not accepted history
runtime components should not all share the same mutation authority
```
