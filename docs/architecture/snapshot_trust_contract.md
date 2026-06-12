# Snapshot Trust Contract

[← Back to Architecture](README.md)

## Purpose

This architecture note explains how snapshot support fits into Streaming System + Compass.

Snapshot support is introduced in Stage 3.5D as a replay-efficiency mechanism.

However, snapshot is not only a performance optimization.

Snapshot creates a trust boundary because it allows runtime reconstruction to start from derived state rather than from the beginning of accepted history.

---

## Current Baseline Before Snapshot

Before Stage 3.5D, the system has:

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

This means the system can already rebuild or validate derived state through accepted history.

Stage 3.5D adds a new question:

```text
Can reconstruction be accelerated through a snapshot while preserving trust?
```

---

## Architectural Principle

```text
accepted history is authority
snapshot is acceleration
```

The snapshot path must be optional.

If a snapshot is missing, invalid, stale, unsupported, suspicious, or generated non-deterministically, the system must be able to fall back to accepted-history replay.

---

## Runtime Paths

### Authority Path

```text
accepted history
→ full replay
→ reconstructed state
```

This path is authoritative.

It should be used for:

- audit
- rebuild
- suspicious derived state
- snapshot trust failure
- reducer / aggregate logic upgrade
- high-risk verification
- later Layer 2 evidence generation

### Fast Path

```text
snapshot
→ trust checks
→ tail replay
→ reconstructed state
```

This path is performance-oriented.

It may be used only if trust checks qualify the snapshot.

---

## Responsibility Separation

Snapshot architecture should separate four responsibilities:

```text
SnapshotBuilder
= constructs a snapshot from trusted reconstruction result

SnapshotStore
= persists and loads snapshots

SnapshotTrustValidator
= decides whether an existing snapshot may be used

SnapshotGenerationPolicy
= decides when a new snapshot should be produced
```

The validator should not implicitly write snapshots.

The store should not decide generation timing.

The generation policy should not decide trust.

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

The first implementation target is projection snapshot support.

Aggregate snapshot support is a later extension for write-side rehydration.

---

## Projection Snapshot Path

Projection snapshot-assisted replay is used to accelerate read-side replay / rebuild / validation.

```text
projection snapshot
→ verify lineage / hash / schema / reducer version
→ load tail events after source_global_position
→ replay tail through canonical reducer
→ reconstructed projection state
```

This extends Stage 3.5C durable replay / rebuild validation.

---

## Aggregate Snapshot Path

Aggregate snapshot-assisted rehydration is used to accelerate write-side command handling.

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

The first implementation should not require automatic generation.

Safe snapshot consumption should be implemented before production policy becomes automatic.

---

## Snapshot Write Collision

Snapshot write should be idempotent for benign races.

If another worker already wrote the same snapshot boundary with the same payload hash, the write can be treated as success.

If another worker wrote the same boundary with a different payload hash, the system should raise an explicit collision error.

This detects non-deterministic snapshot generation or corrupted writer behavior.

---

## Failure Modes

Snapshot-assisted reconstruction should reject or ignore a snapshot when:

```text
snapshot missing
source event missing
source event belongs to another stream
source sequence mismatch
source global position mismatch
snapshot schema unsupported
logic version unsupported
payload hash mismatch
tail discontinuity
snapshot state version incompatible
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
SNAPSHOT_HASH_MISMATCH
SNAPSHOT_TAIL_DISCONTINUITY
SNAPSHOT_LOGIC_VERSION_UNTRUSTED
SNAPSHOT_REPLAY_MISMATCH
SNAPSHOT_WRITE_COLLISION
```

Stage 4 may later classify these failures and map them to runtime decisions.

---

## Non-goals

This note does not define:

- exact SQL table shape
- Python store implementation
- automatic snapshot rebuild scheduling
- automatic repair policy
- runtime decision policy
- action safety behavior
- sealed snapshot cryptography
