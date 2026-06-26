# ADR 0013: Snapshot Runtime Eligibility and Validation Receipt Boundary

[← Back to ADR Index](README.md)

## Status

Proposed

---

## Target Stage

Stage 3.5D — Snapshot Trust Contract / Replay Efficiency

This ADR affects:

```text
PR4   — Projection Snapshot-Assisted Replay Validator
PR4.5 — Projection Snapshot-Assisted State Resolver
PR5   — Aggregate Snapshot Trust Boundary / Deferral Decision
Future PR4.x — Snapshot Runtime Eligibility Policy / Validation Receipts
Future optimization — Aggregate Snapshot Schema / Store and Write-Side Rehydration
```

---

## Scope Clarification

This ADR records the long-term trust model for runtime snapshot use.

It distinguishes three related but separate boundaries:

```text
PR4 validator evidence
PR4.5 snapshot-assisted state resolution
future validation receipts
```

PR4.5 does **not** implement the full runtime trust-gate lifecycle or persisted validation receipts.

PR4.5 introduces the resolver primitive:

```text
explicitly qualified snapshot
+ tail replay
→ resolved projection state
```

If the resolver cannot use the provided snapshot, it should return a structured unresolved result.

Whether the caller falls back to full accepted-history replay is outside the resolver boundary.


## Stage 3.5D Scope Note

This ADR describes the general runtime eligibility model for snapshot use.

In the current Stage 3.5D pass, the production implementation applies this model to **projection snapshots**.

Projection snapshots operate on derived read-side state:

```text
accepted history
→ projection reducer
→ projection state / projection snapshot
```

The read-side snapshot path is useful for:

```text
projection replay efficiency
derived-state integrity evidence
snapshot-assisted read-state resolution
future Compass Layer 2 evidence substrate
```

It does not directly protect accepted-history admission.

The original high-risk Snapshot Trust Contract concern is stronger on the write-side aggregate path:

```text
invalid aggregate snapshot
→ false aggregate state
→ incorrect command validation
→ incorrect candidate event
→ possible accepted-history admission risk
```

However, the current order aggregate has shallow per-order history.

Write-side rehydration is based on the target aggregate's accepted events, not the total global event-log length.

Therefore, Stage 3.5D now closes aggregate snapshot work with:

```text
PR5 — Aggregate Snapshot Trust Boundary / Deferral Decision
```

The following production implementations are deferred as future optimizations:

```text
Aggregate Snapshot Schema / Store
Snapshot-Assisted Write-Side Rehydration
```

This is a deferral decision, not a rejection of aggregate snapshots as an architectural concept.

---

## Context

Stage 3.5D introduces projection snapshots as a replay-efficiency mechanism.

The basic motivation is:

```text
accepted event history grows over time
→ full replay becomes increasingly expensive
→ snapshot can reduce replay / rehydration cost
```

However, this project treats accepted history as the authority:

```text
accepted history = authority
snapshot = derived state compression
```

A snapshot is not the source of truth. It is a derived artifact that may be used as a fast-path starting point only when it is safe enough to use.

During PR4 integration tests, one important failure case became explicit.

A projection snapshot can be structurally valid according to the database schema while still being semantically wrong.

Example:

```text
accepted history:
1. CREATED
2. PAID

snapshot source boundary:
source_event_id = paid_event.event_id
source_event_sequence = 2
source_global_position = paid_record.global_position

snapshot state:
state_status = CREATED
paid_amount = 0.00
state_version = 2
```

This row can pass database constraints:

```text
source_event_sequence > 0
source_global_position > 0
state_status IN ('CREATED', 'PAID')
paid_amount >= 0
paid_amount <= total_amount
state_version >= 0
state_version <= source_event_sequence
```

But it is still semantically inconsistent.

The source boundary says:

```text
this snapshot has replayed accepted history through the PAID event
```

while the snapshot state says:

```text
the order is still CREATED
```

Therefore, database shape validation is not enough to prove snapshot correctness.

---

## Problem

PR4 establishes that a snapshot may be:

```text
structurally valid
but semantically inconsistent with accepted history
```

This creates a design tension for PR4.5.

PR4.5 exists to use snapshot-assisted replay as a meaningful fast path:

```text
load snapshot
→ hydrate snapshot state
→ replay tail events
→ avoid full replay from the beginning
```

