# Roadmaps

[← Back to Docs Home](../README.md)

This directory contains roadmap documents for **Streaming System + Compass**.

Roadmaps describe implementation sequencing and system evolution. They are not meant to replace architecture notes, ADRs, boundary notes, implementation notes, or postmortems.

Use roadmap documents to understand:

* what should be built first
* what depends on what
* which features are intentionally deferred
* how the project moves from durable truth toward runtime governance
* how the project has completed Stage 3.5E and is entering Stage 4 runtime semantic governance

---

## Completed Baseline

The project has completed the baseline sequence up to Stage 3.5E:

* Stage 1 — Transactional Semantic Core
* Stage 2 — Compass Layer 1 Write-side Validation
* Stage 3 — Projection Runtime Baseline
* Stage 3.5A — Decimal / Money Hardening
* Stage 3.5B — Durable Write-Side Baseline
* Stage 3.5C — Durable Read-Side Baseline
* Stage 3.5D — Snapshot Trust Contract / Replay Efficiency
* Stage 3.5E — Durable History and Permission Hardening

Detailed sequencing remains in [Implementation Roadmap](implementation_roadmap.md).

Completed implementation details from Stage 3.5B onward are preserved in [Implementation Notes](../implementation_notes/):

* [Stage 3.5B Implementation Notes](../implementation_notes/stage_3_5b/)
* [Stage 3.5C Implementation Notes](../implementation_notes/stage_3_5c/)
* [Stage 3.5D Implementation Notes](../implementation_notes/stage_3_5d/)
* [Stage 3.5E Implementation Notes](../implementation_notes/stage_3_5e/)

Stage 3.5E has completed the minimal durable-history role / permission boundary and actor-metadata boundary needed before Stage 4.

---

## Roadmap Index

| Document | Purpose |
|---|---|
| [Implementation Roadmap](implementation_roadmap.md) | Defines the overall implementation order from transactional semantic core to projection runtime, durable persistence, snapshot trust / replay efficiency, minimal actor / permission boundary, Stage 4 runtime semantic governance, Stage 5 action safety, and later production / agent-facing hardening. |
| [Compass Runtime Roadmap](compass_runtime_roadmap.md) | Defines the focused evolution path from the current Compass write-side baseline toward runtime semantic governance, structured semantic outcomes, runtime decisions, strategy selection, retry governance, action safety, and later production / agent-facing hardening. |
| [Deferred Architecture Backlog](deferred_architecture_backlog.md) | Records architecture concerns intentionally deferred beyond the current implementation scope, including aggregate snapshot revival, UUIDv7 evaluation, protocol boundaries, JSONB evidence hydration, metadata timing, append-only hardening, retry classification, cleanup failure handling, isolated derived-state runtime, and later production / governance-hardening concerns. |

---

## Recommended Reading Order

1. [Implementation Roadmap](implementation_roadmap.md)
2. [Compass Runtime Roadmap](compass_runtime_roadmap.md)
3. [Deferred Architecture Backlog](deferred_architecture_backlog.md)

The implementation roadmap gives the global project sequence.

The Compass runtime roadmap gives a more focused view of how Compass should evolve from the current write-side baseline toward runtime semantic governance, structured semantic outcomes, runtime decisions, strategy selection, retry governance, action safety, and later hardening.

The deferred architecture backlog should be read after the main roadmaps. It does not expand the current implementation scope. It records known architecture concerns that have been intentionally postponed until the right stage.

---

## Current Roadmap Position

Current implementation focus:

```text
Stage 4 — Runtime Semantic Governance
```

Stage 3.5E is complete at the baseline level. It established database responsibility roles, permission-boundary tests, SET ROLE probing scope, minimal actor metadata semantics, and explicit deferrals for full RBAC and production identity wiring.

Stage 4 now starts from a cleaner foundation:

- durable authority is protected
- derived state remains operationally mutable under controlled runtime roles
- snapshots remain derived and subordinate to accepted history
- minimal actor metadata is separated from governance decision evidence

---

## Roadmap Principle

The project should evolve from semantic clarity toward runtime complexity:

```text
semantic truth
→ transactional execution
→ concurrency-safe admission
→ event truth validation
→ projection runtime
→ exact money hardening before durable persistence
→ durable write-side baseline
→ durable read-side baseline
→ snapshot trust qualification / replay efficiency
→ minimal actor / permission boundary
→ runtime semantic governance
→ action safety demo
→ later production and agent-facing hardening
```

The system should not attempt to solve chaos, broad governance, agent isolation, or distributed complexity before the transactional semantic core, write-side safety boundaries, runtime semantics, durable persistence boundaries, and runtime governance vocabulary are coherent.

---

## Stage 4 Entrance

Stage 4 introduces Compass runtime semantic governance.

The public sequence is:

```text
technical evidence
→ SemanticOutcome
→ DecisionReceipt
→ measurement evidence
→ DiagnosticTrace when needed
→ policy-linked RuntimeDecision
→ StrategySelector
→ Retry Governance
```

Stage 4 should not be reduced to an error taxonomy.

It should turn runtime correctness evidence into governable semantic meaning.

Important boundaries:

```text
technical status ≠ semantic outcome
semantic outcome ≠ runtime decision
runtime decision ≠ execution strategy
retry attempt ≠ same intent
```

Stage 4 does not yet claim to implement production benchmarking, full observability, full authorization, general policy authoring, agent workflow orchestration, or final action safety.

Those belong to later stages.

---

## Stage 4 Public Subsequence

Stage 4 is expected to proceed through:

* Stage 4A — SemanticOutcome Core
* Stage 4B — DecisionReceipt / Runtime Evidence Record
* Stage 4B.1 — DiagnosticTrace / ResolutionTrace Boundary
* Stage 4B.2 — Measurement Matrix / Cost Evidence Inventory
* Stage 4B.5 — Order Domain Policy Contract v0
* Stage 4C — RuntimeDecisionPolicy
* Stage 4C.5 — Layer 1 / Layer 2 Outcome Alignment
* Stage 4D — StrategySelector / Fast-Path Health Policy
* Stage 4E — Retry Governance / Attempt Classification

The detailed implementation of each step belongs in stage-specific implementation notes and PRs, not in this roadmap index.

---

## Stage 5 Reminder

Stage 5 should demonstrate dual-dimension governance / action safety:

```text
semantic correctness
×
operational freshness / runtime trust
→
action safety
```

The key cases are:

```text
semantic correct + operational fresh
semantic correct + operational stale
semantic incorrect + operational fresh
semantic incorrect + operational stale
```

This is where Compass can show that a system may be technically live but semantically unsafe, or semantically correct but operationally too stale for certain actions.

---

## Later Work Reminder

Later work may evaluate production and agent-facing hardening such as:

* benchmark suite
* evidence retention policy
* cost-aware semantic governance
* projection delivery layer if needed
* isolated derived-state runtime
* oblivious agent runtime evaluation
* broader governance hardening

These should wait until the project has a working Stage 4 semantic governance pipeline.
