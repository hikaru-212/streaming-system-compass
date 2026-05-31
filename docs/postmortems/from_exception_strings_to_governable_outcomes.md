# Postmortem: From Exception Strings to Governable Outcomes

[← Back to Postmortems Index](README.md)

Recorded on: 2026-05-14  
Updated for Stage 4 planning: 2026-05-21

---

## Purpose

This note records a conceptual transition that should later be preserved as part of the project’s Stage 4 evolution.

It explains why the project should not stop at generic failure expressions such as:

```python
raise ValueError("invalid transition")
```

and why the next meaningful step is not only:

```text
structured semantic outcome
```

but also:

```text
structured semantic outcome
→ runtime decision policy
→ runtime decision
→ action safety gate
→ layered trust / governance
```

This note is intentionally written before the corresponding Stage 4 implementation is fully complete.

Its purpose is not to claim that structured semantic outcomes or runtime decision policies already exist in production form.

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
- whether the failure is reversible
- what runtime control decision should follow
- whether the system should continue, retry, rebuild, block, quarantine, or escalate
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

```text
exception strings can interrupt a system,
but they cannot yet govern it.
```

This becomes especially important once the project evolves beyond:

- write-side event rejection
- simple projection mismatch detection

and starts asking:

- what failed semantically?
- how severe is the failure?
- is the failure reversible?
- what evidence proves it?
- what should the runtime do next?
- is it still safe to read?
- is it still safe to act?

At that point, the project needs more than an exception.

It needs a structured failure language.

---

## Why Structured Outcomes Come Before Layered Trust

This is the first sequencing rule.

Layered trust requires inputs that are:

- structured
- comparable
- evidence-carrying
- semantically meaningful
- machine-readable

A generic exception string does not provide that.

Before the system can reason about:

- semantic correctness
- operational freshness
- action safety

it must first be able to express semantic failure in a stable form.

That is why the project must evolve from:

```text
raise ValueError(...)
→ structured semantic outcome
→ runtime decision policy
→ action safety
→ layered trust / governance
```

Without the structured outcome step, later trust reasoning has no stable vocabulary.

If layered trust were built directly on top of raw exceptions, the system would still lack:

- stable failure categories
- explicit evidence
- shared language between Layer 1 and Layer 2
- reusable decision inputs
- a clear distinction between what happened and what should be done

That would make the trust layer fragile and mostly cosmetic.

So the structured semantic outcome is not an optional improvement.

It is the semantic bridge between:

```text
raw implementation failure
→ governance-ready runtime reasoning
```

---

## Why Structured Outcomes Still Need Runtime Decision Policy

A structured semantic outcome is necessary, but it is not the final control boundary.

A semantic outcome explains what happened:

- what failed
- where it failed
- why it matters
- what evidence supports it
- whether the failure is reversible

But the runtime still needs a separate policy layer to decide what to do next.

This separation matters because classification and control are different responsibilities.

A `SemanticOutcome` should describe the semantic meaning of a failure.

A `RuntimeDecisionPolicy` should convert that meaning into an executable runtime control decision.

A `RuntimeDecision` should carry the final control action.

An `ActionSafetyGate` should enforce that decision before an irreversible or externally visible action is executed.

The intended evolution is therefore:

```text
raise ValueError(...)
→ structured semantic outcome
→ runtime decision policy
→ runtime decision
→ action safety gate
→ layered trust / governance
```

This is especially important near irreversible boundaries.

For example:

```text
invalid candidate event before event-log append
→ SemanticOutcome(DOMAIN_TRANSITION_VIOLATION)
→ RuntimeDecision(BLOCK)
→ event never enters accepted history
```

Or:

```text
projection drift before downstream action
→ SemanticOutcome(SEMANTIC_PROJECTION_DRIFT)
→ RuntimeDecision(REBUILD or QUARANTINE)
→ downstream action is blocked until state is trustworthy
```

This means the structured error model is not merely an observability improvement.

It is the input language for runtime control.

The project should therefore treat Stage 4 not only as structured error modeling, but as the transition toward semantic runtime control:

```text
detect
→ classify
→ decide
→ control
```

---

## Error Model Is Not Just Logging

The error model should not be treated as a passive reporting layer.

It should not only answer:

```text
What went wrong?
```

It must eventually support:

```text
What should the runtime do now?
```

This matters because some failures occur near irreversible boundaries.

In those cases, the system must not wait until after execution to classify the failure.

It must block before the irreversible operation happens.

Examples of irreversible or high-risk boundaries include:

- appending accepted history
- recording idempotency success
- marking projection state as trusted
- emitting downstream signals
- exporting data externally
- triggering settlement-style reports
- calling external systems with side effects

The project already contains this pattern in Compass Layer 1.

Layer 1 blocks invalid candidate events before they enter the accepted event log.

Stage 4 generalizes this idea:

```text
invalid semantic condition
→ structured outcome
→ runtime decision
→ block before unsafe execution
```

This is the same core principle applied to a wider runtime boundary.

---

## Relationship to Compass Layer 1

Compass Layer 1 already proves the core idea.

In the write-side flow:

```text
candidate event
→ Layer 1 transition validation
→ ALLOW / BLOCK
→ only ALLOW reaches EventStore
```

An invalid transition such as:

```text
INIT → PAID
```

must be blocked before it becomes accepted history.

This is already a runtime control pattern, even if the current implementation still uses a thinner validation result / enforcement action structure.

Stage 4 should preserve this principle and make it more explicit:

```text
SemanticOutcome
→ RuntimeDecisionPolicy
→ RuntimeDecision
→ ActionSafetyGate
```

The goal is not to replace Layer 1’s meaning.

The goal is to align Layer 1 and Layer 2 around a common outcome-and-decision flow.

