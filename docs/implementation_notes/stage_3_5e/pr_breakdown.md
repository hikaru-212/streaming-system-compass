# Stage 3.5E PR Breakdown

[← Back to Stage 3.5E](README.md)

## Purpose

This note proposes the implementation sequence for:

```text
Stage 3.5E — Durable History and Permission Hardening
```

The goal of Stage 3.5E is to introduce a minimal durable-history mutation boundary before the project enters broader runtime semantic governance.

Stage 3.5E should not become a full authentication or authorization system.

It should define the minimum permission semantics needed to make accepted history harder to mutate than derived runtime state.

---

## Stage Principle

```text
accepted history = authority
successful request-effect receipt = insert-once evidence
derived state = rebuildable runtime artifact
permission boundary must respect authority level
```

This means:

```text
order_events
should be append-oriented and mutation-restricted

idempotency_records
should remain successful request-to-accepted-event receipts under the current schema

projection_states
should remain controlled-but-mutable because projections are derived

projection_checkpoints
should remain controlled-but-mutable because checkpoints are operational progress metadata

projection_snapshots
should remain derived evidence and replay-efficiency artifacts, not authority
```

Additional implementation principles:

```text
permission hardening must not replace semantic validation
database roles should represent runtime responsibility boundaries, not product users
accepted-history mutation should be stricter than derived-state mutation
successful idempotency receipts should not be rewritten by normal runtime roles
write-side command admission must not depend on read-side projection state
existing integration tests may still use high-privilege setup / cleanup paths
permission tests should be isolated from normal storage behavior tests
Stage 3.5E should prepare for Stage 4 receipts without implementing Stage 4
```

---

## Stage Branch / PR Branch Workflow

Stage 3.5E follows the staged delivery workflow used in earlier implementation phases.

The project should not treat one PR as necessarily equal to one commit.

Instead, the intended workflow is:

```text
one stage branch
= one integration branch for the whole stage

one PRx branch
= one coherent semantic delivery unit inside the stage

one PRx branch may contain multiple commits
= each commit preserves a smaller documentation, schema, code, or test boundary
```

For Stage 3.5E, the integration branch is:

```text
feat/stage3.5e-durable-history-permission-hardening
```

Individual PR branches should be created from the current Stage 3.5E integration branch, for example:

```text
feat/stage3.5e-pr2-database-role-privilege-baseline
feat/stage3.5e-pr3-accepted-history-mutation-hardening-tests
feat/stage3.5e-pr4-derived-state-mutation-permission-tests
```

Each PR branch should be merged back into the Stage 3.5E integration branch.

The Stage 3.5E integration branch should be merged back to `main` only after the stage is complete or intentionally closed.

---

## Commit Discipline

A PR may contain more than one commit.

The important rule is not:

```text
one PR = one commit
```

The important rule is:

```text
one PR = one coherent semantic delivery unit
one commit = one smaller boundary-preserving change
```

For example, a PR may contain:

```text
docs: define database role privilege baseline
db: add durable-state permission role migration
docs: align database role privilege baseline
```

These commits may all belong to the same PR if they serve the same PR-level semantic goal.

The commit boundary should remain small enough to explain what changed and why.

The PR boundary should remain large enough to deliver one meaningful stage sub-goal.

---

## Documentation-First Implementation Pattern

When a PR introduces a new semantic or infrastructure boundary, the preferred order is:

```text
1. define the boundary in documentation
2. implement the minimum mechanism
3. add or defer tests according to the PR scope
4. align README / roadmap / breakdown notes if needed
```

This does not mean that documentation and implementation must always be split into separate PRs.

It means the PR should make the semantic contract clear before or alongside the implementation.

Detailed commit planning should happen when entering each PRx.

This breakdown records the PR-level sequence, not the exact commit-level sequence.

---

## Proposed PR Sequence

```text
PR1 — Durable History Permission Boundary
PR2 — Database Role / Privilege Baseline
PR3 — Accepted-History Mutation Hardening Tests
PR4 — Derived-State Mutation Permission Tests
PR5 — Minimal Actor Metadata Boundary
PR6 — Stage 3.5E Closeout
```

