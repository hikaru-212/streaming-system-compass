# Implementation Roadmap

[← Back to Roadmaps Index](README.md)

## Purpose

This roadmap describes the intended implementation order of the project.

It is not merely a list of desired features.  
It is a sequencing guide for building the system without losing semantic clarity.

This version reflects the project position after the completion of Stage 3.5D:

- Stage 3.5B durable write-side implementation details have been moved to implementation notes.
- Stage 3.5C durable read-side implementation details have been moved to implementation notes.
- Stage 3.5D snapshot trust / replay-efficiency implementation details have been moved to implementation notes.
- Stage 3.5E remains the next implementation stage.
- Stage 4 and later stages remain forward-looking runtime governance work.

---

## Current Position

The project has completed an executable baseline across:

- transactional semantic core
- Compass Layer 1 write-side semantic validation
- deterministic in-memory projection runtime
- exact Decimal / money handling
- durable PostgreSQL-backed write-side persistence
- durable PostgreSQL-backed read-side persistence
- durable replay / rebuild validation
- projection snapshot trust / replay-efficiency baseline

This means:

- Stage 1 is complete at a baseline level.
- Stage 2 is complete at a baseline level.
- Stage 3 exists as a minimal executable read-side runtime baseline.
- Stage 3.5A is complete as the pre-persistence money / exact-value hardening step.
- Stage 3.5B is complete as the durable write-side baseline.
- Stage 3.5C is complete as the durable read-side baseline.
- Stage 3.5D is complete as the projection snapshot trust / replay-efficiency baseline.
- Write-side aggregate snapshot implementation is explicitly deferred.
- Stage 3.5E is the next implementation stage.

Detailed completed-stage execution records now live under:

- [Stage 3.5B Implementation Notes](../implementation_notes/stage_3_5b/)
- [Stage 3.5C Implementation Notes](../implementation_notes/stage_3_5c/)
- [Stage 3.5D Implementation Notes](../implementation_notes/stage_3_5d/)

The current major focus is:

- **Stage 3.5E — Durable History and Permission Hardening**

After Stage 3.5E, the project can proceed toward:

- Stage 4 runtime semantic validation, structured semantic outcomes, and runtime decision policy
- Stage 5 dual-dimension governance demo
- Stage 5+ isolated derived-state runtime / oblivious agent runtime evaluation

---

## Guiding Principle

The project should evolve from:

1. semantic truth
2. transactional execution
3. concurrency-safe admission
4. event truth validation
5. projection / runtime correctness
6. exact durable money semantics
7. candidate / accepted event identity boundary cleanup
8. durable write-side persistence semantics
9. durable read-side persistence semantics
10. persistence optimization / replay efficiency
11. snapshot trust qualification for fast-path replay
12. durable history immutability and permission hardening
13. runtime semantic outcomes
14. runtime decision policy
15. action safety gate
16. dual-dimension governance demo
17. later isolated derived-state runtime and adversarial hardening

This order is intentional.

The system should not attempt to solve chaos, analytics, broad governance, or distributed complexity before its semantic core, write-side safety boundaries, runtime semantics, and durable persistence boundaries are clear.

---

## Stage 1: Transactional Semantic Core

### Goal

Establish the write-side meaning of the system.

### Deliverable

A deterministic transactional baseline capable of:

- producing candidate events
- conditionally admitting accepted events
- persisting accepted history in the current baseline
- replaying aggregate state
- preventing duplicate semantic effects
- preventing stale writes through conditional admission

### Status

Implemented as the current write-side baseline.

---

## Stage 2: Event Truth Validation

### Goal

Integrate the first Compass layer into the transactional path.

### Deliverable

A write-side flow that can reject semantically inconsistent events before they enter accepted history, while preserving the distinction between:

- semantic validation through Compass
- conditional admission through the persistence / concurrency boundary
- idempotency replay / conflict classification

### Status

Implemented at a baseline level as the current Compass Layer 1 path.

---

## Stage 3: Projection Runtime Baseline

### Goal

Upgrade projection from replay helper into a real runtime subsystem.

### Deliverable

A read-side runtime capable of incremental state derivation and replay / rebuild through the same runtime path.

