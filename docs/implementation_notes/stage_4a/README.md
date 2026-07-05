# Stage 4A — SemanticOutcome Core

[← Back to Implementation Notes](../README.md)

## Purpose

This directory records the implementation plan for:

```text
Stage 4A — Compass Layer 2 SemanticOutcome Core
```

Stage 4A begins the Stage 4 transition from runtime correctness evidence into governable semantic meaning.

The goal is not to build a general policy engine, observability platform, benchmark suite, or agent protocol.

The goal is to make runtime validation results interpretable, durable where needed, and safe to use as inputs for later decisions.

---

## Why This Stage Exists

The project now has durable baselines for:

```text
accepted history
idempotency receipts
projection state
projection checkpoints
projection snapshots
snapshot-assisted replay validation
snapshot-assisted state resolution
durable history / permission hardening
```

Earlier stages established the core authority model:

```text
accepted history = authority
projection state = derived runtime view
snapshot = derived state compression
checkpoint = operational progress metadata
```

Stage 3.5D established that snapshots can support replay efficiency without becoming authority.

Stage 3.5E established that durable authority should be harder to mutate than derived runtime state.

Those boundaries make the next question unavoidable:

```text
When runtime evidence is produced,
what does it mean semantically?
```

A validator can return `MATCH`.

A resolver can return a state.

A replay path can complete.

A retry can succeed.

But none of those technical facts automatically proves that the system should trust the result, reuse the fast path, rebuild derived state, allow downstream usage, or retry the same intent.

Stage 4A exists to define the first semantic boundary that prevents that collapse.

---

## Core Principle

```text
technical status
≠
semantic outcome

semantic outcome
≠
runtime decision

runtime decision
≠
execution strategy

retry attempt
≠
same intent
```

Stage 4 should preserve these distinctions.

The staged direction is:

```text
technical evidence
→ SemanticOutcome
→ DecisionReceipt
→ DiagnosticTrace / Measurement Evidence
→ Policy Contract
→ RuntimeDecisionPolicy
→ StrategySelector
→ Retry Governance
```

The order matters because later governance layers should not make decisions directly from raw technical statuses.

---

## Stage 4A Focus

Stage 4A introduces the first runtime semantic governance boundary:

```text
Stage 4A — Compass Layer 2 SemanticOutcome Core
```

Stage 4A answers:

```text
Given technical runtime evidence,
what does this mean for semantic correctness?
```

Stage 4A should come before receipts, traces, measurement matrices, policy contracts, strategy selection, and retry governance.

It is the place where the system begins to translate runtime results such as:

```text
MATCH
MISSING_SNAPSHOT
INVALID_SNAPSHOT_BOUNDARY
SNAPSHOT_ASSISTED_DRIFT
RESOLVED_FROM_SNAPSHOT
INVALID_SNAPSHOT_PRECONDITION
TAIL_REPLAY_FAILED
OCC_CONFLICT_AFTER_VALIDATION
IDEMPOTENT_REPLAY
IDEMPOTENCY_CONFLICT
```

into semantic meanings such as:

```text
SEMANTICALLY_VALID
RUNTIME_UNRESOLVED
DERIVED_STATE_UNTRUSTED
DRIFT_DETECTED
FAST_PATH_UNAVAILABLE
REQUIRES_AUTHORITY_FALLBACK
REQUIRES_REBUILD
REQUIRES_OPERATOR_REVIEW
CONCURRENCY_UNCERTAIN
IDEMPOTENT_REPLAY_ALLOWED
SEMANTIC_CONFLICT_DETECTED
INTENT_DRIFT_DETECTED
```

The exact vocabulary may evolve during implementation.

The important boundary is that the system should not treat a raw technical result as a complete semantic decision.

---

## Scope

Stage 4 may eventually include:

