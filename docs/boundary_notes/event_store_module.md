# Boundary Note: Event Store Module

## Purpose

This module defines the persistence boundary for append-only event history.

It preserves the accepted event stream and supports replay, version continuity checks, and retrieval of prior history.

---

## Responsible For

This module is responsible for:

- appending events to a stream
- loading event history for a given entity
- retrieving the latest prior event
- enforcing persistence-side continuity checks
- supporting deterministic replay

---

## Not Responsible For

This module is **not** responsible for:

- deciding domain legality
- deciding whether an event claim is semantically trustworthy
- deciding how projections are computed
- deciding runtime governance policy

Those belong to:
- aggregate
- Compass
- projection layer

---

## Input Ownership

The event store receives:
- already-produced candidate events
- current-version expectation from the caller

This means the event store validates a persistence boundary, but does not invent the domain meaning of the write.

---

## Output Consumers

The event history is later consumed by:

- aggregate replay / rehydration
- Compass transition validation
- projection pipeline
- analytical pipeline
- recovery logic

Because many downstream layers depend on event history, this module is a foundational storage boundary.

---

## Design Principle

The event store should behave as an append-only semantic history boundary.

It preserves event order and continuity, but it does not replace higher-level semantic validation.

In short:

- aggregate decides meaning
- Compass checks semantic trust
- event store preserves accepted history

---

## Practical Warning

If event store logic starts deciding business rules, it becomes a second aggregate.

If event store continuity is too weak, replay and validation become unstable.

The right balance is:
- storage-level continuity checks
- without turning storage into the owner of domain truth