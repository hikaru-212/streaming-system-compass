# Stage 4A Closeout — SemanticOutcome Core

[← Back to Stage 4A](README.md)

## Status

```text
Stage 4A — closed
Next stage — Stage 4B / DecisionReceipt and DiagnosticTrace
```

---

## Purpose

This note closes:

```text
Stage 4A — Compass Layer 2 SemanticOutcome Core
```

Stage 4A introduced the first runtime semantic interpretation boundary for the project.

It turns raw runtime correctness evidence into structured `SemanticOutcome` values without turning those outcomes into durable receipts, runtime decisions, execution strategies, retry policies, or recovery actions.

---

## Final Stage 4A Shape

Stage 4A now supports:

```text
technical status
→ SemanticOutcome

read-side validation result
→ SemanticOutcome

snapshot trust / resolver result
→ SemanticOutcome

write-side admission / orchestration result
→ SemanticOutcome
```

The final Stage 4A pipeline is:

```text
runtime technical evidence
→ adapter-specific technical status + boundary + reason + context + evidence
→ map_runtime_technical_status(...)
→ SemanticOutcome
```

This preserves the distinction:

```text
observation
≠
root cause

semantic meaning
≠
runtime decision

replay classification
≠
retry governance
```

---

## Completed PRs

```text
PR1 — Runtime SemanticOutcome Boundary
PR2 — SemanticOutcome Vocabulary / Result Contract
PR3 — Runtime Technical Status Mapping
PR4 — Snapshot / Projection Outcome Mapping
PR5 — Write-Side Admission Outcome Mapping
PR6 — Stage 4A Closeout
```

---

## What Stage 4A Added

### PR1 — Boundary

PR1 defined why `SemanticOutcome` exists and why it must not be collapsed into raw technical status, runtime decision, execution strategy, retry governance, or action safety.

### PR2 — Result Contract

PR2 introduced the in-code `SemanticOutcome` contract and vocabulary:

```text
SemanticOutcome
SemanticOutcomeCategory
SemanticOutcomeCode
SemanticBoundary
SemanticSeverity
SemanticRiskLevel
SemanticReversibility
```

### PR3 — Generic Technical Status Mapping

PR3 introduced:

```text
RuntimeTechnicalStatusMapping
map_runtime_technical_status
supported_runtime_technical_statuses
```

This made semantic mapping explicit, test-visible, and reusable by later adapters.

### PR4 — Read-Side / Snapshot Mapping

PR4 connected read-side and snapshot result objects to `SemanticOutcome`:

```text
ReplayValidationResult
ProjectionSnapshotReplayValidationResult
ProjectionSnapshotAssistedResolutionResult
```

It preserved observation boundary semantics and avoided root-cause inference.

### PR5 — Write-Side Admission Mapping

PR5 connected write-side admission / orchestration evidence to `SemanticOutcome`:

```text
PostgresWriteSideResult
```

It mapped acceptance, replay, idempotency conflict, validation block, concurrency uncertainty, and write-side infrastructure abnormality without changing accepted-history admission behavior.

### PR6 — Closeout

PR6 aligns Stage 4A documentation, test coverage notes, roadmap state, public notes, and Stage 4B checkpoints.

It does not add new runtime behavior.

---

## Final Artifacts

Implementation notes:

```text
docs/implementation_notes/stage_4a/semantic_outcome_boundary.md
docs/implementation_notes/stage_4a/semantic_outcome_result_contract.md
docs/implementation_notes/stage_4a/runtime_technical_status_mapping.md
docs/implementation_notes/stage_4a/drift_validation_cost_boundary.md
docs/implementation_notes/stage_4a/read_side_outcome_mapping.md
docs/implementation_notes/stage_4a/write_side_admission_outcome_mapping.md
docs/implementation_notes/stage_4a/agent_rule_bypass_risk_semantic_mapping_stability.md
docs/implementation_notes/stage_4a/pr4_closeout.md
docs/implementation_notes/stage_4a/pr5_closeout.md
docs/implementation_notes/stage_4a/stage_4a_closeout.md
```

Runtime code:

```text
src/compass/runtime/semantic_outcome.py
src/compass/runtime/technical_status_mapping.py
src/compass/runtime/read_side_outcome_mapping.py
src/compass/runtime/write_side_outcome_mapping.py
src/compass/runtime/__init__.py
```

Runtime tests:

```text
tests/unit/compass/runtime/test_semantic_outcome.py
tests/unit/compass/runtime/test_technical_status_mapping.py
tests/unit/compass/runtime/test_read_side_outcome_mapping.py
tests/unit/compass/runtime/test_write_side_outcome_mapping.py
```

Public / conceptual notes added or aligned around PR6:

```text
docs/semantic_admission/input_guardrails_are_not_admission_boundaries.md
```

