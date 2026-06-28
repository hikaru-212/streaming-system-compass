# ADR 0004: Why Compass Split into Two Layers

[← Back to ADR Index](README.md)

## Status

Accepted

---

## Implementation Status

Accepted and partially implemented at baseline level.

Layer 1 is implemented as the current write-side candidate-event validation boundary.

Related implementation files:

- `src/compass/transition/runtime.py`
- `src/compass/transition/types.py`
- `src/compass/transition/validators.py`

Layer 1 implementation evidence:

- `ValidationRuntime` orchestrates validator selection and policy mapping.
- `ValidationDispatcher` selects the active validation path.
- `ValidationPolicy` maps semantic validation results into runtime enforcement actions.
- `ValidationResult` records the candidate-event validation outcome.
- `ValidationDecision` separates semantic validation result from runtime action.
- `FullProofValidator` validates candidate-event truth against accepted-history context.

Related tests:

- `tests/unit/compass/transition/test_predecessor_mismatch_cases.py`
- `tests/unit/compass/transition/test_prev_status_mismatch_cases.py`
- `tests/unit/compass/transition/test_prev_version_mismatch_cases.py`
- `tests/unit/compass/transition/test_stale_candidate_cases.py`

Layer 2 is accepted as an architectural direction but has not yet been implemented as a full runtime governance layer.

Stage 3.5C and Stage 3.5D provide substrates for future Layer 2 work:

- durable read-side projection state
- durable checkpoint progress
- durable replay / rebuild validation
- projection snapshot-assisted replay validation
- projection snapshot-assisted state resolution

Future Layer 2 work should build on those substrates through structured validation outcomes, runtime decision policy, and action safety.

---

## Context

Compass did not begin as a two-layer architecture.

The original intuition was simpler:

```text
event store -> projection -> state verification
```

At the beginning of the project, most attention was placed on the projection side.

The main questions were things such as:

- out-of-order events
- retries
- replay correctness
- checkpoint progression
- state rebuild after failure
- read-side drift and inconsistency

In that early mental model, the event store was treated mostly as:

- the place where events are stored
- the durable input for projection
- the append-only source used for replay

In other words, the first focus was on what could go wrong **after** events already existed.

This led naturally to a first Compass intuition centered on runtime / state-level verification:

- if projection derives an invalid state
- if replay and incremental processing diverge
- if runtime state drifts from what it should be

then some verification layer should exist at the read-side or runtime layer.

That was the original Compass intuition.

---

## Problem Discovery

Once the project moved from abstract thinking into concrete implementation, a different question became unavoidable:

> Where do the events actually come from, and how can I ensure that the events entering the event store are themselves meaningful and legal?

This became especially important because the project is self-directed and does not begin with a real external transaction source.

There was no existing production event generator to inherit from.

That forced a more foundational question:

- how should an event be generated at all?
- what makes an event meaningful rather than garbage?
- what makes an event lawful rather than merely syntactically shaped?
- if the event store is the accepted history of the system, what stops semantically false events from entering it?

At that point, the original one-layer runtime-verification model became insufficient.

A later state-level verification layer could detect that something had gone wrong in derived state,
but it could not fully answer a stricter concern:

> how do we prevent semantically false events from entering accepted history in the first place?

This concern became stronger once proof-carrying event thinking entered the design.

Events were no longer treated as bare payloads.
They could carry claims such as:

- claimed previous status
- claimed previous version
- claimed predecessor identity

Once that became visible, the architectural question changed.

The problem was no longer only:

- “Is the projected state still correct?”

It also became:

- “Does this candidate event truthfully follow accepted history before it is allowed to enter accepted history?”

That is a different verification problem.

It is earlier in time, narrower in scope, and closer to event admission.

---

## Decision

Compass is split into two layers.

### Compass Layer 1

Compass Layer 1 performs **pre-persistence event-level transition truth validation**.

Its responsibility is to validate whether a candidate event truthfully follows accepted history before the event is admitted into accepted history.

Typical concerns include:

- claimed predecessor consistency
- claimed previous version consistency
- claimed previous status consistency
- event-level truth before persistence

