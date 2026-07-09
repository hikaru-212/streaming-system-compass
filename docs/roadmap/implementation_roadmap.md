# Implementation Roadmap

[← Back to Roadmaps Index](README.md)

## Purpose

This roadmap describes the intended implementation order of the project.

It is not merely a list of desired features.  
It is a sequencing guide for building the system without losing semantic clarity.

This version reflects the project position after the completion of Stage 4A:

- Stage 3.5B durable write-side implementation details have been moved to implementation notes.
- Stage 3.5C durable read-side implementation details have been moved to implementation notes.
- Stage 3.5D snapshot trust / replay-efficiency implementation details have been moved to implementation notes.
- Stage 3.5E durable history and permission hardening is complete.
- Stage 4A SemanticOutcome core is complete.
- Stage 4B DecisionReceipt / DiagnosticTrace is now the next implementation stage.
- Stage 5 and later stages remain forward-looking governance / production-hardening work.

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
- durable history and permission hardening baseline

This means:

- Stage 1 is complete at a baseline level.
- Stage 2 is complete at a baseline level.
- Stage 3 exists as a minimal executable read-side runtime baseline.
- Stage 3.5A is complete as the pre-persistence money / exact-value hardening step.
- Stage 3.5B is complete as the durable write-side baseline.
- Stage 3.5C is complete as the durable read-side baseline.
- Stage 3.5D is complete as the projection snapshot trust / replay-efficiency baseline.
- Stage 3.5E is complete as the durable history and permission hardening baseline.
- Write-side aggregate snapshot implementation is explicitly deferred.
- Stage 4A is complete as the SemanticOutcome core.
- Stage 4B is the next implementation stage.

Detailed completed-stage execution records now live under:

- [Stage 3.5B Implementation Notes](../implementation_notes/stage_3_5b/)
- [Stage 3.5C Implementation Notes](../implementation_notes/stage_3_5c/)
- [Stage 3.5D Implementation Notes](../implementation_notes/stage_3_5d/)
- [Stage 3.5E Implementation Notes](../implementation_notes/stage_3_5e/)
- [Stage 4A Implementation Notes](../implementation_notes/stage_4a/)

The current major focus is:

- **Stage 4B — DecisionReceipt / DiagnosticTrace**

After Stage 4A, the project can now proceed toward:

- Stage 4B DecisionReceipt / DiagnosticTrace: durable runtime evidence records, diagnostic traces, evidence shape, and correlation boundaries
- Stage 5 dual-dimension governance demo / action safety
- Stage 5+ production and agent-facing hardening

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
13. runtime semantic governance / SemanticOutcome core
14. decision receipts / runtime evidence
15. strategy selection and retry governance
16. action safety gate / dual-dimension governance demo
17. later production and agent-facing hardening

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
- [Stage 3.5E Implementation Notes](../implementation_notes/stage_3_5e/)
- [Stage 4A Implementation Notes](../implementation_notes/stage_4a/)

---

# Stage 3.5E: Durable History and Permission Hardening

## Goal

Harden the durable storage authority boundary after the durable write-side, durable read-side, and replay-efficiency baselines became clear.

Stage 3.5E made accepted history harder to rewrite accidentally or improperly at the database permission boundary while preserving controlled mutability for derived runtime artifacts.

## Why

Stage 3.5B established PostgreSQL-backed accepted history.

Stage 3.5C established PostgreSQL-backed durable read-side state.

Stage 3.5D improved replay, rehydrate, and rebuild efficiency without replacing accepted history.

After those baselines existed, the project could define database-level authority more accurately:

```text
order_events = accepted history / source of truth
idempotency_records = successful request-effect evidence
projection_states = mutable derived runtime view
projection_checkpoints = mutable worker progress metadata
projection_snapshots = derived state compression / evidence artifact
```

Stage 3.5E exists because these tables do not have the same authority level or mutability requirements.

## Status

Completed.

## Summary

Stage 3.5E established:

