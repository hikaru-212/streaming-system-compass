# Boundary Note: Proof Module

## Purpose

This module defines the proof / provenance claim attached to an event.

Its purpose is to let an event carry a lightweight semantic claim about the state it says it follows.

Typical examples include:

- claimed previous status
- claimed previous version
- claimed predecessor event identity

This allows the system to validate not only that an event exists, but also that it truthfully represents a legal transition from an actual prior state.

---

## Responsible For

This module is responsible for:

- defining the structure of transition proof
- carrying lightweight predecessor claims
- supporting event-level semantic validation
- making transition provenance explicit rather than implicit

Typical proof fields may include:
- `prev_status`
- `prev_version`
- `prev_event_id`

---

## Not Responsible For

This module is **not** responsible for:

- deciding whether a transition is legal
- deciding the next sequence
- deciding whether an event should be accepted
- deriving projection state
- replacing event history as the source of truth

Those responsibilities belong to:
- aggregate
- Compass transition validator
- event store
- projection pipeline

---

## Design Principle

Proof should be treated as a **semantic claim**, not as the final proof of truth by itself.

In other words:

- proof says what the event claims to follow
- Compass compares that claim against actual history
- event store preserves the actual history

This means proof is not a substitute for validation.  
It is an input to validation.

---

## Relationship to Event

Proof is typically carried **inside** the event, but it is conceptually different from the event's business payload.

For example:

- event payload may describe what happened
- proof describes what this event claims to follow

This distinction matters because:
- projection usually depends only on minimal event semantics
- transition validation may depend on proof fields

---

## Relationship to Aggregate

The aggregate is the most natural owner of proof generation because it knows:

- current state
- current version
- predecessor event identity
- whether the command is being issued from a legal current state

Therefore, proof is usually constructed at the same time the aggregate produces a candidate event.

---

## Relationship to Compass

Proof mainly belongs to the **transition validation** layer of Compass.

Compass uses proof to compare:

- claimed predecessor
- claimed previous version
- claimed previous status

against actual persisted history.

This helps answer:

> Does this event truthfully represent a legal transition from the state it claims to follow?

---

## Relationship to Projection

Projection should generally **not** depend on proof internals unless absolutely necessary.

Projection usually needs only:
- entity id
- event type
- sequence
- payload required for state updates

This means proof belongs mostly to event admission / semantic truth validation, not to state derivation logic.

---

## Practical Warning

If proof is treated as business payload, boundaries become blurry.

If proof is ignored entirely, event-level semantic validation becomes weaker.

The right balance is:
- keep proof explicit
- keep proof lightweight
- use proof mainly for transition truth checks
- avoid leaking proof into places that only need projection semantics

---

## Summary

The proof module defines how an event carries a claim about its predecessor state.

It does not decide truth by itself.  
Its role is to make semantic transition claims explicit, so that Compass can validate them against actual history.