# Projection Snapshot-Assisted Replay Validator

[← Back to Stage 3.5D Notes](README.md)

## Purpose

This note defines the implementation boundary for **Stage 3.5D PR4 — Projection Snapshot-Assisted Replay Validator**.

Stage 3.5D PR1 defined the general Snapshot Trust Contract.

Stage 3.5D PR2 introduced the durable `projection_snapshots` schema.

Stage 3.5D PR3 introduced `PostgresProjectionSnapshotStore`, making projection snapshots persistable and loadable through a Python storage boundary.

PR4 introduces the first validator that checks whether a projection snapshot-assisted replay path reconstructs the same projection state implied by accepted history.

The goal is not to make snapshots authoritative.

The goal is to verify whether:

```text
snapshot state
+ tail events after snapshot boundary
= accepted-history replay result
```

The accepted history remains the authority.

---

## Core Rule

```text
accepted history = authority
projection snapshot = derived compression
snapshot-assisted replay = fast path candidate
authority replay = correctness baseline
```

A projection snapshot may reduce replay work only if the system can prove that the snapshot-assisted replay path reconstructs the same state as accepted-history replay.

PR4 therefore validates snapshot-assisted replay behavior.

It does not replace accepted-history replay as the authority path.

---

## Scope

PR4 introduces:

- `ProjectionSnapshotReplayValidationStatus`
- `ProjectionSnapshotReplayValidationResult`
- `ProjectionSnapshotReplayValidator`
- snapshot-to-projection-state hydration boundary
- authority replay through the canonical projection reducer
- tail replay after `snapshot.source_global_position`
- tail pagination across multiple pages
- tail event source cursor contract checks
- comparison against accepted-history authority replay
- `PostgresAcceptedHistoryEventSource` as the read-only accepted-history adapter
- PostgreSQL-backed adapter tests for accepted-history loading
- PostgreSQL integration tests wiring:
  - `PostgresProjectionSnapshotStore`
  - `PostgresAcceptedHistoryEventSource`
  - `PostgresProjectionEventSource`
  - `ProjectionSnapshotReplayValidator`

The validator uses existing Stage 3.5C / Stage 3.5D pieces where possible:

```text
PostgresProjectionSnapshotStore
PostgresProjectionEventSource
canonical projection reducer
accepted-history replay through PostgresAcceptedHistoryEventSource
```

---

## Non-goals

PR4 does not implement:

- snapshot generation
- canonical payload hash verification
- production snapshot scheduling
- reducer version compatibility matrix
- snapshot schema migration policy
- aggregate snapshots
- aggregate snapshot trust extension
- write-side snapshot-assisted rehydration
- runtime decision policy
- automatic fallback
- automatic repair
- snapshot quarantine
- Compass Layer 2 governance
- `SemanticOutcome`
- action safety behavior
- production hot-path snapshot resolver

PR4 produces validation evidence.

It does not decide operational action.

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

If snapshot-assisted replay disagrees with the authority path, the snapshot-assisted path is invalid evidence.

---

## Snapshot-Assisted Path

The snapshot-assisted path starts from the latest loaded projection snapshot.

Conceptually:

```text
latest projection snapshot for order
→ hydrate snapshot state
→ load tail events after snapshot.source_global_position
→ replay tail events through canonical reducer
→ snapshot-assisted projection state
```

The resulting state is a candidate reconstruction.

It must be compared against authority replay before it can be trusted.

---

## Accepted-History Adapter Boundary

PR4 introduces `PostgresAcceptedHistoryEventSource`.

It is a narrow read-only adapter that satisfies the validator's accepted-history dependency:

```text
order_id
→ accepted OrderEvent list
→ ordered by aggregate-local sequence
```

It exists so the validator can read accepted history without depending directly on write-side append/idempotency responsibilities.

It does not:

```text
append accepted events
mutate accepted history
manage idempotency
decide admission
own commit / rollback
write projection state
write snapshots
```

This preserves the separation between accepted-history storage and read-side validation.

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

Therefore PR4 treats `source_global_position` as the replay boundary.

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

## Tail Pagination Boundary

PR4 loads tail events with pagination.

Conceptually:

