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

The two roadmaps overlap around Stage 3.5B, Stage 3.5C, Stage 3.5D, and Stage 3.5E because Compass depends on durable write-side, durable read-side, replay-efficiency, and accepted-history hardening boundaries before stronger runtime validation grows.

However, this document avoids repeating detailed schema columns, migration details, and store test matrices.

Those belong in the implementation roadmap.

This document instead tracks how those implementation stages support the next Compass capabilities.

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

- Compass Phases 1–3 correspond to the current write-side validation and durable persistence dependencies across Stage 2, Stage 3, Stage 3.5B, Stage 3.5C, the Stage 3.5D replay-efficiency substrate, and the Stage 3.5E durable history hardening boundary.
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

The current system already supports:

- write-side candidate-event generation
- proof-carrying event structure
- Layer 1 transition validation
- validation dispatch
- basic `ALLOW` / `BLOCK` enforcement
- candidate vs accepted event identity boundary clarification
- rejection before invalid events enter accepted history
- PostgreSQL-backed accepted history through `PostgresEventStore`
- PostgreSQL-backed idempotency memory through `PostgresIdempotencyStore`
- Compass-guarded transactional write-side flow in Stage 3.5B PR4
- PostgreSQL-backed two-phase concurrency admission through Stage 3.5B PR5
- validation placement strategy through Stage 3.5B PR6
- durable order-event vocabulary hardening through Stage 3.5C PR0
- durable read-side schema baseline through Stage 3.5C PR1
- PostgreSQL-backed projection state persistence through Stage 3.5C PR2

This means Compass is already more than a passive checker.

It already has runtime control authority at the write-side boundary:

```text
invalid candidate event
→ blocked before accepted history
```

PR4 extends this authority into the durable PostgreSQL-backed write-side path:

```text
candidate event
→ Compass Layer 1 validation
→ append accepted event + record idempotency in one transaction
```

---

## Current Limitation

Compass does not yet fully protect derived runtime state.

The current Stage 3 projection baseline can derive state through a deterministic reducer / worker path, but Compass has not yet become a state-level validator.

That means the following question is not yet fully answered:

> Even if accepted history is valid, is the current read-side projection still faithful to that history?

This is the gap that later stages must close.

The durable write-side is now concurrency-admission-aware at the Stage 3.5B baseline level.

Stage 3.5B PR5 restored the concurrency/admission boundary for PostgreSQL-backed execution, Stage 3.5B PR6 introduced validation placement strategy as a Stage 4 prelude, Stage 3.5C PR0 hardened durable order-event vocabulary before read-side persistence begins, Stage 3.5C PR1 established the durable read-side schema boundary for projection state and checkpoint progress, and Stage 3.5C PR2 has made projection state durable through `PostgresProjectionStore`.

---

## Compass Evolution Principle

Compass should evolve from:

