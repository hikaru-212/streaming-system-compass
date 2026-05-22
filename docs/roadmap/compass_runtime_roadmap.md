# Compass Runtime Roadmap

[← Back to Roadmaps Index](README.md)

## Purpose

This roadmap describes the **Compass runtime evolution path**.

It intentionally does not repeat the full implementation roadmap.

For the project-wide implementation sequence, including detailed Stage 3.5B PostgreSQL tables, migrations, store implementation order, and PR breakdowns, see:

- [Implementation Roadmap](implementation_roadmap.md)

This document focuses on a narrower question:

> How does Compass evolve from write-side semantic validation into runtime semantic validation, structured outcomes, runtime decisions, action safety, and dual-dimension governance?

In other words, this roadmap is about the semantic control layer, not the full project build plan.

---

## Scope Boundary

The implementation roadmap answers:

> What should be built, and in what order?

This Compass runtime roadmap answers:

> How does Compass become more capable as a runtime semantic control layer?

The two roadmaps overlap around Stage 3.5B and Stage 3.5C because Compass depends on durable write-side and read-side boundaries.

However, this document avoids repeating detailed schema columns, migration details, and store test matrices.

Those belong in the implementation roadmap.

This document instead tracks how those implementation stages support the next Compass capabilities.

---

## Current Compass Position

Compass currently has a working Layer 1 baseline.

Layer 1 protects the write-side accepted-history boundary:

```text
candidate event
→ transition-truth validation
→ ALLOW / BLOCK
→ only allowed event can reach accepted history
```

The current system already supports:

- write-side candidate-event generation
- proof-carrying event structure
- Layer 1 transition validation
- validation dispatch
- basic `ALLOW` / `BLOCK` enforcement
- candidate vs accepted event identity boundary clarification
- rejection before invalid events enter accepted history

This means Compass is already more than a passive checker.

It already has runtime control authority at the write-side boundary:

```text
invalid candidate event
→ blocked before accepted history
```

---

## Current Limitation

Compass does not yet fully protect derived runtime state.

The current Stage 3 projection baseline can derive state through a deterministic reducer / worker path, but Compass has not yet become a state-level validator.

That means the following question is not yet fully answered:

> Even if accepted history is valid, is the current read-side projection still faithful to that history?

This is the gap that later stages must close.

---

## Compass Evolution Principle

Compass should evolve from:

```text
write-side event truth
→ durable accepted history
→ durable derived state
→ Layer 2 state validation
→ structured semantic outcomes
→ runtime decisions
→ action safety
→ dual-dimension governance
```

The key principle is:

> A semantic failure should not only be detected.  
> It should become explicit enough that the runtime can decide whether to continue, rebuild, block, quarantine, stop, or escalate.

---

# Phase 1 — Layer 1 Write-Side Validation

## Goal

Protect accepted history before invalid facts enter the event log.

## Already Established

Compass Layer 1 checks whether a candidate event truthfully follows accepted history.

Examples:

```text
INIT → CREATED  allowed
CREATED → PAID  allowed
INIT → PAID     blocked
```

Layer 1 currently protects:

- transition truth
- claimed previous state
- claimed previous version
- candidate event consistency
- accepted-history entry

## Runtime Meaning

Layer 1 is already a runtime control boundary.

It does not merely record that an event is invalid.

It prevents invalid history from being written.

```text
invalid semantic transition
→ BLOCK
→ no accepted event
```

## Current Status

Implemented at baseline level.

---

# Phase 2 — Durable Write-Side Dependency

## Why Compass Needs This

Layer 1 protects accepted history, but accepted history must become durable before later runtime validation can be trusted across restart, retry, and partial failure.

Stage 3.5B provides this dependency.

The implementation roadmap owns the detailed PR sequence:

```text
PR1 Physical Schema + Local PostgreSQL + Migration
PR2 PostgresEventStore
PR3 PostgresIdempotencyStore
PR4 Transactional Write-Side Boundary
```

From the Compass perspective, Stage 3.5B matters because it turns accepted history into a durable validation source.

## Compass-Relevant Outcomes

Stage 3.5B should give Compass:

- durable accepted history
- durable event identity
- durable replay source
- durable idempotency result memory
- transactionally coordinated event append and idempotency record write
- clear candidate / accepted identity boundary

## Related Postmortems

- [From In-Memory Correctness to Durable Consistency](../postmortems/from_in_memory_correctness_to_durable_consistency.md)
- [From Git Local–Remote Drift to Database Immutability Boundaries](../postmortems/from_git_sync_to_db_immutability.md)
- [From Local PostgreSQL Setup to Defense-in-Depth Boundaries](../postmortems/from_local_postgres_to_defense_in_depth.md)
- [From Runtime Behavior to Durable Evidence](../postmortems/from_runtime_behavior_to_durable_evidence.md)

These explain why persistence is not just a backend swap.

For Compass, the important lesson is:

```text
Python-side semantic behavior is not durable evidence
unless the selected facts are persisted into an explicit evidence channel.
```

## Current Status

Stage 3.5B PR1 is complete.

Next implementation work is Stage 3.5B PR2: `PostgresEventStore`.

