# Boundary Note: Registry Module

[← Back to Boundary Notes Index](README.md)

## Purpose

This module defines the orchestration boundary of the transactional path.

It does not own domain semantics directly.  
Instead, it coordinates the order in which domain, validation, concurrency/admission, and persistence modules interact.

---

## Responsible For

This module is responsible for:

- checking idempotency before processing
- loading or creating aggregate instances
- replaying prior history when needed
- calling aggregate logic
- calling transition validation when required
- coordinating conditional persistence through the event store / concurrency gate
- applying accepted events to short-lived in-memory aggregate state

---

## Not Responsible For

This module is **not** responsible for:

- inventing business rules
- defining event schema
- being the persistence layer itself
- owning concurrency / admission strategy semantics
- making authoritative persistence decisions without the storage / concurrency boundary
- being the final owner of semantic policy
- being the projection runtime

Those belong to:

- core
- storage
- concurrency / admission boundary
- Compass
- projection pipeline

---

## Input Ownership

The registry receives:

- external commands / requests
- storage dependencies
- validation dependencies
- aggregate access
- concurrency / admission dependencies

It is therefore a coordination layer, not a domain truth layer or persistence truth layer.

---

## Output Consumers

The registry returns:

- accepted events
- rejection outcomes
- previous idempotent results when applicable
- conflict / retry-related outcomes when conditional admission fails

Its outputs are mainly consumed by:

- external command handlers
- experiments / demos
- later service boundaries

---

## Design Principle

The registry should be thought of as the **transactional conductor**.

It defines:

- what gets called
- in what order
- under what boundary assumptions

But it should not itself become the owner of:

- domain legality
- persistence truth
- concurrency / admission strategy semantics
- runtime governance policy

The key distinction is:

- the registry coordinates admission
- the storage / concurrency boundary makes the authoritative write decision
- Compass validates semantic trust
- the aggregate owns domain transition legality

For the concurrency and retry-safety decision behind this boundary, see [Concurrency Control, Idempotency, and Retry Safety](../adr/0003_concurrency_idempotency_and_retry_safety.md).

---

## Practical Warning

If the registry begins to encode domain transitions directly, it duplicates aggregate logic.

If the registry starts making authoritative persistence or concurrency decisions by itself, it leaks storage/admission responsibility into orchestration.

If it becomes too passive, pipeline sequencing becomes unclear.

Its correct role is orchestration, not semantic ownership, persistence ownership, or admission-strategy ownership.

---

## Summary

The registry is the transactional coordination boundary.

It connects idempotency, aggregate behavior, Compass transition validation, and conditional persistence, but it should not absorb the responsibilities of those components.

Its job is to preserve the order of the write-side flow while keeping domain truth, semantic validation, persistence truth, and concurrency/admission decisions in their proper layers.
