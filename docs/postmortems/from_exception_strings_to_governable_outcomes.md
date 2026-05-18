# Postmortem: From Exception Strings to Governable Outcomes

[← Back to Postmortems Index](README.md)

**Recorded on:** 2026-05-14

## Purpose

This note records a conceptual transition that should later be preserved as part of the project’s Stage 4 evolution.

It explains why the project should not stop at generic failure expressions such as:

```python
raise ValueError("invalid transition")
```

and why the next meaningful step is:

```text
structured semantic error outcome
```

before the project can evolve further into:

```text
layered trust
action safety
governance-ready decisions
```

This note is intentionally written before the corresponding implementation is fully complete.

Its purpose is not to claim that structured error outcomes already exist in production form.

Its purpose is to preserve the architectural reasoning for why they must become the bridge between raw validation failures and later trust / action-safety decisions.

---

## The Original Limitation

In earlier project stages, failure was often represented through:

- exception strings
- boolean validation results
- simple pass / fail indicators
- ad hoc rejection reasons

These forms were enough for local implementation progress.

They were useful for:

- proving that an invalid transition was blocked
- proving that a replay mismatch existed
- asserting that validation logic worked in tests
- making failure visible to the developer

But they were not yet enough to support the deeper project direction.

They could tell a human engineer that something failed.

They could not yet tell the system:

- what kind of semantic failure occurred
- what evidence supports that conclusion
- what governance meaning that failure carries
- what action should be taken next
- whether the system is still safe to act on

That is the real limitation of exception-first failure expression.

---

## Why `raise ValueError(...)` Is Not Enough

A plain exception string is too weak for the next stage of the project.

It is:

- human-readable
- local
- implementation-specific
- hard to compare across layers
- hard to consume as a governance signal
- hard to lift into action-safety reasoning

An exception may stop execution, but it does not yet create a reusable semantic artifact.

In other words:

> exception strings can interrupt a system, but they cannot yet govern it.

This becomes especially important once the project evolves beyond:

- write-side event rejection
- simple projection mismatch detection

and starts asking:

- what failed semantically?
- how severe is the failure?
- what evidence proves it?
- what should the system do next?
- is it still safe to read?
- is it still safe to act?

At that point, the project needs more than an exception.

It needs a structured failure language.

---

## Why Error Model Comes Before Layered Trust

This is the most important sequencing rule.

Layered trust requires inputs that are:

- structured
- comparable
- evidence-carrying
- semantically meaningful
- machine-readable

A generic exception string does not provide that.

Before the system can reason about:

- semantic correctness
- operational trust
- action safety

it must first be able to express semantic failure in a stable form.

That is why the project must evolve in this order:

```text
raise ValueError(...)
→ structured semantic error outcome
→ layered trust verdict
→ action safety decision
```

Without the middle step, the final step has no real foundation.

If layered trust were built directly on top of raw exceptions, the system would still lack:

- stable failure categories
- explicit evidence
- reusable governance hints
- a shared vocabulary between Layer 1 and Layer 2

That would make the trust layer fragile and mostly cosmetic.

So the structured error model is not an optional improvement.

It is the semantic bridge between:

```text
raw implementation failure
→ governance-ready system reasoning
```

---

## Why This Matters for Agents

This transition is also important beyond the current streaming domain.

A raw exception string is understandable mainly to the engineer who wrote the code.

A structured error outcome is more powerful because it can become readable to:

- the validation layer
- the governance layer
- future trust evaluators
- downstream automation
- and eventually agents

That makes the structured error model the first serious step from:

```text
human debugging
→ machine-consumable semantic governance
```

This does not mean the current project is already a general agent framework.

It means the current domain-specific error model is the first concrete proving ground for that future direction.

In this sense:

> the domain-specific error model is not the final abstraction,
> but it is the first executable bridge toward one.

---

## Why This Transition Fits the Project’s Core Philosophy

The project is not only about making systems run.

It is about making correctness, drift, and failure:

- explicit
- replayable
- testable
- explainable
- governable

That is why the architecture already evolved from:

```text
transactional correctness
→ projection correctness
→ structured error outcomes
→ layered trust and action safety
```

A plain exception belongs to an earlier stage of engineering maturity.

A structured error outcome belongs to a system that is beginning to understand failure as meaning, not just interruption.

This fits the Compass philosophy directly:

- Layer 1 should not only reject invalid candidate events
- Layer 2 should not only detect projection drift
- the system should begin to explain those failures in a reusable semantic form

Only then can layered trust become a meaningful next step.

---

## Relationship to ADR 0007

ADR 0007 separates semantic correctness from operational trust.

That ADR establishes that the system eventually needs more than a single trusted / untrusted verdict.

It needs to distinguish questions such as:

- Is the fact semantically valid?
- Is accepted history clean?
- Is projected state faithful to accepted history?
- Is the current operational view fresh and healthy?
- Is it safe for a downstream service, operator, or agent to act?

However, ADR 0007 depends on a prior capability:

> semantic failures must first be expressed as structured outcomes.

This postmortem records why that dependency exists.

Without structured semantic outcomes, layered trust would have no stable failure vocabulary to consume.

So this note serves as the reasoning bridge between:

```text
ad hoc exception / validation failure
→ structured semantic outcome
→ layered trust verdict
→ action safety decision
```

---

## Reusable Lesson

The reusable lesson is:

```text
exception
→ local interruption

error model
→ reusable semantic artifact

layered trust
→ action-safety reasoning built on those artifacts
```

This means the project should not treat structured error modeling as cosmetic polish.

It is a foundational transition.

It is the point where failure stops being only an implementation detail and starts becoming governance data.

---

## Future Role in the Repository

This note belongs in `docs/postmortems/` because it records a design-learning transition:

- why earlier failure expression was sufficient for local progress
- why it later became insufficient
- why the project needed structured outcomes before layered trust
- why this transition is the real starting point for future agent-facing governance ideas

It is not an ADR because it does not finalize the exact API shape of the structured error model.

It is not an implementation guide because the concrete outcome types still belong to a later Stage 4 implementation.

It is a postmortem because it preserves the corrected architectural model:

```text
raw exception strings are enough to interrupt execution,
but not enough to support semantic governance.
```

---

## Summary

This note records one key architectural realization:

> generic exceptions are enough to stop execution,
> but not enough to support semantic governance.

That is why the project must evolve from:

```text
raise ValueError(...)
```

to:

```text
structured semantic outcomes
```

before it can legitimately evolve into:

```text
layered trust
action safety
future agent-facing governance
```

The structured error model is therefore not just a better error format.

It is the first machine-readable semantic contract of failure.
