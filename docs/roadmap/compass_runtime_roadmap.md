# Compass Runtime Roadmap

[← Back to Roadmaps Index](README.md)

## Purpose

This roadmap describes the **Compass runtime evolution path**.

It intentionally does not repeat the full implementation roadmap or preserve PR-level execution history.

For project-wide implementation sequencing, see:

- [Implementation Roadmap](implementation_roadmap.md)

For completed stage execution notes, see:

- [Stage 3.5B Implementation Notes](../implementation_notes/stage_3_5b/)
- [Stage 3.5C Implementation Notes](../implementation_notes/stage_3_5c/)
- [Stage 3.5D Implementation Notes](../implementation_notes/stage_3_5d/)

This document focuses on a narrower question:

> How does Compass evolve from write-side semantic validation into runtime semantic validation, structured outcomes, runtime decisions, action safety, and dual-dimension governance?

In other words, this roadmap is about the semantic control layer, not the full project build plan.

---

## Scope Boundary

The implementation roadmap answers:

> What should be built, and in what order?

This Compass runtime roadmap answers:

> How does Compass become more capable as a runtime semantic control layer?

The two roadmaps overlap around Stage 3.5B, Stage 3.5C, Stage 3.5D, and Stage 3.5E because Compass depends on durable write-side, durable read-side, snapshot trust, and actor / permission boundaries before stronger runtime validation grows.

However, this document avoids repeating detailed schema columns, migrations, store test matrices, and PR-level implementation history.

Those belong in the implementation roadmap and implementation notes.

This document instead tracks how those stages support the next Compass capabilities.

---

## Terminology Note: Compass Phases vs Project Stages

This document uses **Phase** to describe the focused evolution of Compass as a runtime semantic control layer.

The broader implementation roadmap uses **Stage** to describe project-wide build sequencing.

These two terms are intentionally related but not identical:

```text
Compass Phase = semantic-control capability progression
Project Stage = repository-wide implementation milestone
```

For example:

- Compass Phases 1–3 correspond to the current write-side validation and durable persistence dependencies across Stage 2, Stage 3, Stage 3.5B, Stage 3.5C, and the Stage 3.5D replay-efficiency substrate.
- Stage 3.5E provides a minimal actor / permission boundary before broader runtime governance.
- Compass Phase 4 roughly maps to the beginning of Stage 4 Layer 2 validation work.
- Compass Phases 5–7 roughly map to Stage 4 structured semantic outcomes, runtime decision policy, and action safety.
- Compass Phase 8 maps to the Stage 5 dual-dimension governance demo.

The phase labels in this document should therefore be read as a Compass-specific capability path, not as a replacement for the project-wide Stage numbering in the implementation roadmap.

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

The project has now completed the main durability and replay-efficiency substrate needed before Stage 3.5E and Stage 4:

```text
Stage 3.5B = durable write-side baseline
Stage 3.5C = durable read-side baseline
Stage 3.5D = read-side snapshot trust / replay-efficiency baseline
```

This means Compass is already more than a passive checker.

It already has runtime control authority at the write-side boundary:

```text
invalid candidate event
→ blocked before accepted history
```

Stage 3.5B extended that authority into the durable PostgreSQL-backed write-side path:

```text
candidate event
→ Compass Layer 1 validation
→ append accepted event + record idempotency in one transaction
```

Stage 3.5C established the durable read-side target:

```text
accepted history
→ global-position projection event source
→ canonical reducer
→ durable projection state
→ durable checkpoint progress
```

Stage 3.5D added the snapshot trust / replay-efficiency substrate:

```text
projection snapshot
+ tail replay
→ validation against accepted-history replay
→ externally qualified snapshot-assisted state resolution
```

This does not make Compass Layer 2 active yet.

It provides durable correctness evidence and replay-efficiency primitives that Layer 2 can later classify and govern.

---

## Current Limitation

