# Runtime Technical Status Mapping

[← Back to Stage 4A](README.md)

## Purpose

This note documents the mapping introduced by:

```text
Stage 4A PR3 — Runtime Technical Status Mapping
```

PR3 converts selected raw runtime technical statuses into structured `SemanticOutcome` values.

It is the first mapping layer after the core `SemanticOutcome` contract.

PR3 answers:

```text
Given a raw technical status name,
what semantic outcome should it represent?
```

It does not answer:

```text
What runtime action should be executed?
Which fallback path should be selected?
Should a durable receipt be written?
Should retry be allowed?
Which strategy is cheapest or healthiest?
```

Those responsibilities belong to later Stage 4 components.

---

## Scope

PR3 adds a generic runtime technical status mapper:

```text
technical_status string / enum
+ boundary
+ reason
+ context
+ evidence
→ SemanticOutcome
```

The mapper is intentionally generic.

It does not import or inspect adapter-specific result objects such as projection validators, snapshot validators, admission validators, or retry attempt records.

Adapter-specific mapping belongs to later PRs.

---

## Added Runtime Contract

PR3 introduces:

```text
RuntimeTechnicalStatusMapping
map_runtime_technical_status
supported_runtime_technical_statuses
```

`RuntimeTechnicalStatusMapping` records the semantic fields that can be determined from a technical status alone:

```text
ok
category
semantic_code
severity
risk_level
reversibility
```

The caller still supplies:

```text
outcome_id
boundary
reason
context
evidence
```

Those fields are not part of the static mapping rule because they depend on where and why the status was produced.

---

## Supported Initial Statuses

PR3 supports the first generic set of runtime technical statuses:

```text
MATCH
RESOLVED_FROM_SNAPSHOT
MISSING_SNAPSHOT
MISSING_PROJECTION
NO_ACCEPTED_HISTORY
NO_ACCEPTED_HISTORY_FOR_ORDER
INVALID_SNAPSHOT_BOUNDARY
INVALID_SNAPSHOT_PRECONDITION
INVALID_SNAPSHOT_COMPATIBILITY
TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
TAIL_REPLAY_FAILED
DRIFT
SNAPSHOT_ASSISTED_DRIFT
OCC_CONFLICT_AFTER_VALIDATION
LOCK_TIMEOUT
IDEMPOTENT_REPLAY
IDEMPOTENCY_CONFLICT
```

The list is intentionally small and should evolve through later adapter-specific PRs.

---

## Mapping Families

### Valid statuses

```text
MATCH
RESOLVED_FROM_SNAPSHOT
```

map to:

```text
category = VALID
semantic_code = SEMANTICALLY_VALID
```

These statuses mean the technical evidence is semantically acceptable at the boundary that produced it.

They do not prove that downstream action is allowed.

---

### Fast-path unavailable statuses

```text
MISSING_SNAPSHOT
TAIL_REPLAY_FAILED
```

map to:

```text
category = FALLBACK_REQUIRED
semantic_code = FAST_PATH_UNAVAILABLE
```

These statuses mean the current fast path cannot be used.

They do not automatically imply data corruption, snapshot corruption, or semantic drift.

---

### Derived-state untrusted statuses

```text
INVALID_SNAPSHOT_BOUNDARY
INVALID_SNAPSHOT_PRECONDITION
INVALID_SNAPSHOT_COMPATIBILITY
```

map to:

```text
category = UNTRUSTED
semantic_code = DERIVED_STATE_UNTRUSTED
```

These statuses mean the derived state or snapshot boundary should not be trusted without later recovery or rebuild logic.

PR3 does not execute that recovery.

---

### Runtime unresolved statuses

```text
NO_ACCEPTED_HISTORY
NO_ACCEPTED_HISTORY_FOR_ORDER
TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
```

map to:

```text
category = UNRESOLVED
semantic_code = RUNTIME_UNRESOLVED
```

`NO_ACCEPTED_HISTORY` and `NO_ACCEPTED_HISTORY_FOR_ORDER` are intentionally mapped conservatively in PR3.

They may describe different future domain situations, such as global cold start versus one aggregate with no accepted history.

PR3 preserves the original `technical_status` in evidence so later policy or adapter layers can distinguish them without making PR3 domain-aware.

---

### Drift statuses

```text
DRIFT
SNAPSHOT_ASSISTED_DRIFT
```

map to:

```text
category = DRIFT
semantic_code = DRIFT_DETECTED
```

Both statuses mean a derived result diverged from authority.

They differ by source and boundary.

`DRIFT` is the generic derived-state drift status.

For read-side projection validation, it usually means:

```text
persisted projection state
≠
accepted-history replay for the same aggregate
```

`SNAPSHOT_ASSISTED_DRIFT` means:

```text
snapshot + tail replay
≠
full accepted-history replay
```

Both can share `DRIFT_DETECTED` while remaining distinguishable through `boundary` and `evidence["technical_status"]`.

