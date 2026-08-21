# Roadmaps

[← Back to Docs Home](../README.md)

This directory contains roadmap documents for **Streaming System + Compass**.

Roadmaps describe implementation sequencing and system evolution. They are not meant to replace architecture notes, ADRs, boundary notes, implementation notes, or postmortems.

Use roadmap documents to understand:

* what should be built first
* what depends on what
* which features are intentionally deferred
* how the project moves from durable truth toward runtime governance
* how the project completed Stage 4B.2 measurement, closed Stage 4B.3 after an evidence-first necessity review, completed the separately owned Stage 4B.5 correctness-contract work, and closed Stage 4C Runtime Decision Authority

---

## Completed Baseline

The project has completed the Stage 4 foundation / evidence baseline through
Stage 4B.5 and Stage 4C Runtime Decision Authority:

* Stage 1 — Transactional Semantic Core
* Stage 2 — Compass Layer 1 Write-side Validation
* Stage 3 — Projection Runtime Baseline
* Stage 3.5A — Decimal / Money Hardening
* Stage 3.5B — Durable Write-Side Baseline
* Stage 3.5C — Durable Read-Side Baseline
* Stage 3.5D — Snapshot Trust Contract / Replay Efficiency
* Stage 3.5E — Durable History and Permission Hardening
* Stage 4A — SemanticOutcome Core
* Stage 4B — DecisionReceipt / Runtime Evidence Record
* Stage 4B.1 — DiagnosticTrace / ResolutionTrace
* Stage 4B.2 — Measurement Evidence
* Stage 4B.3 — Projection Trust Boundary and Continuation — closed as not currently justified
* Stage 4B.5 — Order Correctness Contract V0
* Stage 4C — Runtime Decision Authority — complete / closed

Detailed sequencing remains in [Implementation Roadmap](implementation_roadmap.md).

Completed implementation details from Stage 3.5B onward are preserved in [Implementation Notes](../implementation_notes/):

* [Stage 3.5B Implementation Notes](../implementation_notes/stage_3_5b/)
* [Stage 3.5C Implementation Notes](../implementation_notes/stage_3_5c/)
* [Stage 3.5D Implementation Notes](../implementation_notes/stage_3_5d/)
* [Stage 3.5E Implementation Notes](../implementation_notes/stage_3_5e/)
* [Stage 4A Implementation Notes](../implementation_notes/stage_4a/)
* [Stage 4B Implementation Notes](../implementation_notes/stage_4b/)
* [Stage 4B.1 Implementation Notes](../implementation_notes/stage_4b_1/)
* [Stage 4B.2 Implementation Notes](../implementation_notes/stage_4b_2/)
* [Stage 4B.3 Closeout Notes](../implementation_notes/stage_4b_3/)
* [Stage 4B.5 Implementation Notes](../implementation_notes/stage_4b_5/)
* [Stage 4C Implementation Notes and Closeout](../implementation_notes/stage_4c/)

Stage 4B PR1–PR7 completed the DecisionReceipt boundary, contract, generic and
producer mapping, strict serializer, storage-neutral persistence contracts,
and PostgreSQL persistence foundation. Automatic materialization and
reconciliation remain deferred.

Stage 4B.1 PR1–PR7 completed the producer-specific DiagnosticTrace /
ResolutionTrace boundary, PostgreSQL write-side execution characterization,
immutable write-side trace contract, traced Result + Trace integration, and
closeout. Stage 4B.2 PR1–PR8 then completed producer-specific measurement,
controlled comparison, explanatory characterization, bounded concurrency
evidence, and closeout. Stage 4B.3 PR1/PR2 then bounded and characterized
projection-trust continuation before ADR 0026 closed the stage as not currently
justified. Stage 4B.5 independently completed the Order correctness contract,
exact FullProof evidence path, runtime/write-side propagation, terminal
refinement, YAML projection, overhead characterization, and closeout. Stage 4C
then delivered the PR1 source-grounded entry boundary, PR2 generic immutable
`RuntimeDecision` plus first Layer-1 PostgreSQL / Order evaluation profile, and
the Stage 4C.5 compatibility / documentation closeout.