Compass does not yet make runtime governance decisions for derived state.

The system can now preserve durable accepted history, persist derived read-side state, compare persisted projection state against accepted-history replay, validate snapshot-assisted replay, and resolve read-side state from an externally qualified snapshot id.

However, Compass has not yet become a full state-level governance layer.

That means the next question is no longer only whether drift or snapshot mismatch can be detected. The next question is:

> If derived-state drift, snapshot mismatch, or runtime trust failure is detected, what does it mean, and what should the runtime do?

That interpretation and decision boundary belongs to later Compass Layer 2, structured `SemanticOutcome`, runtime decision policy, and action safety work.

Before that, Stage 3.5E should establish the minimal actor / permission boundary needed for future receipts and privileged runtime actions.

---

## Snapshot Substrate Status

Stage 3.5D has completed the read-side projection snapshot trust substrate and explicitly deferred write-side aggregate snapshot implementation.

Completed baseline:

```text
PR1   — Snapshot Trust Contract Boundary
PR1.5 — CI Stage Branch Checks
PR2   — Projection Snapshot Schema Baseline
PR3   — PostgresProjectionSnapshotStore
PR4   — Projection Snapshot-Assisted Replay Validator
PR4.5 — Projection Snapshot-Assisted State Resolver
PR5   — Aggregate Snapshot Trust Boundary / Deferral Decision
```

The important boundary is:

```text
read-side projection snapshot
= derived state compression / replay-efficiency support

write-side aggregate snapshot
= command admission path optimization / stricter trust problem
```

Projection snapshots can support read-side resolution when externally qualified.

Aggregate snapshot schema / store work and snapshot-assisted write-side rehydration remain deferred because stale or corrupted aggregate snapshots could influence future accepted-history admission.

Detailed Stage 3.5D execution notes live in:

- [Stage 3.5D Implementation Notes](../implementation_notes/stage_3_5d/)

---

## Compass Evolution Principle

Compass should evolve from:

```text
write-side event truth
→ durable accepted history
→ durable derived state
→ snapshot trust / replay-efficiency substrate
→ minimal actor / permission boundary
→ Layer 2 state validation
→ minimal domain policy contract / policy-linked recovery basis
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

Stage 3.5B preserves Layer 1 inside the PostgreSQL-backed transactional write-side flow.

---

# Phase 2 — Durable Write-Side Dependency

## Why Compass Needs This

Layer 1 protects accepted history, but accepted history must become durable before later runtime validation can be trusted across restart, retry, and partial failure.

Stage 3.5B provides this dependency.

Detailed PR-level execution history lives in:

- [Stage 3.5B Implementation Notes](../implementation_notes/stage_3_5b/)

## Compass-Relevant Outcomes

Stage 3.5B gives Compass:

- durable accepted history
- durable event identity
- durable replay source
- durable idempotency result memory
- transactionally coordinated event append and idempotency record write
- Compass Layer 1 preserved before durable accepted-history mutation
- clear candidate / accepted identity boundary
- PostgreSQL-backed two-phase concurrency admission
- validation placement strategy
- minimal `PRE_TRANSACTION` validation path guarded by append-time admission

## Current Status

Completed at the durable write-side baseline level.

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

Detailed PR-level execution history lives in:

- [Stage 3.5C Implementation Notes](../implementation_notes/stage_3_5c/)

## Compass-Relevant Outcomes

Stage 3.5C gives Compass:

- durable projection state schema
- durable checkpoint state schema
- PostgreSQL-backed projection state store
- PostgreSQL-backed checkpoint store
- global-position accepted-history consumption
- PostgreSQL-backed projection worker orchestration
- projection-state and checkpoint-progress atomic persistence
- durable replay / rebuild validation

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

Completed at the durable read-side baseline level.

---

# Stage 3.5D Dependency — Snapshot Trust Contract / Replay Efficiency

Stage 3.5D is complete at the read-side snapshot trust / replay-efficiency baseline level.

It does not implement Layer 2 validation itself.

Instead, it improves the replay, rehydration, and recovery substrate that Layer 2 may later depend on.

Stage 3.5D treats snapshots as derived state-compression artifacts:

```text
accepted history = source of truth
snapshot = derived state compression
projection state = derived runtime view
```

The purpose is to reduce replay, rehydrate, and rebuild cost without allowing snapshots to replace accepted history.

The Stage 3.5D trust model is:

```text
fast path = externally qualified snapshot + tail replay
authority path = full accepted-history replay
```

Compass-relevant outcomes include:

- projection snapshot lineage back to accepted history
- projection snapshot support for read-side replay efficiency
- snapshot-assisted replay validation against accepted-history replay
- snapshot-assisted state resolution from an externally qualified snapshot id
- explicit aggregate snapshot deferral until write-side trust prerequisites are stronger
- fast-path vs authority-path distinction
- future replay cost measurement through receipts / runtime evidence records

Detailed execution notes live in:

- [Stage 3.5D Implementation Notes](../implementation_notes/stage_3_5d/)

Stage 3.5D should remain persistence / replay hardening.

It should not absorb structured semantic outcomes, runtime decision policy, action safety, or dual-dimension governance.

---

# Stage 3.5E Dependency — Minimal Actor / Permission Boundary

Before Compass grows into stronger runtime governance, the system should establish a minimal actor / permission boundary.

```text
Stage 3.5E — Minimal Actor / Permission Boundary
```

This stage does not implement Layer 2 validation, structured semantic outcomes, runtime decision policy, full RBAC, login/session handling, or benchmarking.

Instead, it clarifies who or what is allowed to produce validation, snapshots, receipts, decisions, rebuilds, and privileged operations.

Compass depends on this distinction because later runtime governance will treat accepted history as durable evidence:

```text
accepted history = source of truth / durable evidence
projection state = derived runtime view
checkpoint = operational progress metadata
```

Stage 3.5E should therefore define minimal actor semantics before Stage 4 receipts need fields such as `created_by`, `validated_by`, `decision_by`, `receipt_by`, or `triggered_by`.

Compass-relevant outcomes include:

- system / admin / operator / test actor semantics
- privileged operation boundary documentation
- created_by / future validated_by / decision_by metadata alignment
- optional database role boundary documentation
- accepted-history tables protected from casual `UPDATE` / `DELETE` where appropriate
- read-side tables left mutable for upsert, resume, reset, and rebuild
- stronger confidence that later Layer 2 receipts can identify who or what produced evidence

This stage should remain minimal actor / permission boundary hardening.

It should not absorb Layer 2 validation, `SemanticOutcome`, runtime decision policy, action safety, or dual-dimension governance.

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
- snapshot metadata invalidity
- snapshot hash mismatch
- unsupported snapshot schema
- untrusted snapshot reducer version
- snapshot tail discontinuity
- snapshot replay mismatch

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

## Retry Reason Classification and Intent Consistency

Stage 4 structured outcomes should explicitly classify retry-like situations.

Retry is not a single category.

Possible retry-related outcomes include:

- idempotent replay of the same request identity
- idempotency conflict where the same request identity carries different command meaning
- stale-write retry caused by concurrency admission
- transient infrastructure retry
- rebuild-oriented retry caused by projection or snapshot drift
- future agent intent drift where the agent claims to retry the same task but changes the intended meaning

This classification belongs in `SemanticOutcome` / request-attempt evidence design.

It should not be stored directly in `idempotency_records`, because `idempotency_records` remain successful request-result memory.

Suggested concepts:

```text
retry_class
retry_safety
intent_consistency
```

Examples:

```text
same request_id + same semantic_fingerprint
→ IDEMPOTENT_REPLAY / SAFE_TO_REPLAY / SAME_INTENT

