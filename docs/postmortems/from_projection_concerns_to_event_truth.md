# From Projection Concerns to Event Truth

[← Back to Postmortems Index](README.md)

**Recorded on:** 2026-05-01

## Purpose

This note records an important design evolution in the project:

the shift from focusing primarily on projection/runtime problems
to recognizing that event-source correctness had to be treated as an earlier and more foundational problem.

This was not a minor change in implementation detail.

It changed:

- what the project treated as the first line of defense
- how Compass evolved
- how accepted history was understood
- why write-side validation became unavoidable before read-side verification could be trusted

---

## Original Starting Point

At the beginning, the mental model of the system was relatively simple:

```text
event store -> projection -> state
```

At that stage, the event store was not taken especially seriously as an architectural problem.

It was understood mostly as:

- the place where events are stored
- the source from which projection reads
- the durable history used for replay

Because of that, the first major area of attention became projection.

The early concerns were things such as:

- out-of-order events
- retries
- replay correctness
- state rebuild
- checkpoint progression
- DLQ, watermark, and other stream-processing concepts
- how projected state can drift or become inconsistent

For roughly the first stage of the project, the main intuition was:

> if the system is going to fail, it will probably fail at the projection/runtime side

That made the first Compass intuition naturally read-side oriented.

---

## What Was Underestimated

What was underestimated at that stage was the event store itself.

More precisely:

the event store was recognized as important for durability and replay,
but the semantic quality of the events entering it was not yet treated as the primary architectural problem.

The event store was seen as a place that receives events.

It was not yet seen clearly enough as:

> the place where the system formally accepts history

That distinction turned out to matter a lot.

Because if the event store is only seen as “where events are stored,”
then the main question becomes:

- how should later consumers handle whatever is already there?

But if the event store is seen as “accepted history,”
then a more demanding question appears:

- what gives the system the right to accept this event as part of history at all?

That question was not clear enough at the beginning.

---

## The Turning Point

The turning point came when the project stopped being only an abstract streaming idea
and started moving toward an actual end-to-end implementation.

At that point, a basic question became unavoidable:

> Where do my events actually come from?

This mattered because the project was not inheriting events from a real production transaction system.

There was no existing upstream payment platform, order system, or external stream to consume.

That meant the project could not hide behind a pre-existing event source.

It had to answer for itself:

- how are events created?
- why should those events be trusted?
- how do I know the generated event is meaningful?
- how do I know it is lawful?
- how do I stop garbage events from becoming formal system history?

At that point, the earlier projection-first emphasis started to look incomplete.

Even if projection could defend itself well against:

- replay bugs
- checkpoint bugs
- out-of-order delivery
- read-side inconsistency

there was still a deeper unresolved problem:

> what if the event itself should never have entered accepted history in the first place?

That question moved the architectural center of gravity upstream.

---

## Why Projection Was No Longer Enough

Projection problems are real.

They remain important.

But projection only begins **after** accepted history already exists.

That means projection can help answer questions like:

- is the read-side state still coherent?
- is replay equal to incremental reduction?
- is runtime derivation stable under restart?

But projection cannot fully solve an earlier problem:

- should this event have been admitted into accepted history at all?

If that question is ignored, then the system risks becoming very good at one thing:

> carefully projecting garbage.

That realization changed the project.

The issue was no longer only:

- how to defend runtime state

It became:

- how to defend accepted history itself

And once that became the real question,
the event source could no longer be treated as a casual input generator.

---

## Single-Machine First, Before Distributed Reality

An important part of this evolution was a deliberate refusal to hide behind “real-world systems do X” too early.

The project first asked a stricter question:

> In the simplest single-machine world, how do I guarantee that each generated event is already meaningful and lawful before it is accepted?

This mattered because distributed reality often introduces many later-stage concerns:

- retries
- replication
- offsets
- partitions
- late delivery
- consumer restarts

Those are important,
but they can also obscure the more basic semantic issue.

So the project first narrowed the problem down:

- ignore the distributed excuse for a moment
- forget how large production systems currently tolerate or repair bad inputs
- ask what it would mean to make the event semantically sound at the source

That move was important.

Because it changed the project from:

- “how do I process events robustly?”

to:

- “how do I make event entry itself defensible?”

Only after that single-machine semantic question became clear
did it make sense to later expand back outward toward distributed runtime concerns.

---

## The Role of Proof-Carrying Events

This shift became much sharper once proof-carrying event ideas entered the design.

Before that, an event could still be imagined mostly as a payload:

- order_id
- event_type
- amount
- sequence

But once the event also carried claims such as:

- previous status
- previous version
- predecessor identity

the event was no longer just data.

It became a semantic statement about history.

At that point, the project had to confront a stronger question:

> if an event is making a claim about prior truth, who checks that claim before the event becomes accepted history?

That question directly led to the need for write-side transition-truth validation.

This is where the project stopped seeing Compass only as a runtime state checker.

It became clear that there were two different correctness problems:

1. event-entry truth
2. post-derivation runtime correctness

That realization later became the basis for the two-layer Compass architecture.

---

## What Changed After This Realization

Once source correctness became central, several design directions changed.

### 1. Event generation became a first-class problem

The project no longer treated event creation as a trivial precursor to the “real” streaming work.

Instead, event generation became part of the correctness boundary.

### 2. Accepted history gained stronger meaning

The event store stopped being treated merely as a storage location.

It became:

- the formal accepted history of the system
- something that should not casually admit semantically false events

### 3. Projection became secondary in temporal order

Projection remained important,
but it was no longer seen as the first correctness boundary.

It became the second major layer:

- after accepted history already exists

### 4. Compass evolved

Compass stopped being only a state/runtime verification idea.

It became two-layered:

- Layer 1: defend accepted history entry
- Layer 2: defend derived runtime state

---

## What This Taught the Project

This design evolution taught a reusable lesson:

> not all streaming correctness problems begin at the consumer side

Many discussions of streaming systems begin from:

- how to consume safely
- how to checkpoint correctly
- how to handle disorder
- how to rebuild state

Those are real problems.

But they are not the only problems.

Sometimes the more foundational issue is:

- whether the system should have accepted the event at all

That is a different kind of correctness question.

It belongs earlier in time.
It is closer to event creation, event meaning, and event admission.

And once that question becomes visible,
the whole architecture shifts.

---

## Why This Matters Beyond This Project

This was not just a private learning moment.

It has broader architectural importance.

Because many systems are designed as if there are only two layers:

1. event ingestion
2. downstream processing

But this project discovered the need to distinguish at least three semantic moments:

1. **event generation and truth claim**
2. **accepted-history admission**
3. **runtime state derivation**

That middle distinction matters.

Without it, a system may collapse source truth and downstream repair into one vague process.

With it, the system can ask more precise questions:

- what makes an event admissible?
- what makes accepted history trustworthy?
- what makes derived state correct?

Those should not all be treated as the same problem.

---

## Final Summary

This project originally began by focusing on projection/runtime problems:

- replay
- checkpoints
- out-of-order handling
- state rebuild
- drift after derivation

But as implementation became concrete, a deeper issue emerged:

- the event store is not just where events are stored
- it is where the system accepts history
- therefore event-entry correctness matters before projection correctness

That shift changed the architecture.

It led from a projection-first correctness mindset
to a stronger source-truth-first mindset.

In short:

```text
first concern:
event store -> projection -> state verification

later realization:
event generation -> event truth -> accepted history -> projection -> runtime state verification
```

That change is one of the most important conceptual evolutions in the project.