Layer 1 exists to reduce the risk of polluting accepted history with semantically false events.

---

### Compass Layer 2

Compass Layer 2 performs **post-projection state-level runtime verification**.

Its responsibility is to validate whether derived or projected state remains semantically correct after accepted events are processed.

Typical concerns include:

- replay vs incremental consistency
- projected version correctness
- projected state invariants
- runtime drift after derivation

Layer 2 exists because even accepted history can still be incorrectly consumed, reduced, checkpointed, or materialized.

---

## Why One Layer Was Not Enough

A single state-level verification layer was not sufficient because it is too late for certain problems.

If a candidate event is semantically false before entering accepted history, then relying only on state-level verification means:

- detection happens later
- accepted history may already be polluted
- error isolation becomes weaker
- write-side truth and read-side drift become conflated

On the other hand, a single event-entry validation layer is also not sufficient.

Even if every accepted event is individually valid, the read-side can still fail through:

- projection bugs
- replay divergence
- checkpoint mismatch
- runtime processing errors
- incremental vs rebuild inconsistency

Therefore the two concerns must remain separate:

- **event-entry truth**
- **state-level runtime correctness**

This is the reason Compass became two-layered.

---

## Why This Is Not Over-Engineering

This split was not introduced as an abstract desire for more architecture.

It emerged because two different failure surfaces became visible during implementation thinking:

### Failure Surface A: Garbage Events Enter Accepted History

This is a write-side admission problem.

It asks:

- is this candidate event meaningful?
- is this candidate event lawful?
- does this event truthfully follow accepted history?

That belongs to Layer 1.

### Failure Surface B: Correct Events Produce Incorrect Runtime State

This is a read-side runtime problem.

It asks:

- is projection still correct?
- is replay equal to incremental processing?
- is checkpoint-aware state derivation still semantically coherent?

That belongs to Layer 2.

The split is therefore not cosmetic.
It is a separation of two different correctness problems.

---

## Consequences

### Positive Consequences

- accepted history receives stronger semantic protection
- runtime state verification remains distinct from admission validation
- write-side and read-side failure surfaces become easier to reason about
- proof-carrying event thinking becomes architecturally useful rather than decorative
- Compass now has a clearer growth path:
  - Layer 1 for event truth
  - Layer 2 for state/runtime truth

### Negative Consequences

- the architecture becomes more layered
- the implementation sequence becomes more demanding
- boundaries must be documented more carefully
- test design becomes more explicit because each layer needs different failure cases

These costs are accepted because they preserve semantic clarity.

---

## Implementation Consequence

This decision changes the implementation order of the system.

Before this split, Compass could have been treated mainly as a state-level runtime verifier attached to projection.

After this split, the write-side baseline must include:

- proof-carrying candidate events
- event-level transition validation before persistence
- a clear boundary between validation and admission

And the read-side must later include:

- projection reducer / worker separation
- replay and incremental equivalence checks
- projected-state verification

This means the architecture now evolves as:

```text
candidate event generation
-> Layer 1 transition-truth validation
-> admission into accepted history
-> projection / derivation
-> Layer 2 runtime state verification
```

---

## Retrospective Note

This decision was recognized clearly only after the write-side baseline had already been substantially built.

In that sense, this ADR is partly retrospective in explanation.

However, the architectural consequence is forward-looking.

The purpose of recording it now is to prevent future confusion such as:

- treating Compass as only a projection verifier
- assuming event-entry truth can be deferred until runtime state validation
- collapsing write-side semantic validation and read-side verification into one concept

The repository should instead preserve the distinction explicitly.

---

## Final Summary

Compass originally began as a one-layer intuition centered on runtime or state-level verification.

As the project moved from abstract projection concerns toward event generation and proof-carrying event semantics, a deeper problem became visible:

- projection correctness is not enough
- accepted-history entry itself must also be defended

That is why Compass became two-layered.

In short:

- **Layer 1 protects accepted history from semantically false event entry**
- **Layer 2 protects derived runtime state from semantic drift after derivation**