After PR6, Stage 3.5E should be ready to merge the stage branch into `main`.

---

# PR1 — Durable History Permission Boundary

## Goal

Define the Stage 3.5E boundary before implementation begins.

PR1 establishes why durable-history permission hardening exists and how it relates to the project authority model.

## Status

Completed.

## Scope

PR1 should add:

```text
docs/implementation_notes/stage_3_5e/README.md
docs/implementation_notes/stage_3_5e/pr_breakdown.md
docs/boundary_notes/durable_history_permission_boundary.md
```

PR1 should clarify:

```text
why Stage 3.5E exists
why accepted history requires stricter mutation boundaries
why derived state must remain rebuildable
why this stage is not full RBAC
how this stage prepares for Stage 4 receipts / governance
```

## Non-goals

PR1 does not add:

```text
SQL migrations
PostgreSQL roles
permission tests
actor metadata tables
runtime policy code
Compass Layer 2
SemanticOutcome
DecisionReceipt
RuntimeDecisionPolicy
```

---

# PR2 — Database Role / Privilege Baseline

## Goal

Introduce the minimal PostgreSQL permission structure needed to distinguish accepted-history mutation from derived-state mutation.

PR2 translates the durable-history permission boundary into a database-native role / privilege baseline.

## Status

Completed after the role / privilege migration baseline is added.

## Scope

PR2 may include:

```text
database role / privilege boundary documentation
minimal PostgreSQL runtime roles
table-level GRANT / REVOKE rules
migration for role / privilege baseline
README / PR breakdown alignment if needed
```

PR2 may introduce database role concepts such as:

```text
migration_owner
app_writer
projection_worker
snapshot_worker
read_only_observer
```

The exact names may change during implementation.

The important point is not the naming.

The important point is that different runtime responsibilities should not have identical mutation authority over all durable tables.

## Expected Direction

A possible baseline:

```text
migration_owner
= owns schema / migration authority
= not a normal runtime role

app_writer
= can append accepted events through intended write-side path
= can insert successful idempotency receipts
= should not freely update / delete accepted history
= should not rewrite idempotency receipts
= should not depend on projection state for command admission

projection_worker
= can read accepted history
= can update projection_states
= can update projection_checkpoints
= should not mutate accepted history
= should not mutate idempotency receipts

snapshot_worker
= can inspect accepted history / derived state as needed
= can insert projection_snapshots under controlled paths
= should not mutate accepted history
= should not mutate projection state or checkpoints

read_only_observer
= can read relevant runtime tables
= cannot mutate durable state
```

## Permission Direction

A possible table-level direction:

```text
order_events
= app_writer SELECT / INSERT
= projection_worker SELECT
= snapshot_worker SELECT
= read_only_observer SELECT
= no normal runtime UPDATE / DELETE

idempotency_records
= app_writer SELECT / INSERT
= read_only_observer SELECT
= no normal runtime UPDATE / DELETE under the current successful-receipt design

projection_states
= projection_worker SELECT / INSERT / UPDATE / DELETE
= snapshot_worker SELECT
= read_only_observer SELECT
= app_writer has no access by default

projection_checkpoints
= projection_worker SELECT / INSERT / UPDATE / DELETE
= snapshot_worker SELECT
= read_only_observer SELECT
= app_writer has no access by default

projection_snapshots
= snapshot_worker SELECT / INSERT
= projection_worker SELECT
= read_only_observer SELECT
= app_writer has no access by default
= no normal runtime UPDATE / DELETE by default
```

This direction may be refined during implementation.


## Implemented Migration Boundary

PR2 adds:

```text
db/migrations/005_create_durable_state_permission_roles.sql
```

The migration creates runtime responsibility roles and grants table-specific privileges without changing the existing `compass_user` test owner path.

The migration intentionally does not revoke privileges from `compass_user`, does not transfer table ownership, and does not force existing integration tests to use low-privilege runtime roles.

