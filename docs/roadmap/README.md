# Roadmaps

[← Back to Docs Home](../README.md)

This directory contains roadmap documents for **Streaming System + Compass**.

Roadmaps describe implementation sequencing and system evolution. They are not meant to replace architecture notes or ADRs.

Use roadmap documents to understand:

- what should be built first
- what depends on what
- which features are intentionally deferred
- how the project moves from durable truth toward runtime governance

---

## Roadmap Index

| Document | Purpose |
|---|---|
| [Implementation Roadmap](implementation_roadmap.md) | Defines the overall implementation order from transactional semantic core to projection runtime, durable persistence, runtime semantic outcomes, runtime decision policy, action safety, and the Stage 5 dual-dimension governance demo. |
| [Compass Runtime Roadmap](compass_runtime_roadmap.md) | Defines the focused evolution path from the current Compass write-side baseline toward durable runtime validation, structured semantic outcomes, runtime decisions, action safety, and later dual-dimension governance. |
| [Deferred Architecture Backlog](deferred_architecture_backlog.md) | Records architecture concerns intentionally deferred from the current implementation scope, including durable vocabulary normalization, UUIDv7 evaluation, formal protocols, JSONB evidence hydration, metadata timing, transaction ownership, persistence errors, append-only hardening, and integration-test strategy. |

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

The project has already completed:

- Stage 1 — Transactional Semantic Core
- Stage 2 — Compass Layer 1 Write-side Validation
- Stage 3 — Projection Runtime Baseline
- Stage 3.5A — Decimal / Money Hardening
- Stage 3.5B PR1 — Schema + Docker PostgreSQL + Migration Skeleton
- Stage 3.5B PR2 — PostgresEventStore baseline

The current next work is:

```text
Stage 3.5B PR3 — PostgresIdempotencyStore
```

The remaining Stage 3.5B path is:

```text
PR3 PostgresIdempotencyStore
→ PR4 Transactional Write-side Boundary
```

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
→ runtime semantic validation
→ structured semantic outcome
→ runtime decision policy
→ action safety gate
→ dual-dimension governance demo
```

The system should not attempt to solve chaos, broad governance, or distributed complexity before the transactional semantic core, write-side safety boundaries, runtime semantics, and durable persistence boundaries are coherent.

---

## Stage 3.5B Reminder

Stage 3.5B is split into four small checkpoints:

1. **PR1 — Schema + Docker + Migration**  
   Establishes `order_events`, `idempotency_records`, local PostgreSQL setup, and durable schema contract.

2. **PR2 — PostgresEventStore**  
   Makes accepted event history durable.

3. **PR3 — PostgresIdempotencyStore**  
   Makes request-level idempotency durable.

4. **PR4 — Transactional Write-side Boundary**  
   Coordinates event append and idempotency record write in one database transaction.

---

## Deferred Architecture Backlog Reminder

Some architecture issues are known but intentionally deferred to avoid scope creep.

Examples include:

- durable `EventType` vocabulary normalization
- UUIDv7 / time-ordered UUID evaluation
- formal `EventStoreProtocol`
- stored event record / JSONB evidence hydration
- registry-stage timing in `metadata_json`
- transaction lifecycle ownership
- custom persistence exceptions
- append-only database hardening
- integration-test structure and CI strategy

These are tracked in:

- [Deferred Architecture Backlog](deferred_architecture_backlog.md)

They should be converted into GitHub Issues only when their suggested timing becomes active.

---

## Stage 4 Reminder

Stage 4 is not only error classification.

It evolves Compass into:

```text
Layer 2 validation
→ SemanticOutcome
→ RuntimeDecisionPolicy
→ RuntimeDecision
→ ActionSafetyGate
```

This reflects the core principle:

> Error semantics should not only be observed.  
> They should help the runtime decide whether to continue, rebuild, block, quarantine, stop, or escalate.

---

## Stage 5 Reminder

Stage 5 packages the final governance demo around:

```text
semantic correctness × operational freshness → action safety
```

The key matrix is:

|  | Operational Fresh | Operational Stale |
|---|---|---|
| Semantic Correct | Safe to act | Semantically correct but stale |
| Semantic Incorrect | Operationally healthy but semantically unsafe | Unsafe / stop / escalate |

This final demo should show that:

- operational freshness is not semantic correctness
- semantic correctness is not operational freshness
- action safety requires both dimensions