- durable history permission boundary documentation
- PostgreSQL role / privilege baseline
- accepted-history mutation hardening tests
- successful idempotency receipt rewrite-prevention tests
- accepted-history global-position sequence permission tests
- derived-state mutation permission tests
- projection snapshot insert-oriented evidence protection
- test-time `SET ROLE` permission probing boundary
- minimal actor metadata boundary
- explicit deferral of full RBAC, production login identity wiring, connection-pool isolation, chaos tests, and Stage 4 governance objects

The implemented runtime responsibility roles are:

```text
compass_migration_owner
compass_app_writer
compass_projection_worker
compass_snapshot_worker
compass_readonly
```

The completed baseline preserves the intended authority split:

```text
accepted history
= mutation-restricted authority

successful idempotency receipts
= insert-once request-effect evidence under the current schema

derived runtime state
= controlled mutable / rebuildable operational state

projection snapshots
= derived insert-oriented evidence artifacts, not accepted-history authority
```

## Implemented Work

Stage 3.5E completed:

- database role boundary documentation
- migration owner vs runtime responsibility-role separation
- write-side runtime permission baseline
- projection worker permission baseline
- snapshot worker permission baseline
- read-only observer permission baseline
- runtime `UPDATE` / `DELETE` restriction for `order_events`
- runtime `UPDATE` / `DELETE` restriction for `idempotency_records` under the current successful-receipt design
- runtime sequence-usage restriction for `order_events_global_position_seq`
- tests proving runtime roles cannot rewrite accepted history
- tests proving runtime roles cannot rewrite successful idempotency receipts
- tests proving only the intended writer role can consume the accepted-history global-position sequence
- tests proving derived runtime tables remain operationally mutable through intended roles
- tests proving snapshot records are insert-oriented and not rewritable by normal runtime roles
- documentation explaining why read-side tables remain mutable while accepted history is hardened
- documentation clarifying that `created_by`-style metadata is producer metadata, not governance decision evidence

## Final Role Model

The implemented baseline distinguishes:

```text
compass_migration_owner
= migration / setup authority, not a normal runtime role

compass_app_writer
= write-side runtime; may append accepted events and insert successful idempotency receipts

compass_projection_worker
= read-side projection runtime; may mutate derived projection state and checkpoints

compass_snapshot_worker
= snapshot artifact producer; may insert projection snapshots and inspect required source state

compass_readonly
= observation role; may read but not mutate durable state
```

## Completion Result

Stage 3.5E is complete at the baseline level because:

- accepted history is protected by database-level permission boundaries
- normal runtime roles cannot casually update or delete `order_events`
- successful idempotency receipts cannot be casually rewritten by normal runtime roles
- projection worker permissions are separated from write-side event admission authority
- read-only observer access is separated from mutation authority
- mutable read-side tables remain able to support projection upsert, checkpoint updates, reset, and rebuild
- snapshot records are insert-oriented evidence artifacts rather than mutable authority
- security permission tests verify the core role / privilege assumptions in local PostgreSQL
- documentation clearly states that permission hardening protects authority boundaries without making derived read-side views authoritative

## Non-goals

Stage 3.5E did not implement:

- cloud IAM
- production secret-manager integration
- production login identity wiring
- connection-pool role isolation
- full deployment security architecture
- multi-tenant access control
- complex audit policy framework
- actor registry
- user table
- login / session auth
- Compass Layer 2 validation
- structured `SemanticOutcome`
- `DecisionReceipt`
- runtime decision policy
- action safety gate
- cryptographic snapshot sealing
- HMAC signatures
- hash chains
- agent runtime isolation
- production-like chaos / concurrency tests

Those belong to Stage 4, Stage 5, or later production-hardening work.

## Boundary Statement

Stage 3.5E hardened storage authority.

It did not change the source of truth.

```text
accepted history remains the source of truth
permission hardening limits who can mutate storage
derived read-side state remains operational and rebuildable
producer metadata does not equal trust evidence
actor metadata does not equal governance decision evidence
```

Detailed execution records are maintained in:

- [Stage 3.5E Implementation Notes](../implementation_notes/stage_3_5e/)
- [Stage 4A Implementation Notes](../implementation_notes/stage_4a/)

---

# Stage 4: Runtime Semantic Governance

## Goal

