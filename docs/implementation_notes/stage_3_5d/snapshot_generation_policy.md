# Snapshot Generation Policy

[← Back to Stage 3.5D Notes](README.md)

## Purpose

This note defines how snapshot generation should be reasoned about in Stage 3.5D.

Snapshot generation is separate from snapshot trust validation.

The key rule is:

```text
Snapshot should be produced only after trusted reconstruction,
and consumed only after trust qualification.
```

---

## Current Stage 3.5D Status

Stage 3.5D currently focuses on read-side projection snapshot trust.

Current completed path:

```text
PR4
= projection snapshot-assisted replay validator
= validates snapshot-assisted replay against accepted-history authority replay

PR4.5
= projection snapshot-assisted state resolver
= consumes externally qualified projection snapshots for read-side resolution
```

Projection snapshots are derived-state compression. If they are invalid or unusable, they can be bypassed, rejected, rebuilt, or compared against accepted history.

Write-side aggregate snapshots are intentionally deferred because they may participate in command admission and therefore require a stricter trust model.

Current plan:

```text
PR5
= document Aggregate Snapshot Trust Boundary / Deferral Decision

PR6 / PR7
= deferred
```

Automatic snapshot production remains out of scope for Stage 3.5D closeout.

---

## Responsibility Separation

Stage 3.5D should keep these responsibilities separate:

```text
SnapshotBuilder
= builds snapshot payload from trusted reconstruction result

SnapshotStore
= persists and loads snapshots

SnapshotTrustValidator
= decides whether an existing snapshot may be used

SnapshotGenerationPolicy
= decides when producing a new snapshot is useful
```

The store should not decide when snapshots are generated.

The validator should not silently create snapshots.

The generation policy should not decide whether an existing snapshot is trustworthy.

---

## Trusted Reconstruction Requirement

A snapshot should be generated only after state has been reconstructed through a trusted path.

Trusted paths include:

```text
full accepted-history replay
trusted snapshot + tail replay
projection worker applying accepted events through canonical reducer
write-side aggregate replay through accepted history
```

Untrusted paths must not generate new snapshots.

---

## Projection Snapshot Production Points

Projection snapshots may be produced:

### 1. After Full Replay / Rebuild

```text
full accepted-history replay
→ reconstructed projection state
→ build projection snapshot
→ save projection snapshot
```

This is the safest production point.

### 2. During Projection Worker Processing

```text
projection worker processes accepted event
→ projection state updated
→ checkpoint updated
→ if snapshot interval reached
→ build projection snapshot
```

The snapshot should use the accepted event boundary corresponding to the state.

### 3. After Tail Replay Cost Threshold

```text
latest_global_position - snapshot.source_global_position > threshold
→ produce a new snapshot
```

This is a later optimization.

---

## Aggregate Snapshot Production Points

Aggregate snapshot production is currently deferred.

The following options remain valid future production patterns, but they are not part of the current Stage 3.5D implementation.

### 1. After Full Aggregate Rehydration

```text
full accepted-history replay
→ aggregate reconstructed
→ build aggregate snapshot
→ save aggregate snapshot
```

This is safe and explicit.

### 2. After Accepted Command Crosses Threshold

```text
command accepted
→ accepted event appended
→ if accepted sequence crosses snapshot interval
→ build aggregate snapshot
```

Snapshot writing should remain secondary.

Accepted-history mutation must not depend on snapshot persistence.

### 3. Background Snapshot Builder

```text
background worker scans long / hot streams
→ reconstructs aggregate from accepted history
→ writes aggregate snapshot
```

This avoids adding latency to command handling, but introduces worker coordination concerns.

### 4. Lazy On-Demand Snapshot

```text
command arrives
→ no snapshot or stale snapshot
→ full replay
→ optionally write snapshot after replay
```

This is useful, but it can cause cache stampede.

It requires idempotent write collision handling.

---

## Snapshot Write Failure Rule

Snapshot write failure must not invalidate accepted history.

For write-side flows:

```text
accepted event append success
snapshot write failure
```

must not become:

```text
accepted event rollback
```

unless the snapshot is explicitly part of a separate test-only or rebuild transaction.

Snapshot is derived and rebuildable.

Accepted history is authority.

---

## Generation Policy v1 Recommendation

For the Stage 3.5D closeout direction:

```text
PR1–PR4
= support snapshot trust boundary, schema, storage, and replay validation

PR4.5
= support read-side projection snapshot-assisted resolution from an externally qualified snapshot id

PR5
= document aggregate snapshot trust boundary and deferral decision

PR6 / PR7
= deferred
```

Automatic snapshot production is deferred until safe consumption, collision handling, validation receipts, invalidation policy, and runtime fallback behavior are proven.

This keeps Stage 3.5D focused on trust-safe snapshot usage first.

---

## Collision Policy Requirement

Any generation policy that can be triggered concurrently must use idempotent collision behavior:

```text
same boundary + same payload_hash = idempotent success
same boundary + different payload_hash = collision error
```

For the PR2 projection snapshot schema baseline, the physical boundary is:

```text
source_event_id
order_id + source_event_sequence
source_global_position
```

A future multi-version snapshot design may widen this boundary with `reducer_version` and `snapshot_schema_version`.

This is required for:

- background builders
- lazy on-demand generation
- multiple workers
- repeated rebuild attempts

---

## Non-goals

This note does not implement:

- scheduler
- worker lease
- snapshot rebuild daemon
- cache warming strategy
- production snapshot retention policy
- HMAC / signing
- automatic repair policy
