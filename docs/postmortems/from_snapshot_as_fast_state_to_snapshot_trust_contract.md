# Postmortem: From Snapshot as Fast State to Snapshot Trust Contract

[← Back to Postmortems Index](README.md)

**Recorded on:** 2026-06-05

## 1. Context

While planning the later stages of the Streaming System + Compass project, I started thinking about snapshot support.

The original motivation seemed straightforward:

```text
event log grows over time
→ full replay becomes expensive
→ snapshot can reduce replay / rehydrate cost
```

At first, snapshot looked like a simple performance optimization.

However, the more I examined it, the more I realized that snapshot introduces a deeper correctness problem:

```text
If snapshot state is mutable or corrupted,
the runtime may derive the wrong current state.
```

This matters because Compass depends on trusted reconstruction of accepted history.
If the state used by Compass is already polluted, later validation may become misleading.

---

## 2. Problem

The main problem was a tension between performance and trust.

On one side, snapshot exists to avoid full replay:

```text
load snapshot
→ replay tail events
→ derive current state faster
```

On the other side, if a snapshot can be modified after creation, it may become dangerous.

For example, the accepted event history may imply:

```text
status = CREATED
```

but the snapshot row may be changed to:

```text
status = PAID
```

If the runtime blindly trusts that snapshot, then the system may derive a false aggregate state.

This could cause several downstream problems:

- valid commands may be wrongly rejected
- invalid commands may appear valid
- Compass validation context may be polluted
- read-side state may no longer reflect accepted history
- future action-safety decisions may be based on false derived state

The naive answer would be:

```text
Always full replay and compare snapshot with event log.
```

But that defeats the purpose of snapshot.

If every normal runtime path must perform full replay to verify the snapshot, then snapshot no longer provides meaningful replay efficiency.

---

## 3. Root Cause

The root cause was treating snapshot as a simple cached state without first defining its trust boundary.

I was mixing two different questions:

```text
How can snapshot make replay faster?
```

and:

```text
Why is this snapshot safe enough to use?
```

A snapshot is not the source of truth.

It is derived state.

But if runtime logic uses it as the starting point for rehydration, then it still needs a trust contract.

The missing concept was:

```text
Snapshot should not be blindly trusted,
but it should not require full replay on every normal path either.
```

---

## 4. What I Realized

The correct model is not:

```text
snapshot is always trusted
```

or:

```text
snapshot must always be fully verified by replay
```

The better model is:

```text
snapshot = fast path
event log replay = authority path
```

Normal runtime can use snapshot when it passes lightweight trust checks.

Full replay should be reserved for:

- audit
- debugging
- suspicious snapshot state
- hash / metadata failure
- reducer version changes
- high-risk action verification
- rebuild / recovery
- Layer 2 validation

This means snapshot trust is not binary.

A snapshot can have different trust levels:

- invalid / untrusted
- fast-path eligible
- high-confidence
- recently audited

The key realization is:

```text
Fast checks do not prove full semantic equivalence.
They decide whether the snapshot is qualified to be used on the fast path.
```

Full replay remains the final authority, but it does not need to run every time.

---

## 5. Resolution

The resolution is to treat snapshot as a derived state-compression artifact with an explicit Snapshot Trust Contract.

A future snapshot should include more than only state payload.

It should carry lineage and integrity evidence such as:

```text
snapshot_id
aggregate_id / order_id
snapshot_version
source_event_id
source_event_sequence
snapshot_schema_version
reducer_version
payload_hash
created_at
created_by
```

The runtime can then perform fast trust checks before using the snapshot.

### 5.1 Lineage Check

The snapshot should point back to accepted history.

Check:

```text
snapshot.order_id == target order_id
source_event_id exists
source_event belongs to the same stream
source_event_sequence == snapshot_version
snapshot_version <= latest_event_version
```

This prevents ungrounded snapshots.

### 5.2 Tail Continuity Check

If snapshot is at version 100 and latest event is version 105, the tail replay must contain:

```text
101, 102, 103, 104, 105
```

If any version is missing, snapshot-assisted replay should not be trusted.

### 5.3 Payload Hash Check

The snapshot payload should have a hash.

If someone modifies:

```text
CREATED → PAID
```

without updating the hash, the system can detect the mutation quickly.

This is not full semantic proof, but it protects against accidental corruption and simple tampering.

### 5.4 Schema and Reducer Version Check

A snapshot should record which schema version and reducer version produced it.

If a reducer version is later known to be wrong, snapshots generated by that reducer should be ignored and rebuilt.

This handles the case where the snapshot was not tampered with, but was produced by flawed logic.

### 5.5 Fallback to Full Replay

If any trust check fails:

```text
ignore snapshot
→ full replay accepted history
→ rebuild snapshot
→ optionally emit future SemanticOutcome
```

The snapshot must be discardable.

Accepted event history remains the authority.

---

## 6. Key Takeaway

Snapshot is not just a performance feature.

It creates a trust boundary.

The correct question is not only:

```text
How can snapshot reduce replay cost?
```

but also:

```text
Why is this snapshot safe enough to use on the fast path?
```

The final principle is:

```text
Snapshot is the fast path.
Event log replay is the authority path.
```

A snapshot may accelerate reconstruction, but it must remain:

- traceable to accepted history
- checkable through metadata and integrity evidence
- rejectable when invalid
- discardable when suspicious
- rebuildable from the event log

---

## 7. Reusable Lesson

For future architecture work, I should avoid treating derived state as harmless simply because it can be rebuilt.

Derived state can still cause runtime damage if it is trusted at the wrong moment.

A safer reasoning sequence is:

1. Identify the source of truth.
2. Identify which states are derived.
3. Identify where derived state is used by runtime decisions.
4. Define fast-path trust checks.
5. Define authority-path verification.
6. Define fallback / rebuild behavior.
7. Only then optimize for replay efficiency.

This applies not only to aggregate snapshots, but also to:

- read-side projections
- materialized views
- checkpointed state
- agent-visible derived state
- future isolated read-side DBs

---

## 8. Follow-up Action

This issue should be carried into later roadmap planning.

### Stage 3.5C

Do not implement snapshot.

Focus on:

```text
durable projection state
durable checkpoint state
projection worker persistence
rebuild from accepted history
```

### Stage 3.5D

Introduce snapshot and replay-efficiency work.

Potential tasks:

```text
aggregate snapshot schema
snapshot metadata / lineage
snapshot-assisted rehydrate
tail replay continuity check
snapshot_schema_version
reducer_version
payload_hash
fallback to full replay
replay cost measurement
```

### Stage 4

Convert snapshot / projection trust failures into structured outcomes.

Potential future error types:

```text
SNAPSHOT_METADATA_INVALID
SNAPSHOT_HASH_MISMATCH
SNAPSHOT_SCHEMA_UNSUPPORTED
SNAPSHOT_REDUCER_VERSION_UNTRUSTED
SNAPSHOT_TAIL_DISCONTINUITY
SNAPSHOT_REPLAY_MISMATCH
PROJECTION_DRIFT
```

### Stage 5+

Consider stronger governance hardening only after the core flow works.

Possible future directions:

```text
sealed milestone snapshot
HMAC / digital signature
isolated derived-state runtime
oblivious agent runtime
controlled agent read boundary
```

These are not current implementation requirements.

They are future hardening directions.