### Status

Implemented at a deterministic in-memory baseline level.

### Current Note

The current Stage 3 baseline establishes:

- reducer / worker separation
- projection-state and checkpoint-store separation
- replay-safe projection sequencing
- deterministic in-memory replay / rebuild behavior

It does not yet establish durable storage-backed runtime semantics.

---

## Stage 3.5A: Decimal Hardening Before Durable Persistence

### Goal

Ensure that money-like values are represented exactly before write-side or read-side durable persistence grows larger.

### Deliverable

An exact-money baseline that preserves semantic correctness before persistent storage is introduced more deeply.

### Status

Completed.

---

# Stage 3.5B: Durable Write-Side Baseline

## Goal

Move the write-side baseline from in-memory persistence toward durable PostgreSQL-backed semantics.

## Why

After Stage 3.5A, the next meaningful step was durable write-side evolution.

Accepted-history durability, idempotency durability, transaction grouping, append-only event-store shape, exact money persistence, and candidate / accepted event identity needed to be clarified before the rest of the runtime could grow larger.

## Status

Completed.

## Summary

Stage 3.5B established:

- PostgreSQL-backed `order_events`
- PostgreSQL-backed `idempotency_records`
- `PostgresEventStore`
- `PostgresIdempotencyStore`
- transactional write-side coordination
- Compass Layer 1 preserved before accepted-history mutation
- PostgreSQL-backed concurrency admission
- validation placement strategy

The important semantic boundaries from this stage are:

```text
transaction atomicity ≠ concurrency admission
validation mode ≠ validation placement
candidate event ≠ accepted fact
```

## Implementation Details

Detailed PR-level execution records are maintained in:

- [Stage 3.5B Implementation Notes](../implementation_notes/stage_3_5b/)

---

# Stage 3.5C: Durable Read-Side Baseline

## Goal

Move the read-side runtime from in-memory stores toward durable PostgreSQL-backed projection state, checkpoint progress, global-position consumption, and replay / rebuild validation.

## Why

After the durable write-side baseline was clear, the read-side could safely evolve toward durable projection-state storage and durable checkpoint storage.

Read-side state is not the source of truth.

```text
accepted history = authority
projection state = derived runtime state
checkpoint = operational progress metadata
```

## Status

Completed.

## Summary

Stage 3.5C established:

- durable order-event vocabulary hardening
- `projection_states`
- `projection_checkpoints`
- `PostgresProjectionStore`
- `PostgresCheckpointStore`
- `order_events.global_position`
- `PostgresProjectionEventSource`
- `ProjectionEventRecord`
- `PostgresProjectionWorker`
- projection state + checkpoint progress atomic persistence
- `GLOBAL_POSITION` checkpoint cursor
- durable replay / rebuild validation

The important semantic boundaries from this stage are:

```text
projection state = derived read model
checkpoint = operational progress metadata
accepted-history replay = authority path
```

## Implementation Details

Detailed PR-level execution records are maintained in:

- [Stage 3.5C Implementation Notes](../implementation_notes/stage_3_5c/)

---

# Stage 3.5D: Snapshot Trust Contract / Replay Efficiency

## Goal

Establish snapshot trust and replay-efficiency mechanisms after the durable write-side and durable read-side baselines are complete.

Stage 3.5D treats snapshots as derived state-compression artifacts.

It does not allow snapshots to replace accepted history as the source of truth.

## Why

Stage 3.5B established the durable write-side baseline.

Stage 3.5C established the durable read-side baseline.

Together, they answer:

```text
Can the system form a durable closed loop?
```

Stage 3.5D answered the next replay-efficiency question:

```text
As accepted history grows, how can replay, rehydrate, and rebuild costs be reduced without weakening source-of-truth semantics?
```

It also answered the snapshot trust question:

```text
When is a snapshot qualified for fast-path use without treating it as authority?
```

## Status

Completed.

## Summary

Stage 3.5D established:

- general snapshot trust contract boundary
- projection snapshot schema baseline
- `PostgresProjectionSnapshotStore`
- projection snapshot-assisted replay validation
- projection snapshot-assisted state resolution
- explicit aggregate snapshot trust deferral

