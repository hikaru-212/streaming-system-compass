# Snapshot Generation Policy

[← Back to Implementation Notes](README.md)

## Purpose

This note defines how snapshot generation should be reasoned about in Stage 3.5D.

Snapshot generation is separate from snapshot trust validation.

The key rule is:

```text
Snapshot should be produced only after trusted reconstruction,
and consumed only after trust qualification.
```

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

Aggregate snapshots may be produced:

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

For initial Stage 3.5D implementation:

```text
PR1–PR4:
support explicit snapshot building for tests and replay validation

PR5–PR7:
support aggregate snapshot building after explicit full aggregate replay

automatic production:
defer until safe consumption and collision policy are proven
```

This keeps Stage 3.5D focused on trust-safe snapshot usage first.

---

## Collision Policy Requirement

Any generation policy that can be triggered concurrently must use idempotent collision behavior:

```text
same boundary + same payload_hash = idempotent success
same boundary + different payload_hash = collision error
```

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
