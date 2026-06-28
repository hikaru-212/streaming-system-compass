# Stage 3.5D PR Breakdown

[← Back to Implementation Notes](README.md)

## Purpose

This note records the closeout-oriented implementation sequence for:

```text
Stage 3.5D — Snapshot Trust Contract / Replay Efficiency
```

The goal of Stage 3.5D is to add snapshot-assisted replay / rehydration boundaries without treating snapshots as source of truth.

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
store collision handling must distinguish benign duplicate writes from inconsistent evidence
resolver must consume externally qualified snapshot identity instead of selecting trust itself
write-side aggregate snapshots require a stricter trust contract than read-side projection snapshots
```

---

## Updated PR Sequence

The Stage 3.5D sequence has converged to:

```text
PR1   — General Snapshot Trust Contract Boundary
PR1.5 — CI Stage Branch Checks
PR2   — Projection Snapshot Schema Baseline
PR3   — PostgresProjectionSnapshotStore
PR4   — Projection Snapshot-Assisted Replay Validator
PR4.5 — Projection Snapshot-Assisted State Resolver
PR5   — Aggregate Snapshot Trust Boundary / Deferral Decision
```

The previously planned write-side aggregate snapshot implementation is deferred:

```text
Deferred PR6 — Aggregate Snapshot Schema / Store
Deferred PR7 — Snapshot-Assisted Write-Side Rehydration
```

After PR5, Stage 3.5D is ready to merge the stage branch into `main`.

---

## PR1 — General Snapshot Trust Contract Boundary

### Goal

Define snapshot as a general derived-state trust boundary.

### Status

Completed.

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

## PR1.5 — CI Stage Branch Checks

### Goal

Allow Stage 3.5D feature branches to run CI safely while preserving the stage branch workflow.

### Status

Completed.

### Scope

- allow stage feature branch naming in CI
- preserve PostgreSQL-backed test execution
- support Stage 3.5D PR isolation before merging into the stage branch

---

## PR2 — Projection Snapshot Schema Baseline

### Goal

Create the physical shape for projection snapshots.

### Status

Completed.

### Scope

- add migration for `projection_snapshots`
- define projection snapshot lineage columns
- define snapshot schema version
- define reducer version
- define payload hash
- add schema constraint tests
- avoid over-strict `state_version = source_event_sequence` database constraint
- enforce `source_event_id` as a globally unique accepted-event boundary
- enforce `source_global_position` as a globally unique accepted-history cursor
- preserve `source_event_sequence` as order-local through `UNIQUE(order_id, source_event_sequence)`

### Non-goals

- no Python store
- no replay validator
- no aggregate snapshot table
- no write-side rehydration

---

## PR3 — PostgresProjectionSnapshotStore

### Goal

Make `projection_snapshots` usable through a Python storage boundary.

### Status

Completed.

### Scope

- add `ProjectionSnapshot` model
- add `PostgresProjectionSnapshotStore`
- add `SnapshotWriteCollisionError`
- support `save_snapshot(snapshot)`
- support `load_latest_snapshot(order_id)`
- support `load_snapshot(snapshot_id)` for exact snapshot-id lookup
- support `clear_snapshots(order_id)`
- load latest snapshots by highest `source_global_position`, not by `created_at`
- preserve Decimal amount round-trip
- preserve metadata JSON round-trip
- load database-created `created_at`
- preserve caller-owned transaction boundary
- implement duplicate-write idempotency for same complete source boundary and same snapshot evidence
- detect inconsistent lineage or payload evidence as `SnapshotWriteCollisionError`
- use `INSERT ... ON CONFLICT DO NOTHING` followed by explicit source-boundary inspection
- add PostgreSQL integration tests

### Collision Policy

The complete projection snapshot source boundary is:

```text
source_event_id
+ order_id
+ source_event_sequence
+ source_global_position
```

PR3 treats duplicate writes as idempotent only when the existing row matches the incoming snapshot across:

```text
complete source boundary
+ snapshot_schema_version
+ reducer_version
+ payload_hash
```

PR3 raises `SnapshotWriteCollisionError` for:

```text
same complete source boundary + different payload_hash
same complete source boundary + different reducer_version
same complete source boundary + different snapshot_schema_version
partial boundary match
mixed boundary match across existing source-boundary evidence
same payload_hash but different lineage evidence
```

### Non-goals

- no snapshot trust decision
- no snapshot-assisted replay
- no canonical payload hash computation
- no snapshot builder
- no snapshot generation policy runtime
- no aggregate snapshot store
- no write-side rehydration
- no Compass Layer 2 validation
- no `SemanticOutcome`

---

## PR4 — Projection Snapshot-Assisted Replay Validator

### Goal

Validate projection snapshot-assisted reconstruction against authority-path replay behavior.

### Status

Completed.

### Scope

- add `ProjectionSnapshotReplayValidationStatus`
- add `ProjectionSnapshotReplayValidationResult`
- add `ProjectionSnapshotReplayValidator`
- load projection snapshots through `PostgresProjectionSnapshotStore`
- load accepted history through `PostgresAcceptedHistoryEventSource`
- load tail records through `PostgresProjectionEventSource`
- hydrate projection snapshots into `OrderState`
- replay accepted history through the canonical projection reducer as the authority path
- replay tail events after `snapshot.source_global_position`
- load tail events across pages
- detect non-advancing / out-of-order tail source cursor behavior as `TAIL_EVENT_SOURCE_CONTRACT_VIOLATION`
- compare snapshot-assisted state against authority state
- enforce current reducer compatibility with `snapshot.state_version == snapshot.source_event_sequence`
- reject snapshots whose source sequence is ahead of accepted history
- return structured result / reason / evidence fields
- add unit tests for validator behavior
- add PostgreSQL-backed tests for `PostgresAcceptedHistoryEventSource`
- add PostgreSQL integration tests for validator assembly

### Validation Statuses

```text
MATCH
MISSING_SNAPSHOT
NO_ACCEPTED_HISTORY_FOR_ORDER
INVALID_SNAPSHOT_BOUNDARY
TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
SNAPSHOT_ASSISTED_DRIFT
```

### Non-goals

- no canonical payload hash verification
- no reducer version compatibility matrix
- no snapshot schema migration policy
- no `SemanticOutcome`
- no runtime decision policy
- no automatic fallback / repair / quarantine
- no write-side command path changes
- no hot-path snapshot-assisted state resolver

PR4 is validation / audit evidence.

It is not the runtime fast path.

---

## PR4.5 — Projection Snapshot-Assisted State Resolver

### Goal

Use externally qualified projection snapshot evidence to resolve read-side projection state through snapshot + tail replay without full accepted-history replay on every normal resolver path.

### Status

Completed after closeout documentation.

### Scope

- add `ProjectionSnapshotAssistedResolutionStatus`
- add `ProjectionSnapshotAssistedResolutionResult`
- add `ProjectionSnapshotAssistedStateResolver`
- load exact projection snapshot by `trusted_snapshot_id`
- validate local structural and compatibility preconditions
- hydrate snapshot state
- load accepted-history tail events after `snapshot.source_global_position`
- replay tail through canonical reducer
- return resolved projection state only on successful resolution
- avoid full authority replay in the normal resolver path
- preserve strict no-partial-state exposure on unresolved results
- add unit tests for resolver behavior
- add PostgreSQL integration tests for real store/source wiring
- document how PR4 `MATCH` can currently qualify PR4.5 usage
- document the cost boundary of deriving `trusted_snapshot_id` through PR4 on every request

### Resolver Statuses

```text
RESOLVED_FROM_SNAPSHOT
MISSING_SNAPSHOT
INVALID_SNAPSHOT_PRECONDITION
INVALID_SNAPSHOT_COMPATIBILITY
TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
TAIL_REPLAY_FAILED
```

### Trust Boundary

PR4.5 consumes trust evidence.

It does not produce trust.

The strongest current source of `trusted_snapshot_id` is:

```text
PR4 validator MATCH
→ validation_result.snapshot_id
→ PR4.5 trusted_snapshot_id
```

This is currently an ephemeral and potentially expensive trust path because validation receipts are not yet persisted.

Durable receipt-backed trust selection is deferred to Stage 4.

### Non-goals

- no authority full replay comparison in the normal resolver path
- no `SnapshotTrustGate`
- no `ValidationReceiptStore`
- no `SnapshotFastPathSelector`
- no `RuntimeStateResolutionService`
- no `SemanticOutcome`
- no `DecisionReceipt`
- no diagnostic trace table
- no runtime policy engine
- no automatic fallback orchestration
- no automatic snapshot quarantine
- no write-side aggregate rehydration
- no command admission changes
- no measurement / benchmark substrate

PR4.5 is a read-side resolver primitive and evidence mechanism.

It is not Compass Layer 2 and not the final runtime state resolution service.

---

## PR5 — Aggregate Snapshot Trust Boundary / Deferral Decision

### Goal

Close Stage 3.5D by explicitly deferring write-side aggregate snapshot implementation and documenting why aggregate snapshot trust is stricter than read-side projection snapshot trust.

### Status

Completed.

### Scope

- document the difference between read-side projection snapshots and write-side aggregate snapshots
- explain why aggregate snapshots are higher risk because they can influence command validation / admission
- explain why current aggregate replay depth does not justify production write-side snapshot implementation
- mark aggregate snapshot schema / store as deferred
- mark snapshot-assisted write-side rehydration as deferred
- define future trigger conditions for reviving aggregate snapshot work
- update Stage 3.5D closeout documentation

### Non-goals

- no aggregate snapshot table
- no aggregate snapshot store
- no write-side rehydration code
- no command admission path modification
- no Compass Layer 2 implementation
- no measurement / benchmark suite

PR5 is expected to be docs-only.

---

## Deferred PR6 — Aggregate Snapshot Schema / Store

### Deferred Goal

Add durable aggregate snapshot storage when write-side aggregate replay depth or command admission latency justifies the risk and complexity.

### Deferred Scope

- add `aggregate_snapshots` migration
- add `AggregateSnapshot` model
- add `PostgresAggregateSnapshotStore`
- implement aggregate snapshot collision policy
- add schema and integration tests

### Deferral Rationale

Write-side aggregate snapshots are not only derived read-side compression.

They may affect command validation and accepted-history admission.

A stale or corrupted aggregate snapshot could cause the system to validate a candidate event against the wrong aggregate state.

Therefore, aggregate snapshot storage should wait until stronger trust gates, validation receipts, invalidation policy, and fallback policy exist.

---

## Deferred PR7 — Snapshot-Assisted Write-Side Rehydration

### Deferred Goal

Use trusted aggregate snapshots to accelerate write-side aggregate rehydration.

### Deferred Scope

- add snapshot-aware aggregate rehydration path
- fallback to full accepted-history replay when snapshot trust fails
- preserve idempotency behavior
- preserve Compass Layer 1 validation
- preserve append-time admission
- add write-side tests for snapshot fast path and fallback path

### Deferral Rationale

Write-side snapshot-assisted rehydration belongs on the command admission path.

That path is stricter than read-side projection resolution because an incorrect aggregate state can influence future accepted facts.

This work is deferred until the system has enough need and enough governance infrastructure to make aggregate snapshot trust safe.

---

## Stage 3.5D Closeout Direction

After PR5, Stage 3.5D may be closed by merging:

```text
base: main
compare: feat/stage3.5d-snapshot-trust-contract
```

Suggested Stage 3.5D closeout title:

```text
feat: complete Stage 3.5D snapshot trust contract
```

Stage 3.5D should close with:

```text
read-side projection snapshot schema complete
projection snapshot store complete
projection snapshot-assisted replay validator complete
projection snapshot-assisted state resolver complete
write-side aggregate snapshot implementation explicitly deferred
```

---

## Final Principle

```text
Projection snapshots support derived read-side resolution.
Aggregate snapshots would affect write-side admission.
These are not the same trust problem.
```

Stage 3.5D completes the read-side snapshot trust / replay-efficiency substrate and defers write-side aggregate snapshot implementation until the system has stronger runtime governance and a concrete performance need.
