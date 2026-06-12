# Snapshot Trust Contract Boundary

[← Back to Boundary Notes](README.md)

## Purpose

This note defines the trust boundary for snapshot-assisted replay and rehydration.

Stage 3.5D introduces snapshot work as a replay-efficiency stage, but snapshot must not be treated as a simple cache.

A snapshot is derived state compression.

It may accelerate reconstruction, but it must not replace accepted history as the source of truth.

---

## Stage Scope

Stage 3.5D defines a general Snapshot Trust Contract.

The first implementation pass applies this contract to projection / read-side snapshot-assisted replay.

A later extension may apply the same contract to write-side aggregate snapshot-assisted rehydration.

The write-side extension is more sensitive because reconstructed aggregate state can influence:

- command validation
- candidate event generation
- Compass Layer 1 validation context
- accepted-history admission

Therefore, write-side snapshot support must preserve stricter admission-path constraints.

---

## Source-of-Truth Rule

```text
accepted history = source of truth
snapshot = derived state compression
projection state = derived runtime view
checkpoint = operational progress metadata
```

A snapshot is valid only insofar as it can be traced back to accepted history.

A snapshot must be:

- traceable
- checkable
- rejectable
- discardable
- rebuildable

---

## Snapshot Definition

A snapshot is a durable or in-memory record that captures derived state at a known accepted-history boundary.

At minimum, a snapshot should describe:

```text
what state was captured
which accepted event boundary produced it
which schema version shaped it
which logic version produced it
which integrity evidence protects it
```

Snapshot does not mean "truth."

Snapshot means:

```text
derived state compression qualified for possible fast-path use
```

---

## Snapshot Is Not

A snapshot is not:

- accepted history
- a replacement for the event log
- proof that replay would produce the same result
- a reason to skip append-time admission
- a reason to skip Compass Layer 1 validation
- a future `SemanticOutcome`
- a runtime decision policy
- an action safety gate
- an automatic repair policy

---

## Fast Path vs Authority Path

Stage 3.5D introduces the distinction:

```text
fast path = snapshot + tail replay + trust checks
authority path = full accepted-history replay
```

The fast path exists for normal replay efficiency.

The authority path exists for:

- audit
- rebuild
- suspicious snapshot state
- trust-check failure
- logic version mismatch
- schema version mismatch
- high-risk validation
- future Layer 2 evidence generation

---

## Snapshot Consumption vs Snapshot Production

Snapshot consumption and snapshot production are separate responsibilities.

```text
SnapshotTrustValidator
= decides whether an existing snapshot may be used

SnapshotBuilder
= creates snapshot payload from trusted reconstruction output

SnapshotGenerationPolicy
= decides when a new snapshot should be produced
```

The store should not decide when to produce snapshots.

The validator should not silently create snapshots.

The builder should not decide whether a snapshot is safe to consume.

This separation prevents snapshot optimization from becoming implicit runtime mutation.

---

## Required Snapshot Evidence

A snapshot should carry evidence such as:

```text
snapshot_id
snapshot_kind
order_id
source_event_id
source_event_sequence
source_global_position
snapshot_schema_version
logic_version
payload_hash
created_at
created_by
metadata_json
```

For projection snapshots:

```text
logic_version = reducer_version
```

For write-side aggregate snapshots:

```text
logic_version = aggregate_rehydration_logic_version
```

The exact physical schema may differ between projection and aggregate snapshots, but both should follow the same trust contract.

---

## Lightweight Trust Checks

Before a snapshot is used on a fast path, the runtime should check:

```text
snapshot belongs to the requested order_id
source_event_id exists in accepted history
source_event belongs to the same order stream
source_event_sequence matches accepted history
source_global_position matches accepted history
snapshot_schema_version is supported
logic_version is supported
payload_hash matches canonical snapshot payload
tail events are continuous after the snapshot boundary
```

These checks qualify the snapshot for fast-path use.

