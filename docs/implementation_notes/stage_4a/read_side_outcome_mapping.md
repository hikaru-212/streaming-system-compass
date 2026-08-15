# Read-Side Outcome Mapping

[← Back to Stage 4A Implementation Notes](README.md)

## Purpose

This note defines the implementation boundary for:

```text
Stage 4A PR4 — Projection Validation / Snapshot Trust Outcome Mapping
```

PR4 connects existing read-side validation and snapshot-trust result objects to the Stage 4A `SemanticOutcome` contract.

The goal is:

```text
read-side runtime result
→ technical status + boundary + reason + context + evidence
→ SemanticOutcome
```

PR4 does not introduce a new validator.

PR4 does not introduce a new policy engine.

PR4 does not execute recovery.

PR4 only adapts existing read-side correctness evidence into the shared semantic outcome vocabulary established by Stage 4A PR1 through PR3.

---

## Scope

PR4 maps the following result objects into `SemanticOutcome`:

```text
ReplayValidationResult
ProjectionSnapshotReplayValidationResult
ProjectionSnapshotAssistedResolutionResult
```

These correspond to:

```text
DurableReplayValidator
ProjectionSnapshotReplayValidator
ProjectionSnapshotAssistedStateResolver
```

The expected production module is:

```text
src/compass/runtime/read_side_outcome_mapping.py
```

The expected unit test module is:

```text
tests/unit/compass/runtime/test_read_side_outcome_mapping.py
```

---

## Mapping Flow

PR4 uses the generic mapper introduced in PR3:

```text
map_runtime_technical_status(...)
```

The adapter is responsible for extracting:

```text
technical_status
boundary
reason
context
evidence
```

from concrete read-side result objects.

The generic PR3 mapper is still responsible for converting the technical status into:

```text
ok
category
semantic_code
severity
risk_level
reversibility
```

This preserves the Stage 4A separation:

```text
adapter-specific result object
≠
generic technical status mapping
≠
runtime decision
```

---

## Mapped Boundaries

### Durable Replay Validation

`ReplayValidationResult` maps to:

```text
boundary = LAYER_2_READ_SIDE
```

because `DurableReplayValidator` validates persisted projection state against accepted-history replay.

It answers:

```text
Does durable read-side projection state match accepted-history authority?
```

It does not answer:

```text
Why did accepted history or candidate admission behave that way?
```

### Projection Snapshot Replay Validation

`ProjectionSnapshotReplayValidationResult` maps to:

```text
boundary = SNAPSHOT_TRUST
```

because `ProjectionSnapshotReplayValidator` evaluates whether snapshot-assisted replay can be trusted against accepted-history authority replay.

It answers:

```text
Does snapshot + tail replay agree with full accepted-history replay?
```

### Projection Snapshot-Assisted Resolution

`ProjectionSnapshotAssistedResolutionResult` maps to:

```text
boundary = SNAPSHOT_TRUST
```

because `ProjectionSnapshotAssistedStateResolver` consumes an externally qualified snapshot boundary and attempts to resolve read-side projection state through snapshot + tail replay.

It answers:

```text
Given a qualified snapshot boundary, can read-side state be resolved through snapshot + tail replay?
```

It does not prove authority equivalence by itself.

---

## Observation Boundary vs Root Cause Boundary

PR4 preserves an important semantic distinction:

```text
SemanticBoundary records where the condition was observed.
It does not prove the original root cause.
```

For example, when `DurableReplayValidator` returns:

```text
NO_ACCEPTED_HISTORY
```

the outcome remains scoped to:

```text
boundary = LAYER_2_READ_SIDE
```

because the condition was observed while validating read-side derived state against accepted-history authority evidence.

Similarly, when `ProjectionSnapshotReplayValidator` returns:

```text
NO_ACCEPTED_HISTORY_FOR_ORDER
```

the outcome remains scoped to:

```text
boundary = SNAPSHOT_TRUST
```

because the condition was observed while attempting to establish snapshot-assisted replay trust.

These outcomes do not claim that Layer 1 write-side admission failed.

They only claim that the current read-side or snapshot-trust boundary cannot establish authority-backed validation because accepted-history evidence is unavailable for the requested order.

A future Layer 1 write-side outcome may explain why no accepted event exists, such as:

```text
candidate event rejected
request never submitted
domain invariant violation
proof mismatch
idempotency conflict
```

However, that root-cause relationship should be established later through `DecisionReceipt`, `DiagnosticTrace`, `ResolutionTrace`, or another correlation mechanism.

PR4 must remain conservative:

```text
read-side / snapshot observation
→ RUNTIME_UNRESOLVED
```

It must not infer:

```text
read-side missing authority evidence
→ write-side failure
```

Root-cause correlation is deferred to later Stage 4B+ evidence and trace layers.

---

## No Accepted History Boundary

A read-side or snapshot validator may observe:

```text
NO_ACCEPTED_HISTORY
NO_ACCEPTED_HISTORY_FOR_ORDER
```

This means:

```text
accepted-history authority evidence is unavailable for this validation scope
```

It does not automatically mean:

```text
Layer 1 write-side admission failed
```

Possible explanations include:

```text
the order was never requested
the order_id is wrong
test data was not created
a candidate event was rejected
a transaction rolled back
a snapshot artifact is orphaned
an accepted-history query condition is wrong
a cleanup process removed authority evidence from the test fixture
```

Therefore PR4 maps these statuses conservatively to:

```text
category = UNRESOLVED
semantic_code = RUNTIME_UNRESOLVED
```

A future write-side admission outcome may provide an upstream cause, but PR4 should not guess that cause.

---

## Tail Source Contract Violation Boundary

`TAIL_EVENT_SOURCE_CONTRACT_VIOLATION` is not drift evidence.

In the snapshot replay validator, this status means:

```text
snapshot boundary state exists
authority state may exist
tail event source contract failed
snapshot-assisted replay could not safely complete
```

Therefore the mapping remains:

```text
category = UNRESOLVED
semantic_code = RUNTIME_UNRESOLVED
```

even if:

```text
snapshot_assisted_state != authority_state
```

The reason is that the snapshot-assisted path did not finish. The observed state difference is not a completed comparison result.

The completed drift comparison is represented by:

```text
SNAPSHOT_ASSISTED_DRIFT
→ DRIFT_DETECTED
```

A tail source contract violation should not be collapsed into snapshot-assisted drift.

---

## Full Replay Validator vs Assisted Resolver

PR4 keeps the snapshot validator and snapshot resolver separate.

### ProjectionSnapshotReplayValidator

This is a full authority replay validator.

It may produce:

```text
authority_state
snapshot_assisted_state
```

because it compares:

```text
snapshot + tail replay
vs
full accepted-history replay
```

For example:

```text
MISSING_SNAPSHOT:
snapshot_assisted_state = None
authority_state = reconstructed from accepted history

TAIL_EVENT_SOURCE_CONTRACT_VIOLATION:
snapshot_assisted_state = snapshot boundary state
authority_state = reconstructed from accepted history
```

### ProjectionSnapshotAssistedStateResolver

This is a resolver / fast-path primitive.

It consumes an externally qualified snapshot identity.

It does not perform full accepted-history replay.

Its primary state output is:

```text
resolved_state
```

It does not produce:

```text
authority_state
```

Therefore resolver outcomes should not pretend to have authority comparison evidence.

---

## Reason Preservation

PR4 keeps result reasons when they are present.

If a source result provides a blank or missing reason, the adapter uses a conservative fallback:

```text
Missing explicit reason from <ResultType>.
```

This avoids silently normalizing missing source evidence into a generic message without lineage.

The fallback is not a root-cause inference.

It only records which result type failed to provide an explicit reason.

---

## Non-goals

PR4 does not implement:

```text
Layer 1 write-side admission mapping
ordinary ProjectionWorker execution mapping
DecisionReceipt
DiagnosticTrace
ResolutionTrace
Measurement Matrix
RuntimeDecisionPolicy
StrategySelector
RetryGovernance
ActionSafetyGate
fallback execution
rebuild execution
snapshot quarantine
receipt persistence
SQL migrations
root-cause inference
```

---

## Projection Worker Freshness Deferral

Projection worker execution evidence is intentionally not part of PR4.

PR4 maps validation and resolver result objects, not ordinary worker execution outcomes.

Projection validation and projection worker execution are different boundaries:

```text
Projection validation:
Does derived read-side state match accepted-history authority?

Projection worker execution:
Is the projection runtime currently processing accepted events successfully and freshly?
```

Therefore:

```text
projection worker failure ≠ projection drift
projection lag ≠ semantic corruption
projection freshness ≠ accepted-history authority
```

Projection worker freshness evidence belongs to a future Stage 5+ operational freshness / runtime trust line.

It may later support dual-dimension governance:

```text
semantic correctness
×
operational freshness / runtime trust
→
action safety
```

But it should not be added to Stage 4A PR4.

---

## Completion Result

PR4 is complete when the system can map read-side correctness evidence into `SemanticOutcome` without crossing into decision or recovery behavior.

The completed PR4 pipeline is:

```text
DurableReplayValidator
ProjectionSnapshotReplayValidator
ProjectionSnapshotAssistedStateResolver
→ read-side outcome adapter
→ map_runtime_technical_status(...)
→ SemanticOutcome
```

The important result is:

```text
read-side / snapshot correctness evidence
now speaks the same SemanticOutcome vocabulary
as the rest of Stage 4A.
```

PR4 prepares the way for PR5:

```text
Layer 1 write-side admission rejection
→ SemanticOutcome
```

without changing the meaning of read-side or snapshot observations.
