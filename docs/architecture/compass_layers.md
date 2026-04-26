# Compass Layers
[← Back to Architectures Index](README.md)


## Purpose

This document describes the layered role of Compass in the project.

Compass is not treated as a single undifferentiated validator.  
Instead, it grows through multiple semantic layers, each validating a different aspect of system correctness.

---

## Why Compass Must Be Layered

A streaming system can fail semantically in more than one way.

For example:

- an event may falsely claim to follow a legal predecessor
- a projection may drift even though each event was individually valid
- a checkpoint may claim progress that does not match actual processed history
- a system may execute successfully but still violate intended meaning

Because these are different failure modes, Compass should not be modeled as one flat validation step.

---

## Layer 1: Transition Truth Validation

### Question
Does this event truthfully represent a legal transition from the state it claims to follow?

### Scope
This layer validates the event itself before or during admission.

Typical checks include:
- sequence continuity
- predecessor identity
- claimed previous version
- claimed previous status
- transition legality

### Inputs
- candidate event
- optional proof / provenance claim
- actual prior history from event store

### Typical Location
`src/compass/transition/`

### Meaning
This is the earliest Compass boundary.

It does not ask whether the whole runtime pipeline is correct yet.  
It asks whether the individual event is semantically trustworthy.

---

## Layer 2: Runtime State / Projection Validation

### Question
After events have been consumed and state has been derived, does the resulting runtime state still satisfy expected invariants?

### Scope
This layer validates state after projection or checkpoint progression.

Typical checks include:
- projected version consistency
- state-machine legality in materialized state
- replay vs incremental consistency
- checkpoint correctness
- domain invariants over projected values

### Inputs
- projected state
- replayed state
- processed history
- checkpoint metadata

### Typical Location
`src/compass/state/`

### Meaning
This is closer to the original runtime verification vision of Compass.

It does not care only about whether an event looked legal.  
It cares whether execution over time remains semantically correct.

---

## Layer 3: Policy and Governance

### Question
If a semantic violation occurs, what should the system do?

### Scope
This layer handles response strategy.

Typical actions include:
- ACCEPT
- WARN
- REJECT
- QUARANTINE

It may also include:
- violation classification
- evidence reporting
- audit records
- downstream action triggers

### Typical Location
`src/compass/policy/`
and
`src/compass/evidence/`

### Meaning
This is where Compass stops being only a validator and becomes a semantic governance mechanism.

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