Sequence privilege is intentionally narrow:

```text
order_events_global_position_seq
= USAGE / SELECT for compass_app_writer
= SELECT for compass_readonly
= no USAGE for projection_worker or snapshot_worker
```

Only `compass_app_writer` should be able to consume the accepted-history global-position sequence because it is the only runtime role in PR2 allowed to insert into `order_events`.

## Non-goals

PR2 should not implement:

```text
full permission test matrix
accepted-history mutation hardening tests
derived-state mutation permission tests
retry lifecycle table
failed attempt table
full RBAC
user accounts
login
JWT
session lifecycle
multi-tenant roles
cloud IAM mapping
actor registry
DecisionReceipt
RuntimeDecisionPolicy
Compass Layer 2
```

Detailed permission tests belong to later PRs.

---

# PR3 — Accepted-History Mutation Hardening Tests

## Goal

Prove that accepted history is harder to mutate than derived runtime state.

PR3 verifies the database mutation boundary around `order_events`, successful idempotency receipts, and the accepted-history global-position sequence.

## Status

Completed.

## Scope

PR3 adds isolated permission-boundary integration tests demonstrating that unauthorized or unintended mutation patterns against authority-adjacent write-side tables are rejected.

The tests focus on mutation semantics and database privilege boundaries, not business-domain validation.

Implemented test location:

```text
tests/integration/security/
```

Implemented support note:

```text
docs/boundary_notes/layered_testing_strategy_for_permission_and_governance.md
```

PR3 covers:

```text
order_events
idempotency_records
order_events_global_position_seq
```

Implemented test coverage:

```text
compass_app_writer
= can SELECT / INSERT order_events
= cannot UPDATE / DELETE order_events
= can SELECT / INSERT idempotency_records
= cannot UPDATE / DELETE idempotency_records
= can consume order_events_global_position_seq

compass_projection_worker
= can SELECT order_events
= cannot INSERT / UPDATE / DELETE order_events
= cannot SELECT / INSERT / UPDATE / DELETE idempotency_records
= cannot consume order_events_global_position_seq

compass_snapshot_worker
= can SELECT order_events
= cannot INSERT / UPDATE / DELETE order_events
= cannot SELECT / INSERT / UPDATE / DELETE idempotency_records
= cannot consume order_events_global_position_seq

compass_readonly
= can SELECT order_events
= can SELECT idempotency_records
= cannot INSERT / UPDATE / DELETE order_events
= cannot INSERT / UPDATE / DELETE idempotency_records
= cannot consume order_events_global_position_seq
```

The sequence tests intentionally verify the accepted-history cursor boundary directly instead of relying only on `INSERT order_events` as an indirect proof.

The permission tests use a layered testing model:

```text
compass_user
= test-owner setup / cleanup / fixture authority

compass_* runtime roles
= isolated permission probes through SET ROLE
```

`SET ROLE` is used only as a test mechanism. It is not a production role-switching abstraction, and it is not intended for Layer 3 causal / multi-role runtime-flow tests.

## Important Boundary

These tests do not replace Compass Layer 1.

Compass Layer 1 decides whether a candidate event is semantically admissible.

Stage 3.5E permission hardening decides whether a runtime actor is allowed to mutate durable state through a given path.

These are different boundaries.

At the current schema level, `idempotency_records` stores only successful request-effect receipts:

```text
request_id → accepted_event_id
status = SUCCEEDED
```

It does not store failed attempts, rejected candidates, retry lifecycle state, failure reasons, or runtime decision traces.

Therefore, `compass_readonly` may SELECT `idempotency_records` in Stage 3.5E. If future governance tables introduce failure reasons, retry attempts, or decision traces, those tables may require a separate audit-oriented read role.

## Non-goals

PR3 does not add:

```text
new business-domain validation rules
new Compass Layer 1 semantics
projection mutation tests
snapshot trust validation
SemanticOutcome
DecisionReceipt
RuntimeDecisionPolicy
full RBAC tests
production role-switching infrastructure
Layer 3 multi-role causal-flow tests
```