The important semantic boundaries from this stage are:

```text
accepted history = authority
snapshot = derived state compression
fast path = qualified snapshot + tail replay + trust checks
authority path = full accepted-history replay
```

Stage 3.5D completes the read-side projection snapshot trust / replay-efficiency substrate.

Write-side aggregate snapshots are explicitly deferred because they may influence command validation and accepted-history admission.

## Implementation Details

Detailed PR-level execution records and snapshot-specific implementation notes are maintained in:

- [Stage 3.5D Implementation Notes](../implementation_notes/stage_3_5d/)

---

# Stage 3.5E: Durable History and Permission Hardening

## Goal

Harden the durable storage authority boundary after the durable write-side, durable read-side, and replay-efficiency baselines are clear.

Stage 3.5E focuses on making accepted history harder to rewrite accidentally or improperly at the database boundary.

## Why

Stage 3.5B establishes PostgreSQL-backed accepted history.

Stage 3.5C establishes PostgreSQL-backed durable read-side state.

Stage 3.5D improves replay, rehydrate, and rebuild efficiency without replacing accepted history.

After these baselines exist, the project can define database-level authority more accurately:

```text
order_events = accepted history / source of truth
idempotency_records = successful request-result memory
projection_states = mutable derived runtime view
projection_checkpoints = mutable worker progress metadata
```

This stage exists because these tables do not have the same mutability requirements.

`order_events` should move toward append-only accepted history.

`projection_states` and `projection_checkpoints` must remain mutable enough to support upsert, resume, reset, and rebuild.

If Stage 3.5D introduces aggregate snapshot tables, Stage 3.5E may also evaluate whether snapshot rows should follow append-only derived-artifact discipline. This is different from making snapshots the source of truth. It only protects derived artifact integrity.

## Main Work

Stage 3.5E may include:

- database role boundary documentation
- migration owner vs runtime role separation
- write-side runtime permission baseline
- projection worker permission baseline
- read-only observer permission baseline
- revoking runtime `UPDATE` / `DELETE` authority from `order_events`
- optional trigger-based rejection of `UPDATE` / `DELETE` on `order_events`
- tests proving runtime roles cannot rewrite accepted history
- documentation explaining why read-side tables remain mutable while accepted history is hardened
- optional snapshot table permission review if snapshot tables exist:
  - restrict casual UPDATE / DELETE on snapshot rows
  - preserve insert-only snapshot history if chosen
  - document why snapshot append-only protects derived artifact integrity, not source-of-truth authority

## Candidate Role Model

A minimal role model may distinguish:

```text
migration_owner
write_side_runtime
projection_worker
read_only_observer
```

Possible baseline permissions:

| Role | `order_events` | `idempotency_records` | `projection_states` | `projection_checkpoints` |
|---|---|---|---|---|
| `migration_owner` | schema owner | schema owner | schema owner | schema owner |
| `write_side_runtime` | SELECT / INSERT | SELECT / INSERT | no access or SELECT only | no access |
| `projection_worker` | SELECT | no access or SELECT | SELECT / INSERT / UPDATE | SELECT / INSERT / UPDATE |
| `read_only_observer` | SELECT | SELECT | SELECT | SELECT |

The exact grants should follow the final Stage 3.5C / 3.5D runtime shape.

## Completion Criteria

Stage 3.5E is complete at the baseline level when:

- accepted history is protected by database-level permission boundaries
- runtime roles cannot casually update or delete `order_events`
- projection worker permissions are separated from write-side event admission authority
- read-only observer access is separated from mutation authority
- mutable read-side tables remain able to support projection upsert, checkpoint updates, reset, and rebuild
- tests verify the core permission / append-only assumptions in local PostgreSQL
- documentation clearly states that append-only hardening protects accepted history, not derived read-side views

## Non-goals

Stage 3.5E does not implement:

- cloud IAM
- production secret-manager integration
- full deployment security architecture
- multi-tenant access control
- complex audit policy framework
- Compass Layer 2 validation
- structured `SemanticOutcome`
- runtime decision policy
- action safety gate
- cryptographic snapshot sealing
- HMAC signatures
- hash chains
- agent runtime isolation

