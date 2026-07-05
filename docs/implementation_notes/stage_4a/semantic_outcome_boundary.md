# Runtime SemanticOutcome Boundary

[← Back to Stage 4A](README.md)

## Purpose

This note defines the implementation boundary for:

```text
Stage 4A PR1 — Runtime SemanticOutcome Boundary
```

Stage 4A introduces the first Compass Layer 2 runtime semantic concept:

```text
SemanticOutcome
```

The goal is not to make a runtime decision yet.

The goal is to separate technical execution results from semantic interpretation.

---

## Core Rule

```text
technical status
≠
semantic outcome
```

A technical status says what a component observed or completed.

A semantic outcome says what that observation means for correctness, trust, risk, or downstream usage.

For example:

```text
MATCH
= technical validator status

SEMANTICALLY_VALID
= semantic interpretation under a specific boundary
```

Another example:

```text
TAIL_REPLAY_FAILED
= technical resolver failure

RUNTIME_UNRESOLVED
or
REQUIRES_AUTHORITY_FALLBACK
= semantic interpretation
```

The mapping is not always one-to-one.

The same technical status may imply different semantic outcomes depending on boundary, evidence, freshness, authority source, or failure context.

---

## Why Technical Status Is Not Enough

Raw technical statuses are useful for tests and component contracts.

They are not enough for runtime governance.

Examples of technical statuses include:

```text
MATCH
MISSING_SNAPSHOT
NO_ACCEPTED_HISTORY_FOR_ORDER
INVALID_SNAPSHOT_BOUNDARY
SNAPSHOT_ASSISTED_DRIFT
RESOLVED_FROM_SNAPSHOT
INVALID_SNAPSHOT_PRECONDITION
INVALID_SNAPSHOT_COMPATIBILITY
TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
TAIL_REPLAY_FAILED
OCC_CONFLICT_AFTER_VALIDATION
LOCK_TIMEOUT
IDEMPOTENT_REPLAY
IDEMPOTENCY_CONFLICT
```

These statuses answer questions such as:

```text
Did the validator match authority replay?
Was a snapshot missing?
Did tail replay fail?
Did optimistic concurrency lose?
Was the request an idempotent replay?
```

They do not fully answer:

```text
Is the runtime result semantically safe to use?
Is derived state trusted?
Is fallback required?
Is rebuild required?
Should downstream usage be blocked?
Is the failure reversible?
Does the same request identity still preserve the same intent?
```

Stage 4A begins answering those semantic questions.

---

## SemanticOutcome Responsibility

A SemanticOutcome should describe the meaning of runtime evidence.

It may capture:

```text
semantic code
boundary / layer
severity
risk level
reversibility
human-readable reason
context summary
evidence summary
```

It may eventually reference policy or recovery hints after a policy contract exists.

However, Stage 4A should not require policy contracts yet.

The first responsibility is semantic interpretation.

---

## Candidate Semantic Meanings

Stage 4A may introduce or refine semantic meanings such as:

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

These names are candidates until implementation settles the exact enum / code vocabulary.

The vocabulary should remain small enough to test and reason about.

It should not become a large catalog of every possible exception string.

---

## Outcome Category Boundary

A first implementation may group outcomes into categories such as:

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

The category should describe broad semantic meaning.

The semantic code should describe the more specific case.

For example:

```text
category = DRIFT
semantic_code = SEMANTIC_PROJECTION_DRIFT
```

or:

```text
category = FALLBACK_REQUIRED
semantic_code = SNAPSHOT_FAST_PATH_UNAVAILABLE
```

or:

```text
category = INTENT_INCONSISTENT
semantic_code = IDEMPOTENCY_CONFLICT
```

This keeps the model structured without forcing every downstream policy to match raw technical statuses.

---

## SemanticOutcome Is Not RuntimeDecision

```text
semantic outcome
≠
runtime decision
```

A SemanticOutcome describes what the runtime evidence means.

A RuntimeDecision decides what the system should do.

For example:

```text
SemanticOutcome:
DRIFT_DETECTED

Possible later RuntimeDecision:
REBUILD
or
QUARANTINE
or
ESCALATE
```

Another example:

```text
SemanticOutcome:
FAST_PATH_UNAVAILABLE

Possible later RuntimeDecision:
FALLBACK_TO_AUTHORITY
```

Stage 4A may say that fallback is semantically required.