Derived-state mutation boundaries remain scoped to PR4.
---

# PR4 — Derived-State Mutation Permission Tests

## Goal

Prove that derived runtime state remains operationally mutable through intended paths.

PR4 verifies that Stage 3.5E does not accidentally treat all durable tables as append-only authority.

## Status

Completed.

## Scope

PR4 adds isolated permission-boundary integration tests showing that projection-related tables support their intended runtime operations while still rejecting unintended mutation paths.

Implemented test location:

```text
tests/integration/security/
```

Shared security-test setup:

```text
tests/integration/security/conftest.py
```

Implemented closeout note:

```text
docs/implementation_notes/stage_3_5e/derived_state_mutation_permission_tests.md
```

PR4 covers:

```text
projection_states
projection_checkpoints
projection_snapshots
```

Implemented test coverage:

```text
compass_projection_worker
= can SELECT / INSERT / UPDATE / DELETE projection_states
= can SELECT / INSERT / UPDATE / DELETE projection_checkpoints
= can SELECT projection_snapshots
= cannot INSERT / UPDATE / DELETE projection_snapshots

compass_snapshot_worker
= can SELECT projection_states
= cannot INSERT / UPDATE / DELETE projection_states
= can SELECT projection_checkpoints
= cannot INSERT / UPDATE / DELETE projection_checkpoints
= can SELECT / INSERT projection_snapshots
= cannot UPDATE / DELETE projection_snapshots

compass_readonly
= can SELECT projection_states
= can SELECT projection_checkpoints
= can SELECT projection_snapshots
= cannot INSERT / UPDATE / DELETE derived runtime tables

compass_app_writer
= cannot SELECT / INSERT / UPDATE / DELETE projection_states
= cannot SELECT / INSERT / UPDATE / DELETE projection_checkpoints
= cannot SELECT / INSERT / UPDATE / DELETE projection_snapshots
```

PR4 also verifies that security permission tests can share setup / cleanup infrastructure without converting existing storage or mechanism integration tests into low-privilege role tests.

## Important Boundary

Stage 3.5E should not make all durable tables append-only.

Only accepted history has authority-level append-only semantics.

Successful idempotency receipts are insert-once request-effect evidence under the current schema.

Derived runtime artifacts must remain rebuildable and operational.

The tested distinction is:

```text
projection_states
= derived read-side state
= controlled mutable artifact

projection_checkpoints
= operational progress metadata
= controlled mutable artifact

projection_snapshots
= derived evidence / replay-efficiency artifact
= insertable by snapshot worker
= not rewritable or deletable by normal runtime roles
```

## Assertion Fidelity Lesson

PR4 reinforced a test-design rule:

```text
If a permission probe uses RETURNING, assert the returned evidence directly.
```

This matters because row-count-only assertions can hide driver-level type mismatches.

During snapshot permission tests, exact row assertions exposed the PostgreSQL UUID → Python UUID boundary. A weaker assertion such as `len(rows) == 1` would have hidden that mismatch.

The reusable lesson is recorded in:

```text
docs/postmortems/from_row_count_assertions_to_evidence_assertions.md
```

## SET ROLE Boundary

PR4 uses `SET ROLE` as a test-time permission probing mechanism.

This proves effective PostgreSQL privileges for runtime responsibility roles.

It does not prove production login identity wiring, role-specific database URLs, secret management, or connection-pool role isolation.

That testing-scope decision is recorded in:

```text
docs/adr/0015_permission_probing_with_set_role.md
```

## Deferred Chaos / Production-Hardening Tests

PR4 does not prove production-like behavior under:

```text
concurrent workers
independent runtime connections
connection-pool reuse
rollback failure
worker crash windows
snapshot write races
checkpoint advancement races
derived-state corruption recovery
permission bypass attempts during active workflows
```

Those belong to later production-hardening / chaos-test work after runtime governance, structured outcomes, retry classification, and decision receipts are more complete.

