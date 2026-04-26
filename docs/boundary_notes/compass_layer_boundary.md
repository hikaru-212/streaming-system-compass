# Boundary Note: Compass Layer module

[← Back to Boundary Notes Index](README.md)

## Purpose

This note clarifies the responsibility boundaries between Compass layers and the rest of the system.

Compass is not a single flat validator. It is intended to evolve as a layered semantic defense system.

This note is a practical boundary companion to [Compass Layers](../architecture/compass_layers.md).

---

## Core Boundary Statement

Compass answers semantic correctness questions.

It does **not** replace:

- aggregate domain decision logic
- persistence concurrency control
- idempotency handling
- projection execution
- checkpoint storage
- downstream side-effect delivery

Compass observes, validates, classifies, and may later govern semantic outcomes.  
It should not silently take over responsibilities that belong to execution or storage layers.

---

## Layer 1: Transition Truth Validation

### Question

Does this candidate event truthfully represent a legal transition from the state it claims to follow?

### Owns

- candidate event semantic validation
- predecessor claim checking
- previous version/status verification
- transition truth checks
- proof/provenance comparison against actual prior history

### Does Not Own

- producing the candidate event
- deciding domain behavior inside the aggregate
- persisting the accepted event
- enforcing expected-version admission
- updating projection state

### Typical Location

```text
src/compass/transition/
```

### Boundary Summary

Layer 1 validates event truth before or during admission.

It can reject a semantically inconsistent candidate event, but it does not replace the persistence boundary that decides whether the candidate can still become the next accepted fact.

---

## Layer 2: Runtime State / Projection Validation

### Question

After accepted events have been consumed and state has been derived, does the resulting runtime state still satisfy expected invariants?

### Owns

- projected state invariant checks
- replay vs incremental consistency checks
- projected version correctness
- checkpoint semantic alignment
- state-level drift or mismatch reporting

### Does Not Own

- consuming events from the event log
- applying reducer logic
- persisting projection state
- persisting checkpoints
- deciding write-side admission

### Typical Location

```text
src/compass/state/
```

### Boundary Summary

Layer 2 validates the result of runtime execution.

It checks whether projection output remains semantically correct, but it should not become the projection worker itself.

---

## Layer 3: Policy and Governance

### Question

If a semantic violation occurs, what should the system do?

### Owns

- violation classification
- enforcement action mapping
- warning / rejection / quarantine policy
- evidence reporting
- audit-oriented response metadata

### Does Not Own

- raw domain decision logic
- low-level database writes
- event consumption mechanics
- retry scheduling
- message publication mechanics

### Typical Locations

```text
src/compass/policy/
src/compass/evidence/
```

### Boundary Summary

Layer 3 turns semantic validation results into governance actions.

It is where Compass evolves from validation into semantic governance, but it should still avoid becoming the entire runtime engine.

---

## Relationship to Aggregate

The aggregate owns domain behavior.

It decides whether a command can produce a candidate event according to domain rules.

Compass does not replace aggregate logic.

Instead:

```text
Aggregate produces candidate event.
Compass validates whether the candidate truthfully matches semantic history.
```

This keeps domain behavior and semantic admission checks separate.

---

## Relationship to Registry

The registry is an orchestration boundary.

It may call Compass validation and consume the resulting verdict or enforcement action.

However, the registry should not own Compass validation semantics.

Clean separation:

```text
Registry coordinates flow.
Compass validates meaning.
Policy decides enforcement action.
Persistence admits accepted facts.
```

---

## Relationship to Event Store

The event store preserves accepted event history and enforces persistence-level constraints such as expected-version admission.

Compass may read event history to validate proof or predecessor claims, but it should not become the event store.

The event store answers:

> What has been accepted?

Compass answers:

> Does this candidate or derived state remain semantically trustworthy?

---

## Relationship to Projection

Projection derives read-side state from accepted event history.

Compass Layer 2 may later validate projection results through state-level checks.

Projection answers:

> What state is derived from accepted events?

Compass Layer 2 answers:

> Is that derived state still semantically consistent?

Projection should not need all proof metadata if that metadata is only required for Layer 1 transition validation.

---

## Relationship to Concurrency Control

Concurrency control protects the persistence boundary from stale writes.

Compass protects semantic correctness.

A candidate event may be semantically valid but still fail concurrency admission if another event has already become the next accepted fact.

Therefore:

```text
Compass validation
≠
concurrency admission
```

Both are necessary.

---

## Relationship to Evidence

Evidence is the record that makes semantic validation explainable.

Depending on the layer, evidence may include:

- proof/provenance claims
- validation result metadata
- expected vs actual predecessor state
- projection mismatch reports
- checkpoint validation records
- policy action records

Evidence should support auditability and diagnosis, but it should not blur ownership of execution logic.

---

## Boundary Anti-Patterns

Avoid these mistakes:

- making Registry own validation semantics
- making Compass produce domain events directly
- making Projection depend on unnecessary proof metadata
- making EventStore decide domain legality
- treating Compass validation as a replacement for concurrency control
- treating policy actions as raw validation checks
- collapsing transition validation and state validation into one ambiguous validator

---

## Summary

Compass should be understood as a layered semantic validation and governance system.

A clean mental model is:

```text
Layer 1: validates event truth.
Layer 2: validates derived runtime state.
Layer 3: governs response to semantic violations.
```

Compass should remain close enough to runtime execution to validate meaning, but not so broad that it absorbs domain logic, persistence admission, projection execution, or retry handling.
