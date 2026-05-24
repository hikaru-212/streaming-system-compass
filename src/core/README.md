# Core Layer

[← Back to src README](../README.md)

This directory contains the semantic source of truth for **Streaming System + Compass**.

If `src/` is the executable heart of the repository, `core/` is the part that defines what the system *means* before persistence, runtime orchestration, or validation layers are applied.

---

## Purpose

The purpose of `core/` is to define:

- domain event meaning
- aggregate meaning
- legal state transitions
- domain-local invariants
- shared semantic building blocks used by higher layers

This layer exists so that the rest of the system can depend on stable semantic meaning rather than inventing rules ad hoc at runtime.

---

## Current Structure

```text
src/core/
├── common/   # shared semantic primitives such as exact money handling
└── order/    # order-domain semantic core
```

---

## Directory Guide

### [common/](common/README.md)

Shared semantic building blocks.

This area is appropriate for items that are:

- domain-adjacent but not owned by one specific aggregate
- stable enough to be reused across multiple domain modules
- still part of semantic meaning rather than infrastructure detail

At the current stage, this area remains intentionally small.

Current concrete examples include:

- `money.py` — exact decimal money parsing, normalization, and durable string conversion for the current v1 domain.
- `ids.py` — centralized event identity generation for the current write-side event model.

`ids.py` currently generates UUIDv4 canonical string identities through a single boundary. This does not introduce UUIDv7 yet. The purpose is to prevent event identity generation from being scattered across domain, storage, and tests, so future UUID policy changes can be evaluated in one place.

This layer should remain small and disciplined.
It should not become a dumping ground for generic helpers.

---

### [order/](order/README.md)

The current primary domain module.

Use this directory when you want to understand:

- what `OrderEvent` means
- what the order aggregate owns
- what transitions are legal
- what invariants define order-state correctness
- how replay rebuilds aggregate state

At the current stage, `order/` is the main implemented transactional domain boundary in the repository.

---

## Design Principle

This layer should be treated as the **semantic source**, not as a runtime layer.

That means `core/` should define:

- meaning
- legality
- invariants
- apply-based state evolution

It should **not** define:

- persistence implementation
- runtime wiring
- checkpoint handling
- projection orchestration
- governance policy
- chaos injection

Those belong to:

- [storage/](../storage/README.md)
- [pipeline/](../pipeline/README.md)
- [bootstrap/](../bootstrap/README.md)
- [compass/](../compass/README.md)
- `chaos_engine/`

---

## Reading Order

If reading `core/` from scratch, the recommended order is:

1. `order/`
2. `common/` as needed for supporting types or shared semantic pieces

This is because the main semantic baseline of the repository currently lives in the order domain.

---

## Current Baseline

At the current stage, `core/` already provides the semantic baseline for:

- transactional write-side event generation
- aggregate replay / rehydration
- legal state transition definition
- proof-carrying event structure
- deterministic apply-based state evolution

This is why later layers can talk about:

- accepted history
- replayability
- transition truth
- projection correctness

without collapsing semantic meaning into storage or runtime mechanics.

---

## Practical Warning

`core/` should stay semantically strict.

If logic is placed here only because it is "important," that is not enough.

The real question is:

> does this logic define what the system means?

If the answer is no, it probably belongs elsewhere.

This matters because semantic drift inside `core/` is especially dangerous:
once meaning becomes blurred here, every higher layer becomes harder to reason about.

---

## Summary

`core/` is the layer that defines what the system is allowed to mean before the rest of the system executes around it.

If `pipeline/` defines movement and `storage/` defines persistence boundaries, `core/` defines the semantic truth those layers are built around.

