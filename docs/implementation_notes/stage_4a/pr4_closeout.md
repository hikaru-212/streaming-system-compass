# Stage 4A PR4 Closeout — Snapshot / Projection Outcome Mapping

[← Back to Stage 4A](README.md)

## Status

Stage 4A PR4 is complete at the read-side outcome mapping level.

PR4 connects existing projection validation, snapshot trust validation, and snapshot-assisted resolution result objects to the Stage 4A `SemanticOutcome` contract.

---

## Implemented Boundary

PR4 adds the read-side outcome mapping adapter:

```text
src/compass/runtime/read_side_outcome_mapping.py
tests/unit/compass/runtime/test_read_side_outcome_mapping.py
docs/implementation_notes/stage_4a/read_side_outcome_mapping.md
```

The adapter maps:

```text
ReplayValidationResult
ProjectionSnapshotReplayValidationResult
ProjectionSnapshotAssistedResolutionResult
```

into:

```text
SemanticOutcome
```

through the generic PR3 mapper:

```text
map_runtime_technical_status(...)
```

---

## What PR4 Proves

PR4 proves that Stage 3.5 read-side / snapshot result objects can be translated into Stage 4A semantic meaning without collapsing into later governance layers.

It covers:

```text
projection replay validation
snapshot-assisted replay validation
snapshot-assisted resolution
```

It preserves:

```text
technical_status
observation boundary
reason
context
evidence
result source type
state-presence evidence
```

---

## Observation Boundary vs Root Cause Boundary

The key closeout decision is:

```text
SemanticBoundary records where the condition was observed.
It does not prove the original root cause.
```

Therefore:

```text
ReplayValidationStatus.NO_ACCEPTED_HISTORY
observed by DurableReplayValidator
→ boundary = LAYER_2_READ_SIDE
```

and:

```text
ProjectionSnapshotReplayValidationStatus.NO_ACCEPTED_HISTORY_FOR_ORDER
observed by ProjectionSnapshotReplayValidator
→ boundary = SNAPSHOT_TRUST
```

These are not Layer 1 write-side root-cause claims.

They mean that authority evidence is unavailable for the requested read-side or snapshot-trust validation boundary.

A future write-side admission receipt may explain why no accepted event exists.

PR4 does not infer that root cause.

---

## Tail Source Contract Violation Boundary

PR4 also preserves this distinction:

```text
TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
≠
SNAPSHOT_ASSISTED_DRIFT
```

A tail source contract violation means:

```text
snapshot boundary state may exist
authority state may exist
tail replay did not safely complete
```

Therefore the result is:

```text
RUNTIME_UNRESOLVED
```

not:

```text
DRIFT_DETECTED
```

Drift requires a completed snapshot-assisted replay comparison against authority replay.

If the tail source violates its contract, that comparison precondition is not satisfied.

---

## Resolver vs Validator Boundary

PR4 keeps the full validator and the resolver conceptually separate.

`ProjectionSnapshotReplayValidator` may produce:

```text
authority_state
snapshot_assisted_state
```

because it performs full authority comparison.

`ProjectionSnapshotAssistedStateResolver` produces:

```text
resolved_state
```

because it consumes a pre-qualified snapshot identity and does not perform full accepted-history replay.

PR4 mapping reflects that difference through evidence shape:

```text
authority_state_present
snapshot_assisted_state_present
resolved_state_present
```

---

## Deferred Projection Worker Mapping

PR4 intentionally does not map ordinary projection worker execution outcomes.

Projection validation answers:

```text
Does derived read-side state match accepted-history authority?
```

Projection worker execution answers:

```text
Is the projection runtime currently processing accepted events successfully and freshly?
```

These are related but different boundaries.

Projection worker freshness evidence is deferred to Stage 5+ / later dual-dimension governance work.

The future direction is:

```text
semantic correctness
×
operational freshness / runtime trust
→
action safety
```

Projection validation belongs to semantic correctness.

Projection worker freshness belongs to operational freshness / runtime trust.

Action safety may eventually need both.

---

## Non-goals Preserved

PR4 does not implement:

```text
write-side admission mapping
root-cause inference
DecisionReceipt
DiagnosticTrace
Measurement Matrix
RuntimeDecisionPolicy
StrategySelector
RetryGovernance
fallback execution
rebuild execution
snapshot quarantine
projection repair
projection worker execution mapping
SQL migrations
durable receipt store
```

---

## Relationship to PR5

PR5 should add:

```text
Layer 1 write-side admission rejection
→ SemanticOutcome
```

PR5 should not rewrite PR4 read-side / snapshot outcomes as Layer 1 outcomes.

The intended model is:

```text
write-side outcome
= possible upstream cause

read-side / snapshot outcome
= downstream observation / symptom
```

The correlation belongs to later receipt and trace layers.

Stage 4A remains a mapping layer:

```text
technical evidence
→ SemanticOutcome
```

It does not perform root-cause reasoning.

---

## Completion Statement

PR4 completes the read-side / snapshot adapter portion of Stage 4A.

After PR4, Stage 4A has:

```text
PR1 — Runtime SemanticOutcome Boundary
PR2 — SemanticOutcome Result Contract
PR3 — Runtime Technical Status Mapping
PR4 — Read-Side / Snapshot Outcome Mapping
```

The next planned PR is:

```text
PR5 — Write-Side Admission Outcome Mapping
```
