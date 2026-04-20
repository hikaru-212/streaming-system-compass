# Boundary Note: Registry Module

## Purpose

This module defines the orchestration boundary of the transactional path.

It does not own domain semantics directly.  
Instead, it coordinates the order in which domain, validation, and persistence modules interact.

---

## Responsible For

This module is responsible for:

- checking idempotency before processing
- loading or creating aggregate instances
- replaying prior history when needed
- calling aggregate logic
- calling transition validation when required
- persisting accepted events
- applying accepted events to in-memory aggregate state

---

## Not Responsible For

This module is **not** responsible for:

- inventing business rules
- defining event schema
- being the persistence layer itself
- being the final owner of semantic policy
- being the projection runtime

Those belong to:
- core
- storage
- Compass
- projection pipeline

---

## Input Ownership

The registry receives:
- external commands / requests
- storage dependencies
- validation dependencies
- aggregate access

It is therefore a coordination layer, not a domain truth layer.

---

## Output Consumers

The registry returns:
- accepted events
- rejection outcomes
- previous idempotent results when applicable

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
- runtime governance policy

---

## Practical Warning

If the registry begins to encode domain transitions directly, it duplicates aggregate logic.

If it becomes too passive, pipeline sequencing becomes unclear.

Its correct role is orchestration, not semantic ownership.