However, if every runtime use of a snapshot must first run the full PR4 validator:

```text
snapshot-assisted replay
vs
full accepted-history replay
```

then snapshot-assisted replay loses its performance value.

The project needs to answer:

```text
How can runtime use snapshots without blindly trusting them,
while also avoiding full authority replay on every normal path?
```

The wrong answer would be:

```text
snapshot row exists
→ database constraints passed
→ trust snapshot
```

That is insufficient.

A structurally valid snapshot row cannot prove its own semantic correctness.

---

## Decision

The project will distinguish between:

```text
snapshot existence
snapshot fast-path eligibility
snapshot authority-validated trust
```

A projection snapshot is not trusted merely because it exists.

The project adopts the following rule:

```text
Snapshots are not trusted by existence.
Snapshots are used only with explicit evidence or explicit precondition.
```

For PR4.5, runtime snapshot-assisted resolution requires an explicit snapshot precondition supplied by the caller.

The resolver may perform minimal local compatibility checks before using the snapshot, such as:

```text
- snapshot exists
- snapshot order_id matches the target order
- snapshot_schema_version is supported
- reducer_version matches the current projection reducer
- source_event_sequence is positive
- source_global_position is positive
- state_version is compatible with the current reducer contract
- state payload can be hydrated into the current projection state model
```

These checks are **eligibility checks**, not full semantic proof.

If eligibility or precondition checks fail:

```text
PR4.5 must not use the snapshot.
```

The resolver should return a structured unresolved result.

Whether a caller then runs full accepted-history replay is a runtime decision outside PR4.5.

A stronger future design should introduce persisted validation receipts.

A validation receipt records that a specific snapshot has previously passed authority-based validation.

In that stronger model, runtime does not trust the snapshot row alone.

It trusts:

```text
snapshot row
+ validation receipt
+ version compatibility
+ payload integrity
+ source boundary consistency
```

---

## Chosen Approach

The selected approach is a staged model.

### Stage 1 — PR4 Validator

PR4 introduces the expensive authority validation path.

It can compare:

```text
snapshot-assisted replay result
vs
full accepted-history replay result
```

Possible outcomes include:

```text
MATCH
MISSING_SNAPSHOT
NO_ACCEPTED_HISTORY_FOR_ORDER
INVALID_SNAPSHOT_BOUNDARY
TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
SNAPSHOT_ASSISTED_DRIFT
```

PR4 proves whether a snapshot-assisted reconstruction agrees with the authority path.

This is allowed to be expensive because it is a validator / audit mechanism, not the normal runtime fast path.

---

### Stage 2 — PR4.5 Snapshot-Assisted State Resolver

PR4.5 introduces a resolver that can use an explicitly qualified projection snapshot as the starting point for state reconstruction.

Conceptually:

```text
explicitly qualified projection snapshot
→ hydrate snapshot state
→ load tail events after snapshot.source_global_position
→ replay tail events through canonical reducer
→ resolved projection state
```

PR4.5 does not prove full semantic equivalence.

It also does not decide the broader runtime action.

It only answers:

```text
Can this resolver reconstruct state from the provided snapshot precondition and tail events?
```

The first implementation may use conservative local compatibility checks such as:

```text
- reducer_version must match the current reducer
- snapshot_schema_version must be supported
- snapshot belongs to the requested order
- state_version must satisfy the current reducer contract
- snapshot payload must hydrate into the current projection state model
- tail event source must satisfy cursor-ordering contract
```

If these checks reject the snapshot:

```text
resolver returns unresolved status
```

The caller may choose to run full accepted-history replay, but that fallback decision is outside the resolver boundary.

PR4.5 should avoid naming these local checks as strong trust.

A better description is:

```text
fast-path eligibility checks
```

These checks can reject obviously unsafe snapshots.

They cannot prove that a structurally valid snapshot equals the state implied by accepted history.

---

### Stage 3 — Future Validation Receipts

A future PR4.x may introduce a persisted validation receipt table.

A possible table could be:

