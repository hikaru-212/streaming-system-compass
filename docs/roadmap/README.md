# Roadmaps

[← Back to Docs Home](../README.md)

This directory contains roadmap documents for **Streaming System + Compass**.

Roadmaps describe implementation sequencing and system evolution. They are not meant to replace architecture notes or ADRs.

Use roadmap documents to understand what should be built first, what depends on what, and which features are intentionally deferred.

---

## Roadmap Index

| Document | Purpose |
|---|---|
| [Implementation Roadmap](implementation_roadmap.md) | Defines the overall implementation order from transactional semantic core to projection runtime, durable persistence, runtime semantic outcomes, reviewer-facing demo packaging, and later governance / chaos hardening. |
| [Compass Runtime Roadmap](compass_runtime_roadmap.md) | Defines the focused evolution path from the current write-side Compass baseline toward projection runtime, durable baselines, runtime semantic validation, and later governance behavior. |

---

## Recommended Reading Order

1. [Implementation Roadmap](implementation_roadmap.md)
2. [Compass Runtime Roadmap](compass_runtime_roadmap.md)

The implementation roadmap gives the global project sequence.

The Compass runtime roadmap gives a more focused view of how Compass should evolve from the current write-side baseline toward projection runtime, durable persistence, runtime semantic validation, and later governance behavior.

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
→ runtime semantic validation and outcome structuring
→ reviewer-facing demo packaging
→ governance and chaos hardening
```

The system should not attempt to solve chaos, broad governance, or distributed complexity before the transactional semantic core, write-side safety boundaries, runtime semantics, and durable persistence boundaries are coherent.