same request_id + different semantic_fingerprint
→ SEMANTIC_CONFLICT / NOT_RETRYABLE / SAME_IDENTITY_DIFFERENT_MEANING

stale expected_version
→ CONCURRENCY_RETRY / SAFE_TO_RETRY_AFTER_RELOAD / NOT_AN_IDEMPOTENCY_REPLAY

future same intent_id + different intent_fingerprint
→ SEMANTIC_DRIFT / BLOCK_AND_ESCALATE / AGENT_INTENT_DRIFT
```


## Policy-Linked Outcomes and Recovery Basis

Stage 4 may introduce a small domain-specific policy contract so that `SemanticOutcome` can reference the rule that explains why a runtime action was allowed, blocked, replayed, rebuilt, quarantined, or escalated.

This should not become a full general-purpose policy authoring system during Stage 4.

The intended scope is narrower:

```text
Order Domain Policy Contract v0
→ machine-readable rules for the current minimal order/payment domain
→ rule IDs that `SemanticOutcome` can reference
→ recovery hints that `RuntimeDecisionPolicy` can consume
```

This addition exists to prevent retry from becoming blind trial-and-error against Compass.

Without a policy / contract reference, an agent or runtime can learn:

```text
what failed
why it failed
```

but it may not know:

```text
which correction path is semantically allowed
```

A minimal policy-linked outcome may therefore carry:

```python
@dataclass(frozen=True)
class PolicyRuleRef:
    contract_id: str
    rule_id: str
    version: int
```

and `SemanticOutcome` may later include optional fields such as:

```text
policy_ref
recovery_hint
retry_safety
intent_consistency
```

Example:

```json
{
  "decision_basis": "semantic_outcome",
  "error_type": "STALE_WRITE",
  "policy_ref": {
    "contract_id": "order_domain_v1",
    "rule_id": "order.payment.requires_fresh_version",
    "version": 1
  },
  "recovery_hint": "REFRESH_ACCEPTED_HISTORY_AND_REBUILD_ONCE"
}
```

This keeps the boundary clear:

```text
SemanticOutcome
→ describes what happened and which rule was involved

RuntimeDecisionPolicy
→ decides whether to allow, block, replay, retry, rebuild, quarantine, or escalate

Domain Policy Contract v0
→ provides the rule and recovery vocabulary used by the outcome / decision path
```

## Boundary

A semantic outcome describes what happened.

It should not directly own the final control action.

That responsibility belongs to `RuntimeDecisionPolicy`.

---


# Phase 5.5 — Order Domain Policy Contract v0

## Goal

Introduce a minimal machine-readable contract for the current order domain so that structured semantic outcomes can point to stable rule IDs and recovery hints.

This is a Stage 4B.5-style optional extension between:

```text
Structured Semantic Outcomes
```

and:

```text
Runtime Decision Policy
```

## Why

`SemanticOutcome` can explain what failed.

However, agentic retry and governed recovery also need a comparison source that says:

```text
which rule was violated
which recovery path is allowed
whether retry is safe
whether replay is allowed
whether human review is required
```

Without this layer, an agent may repeatedly modify a candidate action until Compass allows it.
That is not policy-guided recovery.
It is trial-and-error against the runtime gate.

## Minimal Contract Scope

The first contract should remain domain-specific and small.

It should cover only the current v1 order world:

- `INIT → CREATED`
- `CREATED → PAID`
- full-payment semantics
- positive amount rules
- idempotent replay rules
- idempotency conflict rules
- stale-write / reload-oriented recovery
- projection-drift rebuild-oriented recovery

It should not attempt to define:

- a general policy language
- policy promotion workflows
- release packs
- cross-domain governance
- full agent workflow orchestration

## Candidate Artifact

A future file may look like:

```text
contracts/order_domain_policy_contract_v1.yaml
```

Candidate shape:

```yaml
contract_id: order_domain_v1
domain: order
version: 1