## Non-goals

PR4 does not add:

```text
accepted-history mutation tests already covered by PR3
new projection reducer behavior
new snapshot trust decision logic
new replay validator behavior
new runtime state resolver policy
new actor metadata schema
production login users
connection-pool policy
chaos tests
SemanticOutcome
DecisionReceipt
RuntimeDecisionPolicy
Compass Layer 2
```

---

# PR5 — Minimal Actor Metadata Boundary

## Goal

Introduce or document the minimum actor metadata needed before Stage 4 receipts and runtime governance.

PR5 should clarify what the project needs to know about runtime actors without turning Stage 3.5E into a full identity system.

## Status

Planned.

## Scope

PR5 may add lightweight metadata concepts such as:

```text
actor_id
actor_type
actor_role
created_by
triggered_by
runtime_component
```

The exact implementation depends on the existing schema and should be kept minimal.

The goal is to prepare for future questions such as:

```text
who produced validation evidence?
who generated a snapshot?
who triggered rebuild?
who requested repair?
who quarantined runtime state?
who made a privileged runtime decision?
```

PR5 may be documentation-only if schema changes are not yet justified.

## Non-goals

PR5 should not implement:

```text
DecisionReceipt
RuntimeDecisionPolicy
SemanticOutcome
full actor registry
user management
login
session management
JWT
audit dashboard
cloud IAM integration
```

---

# PR6 — Stage 3.5E Closeout

## Goal

Close Stage 3.5E after the durable-history permission boundary is implemented and documented.

PR6 should align the stage documentation with the final implementation state.

## Status

Planned.

## Scope

PR6 should update only the documents that need closeout alignment, such as:

```text
docs/implementation_notes/stage_3_5e/README.md
docs/roadmap/implementation_roadmap.md
docs/roadmap/compass_runtime_roadmap.md
docs/roadmap/deferred_architecture_backlog.md
docs/adr/README.md
README.md only if needed
```

The exact closeout files should be decided after PR2–PR5 are completed.

## Expected Closeout Statements

The closeout should record:

```text
Stage 3.5E completed the minimal durable-history permission boundary.

Accepted history is protected differently from derived runtime state.

Successful idempotency receipts are protected as insert-once request-effect evidence under the current schema.

Derived projection state, checkpoints, and snapshots remain operationally mutable or insertable through controlled paths.

Full RBAC, login/session auth, cloud IAM, and Stage 4 runtime decision policy remain deferred.
```

## Non-goals

PR6 should not add new runtime behavior.

PR6 should not introduce new schema or permission semantics unless a small documentation correction reveals a previously missed alignment issue.

---

## Stage 3.5E Non-goals Summary

Across all PRs, Stage 3.5E should avoid:

```text
full RBAC
login
JWT
session management
multi-tenant auth
production IAM
complete audit platform
retry lifecycle table
failed attempt table
Compass Layer 2
SemanticOutcome
DecisionReceipt
RuntimeDecisionPolicy
action safety gate
agent sandboxing
```

Those belong to later stages.

Stage 3.5E is the minimum durable-history permission hardening layer.

---

## Stage 3.5E Closeout Direction

After PR6, Stage 3.5E may be closed by merging:

```text
base: main
compare: feat/stage3.5e-durable-history-permission-hardening
```

Suggested Stage 3.5E closeout title:

```text
feat: complete Stage 3.5E durable history permission hardening
```

Stage 3.5E should close with:

```text
durable history permission boundary documented
database role / privilege baseline established
accepted-history mutation hardening verified
successful idempotency receipt rewrite prevention verified
derived-state controlled mutation verified
minimal actor metadata boundary documented or explicitly deferred
full RBAC and Stage 4 runtime governance explicitly deferred
```

---

## Final Principle

```text
Accepted history defines truth.
Successful idempotency receipts preserve request-to-effect evidence.
Derived runtime state supports operation.
Permission boundaries must respect those differences.
```

Stage 3.5E completes the minimum database mutation hardening needed before broader runtime semantic governance.