```text
SemanticOutcome vocabulary
DecisionReceipt / runtime evidence records
DiagnosticTrace / ResolutionTrace
Measurement Matrix / Cost Evidence Inventory
Order Domain Policy Contract v0
RuntimeDecisionPolicy
Layer 1 / Layer 2 outcome alignment
StrategySelector / Fast-Path Health Policy
Retry Governance / Attempt Classification
```

However, Stage 4A PR1 should remain documentation-first.

It should define the SemanticOutcome boundary before introducing production code.

---

## Non-goals

Stage 4A PR1 does not implement:

```text
production SemanticOutcome dataclass
DecisionReceipt persistence
DiagnosticTrace tables
Measurement Matrix implementation
policy contract YAML
RuntimeDecisionPolicy
StrategySelector
RetryGovernance
benchmark suite
projection delivery layer
Stage 5 action safety gate
agent workflow orchestration
full observability platform
```

Stage 4A PR1 is a boundary PR.

It should make the first Layer 2 semantic vocabulary clear without turning the PR into all of Stage 4.

---

## Relationship to Earlier Stages

### Stage 1

Stage 1 established the transactional semantic core for the order/payment domain.

It defined valid business transitions before durable infrastructure was introduced.

Stage 4 should not replace this domain truth.

It should make runtime consequences of that truth machine-readable.

---

### Stage 2

Stage 2 introduced Compass Layer 1 / Admission Boundary.

Layer 1 protects:

```text
candidate event
→ accepted history
```

Stage 4A begins Compass Layer 2.

Layer 2 protects interpretation of runtime evidence after accepted history already exists.

---

### Stage 3

Stage 3 introduced projection runtime behavior.

It established that derived runtime state can be built from accepted history.

Stage 4A does not change the projection model.

It defines how projection and replay validation results should be interpreted semantically.

---

### Stage 3.5D

Stage 3.5D introduced snapshot trust and replay-efficiency support.

It clarified:

```text
snapshot = derived state compression
snapshot-assisted validation = evidence producer
snapshot-assisted resolver = trust consumer
```

Stage 4A should be able to map snapshot trust and resolver outcomes into semantic outcomes.

---

### Stage 3.5E

Stage 3.5E introduced durable history and permission hardening.

It clarified:

```text
database role
≠
actor metadata
≠
governance evidence
```

Stage 4A does not introduce governance evidence persistence yet.

It prepares the semantic vocabulary that later receipts and decisions can record.

---

## Relationship to Future Stage 4 Work

Stage 4A defines semantic meaning.

Later stages may build on it:

```text
Stage 4B
= records SemanticOutcome and evidence as DecisionReceipt

Stage 4B.1
= records detailed failure path and partial progress as DiagnosticTrace

Stage 4B.2
= defines timing / cost evidence vocabulary

Stage 4B.5
= links outcomes to narrow order-domain policy rules and recovery hints

Stage 4C
= converts SemanticOutcome plus evidence into RuntimeDecision

Stage 4C.5
= aligns Layer 1 and Layer 2 around compatible outcome / decision vocabulary

Stage 4D
= chooses execution strategy among semantically allowed options

Stage 4E
= governs retries and distinguishes attempt identity from intent preservation
```

Stage 4A should not implement those layers early.

It should only preserve extension points so those later layers can consume the outcome vocabulary cleanly.

---

## Expected PR Sequence

A minimal Stage 4 sequence should be:

```text
PR1 — Runtime SemanticOutcome Boundary
PR2 — SemanticOutcome Vocabulary / Result Contract
PR3 — Runtime Technical Status Mapping
PR4 — Snapshot / Projection Outcome Mapping
PR5 — Write-Side Admission Outcome Mapping
PR6 — Stage 4A Closeout
```

Detailed notes:

- [PR Breakdown](pr_breakdown.md)
- [Runtime SemanticOutcome Boundary](semantic_outcome_boundary.md)

This sequence may be adjusted as implementation reveals constraints.

However, Stage 4A should avoid expanding into receipts, policy, strategy selection, or retry governance.