rules:
  - id: order.transition.init_to_created
    type: transition
    from: INIT
    to: CREATED
    allowed: true

  - id: order.transition.created_to_paid
    type: transition
    from: CREATED
    to: PAID
    allowed: true

  - id: order.transition.init_to_paid
    type: transition
    from: INIT
    to: PAID
    allowed: false
    violation: DOMAIN_TRANSITION_VIOLATION
    recovery: BLOCK

  - id: order.payment.requires_fresh_version
    type: admission
    violation: STALE_WRITE
    recovery: REFRESH_ACCEPTED_HISTORY_AND_REBUILD_ONCE

  - id: order.request.same_id_same_fingerprint
    type: idempotency
    outcome: IDEMPOTENT_REPLAY
    recovery: ALLOW_REPLAY

  - id: order.request.same_id_different_fingerprint
    type: idempotency
    violation: IDEMPOTENCY_CONFLICT
    recovery: BLOCK

recovery_strategies:
  BLOCK:
    retryable: false
    human_required: false

  REFRESH_ACCEPTED_HISTORY_AND_REBUILD_ONCE:
    retryable: true
    max_attempts: 1
    required_action: reload_accepted_history

  ALLOW_REPLAY:
    retryable: false
    required_action: return_prior_accepted_result

  BLOCK_AND_ESCALATE:
    retryable: false
    human_required: true
```

## Runtime Meaning

This contract gives `SemanticOutcome` and `RuntimeDecisionPolicy` a stable rule source.

The runtime path becomes:

```text
Compass validation result
→ SemanticOutcome
→ optional policy_ref / recovery_hint
→ RuntimeDecisionPolicy
→ RuntimeDecision
→ ActionSafetyGate
```

## Completion Criteria

This phase is minimally useful when:

- an order-domain policy contract file exists
- rule IDs correspond to existing domain rules
- selected `SemanticOutcome` objects can reference `policy_ref`
- recovery hints cover at least block, replay, reload/rebuild-once, and escalate paths
- tests prove that policy-linked outcomes can drive runtime decisions

## Boundary

This is not a full policy governance system.

It is a domain-specific contract layer that makes Stage 4 outcomes more useful for agentic retry, recovery, replay, and audit.

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

IDEMPOTENT_REPLAY
→ ALLOW_REPLAY

SEMANTIC_CONFLICT / IDEMPOTENCY_CONFLICT
→ BLOCK

CONCURRENCY_RETRY
→ RETRY_AFTER_RELOAD or BLOCK

INFRASTRUCTURE_RETRY
→ RETRY_WITH_BACKOFF or ESCALATE

REBUILD_REQUIRED
→ REBUILD or QUARANTINE

AGENT_INTENT_DRIFT
→ BLOCK_AND_ESCALATE
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

Snapshot and projection trust should contribute to the semantic correctness signal. A state can be fresh but unsafe if snapshot trust checks fail, reducer version is untrusted, checkpoint and state disagree, or projection differs from accepted-history replay.

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
- isolated derived-state runtime / oblivious agent runtime
- separate read-side projection DB for untrusted agent observation
- controlled agent read API
- generalized semantic governance protocol

These are intentionally deferred.

The project should first prove:

```text
semantic truth
→ durable evidence
→ hardened accepted history
→ structured outcome
→ runtime decision
→ action safety
```

---

## Summary View

```text
Current:
Layer 1 write-side event truth validation ✅

Durable Write-side:
Stage 3.5B PR1 schema ✅
Stage 3.5B PR2 event store ✅
Stage 3.5B PR3 idempotency store ✅
Stage 3.5B PR4 transactional semantic write-side ✅
Stage 3.5B PR5 concurrency admission ✅

Dependency:
Stage 3.5C durable read-side baseline
Stage 3.5D replay-efficiency substrate
Stage 3.5E durable history hardening

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
isolated derived-state runtime
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

