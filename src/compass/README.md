# Compass Layer

This module defines the semantic validation and governance logic of the system.

If `src/core/` defines meaning, and `src/pipeline/` executes meaning, then `src/compass/` exists to check whether that meaning remains valid under runtime conditions.

---

## Purpose

The purpose of Compass is to validate correctness beyond simple execution success.

It is designed to answer questions such as:

- Is this event truly a legal transition from the state it claims to follow?
- Does projected state still satisfy expected invariants?
- Does replayed state match incrementally derived state?
- Should a violation be accepted, warned, rejected, or quarantined?

Compass is therefore not just a validator.  
It is the beginning of a semantic runtime governance layer.

---

## Responsible For

This module is responsible for:

- event-level transition validation
- proof / provenance checking
- projected-state invariant validation
- checkpoint semantic validation
- semantic policy classification
- evidence / violation reporting

Typical submodules may include:

- `transition/`
- `state/`
- `policy/`
- `evidence/`

---

## Not Responsible For

This module is **not** responsible for:

- defining the order domain itself
- storing event history as the source of truth
- running the full transactional or projection pipeline
- injecting chaos scenarios
- replacing the event log or projection system

Those responsibilities belong to:

- `src/core/`
- `src/storage/`
- `src/pipeline/`
- `chaos_engine/`

---

## Design Principle

Compass exists because a system is not correct merely because it runs.

A pipeline may successfully process data while still drifting semantically.

Compass therefore focuses on validating:

- transition truth
- state correctness
- checkpoint consistency
- semantic governance decisions

This reflects the broader project principle:

> A system is not correct because it works.  
> A system is correct because it preserves intended meaning under execution and failure.

---

## Compass Layers

### `transition/`
This is the first Compass layer.

It validates whether an event truthfully represents a legal transition from the state it claims to follow.

Typical checks may include:
- sequence continuity
- predecessor identity
- proof consistency
- transition legality

This is the most immediate Compass implementation target.

---

### `state/`
This is the second Compass layer.

It validates whether state derived through projection or replay remains semantically correct.

Typical checks may include:
- projected version consistency
- projected state invariants
- replay vs incremental consistency
- checkpoint correctness

Example semantic violations may include:
- if current state is `SHIPPED` and an event behaves like `PAYMENT_ADJUSTED`, the projected state may violate the intended order lifecycle
- if `paid_amount != total_amount` while state ∈ {`PAID`, `SHIPPED`}, the runtime state may be semantically inconsistent

This layer becomes important after projection evolves into a real runtime worker.

---

### `policy/`
This layer determines how semantic violations are handled.

Typical actions may include:
- ACCEPT
- WARN
- REJECT
- QUARANTINE

It may also include:
- violation classification
- evidence reporting
- audit records
- downstream action triggers

### Future Work
- policy-driven validation
- dynamic rule injection
- failure classification

This is where Compass stops being only a validator and becomes a semantic governance mechanism.

---

### `evidence/`
This layer structures how validation results are recorded and surfaced.

Typical responsibilities:
- Compass result formats
- evidence records
- audit-friendly validation output
- semantic violation logging

---

## Relationship Between the Layers

The layers are not substitutes for one another.

They answer different questions:

- transition layer asks whether an event is trustworthy
- state layer asks whether execution results remain correct
- policy layer asks how the system should respond to semantic violations

This layered approach prevents Compass from collapsing multiple concerns into one ambiguous boundary.

---

## Role of Proof-Carrying Data

Proof-carrying data belongs mainly to **Layer 1**.

Its purpose is to strengthen event-level semantic admission by allowing Compass to compare:

- claimed predecessor
- claimed previous version
- claimed previous status

against actual event history.

This is useful when event truth itself needs stronger validation.

However, proof-carrying data is not required for all forms of Compass.

Layer 2, for example, can still exist without proof-carrying data if the system can validate derived state and replay consistency from history and projection outputs.

In that sense:

- proof strengthens **transition truth validation**
- proof is not the sole foundation of **runtime state verification**

---

## Current Project Focus

The immediate Compass focus should be:

1. transition truth validation
2. later state-level validation
3. later policy and governance behavior

This order is intentional.

The system should first decide:
- what counts as a trustworthy event

before it attempts to decide:
- whether downstream state remains semantically correct over time

---

## Future Evolution

Over time, Compass is expected to evolve from:

- event-level semantic admission

into:

- runtime state validation
- checkpoint verification
- evidence logging
- policy-driven governance
- adversarial semantic survivability under chaos

This evolution matches the broader direction of the project.

---

## Summary

Compass is best understood as a layered semantic defense system.

- Layer 1 protects event truth
- Layer 2 protects runtime state correctness
- Layer 3 governs system response to semantic violations

This layered view keeps Compass aligned with both transactional correctness and long-term streaming-runtime governance.