```sql
CREATE TABLE projection_snapshot_validation_receipts (
    receipt_id UUID PRIMARY KEY,
    snapshot_id UUID NOT NULL,
    order_id TEXT NOT NULL,

    source_event_id UUID NOT NULL,
    source_event_sequence INTEGER NOT NULL,
    source_global_position BIGINT NOT NULL,

    snapshot_schema_version INTEGER NOT NULL,
    reducer_version TEXT NOT NULL,
    payload_hash TEXT NOT NULL,

    validation_status TEXT NOT NULL,
    validator_version TEXT NOT NULL,

    authority_state_hash TEXT NULL,
    snapshot_assisted_state_hash TEXT NULL,

    validated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    validated_by TEXT NOT NULL DEFAULT 'system'
);
```

A receipt should be written only when the PR4 validator confirms that the snapshot-assisted path matches authority replay.

Runtime can then check:

```text
receipt exists
receipt.snapshot_id == snapshot.snapshot_id
receipt.order_id == snapshot.order_id
receipt.source_event_id == snapshot.source_event_id
receipt.source_event_sequence == snapshot.source_event_sequence
receipt.source_global_position == snapshot.source_global_position
receipt.snapshot_schema_version == snapshot.snapshot_schema_version
receipt.reducer_version == snapshot.reducer_version
receipt.payload_hash == snapshot.payload_hash
receipt.validation_status == MATCH
```

If these checks pass, runtime may treat the snapshot as authority-validated fast-path evidence.

If they fail, runtime must not treat the snapshot as authority-validated evidence.

Validation receipts are not implemented in PR4.5.

They are a future hardening direction.

---

## Rationale

### 1. Database constraints protect shape, not semantic equivalence

The projection snapshot schema can enforce physical plausibility:

```text
positive source_event_sequence
positive source_global_position
valid state_status
non-negative amounts
state_version not ahead of source_event_sequence
non-empty reducer_version
non-empty payload_hash
```

But it cannot prove:

```text
this snapshot state equals the state implied by accepted history
```

That requires replay semantics.

Therefore, database constraints are necessary but not sufficient.

---

### 2. Lightweight runtime checks cannot prove full correctness

Checks such as:

```text
reducer_version matches
schema version matches
source boundary is physically plausible
payload can be hydrated
```

are useful and cheap.

They can reject obviously unsafe snapshots.

However, they cannot prove that a buggy snapshot builder did not produce a semantically wrong but internally consistent snapshot.

For example, a flawed builder could produce:

```text
source boundary = PAID
state payload = CREATED
payload_hash = hash(CREATED version 2)
```

A payload hash can prove row integrity if implemented correctly.

It cannot prove authority equivalence.

Therefore, lightweight checks should be treated as eligibility checks, not as full semantic proof.

---

### 3. Full replay remains the authority path

The accepted event log remains the source of truth.

If there is doubt, the broader runtime must be able to discard the snapshot and use accepted-history replay.

This preserves the core rule:

```text
accepted history = authority
snapshot = derived / subordinate / discardable
```

---

### 4. Validation receipts preserve performance and trust

A validation receipt allows the project to separate:

```text
expensive proof
```

from:

```text
cheap runtime use
```

The expensive proof is produced by PR4 validator.

The cheap runtime path later checks that the proof still applies to the exact snapshot row.

This avoids two bad extremes:

```text
blindly trust every snapshot
```

and:

```text
full replay on every normal runtime path
```

---

## Alternatives Considered

### Option A — Trust snapshot rows after database constraints

Under this option, runtime would use any latest snapshot that passes database constraints and basic version checks.

#### Benefits

```text
- simplest implementation
- fastest runtime path
- no extra receipt table
- no extra lifecycle state
```

#### Costs

```text
- cannot detect structurally valid but semantically wrong snapshots
- allows corrupted derived state to become runtime input
- contradicts accepted-history authority
- weakens the Snapshot Trust Contract
```

#### Decision

Rejected.

Database shape validity is not enough to trust derived state.

---

### Option B — Run full PR4 validation every time before using snapshot

Under this option, every runtime use of snapshot would perform:

```text
snapshot-assisted replay
vs
full accepted-history replay
```

#### Benefits

```text
- strongest correctness check
- simple trust story
- no separate receipt system required
```

#### Costs

```text
- defeats snapshot replay efficiency
- makes snapshot useless as normal fast path
- turns every runtime read into an expensive audit
```

#### Decision

Rejected for normal runtime.

Full validation remains valuable for audit, debugging, suspicious snapshots, rebuild, and receipt creation.

---

### Option C — Lightweight runtime eligibility checks only

