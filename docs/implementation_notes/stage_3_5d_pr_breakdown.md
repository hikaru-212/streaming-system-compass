# Stage 3.5D PR Breakdown

[← Back to Implementation Notes](README.md)

## Purpose

This note proposes the implementation sequence for:

```text
Stage 3.5D — Snapshot Trust Contract / Replay Efficiency
```

The goal is to add snapshot-assisted replay / rehydration without treating snapshot as source of truth.

---

## Stage Principle

```text
accepted history = authority
snapshot = derived state compression
fast path = snapshot + tail replay + trust checks
authority path = full accepted-history replay
```

Additional implementation principles:

```text
canonical hash must be deterministic
snapshot write must be idempotent for benign races
snapshot generation policy must be separate from trust validation
database constraints should not over-assume reducer version semantics
```

---

## Proposed PR Sequence

```text
PR1 — General Snapshot Trust Contract Boundary
PR2 — Projection Snapshot Schema Baseline
PR3 — PostgresProjectionSnapshotStore
PR4 — Projection Snapshot-Assisted Replay Validator
PR5 — Aggregate Snapshot Trust Extension
PR6 — Aggregate Snapshot Schema / Store
PR7 — Snapshot-Assisted Write-Side Rehydration
```

A later PR may close out Stage 3.5D after PR7.

---

## PR1 — General Snapshot Trust Contract Boundary

### Goal

Define snapshot as a general derived-state trust boundary.

### Scope

- add snapshot trust postmortem
- add snapshot trust boundary note
- add snapshot trust architecture note
- add Stage 3.5D PR breakdown note
- define read-side first implementation
- recognize write-side aggregate snapshot as a stricter extension
- define canonical hashing as required implementation boundary
- define snapshot write collision policy
- define snapshot generation policy separation

### Non-goals

- no production code
- no schema
- no store
- no validator
- no write-side command path changes

---

## PR2 — Projection Snapshot Schema Baseline

### Goal

Create the physical shape for projection snapshots.

### Scope

- add migration for `projection_snapshots`
- define projection snapshot lineage columns
- define snapshot schema version
- define reducer version
- define payload hash
- add schema constraint tests
- avoid over-strict `state_version = source_event_sequence` constraint

### Non-goals

- no Python store
- no replay validator
- no aggregate snapshot table
- no write-side rehydration

---

## PR3 — PostgresProjectionSnapshotStore

### Goal

Make `projection_snapshots` usable through a Python storage boundary.

### Scope

- add `ProjectionSnapshot` model
- add `PostgresProjectionSnapshotStore`
- support save / load latest / clear behavior
- preserve caller-owned transaction boundary
- implement idempotent snapshot write collision policy
- add integration tests

### Non-goals

- no snapshot trust decision
- no snapshot-assisted replay
- no aggregate snapshot store

---

## PR4 — Projection Snapshot-Assisted Replay Validator

### Goal

Validate projection snapshot fast-path reconstruction against authority-path replay behavior.

### Scope

- load projection snapshot
- run trust checks
- verify canonical payload hash
- load tail events after snapshot boundary
- replay tail through canonical reducer
- compare against full accepted-history replay where required by tests
- return structured result / reason

### Non-goals

- no `SemanticOutcome`
- no runtime decision policy
- no automatic repair
- no write-side command path changes

---

## PR5 — Aggregate Snapshot Trust Extension

### Goal

Extend the general Snapshot Trust Contract to write-side aggregate rehydration.

### Scope

- document why write-side snapshot is stricter
- define aggregate snapshot trust evidence
- define admission-path constraints
- define fallback behavior
- add implementation plan for aggregate snapshot schema / store

### Non-goals

- no aggregate snapshot table yet
- no store yet
- no command path modification yet

---

## PR6 — Aggregate Snapshot Schema / Store

### Goal

Add durable aggregate snapshot storage.

### Scope

- add `aggregate_snapshots` migration
- add `AggregateSnapshot` model
- add `PostgresAggregateSnapshotStore`
- implement idempotent collision policy
- add schema and integration tests

### Non-goals

- no command path integration yet
- no relaxation of admission
- no automatic repair policy

---

## PR7 — Snapshot-Assisted Write-Side Rehydration

### Goal

Use trusted aggregate snapshots to accelerate write-side aggregate rehydration.

### Scope

- add snapshot-aware rehydration path
- fallback to full accepted-history replay when snapshot trust fails
- preserve idempotency behavior
- preserve Compass Layer 1 validation
- preserve append-time admission
- add write-side tests for snapshot fast path and fallback path

### Non-goals

- no bypass of accepted history
- no bypass of concurrency admission
- no bypass of Compass Layer 1
- no `SemanticOutcome`
- no action safety behavior