---

## Relationship to Compass Layer 2

Layer 1 protects accepted history.

Layer 2 protects derived runtime state.

Even if accepted history is clean, read-side truth can still fail.

For example:

```text
accepted history replay result: PAID
persisted projection state: CREATED
```

This is not a write-side transition violation.

It is a read-side semantic drift.

Layer 2 should detect this by comparing:

```text
replayed expected state
vs
persisted projection state
```

The result should not remain a raw mismatch string.

It should become a structured semantic outcome:

```python
SemanticOutcome(
    error_type="SEMANTIC_PROJECTION_DRIFT",
    layer="LAYER_2_READ_SIDE",
    evidence={
        "expected_state": "...",
        "actual_state": "...",
    },
)
```

Then a runtime decision policy can decide whether to:

- rebuild the projection
- quarantine the derived state
- block dependent actions
- escalate for investigation

This turns projection validation from a debugging tool into a runtime safety mechanism.

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

```text
semantic failures must first be expressed as structured outcomes.
```

This postmortem records why that dependency exists.

Without structured semantic outcomes, layered trust would have no stable failure vocabulary to consume.

Without runtime decision policy, structured outcomes would still be closer to reports than control mechanisms.

So this note serves as the reasoning bridge between:

```text
ad hoc exception / validation failure
→ structured semantic outcome
→ runtime decision policy
→ action safety gate
→ layered trust verdict
```

---

## Why This Matters for Agents

This transition is also important beyond the current streaming domain.

A raw exception string is understandable mainly to the engineer who wrote the code.

A structured semantic outcome is more powerful because it can become readable to:

- the validation layer
- the governance layer
- future trust evaluators
- downstream automation
- eventually agents

But for agents, structured outcomes alone are not enough.

An agent-facing runtime also needs a policy boundary that can decide:

- continue
- retry
- block
- stop
- escalate
- require approval

This does not mean the current project is already a general agent framework.

It means the current domain-specific runtime is the first concrete proving ground for that future direction.

In this sense:

```text
the domain-specific semantic outcome and decision policy
are not the final abstraction,
but they are the first executable bridge toward one.
```

---

## Why This Transition Fits the Project’s Core Philosophy

The project is not only about making systems run.

It is about making correctness, drift, and failure:

- explicit
- replayable
- testable
- explainable
- governable

That is why the architecture evolves from:

```text
transactional correctness
→ projection correctness
→ structured semantic outcomes
→ runtime decision policy
→ action safety
→ layered trust and governance
```

A plain exception belongs to an earlier stage of engineering maturity.

A structured semantic outcome belongs to a system that is beginning to understand failure as meaning, not just interruption.

A runtime decision policy belongs to a system that can translate failure meaning into control.

This fits the Compass philosophy directly:

- Layer 1 should not only reject invalid candidate events.
- Layer 2 should not only detect projection drift.
- The system should explain those failures in a reusable semantic form.
- The runtime should decide whether action is still safe.
- Unsafe or irreversible actions should be blocked before execution.

Only then can layered trust become meaningful.

---

## Reusable Lesson

The reusable lesson is:

```text
exception
→ local interruption

semantic outcome
→ reusable semantic artifact

runtime decision policy
→ control decision based on semantic meaning

action safety gate
→ enforcement before unsafe execution

layered trust
→ action-safety reasoning across semantic and operational dimensions
```

This means the project should not treat structured error modeling as cosmetic polish.

It is a foundational transition.

It is the point where failure stops being only an implementation detail and starts becoming governance data.

The policy layer is the point where governance data becomes runtime control.

---

## Future Role in the Repository

This note belongs in `docs/postmortems/` because it records a design-learning transition:

- why earlier failure expression was sufficient for local progress
- why it later became insufficient
- why the project needed structured outcomes before layered trust
- why structured outcomes still need runtime decision policy
- why this transition is the real starting point for future agent-facing governance ideas

It is not an ADR because it does not finalize the exact API shape of the structured semantic outcome, runtime decision policy, or action safety gate.

It is not an implementation guide because the concrete outcome types and policy rules still belong to a later Stage 4 implementation.

It is a postmortem because it preserves the corrected architectural model:

```text
raw exception strings are enough to interrupt execution,
but not enough to support semantic runtime governance.
```

---

## Future ADR Boundary

A later ADR should define the actual Stage 4 decision boundary.

A likely ADR title is:

```text
ADR 0009 — Semantic Outcome and Runtime Decision Policy Boundary
```

That ADR should decide:

- the final `SemanticOutcome` shape
- the relationship between `SemanticOutcome` and `RuntimeDecision`
- the minimal `RuntimeAction` enum
- how Layer 1 and Layer 2 map into the same outcome family
- which actions are blockable before irreversible execution
- which outcomes imply rebuild, quarantine, or escalation
- how this remains domain-specific before any general agent protocol exists

This postmortem only records why that ADR will be necessary.

It does not replace it.

---

## Summary

This note records one key architectural realization:

```text
generic exceptions are enough to stop execution,
but not enough to support semantic governance.
```

The project must evolve from:

```text
raise ValueError(...)
```

to:

```text
structured semantic outcomes
```

and then to:

```text
runtime decision policy
```

before it can legitimately evolve into:

- action safety
- layered trust
- future agent-facing governance

The structured error model is therefore not just a better error format.

It is the first machine-readable semantic contract of failure.

The runtime decision policy is the next boundary.

It gives that semantic contract operational authority:

- `ALLOW`
- `BLOCK`
- `REBUILD`
- `ESCALATE`
- `QUARANTINE`

This is the transition from:

```text
failure as interruption
```

to:

```text
failure as governable runtime signal
```