Stage 4 introduces the first public-facing runtime semantic governance layer after the durable history, snapshot trust, and minimal actor / permission baselines are in place.

The goal is not to add another pile of validators, logs, or retry labels.

The goal is to make runtime correctness evidence governable:

```text
technical evidence
→ semantic interpretation
→ durable evidence
→ policy-linked decision
→ execution strategy
→ retry governance
```

Stage 4 is where Compass begins to answer:

> Given technical runtime evidence, what does this mean for semantic correctness, and what should the system be allowed to do next?

---

## Why Stage 4 Comes After Stage 3.5E

Stage 3.5E completed the minimal durable-history and permission boundary needed before runtime governance grows:

- accepted history has stronger mutation boundaries
- derived state remains operationally mutable under controlled runtime roles
- snapshot artifacts remain derived and subordinate to accepted history
- runtime role responsibility is clearer
- minimal actor metadata is separated from future governance decision evidence

Stage 4 can now build on this foundation without mixing authority, derived state, actor identity, and governance decisions into one layer.

---

## Core Principle

Stage 4 preserves the following distinctions:

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

These distinctions prevent Compass from treating a raw exception, a failed replay, a stale snapshot, a retry attempt, or a fast path as if each already carried enough semantic meaning to decide what should happen next.

---

## Public Stage 4 Sequence

The public Stage 4 sequence is:

```text
Stage 4A — SemanticOutcome Core
Stage 4B — DecisionReceipt / Runtime Evidence Record
Stage 4B.1 — DiagnosticTrace / ResolutionTrace Boundary
Stage 4B.2 — Measurement Matrix / Cost Evidence Inventory
Stage 4B.5 — Order Domain Policy Contract v0
Stage 4C — RuntimeDecisionPolicy
Stage 4C.5 — Layer 1 / Layer 2 Outcome Alignment
Stage 4D — StrategySelector / Fast-Path Health Policy
Stage 4E — Retry Governance / Attempt Classification
```

This sequence is intentionally staged.

Compass should first define semantic meaning, then preserve decision evidence, then connect outcomes to policy, then decide runtime action, then choose execution strategy, and only then govern retries.

---

## Stage 4A — SemanticOutcome Core

### Goal

Stage 4A defines the semantic outcome vocabulary for runtime correctness.

Status: Completed.

It maps technical runtime evidence into structured semantic meaning.

Examples of technical evidence include:

- replay validation result
- projection drift detection
- snapshot trust failure
- snapshot fast-path unavailability
- idempotency classification
- concurrency conflict
- unresolved runtime state

Stage 4A does not make final runtime decisions directly.

It should answer:

```text
What does this evidence mean semantically?
```

not:

```text
Which execution path is cheapest?
```

### Non-goals

Stage 4A does not implement:

- receipt persistence
- diagnostic trace tables
- policy contract
- strategy selector
- retry governance
- benchmark suite
- action safety gate

---

## Stage 4B — DecisionReceipt / Runtime Evidence Record

### Goal

Stage 4B is the next implementation stage.

It records the semantic outcome and the evidence used to produce it.

A receipt should preserve summary-level runtime evidence:

- what semantic outcome was produced
- what evidence source was used
- what boundary was evaluated
- which actor or runtime role was involved
- whether fallback, rebuild, quarantine, review, or retry may be required
- selected timing / cost summaries when relevant

A receipt is not a full diagnostic trace table.

It should make runtime semantic decisions reviewable without turning every internal detail into permanent business history.

---

## Stage 4B.1 — DiagnosticTrace / ResolutionTrace Boundary

### Goal

Stage 4B.1 separates detailed failure-path diagnostics from primary semantic results and decision receipts.

The rule is:

```text
resolved state belongs in the primary result only when resolution succeeds
partial progress belongs in diagnostic trace
```

This keeps primary contracts strict while still preserving useful investigation evidence when resolution fails.

---

## Stage 4B.2 — Measurement Matrix / Cost Evidence Inventory

### Goal

Stage 4B.2 defines what cost and timing evidence should be observable before StrategySelector can make cost-aware decisions.

This is not a benchmark suite.

It is a measurement vocabulary for later runtime governance.

