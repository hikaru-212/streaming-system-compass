# Common Semantic Primitives

[← Back to core README](../README.md)

This directory contains shared semantic primitives used by the core domain layer.

These modules are intentionally small.

They should support stable domain meaning without becoming a dumping ground for generic helpers.

---

## Purpose

The purpose of `core/common/` is to hold reusable semantic building blocks that are:

- shared across core domain modules
- stable enough to be reused
- close to domain meaning
- independent of storage, orchestration, and infrastructure concerns

This directory should not contain general-purpose utilities just because they are convenient.

A module belongs here only if it supports the semantic meaning of the system.

---

## Current Modules

### `money.py`

Provides exact decimal handling for the current v1 domain.

Responsibilities include:

- rejecting float-based money ambiguity
- parsing money inputs into `Decimal`
- normalizing money values to the current v1 precision baseline
- enforcing positive-money validation
- producing stable durable/string forms for payloads and semantic fingerprints

This module exists because money-like values are part of domain semantics and must remain exact before persistence or fingerprinting logic depends on them.

---

### `ids.py`

Provides centralized event identity generation.

The current implementation generates UUIDv4 canonical string identities through one boundary.

This module exists so event identity generation does not become scattered across domain logic, storage logic, and tests.

Current behavior:

```python
generate_event_id() -> str
```

The current implementation uses UUIDv4 canonical string form.

UUIDv7 or another time-ordered UUID strategy may be evaluated later, but that decision should be made at this boundary rather than by changing event creation logic throughout the codebase.

---

## Boundary

This directory is responsible for shared semantic primitives.

It is not responsible for:

- persistence implementation
- database connection handling
- runtime orchestration
- validation policy
- governance decisions
- test infrastructure
- generic utility accumulation

Those belong to other layers such as:

- `src/storage/`
- `src/pipeline/`
- `src/compass/`
- tests / tooling directories

---

## Design Principle

Keep this directory small.

A new module should be added here only when it represents a stable semantic support boundary.

Good candidates:

- exact money handling
- identity generation policy boundary
- future shared value-object primitives

Bad candidates:

- random formatting helpers
- one-off test helpers
- database utilities
- orchestration helpers
- generic convenience functions

---

## Summary

`core/common/` supports semantic consistency across the core layer.

It should remain small, explicit, and disciplined.
