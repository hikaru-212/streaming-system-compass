# ADR: Stateless Registry and Concurrency Strategy Boundary

## Status

Accepted

---

## Context

The transactional path of the project requires a registry/orchestration layer that coordinates:

- idempotency checks
- aggregate rehydration
- candidate event production
- transition validation
- event persistence
- accepted-event application

An earlier design direction allowed the registry to keep long-lived in-memory aggregate instances, for example through an internal cache such as:

- `self._instances = {}`

This approach is attractive in a strictly single-node setting because it reduces replay cost and allows O(1)-like in-memory access for hot entities.

However, the target architecture of this project is not a pure single-node system.  
It is intended to evolve toward a production-inspired event-driven system with:

- replayability
- shared source of truth
- future multi-node consistency
- semantic correctness under failure

Because of that, the registry design must prioritize architectural direction over local in-memory optimization.

---

## Decision

The project adopts a **stateless registry / rehydration-based transactional flow** as the baseline design.

This means:

- the registry does not keep long-lived aggregate instances as a durable in-memory truth source
- aggregate state is rebuilt from persisted event history when needed
- accepted history remains the primary source of semantic reconstruction
- in-memory aggregate objects are treated as short-lived execution objects, not as globally trusted cached state

In addition, concurrency handling is treated as a **separate boundary** rather than being permanently hard-coded into the registry itself.

The registry will therefore be designed so that concurrency / admission strategy can later be switched without rewriting the domain core.

The first concrete strategy will still be an optimistic version-based approach, but the architecture should leave room for other strategies later.

---

## Why This Decision Was Chosen

### 1. Alignment with the target architecture

This project aims to demonstrate:

- deterministic replay
- correctness from event history
- semantic validation under failure
- future multi-node thinking

A stateless registry fits this direction better than a long-lived local aggregate cache.

---

### 2. Separation between semantic truth and local optimization

A persistent in-memory registry cache is a local optimization.

It may be valid in a perfect single-node system, but it should not become the architectural truth model of a system intended to grow toward distributed execution.

The project therefore chooses to keep:

- event history as durable truth
- aggregate rehydration as reconstruction mechanism

rather than:
- registry memory as long-lived operational truth

---

### 3. Cleaner future path toward multi-node consistency

If aggregate truth lives in local memory, multi-node consistency becomes difficult because each process owns a different local snapshot.

A stateless registry avoids making local memory a first-class consistency boundary.

---

### 4. Explicit trade-off rather than accidental design

This decision does **not** mean that single-node caching is always wrong.

In a strictly single-node environment, an in-memory aggregate cache plus eviction policy may be a strong performance optimization.

However, this repository intentionally chooses a different baseline because the project’s goal is not merely single-node speed.  
Its goal is correctness-oriented system design with replayability and future multi-node extensibility.

---

## Consequences

### Positive Consequences

- replay becomes a first-class design principle
- registry behavior aligns with future distributed thinking
- aggregate memory state becomes short-lived and easier to reason about
- event history remains the stable reconstruction source
- future snapshot insertion becomes easier to justify and describe
- concurrency control can later evolve without rewriting the domain core

---

### Negative Consequences

- rebuilding aggregate state on demand is more expensive than reading from a local long-lived cache
- replay cost may become noticeable for long event histories
- performance optimizations such as snapshots may be needed later
- the baseline implementation may appear less “optimal” than a perfect single-node cache design

These costs are accepted intentionally in exchange for stronger architectural clarity.

---

## Concurrency Strategy Decision

The registry should not permanently assume that one concurrency strategy is always optimal.

Different workloads may require different concurrency strategies:

- optimistic control for low-contention entity flows
- pessimistic locking for stronger serialization needs
- queue/serialization-based approaches for extreme contention

Therefore, concurrency handling should be treated as an abstract boundary that can evolve independently of the domain core.

The first concrete implementation may still use optimistic version-based checking, but this should be understood as:

- current strategy choice
- not permanent semantic truth

---

## Not Chosen

### Option A: Long-lived in-memory registry cache as the main baseline
Not chosen as the main baseline because:
- it risks unbounded memory growth
- it makes local process state too important
- it does not align well with future multi-node execution

### Option B: Immediate full concurrency strategy framework
Not chosen yet because:
- it would introduce too much abstraction too early
- the project first needs a clear working transactional baseline
- one concrete strategy should exist before multiple strategies are generalized

---

## Follow-Up Implications

This decision suggests the following follow-up directions:

1. implement transactional flow around rehydration rather than long-lived aggregate cache
2. keep replay explicit in the registry path
3. leave a clean insertion point for future snapshot logic
4. leave a clean insertion point for future concurrency strategy abstraction
5. document the single-node perfect-cache alternative as a conscious trade-off, not as a forgotten possibility

---

## Summary

The registry remains an orchestration boundary, but its implementation direction is now clarified:

- stateless by baseline
- replay-oriented
- future snapshot-friendly
- future concurrency-strategy-extensible

This is not because single-node caching is universally inferior, but because the project intentionally prioritizes replayable semantic correctness and future multi-node alignment over local in-memory optimality.