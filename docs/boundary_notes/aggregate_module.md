# Boundary Note: Aggregate Module

[← Back to Boundary Notes Index](README.md)

## Purpose

This module defines the domain decision-maker of the transactional core.

It is responsible for deciding whether a command can produce a new legal event, and for applying accepted events to evolve aggregate state.

---

## Responsible For

This module is responsible for:

- enforcing legal state transitions
- deciding whether a command is valid under current state
- determining next semantic step
- determining next sequence progression
- applying events to mutate aggregate state
- supporting replay / rehydration through apply logic

---

## Not Responsible For

This module is **not** responsible for:

- event persistence
- idempotency storage
- orchestration across modules
- checkpoint persistence
- analytical aggregation
- chaos scenario injection

Those belong to:
- storage
- pipeline
- chaos_engine

---

## Input Ownership

The aggregate should receive:

- command inputs
- current aggregate state
- previously replayed history, indirectly through apply

It should not need to know:
- database details
- transport details
- external consumer offsets

---

## Output Consumers

The aggregate mainly produces:
- candidate domain events

Those events are then consumed by:
- transactional pipeline
- event store
- Compass transition validation
- replay / projection layers

---

## Design Principle

The aggregate is the owner of **domain legality**, not the owner of infrastructure.

It answers:
- can this action happen now?
- if yes, what event should represent it?
- if an accepted event is applied, how should state evolve?

---

## Practical Warning

If the aggregate becomes responsible for persistence or orchestration, boundaries blur.

If the aggregate does not clearly own transition legality, domain correctness becomes distributed across too many modules.

The aggregate should remain the semantic decision core of the write-side domain.