It should not implement the policy that chooses and executes the fallback.

That belongs to Stage 4C and Stage 4D.

---

## SemanticOutcome Is Not StrategySelector

```text
runtime decision
≠
execution strategy
```

A later RuntimeDecision may say:

```text
FALLBACK_TO_AUTHORITY
```

But the system may still need to choose how to perform that fallback.

Examples:

```text
full accepted-history replay
fresh snapshot validation then resolver
receipt-backed resolver
temporary fast-path downgrade
projection rebuild
```

Choosing among semantically allowed paths belongs to StrategySelector.

Stage 4A should not perform strategy selection.

---

## SemanticOutcome Is Not Retry Governance

```text
retry attempt
≠
same intent
```

Stage 4A may represent outcomes related to concurrency, idempotency, or intent inconsistency.

However, it should not implement full retry governance.

For example:

```text
IDEMPOTENT_REPLAY_ALLOWED
```

is a semantic outcome that says a prior accepted result can be treated as the same request effect.

But retry attempt classification, max attempts, backoff, reload/rebuild-once policy, and agent intent drift handling belong to later Stage 4E.

---

## Relationship to Compass Layer 1

Compass Layer 1 protects:

```text
candidate event
→ accepted history
```

Layer 1 prevents invalid candidate actions from becoming accepted facts.

Stage 4A begins Layer 2 semantic interpretation.

Layer 2 protects runtime meaning after accepted history exists, especially across derived state, snapshots, replay, and resolver paths.

The two layers should eventually use compatible semantic vocabulary.

However, Stage 4A PR1 should not rewrite Layer 1.

Layer 1 alignment can be introduced later after the SemanticOutcome vocabulary stabilizes.

---

## Relationship to Existing Durable Artifacts

Stage 4A should preserve the current durable artifact model:

```text
order_events
= accepted history / authority

idempotency_records
= successful request-effect receipt memory

projection_states
= derived read-side state

projection_checkpoints
= operational progress metadata

projection_snapshots
= derived state compression
```

SemanticOutcome should not change the authority source.

It should interpret runtime evidence about those artifacts.

For example:

```text
projection state differs from accepted-history replay
→ semantic outcome may be DRIFT_DETECTED

snapshot boundary is invalid
→ semantic outcome may be DERIVED_STATE_UNTRUSTED or FAST_PATH_UNAVAILABLE

accepted history is missing for an order
→ semantic outcome may be RUNTIME_UNRESOLVED, depending on boundary
```

The exact mapping should be implemented in later Stage 4A PRs.

---

## Evidence Boundary

SemanticOutcome may carry summary evidence.

Examples:

```text
technical_status
validator_name
resolver_name
order_id
snapshot_id
source_global_position
expected_state_summary
actual_state_summary
reason
```

But SemanticOutcome should not become a full diagnostic trace.

Detailed failure path, partial replay progress, cursor position, and fallback path details belong to DiagnosticTrace / ResolutionTrace.

Durable reviewable evidence belongs to DecisionReceipt.

This means:

```text
SemanticOutcome
= semantic meaning

DecisionReceipt
= durable summary evidence

DiagnosticTrace
= detailed failure path / partial progress
```

Those should remain separate.

---

## Minimal PR1 Boundary

Stage 4A PR1 should establish only the documentation boundary.

It should not require final code names.

It should not require the final enum values.

It should not require a database migration.

It should not require a receipt table.

The acceptable PR1 output is:

```text
Stage 4 implementation notes baseline
Stage 4 PR breakdown
SemanticOutcome boundary note
runtime semantic outcome boundary note
optional roadmap alignment
```

---

## Non-goals

Stage 4A PR1 does not implement:

```text
production SemanticOutcome model
technical status mapper
DecisionReceipt
DiagnosticTrace
Measurement Matrix
policy contract
RuntimeDecisionPolicy
StrategySelector
RetryGovernance
benchmark suite
projection delivery layer
agent action safety gate
new SQL migrations
```

It also does not claim that the candidate outcome names are final.

---

## Completion Criteria

PR1 is complete when:

```text
Stage 4A SemanticOutcome boundary is documented
technical status and semantic outcome are separated
SemanticOutcome and RuntimeDecision are separated
RuntimeDecision and StrategySelector are separated
retry attempt and same intent are separated
Stage 4B / 4C / 4D / 4E concepts are explicitly deferred
future implementation PRs have a clear sequence
```

