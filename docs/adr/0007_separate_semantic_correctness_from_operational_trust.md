# ADR 0007: Separate Semantic Correctness from Operational Trust

[← Back to ADR Index](README.md)

## Status

Proposed

## Target Stage

Future Stage 4D — Layered Trust Verdict Minimal Simulation

## Depends On

- Stage 4A — Layer 2 Minimal Validator
- Stage 4B — Structured Error Model v1
- Stage 4C — Backport Layer 1 to Same Outcome Family

## Context

Compass currently focuses on semantic correctness.

At the write-side boundary, Compass Layer 1 validates whether a candidate event truthfully follows accepted history before it can become part of the event log.

At the read-side boundary, Compass Layer 2 is planned to validate whether projected runtime state remains faithful to accepted history.

This gives the system a strong semantic foundation:

- candidate events are not trusted merely because they can be written
- accepted history is protected before persistence
- projection state can later be checked against replayed history
- semantic failures can evolve from ad-hoc exceptions into structured outcomes

However, semantic correctness is not the same as operational usability.

A system can be semantically correct but operationally stale.

A system can be operationally healthy but semantically invalid.

For example:

- an event may pass Compass validation and become accepted history, while the downstream projection is still lagging
- a projection table may be fresh, recently updated, and operationally healthy, while it faithfully reflects semantically invalid history
- a read model may be structurally available but unsafe for real-time decisions due to freshness or incident status
- an observability system may report a healthy pipeline, while Compass detects an invalid transition or corrupted semantic state

Therefore, a single `trusted / untrusted` verdict is not expressive enough.

The system needs to distinguish:

- whether a fact is semantically valid
- whether accepted history remains clean
- whether projected state faithfully reflects accepted history
- whether the current operational view is fresh and healthy
- whether it is safe for a downstream user, service, or agent to act

This ADR is recorded before implementation to preserve the design reasoning.

It does not change the current Stage 3.5 implementation priority.

The current implementation priority remains:

1. Decimal / money semantics hardening
2. write-side durable baseline
3. read-side durable baseline
4. Layer 2 minimal validator
5. structured error model v1

The layered trust model described here is a future evolution after structured error outcomes exist.

## Decision

We will separate trust evaluation into multiple dimensions:

- **Semantic Correctness**  
  Is the business logic valid?

- **History Correctness**  
  Is accepted history clean, replayable, and free from known semantic corruption?

- **Projection Correctness**  
  Is the current view faithful to accepted history?

- **Operational Trust**  
  Is the pipeline fresh, healthy, and free from unresolved operational incidents?

- **Action Safety**  
  Based on the above, is it safe for a downstream service, operator, or agent to execute a side effect?

The first implementation will be a minimal simulation introduced after Stage 4B, once structured error outcomes exist.

This model does not replace observability tools.

Instead:

- Compass provides semantic correctness signals
- observability systems provide operational trust signals
- the layered trust evaluator combines both into an action-safety verdict

The system should not collapse these signals into one boolean.

Instead, it should preserve the reason why something is or is not safe to use.

## Consequences

This decision introduces a clearer boundary between semantic truth and operational usability.

Compass remains responsible for semantic correctness:

- event truth
- transition truth
- accepted history integrity
- projection faithfulness
- structured semantic failure outcomes

Observability remains responsible for operational signals:

- freshness
- incident status
- pipeline health
- upstream / downstream availability
- operational degradation

The layered trust evaluator combines these signals but does not own their raw detection logic.

This allows Compass to integrate with existing production ecosystems instead of replacing them.

For example, a future production system could combine:

- Compass semantic outcomes
- OpenTelemetry / Datadog-style runtime signals
- Monte Carlo-style data observability signals
- internal incident / lineage status
- service-level policy rules

The first version will not implement those integrations.

It will only simulate operational signals to prove the trust matrix.

## Non-goals

This ADR does not introduce:

- a full observability platform
- a Monte Carlo integration
- a Datadog / OpenTelemetry integration
- a real lineage graph
- a full incident management system
- a general-purpose agent governance framework
- a production policy engine
- a dashboard UI
- a replacement for Compass Layer 1 or Layer 2
- a replacement for structured error outcomes

This ADR also does not move Stage 4D ahead of the current durable baseline work.

The current implementation order remains conservative.

## First Minimal Implementation

We will implement a pure-logic layered trust evaluator using the following core structures:

- `SemanticSignal`  
  Derived from Compass Layer 1 and Layer 2 verdicts.

