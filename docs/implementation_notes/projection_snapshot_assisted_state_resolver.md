# Projection Snapshot-Assisted State Resolver

[← Back to Implementation Notes](README.md)

## Purpose

This note records the closeout boundary for:

```text
Stage 3.5D PR4.5 — Projection Snapshot-Assisted State Resolver
```

PR4.5 introduces a read-side resolver primitive that reconstructs projection state from an explicitly qualified projection snapshot plus accepted-history tail events.

The implemented goal is:

```text
externally qualified projection snapshot
+ accepted-history tail events after snapshot.source_global_position
→ resolved read-side projection state
```

The resolver is designed to avoid full accepted-history replay on the normal resolver path.

It is a read-side resolution primitive, not a trust producer, not a fallback orchestrator, and not Compass Layer 2.

---

## Closeout Summary

PR4.5 completes the following Stage 3.5D boundary:

```text
explicit snapshot identity
+ local compatibility checks
+ snapshot hydration
+ tail replay after snapshot.source_global_position
→ resolved derived projection state
```

PR4.5 proves:

- the resolver result contract
- exact snapshot lookup by `snapshot_id`
- snapshot hydration into `OrderState`
- tail replay strictly after the snapshot source boundary
- tail source cursor contract protection
- no partial state exposure on unresolved results
- PostgreSQL wiring with `PostgresProjectionSnapshotStore`
- PostgreSQL wiring with `PostgresProjectionEventSource`
- a current expensive trust path where PR4 `MATCH` can supply `trusted_snapshot_id` for PR4.5

PR4.5 intentionally leaves trust persistence, fallback orchestration, diagnostic traces, and runtime policy to later stages.

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

It produces technical evidence that future Compass Layer 2 runtime policy may consume.

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
Given an externally qualified projection snapshot,
can the system resolve read-side projection state through snapshot + tail replay?
```

Conceptually:

```text
qualified snapshot
→ hydrate snapshot state
→ replay tail events
→ resolved projection state
```

PR4.5 should not recreate PR4 validation on every read as part of the resolver primitive.

---

## Trusted Snapshot ID Boundary

The resolver requires an externally supplied `trusted_snapshot_id`.

The resolver consumes trust; it does not produce trust.

The important rule is:

```text
latest persisted snapshot != latest trusted snapshot
```

Therefore PR4.5 must not silently choose `load_latest_snapshot(order_id)` as the trust decision.

The snapshot store may expose:

```python
load_snapshot(snapshot_id: UUID) -> ProjectionSnapshot | None
```

This is a storage retrieval helper only.

It does not decide whether the snapshot is trustworthy.

### Current Strongest Trust Source

In the current system, the strongest available source of `trusted_snapshot_id` is a successful PR4 replay validation result:

```text
PR4 validator returns MATCH
→ validation_result.snapshot_id
→ trusted_snapshot_id
→ PR4.5 resolver
```

This proves that a `trusted_snapshot_id` can exist in the current system.

However, this trust is currently ephemeral because validation receipts are not yet persisted.

### Cost Boundary

If PR4 validation is executed before every resolver call, the system pays additional authority-validation cost before using the resolver:

```text
full accepted-history replay
+ snapshot-assisted validation replay
+ comparison
+ resolver snapshot + tail replay
```

This path is useful as a correctness demonstration, but it is not the final optimized runtime path.

The intended future path is:

```text
PR4 validator MATCH
→ persist validation receipt
→ SnapshotTrustGate / SnapshotFastPathSelector reads receipt
→ returns trusted_snapshot_id
→ PR4.5 resolver consumes trusted_snapshot_id
```

Durable receipt-backed trust selection is deferred to Stage 4.

---

## Core Rule

```text
accepted history = authority
projection snapshot = derived evidence
snapshot-assisted resolver = read-side reconstruction primitive
Compass Layer 2 = future semantic outcome / runtime decision layer
```

The resolver must not treat a persisted snapshot row as self-authenticating truth.

It should consume an explicitly qualified snapshot selected by the caller or by a future eligibility / receipt mechanism.

The resolver may reject a snapshot through local compatibility checks, but those checks are not full semantic proof.

---

## Resolver Input Boundary

The PR4.5 resolver API requires an explicit snapshot identity:

```python
def resolve_order(
    self,
    order_id: str,
    *,
    trusted_snapshot_id: UUID | None,
) -> ProjectionSnapshotAssistedResolutionResult:
    ...
