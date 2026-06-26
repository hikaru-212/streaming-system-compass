# Projection Snapshot-Assisted State Resolver

[← Back to Implementation Notes](README.md)

## Purpose

This note defines the implementation boundary for:

```text
Stage 3.5D PR4.5 — Projection Snapshot-Assisted State Resolver
```

PR4.5 introduces the read-side resolver primitive that reconstructs projection state from an explicitly qualified projection snapshot plus accepted-history tail events.

The goal is:

```text
qualified projection snapshot
+ tail events after snapshot.source_global_position
→ resolved read-side projection state
```

without running full accepted-history replay on every normal resolver path.

---

## Scope Correction

PR4.5 is not the original high-risk write-side aggregate snapshot trust boundary.

The original Snapshot Trust Contract was motivated most strongly by write-side aggregate rehydration risk:

```text
invalid aggregate snapshot
→ false aggregate state
→ incorrect command validation
→ incorrect candidate event
→ possible accepted-history admission risk
```

PR4.5 operates on derived read-side projection state instead.

Its purpose is:

```text
projection replay efficiency
derived-state integrity evidence
snapshot-assisted read-state resolution
future Compass Layer 2 evidence substrate
```

It does not directly protect accepted-history admission.

It provides technical evidence that future Compass Layer 2 runtime policy may consume.

---

## Relationship to PR4

PR4 answers:

```text
Does snapshot-assisted replay match accepted-history authority replay?
```

PR4 is allowed to be expensive because it is a validator / audit boundary.

Conceptually:

```text
snapshot + tail replay
vs
full accepted-history replay
```

PR4.5 answers a different question:

```text
Given a qualified projection snapshot,
can the system resolve read-side projection state through snapshot + tail replay?
```

Conceptually:

```text
qualified snapshot
→ hydrate snapshot state
→ replay tail events
→ resolved projection state
```

PR4.5 should not recreate PR4 validation on every read.

---

## Core Rule

```text
accepted history = authority
projection snapshot = derived evidence
snapshot-assisted resolver = read-side fast-path reconstruction
Compass Layer 2 = future semantic outcome / runtime decision layer
```

The resolver must not treat a persisted snapshot row as self-authenticating truth.

It should consume an explicitly qualified snapshot selected by the caller or by a future eligibility / receipt mechanism.

The resolver may reject a snapshot through local compatibility checks, but those checks are not full semantic proof.

---

## Resolver Input Boundary

The preferred resolver API should require an explicit snapshot identity:

```python
def resolve_order(
    self,
    order_id: str,
    *,
    trusted_snapshot_id: UUID | None,
) -> ProjectionSnapshotAssistedResolutionResult:
    ...
```

or, more strictly:

```python
def resolve_order_from_snapshot(
    self,
    order_id: str,
    trusted_snapshot_id: UUID,
) -> ProjectionSnapshotAssistedResolutionResult:
    ...
```

The important rule is:

```text
latest persisted snapshot != latest trusted snapshot
```

Therefore PR4.5 should not silently choose `load_latest_snapshot(order_id)` as the trust decision.

The store may expose:

```python
load_snapshot(snapshot_id: UUID) -> ProjectionSnapshot | None
```

This is a storage retrieval helper only.

It does not decide whether the snapshot is trustworthy.

---

## Scope

PR4.5 introduces:

- `ProjectionSnapshotAssistedResolutionStatus`
- `ProjectionSnapshotAssistedResolutionResult`
- `ProjectionSnapshotAssistedStateResolver`
- exact snapshot-id based loading, if the store does not already support it
- local compatibility checks before snapshot hydration
- snapshot-to-`OrderState` hydration
- tail event loading after `snapshot.source_global_position`
- tail cursor contract checks
- canonical reducer tail replay
- structured unresolved statuses when the snapshot cannot be used
- unit tests for resolver behavior
- PostgreSQL integration tests using real snapshot store and tail event source

---

## Non-goals

PR4.5 does not implement:

- full accepted-history replay comparison in the normal resolver path
- PR4 authority validator replacement
- persisted validation receipt table
- validation receipt writer
- full runtime trust-gate lifecycle
- runtime decision policy
- automatic fallback policy
- automatic snapshot repair
- snapshot quarantine
- snapshot generation
- aggregate snapshots
- write-side aggregate rehydration
- command admission behavior
- Compass Layer 2 `SemanticOutcome`
- action safety behavior

If the resolver cannot use the provided snapshot, it should return a structured unresolved result.

Whether the caller falls back to full accepted-history replay belongs to a caller / future runtime policy boundary, not the resolver primitive.

---

## Local Compatibility Checks

The first PR4.5 implementation may perform checks such as:

```text
trusted_snapshot_id is present
snapshot row exists
snapshot.order_id == requested order_id
snapshot.source_global_position > 0
snapshot.source_event_sequence > 0
snapshot.state_version >= 0
snapshot.state_version <= snapshot.source_event_sequence
snapshot.state_version == snapshot.source_event_sequence  # current reducer compatibility
snapshot.state_status is supported by the current projection model
snapshot_schema_version is supported
reducer_version is compatible with the current reducer
```

These checks are local eligibility checks.

They can reject obviously unsafe or incompatible snapshots.

They cannot prove that the snapshot payload equals the state implied by accepted history.

That stronger authority-equivalence proof belongs to PR4 and future validation receipts.

---

## Tail Replay Boundary

The resolver must replay accepted tail events after the snapshot boundary:

```text
event.global_position > snapshot.source_global_position
```

The source event itself must not be replayed again, because the snapshot already claims to include accepted history through that boundary.

The resolver should load tail records through the projection event source and verify cursor advancement:

```text
current_position = snapshot.source_global_position

loop:
    records = tail_source.load_after(current_position, limit)
    if records is empty:
        stop
    every record.global_position must be greater than current_position
    replay records through canonical reducer
    current_position = last record.global_position
```

If the source returns a non-advancing record, the resolver should return a source-contract failure status rather than treating it as projection drift.

---

## Result Model Sketch

Suggested status values:

```python
class ProjectionSnapshotAssistedResolutionStatus(str, Enum):
    RESOLVED_FROM_SNAPSHOT = "RESOLVED_FROM_SNAPSHOT"
    MISSING_SNAPSHOT = "MISSING_SNAPSHOT"
    INVALID_SNAPSHOT_PRECONDITION = "INVALID_SNAPSHOT_PRECONDITION"
    INVALID_SNAPSHOT_COMPATIBILITY = "INVALID_SNAPSHOT_COMPATIBILITY"
    TAIL_EVENT_SOURCE_CONTRACT_VIOLATION = "TAIL_EVENT_SOURCE_CONTRACT_VIOLATION"
    TAIL_REPLAY_FAILED = "TAIL_REPLAY_FAILED"
```

Suggested result fields:

```text
order_id
status
resolved_state
snapshot_id
source_global_position
reason
```

Do not include `authority_state` in the PR4.5 result.

`authority_state` belongs to PR4 because PR4 performs the full accepted-history comparison.

---

## PostgreSQL Integration Proof

PR4.5 should include integration tests wiring:

```text
PostgresProjectionSnapshotStore
+ PostgresProjectionEventSource
+ ProjectionSnapshotAssistedStateResolver
```

It should not require `PostgresAcceptedHistoryEventSource` in the normal resolver path because PR4.5 does not perform full accepted-history replay comparison.

Integration tests should prove:

- persisted snapshot + no tail resolves state
- persisted snapshot + tail event resolves updated state
- tail replay starts after `snapshot.source_global_position`
- exact `snapshot_id` loading does not select the latest snapshot by accident
- resolver does not mutate accepted history
- resolver does not mutate projection state, checkpoint state, or snapshot rows

---

## Relationship to Compass Layer 2

PR4.5 is not Compass Layer 2.

It produces read-side technical evidence that Compass Layer 2 may later consume.

A useful boundary is:

```text
Stage 3.5D PR4 / PR4.5
= evidence mechanisms

Stage 4 Compass Layer 2
= semantic outcome + runtime decision policy
```

PR4.5 may help future Layer 2 answer questions such as:

```text
Can this read-side state be explained by accepted-history lineage?
Was this state resolved from qualified snapshot evidence?
Did tail replay preserve the source contract?
Should downstream runtime policy treat this state as usable, degraded, uncertain, or blocked?
```

The first three are PR4.5 evidence questions.

The last one is a future Layer 2 policy question.

---

## Implementation Sequence

Recommended PR4.5 commits:

```text
Commit 1 — docs: define projection snapshot-assisted state resolver boundary
Commit 2 — docs: align snapshot runtime eligibility ADR with Stage 3.5D scope
Commit 3 — storage: load projection snapshot by snapshot id
Commit 4 — resolution: define projection snapshot-assisted resolver result contract
Commit 5 — resolution: implement projection snapshot-assisted state resolver
Commit 6 — tests: cover projection snapshot-assisted resolver with PostgreSQL stores
Commit 7 — docs: align projection snapshot-assisted state resolver closeout
```

---

## Final Principle

```text
Read-side snapshot resolution is not accepted-history admission trust.
It is derived-state reconstruction evidence.
```

The resolver may make read-side state faster and more explainable.

It must remain subordinate to accepted history and to future runtime policy.
