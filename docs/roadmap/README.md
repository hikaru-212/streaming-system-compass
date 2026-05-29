# Roadmaps

[← Back to Docs Home](../README.md)

This directory contains roadmap documents for **Streaming System + Compass**.

Roadmaps describe implementation sequencing and system evolution. They are not meant to replace architecture notes, ADRs, or postmortems.

Use roadmap documents to understand:

- what should be built first
- what depends on what
- which features are intentionally deferred
- how the project moves from durable truth toward runtime governance
- which Stage 3.5B concerns are now complete, planned, or intentionally deferred

---

## Roadmap Index

| Document | Purpose |
|---|---|
| [Implementation Roadmap](implementation_roadmap.md) | Defines the overall implementation order from transactional semantic core to projection runtime, durable persistence, runtime semantic outcomes, runtime decision policy, action safety, and the Stage 5 dual-dimension governance demo. |
| [Compass Runtime Roadmap](compass_runtime_roadmap.md) | Defines the focused evolution path from the current Compass write-side baseline toward durable runtime validation, structured semantic outcomes, runtime decisions, action safety, and later dual-dimension governance. |
| [Deferred Architecture Backlog](deferred_architecture_backlog.md) | Records architecture concerns intentionally deferred from the current implementation scope, including durable vocabulary hardening, UUIDv7 evaluation, protocol boundaries, JSONB evidence hydration, metadata timing, persistence/admission errors, append-only hardening, validation placement strategy, and test boundary follow-ups. |

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
- Stage 3.5B PR3 — PostgresIdempotencyStore baseline
- Stage 3.5B PR4 — Transactional Semantic Write-side Boundary

The current next work is:

```text
Stage 3.5B PR5 — PostgreSQL Concurrency Admission Boundary
```

PR5 completes the remaining durable write-side correctness boundary by separating:

```text
transaction atomicity
≠
concurrency admission
```

After PR5, the project may optionally add a PR6 / Stage 4 prelude for validation placement strategy:

```text
IN_TRANSACTION Compass validation
vs
PRE_TRANSACTION Compass validation + OCC
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

Stage 3.5B is now split into five durable write-side checkpoints:

1. **PR1 — Schema + Docker + Migration**  
   Establishes `order_events`, `idempotency_records`, local PostgreSQL setup, and durable schema contract.

2. **PR2 — PostgresEventStore**  
   Makes accepted event history durable.

3. **PR3 — PostgresIdempotencyStore**  
   Makes request-level idempotency durable.

4. **PR4 — Transactional Semantic Write-side Boundary**  
   Coordinates event append and idempotency record write in one database transaction, while preserving Compass Layer 1 validation before accepted-history mutation.

5. **PR5 — PostgreSQL Concurrency Admission Boundary**  
   Reintroduces durable optimistic / pessimistic admission so concurrent writers can be admitted or rejected through a stable application boundary rather than raw database errors.

A later PR6 or Stage 4 prelude may introduce validation placement strategy:

```text
ValidationMode
≠
ValidationPlacement
```

This is not required to complete the durable write-side baseline, but it is important for future latency / safety trade-off experiments.

---

## Deferred Architecture Backlog Reminder

Some architecture issues are known but intentionally deferred to avoid scope creep.

Examples include:

- durable `EventType` vocabulary normalization
- durable `OrderStatus` constraint hardening
- UUIDv7 / time-ordered UUID evaluation
- formal `EventStoreProtocol`
- stored event record / JSONB evidence hydration
- registry-stage timing in `metadata_json`
- storage/admission error mapping
- append-only database hardening
- validation placement strategy
- integration-test follow-ups after the PR4 isolation baseline

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

Stage 4 should not be used as a dumping ground for every remaining durable schema cleanup.

For example:

```text
EventType / OrderStatus durable vocabulary hardening
```

belongs to durable schema hardening, not Stage 4 Error Model work.

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
