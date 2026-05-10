# Postmortem: From In-Memory Correctness to Durable Consistency

[← Back to Postmortems Index](README.md)

**Recorded on:** 2026-05-10

## Purpose

This note records an important design transition in the project:

moving from an in-memory baseline toward a persistence-backed runtime is not a simple storage replacement.

At first, it is tempting to think:

> if the in-memory version already behaves correctly, then persistence is just a matter of swapping the backend.

The project eventually made a more precise distinction:

> in-memory correctness and durable consistency are related, but they are not the same problem.

This note preserves that distinction.

---

## Context

By the time this transition became clear, the repository already had:

- a transactional write-side semantic baseline
- accepted-history replay
- idempotency replay / conflict distinction
- Compass Layer 1 transition-truth validation
- a Stage 3 projection runtime baseline in deterministic in-memory form
- projection-state and checkpoint-store separation
- replay / rebuild through the same projection runtime path

At that point, the next obvious step seemed to be:

- replace in-memory stores with database-backed stores

However, that framing turned out to be incomplete.

---

## The Initial Intuition

The initial intuition was roughly:

- the semantic boundaries are already clear
- the runtime flow already works
- replay / rebuild already works
- therefore persistence is mostly a technical storage concern

Under that intuition, the next step might appear to be:

- take the current event store
- take the current idempotency store
- take the current projection store
- take the current checkpoint store
- replace in-memory dictionaries or objects with PostgreSQL tables

That intuition is understandable, but it hides an important difference between the two worlds.

---

## The Corrected Model

A more precise way to describe the transition is this:

persistent storage does not only mean that state lives longer than process memory.

It also means that many guarantees that felt natural in the in-memory world are no longer free.

In the in-memory baseline, several forms of consistency feel almost built in:

- related state changes happen inside one living process
- multiple updates often share one control flow
- process death removes the whole local world together

Because of that, some guarantees feel almost natural.

But once state is required to survive across time, restart, and partial failure, those guarantees no longer come for free.

That is why durable systems need additional mechanisms—such as transactions, idempotency discipline, and checkpoint consistency—to approximate guarantees that felt almost natural in the in-memory baseline.

The key realization is:

## in-memory systems get some forms of consistency "for free"

while persistence-backed systems do not.

### In the in-memory world

Many related updates happen:

- inside one process
- inside one control flow
- against one immediate runtime view of state

This means that several forms of coordination feel natural:

- state update and checkpoint update feel like one movement
- event append and idempotency record update feel like one flow
- replay and current state coexist in one living process context

When the process dies, the whole memory world disappears together.

That can hide partial-state problems because nothing survives long enough to expose them.

---

### In the durable world

Persistence changes the problem.

Now the system must deal with:

- data surviving process lifetime
- restart seeing only part of a previously attempted update
- multiple persistence records requiring coordinated consistency
- transaction boundaries becoming explicit
- replay trust depending on durable source-of-truth state
- checkpoint trust depending on durable progress state
- semantic interpretation across time, not only within one execution

This means persistence is not merely "save what already exists."

It introduces a new class of questions:

- what survives restart?
- what is the true durable source of truth?
- what if one record is persisted and the other is not?
- how is replay validated against already persisted derived state?
- how do retry semantics survive across process lifetime?

---

## Why In-Memory Can Look Correct While Persistence Can Still Fail

This difference can be summarized in one sentence:

> in-memory correctness is mostly about single-execution consistency, while durable consistency is about cross-time consistency under partial failure.

That is why an in-memory baseline can be correct and still leave major questions unanswered.

### Example: Write-Side

In-memory flow may make the following feel naturally aligned:

- append accepted event
- record idempotency result

But in a persistence-backed world, these may split into separate durable writes.

That introduces real failure possibilities:

- event persisted but idempotency record missing
- idempotency record persisted but event missing

This is not just a storage inconvenience.
It directly affects replay / conflict semantics.

### Example: Read-Side

In-memory projection flow may make the following feel naturally aligned:

- update projected state
- advance checkpoint

But in a persistence-backed world, these can also split into separate durable writes.

That introduces restart ambiguity:

- projected state updated but checkpoint not advanced
- checkpoint advanced but projected state not updated

This is not just an operational edge case.
It directly affects replay trust and rebuild semantics.

---

## The More Precise Engineering Distinction

The transition from in-memory to durable execution introduced a more precise mental model:

### In-Memory Baseline Proves

- semantic boundaries are coherent
- reducer / worker separation is meaningful
- state / checkpoint separation is meaningful
- replay / rebuild logic is executable
- write-side and read-side flows make sense

### Persistent Baseline Must Prove

- those same boundaries remain coherent when state survives restart
- related durable updates remain transactionally consistent
- replay / rebuild equivalence still holds against persisted state
- accepted history remains the true durable source of truth
- idempotency semantics remain correct across process lifetime

So the persistence stage is not just a backend swap.

It is the stage where the architecture is tested against a world in which partial failure leaves traces behind.

---

## Reusable Lesson

A useful engineering rule emerged from this transition:

> never treat durable persistence as a purely mechanical replacement of in-memory state.

Instead, ask two separate questions:

### Question 1

What semantic boundary does this data belong to?

### Question 2

What consistency boundary does this data require?

Those two questions must not be collapsed.

For example:

- event history and idempotency may require coordinated durability
- projection state and checkpoint may require coordinated durability

But that does **not** mean their semantic boundaries should be merged.

---

## Why This Matters for the Project Roadmap

This realization also clarified why the next step after the Stage 3 in-memory baseline should be:

- persistent storage baseline

and **not yet**:

- DLQ
- buffering
- watermarking
- multi-worker coordination

The reason is simple:

without durable baseline semantics, those later runtime features would be built on top of a still-fragile restart and persistence model.

In other words:

- first preserve correctness across time
- then add more runtime complexity

---

## Future Rule

The corrected design rule for the project became:

1. establish in-memory semantic baseline
2. make write-side durability trustworthy
3. make read-side durability trustworthy
4. verify replay / rebuild against durable state
5. only then expand into more advanced runtime concerns

This keeps the project aligned with its main philosophy:

> preserve meaning first, then expand runtime complexity.

---

## Summary

The shift from in-memory to persistence-backed execution is not just a storage upgrade.

It is a shift from:

- correctness within one execution

to:

- correctness that survives time, restart, and partial failure.

That is why this transition deserves to be treated as an architectural learning moment, not only as an implementation detail.

In short:

```text
in-memory correctness
→ semantic boundaries proven inside one runtime

durable consistency
→ those same boundaries must survive time, restart, and partial failure
```