Completed work is recorded in the
[Stage 4B.3 implementation notes](../implementation_notes/stage_4b_3/) and
[Stage 4B.5 implementation notes](../implementation_notes/stage_4b_5/).

---

## Roadmap Index

| Document | Purpose |
|---|---|
| [Implementation Roadmap](implementation_roadmap.md) | Defines the overall implementation order from transactional semantic core to projection runtime, durable persistence, snapshot trust / replay efficiency, minimal actor / permission boundary, Stage 4 runtime semantic governance, Stage 5 action safety, and later production / agent-facing hardening. |
| [Compass Runtime Roadmap](compass_runtime_roadmap.md) | Defines the focused evolution path from the current Compass write-side baseline toward structured semantic outcomes, separate runtime decision / strategy / another-attempt authorities, action safety, and later production / agent-facing hardening. |
| [Deferred Architecture Backlog](deferred_architecture_backlog.md) | Records architecture concerns intentionally deferred beyond the current implementation scope, including aggregate snapshot revival, UUIDv7 evaluation, protocol boundaries, JSONB evidence hydration, metadata timing, append-only hardening, retry classification, cleanup failure handling, isolated derived-state runtime, and later production / governance-hardening concerns. |

---

## Recommended Reading Order

1. [Implementation Roadmap](implementation_roadmap.md)
2. [Compass Runtime Roadmap](compass_runtime_roadmap.md)
3. [Deferred Architecture Backlog](deferred_architecture_backlog.md)

The implementation roadmap gives the global project sequence.

The Compass runtime roadmap gives a more focused view of how Compass should
evolve from the current write-side baseline toward structured semantic
outcomes, separate runtime decision / strategy / another-attempt authorities,
action safety, and later hardening.

The deferred architecture backlog should be read after the main roadmaps. It does not expand the current implementation scope. It records known architecture concerns that have been intentionally postponed until the right stage.

---

## Current Roadmap Position

Completed Stage 4 foundation / evidence work:

```text
Stage 4B.2
= COMPLETE / CLOSED

Stage 4B.3
= PROJECTION TRUST BOUNDARY AND CONTINUATION / COMPLETE / CLOSED AS NOT CURRENTLY JUSTIFIED

Stage 4B.5
= ORDER CORRECTNESS CONTRACT V0 / COMPLETE / CLOSED

Stage 4C
= RUNTIME DECISION AUTHORITY / COMPLETE / CLOSED
= PR1 SOURCE-GROUNDED ENTRY BOUNDARY
= PR2 GENERIC CONTRACT + FIRST LAYER-1 PROFILE
= STAGE 4C.5 COMPATIBILITY / DOCUMENTATION CLOSEOUT
```

Stage 4B.3 produced a closeout decision, not a Projection Trust Continuation
mechanism. Stage 4B.5 contains 18 stable correctness rules, while exactly six
FullProof `TRANSITION_TRUTH` rules currently have typed runtime producer
coverage.

Stage 4B, Stage 4B.1, Stage 4B.2, and Stage 4B.5 are complete. Stage 4B.2 consumed a stable
semantic and execution-topology evidence foundation:

- raw technical status has a stable SemanticOutcome interpretation layer
- read-side / snapshot observations preserve their observation boundaries
- write-side admission outcomes preserve Layer 1 boundary semantics
- identity evidence hardening is preserved in durable receipt contracts
- producer-created flags remain `NOT_EVALUATED`
- serializer v1 and explicit caller-owned persistence are implemented
- traces remain producer-specific and separate from measurement evidence
- Stage 4B.2 completed one-execution measurement semantics, controlled
  strategy comparison, explanatory characterization, and bounded concurrency
  evidence without creating production policy

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
→ SemanticOutcome core
→ DecisionReceipt
→ DiagnosticTrace / ResolutionTrace
→ Measurement Evidence
→ Order Correctness Contract V0
→ Runtime Decision Authority — complete / closed

