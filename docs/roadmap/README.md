# Roadmaps

[← Back to Docs Home](../README.md)

This directory contains roadmap documents for **Streaming System + Compass**.

Roadmaps describe implementation sequencing and system evolution. They are not meant to replace architecture notes, ADRs, boundary notes, implementation notes, or postmortems.

Use roadmap documents to understand:

* what should be built first
* what depends on what
* which features are intentionally deferred
* how the project moves from durable truth toward runtime governance
* how the project has completed the pre-Stage 3.5E documentation alignment and is entering Stage 3.5E

---

## Completed Baseline

The project has completed the baseline sequence up to Stage 3.5D:

* Stage 1 — Transactional Semantic Core
* Stage 2 — Compass Layer 1 Write-side Validation
* Stage 3 — Projection Runtime Baseline
* Stage 3.5A — Decimal / Money Hardening
* Stage 3.5B — Durable Write-Side Baseline
* Stage 3.5C — Durable Read-Side Baseline
* Stage 3.5D — Snapshot Trust Contract / Replay Efficiency

Detailed sequencing remains in [Implementation Roadmap](implementation_roadmap.md).

Completed implementation details from Stage 3.5B onward are preserved in [Implementation Notes](../implementation_notes/):

* [Stage 3.5B Implementation Notes](../implementation_notes/stage_3_5b/)
* [Stage 3.5C Implementation Notes](../implementation_notes/stage_3_5c/)
* [Stage 3.5D Implementation Notes](../implementation_notes/stage_3_5d/)

The pre-Stage 3.5E documentation alignment pass has also been completed at the roadmap / ADR / implementation-note level.

---

## Roadmap Index

| Document | Purpose |
|---|---|
| [Implementation Roadmap](implementation_roadmap.md) | Defines the overall implementation order from transactional semantic core to projection runtime, durable persistence, snapshot trust / replay efficiency, minimal actor / permission boundary, runtime semantic outcomes, runtime decision policy, action safety, Stage 5 dual-dimension governance, and later isolated derived-state runtime evaluation. |
| [Compass Runtime Roadmap](compass_runtime_roadmap.md) | Defines the focused evolution path from the current Compass write-side baseline toward durable runtime validation, snapshot-aware state validation, structured semantic outcomes, retry reason classification, runtime decisions, action safety, dual-dimension governance, and later agent-facing governance hardening. |
| [Deferred Architecture Backlog](deferred_architecture_backlog.md) | Records architecture concerns intentionally deferred beyond the current implementation scope, including aggregate snapshot revival, UUIDv7 evaluation, protocol boundaries, JSONB evidence hydration, metadata timing, append-only hardening, retry classification, cleanup failure handling, isolated derived-state runtime, and later production / governance-hardening concerns. |

---

## Recommended Reading Order

1. [Implementation Roadmap](implementation_roadmap.md)
2. [Compass Runtime Roadmap](compass_runtime_roadmap.md)
3. [Deferred Architecture Backlog](deferred_architecture_backlog.md)

The implementation roadmap gives the global project sequence.

The Compass runtime roadmap gives a more focused view of how Compass should evolve from the current write-side baseline toward durable persistence, runtime semantic validation, structured semantic outcomes, runtime decision policy, action safety, and dual-dimension governance.

The deferred architecture backlog should be read after the main roadmaps. It does not expand the current implementation scope. It records known architecture concerns that have been intentionally postponed until the right stage.

---

## Current Roadmap Position

Current implementation focus:

```text
Stage 3.5E — Minimal Actor / Permission Boundary
```

The pre-Stage 3.5E cleanup pass has completed at the roadmap / ADR / implementation-note level.

Stage 3.5E should stay minimal.

It should clarify actor / permission semantics needed before Stage 4 receipts and runtime governance, without turning the project into full RBAC, login/session handling, JWT infrastructure, multi-tenant auth, or a complete access-control platform.

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
→ runtime semantic validation
→ structured semantic outcome
→ retry reason classification and intent consistency
→ runtime decision policy
→ action safety gate
→ dual-dimension governance demo
→ later isolated derived-state runtime and adversarial hardening
```

The system should not attempt to solve chaos, broad governance, agent isolation, or distributed complexity before the transactional semantic core, write-side safety boundaries, runtime semantics, and durable persistence boundaries are coherent.

---

## Stage 3.5E Reminder

Stage 3.5E is reserved for minimal actor / permission boundary hardening after durable write-side, durable read-side, and replay-efficiency boundaries are clear.

The first hardening target is accepted history:

```text
order_events = accepted history / source of truth
```

Stage 3.5E should evaluate:

* system / admin / operator / test actor semantics
* privileged operation boundaries
* `created_by` / future `validated_by` / `decision_by` metadata alignment
* migration owner vs runtime role separation
* write-side runtime permissions
* projection worker permissions
* read-only observer permissions
* whether runtime roles should be prevented from casual `UPDATE` / `DELETE` on accepted-history tables

Stage 3.5E should not implement:

* full RBAC
* login / session management
* JWT auth
* multi-tenant auth
* complete access-control infrastructure
* Compass Layer 2 validation
* `SemanticOutcome`
* runtime decision policy
* action safety gate

---

## Deferred Architecture Backlog Reminder

The deferred backlog should contain only future architecture concerns whose timing depends on stage readiness, production need, runtime evidence, or governance maturity.

It should not collect completed PR details.

Examples of valid deferred concerns include:

* aggregate snapshot revival
* worker leasing / checkpoint row locking
* UUIDv7 evaluation
* durable JSONB evidence hydration
* registry-stage timing evidence
* append-only database hardening
* retry reason classification
* isolated derived-state runtime

---

## Stage 4 Reminder

Stage 4 should introduce Compass Layer 2 and structured runtime governance.

The main direction is:

```text
accepted history
→ derived state
→ validation result
→ structured SemanticOutcome
→ runtime decision
→ action safety gate
```

Stage 4 should not be reduced to an error taxonomy.

It should create machine-readable semantic outcomes that can support runtime decisions, retry classification, recovery, receipts, and future agent-facing safety boundaries.

### Retry Reason Classification

Stage 4 should distinguish retry-like situations such as:

* idempotent replay
* idempotency conflict
* stale-write retry
* transient infrastructure retry
* projection-drift rebuild
* snapshot-trust fallback
* future agent intent drift

Retry classification belongs in `SemanticOutcome` / request-attempt evidence design, not directly in `idempotency_records`.

---

## Stage 5 Reminder

Stage 5 should demonstrate dual-dimension governance:

```text
semantic correctness
×
operational freshness
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

## Stage 5+ Reminder

Later work may evaluate isolated derived-state runtime / oblivious agent runtime.

This should wait until the project has:

* Layer 2 validation
* structured semantic outcomes
* runtime decision policy
* action safety gate
* dual-dimension governance demo

This should remain future governance hardening, not a Stage 3.5E requirement.