Stage 4B.2 should help distinguish:

```text
semantic trust
≠
execution cost
≠
runtime strategy
```

The purpose is not to always choose the fastest path.

The purpose is to eventually choose the lowest-cost path among semantically acceptable paths.

### Public Boundary

Stage 4B.2 may define high-level measurement categories such as:

- validation cost
- replay cost
- resolver cost
- transaction duration
- lock wait
- retry count
- tail length
- snapshot usage
- receipt usage
- fallback usage
- semantic risk level

It should not yet become a production benchmark suite, performance dashboard, or automatic optimization system.

---

## Stage 4B.5 — Order Domain Policy Contract v0

### Goal

Stage 4B.5 introduces a narrow policy-contract boundary for the current order/payment domain.

The purpose is to connect semantic outcomes to stable rule references and recovery hints without turning Stage 4 into a general policy platform.

Core boundary:

```text
policy contract defines intended correctness
Compass verifies runtime semantic truth
runtime policy decides allowed action
```

Policy contract does not replace Compass.

Compass does not replace policy contract.

### Non-goals

Stage 4B.5 does not implement:

- general policy authoring platform
- policy promotion workflow
- cross-domain governance
- automatic policy evolution
- agent workflow orchestration

---

## Stage 4C — RuntimeDecisionPolicy

### Goal

Stage 4C converts semantic outcomes and supporting evidence into runtime decisions.

It answers:

```text
Given this semantic outcome and evidence, what should the system be allowed to do?
```

Examples of runtime decisions may include:

- allow
- block
- replay prior accepted result
- fallback to authority
- rebuild
- quarantine
- retry after reload
- escalate

Stage 4C decides what action is semantically allowed.

It does not choose the cheapest execution path. That belongs to Stage 4D.

---

## Stage 4C.5 — Layer 1 / Layer 2 Outcome Alignment

### Goal

Stage 4C.5 aligns write-side Layer 1 and read-side Layer 2 around compatible semantic outcome and runtime decision vocabulary.

Layer 1 protects:

```text
candidate event → accepted history
```

Layer 2 protects:

```text
accepted history → derived runtime state
```

They should not become separate semantic worlds.

The purpose of Stage 4C.5 is alignment, not rewriting the already-working write-side admission model.

---

## Stage 4D — StrategySelector / Fast-Path Health Policy

### Goal

Stage 4D selects execution strategy under changing runtime conditions.

It should choose among paths that are already allowed by semantic outcome, policy contract, and runtime decision.

Examples of strategy questions:

- should the runtime use authority replay or snapshot fast path?
- is a receipt-backed trusted snapshot sufficient?
- should a repeated fast-path failure temporarily disable the fast path?
- should projection be rebuilt or quarantined?
- should write-side contention prefer optimistic or pessimistic admission strategy?

Important principle:

```text
StrategySelector should not choose the fastest path.
It should choose the lowest-cost path among semantically acceptable paths.
```

---

## Stage 4E — Retry Governance / Attempt Classification

### Goal

Stage 4E classifies and governs retry attempts.

Core rule:

```text
retry attempt
≠
same intent
```

A retry loop may preserve request identity while changing action path, target state, semantic meaning, or safety boundary.

Stage 4E should distinguish retry-like situations such as:

- idempotent replay
- concurrency retry
- infrastructure retry
- semantic conflict
- semantic drift
- rebuild-required retry
- future agent intent drift

Retry governance should come after SemanticOutcome, DecisionReceipt, policy boundary, runtime decision policy, and strategy selection because a retry cannot be classified safely without knowing what semantic outcome happened before it.

---

## Stage 4 Non-goals

Stage 4 does not attempt to complete:

- full production benchmark suite
- observability platform
- production SLO system
- full RBAC or identity management
- general-purpose policy platform
- agent workflow orchestration
- projection delivery layer
- final action-safety demo
- automatic strategy optimization

These belong to later hardening stages or Stage 5.

---

## Stage 4 Completion Direction

Stage 4 is complete when the system can represent a governable runtime semantic pipeline:

```text
technical evidence
→ SemanticOutcome
→ DecisionReceipt
→ diagnostic trace when needed
→ measurement matrix / cost evidence
→ policy-linked runtime decision
→ strategy selection
→ retry governance
```

The important result is not that every production concern is fully optimized.

The important result is that runtime correctness evidence is no longer only raw technical status. It becomes structured semantic meaning that can support reviewable decisions and safe recovery.

---

## Final Principle

```text
A green runtime path does not prove semantic correctness.
A logged technical trace does not prove semantic understanding.
A successful retry does not prove intent preservation.
A measured fast path does not justify trust unless the trust source is explicit.
A policy rule does not replace runtime admission.
```


# Stage 5: Dual-Dimension Governance Demo / Action Safety

## Goal

Stage 5 demonstrates how runtime semantic governance can be used before externally meaningful actions are executed.

Stage 4 creates the semantic governance pipeline.

Stage 5 makes that pipeline visible as a reviewer-facing action-safety demo.

The key relationship is:

```text
semantic correctness
×
operational freshness / runtime trust
→
action safety
```

---

## Why This Comes After Stage 4

Action safety should not be built directly from raw technical status.

Before an action-safety gate can make trustworthy decisions, the system needs:

- SemanticOutcome
- DecisionReceipt
- runtime decision policy
- strategy selection
- retry governance
- clear separation between accepted history and derived state

Stage 5 uses those pieces to decide whether a downstream or externally visible action should proceed.

---

## Candidate Action Classes

Stage 5 may simulate actions such as:

- emitting a downstream signal
- generating a settlement report
- marking derived state as trusted
- advancing an external export
- allowing an agent-facing action to proceed

The exact action set can remain narrow.

The purpose is to demonstrate the governance loop, not to build a full production action platform.

---

## Dual-Dimension Matrix

Stage 5 should demonstrate at least four cases:

```text
semantic correct + operational fresh
semantic correct + operational stale
semantic incorrect + operational fresh
semantic incorrect + operational stale
```

This shows why technical liveness and semantic correctness are different dimensions.

A system can be operationally fresh but semantically unsafe.

A system can be semantically correct but operationally too stale for certain actions.

---

## Public Completion Direction

Stage 5 is complete when the project can demonstrate:

```text
requested action
→ semantic state check
→ SemanticOutcome
→ DecisionReceipt
→ RuntimeDecisionPolicy
→ StrategySelector
→ ActionSafetyGate
→ execute or block
```

---

## Non-goals

Stage 5 does not need to implement:

- production-grade external integrations
- full agent orchestration
- general workflow engine
- production SLO system
- full policy authoring platform

---

## Final Principle

```text
A system should not execute externally meaningful actions only because the pipeline is green.
It should execute them only when semantic correctness and operational trust are both acceptable for the action.
```


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
Runtime Semantic Governance
  4A SemanticOutcome Core
  4B DecisionReceipt / Runtime Evidence Record
  4B.1 DiagnosticTrace / ResolutionTrace Boundary
  4B.2 Measurement Matrix / Cost Evidence Inventory
  4B.5 Order Domain Policy Contract v0
  4C RuntimeDecisionPolicy
  4C.5 Layer 1 / Layer 2 Outcome Alignment
  4D StrategySelector / Fast-Path Health Policy
  4E Retry Governance / Attempt Classification

Stage 5:
Dual-Dimension Governance Demo / Action Safety
  semantic correctness × operational freshness / runtime trust
  action safety verdict

Stage 5+:
Projection Worker Freshness / Runtime Execution Evidence
  semantic correctness × operational freshness / runtime trust
  future ActionSafetyGate evidence source

