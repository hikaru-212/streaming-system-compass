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
- [Stage 3.5E Implementation Notes](../implementation_notes/stage_3_5e/)

This document focuses on a narrower question:

> How does Compass evolve from write-side semantic validation into runtime semantic validation, structured outcomes, runtime decisions, action safety, and dual-dimension governance?

In other words, this roadmap is about the semantic control layer, not the full project build plan.

---

## Scope Boundary

The implementation roadmap answers:

> What should be built, and in what order?

This Compass runtime roadmap answers:

> How does Compass become more capable as a runtime semantic control layer?

The two roadmaps overlap around Stage 3.5B, Stage 3.5C, Stage 3.5D, and Stage 4 because Compass depends on durable write-side, durable read-side, snapshot trust, and completed actor / permission boundaries before stronger runtime validation grows.

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
- Stage 3.5E provides the completed minimal actor / permission boundary before broader runtime governance.
- Compass Phase 4 maps to Stage 4 runtime semantic governance.
- Compass Phase 5 maps to the Stage 5 action safety / dual-dimension governance demo.
- Compass Phase 6 maps to later production and agent-facing hardening.

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

The project has now completed the main durability and replay-efficiency substrate needed before Stage 4:

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

Stage 3.5E then added the durable permission and minimal actor boundary:

```text
accepted history permission hardening
+ derived-state controlled mutation
+ minimal producer metadata
→ cleaner Stage 4 receipt / governance foundation
```

This does not make Compass Layer 2 active yet.

It provides durable correctness evidence, replay-efficiency primitives, and actor / permission boundaries that Layer 2 can later classify and govern.

---

## Current Limitation

Compass does not yet make runtime governance decisions for derived state.

The system can now preserve durable accepted history, persist derived read-side state, compare persisted projection state against accepted-history replay, validate snapshot-assisted replay, and resolve read-side state from an externally qualified snapshot id.

However, Compass has not yet become a full state-level governance layer.

That means the next question is no longer only whether drift or snapshot mismatch can be detected. The next question is:

> If derived-state drift, snapshot mismatch, or runtime trust failure is detected, what does it mean, and what should the runtime do?

That interpretation and decision boundary belongs to Stage 4 runtime semantic governance and later Stage 5 action safety work.

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
- [Stage 3.5E Implementation Notes](../implementation_notes/stage_3_5e/)

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
- [Stage 3.5E Implementation Notes](../implementation_notes/stage_3_5e/)

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

# Phase 4 — Runtime Semantic Governance

## Goal

Phase 4 describes how Compass evolves from write-side semantic validation and durable replay evidence into a runtime semantic governance layer.

At this point, Compass should begin turning technical validation results into structured semantic meaning and reviewable runtime decisions.

The high-level flow is:

```text
technical evidence
→ SemanticOutcome
→ DecisionReceipt
→ DiagnosticTrace when needed
→ Measurement Matrix / cost evidence
→ policy-linked RuntimeDecision
→ StrategySelector
→ Retry Governance
```

---

## Core Boundary

Compass Phase 4 preserves four distinctions:

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

This prevents raw validator results, exception strings, retry counters, or fast-path health signals from being treated as complete governance decisions.

---

## Capability Path

Phase 4 roughly maps to Stage 4 in the implementation roadmap.

The capability path is:

1. define runtime semantic outcome vocabulary
2. record decision evidence at receipt level
3. preserve detailed failure diagnostics separately
4. make cost / timing evidence observable
5. connect outcomes to narrow policy references
6. convert semantic outcomes into runtime decisions
7. align Layer 1 and Layer 2 outcome families
8. select execution strategies among semantically acceptable paths
9. classify retry attempts without assuming same intent

---

## Runtime Meaning

This phase is where Compass starts to answer:

> If derived state is stale, untrusted, drifting, or unresolved, what does that mean for the runtime?

The answer should not be only a log line.

It should become structured semantic evidence that can support recovery, fallback, quarantine, rebuild, retry classification, and later action safety.

---

## Public Non-goals

Phase 4 does not claim to complete:

- full production benchmarking
- full observability platform
- full authorization system
- general policy platform
- agent workflow orchestration
- projection delivery layer
- final action safety demo

Those concerns belong to later hardening or Stage 5.

---

# Phase 5 — Action Safety / Dual-Dimension Governance Demo

## Goal

Phase 5 demonstrates how Compass governance can guard externally meaningful actions.

The key relationship is:

```text
semantic correctness
×
operational freshness / runtime trust
→
action safety
```

Stage 4 creates semantic meaning, evidence, decisions, strategies, and retry governance.

Stage 5 uses those outputs to decide whether an action should execute.

---

## Runtime Meaning

A green technical path is not enough.

An action may still be unsafe if:

- derived state is stale
- projection drift has not been resolved
- snapshot trust is unavailable
- the retry changed semantic intent
- the policy boundary requires escalation
- operational freshness is insufficient for the requested action

---

## Demonstration Direction

The demo should show the matrix:

```text
semantic correct + operational fresh
semantic correct + operational stale
semantic incorrect + operational fresh
semantic incorrect + operational stale
```

This makes visible why technical liveness and semantic correctness are different dimensions.

---

# Phase 6 — Later Governance and Production Hardening

## Goal

Later phases can harden the runtime around production concerns once the semantic governance model is stable.

Possible directions include:

- benchmark suite
- cost-aware admission strategy
- evidence retention policy
- production observability integration
- projection delivery layer if needed
- isolated derived-state runtime
- agent-facing governance boundaries
- broader domain expansion

---

## Final Summary

Compass evolves through the following capability path:

| Phase | Capability |
|---|---|
| 1 | Write-side transition-truth validation |
| 2 | Durable write-side accepted-history protection |
| 3 | Durable read-side and snapshot trust substrate |
| 4 | Runtime semantic governance |
| 5 | Action safety / dual-dimension governance demo |
| 6 | Later production and agent-facing hardening |

The core principle remains:

```text
accepted history is authority
derived state is useful but subordinate
technical success is not semantic correctness
runtime governance should preserve meaning before optimizing execution
```
