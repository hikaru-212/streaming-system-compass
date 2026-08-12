# Boundary Note: Projection Module

[← Back to Boundary Notes Index](README.md)

> **Current implementation note:** The original external responsibility split
> below remains valid. Runtime progress is now implemented through exact-next
> per-order rows for the fixed projection definition and repaired epoch, while
> legacy scalar checkpoints are historical operational evidence. Stage 4B.3
> separately defines projection trust continuation; it does not change accepted
> history into derived projection authority. See [ADR 0020](../adr/0020_per_order_projection_progress_and_order_local_snapshot_tails.md)
> and the [Stage 4B.3 responsibility boundary](../implementation_notes/stage_4b_3/projection_trust_continuation_boundary.md).

## Purpose

This module defines how accepted event history is transformed into read-side state.

Its role is to derive state from event streams, not to decide whether events are semantically admissible in the first place.

This note describes the external boundary of the projection module.

For the internal Stage 3 boundary between reducer, worker, projection store, and checkpoint store, see [Projection Boundary Note](projection_boundary.md).

---

## Responsible For

This module is responsible for:

- reading accepted event history
- applying projection logic incrementally
- deriving read-side state
- supporting rebuild / replay
- tracking exact-next order-local processing through durable per-order progress

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
- read-side validation and Stage 4 governance-evidence mapping
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