---

## Final Supported Outcome Areas

Stage 4A supports semantic interpretation for:

```text
valid replay / resolution
fast-path unavailability
missing authority evidence
snapshot boundary invalidity
snapshot compatibility invalidity
snapshot-assisted drift
read-side drift
write-side accepted candidate
write-side idempotent replay
write-side idempotency conflict
write-side validation block
write-side accepted-history staleness
write-side lock timeout
write-side infrastructure abnormality
```

---

## Important Preserved Boundaries

Stage 4A preserves:

```text
technical status
≠
semantic outcome

SemanticOutcome
≠
DecisionReceipt

SemanticOutcome
≠
RuntimeDecisionPolicy

SemanticOutcome
≠
StrategySelector

SemanticOutcome
≠
RetryGovernance

candidate event
≠
accepted fact

idempotent replay
≠
new accepted candidate

read-side observation
≠
write-side root cause

snapshot failure
≠
proven semantic drift unless comparison completed

write-side infrastructure abnormality
≠
ordinary read-side unresolved observation
```

---

## Identity and Evidence Boundary

Stage 4A establishes that core identity evidence is not ordinary metadata.

In write-side outcome mapping, protected context keys include:

```text
write_side_outcome
order_id
request_id
candidate_event_id
accepted_event_id
```

Caller context cannot contradict adapter-derived protected context.

Internal write-side evidence cannot contradict itself across `order_id` or `request_id` sources.

`ValidationResult.metadata["order_id"]` is not treated as authoritative identity evidence in Stage 4A.

---

## Stage 4B Checkpoints

Stage 4B should revisit the following before implementing durable receipts and traces.

### ValidationResult Identity Contract

Question:

```text
Should ValidationResult promote order_id to a first-class field?
```

Current Stage 4A answer:

```text
Do not change ValidationResult in Stage 4A.
Do not treat metadata["order_id"] as authoritative identity evidence.
Revisit before DecisionReceipt / DiagnosticTrace.
```

Decision criteria:

```text
rejected validation outcomes must be queryable by order_id
validation-only blocked outcomes may not always have stream_admission_result
candidate_event_id alone is insufficient for later correlation
read-side unresolved observations need correlation back to write-side validation failures
rejected candidate evidence may be persisted independently
```

### DecisionReceipt Shape

Stage 4B should define what summary evidence is durable enough for receipt storage.

It should not store every diagnostic path by default.

### DiagnosticTrace Shape

Stage 4B should define how to preserve failure path, partial progress, correlation evidence, and diagnostic context without turning receipts into full traces.

### Failure Model Levels

Stage 4B should decide whether to introduce a public `Failure Model Levels` note or an implementation-facing `Failure Evidence / Lineage Model` note before receipt work.

This should build on the distinction:

```text
failure classification
failure handling
failure evidence
failure lineage
failure genesis
```

### Write-Side Infrastructure Abnormality

Stage 4A maps `WRITE_SIDE_INFRASTRUCTURE_ERROR` to:

```text
ESCALATION_REQUIRED
REQUIRES_OPERATOR_REVIEW
```

Stage 4B+ should decide how receipts, traces, and policies preserve or act on this signal.

Stage 4A does not execute fail-closed behavior.

### ProjectionWorker / Freshness Governance

Stage 4A intentionally does not map ordinary projection worker execution or freshness outcomes.

That belongs to later dual-dimension governance work where semantic correctness and operational freshness are separated.

---

## Non-goals Still Deferred

Stage 4A does not implement:

```text
DecisionReceipt persistence
DiagnosticTrace tables
Measurement Matrix implementation
policy contract YAML
RuntimeDecisionPolicy
StrategySelector
RetryGovernance
automatic retry blocking
operator review execution
Stage 5 action safety gate
agent workflow orchestration
ProjectionWorker governance
rejected candidate table
admission_rejection_records
SQL migrations for receipts or traces
```

---

## Final Validation

Run:

```bash
pytest tests/unit/compass/runtime -q
```

Or:

```bash
pytest tests/unit/compass/runtime/test_semantic_outcome.py \
       tests/unit/compass/runtime/test_technical_status_mapping.py \
       tests/unit/compass/runtime/test_read_side_outcome_mapping.py \
       tests/unit/compass/runtime/test_write_side_outcome_mapping.py -q
```

---

## Closeout Summary

Stage 4A is complete when:

```text
SemanticOutcome contract exists
runtime technical statuses are mapped
read-side and snapshot results are mapped
write-side admission / orchestration results are mapped
mapping stability is documented
identity evidence hardening is documented
Stage 4B checkpoints are recorded
```

At that point, the project can proceed to:

```text
Stage 4B — DecisionReceipt / DiagnosticTrace
```
