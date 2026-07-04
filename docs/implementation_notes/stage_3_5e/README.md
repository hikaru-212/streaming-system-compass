# Stage 3.5E — Durable History and Permission Hardening

[← Back to Implementation Notes](../README.md)

## Purpose

This directory records the implementation plan for:

```text
Stage 3.5E — Durable History and Permission Hardening
```

Stage 3.5E introduces the minimal database-level and runtime-facing permission boundary needed before Compass grows into stronger runtime semantic governance.

The goal is not to build a full authentication or authorization system.

The goal is to make the system’s durable authority boundary harder to mutate than derived runtime state.

---

## Why This Stage Exists

The project now has durable baselines for:

```text
accepted history
successful idempotency receipts
projection state
projection checkpoints
projection snapshots
snapshot-assisted replay validation
snapshot-assisted state resolution
```

Stage 3.5D introduced snapshot trust and replay-efficiency support while preserving the core rule:

```text
accepted history = authority
snapshot = derived state compression
```

That distinction creates the next necessary boundary:

```text
authoritative durable history
must be harder to mutate than
derived runtime artifacts
```

Without this boundary, the system may correctly distinguish accepted history from derived state at the architecture level, but still allow operational mutation paths that treat them too similarly.

Stage 3.5E exists to prevent that semantic collapse.

---

## Core Principle

```text
accepted history should be harder to mutate than derived runtime state
```

This means different durable tables should not share the same mutation assumptions.

For example:

```text
order_events
= accepted history
= source of truth
= append-only / restricted mutation direction

idempotency_records
= successful request-effect receipts
= request_id to accepted_event_id mapping
= insert-once / restricted rewrite under the current schema

projection_states
= derived read-side state
= rebuildable
= mutable through controlled projection runtime paths

projection_checkpoints
= operational progress metadata
= mutable by projection workers and rebuild flows

projection_snapshots
= derived state compression
= insertable and selectable only under explicit trust / evidence boundaries
```

Stage 3.5E makes these differences explicit.

---

## Scope

Stage 3.5E should define and implement the minimum permission semantics needed to protect durable accepted history and prepare for future runtime governance.

The stage may include:

```text
database-level mutation hardening
append-only accepted-history direction
successful idempotency receipt rewrite prevention
role / privilege separation for durable tables
minimal actor metadata
permission boundary documentation
tests proving forbidden mutations are rejected
tests proving derived runtime state remains operationally mutable
```

The first PR should be documentation-only.

Implementation should come only after the boundary is clear.

---

## Non-goals

Stage 3.5E does not implement:

```text
full RBAC
login
JWT
session management
multi-tenant auth
cloud IAM integration
secret manager integration
user account management
UI permissions
production access-control infrastructure
retry lifecycle table
failed attempt table
Compass Layer 2
SemanticOutcome
runtime decision policy
action safety gate
agent runtime isolation
```

Stage 3.5E is not a security product.

It is a minimum durable-history mutation boundary.

---

## Relationship to Earlier Stages

### Stage 3.5B

Stage 3.5B established durable write-side storage and transactional semantic write-side behavior.

It made accepted history durable through PostgreSQL-backed `order_events`, while preserving Compass Layer 1 before accepted-history mutation.

It also introduced `idempotency_records` as successful request-to-accepted-event receipts, not as a retry lifecycle table.

Stage 3.5E builds on this by making accepted-history mutation harder to perform outside intended append paths and by preventing successful idempotency receipts from being casually rewritten.

---

### Stage 3.5C

Stage 3.5C established durable read-side projection state, checkpoints, global-position consumption, projection worker orchestration, and durable replay / rebuild validation.

Stage 3.5E must preserve read-side mutability where appropriate.

Projection state and checkpoint state are derived / operational artifacts. They must remain clearable, rebuildable, and updatable by controlled runtime flows.

---

### Stage 3.5D

Stage 3.5D established projection snapshot trust and replay-efficiency support.

It clarified that snapshots are derived state compression, not authority.

Stage 3.5E must preserve this distinction. Snapshot tables may require evidence-oriented write protection, but they should not be treated like accepted history.

---

## Relationship to Future Stage 4

Stage 4 will introduce stronger runtime semantic validation, structured outcomes, decision receipts, runtime decision policy, and governance-oriented execution control.

Stage 3.5E prepares for that future by defining minimum actor / permission concepts.

Examples:

```text
who produced validation evidence
who or what triggered rebuild
who or what attempted repair
who is allowed to mutate accepted history
who is allowed to mutate successful request-effect receipts
who is allowed to mutate derived runtime state
```

Stage 3.5E does not yet implement Stage 4 receipts.

It only creates the durable-history hardening foundation that those receipts will later depend on.

---

## Expected PR Sequence

A minimal Stage 3.5E sequence should be:

```text
PR1 — Durable History Permission Boundary
PR2 — Database Role / Privilege Baseline
PR3 — Accepted-History Mutation Hardening Tests
PR4 — Derived-State Mutation Permission Tests
PR5 — Minimal Actor Metadata Boundary
PR6 — Stage 3.5E Closeout
```

