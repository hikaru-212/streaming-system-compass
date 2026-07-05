# From Generated Language to Source-Grounded Semantic Admission

[← Back to AI Governance Index](README.md)

**Recorded on:** 2026-06-23

## Research Status

Public conceptual note.

This document records a research direction for AI governance within the broader Streaming System + Compass project. It is not an implementation specification, an ADR, a validator contract, a schema definition, or a Stage 4 commitment.

The purpose is to preserve a public version of the idea:

```text
generated language
→ candidate semantic artifact
→ source-grounded review
→ semantic admission decision
```

The core principle is:

```text
generated text is not automatically grounded truth
```

---

## Problem Context

AI systems can generate summaries, explanations, reports, recommendations, and decision-support text from large collections of source material.

That output may sound fluent and useful, but fluency does not prove that the generated language is faithful to the sources.

A generated overview may:

- combine unsupported claims with supported ones
- overstate weak evidence
- omit important uncertainty
- collapse conflicting sources into one clean narrative
- preserve stale information
- introduce claims that were never present in the source material
- present inference as fact

The governance problem is not only whether the model can generate useful language.

The deeper question is:

```text
When should generated language be allowed to become a trusted semantic artifact?
```

---

## Core Distinction

This note separates two things:

```text
generated language
```

and:

```text
source-grounded semantic artifact
```

A model can produce language before the system has enough evidence to trust that language.

In Compass terms, the generated output is still a candidate.

It may be useful, but it should not automatically become accepted semantic context.

---

## Why Source Grounding Matters

A generated answer may be technically well-formed while still being semantically unsafe.

For example, a generated overview may correctly summarize some parts of the available evidence while silently adding an unsupported conclusion.

That creates a dangerous middle state:

```text
partially grounded
but presented as fully reliable
```

This is especially important for enterprise AI systems because generated summaries may influence:

- business decisions
- operational workflows
- analytics interpretation
- customer communication
- compliance review
- future retrieval context
- downstream agent actions

Once a generated artifact is reused by other systems, it may stop being treated as a temporary answer and start functioning as durable context.

That is why source grounding should be treated as an admission problem, not only a generation-quality problem.

---

## Public Conceptual Flow

A safer system may use a flow like this:

```text
source material
→ generated candidate overview
→ source-grounded review
→ semantic admission result
→ allowed / revised / blocked / escalated output
```

The exact implementation may vary.

The important boundary is that the generated artifact is not treated as accepted truth until it has been reviewed against source evidence and risk context.

---

## Possible Review Questions

A source-grounded admission process may ask questions such as:

- Which parts of the generated output are directly supported by the source material?
- Which parts are inferred rather than explicitly stated?
- Are there source conflicts that the output hides?
- Does the output present uncertainty as certainty?
- Is the output stale relative to newer source material?
- Does the output make high-impact claims that require stronger evidence?
- Does the output depend on source material that is incomplete, outdated, or scoped to the wrong context?
- Should the output be shown, revised, retried, blocked, or sent to human review?

This list is intentionally conceptual.

It does not define the final validator algorithm, policy table, data model, or runtime contract.

---

## Relationship to Compass

The existing Compass project focuses on protecting accepted history and validating candidate events before they become durable truth.

This research direction extends the same principle to generated language:

```text
candidate event
→ admission boundary
→ accepted history
```

becomes:

```text
candidate generated artifact
→ source-grounded review
→ accepted semantic artifact
```

The shared rule is:

```text
candidate output must not become system truth by default
```

---

## Example: Generated Overview Risk

Suppose an AI system generates a short overview from multiple documents.

Some statements may be directly supported.
Some statements may be weakly implied.
Some statements may be unsupported.
Some statements may depend on documents that are stale or scoped to a specific team.

A public-facing system should not treat the whole overview as equally trusted simply because it reads well.

A safer design would preserve the distinction between:

```text
what the model generated
```

and:

```text
what the evidence supports
```

The system may then decide whether the overview can be shown as-is, revised with clearer uncertainty, retried with stricter grounding, blocked, or escalated for review.

---

## Non-goals

This public note intentionally does not define:

- final claim schemas
- verifier internals
- source scoring algorithms
- policy tables
- admission status enums
- cache metadata
- runtime enforcement contracts
- implementation-specific data structures
- production verification architecture

Those details should remain private research or future implementation work until the project intentionally chooses to publish them.

---

## Key Principle

Generated language can be useful before it is trustworthy.

The system should therefore distinguish:

```text
candidate generated output
```

from:

```text
source-grounded accepted semantic artifact
```

The goal is not to eliminate generation.

The goal is to prevent unsupported or weakly grounded generated language from silently becoming trusted context.
