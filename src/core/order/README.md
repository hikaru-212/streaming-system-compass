# Order Domain Core

[← Back to core README](../README.md)

This module is the semantic starting point of the project.

At the current stage of development, the system begins here rather than from:
- projection workers
- analytical pipelines
- chaos scenarios
- distributed deployment

The goal of this module is to define the **transactional semantic core** of the order domain before the surrounding runtime layers are built around it.

---

## Why This Module Comes First

The broader project aims to become a failure-aware streaming system with:

- transactional correctness
- projection/runtime correctness
- semantic validation through Compass
- adversarial validation through chaos engineering

However, before any of those layers can be meaningfully implemented, the system must first define:

- what an order event is
- what an order state is
- what counts as a legal state transition
- what sequence/version means
- what proof/provenance means
- which invariants belong to the order domain itself

This module exists to answer those questions first.

---

## Role in the Final Architecture

This module belongs to the **domain semantic core** of the system.

Within the intended long-term architecture, the project is expected to evolve roughly as follows:

```text
src/core/order/
→ src/storage/
→ src/pipeline/transactional/
→ src/compass/transition/
→ src/pipeline/projection/
→ src/storage/projection_store + checkpoint_store
→ src/compass/state/
→ src/pipeline/analytical/
→ chaos_engine/
```

This means:

- `core/order` defines semantic truth
- `storage` preserves semantic history
- `pipeline/transactional` executes the write-side flow
- `compass/transition` validates event truth
- `projection` derives read-side state
- `compass/state` validates runtime state correctness
- `chaos_engine` pressure-tests whether the above guarantees survive failure

This module is therefore not an isolated utility folder.  
It is the first implementation boundary of the full system.

---

## Purpose

This module defines the smallest semantically coherent write-side core for the order domain.

Its purpose is to make the following explicit:

- order event schema
- proof / provenance claim schema
- aggregate transition rules
- apply-based state mutation
- version / sequence semantics
- domain-level invariants

---

## Responsible For

This module is responsible for:

- defining domain vocabulary for the order lifecycle
- defining canonical event schema for orders
- defining proof structure for event-level transition claims
- defining the aggregate as the domain decision-maker
- defining how accepted events are applied to aggregate state
- defining the semantic meaning of sequence/version progression
- defining domain-level invariants related to transactional correctness

Typical files in this module include:

- `types.py`
- `event.py`
- `proof.py`
- `aggregate.py`
- `invariants.py` (optional later)

---

## Not Responsible For

This module is **not** responsible for:

- event persistence
- request-level idempotency storage
- orchestration of the transactional flow
- projection worker logic
- projection checkpoint persistence
- analytical event-time processing
- Compass policy actions
- chaos/failure injection
- deployment or infrastructure concerns

Those responsibilities belong to other layers such as:

- `src/storage/`
- `src/pipeline/`
- `src/compass/`
- `chaos_engine/`

---

## Main Components

### `types.py`
Defines shared domain vocabulary.

Examples:
- `EventType`
- `OrderStatus`
- other shared enums or semantic constants

This file establishes the basic language of the order domain.

---

### `event.py`
Defines the canonical order event shape.

`OrderEvent` is a semantic data contract.

It is responsible for carrying:
- event identity
- order identity
- event type
- sequence
- payload fields
- proof/provenance fields when needed

It is **not** responsible for deciding:
- whether a transition is legal
- what the next sequence should be
- whether the event should be accepted

---

### `proof.py`
Defines the proof / provenance claim attached to an event.

Typical proof fields may include:
- `prev_status`
- `prev_version`
- `prev_event_id`

The purpose of proof is to let an event explicitly claim what predecessor state it says it follows.

This is mainly used by the **Compass transition layer**, not by projection logic itself.

---

### `aggregate.py`
Defines the order aggregate.

This is the domain decision-maker.

It is responsible for:
- validating legal transitions
- deciding whether a command can produce an event
- determining next sequence progression
- applying events to rebuild or evolve aggregate state

This module should preserve a clear rule:

> The aggregate owns domain legality.  
> It does not own persistence or orchestration.

---

### `invariants.py` (optional later)
Defines explicit domain-level invariants.

Examples may include:
- illegal transition constraints
- amount-related semantic constraints
- sequence-related semantic assumptions

This file is optional at the very beginning, but likely useful as the core matures.

---

## Design Principle

This module follows a simple principle:

> Define semantic meaning first.  
> Build execution and failure testing around that meaning later.

In practical terms:

- event schema should be explicit
- proof schema should be explicit
- aggregate legality should be explicit
- state mutation should be explicit
- boundaries should be explicit

The more explicit this module is, the easier it becomes to implement:
- storage
- transactional orchestration
- Compass validation
- projection pipelines
- chaos scenarios

without semantic drift.

---

## Sequence / Version Ownership

One important design rule in this module is that **sequence/version is owned by the aggregate/domain transition logic**, not by the event object itself.

That means:

- the event carries `sequence`
- but the aggregate decides what that sequence should be

This keeps boundary ownership clear:
- event = semantic carrier
- aggregate = semantic decision-maker

---

## Relationship to Proof-Carrying Data

This project intentionally supports a proof-carrying event model.

That means events may carry a lightweight semantic claim about the state they follow.

This does **not** mean proof replaces validation.

Instead:

- proof makes transition claims explicit
- Compass later compares those claims against actual history
- projection may ignore most proof fields if they are not needed for state derivation

So proof belongs primarily to:
- event truth validation
not to:
- projection reducer logic

---

## Current Implementation Scope

At the current stage, this module focuses only on the first semantic baseline.

The immediate scope is:

1. define order types
2. define order event structure
3. define proof structure
4. define aggregate rules
5. define apply-based state mutation
6. define sequence semantics

This means the current goal is **not yet** to solve:
- real projection runtime
- analytics
- chaos hardening
- distributed coordination

Those come later.

---

## Near-Term Integration Points

After this module stabilizes, it will integrate with:

### `src/storage/`
For:
- event persistence
- idempotency persistence
- replay source

### `src/pipeline/transactional/`
For:
- command handling
- orchestration
- aggregate rehydration
- event admission flow

### `src/compass/transition/`
For:
- proof consistency checks
- predecessor validation
- event truth validation

---

## Long-Term Integration Points

Later, this module will also support:

### `src/pipeline/projection/`
Where accepted events are consumed to derive read-side state.

### `src/compass/state/`
Where projected state and runtime checkpoints are semantically validated.

### `chaos_engine/`
Where the system is tested under:
- duplicates
- out-of-order events
- partial commits
- jitter
- backpressure
- recovery failures

---

## Key Invariants

At this stage, the most important invariants include:

- order state transitions must be legal
- event sequence must remain continuous
- accepted events must be replayable
- replay must deterministically rebuild aggregate state
- if proof is used, proof claims must remain consistent with actual prior history

These invariants form the foundation for later layers.

---

## Practical Reading Order

If implementing or reading this module from scratch, the recommended order is:

1. `types.py`
2. `event.py`
3. `proof.py`
4. `aggregate.py`
5. `invariants.py` (if present)

This order reflects the intended scale of understanding:

- first define vocabulary
- then define event shape
- then define proof semantics
- then define domain decision logic
- then formalize invariants

---

## Summary

`src/core/order/` is the first implementation boundary of the project.

It is where the transactional meaning of the system becomes explicit.

The rest of the system will later grow around this module:
- storage will preserve it
- pipeline will execute it
- Compass will validate it
- chaos will test whether it survives failure

If this module is unstable, the rest of the architecture will drift.  
If this module is clear, the rest of the system can evolve with much stronger consistency.