Detailed notes:

- [PR2 — Database Role / Privilege Baseline](database_role_privilege_baseline.md)
- [PR4 — Derived-State Mutation Permission Tests](derived_state_mutation_permission_tests.md)
- [PR5 — Minimal Actor Metadata Boundary](minimal_actor_metadata_boundary.md)

This sequence may be adjusted as implementation reveals constraints.

However, the stage should avoid expanding into full RBAC or production authentication.

---

## PR2 Implementation State

Stage 3.5E PR2 adds the first PostgreSQL role / privilege baseline:

```text
compass_migration_owner
compass_app_writer
compass_projection_worker
compass_snapshot_worker
compass_readonly
```

The PR2 migration is:

```text
db/migrations/005_create_durable_state_permission_roles.sql
```

This migration defines runtime responsibility roles and table-level grants.

It does not replace the existing high-privilege `compass_user` test owner connection. Existing storage, replay, projection, snapshot, and mechanism integration tests may continue to use `compass_user` for setup, cleanup, and deterministic reset.

Runtime-role permission behavior is verified separately in the Stage 3.5E permission-test PRs.

---

## PR3 Implementation State

Stage 3.5E PR3 adds isolated permission-boundary integration tests for accepted history and authority-adjacent write-side records.

PR3 verifies the PR2 role / privilege baseline for:

```text
order_events
idempotency_records
order_events_global_position_seq
```

The PR3 tests are located under:

```text
tests/integration/security/
```

PR3 also adds a layered testing boundary note:

```text
docs/boundary_notes/layered_testing_strategy_for_permission_and_governance.md
```

The tests intentionally use a layered testing model:

```text
compass_user
= test-owner setup / cleanup / fixture authority

compass_* runtime roles
= permission-boundary probes through SET ROLE
```

PR3 confirms that `compass_app_writer` can use the intended accepted-history append and successful idempotency receipt insert paths, but cannot rewrite accepted events or idempotency receipts.

PR3 also confirms that projection, snapshot, and read-only roles cannot mutate accepted history, cannot rewrite successful idempotency receipts, and cannot consume the accepted-history global-position sequence.

At the current schema level, `idempotency_records` stores only successful request-effect receipts:

```text
request_id → accepted_event_id
status = SUCCEEDED
```

It does not store failed attempts, rejected candidates, retry lifecycle state, failure reasons, or runtime decision traces.

Therefore, `compass_readonly` may SELECT `idempotency_records` in Stage 3.5E. If future governance tables introduce failure reasons, retry attempts, or decision traces, those tables may require a separate audit-oriented read role.

PR3 does not test derived-state mutation permissions. Those remain scoped to PR4.

---

## PR4 Implementation State

Stage 3.5E PR4 adds isolated permission-boundary integration tests for derived read-side durable artifacts.

PR4 verifies the PR2 role / privilege baseline for:

```text
projection_states
projection_checkpoints
projection_snapshots
```

The PR4 tests are located under:

```text
tests/integration/security/
```

PR4 confirms that derived-state artifacts remain operationally mutable or insertable through intended runtime roles:

```text
projection_states
= mutable by compass_projection_worker
= selectable by compass_snapshot_worker and compass_readonly
= inaccessible to compass_app_writer by default

projection_checkpoints
= mutable by compass_projection_worker
= selectable by compass_snapshot_worker and compass_readonly
= inaccessible to compass_app_writer by default

projection_snapshots
= insertable by compass_snapshot_worker
= selectable by compass_projection_worker and compass_readonly
= not updateable or deleteable by normal runtime roles
= inaccessible to compass_app_writer by default
```

PR4 also records that permission probes use `SET ROLE` as a test-time mechanism, not as proof of production login identity wiring.

Production login identities, role-specific connection pools, connection-pool contamination tests, chaos tests, and multi-worker failure behavior remain deferred.

---

## PR5 Implementation State

Stage 3.5E PR5 defines the minimal actor metadata boundary before Stage 4 runtime semantic governance.

PR5 clarifies:

```text
database role
≠ actor metadata
≠ governance decision evidence
```

The current direction is documentation-only:

```text
existing created_by-style fields
= baseline producer metadata

validated_by / decision_by / receipt_by / triggered_by
= Stage 4 governance evidence
```

PR5 does not introduce a full actor registry, audit table, DecisionReceipt schema, or identity system.

It exists to prepare Stage 4 so that future receipts can record who produced or applied evidence without overloading database roles with semantic decision meaning.

---

## Stage Completion Criteria

Stage 3.5E is complete when the project can clearly demonstrate:

```text
accepted history cannot be casually mutated through the same assumptions as derived state

successful idempotency receipts cannot be casually rewritten by normal runtime roles

derived runtime artifacts remain operationally rebuildable / updatable

permission boundaries are documented and tested

minimal actor metadata exists or is clearly deferred

future Stage 4 receipt / decision policy work has a stable durable-history foundation
```

The end state should be stronger semantic infrastructure, not a full security platform.
