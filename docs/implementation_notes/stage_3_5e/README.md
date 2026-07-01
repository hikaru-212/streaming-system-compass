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
idempotency memory
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

Stage 3.5E builds on this by making accepted-history mutation harder to perform outside intended append paths.

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

This sequence may be adjusted as implementation reveals constraints.

However, the stage should avoid expanding into full RBAC or production authentication.

---

## Stage Completion Criteria

Stage 3.5E is complete when the project can clearly demonstrate:

```text
accepted history cannot be casually mutated through the same assumptions as derived state

derived runtime artifacts remain operationally rebuildable / updatable

permission boundaries are documented and tested

minimal actor metadata exists or is clearly deferred

future Stage 4 receipt / decision policy work has a stable durable-history foundation
```

The end state should be stronger semantic infrastructure, not a full security platform.
