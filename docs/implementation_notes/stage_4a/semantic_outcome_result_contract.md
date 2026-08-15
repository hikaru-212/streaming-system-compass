# SemanticOutcome Result Contract

[← Back to Stage 4A](README.md)

## Purpose

This note documents the first in-code result contract introduced by:

```text
Stage 4A PR2 — SemanticOutcome Vocabulary / Result Contract
```

PR2 translates the Stage 4A SemanticOutcome boundary into a minimal runtime contract.

The purpose is to define how runtime correctness evidence can be represented as semantic meaning without collapsing that meaning into runtime decision, execution strategy, retry governance, or durable receipt persistence.

In this model:

```text
SemanticOutcomeCategory = broad semantic family
SemanticOutcomeCode     = precise machine-readable meaning
SemanticBoundary        = where the condition was observed
```

This separation allows the system to preserve both high-level meaning and detailed runtime evidence.

---

## Contract Boundary

A `SemanticOutcome` answers:

```text
What semantic condition was observed?
Where was it observed?
How severe is it?
How risky is it?
Is it reversible, rebuildable, compensable, irreversible, or unknown?
What context and evidence support this interpretation?
```

A `SemanticOutcome` does not answer:

```text
What runtime action should be executed?
Which recovery path should be used?
Which execution strategy is cheapest or healthiest?
Whether retry is allowed?
Whether a durable receipt has already been written?
```

Those responsibilities belong to later Stage 4 components.

---

## Runtime Contract Fields

PR2 introduces a frozen runtime contract with fields equivalent to:

```text
outcome_id
ok
boundary
category
semantic_code
severity
risk_level
reversibility
reason
context
evidence
```

The contract uses a native UUID for `outcome_id`.

This keeps runtime semantic identity compatible with later durable receipts and avoids treating semantic outcome identity as an untyped string.

The contract also defensively copies and freezes `context` and `evidence` for common container types.

This prevents outcome evidence from being mutated through the original input objects after construction.

---

## Category vs Code

A semantic outcome category describes the broad family of a runtime condition.

A semantic outcome code describes the more precise machine-readable meaning within that family.

They are intentionally not one-to-one.

For example:

```text
category = DRIFT
semantic_code = DRIFT_DETECTED
```

or:

```text
category = FALLBACK_REQUIRED
semantic_code = FAST_PATH_UNAVAILABLE
```

or:

```text
category = INTENT_INCONSISTENT
semantic_code = INTENT_DRIFT_DETECTED
```

This prevents the system from hiding important semantic differences behind a single generic error label.

It also prevents downstream policy from depending directly on raw technical exception strings.

---

## SemanticOutcomeCategory

`SemanticOutcomeCategory` represents broad semantic families.

The initial vocabulary is:

```text
VALID
UNRESOLVED
UNTRUSTED
DRIFT
FALLBACK_REQUIRED
REBUILD_REQUIRED
BLOCK_REQUIRED
ESCALATION_REQUIRED
CONCURRENCY_UNCERTAIN
RETRY_CLASSIFIED
INTENT_INCONSISTENT
```

A category should not directly decide:

```text
which action to execute
whether retry is allowed
which strategy is cheapest
whether fallback should be used
whether a durable receipt has already been written
```

Those decisions belong to later policy, strategy, retry governance, and receipt layers.

---

## SemanticOutcomeCode

`SemanticOutcomeCode` represents precise machine-readable semantic meaning.

The initial vocabulary is:

```text
SEMANTICALLY_VALID
RUNTIME_UNRESOLVED
DERIVED_STATE_UNTRUSTED
DRIFT_DETECTED
FAST_PATH_UNAVAILABLE
REQUIRES_AUTHORITY_FALLBACK
REQUIRES_REBUILD
REQUIRES_OPERATOR_REVIEW
REJECT_DOWNSTREAM_USAGE
CONCURRENCY_UNCERTAIN
IDEMPOTENT_REPLAY_ALLOWED
SEMANTIC_CONFLICT_DETECTED
INTENT_DRIFT_DETECTED
```

A code should describe the meaning of observed evidence.

It should not directly execute recovery, select runtime strategy, persist a receipt, or authorize retry.

---

## SemanticBoundary

`SemanticBoundary` records where the semantic condition was observed or applies.

The initial vocabulary is:

```text
LAYER_1_WRITE_SIDE
LAYER_2_READ_SIDE
SNAPSHOT_TRUST
IDEMPOTENCY
CONCURRENCY_ADMISSION
RUNTIME_GOVERNANCE
```

