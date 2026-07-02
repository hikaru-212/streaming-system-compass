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

In progress.

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

PR3 verifies the database mutation boundary around `order_events` and successful idempotency receipts.

## Status

Planned.

## Scope

PR3 should add tests demonstrating that unauthorized or unintended mutation patterns against authority-adjacent write-side tables are rejected.

The tests should focus on mutation semantics, not business-domain validation.

Possible test categories:

```text
unauthorized update of accepted event is rejected
unauthorized delete of accepted event is rejected
unauthorized update of idempotency receipt is rejected
unauthorized delete of idempotency receipt is rejected
append path remains available to intended writer role
successful idempotency receipt insert remains available to intended writer role
read-only role can inspect accepted history but cannot mutate it
projection worker cannot mutate accepted history
snapshot worker cannot mutate accepted history
```

A likely location is:

```text
tests/integration/security/
```

or another clearly separated permission-test location.

## Important Boundary

These tests should not replace Compass Layer 1.

Compass Layer 1 decides whether a candidate event is semantically admissible.

Stage 3.5E permission hardening decides whether a runtime actor is allowed to mutate durable state through a given path.

These are different boundaries.

## Non-goals

PR3 should not add:

```text
new business-domain validation rules
new Compass Layer 1 semantics
projection mutation tests
snapshot trust validation
SemanticOutcome
DecisionReceipt
RuntimeDecisionPolicy
full RBAC tests
```

---

# PR4 — Derived-State Mutation Permission Tests

## Goal

Prove that derived runtime state remains operationally mutable through intended paths.

PR4 verifies that Stage 3.5E does not accidentally treat all durable tables as append-only authority.

## Status

Planned.

## Scope

PR4 should add tests showing that projection-related tables can still support normal runtime operations.

The system must still allow controlled mutation of:

```text
projection_states
projection_checkpoints
projection_snapshots
```

because these tables represent derived state, operational progress metadata, and derived replay-efficiency evidence.

Possible test categories:

```text
projection worker role can upsert projection state
projection worker role can update checkpoint progress
projection worker role can clear projection state during controlled rebuild / reset
snapshot worker role can insert projection snapshot
read-only role cannot mutate derived runtime tables
app_writer does not have projection-state access by default
projection worker cannot mutate snapshots unless explicitly granted
snapshot worker cannot mutate projection checkpoints unless explicitly granted
```

## Important Boundary

Stage 3.5E should not make all durable tables append-only.

Only accepted history has authority-level append-only semantics.

Successful idempotency receipts are insert-once request-effect evidence under the current schema.

Derived runtime artifacts must remain rebuildable and operational.

## Non-goals

PR4 should not add:

```text
accepted-history mutation tests already covered by PR3
new projection reducer behavior
new snapshot trust decision logic
new replay validator behavior
new runtime state resolver policy
SemanticOutcome
DecisionReceipt
RuntimeDecisionPolicy
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