Those belong to later production hardening or Stage 4 / Stage 5 runtime governance work.

## Boundary Statement

Stage 3.5E hardens storage authority.

It does not change the source of truth.

```text
accepted history remains the source of truth
permission hardening limits who can mutate storage
append-only enforcement reduces accidental or improper history rewrites
read-side state remains derived and rebuildable
```

---

# Stage 4: Runtime Semantic Validation and Runtime Decision Boundary

Stage 4 is not only an error classification stage.

It is the transition from:

```text
semantic failure detection
```

to:

```text
structured semantic outcome
→ runtime decision policy
→ action safety boundary
```

The core idea is:

> Error semantics are not only for observation.  
> They should give the runtime authority to continue, retry, rebuild, block, quarantine, stop, or escalate.

## Reasoning Bridge

Stage 4 follows from the limitation that raw exception strings, boolean results, and ad hoc rejection reasons are not enough for runtime governance.

For the reasoning behind this transition, see:

- [From Exception Strings to Governable Outcomes](../postmortems/from_exception_strings_to_governable_outcomes.md)

That postmortem explains why the project must evolve from:

```text
raise ValueError(...)
→ structured semantic outcome
→ runtime decision policy
→ runtime decision
→ action safety gate
→ layered trust / governance
```

The purpose is not to claim that Stage 4 is already implemented.

---

## Stage 4A — Layer 2 Minimal Validator

### Goal

Add the first read-side / state-level Compass validator.

Layer 1 protects:

```text
candidate event → accepted history
```

Layer 2 protects:

```text
accepted history → derived runtime state
```

### Detects

- projection drift
- replay vs persisted projection mismatch
- reducer mismatch
- checkpoint / state mismatch
- snapshot metadata invalidity
- snapshot hash mismatch
- unsupported snapshot schema
- untrusted snapshot reducer version
- snapshot tail discontinuity
- snapshot replay mismatch

### Minimal Flow

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

### Completion Criteria

- deterministically create at least 1–2 projection drift cases
- replay accepted history into expected state
- compare expected state vs persisted projection state
- emit a clear validation result

### Non-goal

Stage 4A should not yet decide what the runtime should do.

It only answers:

> Is derived state semantically correct?

---

## Stage 4B — Structured Semantic Outcome / Error Model v1

### Goal

Convert validation results from bool / exception / string forms into machine-readable semantic outcomes.

### Preferred Name

Use `SemanticOutcome` rather than only `ErrorModel`.

Reason:

Some outcomes are not exceptions.  
They may represent semantic drift, trust issues, violations, or action-safety risks.

### Minimal Structure

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

### Retry Reason Classification and Intent Consistency

Stage 4B should explicitly classify retry-like situations.

Retry is not a single category.

A retry-like situation may represent:

- idempotent replay of the same request identity
- idempotency conflict where the same request identity carries different command meaning
- stale-write retry caused by concurrency admission
- transient infrastructure retry
- rebuild-oriented retry caused by projection / snapshot drift
- future agent intent drift where the agent claims to retry the same task but changes the intended meaning

This classification should belong to `SemanticOutcome` / request-attempt evidence design.

It should not be added to `idempotency_records`.

Candidate context fields:

```text
retry_observed
retry_class
retry_cause
retry_safety
intent_consistency
idempotency_verdict
admission_verdict
validation_verdict
stored_fingerprint
incoming_fingerprint
expected_version
actual_version
```

Candidate values:

```text
retry_class:
- IDEMPOTENT_REPLAY
- CONCURRENCY_RETRY
- INFRASTRUCTURE_RETRY
- SEMANTIC_CONFLICT
- SEMANTIC_DRIFT
- REBUILD_REQUIRED
- UNKNOWN

retry_safety:
- SAFE_TO_REPLAY
- SAFE_TO_RETRY_AFTER_RELOAD
- RETRY_WITH_BACKOFF
- REBUILD_REQUIRED
- NOT_RETRYABLE
- BLOCK_AND_ESCALATE
- UNKNOWN

intent_consistency:
- SAME_INTENT
- SAME_IDENTITY_DIFFERENT_MEANING
- NOT_AN_IDEMPOTENCY_REPLAY
- AGENT_INTENT_DRIFT
- NOT_APPLICABLE
- UNKNOWN
```