The same semantic code may appear under different boundaries.

For example, a semantic conflict may be observed at an idempotency boundary, a write-side admission boundary, or a runtime governance boundary.

The boundary is what makes the meaning operationally interpretable.

---

## Severity, Risk, and Reversibility

PR2 also introduces supporting vocabularies:

```text
SemanticSeverity
SemanticRiskLevel
SemanticReversibility
```

These fields are evidence for later policy and strategy layers.

They do not make decisions by themselves.

For example:

```text
severity = ERROR
risk_level = HIGH
reversibility = REBUILDABLE
```

means the outcome is serious and may be recoverable through rebuild-like mechanisms.

It does not mean Stage 4A should execute rebuild.

That decision belongs to a later RuntimeDecisionPolicy.

---

## Fast-Path Failure vs Drift

PR2 preserves an important distinction:

```text
TAIL_REPLAY_FAILED
≠
SNAPSHOT_ASSISTED_DRIFT
```

A tail replay failure means the current fast path or resolution path failed or became unavailable.

It can be represented as:

```text
category = FALLBACK_REQUIRED
semantic_code = FAST_PATH_UNAVAILABLE
```

By contrast, snapshot-assisted drift means snapshot-assisted reconstruction diverged from what accepted history implies.

It can be represented as:

```text
category = DRIFT
semantic_code = DRIFT_DETECTED
```

This distinction prevents infrastructure / replay-path failure from being collapsed into semantic corruption.

---

## Intent Consistency Is a Family

Intent inconsistency should be treated as a broad family of problems.

It means that a request identity, declared intent, semantic fingerprint, or candidate action no longer aligns with the semantic contract expected by the system.

Different evidence may later produce different precise codes under this family.

This distinction matters because operation-level change, semantic-content conflict, idempotency conflict, and agent intent drift are not always the same failure.

---

## Semantic Conflict Is Not Identifier Equality

A semantic conflict should not be detected merely because two records share the same identifier, product, user, event type, or operation name.

A better definition is:

```text
A semantic conflict exists when a candidate action, fingerprint, or fact
cannot coexist with the relevant semantic contract, accepted history,
or domain invariant.
```

This means semantic conflict is about whether business facts can safely coexist, not whether two fields happen to have the same value.

---

## Identity Boundaries

The model keeps several identities separate:

```text
request identity
event identity
aggregate identity
semantic fingerprint
semantic outcome identity
domain authority
```

These should not be collapsed into one concept.

A request identity is used to reason about retries and duplicate logical requests.

An event identity is used to identify accepted events.

An aggregate identity is used to group business history.

A semantic fingerprint summarizes the meaning of a request.

A semantic outcome identity identifies a semantic interpretation record.

Domain authority determines whether a candidate fact can be accepted.

Keeping these layers separate prevents the system from confusing retry handling, event deduplication, aggregate state validation, semantic interpretation, and accepted business truth.

---

## Derived State and Authority Must Remain Separate

A core Compass principle is that derived state should not be treated as authority.

Read-side state, projection state, cached state, or snapshot-assisted state may be useful for speed, but they must remain subordinate to accepted history.

Therefore, a semantic outcome should be able to distinguish between:

```text
a valid derived state
an unavailable fast path
an untrusted derived state
a detected drift
a required rebuild
an authority fallback
```

These are different semantic meanings and should not be collapsed into one generic failure.

---

## Non-goals

PR2 does not implement:

```text
technical status mapping
ProjectionSnapshotReplayValidationStatus mapping
ProjectionSnapshotAssistedResolutionStatus mapping
write-side admission mapping
DecisionReceipt
DiagnosticTrace
Measurement Matrix
policy contract YAML
RuntimeDecisionPolicy
StrategySelector
RetryGovernance
SQL migrations
durable receipt store
```

PR2 defines the result contract only.

---

## Design Principle

The central rule is:

```text
Do not collapse evidence into action too early.
```

A semantic outcome should preserve meaning.

A policy layer should decide action.

A receipt layer should preserve explanation.

A strategy layer should choose among semantically allowed execution paths.

A retry governance layer should classify attempts after semantic outcome exists.

---

## Summary

PR2 establishes:

```text
Category = broad semantic family
Code     = precise machine-readable meaning
Boundary = where the evidence was observed
```

A category may map to multiple codes.

A code may appear under different boundaries.

A semantic conflict is not detected by identifier equality alone.

Intent inconsistency is not always the same as intent drift.

Derived state is not authority.

Runtime evidence should be interpreted before any recovery, retry, fallback, blocking, or strategy decision is made.