---

### Concurrency uncertainty statuses

```text
OCC_CONFLICT_AFTER_VALIDATION
LOCK_TIMEOUT
```

map to:

```text
category = CONCURRENCY_UNCERTAIN
semantic_code = CONCURRENCY_UNCERTAIN
```

These statuses mean previously computed evidence may not be safely reusable without reload, revalidation, or later retry governance.

PR3 does not decide retry behavior.

---

### Idempotency statuses

```text
IDEMPOTENT_REPLAY
```

maps to:

```text
category = RETRY_CLASSIFIED
semantic_code = IDEMPOTENT_REPLAY_ALLOWED
```

This describes a safe idempotent replay classification.

It does not itself execute replay.

```text
IDEMPOTENCY_CONFLICT
```

maps conservatively to:

```text
category = BLOCK_REQUIRED
semantic_code = SEMANTIC_CONFLICT_DETECTED
```

This status is intentionally coarse in PR3.

PR3 does not inspect operation mismatch, fingerprint mismatch, stored request evidence, or incoming request evidence.

Later write-side admission / idempotency adapters may split this into more precise statuses such as:

```text
IDEMPOTENCY_OPERATION_MISMATCH
→ INTENT_INCONSISTENT / INTENT_DRIFT_DETECTED

IDEMPOTENCY_FINGERPRINT_MISMATCH
→ INTENT_INCONSISTENT / SEMANTIC_CONFLICT_DETECTED
```

That split belongs to adapter-specific mapping or retry governance, not this generic mapper.

---

## Fast-Path Failure Is Not Drift

PR3 preserves an important distinction:

```text
TAIL_REPLAY_FAILED
≠
SNAPSHOT_ASSISTED_DRIFT
```

A tail replay failure means the current resolution path failed or became unavailable.

It maps to:

```text
FAST_PATH_UNAVAILABLE
```

By contrast, snapshot-assisted drift means snapshot-assisted reconstruction diverged from accepted-history authority.

It maps to:

```text
DRIFT_DETECTED
```

This prevents infrastructure or replay-path failure from being collapsed into semantic corruption.

---

## Evidence Handling

The mapper always preserves the mapped technical status in evidence:

```text
evidence["technical_status"] = normalized_status
```

If the caller passes evidence containing a different `technical_status`, the mapper rejects it.

This prevents contradictory semantic evidence such as:

```text
technical_status argument = MATCH
evidence["technical_status"] = TAIL_REPLAY_FAILED
```

PR3 also preserves caller-provided context and evidence.

The resulting `SemanticOutcome` contract defensively freezes context and evidence according to the PR2 result contract.

---

## Deferred Layer 1 Admission Rejection Mapping

PR3 includes some write-side adjacent statuses, such as idempotency and concurrency statuses.

However, it does not implement the explicit Layer 1 admission rejection line:

```text
Layer 1 write-side admission rejection
→ SemanticOutcome
```

That line belongs to PR5.

PR5 should preserve these boundaries:

```text
Layer 1 protects accepted history.
Stage 4A mapping explains why a candidate was rejected.
Rejected candidates remain outside accepted history.
SemanticOutcome makes rejection machine-readable,
but it does not decide retry, persistence, or recovery.
```

Stage 4A should not introduce rejected candidate tables, rejected event logs, admission rejection records, durable receipt writing, retry governance, or agent policy decisions.

---

## Cost Boundary Pointer

`DRIFT` and `SNAPSHOT_ASSISTED_DRIFT` are both semantic drift signals, but they do not imply the same validation cost.

Order-scoped projection drift validation may be cheap when replay is scoped by aggregate identity.

Snapshot trust validation can be more expensive when it requires authority replay to bootstrap trust.

See:

```text
Drift Validation Cost Boundary
```

for the cost distinction between projection-state drift validation, snapshot-assisted drift validation, and global projection consistency checks.

---

## Non-goals

PR3 does not implement:

```text
ProjectionSnapshotReplayValidationResult adapter
ProjectionSnapshotAssistedResolutionResult adapter
DurableReplayValidationResult adapter
write-side admission rejection adapter
DecisionReceipt
DiagnosticTrace
Measurement Matrix
policy contract YAML
RuntimeDecisionPolicy
StrategySelector
RetryGovernance
SQL migrations
durable receipt store
fallback execution
rebuild execution
quarantine mechanism
```

PR3 only maps raw technical status names into `SemanticOutcome`.

---

## Summary

PR3 establishes the first generic mapping layer:

```text
technical_status
→ RuntimeTechnicalStatusMapping
→ SemanticOutcome
```

It preserves:

```text
technical status evidence
boundary supplied by caller
reason supplied by caller
context supplied by caller
category / code / severity / risk / reversibility mapping
```

It does not collapse semantic meaning into runtime decision, strategy, retry, receipt persistence, or rejected-candidate history.