retained responsibility
→ Strategy Selection Authority — implementation deferred

next formal implementation direction
→ Retry / Attempt Authorization

→ action safety demo
→ later production and agent-facing hardening
```

This is implementation orientation, not a mandatory `C → D → E` runtime
pipeline. Stage 4D does not precede Stage 4E when no dynamic `HOW` selection is
required.

The system should not attempt to solve chaos, broad governance, agent isolation, or distributed complexity before the transactional semantic core, write-side safety boundaries, runtime semantics, durable persistence boundaries, and runtime governance vocabulary are coherent.

---

## Stage 4 Entrance

Stage 4 introduces Compass runtime semantic governance.

The public responsibility map is:

```text
technical evidence
→ SemanticOutcome
  ├→ DecisionReceipt as separately persisted durable governance evidence
  └→ eligible current evidence
     → completed Stage 4C current-response decision or refusal
     → caller handling

when another same-request invocation is considered:
eligible prior-invocation evidence
→ Stage 4E authorization or refusal

if another invocation is authorized:
→ Stage 4D selects HOW only if multiple eligible strategies exist
→ execution
→ fresh result
→ Stage 4C handling when applicable

DiagnosticTrace and measurement
= optional supporting evidence for concrete later consumers
```

Stage 4 should not be reduced to an error taxonomy.

It should turn runtime correctness evidence into governable semantic meaning.

Important boundaries:

```text
technical status ≠ semantic outcome
semantic outcome ≠ exact rule refinement
semantic outcome ≠ runtime decision
runtime decision ≠ execution strategy
runtime decision ≠ retry authorization
retry authorization ≠ retry execution
```

ADR 0027 defines the Stage 4C–4E authority boundary. Stage 4C is complete and
closed with a live/in-memory generic decision contract and first Layer-1
PostgreSQL / Order profile. Existing Layer-1 and Layer-2 producer families are
compatible through the producer-neutral `SemanticOutcome` structure; this does
not require identical evidence, decision policy, or caller behavior.
`DecisionReceipt` remains durable governance evidence but is not required for
the live Stage 4C path. Restart recovery remains a distinct deferred consumer.

Stage 4D responsibility remains valid, but implementation is deferred because
strategy composition is currently static, no authorized operation has multiple
dynamically eligible strategies, no reviewed selection rule exists, and a
selector would not change observable behavior. Stage 4E is the next formal
implementation direction. Preparation `LOCK_TIMEOUT` is the most portable
candidate for a narrow first same-request re-invocation profile; Stage 4E is not
implemented by the Stage 4C closeout.

Stage 4 does not yet claim to implement production benchmarking, full observability, full authorization, general policy authoring, agent workflow orchestration, or final action safety.

Those belong to later stages.

---

## Stage 4 Public Subsequence

Stage 4 proceeds through:

* Stage 4A — SemanticOutcome Core — complete
* Stage 4B — DecisionReceipt / Runtime Evidence Record — complete
* Stage 4B.1 — DiagnosticTrace / ResolutionTrace Boundary — complete
* Stage 4B.2 — Measurement Evidence — complete / closed
* Stage 4B.3 — Projection Trust Boundary and Continuation — complete / closed as not currently justified; PR1/PR2 retained as reference, PR3+ not proceeding
* Stage 4B.5 — Order Correctness Contract v0 — complete / closed / independently delivered
* Stage 4C — Runtime Decision Authority — complete / closed
* Stage 4C.5 — compatibility / documentation closeout — complete
* Stage 4D — Strategy Selection Authority inside prior authorization — responsibility retained / implementation deferred
* Stage 4E — Retry / Attempt Authorization — next formal implementation direction / not implemented

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

These should wait until the required Stage 4 semantic-governance responsibilities
and non-linear authority handoffs are implemented for concrete consumers.