### Why `reversibility` Matters

Policy must know whether the failure is:

- reversible
- rebuildable
- recoverable
- irreversible boundary risk

Examples:

- projection drift → reversible / rebuildable
- invalid transition before event append → irreversible boundary risk
- stale checkpoint → operational risk
- reducer mismatch → high severity semantic risk

### Minimal Error Types

- `SEMANTIC_PROJECTION_DRIFT`
- `CHECKPOINT_STATE_MISMATCH`
- `REPLAY_REDUCER_MISMATCH`
- `DOMAIN_TRANSITION_VIOLATION`
- `IRREVERSIBLE_BOUNDARY_RISK`
- `OPERATIONAL_STALENESS`
- `SNAPSHOT_METADATA_INVALID`
- `SNAPSHOT_HASH_MISMATCH`
- `SNAPSHOT_SCHEMA_UNSUPPORTED`
- `SNAPSHOT_REDUCER_VERSION_UNTRUSTED`
- `SNAPSHOT_TAIL_DISCONTINUITY`
- `SNAPSHOT_REPLAY_MISMATCH`
- `IDEMPOTENCY_CONFLICT`
- `STALE_WRITE`
- `AGENT_INTENT_DRIFT`

### Completion Criteria

- projection drift emits `SemanticOutcome`
- outcome contains context and evidence
- tests assert structured fields
- tests do not depend only on exception message strings

### Boundary

Stage 4B classifies what happened.

It does not decide what the runtime should do.

---


## Stage 4B.5 — Order Domain Policy Contract v0

### Goal

Add a small domain-specific policy contract for the current order/payment model so that `SemanticOutcome` can reference stable rule IDs and recovery strategies.

This stage should be treated as an optional Stage 4 extension between structured outcomes and runtime decisions.

It should not become a general-purpose policy framework.

### Why

Stage 4B gives the system structured semantic outcomes.

However, an outcome that only says:

```text
what failed
why it failed
```

is still not enough for governed agentic retry.

A retrying agent or workflow also needs to know:

```text
which rule was violated
whether retry is allowed
which recovery path is semantically valid
whether replay is allowed
whether the action must be blocked or escalated
```

Without a rule / recovery source, retry can degrade into blind trial-and-error against Compass.

The purpose of Stage 4B.5 is to provide a minimal comparison source for policy-guided recovery.

### Candidate Artifact

Introduce a narrow contract file such as:

```text
contracts/order_domain_policy_contract_v1.yaml
```

The contract should be derived from the existing Order Domain v1 rules and should cover only the current minimal commerce model.

Candidate scope:

- allowed transitions: `INIT → CREATED`, `CREATED → PAID`
- forbidden transitions: `INIT → PAID`, `PAID → PAID` for new requests
- positive amount rules
- full-payment semantics for v1
- idempotent replay with same request identity and same semantic fingerprint
- idempotency conflict for same request identity with different semantic fingerprint
- stale-write recovery by reloading accepted history and rebuilding the candidate once
- projection drift recovery by rebuild / quarantine decision

### Candidate YAML Shape

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

  - id: order.transition.paid_to_paid_new_request
    type: transition
    from: PAID
    to: PAID
    allowed: false
    violation: DUPLICATE_PAYMENT_ATTEMPT
    recovery: BLOCK

  - id: order.request.same_id_same_fingerprint
    type: idempotency
    outcome: IDEMPOTENT_REPLAY
    recovery: ALLOW_REPLAY

  - id: order.request.same_id_different_fingerprint
    type: idempotency
    violation: IDEMPOTENCY_CONFLICT
    recovery: BLOCK

  - id: order.admission.requires_fresh_version
    type: admission
    violation: STALE_WRITE
    recovery: REFRESH_ACCEPTED_HISTORY_AND_REBUILD_ONCE

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

### SemanticOutcome Extension

Stage 4B.5 may add a small policy reference type:

```python
@dataclass(frozen=True)
class PolicyRuleRef:
    contract_id: str
    rule_id: str
    version: int
```

`SemanticOutcome` may then include optional fields such as:

```python
policy_ref: PolicyRuleRef | None
recovery_hint: str | None
```

The important point is that `SemanticOutcome` remains descriptive.

It may identify the violated or relevant rule, but it should not directly execute the recovery decision.

### Relationship to Stage 4C

Stage 4C can consume:

```text
SemanticOutcome.error_type
SemanticOutcome.policy_ref
SemanticOutcome.recovery_hint
```

and produce:

```text
RuntimeDecision
```

This keeps the flow explicit:

```text
Domain Policy Contract
→ SemanticOutcome
→ RuntimeDecisionPolicy
→ RuntimeDecision
→ ActionSafetyGate
```

### Completion Criteria

Stage 4B.5 is minimally complete when:

- `contracts/order_domain_policy_contract_v1.yaml` exists
- it contains rule IDs for the current v1 order/payment model
- it contains recovery strategies for block, replay, reload/rebuild-once, and escalate
- `SemanticOutcome` can optionally reference `policy_ref`
- tests prove at least a few outcomes are linked to rule IDs
- runtime decision tests can consume recovery hints without hardcoding every rule directly in the decision policy

### Non-goals

Stage 4B.5 does not implement:

- a general policy authoring platform
- compiled execution plans
- release packs
- policy promotion workflow
- policy diff tooling
- cross-domain governance
- agent workflow orchestration

---

## Stage 4C — Runtime Decision Policy v1

### Goal

Convert `SemanticOutcome` into `RuntimeDecision`.

This is the detect → classify → decide step.

If Stage 4B.5 is implemented, this policy may also consume `policy_ref` and `recovery_hint` from `SemanticOutcome` so that decisions are guided by the order-domain contract rather than only by hardcoded error-code mapping.

### Minimal Structure

```python
class RuntimeAction(Enum):
    ALLOW = "allow"
    BLOCK = "block"
    REBUILD = "rebuild"
    ESCALATE = "escalate"
    QUARANTINE = "quarantine"
```

```python
@dataclass(frozen=True)
class RuntimeDecision:
    action: RuntimeAction
    allowed: bool
    reason: str
    outcome_id: str
    requires_human_review: bool = False
```

```python
class RuntimeDecisionPolicy:
    def decide(self, outcome: SemanticOutcome) -> RuntimeDecision:
        ...
```

### Minimal Policy Rules

- `ok=True` → `ALLOW`
- `SEMANTIC_PROJECTION_DRIFT` + `severity=ERROR` → `REBUILD` or `QUARANTINE`
- `CHECKPOINT_STATE_MISMATCH` → `REBUILD` or `ESCALATE`
- `REPLAY_REDUCER_MISMATCH` → `BLOCK` or `ESCALATE`
- `DOMAIN_TRANSITION_VIOLATION` → `BLOCK`
- `IRREVERSIBLE_BOUNDARY_RISK` → `BLOCK`

Retry-related mappings may include:

```text
IDEMPOTENT_REPLAY
→ ALLOW_REPLAY

IDEMPOTENCY_CONFLICT / SEMANTIC_CONFLICT
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

`SemanticOutcome` describes why the retry-like situation occurred.

`RuntimeDecisionPolicy` decides whether the system should replay, retry, reload, rebuild, block, quarantine, or escalate.

### Completion Criteria

- policy converts projection drift outcome into `REBUILD` / `QUARANTINE` / `ESCALATE`
- policy converts irreversible semantic violation into `BLOCK`
- tests assert `decision.action`
- tests assert `allowed=True / False`
- irreversible action does not proceed when decision is `BLOCK`

---

## Stage 4D — Layer 1 / Layer 2 Outcome + Decision Alignment

### Goal

Align write-side Layer 1 and read-side Layer 2 around the same flow:

```text
SemanticOutcome
        ↓
RuntimeDecisionPolicy
        ↓
RuntimeDecision
```

### Why This Comes After Stage 4C

Layer 1 already works.

The safer order is:

1. build Layer 2 validation
2. define structured outcomes
3. define decision policy
4. backport / align Layer 1 with the same outcome + decision family

### Target Flow

Layer 1:

```text
candidate event violates transition truth
        ↓
