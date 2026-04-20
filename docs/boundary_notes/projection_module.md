# Boundary Note: Projection Module

## Purpose

This module defines how accepted event history is transformed into read-side state.

Its role is to derive state from event streams, not to decide whether events are semantically admissible in the first place.

---

## Responsible For

This module is responsible for:

- reading accepted event history
- applying projection logic incrementally
- deriving read-side state
- supporting rebuild / replay
- later supporting checkpoint-based runtime processing

---

## Not Responsible For

This module is **not** responsible for:

- deciding domain legality
- deciding event admission
- deciding sequence ownership
- carrying full audit/proof semantics if not needed for state derivation
- replacing event truth validation

Those belong to:
- aggregate
- Compass transition layer
- event store

---

## Minimal Dependency Principle

Projection should depend only on the minimum semantic fields required for state derivation.

Typical examples:
- entity id
- event type
- sequence
- payload fields needed by state updates

Projection should avoid unnecessary dependence on:
- proof internals
- predecessor identity details
- admission-only metadata

This keeps the projection layer stable and decoupled from write-side provenance concerns.

---

## Output Consumers

Projection outputs are consumed by:
- read-side query models
- state-level Compass validation
- experiments / demos
- future analytical or monitoring components

---

## Design Principle

Projection should be treated as a **state derivation mechanism**, not as the owner of event truth.

In short:

- transition truth should already be decided earlier
- projection should focus on deriving state from accepted history

---

## Practical Warning

If projection depends on too much write-side internal metadata, it becomes fragile.

If projection ignores sequence and state assumptions entirely, it becomes unsafe.

The right balance is:
- depend on the minimum event semantics required for derivation
- validate projection results at a higher state-validation layer when necessary