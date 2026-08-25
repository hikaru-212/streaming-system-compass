# Compass Layers
[← Back to Architectures Index](README.md)


## Purpose

This document describes the layered role of Compass in the project.

> **Current status:** Layer 1 admission is implemented. Stage 4A maps bounded
> write-side, read-side, and snapshot evidence into `SemanticOutcome`; Stage 4B
> maps selected evidence into strict, optionally persisted `DecisionReceipt`
> records. Stage 4B.1 and Stage 4B.2 completed bounded producer-specific trace
> and measurement evidence, and Stage 4B.5 completed the Order Correctness
> Contract v0. Stage 4C Runtime Decision Authority and Stage 4E Same-Request
> Re-Invocation Authority are complete and closed. Stage 4E implements exactly
> two reviewed authority profiles and one-shot owner custody; it is not generic
> retry governance. Stage 4D Strategy Selection Authority remains deferred.
> These governance responsibilities consume semantic evidence downstream; they
> are not a new Compass validation layer.

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

## Downstream Governance Consumption — Not a Third Validation Layer

### Question
Given current semantic evidence, which generic response is authorized, which
eligible strategy may perform it, and—only when relevant—may another attempt be
made?

### Scope
Governance consumes evidence produced by Layer 1, Layer 2, and bounded producer
adapters. ADR 0027 assigns separate downstream responsibilities:

- Stage 4C Runtime Decision Authority authorizes the generic current response;
- Stage 4D Strategy Selection Authority chooses an eligible execution path
  inside prior authorization;
- Stage 4E Same-Request Re-Invocation Authority decides whether one of its two
  reviewed completed-invocation evidence profiles authorizes at most one fresh
  invocation with the owner-retained same complete `RequestSignature`; and
- execution remains separate from all three.

### Typical Location

The implemented current-response and bounded re-invocation authority contracts
and evaluators live under `src/compass/runtime/`. The one-shot Stage 4E owner
lives at `src/pipeline/transactional/postgres_write_side_invocation_owner.py`.
Stage 4D has no production selector because its implementation is deferred.

### Meaning
This is downstream consumption of semantic evidence, not “Layer 3” validation.
`DecisionReceipt` may preserve durable evidence for later consumers, but prior
receipt persistence is not required for the first live Stage 4C or Stage 4E
path.

---

## Relationship Between the Layers

The layers are not substitutes for one another.

They answer different questions:

- transition layer asks whether an event is trustworthy
- state layer asks whether execution results remain correct
- downstream governance separately owns current-response authorization,
  strategy selection, another-attempt authorization, and execution

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

The current Compass position is:

1. maintain the implemented Layer 1 transition-truth admission boundary;
2. preserve bounded write-side and read-side evidence through completed
   `SemanticOutcome`, `DecisionReceipt`, trace, measurement, and exact-rule
   contracts; and
3. enter Stage 4C production work only after its concrete consumer, invocation
   owner, eligible evidence subset, response vocabulary, and fail-closed
   behavior are frozen.

This order is intentional.

Layer 1 and Layer 2 remain semantic-validation distinctions. Governance remains
a downstream consumer rather than a reason to redefine those layers.

---

## Future Evolution

Over time, Compass is expected to evolve from:

- event-level semantic admission

into:

- runtime state validation
- checkpoint verification
- structured semantic and durable governance evidence
- separately owned runtime decision, strategy-selection, and conditional
  retry / attempt-authorization boundaries
- adversarial semantic survivability under chaos

This evolution matches the broader direction of the project.

---

## Summary

Compass is best understood as a layered semantic defense system.

- Layer 1 protects event truth
- Layer 2 protects runtime state correctness
- downstream governance consumes evidence from those boundaries without
  becoming a third validation layer

This layered view keeps Compass aligned with both transactional correctness and long-term streaming-runtime governance.
