# Snapshot Trust Contract Boundary

[← Back to Boundary Notes](README.md)

## Purpose

This note defines the trust boundary for snapshot-assisted replay and rehydration.

Stage 3.5D introduces snapshot work as a replay-efficiency stage, but snapshot must not be treated as a simple cache.

A snapshot is derived state compression.

It may accelerate reconstruction, but it must not replace accepted history as the source of truth.

---

## Stage Scope After PR4

Stage 3.5D defines a general Snapshot Trust Contract.

The first implemented pass applies this contract to projection / read-side snapshot-assisted replay:

```text
PR1   — Snapshot Trust Contract Boundary
PR1.5 — CI Stage Branch Checks
PR2   — Projection Snapshot Schema Baseline
PR3   — PostgresProjectionSnapshotStore
PR4   — Projection Snapshot-Assisted Replay Validator
```

PR4 validates whether projection snapshot-assisted replay reconstructs the same state as accepted-history replay.

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

Snapshot does not mean truth.

Snapshot means:

```text
derived state compression qualified for possible fast-path use
```

---

## Snapshot Is Not

A snapshot is not:

- accepted history
- a replacement for the event log
- proof by itself that replay would produce the same result
- a reason to skip append-time admission
- a reason to skip Compass Layer 1 validation
- a future `SemanticOutcome`
- a runtime decision policy
- an action safety gate
- an automatic repair policy

---

## Fast Path vs Authority Path

Stage 3.5D preserves the distinction:

```text
fast path candidate = snapshot + tail replay + trust checks
authority path = full accepted-history replay
```

The fast path exists for replay efficiency.

The authority path exists for:

- audit
- rebuild
- suspicious snapshot state
- trust-check failure
- logic version mismatch
- schema version mismatch
- high-risk validation
- future Layer 2 evidence generation

PR4 is a validation path. It compares snapshot-assisted replay against the authority path.

It is not the final production hot-path resolver.

---

## Snapshot Consumption vs Snapshot Production

Snapshot consumption and snapshot production are separate responsibilities.

```text
SnapshotTrustValidator / ReplayValidator
= checks whether existing snapshot evidence can reconstruct authority-equivalent state

SnapshotBuilder
= creates snapshot payload from trusted reconstruction output

SnapshotGenerationPolicy
= decides when a new snapshot should be produced
```

The store does not decide when to produce snapshots.

The validator does not silently create snapshots.

The builder does not decide whether a snapshot is safe to consume.

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

## Implemented PR4 Trust Checks

The PR4 projection replay validator performs a narrow set of checks that are supported by the current evidence model:

```text
accepted history exists for requested order
snapshot exists
snapshot.order_id matches requested order_id
snapshot.source_global_position > 0
snapshot.source_event_sequence > 0
snapshot.source_event_sequence <= authority_max_sequence
snapshot.state_version >= 0
snapshot.state_version <= snapshot.source_event_sequence
snapshot.state_version == snapshot.source_event_sequence under the current reducer
snapshot.state_status is supported by the current projection state model
tail event source returns strictly advancing global_position values
snapshot-assisted replay result matches accepted-history replay result
```

These checks produce validation evidence.

They do not decide runtime repair, quarantine, fallback, or command admission policy.

---

## Deferred Trust Checks

The general boundary still expects future trust checks such as:

```text
source_event_id exists in accepted history
source_event belongs to the same order stream
source_event_sequence matches accepted history
source_global_position matches accepted history
snapshot_schema_version is supported
logic_version is supported
payload_hash matches canonical snapshot payload
tail gaps are explained by an aborted-position / hole registry
snapshot state satisfies projection-domain invariants at the claimed boundary
```

These are deferred because they require additional durable evidence models or policy registries.

---

## Version Compatibility

Database constraints should not assume that every future accepted event must advance business state version.

The physical database constraint should allow:

```text
state_version <= source_event_sequence
```

Stronger domain-specific version rules belong to Python-level trust checks.

For the current minimal order projection reducer, PR4 enforces:

```text
state_version == source_event_sequence
```

This is a current reducer compatibility check, not a permanent database law.

Future event types may represent audit metadata, warnings, or informational events that do not change business state.

---

## Canonical Payload Hashing

`payload_hash` must be computed over a canonical snapshot payload.

The hash must not depend on:

- Python dictionary insertion order
- JSON whitespace
- object memory identity
- non-deterministic serialization
- locale-specific formatting

The canonicalization rules live in a dedicated implementation note and shared helper.

The same logical snapshot payload must always produce the same hash.

PR4 does not yet verify payload hash.

That remains future trust-validation work.

---

## Snapshot Write Collision Policy

Snapshot writes should tolerate benign races.

If the same complete snapshot boundary already exists with the same schema version, logic version, and payload hash, the write should be treated as idempotent success.

If the same boundary already exists with different evidence, the write should fail with an explicit collision error.

```text
same complete boundary + same version evidence + same payload_hash = idempotent success
same complete boundary + different evidence = SnapshotWriteCollisionError
```

This prevents cache-stampede races from crashing normal execution while still detecting non-deterministic snapshot generation.

---

## Tail Continuity

For projection-side replay, the snapshot preserves `source_global_position` so the tail event source can load events strictly after the snapshot boundary:

```text
event.global_position > snapshot.source_global_position
```

PR4 validates the tail source cursor contract:

```text
next global_position must strictly advance
```

It does not yet validate every global-position gap.

That requires a future aborted-position / hole registry so the system can distinguish legitimate gaps from unexplained source discontinuity.

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

PR4 answers the first projection-side validation slice of that question.

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
INVALID_SNAPSHOT_LINEAGE
SNAPSHOT_PAYLOAD_HASH_MISMATCH
UNSUPPORTED_REDUCER_VERSION
UNSUPPORTED_SNAPSHOT_SCHEMA_VERSION
SNAPSHOT_STATE_DOMAIN_VIOLATION
UNEXPLAINED_GLOBAL_POSITION_GAP
TAIL_REPLAY_DOMAIN_FAILURE
ACCEPTED_HISTORY_CONTRACT_VIOLATION
```

Stage 3.5D does not implement the full Stage 4 outcome model.

---

## Non-goals

This boundary note does not implement:

- production code
- snapshot tables
- snapshot stores
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