```text
write-side event truth
→ durable accepted history
→ durable derived state
→ snapshot trust / replay-efficiency substrate
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

Stage 3.5B PR4 preserves Layer 1 inside the PostgreSQL-backed transactional write-side flow.

---

# Phase 2 — Durable Write-Side Dependency

## Why Compass Needs This

Layer 1 protects accepted history, but accepted history must become durable before later runtime validation can be trusted across restart, retry, and partial failure.

Stage 3.5B provides this dependency.

The implementation roadmap owns the detailed PR sequence:

```text
PR1 Physical Schema + Local PostgreSQL + Migration ✅
PR2 PostgresEventStore ✅
PR3 PostgresIdempotencyStore ✅
PR4 Transactional Semantic Write-side Boundary ✅
PR5 PostgreSQL Concurrency Admission Boundary ✅
```

PR6 / Stage 4 prelude adds validation placement strategy:

```text
IN_TRANSACTION validation
PRE_TRANSACTION validation + append-time admission
ASYNC_AUDIT future
```

From the Compass perspective, Stage 3.5B matters because it turns accepted history into a durable validation source.

## Compass-Relevant Outcomes

Stage 3.5B gives Compass:

- durable accepted history
- durable event identity
- durable replay source
- durable idempotency result memory
- transactionally coordinated event append and idempotency record write
- Compass Layer 1 preserved before durable accepted-history mutation
- clear candidate / accepted identity boundary
- PostgreSQL-backed two-phase concurrency admission through PR5
- validation placement strategy through PR6
- minimal `PRE_TRANSACTION` validation path guarded by append-time admission

## Related Postmortems

- [From In-Memory Correctness to Durable Consistency](../postmortems/from_in_memory_correctness_to_durable_consistency.md)
- [From Git Local–Remote Drift to Database Immutability Boundaries](../postmortems/from_git_sync_to_db_immutability.md)
- [From Local PostgreSQL Setup to Defense-in-Depth Boundaries](../postmortems/from_local_postgres_to_defense_in_depth.md)
- [From Runtime Behavior to Durable Evidence](../postmortems/from_runtime_behavior_to_durable_evidence.md)
- [From Durable Persistence to Semantic Gate Preservation](../postmortems/from_durable_persistence_to_semantic_gate_preservation.md)
- [Autocommit, Transaction Boundaries, and Partial-Write Risk](../postmortems/autocommit_boundary_and_partial_write_risk.md)
- [Pre-Transaction Read Cleanup Boundary](../postmortems/pre_transaction_read_cleanup_boundary.md)

These explain why persistence is not just a backend swap.

For Compass, the important lesson is:

```text
Python-side semantic behavior is not durable evidence
unless the selected facts are persisted into an explicit evidence channel.
```

PR4 adds a second durable-persistence lesson:

```text
durable persistence hardening must preserve Compass semantic gates
```

## Related ADRs

- [ADR 0010 — Separate Transaction Atomicity from Concurrency Admission](../adr/0010_transaction_atomicity_vs_concurrency_admission.md)
- [ADR 0011 — Separate Validation Mode from Validation Placement Strategy](../adr/0011_validation_mode_vs_validation_placement.md)
- [ADR 0012 — Two-Phase Concurrency Admission for PostgreSQL Write-Side](../adr/0012_two_phase_concurrency_admission.md)

These clarify why PR4 transaction atomicity, PR5 concurrency admission, two-phase admission, and future validation placement strategy are separate concerns.

## Current Status

Stage 3.5B PR1 / PR2 / PR3 are complete.

Stage 3.5B PR4 establishes the transactional semantic write-side boundary.

Stage 3.5B PR5 is complete for PostgreSQL-backed two-phase concurrency admission.

Stage 3.5B PR6 is complete at the baseline level for validation placement strategy. It preserves `IN_TRANSACTION` as the default and adds a minimal `PRE_TRANSACTION` path guarded by append-time admission.

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

- durable projection state schema
- durable checkpoint state schema
- future durable projection state store
- future durable checkpoint store
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

Current major implementation focus after the Stage 3.5B durable write-side baseline.

Stage 3.5C PR0 has already hardened durable order-event vocabulary before the read-side baseline begins.

Stage 3.5C PR1 has established the durable read-side schema baseline:

```text
projection_states = derived runtime view
projection_checkpoints = worker progress metadata
order_events = accepted-history truth
```

Stage 3.5C PR2 has now implemented `PostgresProjectionStore`, which makes `projection_states` usable from the Python storage boundary.

This gives Compass Layer 2 a more concrete future durable target for drift comparison, but it does not yet implement Layer 2 validation, `PostgresCheckpointStore`, a PostgreSQL-backed projection worker, or replay / rebuild orchestration.

---

# Stage 3.5D Dependency — Persistence Optimization and Replay Efficiency

Before Compass Layer 2 grows into stronger runtime state validation, the persistence substrate may need one additional hardening stage:

```text
Stage 3.5D — Persistence Optimization & Replay Efficiency
```

This stage does not implement Layer 2 validation itself.

Instead, it improves the replay and recovery substrate that Layer 2 may later depend on.

Stage 3.5D treats snapshots as derived state-compression artifacts:

```text
accepted history = source of truth
snapshot = derived state compression
projection state = derived runtime view
```

The purpose is to reduce replay, rehydrate, and rebuild cost without allowing snapshots to replace accepted history.

Compass-relevant outcomes include:

- aggregate snapshot lineage back to accepted history
- snapshot-assisted replay that remains equivalent to full replay
- snapshot validity rules
- lineage, tail-continuity, schema-version, reducer-version, and payload-integrity checks
- fast-path vs authority-path distinction
- replay cost measurement
- safer persistence substrate before Layer 2 drift validation

This stage should remain persistence / replay hardening.

It qualifies snapshots for fast-path use, but it does not make snapshots the source of truth.

It should not absorb structured semantic outcomes, runtime decision policy, action safety, or dual-dimension governance.

---


# Stage 3.5E Dependency — Durable History and Permission Hardening

Before Compass grows into stronger runtime governance, the accepted-history substrate should be hardened against accidental or improper database mutation.

```text
Stage 3.5E — Durable History and Permission Hardening
```

This stage does not implement Layer 2 validation, structured semantic outcomes, or runtime decision policy.

Instead, it clarifies database authority around accepted history and derived state.

Compass depends on this distinction because later runtime governance will treat accepted history as durable evidence:

```text
accepted history = source of truth / durable evidence
projection state = derived runtime view
checkpoint = operational progress metadata
```

Stage 3.5E should therefore harden `order_events` without accidentally making mutable read-side tables immutable.

Compass-relevant outcomes include:

- clearer database role boundaries
- write-side runtime authority limited to accepted-history append behavior
- projection worker authority separated from write-side admission authority
- accepted-history tables protected from casual `UPDATE` / `DELETE`
- read-side tables left mutable for upsert, resume, reset, and rebuild
- stronger confidence that later Layer 2 comparisons are grounded in a hardened accepted-history source

This stage should remain durable storage / authority hardening.

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