```

The `trusted_snapshot_id` name means:

```text
an externally qualified snapshot id supplied by the caller
```

It does not mean:

```text
the resolver itself proved the snapshot trustworthy
```

If no `trusted_snapshot_id` is available, the resolver should return a structured unresolved result rather than selecting a snapshot by itself.

---

## Implemented Scope

PR4.5 introduces or completes:

- `ProjectionSnapshotAssistedResolutionStatus`
- `ProjectionSnapshotAssistedResolutionResult`
- `ProjectionSnapshotAssistedStateResolver`
- exact snapshot-id based loading through `load_snapshot(snapshot_id)`
- local compatibility checks before snapshot hydration
- snapshot-to-`OrderState` hydration
- tail event loading after `snapshot.source_global_position`
- tail cursor contract checks
- canonical reducer tail replay
- structured unresolved statuses when the snapshot cannot be used
- unit tests for resolver behavior
- PostgreSQL integration tests using real snapshot store and tail event source
- integration proof that PR4 `MATCH` can supply `trusted_snapshot_id` for PR4.5

---

## Non-goals

PR4.5 does not implement:

- full accepted-history replay comparison in the normal resolver path
- PR4 authority validator replacement
- persisted validation receipt table
- validation receipt writer
- `SnapshotTrustGate`
- `ValidationReceiptStore`
- `SnapshotFastPathSelector`
- `RuntimeStateResolutionService`
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
- `DecisionReceipt`
- `DiagnosticTrace`
- `RuntimeDecisionPolicy`
- `StrategySelector`
- action safety behavior

If the resolver cannot use the provided snapshot, it should return a structured unresolved result.

Whether the caller falls back to full accepted-history replay belongs to a caller / future runtime policy boundary, not the resolver primitive.

---

## Local Compatibility Checks

PR4.5 performs local eligibility checks such as:

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

These checks can reject obviously unsafe or incompatible snapshots.

They cannot prove that the snapshot payload equals the state implied by accepted history.

That stronger authority-equivalence proof belongs to PR4 and future validation receipts.

---

## Tail Replay Boundary

The resolver replays accepted tail events after the snapshot boundary:

```text
event.global_position > snapshot.source_global_position
```

The source event itself must not be replayed again, because the snapshot already claims to include accepted history through that boundary.

The resolver loads tail records through the projection event source and verifies cursor advancement:

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

If the source returns a non-advancing or out-of-order record, the resolver returns a source-contract failure status rather than treating it as projection drift.

---

## Result Model

Implemented status values:

```python
class ProjectionSnapshotAssistedResolutionStatus(str, Enum):
    RESOLVED_FROM_SNAPSHOT = "RESOLVED_FROM_SNAPSHOT"
    MISSING_SNAPSHOT = "MISSING_SNAPSHOT"
    INVALID_SNAPSHOT_PRECONDITION = "INVALID_SNAPSHOT_PRECONDITION"
    INVALID_SNAPSHOT_COMPATIBILITY = "INVALID_SNAPSHOT_COMPATIBILITY"
    TAIL_EVENT_SOURCE_CONTRACT_VIOLATION = "TAIL_EVENT_SOURCE_CONTRACT_VIOLATION"
    TAIL_REPLAY_FAILED = "TAIL_REPLAY_FAILED"
```

Primary result fields:

```text
order_id
status
resolved_state
snapshot_id
source_global_position
reason
```

The result intentionally does not include `authority_state`.

`authority_state` belongs to PR4 because PR4 performs the full accepted-history comparison.

---

## Partial State Boundary

PR4.5 follows this rule:

```text
Partial progress belongs to observability.
Resolved state belongs to runtime correctness.
```

Therefore:

```text
RESOLVED_FROM_SNAPSHOT
→ resolved_state exists

Any unresolved status
→ resolved_state is None
```

The resolver must not expose partially hydrated or partially replayed state as the current runtime state.

Future diagnostic traces may record partial progress, such as:

```text
snapshot_id
source_global_position
latest_global_position_attempted
last_replayed_global_position
failure_stage
failure_reason
fallback_used
```

Those belong to Stage 4 diagnostic trace / observability work, not to the PR4.5 primary result.

---

## PostgreSQL Integration Proof

PR4.5 includes integration tests wiring:

```text
PostgresProjectionSnapshotStore
+ PostgresProjectionEventSource
+ ProjectionSnapshotAssistedStateResolver
```

The normal resolver path does not require `PostgresAcceptedHistoryEventSource` because PR4.5 does not perform full accepted-history replay comparison.

Integration tests prove:

- persisted snapshot + no tail resolves state
- persisted snapshot + real PostgreSQL tail event resolves updated state
- tail replay starts strictly after `snapshot.source_global_position`
- PR4 `MATCH` can supply `trusted_snapshot_id` for PR4.5
- resolver does not mutate accepted history
- resolver does not mutate projection state, checkpoint state, or snapshot rows

The PR4-to-PR4.5 integration proof is intentionally correctness-oriented and may be expensive.

It demonstrates that current trust can be produced, not that every runtime request should recompute trust through PR4.

---

## Future Measurement Boundary

PR4.5 does not attempt to prove that snapshot-assisted resolution is always faster than full replay.

The current integration path can demonstrate:

```text
PR4 MATCH
→ trusted_snapshot_id
→ PR4.5 resolver
```

However, this path is correctness-oriented and may be expensive because PR4 validation performs authority replay.

Future stages should measure both write-side and read-side costs, including:

- `PRE_transaction + OCC`
- `IN_transaction + pessimistic locking`
- full authority replay
- PR4 validation
- PR4.5 resolver
- receipt-backed resolver
- tail replay length
- lock wait time
- validation elapsed time
- transaction elapsed time

Cost evidence should be recorded in Stage 4 `DecisionReceipt` / runtime evidence records before being used by `RuntimeDecisionPolicy` or `StrategySelector`.

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

## Closeout Commit Sequence

PR4.5 was completed through the following implementation sequence:

```text
Commit 1 — docs: define projection snapshot-assisted state resolver boundary
Commit 2 — docs: align snapshot runtime eligibility with Stage 3.5D scope
Commit 3 — storage: load projection snapshot by snapshot id
Commit 4 — resolution: add projection snapshot-assisted result contract
Commit 5 — resolution: implement projection snapshot-assisted state resolver
Commit 6 — integration: wire projection snapshot-assisted resolver
Commit 7 — docs: close projection snapshot-assisted resolver boundary
```

Exact commit numbers may differ from local history, but the closeout boundary is:

```text
resolver primitive complete
PostgreSQL wiring complete
trust source / cost boundary documented
future receipt / policy / diagnostic work deferred
```

---

## Final Principle

```text
Read-side snapshot resolution is not accepted-history admission trust.
It is derived-state reconstruction evidence.
```

The resolver may make read-side state faster and more explainable.

It must remain subordinate to accepted history and to future runtime policy.