- `OperationalSignal`  
  Simulated inputs such as `FRESH`, `STALE`, `LAGGING`, or `INCIDENT_ACTIVE`, representing signals that could later come from external observability tools.

- `TrustVerdict`  
  The combined interpretation of semantic and operational states.

- `TrustEvaluator`  
  A pure function that reduces semantic and operational signals into an `ActionSafety` boundary.

Example action-safety outcomes:

- `SAFE_TO_ACT`
- `SAFE_TO_READ_ONLY`
- `DEGRADED_USE_WITH_CAUTION`
- `DO_NOT_USE_FOR_REAL_TIME_DECISION`
- `BLOCK_ACTION`
- `HUMAN_REVIEW_REQUIRED`

The first version will use simulated operational signals to prove the matrix logic without requiring real external infrastructure.

## Example Verdicts

### Case 1: Semantically valid but operationally stale

```json
{
  "event_truth": "VALID",
  "history_truth": "CLEAN",
  "projection_truth": "LAGGING",
  "operational_trust": "STALE",
  "action_safety": "DO_NOT_USE_FOR_REAL_TIME_DECISION",
  "final_decision": "SEMANTICALLY_VALID_BUT_OPERATIONALLY_STALE"
}
```

Meaning:

The underlying fact is valid, and accepted history is clean, but the current view is not safe for real-time decisions.

### Case 2: Operationally healthy but semantically invalid

```json
{
  "event_truth": "INVALID",
  "history_truth": "AT_RISK",
  "projection_truth": "FRESH",
  "operational_trust": "HEALTHY",
  "action_safety": "BLOCK_ACTION",
  "final_decision": "OPERATIONALLY_HEALTHY_BUT_SEMANTICALLY_INVALID"
}
```

Meaning:

The pipeline may appear fresh and healthy, but the underlying semantic truth is invalid. The system must block action.

### Case 3: Semantically valid and operationally healthy

```json
{
  "event_truth": "VALID",
  "history_truth": "CLEAN",
  "projection_truth": "CONSISTENT",
  "operational_trust": "HEALTHY",
  "action_safety": "SAFE_TO_ACT",
  "final_decision": "TRUSTED_FOR_ACTION"
}
```

Meaning:

Both semantic correctness and operational trust are aligned. The system can safely act.

### Case 4: Semantically invalid and operationally degraded

```json
{
  "event_truth": "INVALID",
  "history_truth": "CORRUPTED",
  "projection_truth": "INCONSISTENT",
  "operational_trust": "INCIDENT_ACTIVE",
  "action_safety": "HUMAN_REVIEW_REQUIRED",
  "final_decision": "SEMANTIC_AND_OPERATIONAL_FAILURE"
}
```

Meaning:

Both semantic correctness and operational trust are broken. The system should not act automatically.

## Rationale

Structured error outcomes explain what failed.

Layered trust verdicts explain whether the system is safe to act.

These are related but not identical.

Stage 4B answers:

> What kind of semantic failure happened?

Stage 4D answers:

> Given semantic correctness and operational trust, what is safe to do now?

This distinction matters because production systems often fail across time and layers.

An event may be valid at admission time, while the query-time view is stale.

A pipeline may be operationally healthy, while the underlying event history is semantically invalid.

Therefore, trust must be modeled as layered, time-scoped, and action-aware.

## Time-Scoped Trust Semantics

This ADR introduces the concept of time-scoped trust semantics.

Trust depends on when and where it is evaluated:

- **Admission-time correctness**  
  Is the candidate event valid before it enters accepted history?

- **Projection-time correctness**  
  Does the derived read model faithfully reflect accepted history?

- **Query-time trustworthiness**  
  Is the current view fresh, complete, and operationally healthy?

- **Action-time safety**  
  Is it safe for a downstream actor to take action based on the current state?

This prevents the system from treating all correctness failures as the same kind of failure.

## Expected Future Tests

The minimal implementation should include tests such as:

- semantic valid + operational healthy -> safe to act
- semantic valid + projection lagging -> not safe for real-time decision
- semantic invalid + operational healthy -> block action
- clean accepted history + stale projection -> valid truth but degraded view
- active incident + valid history -> safe truth but unsafe query-time decision
- corrupted history + fresh pipeline -> operationally healthy but semantically unsafe

## Summary

Compass does not replace observability.

Observability does not replace semantic validation.

Compass asks:

> Is this fact allowed to become truth?

Observability asks:

> Is the current view safe to use?

Layered trust verdicts combine both questions into:

> Is it safe to act now?
