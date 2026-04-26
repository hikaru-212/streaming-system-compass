# Decision Note: Why Transition Correctness Came Before Full Domain Invariants

[← Back to Domains Index](README.md)

## Purpose

This note explains an intentional design decision made during the early phase of the project:

- first stabilize transition correctness
- then tighten domain business invariants during write-side implementation

This decision should not be interpreted as "domain semantics were unimportant."
Instead, it reflects a staged narrowing of the design space.

---

## Background

In the early design phase, the project focused heavily on:

- state-machine legality
- predecessor proof structure
- sequence progression
- transition truth against prior history
- Compass Layer 1 correctness

At that stage, the main question was:

> can the system determine whether a candidate event truthfully follows the state it claims to follow?

This led to a strong emphasis on transition correctness.

Examples of that focus included:

- `prev_event_id`
- `prev_version`
- `prev_status`
- sequence continuity
- stale candidate detection

---

## Why This Priority Was Reasonable

This priority was intentional and valid.

Before checking whether a business value is meaningful, the system first needed to establish:

- what counts as a legal predecessor
- how version progression works
- how proof claims are compared against accepted history
- how a candidate event becomes semantically admissible

Without this layer, later business checks would be built on an unstable transition model.

In that sense, the early phase prioritized the **continuity of the transition system**.

---

## What Was Deferred

What was not fully tightened at first was a different class of correctness:

- amount reasonableness
- business payload legality
- semantic alignment between event type and numeric content
- stricter request-boundary semantics for retry versus new request handling
- payload-consistency requirements for safe idempotent replay
- the exact business meaning of `PAID`

These are not merely transition questions.
They belong to **domain legality and request-boundary semantics**.

---

## Why This Gap Became Visible Later

Once the design moved from abstract transition validation into actual write-side implementation,
it became clear that transition correctness alone is not enough.

A candidate event may be:

- sequentially valid
- predecessor-consistent
- proof-consistent

and still be business-illegal.

For example:

- `CREATED(amount=-100)`
- `PAID(amount=-100)`
- `PAID(amount != total_amount)` in a full-payment model

This means:

> transition correctness is necessary, but not sufficient.

---

## Current Interpretation

The current interpretation is now:

### Layer A — Command / Domain Legality
Handled by the aggregate / domain rules.

This includes:
- whether the command is business-valid
- whether the amount is reasonable
- whether the event payload matches the intended business meaning

### Layer B — Transition Truth
Handled by Compass Layer 1.

This includes:
- whether the candidate event truthfully follows actual prior history
- whether proof claims match predecessor truth
- whether the candidate has become stale

### Layer C — Admission Continuity
Handled by the admission gate / persistence boundary.

This includes:
- optimistic version match
- append-time continuity

### Layer D — Request Retry Safety
Handled by idempotency / orchestration boundary.

This includes:
- replay of prior accepted result for the same request
- payload-consistency checks for safe replay

---

## Decision

The project now explicitly records the following:

1. The early emphasis on transition correctness was intentional and valid.
2. That emphasis does not remove the need for domain business invariants.
3. As soon as the write-side model becomes executable, domain legality must be tightened.
4. Therefore, the next step is not to replace transition validation, but to complement it with explicit domain rules.

---

## Consequence

This means the write-side model must now include both:

- transition-system correctness
- domain-payload correctness

The system should not accept an event merely because it is structurally aligned with prior history.

It must also be business-legitimate.

---

## Summary

The early design intentionally focused on transition correctness first.

That was not a mistake.

However, once the project moved toward a real write-side semantic loop, it became necessary to add explicit domain invariants and business legality rules.

So the evolution is:

- first, prove transition alignment
- then, tighten domain legality
- then, combine both inside the write-side semantic boundary