They do not prove full semantic equivalence.

---

## Version Compatibility

Database constraints should not assume that every future accepted event must advance business state version.

The physical database constraint should allow:

```text
state_version <= source_event_sequence
```

Stronger domain-specific version rules belong to Python-level trust checks.

For example, the current minimal order domain may require all accepted domain events to advance state version, but future event types may represent audit metadata, warnings, or informational events that do not change business state.

---

## Canonical Payload Hashing

`payload_hash` must be computed over a canonical snapshot payload.

The hash must not depend on:

- Python dictionary insertion order
- JSON whitespace
- object memory identity
- non-deterministic serialization
- locale-specific formatting

The canonicalization rules should live in a dedicated implementation note and shared helper.

The same logical snapshot payload must always produce the same hash.

---

## Snapshot Write Collision Policy

Snapshot writes should tolerate benign races.

If the same snapshot boundary already exists with the same payload hash, the write should be treated as idempotent success.

If the same snapshot boundary already exists with a different payload hash, the write should fail with an explicit collision error.

```text
same boundary + same payload_hash = idempotent success
same boundary + different payload_hash = SnapshotWriteCollisionError
```

This prevents cache-stampede races from crashing normal execution while still detecting non-deterministic snapshot generation.

---

## Tail Continuity

If a snapshot claims to represent state through sequence `N`, and the latest accepted event is sequence `M`, then tail replay must cover:

```text
N + 1
through
M
```

without gaps, if the event stream contract requires contiguous sequence for the given reconstruction path.

For projection-side replay, the snapshot should also preserve enough global-position evidence to support accepted-history consumption after the snapshot boundary.

---

## Fallback Rule

If snapshot trust cannot be established:

```text
ignore snapshot
→ full accepted-history replay
```

The runtime may optionally rebuild the snapshot through a later explicit rebuild path.

Fallback is required.

Automatic repair policy is not part of this boundary note.

---

## Relationship to Stage 3.5C

Stage 3.5C completed the durable read-side baseline:

```text
accepted history
→ projection state
→ checkpoint progress
→ global-position projection worker
→ durable replay / rebuild validation
```

Stage 3.5D builds on that baseline.

The next question is no longer only:

```text
Can persisted projection state be compared against accepted-history replay?
```

The next question is:

```text
Can a snapshot safely accelerate replay without becoming truth?
```

---

## Relationship to Write-Side Snapshot Support

Write-side aggregate snapshot support is valid future work.

It should reuse the same Snapshot Trust Contract, but with stricter constraints:

```text
snapshot may accelerate aggregate rehydration
snapshot must not relax command validation
snapshot must not relax Compass Layer 1
snapshot must not relax append-time admission
snapshot must not bypass idempotency behavior
```

The write-side rule is:

```text
Snapshot may accelerate reconstruction.
It must not gain authority over accepted-history admission.
```

---

## Relationship to Stage 4

Snapshot trust failures may later become structured `SemanticOutcome` evidence.

Potential future failure classifications include:

```text
SNAPSHOT_METADATA_INVALID
SNAPSHOT_HASH_MISMATCH
SNAPSHOT_SCHEMA_UNSUPPORTED
SNAPSHOT_LOGIC_VERSION_UNTRUSTED
SNAPSHOT_TAIL_DISCONTINUITY
SNAPSHOT_REPLAY_MISMATCH
SNAPSHOT_WRITE_COLLISION
```

Stage 3.5D should not implement the full Stage 4 outcome model.

---

## Non-goals

Stage 3.5D PR1 does not implement:

- production code
- snapshot tables
- snapshot stores
- snapshot-assisted replay implementation
- snapshot-assisted write-side rehydration implementation
- `SemanticOutcome`
- `RuntimeDecisionPolicy`
- `ActionSafetyGate`
- automatic repair policy
- quarantine policy
- sealed snapshots
- HMAC / digital signatures
- production DB role hardening
- append-only trigger enforcement
