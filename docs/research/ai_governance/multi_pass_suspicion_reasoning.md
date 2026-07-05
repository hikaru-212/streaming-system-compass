# Multi-pass Suspicion Reasoning

[← Back to AI Governance Index](README.md)

**Recorded on:** 2026-06-23

A candidate-answer validation pipeline for AI-assisted judgment.

---

## Research Status

Exploratory note.

This document records a possible future method for AI answer governance and agent reasoning validation. It is not an implemented Compass feature, an ADR, or a Stage 4 commitment.

The purpose is to preserve a reusable review pattern:

```text
candidate answer
→ fit review
→ suspicion review
→ execution reality review
→ evidence / trust review
→ revised accepted answer
```

The goal is not to expose hidden chain of thought.

The goal is to make review responsibility explicit, externalized, and auditable.

---

## Problem Context

A single-pass LLM answer often optimizes for surface coherence.

When a question contains many familiar keywords, the model may quickly produce a plausible match:

```text
keyword overlap
→ surface fit
→ confident recommendation
```

This can be useful, but it is not enough for judgment-heavy decisions.

A first answer may miss:

- internal contradictions
- delivery realism problems
- evidence gaps
- broken trust signals
- buzzword stacking
- prototype-vs-production ambiguity
- role-boundary confusion
- hidden cost and maintenance trade-offs

The problem is not that the first answer is always wrong.

The problem is that a fluent first answer may become treated as an accepted conclusion before it has been reviewed.

Compass-style framing:

```text
candidate answer ≠ accepted answer
```

---

## Triggering Example

The motivating example was an AI Data Engineer / AI data infrastructure role.

At first glance, the role appeared highly related to the Streaming System + Compass project because the job description mentioned:

- data pipelines
- data models
- semantic layer
- context layer
- AI agent data backend
- data quality
- governance
- observability
- AI workflows
- product-builder mindset
- first-principles engineering

A first-pass answer could reasonably conclude:

```text
This role looks highly aligned with the user's Compass project.
```

That conclusion is not necessarily false.

However, it is incomplete.

A later review noticed several suspicious signals:

- the job description asked candidates to read a required company document before the interview
- the linked document returned a 404
- the role combined many difficult domains into one position
- the role mentioned very fast AI pipeline delivery
- the boundary between prototype, production pipeline, AI agent backend, semantic layer, ML pipeline, and product engineering was unclear

The corrected judgment was not simply:

```text
This role is good.
```

or:

```text
This role is bad.
```

The more mature conclusion was:

```text
The problem space is relevant, but the role and company signals require suspicion.
The opportunity may be worth exploring, but the interview should be used to validate engineering culture, delivery expectations, and role boundaries.
```

The important lesson is that the suspicious signals should ideally be surfaced by the review process itself, not only after the user points them out.

---

## Core Insight

A single-pass LLM tends to answer:

```text
What does this look like?
```

A multi-pass review should also ask:

```text
Is this really trustworthy?
```

The first-pass answer may detect semantic similarity.

The later passes should examine whether that similarity survives:

- skepticism
- execution reality
- evidence review
- trust-signal review
- final decision synthesis

This is the answer-level version of the Compass principle:

```text
candidate output must not become accepted truth by default
```

---

## Externalized Suspicion Notes

This method does not require exposing hidden chain of thought.

Instead, it produces explicit review notes.

The review notes should be:

- visible
- structured
- bounded by responsibility
- auditable
- easy to challenge
- easy to revise

Example structure:

```text
Round 1 — Initial fit
Round 2 — Suspicion note
Round 3 — Execution reality note
Round 4 — Evidence / trust note
Round 5 — Revised accepted answer
```

The goal is to preserve the useful effect of human-like suspicion:

```text
Wait, this answer feels too smooth.
What might be missing?
```

but express it as an external review artifact rather than hidden reasoning.

---

## Proposed Multi-pass Review Architecture

This is not five identical retries.

Each pass has a different responsibility.

---

## Round 1 — Fit Analyst

### Question

Does the opportunity, claim, design, or answer appear to match the user, project, or goal?

### Output

- surface match points
- visible strengths
- likely alignment
- initial conclusion

### Known Risk

This pass is likely to be too optimistic.

It may over-weight:

- keyword similarity
- role title similarity
- impressive vocabulary
- surface-level problem alignment

---

## Round 2 — Suspicion Validator

### Question

Is the first answer too smooth?

Does the answer rely on surface semantic matching while ignoring structural tension?

