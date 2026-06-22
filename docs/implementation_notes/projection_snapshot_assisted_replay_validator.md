# Projection Snapshot-Assisted Replay Validator

[← Back to Implementation Notes](README.md)

## Purpose

This note defines the implementation boundary for **Stage 3.5D PR4 — Projection Snapshot-Assisted Replay Validator**.

Stage 3.5D PR1 defined the general Snapshot Trust Contract.

Stage 3.5D PR2 introduced the durable `projection_snapshots` schema.

Stage 3.5D PR3 introduced `PostgresProjectionSnapshotStore`, making projection snapshots persistable and loadable through a Python storage boundary.

PR4 introduces the first validator that checks whether a projection snapshot can safely participate in a replay fast path.

The goal is not to make snapshots authoritative.

The goal is to verify whether a snapshot-assisted replay path reconstructs the same projection state implied by accepted history.

---

## Core Rule

```text
accepted history = authority
projection snapshot = derived compression
snapshot-assisted replay = fast path candidate
authority replay = correctness baseline
```

A projection snapshot may reduce replay work only if the system can prove that:

```text
snapshot state
+ tail events after snapshot boundary
= accepted-history replay result
```

PR4 therefore validates snapshot-assisted replay behavior.

It does not replace accepted-history replay as the authority path.

---

## Scope

PR4 introduces:

- projection snapshot-assisted replay validator
- snapshot-assisted replay result model
- snapshot-assisted replay status / reason vocabulary
- snapshot-to-projection-state hydration boundary
- tail replay after `source_global_position`
- comparison against accepted-history authority replay
- tests for match, missing snapshot, invalid boundary, and drift cases

The validator should use existing Stage 3.5C / Stage 3.5D pieces where possible:

```text
PostgresProjectionSnapshotStore
PostgresProjectionEventSource
canonical projection reducer
accepted-history replay / durable replay validation logic
```

---

## Non-goals

PR4 does not implement:

- snapshot generation
- canonical payload hash computation
- production snapshot scheduling
- aggregate snapshots
- aggregate snapshot trust extension
- write-side snapshot-assisted rehydration
- runtime decision policy
- automatic repair
- snapshot quarantine
- Compass Layer 2 governance
- `SemanticOutcome`
- action safety behavior

PR4 should produce validation evidence.

It should not decide operational action.

---

## Authority Path

The authority path is accepted-history replay.

Conceptually:

```text
accepted events for order
→ canonical projection reducer
→ authority projection state
```

This path remains the correctness baseline.

If snapshot-assisted replay disagrees with the authority path, the snapshot-assisted path is wrong.

---

## Snapshot-Assisted Path

The snapshot-assisted path starts from the latest loaded projection snapshot.

Conceptually:

```text
latest projection snapshot for order
→ hydrate snapshot state
→ load accepted events after snapshot.source_global_position
→ replay tail events through canonical reducer
→ snapshot-assisted projection state
```

The resulting state is a candidate reconstruction.

It must be compared against authority replay before it can be trusted.

---

## Latest Snapshot Boundary

PR4 relies on the PR3 store behavior:

```sql
ORDER BY source_global_position DESC
LIMIT 1
```

This loads the latest snapshot by accepted-history progress, not by row creation time.

`created_at` answers:

```text
When was this derived snapshot row written?
```

`source_global_position` answers:

```text
How far into accepted history was this snapshot computed?
```

Therefore PR4 should treat `source_global_position` as the replay boundary.

---

## Tail Replay Boundary

Tail replay must load accepted events after the snapshot boundary:

```text
event.global_position > snapshot.source_global_position
```

The snapshot state already claims to include accepted history through:

```text
snapshot.source_global_position
```

Therefore replaying from the snapshot should not re-apply the source event itself.

This avoids double-counting the event represented by the snapshot boundary.

---

## Snapshot State Hydration

PR4 needs a small boundary that converts `ProjectionSnapshot` into the projection state representation expected by the reducer path.

At the current order projection level, the snapshot contains:

```text
order_id
state_status
total_amount
paid_amount
state_version
```

Those fields should hydrate the same semantic state shape used by the projection reducer.

This hydration step should remain simple.

It should not perform trust validation, hash verification, schema migration, reducer compatibility resolution, or automatic repair.

Those belong to future stages.

---

## Trust Preconditions

PR4 may perform minimal structural checks before attempting snapshot-assisted replay.

Examples:

