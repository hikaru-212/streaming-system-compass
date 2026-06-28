# Aggregate Snapshot Trust Boundary / Deferral Decision

[← Back to Implementation Notes](README.md)

## Purpose

This note records the Stage 3.5D PR5 decision to defer aggregate snapshot production and snapshot-assisted write-side rehydration.

Stage 3.5D has completed the read-side projection snapshot trust path:

```text
projection snapshot schema
→ projection snapshot store
→ projection snapshot-assisted replay validator
→ projection snapshot-assisted state resolver
```

That work proves the read-side projection snapshot trust boundary.

However, write-side aggregate snapshots are a different class of risk.

This note explains why aggregate snapshot schema, aggregate snapshot store, and snapshot-assisted write-side rehydration are intentionally deferred.

---

## Decision

Do not implement the following in Stage 3.5D:

```text
Aggregate Snapshot Schema / Store
Snapshot-Assisted Write-Side Rehydration
Production write-side aggregate snapshot fast path
```

Instead, Stage 3.5D closes with a documented deferral decision.

The previously planned work is now classified as deferred:

```text
Deferred PR6 — Aggregate Snapshot Schema / Store
Deferred PR7 — Snapshot-Assisted Write-Side Rehydration
```

---

## Core Distinction

Read-side projection snapshots and write-side aggregate snapshots are not equivalent.

```text
read-side projection snapshot
= derived state compression
= replay-efficiency support
= runtime evidence
= can be rejected, bypassed, rebuilt, or compared against authority

write-side aggregate snapshot
= admission-path optimization
= may influence command validation
= may affect future accepted-history admission
= requires a stricter trust contract
```

This distinction is the main reason for deferral.

---

## Why Projection Snapshots Are Safer

Projection snapshots are derived read-side artifacts.

If a projection snapshot is invalid, stale, incompatible, or unusable, the system can:

```text
reject the snapshot
bypass the snapshot fast path
fall back to accepted-history replay
rebuild projection state
compare against authority using PR4 validator
```

A bad projection snapshot may produce a read-side inconsistency, but it does not directly admit new accepted facts into history.

This makes projection snapshots suitable for Stage 3.5D read-side trust work.

---

## Why Aggregate Snapshots Are Stricter

Aggregate snapshots may participate in write-side rehydration.

That means they may influence:

```text
current aggregate state reconstruction
command validation
candidate event proof construction
semantic admission decisions
future accepted-history append behavior
```

If a write-side aggregate snapshot is stale, corrupted, incompatible, or trusted incorrectly, the system may validate a future command against the wrong state.

That is a stronger failure mode than read-side projection drift.

A bad aggregate snapshot could cause the system to produce the wrong candidate event, accept the wrong transition, or reject a valid command for the wrong reason.

Therefore, aggregate snapshot trust must be stricter than projection snapshot trust.

---

## Accepted History Remains Authority

The current authority model remains:

```text
accepted history = authority
snapshot = derived compression
```

For write-side admission, accepted history must remain the final source of truth.

Until aggregate snapshot trust is mature enough, command handling should continue to use accepted-history replay / rehydration rather than snapshot-assisted write-side rehydration.

---

## Deferral Rationale

Aggregate snapshot implementation is deferred because the current system does not yet have enough supporting infrastructure.

Missing or incomplete future components include:

```text
durable validation receipts
SnapshotTrustGate
SnapshotFastPathSelector
RuntimeStateResolutionService
aggregate snapshot invalidation policy
aggregate snapshot rebuild policy
write-side fallback orchestration
snapshot freshness policy
payload hash recomputation / mismatch classification
write-side snapshot corruption detection
cost-aware strategy selection
```

Without these, aggregate snapshots could be introduced as an optimization before the trust boundary is strong enough.

That would weaken the project's core principle:

```text
technical success does not prove semantic correctness
```

---

## Current Stage 3.5D Closeout Position

Stage 3.5D closes with:

```text
PR1   — General Snapshot Trust Contract Boundary
PR1.5 — CI / Stage Branch Checks
PR2   — Projection Snapshot Schema Baseline
PR3   — PostgresProjectionSnapshotStore
PR4   — Projection Snapshot-Assisted Replay Validator
PR4.5 — Projection Snapshot-Assisted State Resolver
PR5   — Aggregate Snapshot Trust Boundary / Deferral Decision
```

The following work is deferred:

```text
Deferred PR6 — Aggregate Snapshot Schema / Store
Deferred PR7 — Snapshot-Assisted Write-Side Rehydration
```

This gives Stage 3.5D a clean ending:

```text
read-side snapshot trust completed
write-side snapshot trust explicitly deferred
```

---

## Future Revival Conditions

Revisit aggregate snapshots when one or more of the following become true:

```text
aggregate replay depth becomes expensive
command admission latency becomes significant
aggregate history size grows substantially
hot aggregates create meaningful rehydration pressure
validation receipts exist
SnapshotTrustGate exists
SnapshotFastPathSelector exists
write-side fallback policy exists
snapshot invalidation / rebuild policy exists
payload hash recomputation and mismatch classification exist
aggregate snapshot corruption can be detected and safely bypassed
cost-aware RuntimeDecisionPolicy / StrategySelector exists
```

Aggregate snapshots should not be revived merely because snapshots exist on the read side.

They should be revived only when write-side replay cost justifies the additional trust machinery.

---

## Future Aggregate Snapshot Safe Path

A future safe write-side aggregate snapshot flow may look like:

```text
accepted history replay
→ aggregate reconstructed
→ aggregate snapshot built
→ payload hash computed
→ validation receipt written
→ future command receives snapshot candidate
→ trust gate qualifies snapshot
→ snapshot-assisted rehydration
→ tail replay after snapshot boundary
→ command validation
→ accepted event append
```

If trust qualification fails, the system should fall back to accepted-history replay.

The fallback path must remain available because snapshot is derived compression, not authority.

---

## Non-goals

This PR5 note does not implement:

```text
aggregate snapshot table
aggregate snapshot store
aggregate snapshot builder
snapshot-assisted write-side rehydration
write-side snapshot validator
validation receipt store
trust gate
runtime strategy selector
fallback orchestration
benchmark suite
production snapshot retention policy
```

This PR5 note is a deferral and boundary clarification.

---

## Summary

Projection snapshots are read-side derived compression.

Aggregate snapshots may become write-side admission-path state.

Because write-side admission has a stricter correctness requirement, aggregate snapshot implementation is deferred.

Stage 3.5D closes with read-side projection snapshot trust completed and write-side aggregate snapshot trust explicitly deferred.
