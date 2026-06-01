# Roadmaps

[← Back to Docs Home](../README.md)

This directory contains roadmap documents for **Streaming System + Compass**.

Roadmaps describe implementation sequencing and system evolution. They are not meant to replace architecture notes, ADRs, or postmortems.

Use roadmap documents to understand:

- what should be built first
- what depends on what
- which features are intentionally deferred
- how the project moves from durable truth toward runtime governance
- which Stage 3.5B and Stage 3.5C PR0 concerns are complete and which later concerns are intentionally deferred
- why Stage 3.5C is the next implementation focus after the durable write-side baseline
- why Stage 3.5D is kept as a later persistence optimization / replay-efficiency stage

---

## Roadmap Index

| Document | Purpose |
|---|---|
| [Implementation Roadmap](implementation_roadmap.md) | Defines the overall implementation order from transactional semantic core to projection runtime, durable persistence, runtime semantic outcomes, runtime decision policy, action safety, and the Stage 5 dual-dimension governance demo. |
| [Compass Runtime Roadmap](compass_runtime_roadmap.md) | Defines the focused evolution path from the current Compass write-side baseline toward durable runtime validation, structured semantic outcomes, runtime decisions, action safety, and later dual-dimension governance. |
| [Deferred Architecture Backlog](deferred_architecture_backlog.md) | Records architecture concerns intentionally deferred beyond the current implementation scope, including UUIDv7 evaluation, protocol boundaries, JSONB evidence hydration, metadata timing, snapshot / replay-efficiency work, append-only hardening, cleanup failure handling, and later production-hardening concerns. |

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
- Stage 3.5B PR5 — PostgreSQL Concurrency Admission Boundary
- Stage 3.5B PR6 — Validation Placement Strategy Boundary / Stage 4 Prelude
- Stage 3.5C PR0 — Durable Order Event Vocabulary Hardening

Stage 3.5B now forms a durable write-side baseline:

```text
durable accepted history
+ durable idempotency memory
+ transactional write-side execution
+ two-phase concurrency admission
+ validation placement strategy
```

The current major focus is:

```text
Stage 3.5C — Durable Read-Side Baseline
```

Stage 3.5D is intentionally reserved for persistence optimization, snapshots, and replay efficiency after the durable read-side baseline exists.

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
→ persistence optimization / replay efficiency
→ runtime semantic validation
→ structured semantic outcome
→ runtime decision policy
→ action safety gate
→ dual-dimension governance demo
```

The system should not attempt to solve chaos, broad governance, or distributed complexity before the transactional semantic core, write-side safety boundaries, runtime semantics, and durable persistence boundaries are coherent.

---

## Stage 3.5B Reminder

Stage 3.5B completed six durable write-side checkpoints:

1. **PR1 — Schema + Docker + Migration**  
   Established `order_events`, `idempotency_records`, local PostgreSQL setup, and the durable schema contract.

2. **PR2 — PostgresEventStore**  
   Made accepted event history durable.

3. **PR3 — PostgresIdempotencyStore**  
   Made request-level idempotency durable.

4. **PR4 — Transactional Semantic Write-side Boundary**  
   Coordinated event append and idempotency record write in one database transaction, while preserving Compass Layer 1 validation before accepted-history mutation.

5. **PR5 — PostgreSQL Concurrency Admission Boundary**  
   Reintroduced durable optimistic / pessimistic admission so concurrent writers can be admitted or rejected through a stable application boundary rather than raw database errors. PR5 also recorded the two-phase admission decision in ADR 0012 and treats `autocommit=True` as incompatible with transaction-scoped pessimistic admission.

6. **PR6 — Validation Placement Strategy Boundary / Stage 4 Prelude**  
   Separated `ValidationMode` from `ValidationPlacement`, preserved `IN_TRANSACTION` as the default write-side behavior, and added a minimal `PRE_TRANSACTION` orchestration path guarded by append-time admission. PR6 also recorded the pre-transaction read cleanup boundary required to keep the physical connection state aligned with the placement label.


---

## Stage 3.5C PR0 Reminder

Stage 3.5C PR0 completed durable order-event vocabulary hardening before durable read-side persistence begins.

It finalized selected write-side schema vocabulary so later projection and replay code can depend on stable stored event records:

```text
event_type: CREATED / PAID
proof_prev_status: INIT / CREATED / PAID
unique constraint: uq_order_events_order_id_sequence
```

`CommandType` remains lowercase because it represents request/action identity for idempotency records, not accepted event identity.
---

## Stage 3.5C Reminder

Stage 3.5C should move the read-side baseline from in-memory stores toward durable persistence-backed semantics.

The main goal is to add durable projection state and checkpoint state without redefining the source of truth.

```text
event log / order_events = accepted history truth
projection state = derived runtime state
checkpoint = operational progress metadata
```

Stage 3.5C should prepare the system for later Compass Layer 2 validation by making derived state durable enough to compare against replayed accepted history.


---

## Stage 3.5D Reminder

Stage 3.5D should not be mixed into the Stage 3.5C durable read-side baseline.

It is reserved for persistence optimization and replay efficiency after durable write-side and durable read-side baselines are both coherent.

Possible Stage 3.5D work includes:

- aggregate snapshots
- snapshot metadata and lineage
- snapshot validity rules
- projection rebuild optimization
- replay cost measurement

The source-of-truth rule remains unchanged:

```text
accepted history = source of truth
snapshot = derived state compression
projection state = derived runtime view
```
---

## Deferred Architecture Backlog Reminder

Some architecture issues are known but intentionally deferred to avoid scope creep.

Examples include:

- UUIDv7 / time-ordered UUID evaluation
- formal `EventStoreProtocol`
- stored event record / JSONB evidence hydration
- registry-stage timing in `metadata_json`
- payload / proof / metadata JSON shape
- append-only database hardening
- snapshot and replay-efficiency optimization
- pre-transaction cleanup failure handling after Stage 4 error model or connection-pool hardening exists
- integration-test follow-ups as the durable read-side test matrix expands

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

Stage 4 should not be used as a dumping ground for durable persistence cleanup or replay optimization.

Completed schema-hardening work, such as Stage 3.5C PR0 durable event vocabulary normalization and `proof_prev_status` constraint enforcement, should remain recorded in implementation notes, PR history, and roadmaps rather than in the active deferred backlog.

Replay-efficiency work belongs to Stage 3.5D, not Stage 4 Error Model work.

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