```text
current_position = snapshot.source_global_position

loop:
    batch = tail_source.load_after(current_position, limit)
    if batch is empty:
        stop
    verify every returned global_position advances
    append batch
    current_position = last returned global_position
```

The validator rejects tail event source cursor contract violations:

```text
record.global_position <= previous_position
→ TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
```

This covers non-advancing cursor behavior and out-of-order batches.

It does not yet reject every global-position gap.

A future hole registry / aborted-position model is needed before gap detection can distinguish unexplained gaps from valid aborted positions.

---

## Snapshot State Hydration

PR4 converts `ProjectionSnapshot` into the projection state representation expected by the reducer path.

At the current order projection level, the snapshot contains:

```text
order_id
state_status
total_amount
paid_amount
state_version
```

Those fields hydrate the same semantic state shape used by the projection reducer.

This hydration step remains simple.

It does not perform hash verification, schema migration, reducer compatibility resolution, or automatic repair.

Those belong to future stages.

---

## Trust Preconditions

PR4 performs minimal structural and current-reducer compatibility checks before attempting snapshot-assisted replay.

Examples:

```text
accepted history exists
snapshot exists
snapshot.order_id matches requested order_id
snapshot.source_global_position > 0
snapshot.source_event_sequence > 0
snapshot.source_event_sequence <= authority_max_sequence
snapshot.state_version >= 0
snapshot.state_version <= snapshot.source_event_sequence
snapshot.state_version == snapshot.source_event_sequence under the current reducer
snapshot.state_status is supported by the current projection state model
```

The PR2 database schema intentionally allows:

```text
snapshot.state_version <= snapshot.source_event_sequence
```

This preserves future reducer flexibility.

However, the current order projection reducer treats `OrderState.version` as the last accepted event sequence reflected by the state.

Therefore, PR4 enforces the current reducer compatibility rule:

```text
snapshot.state_version == snapshot.source_event_sequence
```

This is a validator-level compatibility check, not a permanent database constraint.

Future reducer versions may relax this rule through an explicit reducer compatibility policy.

---

## Result Model

PR4 returns a structured validation result.

Status vocabulary:

```text
MATCH
MISSING_SNAPSHOT
NO_ACCEPTED_HISTORY_FOR_ORDER
INVALID_SNAPSHOT_BOUNDARY
TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
SNAPSHOT_ASSISTED_DRIFT
```

Result shape:

```python
@dataclass(frozen=True)
class ProjectionSnapshotReplayValidationResult:
    status: ProjectionSnapshotReplayValidationStatus
    order_id: str
    snapshot_id: UUID | None = None
    source_global_position: int | None = None
    snapshot_assisted_state: OrderState | None = None
    authority_state: OrderState | None = None
    reason: str | None = None
```

The result preserves enough evidence to explain why validation matched or failed.

---

## Expected Behaviors

PR4 validates:

```text
no accepted history for requested order
→ NO_ACCEPTED_HISTORY_FOR_ORDER

accepted history exists, but snapshot is missing
→ MISSING_SNAPSHOT

valid snapshot + no tail + matches authority state
→ MATCH

valid snapshot + tail replay + matches authority state
→ MATCH

snapshot boundary is structurally invalid
→ INVALID_SNAPSHOT_BOUNDARY

snapshot state_version is behind source_event_sequence under the current reducer
→ INVALID_SNAPSHOT_BOUNDARY

snapshot source_event_sequence is ahead of accepted history
→ INVALID_SNAPSHOT_BOUNDARY

tail events span multiple pages
→ validator continues loading until the tail event source returns no more records

tail pagination does not advance global_position
→ TAIL_EVENT_SOURCE_CONTRACT_VIOLATION

tail batch returns out-of-order global_position
→ TAIL_EVENT_SOURCE_CONTRACT_VIOLATION

tail source contract is valid, but snapshot-assisted state differs from authority replay
→ SNAPSHOT_ASSISTED_DRIFT

tail replay violates reducer/domain transition rules
→ SNAPSHOT_ASSISTED_DRIFT
```

The validator does not mutate accepted history, projection state, checkpoint progress, or snapshot rows.

---

## Completed Tests

PR4 includes tests for:

- missing snapshot returns `MISSING_SNAPSHOT`
- no accepted history for requested order returns `NO_ACCEPTED_HISTORY_FOR_ORDER`
- snapshot with no tail events matches authority replay
- snapshot with tail events matches authority replay after tail replay
- snapshot-assisted drift is detected
- drift from snapshot payload disagreeing with claimed source boundary
- invalid snapshot boundary is rejected
- `state_version < source_event_sequence` is rejected for current reducer compatibility
- snapshot ahead of accepted history is rejected
- tail replay starts after `snapshot.source_global_position`
- snapshot source event is not double-applied
- tail events are loaded across pages
- non-advancing tail pagination is rejected as `TAIL_EVENT_SOURCE_CONTRACT_VIOLATION`
- out-of-order tail pagination is rejected as `TAIL_EVENT_SOURCE_CONTRACT_VIOLATION`
- tail replay domain failure returns `SNAPSHOT_ASSISTED_DRIFT`
- result includes useful evidence fields
- `PostgresAcceptedHistoryEventSource` loads accepted events from PostgreSQL
- validator works with PostgreSQL-backed snapshot store, accepted-history source, and tail event source

## Boundary Constraints Preserved

The implementation preserves these read-side validation boundaries:

- it does not mutate accepted history
- it does not mutate projection state
- it does not advance checkpoint progress
- it does not write snapshots
- it does not decide runtime repair, fallback, quarantine, or admission policy

---

## Future Semantic Refinements

PR4 intentionally uses a small status vocabulary.

Future Stage 4 / Layer 2 / trust-diagnosis refinements may split coarse statuses into more precise machine-readable diagnoses:

```text
INVALID_SNAPSHOT_LINEAGE
SNAPSHOT_PAYLOAD_HASH_MISMATCH
UNSUPPORTED_REDUCER_VERSION
UNSUPPORTED_SNAPSHOT_SCHEMA_VERSION
SNAPSHOT_STATE_DOMAIN_VIOLATION
UNEXPLAINED_GLOBAL_POSITION_GAP
TAIL_REPLAY_DOMAIN_FAILURE
ACCEPTED_HISTORY_CONTRACT_VIOLATION
```

These are not implemented in PR4 because they require additional evidence models such as:

```text
accepted event identity / lineage records
canonical snapshot payload hash policy
reducer compatibility registry
snapshot schema compatibility policy
projection-domain invariant validator
aborted-position / hole registry
accepted-history integrity validation
```

PR4 only splits out `TAIL_EVENT_SOURCE_CONTRACT_VIOLATION` because that contract is already concrete and testable:

```text
tail event source must return strictly advancing global_position values
```

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

PR4 depends on PR3 storage behavior without moving trust decisions into the store.

---

## Production Assembly Boundary

PR4 proves PostgreSQL-backed assembly through integration tests.

The integration path wires:

```text
PostgresProjectionSnapshotStore
+ PostgresAcceptedHistoryEventSource
+ PostgresProjectionEventSource
+ ProjectionSnapshotReplayValidator
```

However, PR4 does not introduce a production hot-path factory or resolver.

That is intentional.

This validator compares snapshot-assisted replay against full accepted-history replay, so it is an audit / validation path rather than a throughput optimization path.

A later resolver may use trusted snapshot evidence for actual replay acceleration.


## Relationship to PR4.5

PR4 is not the hot-path snapshot resolver.

PR4 performs validation by comparing snapshot-assisted replay against full accepted-history replay.

This produces evidence, but it is not cheaper than full replay.

A follow-up PR should introduce a separate resolver:

```text
PR4.5 — Projection Snapshot-Assisted State Resolver
```

That resolver should answer:

```text
Given a trusted snapshot, can the system reconstruct projection state using snapshot + tail replay without full accepted-history replay?
```

The relationship is:

```text
PR4
= prove snapshot-assisted replay can match authority replay

PR4.5
= use trusted snapshot-assisted replay for efficient state resolution
```

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
projection snapshot-assisted replay can be checked against accepted-history replay
```

The key invariant remains:

```text
accepted history is authority
```

Snapshot-assisted replay is useful only when it reconstructs the same projection state implied by accepted history.

PR4 produces validation evidence.

A later resolver must consume trusted snapshot evidence to provide actual replay acceleration.