```text
snapshot exists
snapshot.order_id matches requested order_id
snapshot.source_global_position > 0
snapshot.source_event_sequence > 0
snapshot.state_version <= snapshot.source_event_sequence
snapshot.state_status is supported by the current projection state model
```

The PR2 database schema intentionally allows:

```text
snapshot.state_version <= snapshot.source_event_sequence
```

This preserves future reducer flexibility.

However, the current order projection reducer treats `OrderState.version` as the last accepted event sequence reflected by the state.

Therefore, PR4 also enforces the current reducer compatibility rule:

```text
snapshot.state_version == snapshot.source_event_sequence
```

This is a validator-level compatibility check, not a permanent database constraint.

Future reducer versions may relax this rule through an explicit reducer compatibility policy.

However, PR4 should not over-expand into full trust governance.

The deeper questions remain future work:

```text
Does payload_hash match canonical snapshot payload?
Is reducer_version compatible beyond the current reducer assumption?
Is snapshot_schema_version supported?
Should an invalid snapshot be quarantined?
Should the runtime fall back automatically?
```

PR4 may expose failure statuses for these future boundaries without implementing the full policy.

---

## Result Model

PR4 should return a structured validation result.

A possible status vocabulary:

```text
MATCH
MISSING_SNAPSHOT
NO_ACCEPTED_HISTORY_FOR_ORDER
INVALID_SNAPSHOT_BOUNDARY
SNAPSHOT_ASSISTED_DRIFT
```

A possible result shape:

```python
@dataclass(frozen=True)
class ProjectionSnapshotReplayValidationResult:
    status: ProjectionSnapshotReplayValidationStatus
    order_id: str
    snapshot_id: UUID | None
    source_global_position: int | None
    snapshot_assisted_state: OrderState | None
    authority_state: OrderState | None
    reason: str | None = None
```

The exact field names may change during implementation, but the result should preserve enough evidence to explain why validation matched or failed.

---

## Expected Behaviors

PR4 should validate:

```text
missing snapshot
→ MISSING_SNAPSHOT

no accepted history for requested order
→ NO_ACCEPTED_HISTORY_FOR_ORDER

valid snapshot + no tail + matches authority state
→ MATCH

valid snapshot + tail replay + matches authority state
→ MATCH

snapshot-assisted state differs from authority replay
→ SNAPSHOT_ASSISTED_DRIFT

snapshot boundary is structurally invalid
→ INVALID_SNAPSHOT_BOUNDARY

snapshot state_version is behind source_event_sequence under the current reducer
→ INVALID_SNAPSHOT_BOUNDARY

tail events span multiple pages
→ validator continues loading until the tail event source returns no more records

tail pagination does not advance global_position
→ SNAPSHOT_ASSISTED_DRIFT
```

The validator should not mutate accepted history, projection state, checkpoint progress, or snapshot rows.

---

## Expected Tests

PR4 should include tests for:

* missing snapshot returns `MISSING_SNAPSHOT`
* no accepted history for requested order returns `NO_ACCEPTED_HISTORY_FOR_ORDER`
* snapshot with no tail events matches authority replay
* snapshot with tail events matches authority replay after tail replay
* snapshot-assisted drift is detected
* invalid snapshot boundary is rejected
* `state_version < source_event_sequence` is rejected for current reducer compatibility
* tail replay starts after `snapshot.source_global_position`
* snapshot source event is not double-applied
* tail events are loaded across pages
* non-advancing tail pagination is rejected
* validator does not mutate accepted history
* validator does not mutate projection state
* validator does not advance checkpoints
* validator does not write snapshots
* result includes useful evidence fields

---

## Relationship to PR3

PR3 makes projection snapshots persistable and loadable.

PR4 decides whether loaded snapshot evidence can reconstruct the same state as accepted-history replay.

```text
PR3
= storage boundary

PR4
= replay validation boundary
```

PR4 should depend on PR3 storage behavior without moving trust decisions into the store.

---

## Relationship to PR5

PR5 should extend the Snapshot Trust Contract toward aggregate snapshots.

Projection snapshots are read-side derived artifacts.

Aggregate snapshots are stricter because they may later participate in write-side rehydration before command admission.

PR4 should therefore stay focused on projection snapshots only.

It should not introduce aggregate snapshot semantics.

---

## Summary

PR4 moves Stage 3.5D from:

```text
projection snapshot can be stored
```

to:

```text
projection snapshot can be checked as a replay fast-path candidate
```

The key invariant remains:

```text
accepted history is authority
```

Snapshot-assisted replay is useful only when it reconstructs the same projection state implied by accepted history.
