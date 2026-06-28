# Snapshot Trust Contract

[← Back to Architecture](README.md)

## Purpose

This architecture note explains how snapshot support fits into Streaming System + Compass.

Snapshot support is introduced in Stage 3.5D as a replay-efficiency mechanism.

However, snapshot is not only a performance optimization.

Snapshot creates a trust boundary because it allows runtime reconstruction to start from derived state rather than from the beginning of accepted history.

---

## Current Baseline After Stage 3.5D PR4

Before Stage 3.5D, the system already had:

```text
order_events
= durable accepted history

projection_states
= durable derived read-side state

projection_checkpoints
= durable projection worker progress

DurableReplayValidator
= accepted-history replay compared with persisted projection state
```

Stage 3.5D has now added the first projection snapshot trust substrate:

```text
PR1   — Snapshot Trust Contract Boundary
PR1.5 — CI Stage Branch Checks
PR2   — Projection Snapshot Schema Baseline
PR3   — PostgresProjectionSnapshotStore
PR4   — Projection Snapshot-Assisted Replay Validator
```

This means the system can now persist projection snapshots and validate whether snapshot-assisted replay reconstructs the same state as accepted-history replay.

Stage 3.5D still does not make snapshots authoritative.

It only makes them traceable, checkable replay fast-path candidates.

---

## Architectural Principle

```text
accepted history is authority
snapshot is acceleration
```

The snapshot path must be optional.

If a snapshot is missing, invalid, stale, unsupported, suspicious, or generated non-deterministically, the system must be able to fall back to accepted-history replay.

PR4 validates this relationship for projection snapshots by comparing:

```text
snapshot state
+ tail replay after snapshot boundary
```

against:

```text
accepted-history replay result
```

---

## Runtime Paths

### Authority Path

```text
accepted history
→ full replay
→ reconstructed state
```

This path is authoritative.

It is used for:

- audit
- rebuild
- suspicious derived state
- snapshot trust failure
- reducer / aggregate logic upgrade
- high-risk verification
- later Layer 2 evidence generation

### Fast-Path Candidate

```text
snapshot
→ structural / compatibility checks
→ tail replay
→ reconstructed state
→ compare against authority path when validating trust
```

This path is performance-oriented, but it may be used only when trust evidence qualifies the snapshot.

PR4 is a validation path, not the final hot-path resolver.

It proves whether snapshot-assisted replay can match the authority path.

A later resolver may consume trusted snapshot evidence to reconstruct state without full accepted-history replay.

---

## Responsibility Separation

Snapshot architecture separates four responsibilities:

```text
SnapshotBuilder
= constructs a snapshot from trusted reconstruction result

SnapshotStore
= persists and loads snapshots

SnapshotTrustValidator / ReplayValidator
= checks whether existing snapshot evidence can reconstruct authority-equivalent state

SnapshotGenerationPolicy
= decides when a new snapshot should be produced
```

The validator does not implicitly write snapshots.

The store does not decide generation timing.

The generation policy does not decide trust.

This keeps snapshot optimization from becoming an implicit mutation side effect.

---

## Snapshot Evidence Model

A snapshot should include:

```text
snapshot identity
snapshot kind
stream / order identity
accepted-history source event boundary
accepted-history source sequence
accepted-history source global position
state payload
state version
schema version
logic version
payload hash
metadata
creation time
creator
```

The `snapshot_kind` separates different uses:

```text
PROJECTION
AGGREGATE
```

The first implemented target is projection snapshot support.

Aggregate snapshot support remains a later extension for write-side rehydration.

---

## Projection Snapshot Path

Projection snapshot-assisted replay is used to validate and later accelerate read-side replay / rebuild / validation.

```text
projection snapshot
→ verify minimal boundary / reducer compatibility
→ load tail events after source_global_position
→ replay tail through canonical reducer
→ reconstructed projection state
→ compare against accepted-history authority replay
```

PR4 implements this comparison as a read-side validator.

It also distinguishes tail event source cursor contract violations from ordinary snapshot-assisted drift:

```text
TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
≠
SNAPSHOT_ASSISTED_DRIFT
```

This keeps source-reader contract failure separate from state mismatch evidence.

---

## Aggregate Snapshot Path

Aggregate snapshot-assisted rehydration is future work.

```text
aggregate snapshot
→ verify lineage / hash / schema / aggregate logic version
→ load tail events after source sequence
→ replay tail into aggregate
→ validate command
→ candidate event
→ Compass Layer 1
→ append-time admission
```

The aggregate snapshot path is stricter because the reconstructed state can influence accepted-history mutation.

The snapshot may accelerate aggregate reconstruction, but it must not replace:

- Compass Layer 1 validation
- idempotency classification
- concurrency admission
- append-time expected-version checks
- accepted history as source of truth

---

## Snapshot Production Points

Snapshot production should happen only after trusted reconstruction has produced state from accepted history.

Possible production points:

```text
after full accepted-history replay / rebuild
after projection worker reaches a configured interval
after successful full aggregate rehydration
after accepted command crosses a configured sequence threshold
through a background snapshot builder
through an explicit manual/admin rebuild command
```

The first implementation does not require automatic generation.

Safe snapshot consumption and validation are implemented before production policy becomes automatic.

---

## Snapshot Write Collision

Snapshot write should be idempotent for benign races.

If another worker already wrote the same complete source boundary with the same snapshot schema version, reducer version, and payload hash, the write can be treated as success.

If another worker wrote the same boundary with different evidence, the system should raise an explicit collision error.

This detects non-deterministic snapshot generation or corrupted writer behavior.

---

## Failure Modes

Snapshot-assisted reconstruction should reject or ignore a snapshot when:

```text
snapshot missing
accepted history missing for requested order
source event missing
source event belongs to another stream
source sequence mismatch
source global position mismatch
snapshot schema unsupported
logic version unsupported
payload hash mismatch
tail event source cursor contract violation
tail discontinuity that cannot be explained by a future hole registry
snapshot state version incompatible
snapshot-assisted state differs from authority replay
same-boundary different-hash collision
```

All trust failures should fall back to the authority path when fallback is possible.

Write collisions should be surfaced explicitly because they indicate non-deterministic snapshot production or corrupted writers.

---

## Future Relationship to Compass Layer 2

Stage 3.5D does not implement Compass Layer 2.

However, snapshot trust failures are natural future evidence for Layer 2 and structured semantic outcomes.

Examples:

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

Stage 4 may later classify these failures and map them to runtime decisions.

---

## Non-goals

This note does not define:

- exact SQL table shape
- Python store implementation details
- automatic snapshot rebuild scheduling
- automatic repair policy
- runtime decision policy
- action safety behavior
- sealed snapshot cryptography
- production hot-path snapshot resolver
- aggregate snapshot schema / store
- write-side snapshot-assisted rehydration
