# Stage 3.5E PR Breakdown

[← Back to Stage 3.5E](README.md)

## Purpose

This note proposes the implementation sequence for:

```text
Stage 3.5E — Durable History and Permission Hardening
```

The goal is to introduce a minimal durable-history mutation boundary before the project enters broader runtime semantic governance.

Stage 3.5E should not become a full authentication or authorization system.

It should define the minimum permission semantics needed to make accepted history harder to mutate than derived runtime state.

---

## Stage Principle

```text
accepted history = authority
derived state = rebuildable runtime artifact
permission boundary must respect authority level
```

This means:

```text
order_events
should be append-oriented and mutation-restricted

projection_states
should remain controlled-but-mutable because projections are derived

projection_checkpoints
should remain controlled-but-mutable because checkpoints are operational progress metadata

projection_snapshots
should remain derived evidence and replay-efficiency artifacts, not authority
```

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

---

# PR1 — Durable History Permission Boundary

## Goal

Define the Stage 3.5E boundary before implementation begins.

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

## Expected Commit

```text
docs: define durable history permission boundary
```

---

# PR2 — Database Role / Privilege Baseline

## Goal

Introduce the minimal PostgreSQL permission structure needed to distinguish accepted-history mutation from derived-state mutation.

## Scope

PR2 may introduce database role concepts such as:

```text
app_writer
projection_worker
snapshot_worker
migration_owner
read_only_observer
```

The exact names may change during implementation.

The important point is not the naming.

The important point is that different runtime responsibilities should not have identical mutation authority over all durable tables.

## Expected Direction

A possible baseline:

```text
app_writer
= can append accepted events through intended write-side path
= should not freely update / delete accepted history

projection_worker
= can update projection_states
= can update projection_checkpoints
= should not mutate accepted history

snapshot_worker
= can insert projection_snapshots under controlled paths
= should not mutate accepted history

read_only_observer
= can read relevant runtime tables
= cannot mutate durable state
```

## Non-goals

PR2 should not implement:

```text
full RBAC
user accounts
login
JWT
session lifecycle
multi-tenant roles
cloud IAM mapping
```

## Expected Commit

```text
db: add minimal durable-state permission roles
```

---

# PR3 — Accepted-History Mutation Hardening Tests

## Goal

Prove that accepted history is harder to mutate than derived runtime state.

## Scope

PR3 should add tests demonstrating that unauthorized or unintended mutation patterns against `order_events` are rejected.

The tests should focus on mutation semantics, not business-domain validation.

Possible test categories:

```text
unauthorized update of accepted event is rejected
unauthorized delete of accepted event is rejected
unauthorized direct insert path is rejected if outside intended role
append path remains available to intended writer role
read-only role can inspect accepted history but cannot mutate it
```

## Important Boundary

These tests should not replace Compass Layer 1.

Compass Layer 1 decides whether a candidate event is semantically admissible.

Stage 3.5E permission hardening decides whether a runtime actor is allowed to mutate durable state through a given path.

These are different boundaries.

## Expected Commit

```text
tests: harden accepted-history mutation permissions
```

---

# PR4 — Derived-State Mutation Permission Tests

## Goal

Prove that derived runtime state remains operationally mutable through intended paths.

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
snapshot worker role can insert projection snapshot
read-only role cannot mutate derived runtime tables
accepted-history writer role does not automatically own derived-state mutation rights
```

## Important Boundary

Stage 3.5E should not make all durable tables append-only.

Only accepted history has authority-level mutation restrictions.

Derived runtime artifacts must remain rebuildable and operational.

## Expected Commit

```text
tests: preserve controlled derived-state mutation permissions
```

---

# PR5 — Minimal Actor Metadata Boundary

## Goal

Introduce or document the minimum actor metadata needed before Stage 4 receipts and runtime governance.

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

## Non-goals

PR5 should not implement:

```text
DecisionReceipt
RuntimeDecisionPolicy
SemanticOutcome
full actor registry
user management
audit dashboard
```

## Expected Commit

```text
docs: define minimal actor metadata boundary
```

or, if implementation is introduced:

```text
db: add minimal actor metadata fields
```

---

# PR6 — Stage 3.5E Closeout

## Goal

Close Stage 3.5E after the durable-history permission boundary is implemented and documented.

## Scope

PR6 should update:

```text
docs/implementation_notes/stage_3_5e/README.md
docs/roadmap/implementation_roadmap.md
docs/roadmap/compass_runtime_roadmap.md
docs/roadmap/deferred_architecture_backlog.md
docs/adr/README.md
README.md only if needed
```

## Expected Closeout Statements

The closeout should record:

```text
Stage 3.5E completed the minimal durable-history permission boundary.

Accepted history is now protected differently from derived runtime state.

Derived projection state, checkpoints, and snapshots remain operationally mutable through controlled paths.

Full RBAC, login/session auth, cloud IAM, and Stage 4 runtime decision policy remain deferred.
```

## Expected Commit

```text
docs: align stage 3.5e closeout
```

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
Compass Layer 2
SemanticOutcome
DecisionReceipt
RuntimeDecisionPolicy
action safety gate
agent sandboxing
```

Those belong to later stages.

Stage 3.5E is the minimum durable-history permission hardening layer.
