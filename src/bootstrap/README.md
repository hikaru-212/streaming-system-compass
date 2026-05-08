# Bootstrap Layer

[← Back to src README](../README.md)

This module defines the **composition roots** of the system.

If `core/` defines meaning, `storage/` preserves semantic artifacts, `pipeline/` defines runtime flow, and `compass/` validates semantic trust, then `bootstrap/` is the layer that decides how concrete implementations are wired together into one executable runtime.

---

## Purpose

The purpose of this module is to:

- instantiate concrete implementations
- assemble them into one runtime boundary
- expose a stable entry point for executable system wiring

This layer exists so that business logic does not need to be mixed with implementation selection.

---

## Responsible For

This module is responsible for:

- instantiating concrete storage implementations
- instantiating concrete validation components
- instantiating concrete admission components
- wiring those components into a runnable system boundary
- selecting runtime composition options such as validation mode

Typical responsibilities include:

- choosing in-memory vs later persistent storage implementations
- choosing strict vs no-op validation modes
- connecting store / validator / gate / orchestrator objects

---

## Not Responsible For

This module is **not** responsible for:

- defining domain meaning
- deciding business legality rules
- inventing semantic policy
- mutating aggregate state rules
- performing validation logic itself
- acting as the persistence layer itself

Those responsibilities belong to:

- [core/](../core/README.md)
- [storage/](../storage/README.md)
- [pipeline/](../pipeline/README.md)
- [compass/](../compass/README.md)

In short:

> business logic must NOT live here

---

## Design Principle

This layer should be treated as a **composition boundary**, not as a semantic boundary.

It decides:

- which implementation is used
- which objects depend on which other objects
- what the runtime graph looks like

It should not decide:

- what an event means
- whether a transition is legal
- what the next state should be
- what semantic rule should exist

That distinction is critical.

Once business logic leaks into composition roots, the system becomes much harder to reason about and much harder to replace or evolve safely.

---

## Current Baseline

At the current stage, the main implemented composition root is the transactional runtime builder.

A typical baseline composition includes:

- `EventStore` as the accepted-history persistence boundary
- `IdempotencyProvider` as the request replay / duplicate protection boundary
- `FullProofValidator` and `NoOpValidator` as validation components
- `ValidationDispatcher`, `ValidationPolicy`, and `ValidationRuntime` as the Compass Layer 1 execution path
- `OptimisticVersionGate` as the admission / stale-write protection boundary
- `OrderRegistry` as the transactional orchestrator

This composition root is intentionally conservative:

- concrete implementations are chosen here
- semantic ownership remains outside this layer

---

## Why This Layer Matters

Without a composition root, the system would either:

- hard-code concrete implementations deep inside business logic
- or force business modules to know too much about infrastructure choices

Both are undesirable.

`bootstrap/` exists to ensure:

- semantic modules stay clean
- infrastructure choices stay replaceable
- runtime assembly remains explicit

This becomes even more important as the project evolves toward:

- persistent storage-backed implementations
- more complex projection runtime wiring
- later state-level Compass validation
- future governance layers

---

## Near-Term Evolution

At the current stage, the implemented composition focus is still strongest on the transactional runtime.

Later, `bootstrap/` is expected to also support:

- Stage 3.5 persistent storage baseline wiring
- projection-runtime composition roots
- later state-level Compass runtime wiring
- future policy / governance assembly

This means `bootstrap/` will grow, but it should grow only in one direction:

> more explicit composition, not more business logic

---

## Practical Reading Order

If reading this module from scratch, the recommended order is:

1. transactional runtime builder(s)
2. validation-mode selection logic
3. later projection / persistence composition roots

Read this module only after you understand:

- [core/](../core/README.md)
- [storage/](../storage/README.md)
- [pipeline/](../pipeline/README.md)
- [compass/](../compass/README.md)

Otherwise it is easy to confuse composition wiring with semantic ownership.

---

## Summary

This module decides how the system is assembled, not what the system means.

If the rest of `src/` defines the semantic and runtime pieces, `bootstrap/` is the layer that turns those pieces into a concrete executable graph.
