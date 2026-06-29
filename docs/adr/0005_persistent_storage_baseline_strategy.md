# ADR 0005: Persistent Storage Baseline Strategy

[← Back to ADR Index](README.md)

## Status

Accepted

---

## Implementation Status

Accepted and implemented at baseline level across Stage 3.5B and Stage 3.5C.

Implemented by:

- Stage 3.5B — Durable Write-Side Baseline
- Stage 3.5C — Durable Read-Side Baseline

Related implementation notes:

- [Stage 3.5B Implementation Notes](../implementation_notes/stage_3_5b/)
- [Stage 3.5C Implementation Notes](../implementation_notes/stage_3_5c/)

Baseline implementation evidence:

- durable accepted history through PostgreSQL-backed write-side storage
- durable idempotency memory through PostgreSQL-backed idempotency records
- transactional coordination between accepted event append and idempotency result recording
- PostgreSQL-backed concurrency admission
- durable projection state
- durable checkpoint progress
- global-position accepted-history consumption
- PostgreSQL-backed projection worker baseline
- durable replay / rebuild validation against accepted history

This ADR is accepted because the project followed the chosen causal order:

```text
durable accepted history
→ durable idempotency memory
→ durable projection state
→ durable checkpoint progress
→ durable replay / rebuild validation
```

Advanced runtime concerns remain deferred until the durable baseline is semantically stable.

---

## Context

The project currently has:

- a transactional write-side semantic baseline
- accepted-history replay baseline
- idempotency replay / conflict distinction
- Compass Layer 1 transition-truth validation
- a Stage 3 projection runtime baseline in deterministic in-memory form

What it does not yet have is durable persistence-backed runtime behavior.

At this point, there are multiple possible directions:

1. move directly into advanced runtime concerns such as buffering, watermarking, DLQ, or multi-worker coordination
2. strengthen the current system by introducing durable persistence first
3. optimize around lighter-weight local persistence tools before adopting a stronger transaction-oriented store
4. introduce durable persistence for read-side projection first, before durable write-side accepted history

The repository needs an explicit decision about which path to take.

---

## Decision

The next stage after the Stage 3 in-memory baseline will be:

## Stage 3.5 — Persistent Storage Baseline

This stage will be implemented with the following strategy:

1. use PostgreSQL as the primary durable storage baseline
2. strengthen write-side persistence first
   - event store
   - idempotency store
3. strengthen read-side persistence second
   - projection store
   - checkpoint store
4. validate replay / rebuild equivalence after durable boundaries exist
5. defer advanced runtime concerns such as DLQ, buffering, watermarking, and multi-worker coordination until durable baseline semantics are clear

---

## Rationale

### Why persistent storage comes next

The current system already has a meaningful in-memory baseline.
The next problem is therefore not "how to add more runtime features," but "how to preserve current correctness across process lifetime and restart."

### Why write-side comes first

Accepted history remains the source of truth.
Projection is derived from accepted history.

Therefore the durable world should follow the same causal order:

- durable accepted history first
- durable projection state second

### Why PostgreSQL

This project is not primarily optimizing for cache-like speed or transient coordination.
It is optimizing for:

- accepted-history durability
- idempotency durability
- replayability
- projection-state persistence
- checkpoint durability
- transactional consistency across related persistence operations

PostgreSQL is a strong fit for these concerns.

### Why not Redis as the primary baseline

Redis may later be useful for auxiliary concerns, but it is not the natural primary baseline for durable accepted history and durable replay semantics.

### Why not SQLite as the primary baseline

SQLite can be useful for small experiments, but PostgreSQL provides a stronger baseline for a production-inspired project focused on correctness under failure and explicit transaction semantics.

### Why advanced runtime concerns are deferred

DLQ, buffering, watermarking, and multi-worker coordination are meaningful only after the durable baseline is strong enough to make restart, replay, and persistent state trustworthy.

---

## Consequences

### Positive Consequences

- the project keeps its causal dependency order intact
- durability is introduced without prematurely adding advanced runtime complexity
- write-side and read-side persistence boundaries remain conceptually separate
- replay / rebuild equivalence can later be validated against durable state
- the project gains a stronger production-inspired signal

### Negative Consequences

- the persistence stage becomes larger than a simple local database demo
- write-side and read-side semantics must both be reconsidered under durable execution
- transaction-boundary questions become more explicit and more demanding
- the project still postpones some visually attractive streaming-runtime features

### Neutral but Important Consequence

Durable persistence must now be treated as part of semantic correctness, not as an implementation detail that can be added casually later.

---

## Alternatives Considered

### Alternative A: Move directly into advanced projection-runtime features

Rejected because the system would still lack a strong answer to durable restart, replay, and checkpoint trust.

### Alternative B: Persist projection first, then accepted history later

Rejected because it inverts the project’s causal architecture.
Projection is derived from accepted history and should not become durable before the source-of-truth boundary is durable.

### Alternative C: Use SQLite as the main baseline

Rejected as the main baseline because the project’s next goal is not merely local persistence convenience, but a stronger production-inspired durability baseline.

### Alternative D: Use Redis as the main baseline

Rejected because the current priority is durable semantic state rather than ephemeral coordination or cache-heavy runtime support.

---

## Follow-Up Work

Expected follow-up work includes:

- persistent storage architecture note
- persistence boundary note
- PostgreSQL-backed event store
- PostgreSQL-backed idempotency store
- PostgreSQL-backed projection store
- PostgreSQL-backed checkpoint store
- durable replay / rebuild verification tests

Completed baseline work includes:

- Stage 3.5B durable write-side baseline
- Stage 3.5C durable read-side baseline
- implementation notes preserving PR-level execution history for both stages

Remaining future work should focus on hardening and governance stages rather than re-opening the baseline persistence strategy.

---

## Summary

The project moved into a PostgreSQL-backed persistent storage baseline.

That baseline was introduced in causal order:

- durable accepted history
- durable idempotency
- durable projection state
- durable checkpoint progress
- durable replay / rebuild validation

Advanced runtime concerns remain deferred until this durable baseline is semantically stable.