### Output

- suspicion notes
- strange signals
- buzzword stacking risk
- boundary ambiguity
- inflated claims
- scope overload

### Typical Observation

```text
The terms are individually reasonable, but the combination may be too broad for one role or one implementation stage.
```

---

## Round 3 — Execution Reality Validator

### Question

Are the delivery expectations realistic?

Does the stated requirement match engineering reality?

Is the claim about a prototype, a demo, or a production-ready system?

### Output

- execution risk
- delivery mismatch
- prototype-vs-production distinction
- maintenance-cost concerns
- role-depth concerns

### Typical Observation

```text
One-day delivery may be reasonable for a prototype or spike.
It is not reasonable if the expectation is a production-grade AI pipeline with reliability, governance, monitoring, and semantic correctness guarantees.
```

---

## Round 4 — Evidence / Trust Validator

### Question

What evidence supports or weakens the first-pass conclusion?

Are there public signals, broken links, missing documents, runtime evidence gaps, or internal inconsistencies?

### Output

- evidence gaps
- trust signals
- broken-link concerns
- missing support
- mismatch between claim and behavior
- follow-up questions

### Typical Observation

```text
A broken link is not automatically fatal.
However, if the job description itself asks candidates to read that document before interview, a 404 on that link becomes a candidate-facing trust signal.
```

---

## Round 5 — Decision Synthesizer

### Question

How should the original conclusion be revised after all review passes?

### Output

- final judgment
- revised conclusion
- action recommendation
- risk summary
- what to verify next

### Example Conclusion

```text
The role's problem space is aligned with the user's project.
However, the job description has boundary and trust-signal risks.
It may be worth applying, but the user should treat the interview as a reverse-evaluation process and validate engineering culture, production expectations, and ownership boundaries.
```

---

## Candidate Answer Validation Pipeline

The method can be summarized as:

```text
Candidate Answer
→ Fit Review
→ Suspicion Review
→ Execution Reality Review
→ Evidence / Trust Review
→ Revised Accepted Answer
```

This turns a vague instruction like:

```text
think again
```

into explicit validators.

The system does not merely ask the model to produce more text.

It asks the model to review the candidate answer under different semantic responsibilities.

---

## Relationship to Compass

Original Compass:

```text
candidate event
→ semantic validation
→ accepted history
```

Answer governance extension:

```text
candidate answer
→ multi-pass semantic review
→ accepted answer
```

The analogy is not exact, but the pattern is useful.

In the runtime system, Compass protects accepted history from invalid candidate events.

In AI-assisted reasoning, a multi-pass review can protect accepted conclusions from first-pass fluency, keyword matching, or unsupported confidence.

The shared principle is:

```text
technical or linguistic success does not automatically imply semantic correctness
```

---

## Prompt Template

```text
Please do not give me only a single-pass answer.
Use Multi-pass Suspicion Reasoning.

Your task is not to reveal hidden chain of thought.
Your task is to produce explicit, reviewable notes across multiple review responsibilities.

Use five rounds:

Round 1 — Fit / Initial Answer
Give an initial judgment based on the surface information.

Round 2 — Suspicion Validator
Check whether the first answer is too smooth, too keyword-driven, or hiding buzzword stacking, boundary ambiguity, or surface semantic matching.

Round 3 — Execution Reality Validator
Check delivery expectations, timeline, responsibility scope, and engineering realism. Distinguish prototype from production-ready system.

Round 4 — Evidence / Trust Validator
Check external evidence, runtime evidence, broken links, missing documents, inconsistent claims, and trust-signal gaps.

Round 5 — Revised Accepted Answer
Synthesize the earlier rounds into a revised conclusion, risks, next actions, and questions that should be verified.

For each round, include:

- observations
- doubts or risks found in that round
- how this modifies the original conclusion
```

---

## Future Use

This note may be useful for future work around:

- AI answer governance
- agent reasoning validation
- interview / opportunity evaluation
- AI-assisted architecture review
- candidate-output admission
- Stage 4 / Stage 5 concept exploration
- Compass-style validation of generated artifacts

It should not be treated as an implemented runtime feature.

---

## Summary

The goal is not to make AI produce more text.

The goal is to make an initial answer pass through multiple explicit semantic validators before it becomes an accepted conclusion.

Core principle:

```text
From "this looks reasonable"
to
"is this actually trustworthy?"
```

Or shorter:

```text
A candidate answer is not an accepted answer.
```
