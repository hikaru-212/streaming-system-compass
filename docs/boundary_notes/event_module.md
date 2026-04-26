# Boundary Note: Event Module

[← Back to Boundary Notes Index](README.md)

## Purpose

This module defines the canonical event format used across the system.

Its job is to provide a stable semantic contract for events so that other layers can read, persist, validate, and project them consistently.

---

## Responsible For

This module is responsible for:

- defining the event schema
- carrying event identity
- carrying entity identity
- carrying event type
- carrying sequence
- carrying payload fields required by downstream consumers
- optionally carrying proof / provenance metadata

---

## Not Responsible For

This module is **not** responsible for:

- deciding whether an action is legal
- deciding the next sequence value
- deciding whether an event should be accepted
- deciding persistence success
- deciding projection correctness

Those responsibilities belong elsewhere:
- legality → aggregate
- acceptance / validation → Compass
- persistence → storage
- projection correctness → projection + Compass state layer

---

## Input Ownership

Important event fields may come from different owners:

- `event_id` may be generated inside the event factory
- `occurred_at_ms` may be generated inside the event factory
- `sequence` is owned by the aggregate / domain decision layer
- `proof` is owned by the semantic transition / provenance design

This means the event module packages semantic facts.  
It does not own all of them.

---

## Output Consumers

The event object is consumed by:

- storage layer
- transactional pipeline
- Compass transition validator
- projection pipeline
- analytical pipeline

Because of this, the event schema should remain stable and explicit.

---

## Design Principle

The event module should be treated as a **semantic data contract**, not as a domain decision-maker.

In short:

- it packages meaning
- it does not create all meaning by itself

---

## Practical Warning

If too much decision logic leaks into the event module, it becomes hard to maintain clear boundaries.

If too little meaning is carried by the event, downstream validation and projection become fragile.

The goal is to carry enough semantic structure for downstream consumers, without turning the event itself into the owner of the whole system.