---

# Phase 3 — Durable Read-Side Dependency

## Why Compass Needs This

Layer 2 validation requires a durable read-side target.

To detect projection drift, Compass needs to compare:

```text
expected state from accepted-history replay
vs
persisted projection state
```

If the projection state exists only in memory, the validation is useful but not yet durable enough for stronger runtime governance.

Stage 3.5C provides this dependency.

## Compass-Relevant Outcomes

Stage 3.5C should provide:

- durable projection state
- durable checkpoint state
- persistence-backed replay / rebuild
- state that survives restart
- a durable target for Layer 2 validation

## Runtime Meaning

Read-side state is not source of truth.

It is derived state.

Compass Layer 2 should eventually verify whether derived state remains faithful to accepted history.

```text
accepted history = truth source
projection state = derived runtime view
Layer 2 = truthfulness check for derived state
```

## Current Status

Planned after Stage 3.5B.

---

# Phase 4 — Layer 2 State-Level Validation

## Goal

Add the first read-side / state-level Compass validator.

Layer 1 protects:

```text
candidate event → accepted history
```

Layer 2 protects:

```text
accepted history → derived runtime state
```

## What Layer 2 Detects

Layer 2 should detect:

- projection drift
- replay vs persisted-state mismatch
- reducer mismatch
- checkpoint / state mismatch

## Minimal Flow

```text
accepted event history
        ↓
replay using canonical reducer
        ↓
expected_state
        ↓ compare
persisted_projection_state
        ↓
Layer 2 validation result
```

## Example

```text
accepted history replay result: PAID
persisted projection state: CREATED
```

This is not a write-side transition violation.

It is read-side semantic drift.

Layer 2 should detect it.

## Completion Criteria

Layer 2 is minimally useful when:

- at least 1–2 projection drift cases can be produced deterministically
- replayed expected state can be compared with persisted projection state
- validation output clearly explains the mismatch
- tests prove the mismatch is detected

## Boundary

Layer 2 detects whether derived state is correct.

It does not yet decide what the runtime should do.

That decision belongs to the runtime decision policy phase.

---

# Phase 5 — Structured Semantic Outcomes

## Goal

Replace raw exception strings, booleans, and ad hoc validation messages with structured semantic outcomes.

## Why

A raw exception can interrupt execution.

But it cannot reliably support governance.

Compass needs a reusable semantic artifact that can be consumed by:

- validators
- runtime decision policies
- action safety gates
- future trust evaluators
- later agent-facing governance paths

## Preferred Concept

Use:

```text
SemanticOutcome
```

rather than only:

```text
ErrorModel
```

because not every outcome is a conventional exception.

Some outcomes represent:

- semantic drift
- trust mismatch
- irreversible boundary risk
- operational staleness
- action safety risk

## Minimal Outcome Shape

A future `SemanticOutcome` should express:

- whether the outcome is OK
- which layer produced it
- what semantic failure occurred
- what evidence supports it
- how severe it is
- whether it is reversible
- what context produced it

Example shape:

```python
@dataclass(frozen=True)
class SemanticOutcome:
    outcome_id: str
    ok: bool
    layer: str
    error_code: str | None
    error_type: str | None
    severity: str
    reversibility: str
    risk_level: str
    context: dict
    evidence: dict
    message: str
```

## Related Postmortem

See:

- [From Exception Strings to Governable Outcomes](../postmortems/from_exception_strings_to_governable_outcomes.md)

That postmortem explains why the system must evolve from:

```text
raise ValueError(...)
→ structured semantic outcome
→ runtime decision policy
→ runtime decision
→ action safety gate
→ layered trust / governance
```

## Boundary

A semantic outcome describes what happened.

It should not directly own the final control action.

That responsibility belongs to `RuntimeDecisionPolicy`.

---

# Phase 6 — Runtime Decision Policy

## Goal

Convert semantic outcomes into runtime decisions.

This is the transition from:

```text
detect and classify
```

to:

```text
decide and control
```

## Core Boundary

Separate these responsibilities:

```text
SemanticOutcome
→ describes what happened

RuntimeDecisionPolicy
→ decides what to do

RuntimeDecision
→ carries the executable decision

ActionSafetyGate
→ enforces the decision before unsafe execution
```

## Minimal Runtime Actions

A minimal runtime action set may include:

- `ALLOW`
- `BLOCK`
- `REBUILD`
- `QUARANTINE`
- `ESCALATE`

## Example Policy Mapping

```text
ok=True
→ ALLOW

DOMAIN_TRANSITION_VIOLATION
→ BLOCK

SEMANTIC_PROJECTION_DRIFT
→ REBUILD or QUARANTINE

REPLAY_REDUCER_MISMATCH
→ BLOCK or ESCALATE

IRREVERSIBLE_BOUNDARY_RISK
→ BLOCK
```

## Runtime Meaning

This is where Compass becomes more than validation.

It begins to answer:

```text
Given this semantic failure, what should the runtime do now?
```

## Completion Criteria

This phase is minimally useful when:

- Layer 2 drift can map to `REBUILD`, `QUARANTINE`, or `ESCALATE`
- Layer 1 invalid transition can map to `BLOCK`
- tests assert decision fields, not only error strings
- irreversible actions do not proceed when the decision is `BLOCK`

---

# Phase 7 — Action Safety Gate

## Goal

Add a domain-level gate before dependent actions execute.

Do not start with a general-purpose agent protocol.

Start with domain actions that are meaningful inside this project.

## Candidate Domain Actions

Possible simulated actions:

- `EMIT_DOWNSTREAM_SIGNAL`
- `GENERATE_SETTLEMENT_REPORT`
- `MARK_PROJECTION_TRUSTED`
- `ADVANCE_EXTERNAL_EXPORT`

## Minimal Flow

```text
requested action
        ↓
semantic state check
        ↓
SemanticOutcome
        ↓
RuntimeDecisionPolicy
        ↓
RuntimeDecision
        ↓
ActionSafetyGate
        ↓
execute or block
```

## Runtime Meaning

This is the generalization of Layer 1.

Layer 1 says:

```text
invalid event must not enter accepted history
```

Action safety says:

```text
unsafe state must not trigger dependent action
```

Both follow the same principle:

```text
Before something becomes irreversible,
check whether it is semantically allowed.
```

## Completion Criteria

The action safety gate is minimally useful when:

- unsafe semantic outcome blocks dependent action
- projection drift can block or quarantine downstream action
- clean semantic state allows action
- tests prove blocked action is not executed

---

# Phase 8 — Dual-Dimension Governance

## Goal

Evaluate runtime trust using two dimensions:

```text
semantic correctness × operational freshness
```

The final question becomes:

```text
Is this state true enough, fresh enough, and safe enough to act on?
```

## Why This Matters

A system can be semantically correct but operationally stale.

A system can be operationally fresh but semantically wrong.

Therefore, action safety cannot depend on a single trusted / untrusted boolean.

## Core Matrix

|  | Operational Fresh | Operational Stale |
|---|---|---|
| Semantic Correct | Safe to act | Semantically correct but stale |
| Semantic Incorrect | Operationally healthy but semantically unsafe | Unsafe / stop / escalate |

## Required Cases

### Case 1 — Semantic Correct + Operational Fresh

Meaning:

```text
truth and view are both reliable
```

Possible verdict:

```text
SAFE_TO_ACT
```

### Case 2 — Semantic Correct + Operational Stale

Meaning:

```text
the fact is semantically valid,
but the current view is stale
```

Possible verdict:

```text
REFRESH_BEFORE_ACTION
```

### Case 3 — Semantic Incorrect + Operational Fresh

Meaning:

```text
the pipeline looks fresh,
but the fact is semantically unsafe
```

Possible verdict:

```text
BLOCK_ACTION
```

This is one of the strongest project insights:

```text
freshness does not imply correctness
```

### Case 4 — Semantic Incorrect + Operational Stale

Meaning:

```text
both semantic correctness and operational freshness are broken
```

Possible verdict:

```text
STOP / QUARANTINE / ESCALATE
```

## Minimal Structures

```python
@dataclass(frozen=True)
class SemanticSignal:
    correct: bool
    outcome: SemanticOutcome | None
```

```python
@dataclass(frozen=True)
class OperationalSignal:
    fresh: bool
    checkpoint_age_ms: int
    worker_lag: int
    reason: str
```

```python
@dataclass(frozen=True)
class ActionSafetyVerdict:
    semantic_correct: bool
    operational_fresh: bool
    action: str
    safe_to_act: bool
    reason: str
```

## Completion Criteria

This phase is minimally useful when:

- all four matrix cases can be produced
- semantic incorrect + operational fresh is clearly shown
- semantic correct + operational stale is clearly shown
- final action-safety verdict is explicit
- demo can explain why pipeline health alone is not correctness

---

# Phase 9 — Later Governance and Chaos Hardening

## Goal

After the minimal governance demo is coherent, Compass can grow toward richer failure-aware runtime governance.

## Possible Later Work

- DLQ
- out-of-order buffering
- watermark semantics
- multi-worker coordination
- stronger transaction boundaries
- real observability integration
- richer policy engine
- chaos testing
- semantic alerts
- agent tool interface
- generalized semantic governance protocol

These are intentionally deferred.

The project should first prove:

```text
semantic truth
→ durable evidence
→ structured outcome
→ runtime decision
→ action safety
```

---

## Summary View

```text
Current:
Layer 1 write-side event truth validation ✅

Dependency:
Stage 3.5B durable write-side baseline
Stage 3.5C durable read-side baseline

Next Compass Growth:
Layer 2 state-level validation
SemanticOutcome
RuntimeDecisionPolicy
RuntimeDecision
ActionSafetyGate
Dual-Dimension Governance

Later:
chaos hardening
richer governance
agent-facing runtime protocol
```

---

## Final Summary

Compass should evolve from a validator into a runtime semantic control layer.

The intended progression is:

```text
validate event truth
→ verify derived state
→ express semantic failure
→ decide runtime action
→ block unsafe execution
→ combine semantic and operational trust
```

This is the core path from Compass Layer 1 toward dual-dimension governance.