Under this option, PR4.5 introduces a resolver with local eligibility checks but no persisted validation receipt.

#### Benefits

```text
- small implementation step
- keeps resolver logic cleaner
- provides better protection than blind snapshot use
- avoids adding receipt lifecycle immediately
```

#### Costs

```text
- cannot prove that a structurally valid snapshot matches authority replay
- cannot fully protect against buggy snapshot builders
- should not be described as strong trust
```

#### Decision

Accepted as the minimum PR4.5 baseline.

This should be treated as fast-path eligibility, not full trust.

---

### Option D — Persist validation receipts after authority validation

Under this option, PR4 validator writes a receipt when a snapshot matches authority replay.

A later runtime path then uses only snapshots with valid receipts.

#### Benefits

```text
- preserves authority-first trust
- avoids full replay on every normal runtime path
- gives runtime cheap trust evidence
- makes snapshot lifecycle explicit
- supports future audit / governance / SemanticOutcome
```

#### Costs

```text
- adds a receipt table
- adds lifecycle complexity
- requires receipt invalidation / version compatibility rules
- may be more than the minimum PR4.5 baseline
```

#### Decision

Accepted as the preferred hardening direction.

This should be introduced after the basic PR4 validator and PR4.5 resolver are stable.

---

## Consequences

### Positive Consequences

The project avoids treating snapshot rows as self-authenticating facts.

The runtime fast path becomes explicit:

```text
snapshot must satisfy explicit precondition / eligibility checks before use
```

The future strong-trust path becomes explicit:

```text
snapshot must have validation evidence before being called authority-validated
```

This preserves the central architectural boundary:

```text
event log replay = authority path
snapshot-assisted replay = fast path
```

It also prepares the system for later structured outcomes such as:

```text
SNAPSHOT_REPLAY_MISMATCH
SNAPSHOT_HASH_MISMATCH
SNAPSHOT_SCHEMA_UNSUPPORTED
SNAPSHOT_LOGIC_VERSION_UNTRUSTED
SNAPSHOT_BOUNDARY_INVALID
SNAPSHOT_RECEIPT_MISSING
SNAPSHOT_RECEIPT_STALE
```

These are future runtime / receipt / SemanticOutcome candidates.

They are not PR4.5 result statuses.

---

### Negative Consequences

The design introduces another lifecycle concept.

The project must distinguish:

```text
missing snapshot
ineligible snapshot
authority-validated snapshot
stale receipt
invalid receipt
semantic drift
```

This adds conceptual complexity.

However, the complexity is necessary if snapshots are to participate in runtime acceleration without becoming false sources of truth.

---

## PR4.5 Boundary Summary

PR4.5 should implement:

```text
ProjectionSnapshotAssistedStateResolver
```

It should answer:

```text
Given an explicitly qualified snapshot,
can the system reconstruct projection state using snapshot + tail replay
without full accepted-history replay?
```

PR4.5 may include:

```text
- resolver result model
- snapshot-id based loading, if needed
- local compatibility checks
- snapshot state hydration
- tail event loading after snapshot.source_global_position
- tail cursor contract checks
- canonical reducer tail replay
- PostgreSQL integration proof for resolver wiring
```

PR4.5 should not include:

```text
- full authority replay comparison
- persisted validation receipt table
- validation receipt writer
- runtime policy engine
- automatic fallback policy
- automatic snapshot repair
- automatic snapshot quarantine
- Compass Layer 2 SemanticOutcome
- write-side aggregate rehydration
- command admission behavior
```

---

## Relationship to Existing ADRs

This ADR builds on:

```text
ADR 0004 — Why Compass Split into Two Layers
ADR 0005 — Persistent Storage Baseline Strategy
ADR 0007 — Separate Semantic Correctness from Operational Trust
ADR 0008 — Pre-Allocated Event Identity and Candidate/Accepted Event Naming Boundary
ADR 0010 — Separate Transaction Atomicity from Concurrency Admission
ADR 0011 — Separate Validation Mode from Validation Placement Strategy
ADR 0012 — Two-Phase Concurrency Admission for PostgreSQL Write-Side
```

It also supports the Stage 3.5D Snapshot Trust Contract:

```text
accepted history = authority
snapshot = derived state compression
fast path = snapshot + tail replay + eligibility / trust evidence
authority path = full accepted-history replay
```