SemanticOutcome(
  error_type=DOMAIN_TRANSITION_VIOLATION,
  layer=LAYER_1_WRITE_SIDE,
  reversibility=IRREVERSIBLE_BOUNDARY_RISK
)
        ↓
RuntimeDecision(BLOCK)
        ↓
event does not enter EventStore
```

Layer 2:

```text
persisted projection state differs from replay expected state
        ↓
SemanticOutcome(
  error_type=SEMANTIC_PROJECTION_DRIFT,
  layer=LAYER_2_READ_SIDE,
  reversibility=REVERSIBLE
)
        ↓
RuntimeDecision(REBUILD or QUARANTINE)
```

### Completion Criteria

- Layer 1 invalid transition emits `SemanticOutcome`
- Layer 1 invalid transition maps to `RuntimeDecision(BLOCK)`
- Layer 2 drift maps to `RuntimeDecision(REBUILD / QUARANTINE / ESCALATE)`
- both layers can be described as Compass semantic runtime control

---

## Stage 4E — Domain Action Safety Gate

### Goal

Add the first domain-level safety gate before dependent actions.

Do not start with an agent protocol.  
Do not start with a universal executor.

Start with the project domain and define a minimal action-safety boundary.

### Candidate Domain Actions

These can be simulations rather than real external calls:

- `EMIT_DOWNSTREAM_SIGNAL`
- `GENERATE_SETTLEMENT_REPORT`
- `MARK_PROJECTION_TRUSTED`
- `ADVANCE_EXTERNAL_EXPORT`

### Minimal Flow

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

### Completion Criteria

- unsafe semantic outcome blocks dependent action
- projection drift can block or quarantine downstream action
- clean semantic state allows action
- tests prove blocked action is not executed

---

# Stage 5: Dual-Dimension Governance Demo

## Goal

Create a reviewer-facing demo that evaluates system trust using two dimensions:

```text
semantic correctness × operational freshness
```

The purpose of this stage is not only to observe whether the system is correct after the fact.

The purpose is to decide whether a dependent action is safe before it executes.

Snapshot / projection trust should contribute to the semantic correctness signal. A state may be operationally fresh but semantically untrusted if projection differs from accepted-history replay, snapshot trust checks fail, reducer version is untrusted, or checkpoint and projection state disagree.

This is especially important for irreversible or high-risk actions, where post-hoc monitoring is too late.

The final question is:

> Is this state true enough, fresh enough, and safe enough to act on?

## Core Matrix

|  | Operational Fresh | Operational Stale |
|---|---|---|
| Semantic Correct | Safe to act | Semantically correct but stale |
| Semantic Incorrect | Operationally healthy but semantically unsafe | Unsafe / stop / escalate |

## Four Required Cases

### Case 1 — Semantic Correct + Operational Fresh

Signals:

- accepted history replay equals persisted projection state
- checkpoint recent
- worker healthy

Decision:

- `SAFE_TO_ACT`

### Case 2 — Semantic Correct + Operational Stale

Signals:

- accepted history replay equals persisted projection state
- checkpoint too old
- worker heartbeat stale

Decision:

- `STALE_BUT_SEMANTICALLY_VALID`
- `REFRESH_BEFORE_ACTION`
- or `ESCALATE`

### Case 3 — Semantic Incorrect + Operational Fresh

Signals:

- worker recently ran
- checkpoint fresh
- projection state differs from replay expected state

Decision:

- `BLOCK_ACTION`
- `REBUILD_PROJECTION`

This is a key project insight:

> Freshness does not imply correctness.

### Case 4 — Semantic Incorrect + Operational Stale

Signals:

- projection drift exists
- checkpoint stale
- worker heartbeat stale

Decision:

- `STOP`
- `QUARANTINE`
- `ESCALATE`

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

```python
class DualDimensionTrustEvaluator:
    def evaluate(
        self,
        semantic_signal: SemanticSignal,
        operational_signal: OperationalSignal,
    ) -> ActionSafetyVerdict:
        ...