```

---

## Final Summary

The intended evolution is:

```text
durable truth
→ derived truth validation
→ replay-efficiency hardening
→ durable history hardening
→ runtime semantic governance
→ decision receipts / runtime evidence
→ strategy selection and retry governance
→ action safety / dual-dimension governance demo
```

The project is not only trying to know that something failed.

It is trying to make semantic failure understandable enough that the runtime can decide whether to continue, rebuild, block, quarantine, stop, or escalate.


---



## Stage 5+ Candidate — Projection Worker Freshness / Runtime Execution Evidence

Projection worker execution evidence is deferred until after the Stage 4 governance pipeline is stable.

Stage 4 focuses on:

```text
technical correctness evidence
→ SemanticOutcome
→ DecisionReceipt
→ DiagnosticTrace / ResolutionTrace
→ Measurement Matrix
→ Policy Contract
→ RuntimeDecisionPolicy
→ StrategySelector
→ RetryGovernance
```

Projection worker mapping is not required for Stage 4A because Stage 4A PR4 maps read-side correctness validation results, not ordinary worker execution outcomes.

Projection validation and projection worker execution are different boundaries.

Projection validation answers:

```text
Does derived read-side state match accepted-history authority?
```

Projection worker execution answers:

```text
Is the projection runtime currently processing accepted events successfully and freshly?
```

These are related, but they are not the same.

```text
projection worker failure ≠ projection drift
projection lag ≠ semantic corruption
projection freshness ≠ accepted-history authority
```

Projection drift must still be established through authority comparison.

Worker freshness only tells the system whether derived state is operationally current enough for a given action.

This line belongs to the Stage 5 dual-dimension governance direction:

```text
semantic correctness
×
operational freshness / runtime trust
→
action safety
```

Projection worker freshness evidence belongs to the second dimension:

```text
operational freshness / runtime trust
```

It is not the `ActionSafetyGate` itself.

It is one possible evidence source that Stage 5 or later action-safety logic may consume.

### Candidate Future Evidence Fields

```text
last_processed_global_position
latest_accepted_global_position
projection_lag
checkpoint_advance_status
reducer_apply_status
projection_state_write_status
projection_worker_error_count
worker_last_success_at
worker_last_failure_at
worker_runtime_role
projection_worker_elapsed_ms
reducer_apply_elapsed_ms
projection_state_write_elapsed_ms
checkpoint_advance_elapsed_ms
worker_idle_ms
worker_lag_ms
```

### Candidate Future Technical Statuses

```text
PROJECTION_WORKER_APPLIED
PROJECTION_WORKER_LAGGING
REDUCER_APPLY_FAILED
PROJECTION_STATE_WRITE_FAILED
CHECKPOINT_ADVANCE_FAILED
PROJECTION_DELIVERY_STALLED
PROJECTION_WORKER_UNAVAILABLE
```

These should not be added to Stage 4A unless there is already a stable `ProjectionWorkerResult` or equivalent execution-result contract.

### Conservative Semantic Interpretation

Future projection worker statuses may map conservatively to semantic families such as:

```text
RUNTIME_UNRESOLVED
CONCURRENCY_UNCERTAIN
ESCALATION_REQUIRED
```

They should not be mapped directly to:

```text
DRIFT_DETECTED
```

A worker failure may mean the projection path is incomplete, delayed, or unresolved.

It does not by itself prove that persisted projection state semantically diverges from accepted-history authority.

### Relationship to Stage 5

Stage 5 dual-dimension governance should eventually demonstrate cases such as:

```text
semantic correct + operational fresh
semantic correct + operational stale
semantic incorrect + operational fresh
semantic incorrect + operational stale
```

Example:

```text
Replay validation confirms projection state matches authority up to checkpoint N.
Projection worker lag shows accepted history has advanced to N + 500.
Semantic correctness may hold for checkpoint N,
but operational freshness may be insufficient for an external action.
```

A future `ActionSafetyGate` may consume:

```text
SemanticOutcome
DecisionReceipt
RuntimeDecision
StrategySelector output
projection worker freshness evidence
```

to decide whether a downstream or externally meaningful action should proceed.

### Non-goals

This future line does not introduce now:

```text
ProjectionWorker execution mapping in Stage 4A PR4
projection delivery log
projection inbox
projection work item lifecycle
fanout retry control
worker governance
production observability platform
full SLO system
```

Immediate rule:

```text
Keep Stage 4 focused.
Do not expand Stage 4A PR4.
Record projection worker freshness evidence as future Stage 5+ support
for dual-dimension governance.
```

Final principle:

```text
Projection validation proves semantic consistency against authority.

Projection worker freshness proves operational currency of the derived-state pipeline.

Action safety may need both.
```


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
