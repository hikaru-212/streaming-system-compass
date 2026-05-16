# Boundary Note: Persistence Boundary

[← Back to Boundary Notes Index](README.md)

## Purpose

This note clarifies how persistence should be introduced into the project without collapsing the existing semantic boundaries.

At the current stage, the repository already separates:

- semantic meaning
- runtime movement
- semantic validation
- projection-state derivation
- checkpoint progression

As persistent storage is introduced, this note exists to make one thing explicit:

> durable storage must preserve boundary clarity rather than blur it.

---

## Main Boundary Principle

Persistence is not the owner of semantic meaning.

Persistence is the owner of durable preservation.

That means:

- `core/` still defines meaning
- `pipeline/` still defines runtime movement
- `compass/` still defines semantic checking
- `storage/` defines how accepted history and runtime progress survive across time

Once persistence begins to invent business truth, the architecture collapses.

---

## The Four Main Persistence Boundaries

### 1. Event Store Boundary

Owns:

- accepted event history persistence
- append-only event recording
- aggregate-local replay source
- sequence continuity at persistence boundary

Does **not** own:

- domain legality
- transition-truth judgment
- idempotency semantics
- projection logic

### 2. Idempotency Store Boundary

Owns:

- request-level replay tracking
- durable retry classification support
- request-to-result durability

Does **not** own:

- event creation
- domain truth
- persistence of accepted event history itself
- projection-state progress

### 3. Projection Store Boundary

Owns:

- materialized read-side state
- current projected version / derived state persistence

Does **not** own:

- accepted history truth
- checkpoint progression metadata
- projection worker orchestration
- state-level semantic validation itself

### 4. Checkpoint Store Boundary

Owns:

- projection progress position
- restart continuation metadata
- durable record of what the projection worker has processed

Does **not** own:

- business state meaning
- materialized read-side state itself
- event truth validation
- projection-runtime control flow

---

## Why Projection State and Checkpoint Must Remain Separate

Projection state and checkpoint are related, but they are not the same.

### Projection State answers:

- what derived state currently exists?

### Checkpoint answers:

- up to what position has processing progressed?

If those are collapsed into one ambiguous structure, the system loses clarity around restart, rebuild, and correctness debugging.

This separation should be preserved even in the durable world.

---

## Why Event History and Idempotency Must Remain Separate

Accepted history and idempotency are also related, but they solve different problems.

### Accepted history answers:

- what facts have been admitted into the system?

### Idempotency answers:

- how should repeated external requests be classified?

If those are collapsed, retry safety and source-of-truth semantics become harder to reason about.

This separation must remain intact in the durable world.

---

## Transactional Consistency Without Boundary Collapse

It is correct to consider transactional consistency across related persistence updates.

However, the existence of one DB transaction does **not** mean the underlying semantic boundaries should be merged.

For example:

- event append and idempotency persistence may need coordinated durability
- projection-state update and checkpoint update may need coordinated durability

But that does **not** mean:

- event store and idempotency store become the same boundary
- projection store and checkpoint store become the same boundary

This distinction matters greatly.

---

## Durable World Reading Rule

When persistent storage is introduced, always ask two questions separately:

### Question 1

What semantic boundary does this record belong to?

### Question 2

What transactional consistency does this record require?

If those two questions are confused, the system may become mechanically consistent but semantically blurred.

---

## Current Practical Rule

At the current stage, persistence should be introduced with the following discipline:

- first make write-side accepted-history and idempotency durable
- then make read-side projection-state and checkpoint durable
- then validate replay / rebuild equivalence
- only later introduce advanced runtime concerns

This is the safest order because it preserves the project’s causal dependency:

```text
accepted history
→ projection runtime
→ derived state
→ later semantic runtime validation
```

---

## What Persistence Must Not Accidentally Become

Persistence must not accidentally become:

- a place where business truth is redefined
- a place where runtime orchestration is hidden
- a place where validation decisions are silently embedded
- a place where restart semantics are assumed rather than made explicit

If that happens, debugging becomes much harder and architectural boundaries become misleading.

---

## Summary

Persistent storage is necessary for the next stage of the project, but it should be introduced as durable preservation of already-defined boundaries, not as a redesign of those boundaries.

In short:

- durable does not mean merged
- transactional does not mean semantically collapsed
- storage consistency must strengthen meaning, not replace it