```

## Demo Story

The final demo should show:

1. Layer 1 blocks invalid event truth before accepted history.
2. Layer 2 detects projection drift from accepted history replay.
3. `SemanticOutcome` explains the failure with evidence.
4. `RuntimeDecisionPolicy` converts semantic outcome into `BLOCK` / `REBUILD` / `ESCALATE`.
5. `DualDimensionTrustEvaluator` combines semantic correctness and operational freshness.
6. `ActionSafetyGate` blocks unsafe dependent action when semantic correctness or operational freshness is insufficient.

## Completion Criteria

- README can explain the demo in 3–5 minutes
- demo script can produce all 4 matrix cases
- tests cover the 4 matrix cases
- semantic incorrect + operational fresh case is clearly shown
- semantic correct + operational stale case is clearly shown
- action-safety verdict is explicit
- docs clearly separate implemented vs future work

---

# Later Work: Governance and Chaos Hardening

After Stage 5, later work may include:

- DLQ
- out-of-order buffering
- watermark semantics
- multi-worker coordination
- stronger transaction boundaries
- real observability integration
- richer policy engine
- chaos testing
- agent tool interface
- generalized semantic governance protocol

These are intentionally deferred until the core semantic and runtime-decision model is stable.

---

## Summary View

```text
Stage 1:
Transactional Semantic Core ✅

Stage 2:
Compass Layer 1 Write-side Validation ✅

Stage 3:
Projection Runtime Baseline ✅

Stage 3.5A:
Decimal / Money Hardening ✅

Stage 3.5B:
Durable Write-side Baseline
  PR1 Schema + Docker + Migration ✅
  PR2 PostgresEventStore ✅
  PR3 PostgresIdempotencyStore ✅
  PR4 Transactional Semantic Write-side Boundary ✅
  PR5 PostgreSQL Concurrency Admission Boundary ✅
  PR6 Validation Placement Strategy ✅

Stage 3.5C PR0:
Durable Order Event Vocabulary Hardening ✅

Stage 3.5C:
Durable Read-side Baseline
  PR1 Durable Read-Side Schema Baseline
  PR2 PostgresProjectionStore
  PR3 PostgresCheckpointStore
  PR4 PostgreSQL-Backed Projection Worker
  PR5 Durable Replay / Rebuild Validation
  PR6 Documentation and Completion Alignment

Stage 3.5D:
Persistence Optimization & Replay Efficiency

Stage 3.5E:
Durable History and Permission Hardening

Stage 4:
Runtime Semantic Validation and Runtime Decision Boundary
  4A Layer 2 Minimal Validator
  4B Structured Semantic Outcome / Error Model v1
  4B.5 Order Domain Policy Contract v0
  4C Runtime Decision Policy v1
  4D Layer 1 / Layer 2 Outcome + Decision Alignment
  4E Domain Action Safety Gate

Stage 5:
Dual-Dimension Governance Demo
  semantic correctness × operational freshness
  action safety verdict
```

---

## Final Summary

The intended evolution is:

```text
durable truth
→ derived truth validation
→ replay-efficiency hardening
→ durable history hardening
→ structured semantic outcome
→ runtime decision policy
→ action safety gate
→ dual-dimension governance demo
```

The project is not only trying to know that something failed.

It is trying to make semantic failure understandable enough that the runtime can decide whether to continue, rebuild, block, quarantine, stop, or escalate.


---

# Stage 5+ / Later Governance Hardening

## Isolated Derived-State Runtime / Oblivious Agent Runtime

Future versions of Compass may isolate untrusted agents from the sovereign event store.

This is not a Stage 3.5C, Stage 3.5D, or Stage 4 requirement.

The future model is:

```text
Sovereign Event Store
→ Projection Pipeline
→ Isolated Derived-State DB / controlled read boundary
→ Agent observes derived state
→ Agent proposes candidate action
→ Compass validates against accepted history
→ accepted event is appended only by the system kernel
```

Core principles:

- agents should not directly read or write accepted history
- agents should observe only derived state through a controlled read boundary
- agents should submit candidate actions rather than mutate truth directly
- Compass remains the admission authority
- accepted event history remains the source of truth
- the derived-state DB can be discarded and rebuilt from accepted history

This should be revisited only after the Stage 5 dual-dimension governance demo is stable, ActionSafetyGate exists, and an agent-facing tool interface becomes concrete.
