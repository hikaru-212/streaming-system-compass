# AI Suggestions Are Candidate Actions, Not Accepted Facts

[← Back to Design Philosophy](README.md)

## Purpose

This note records a practical methodology lesson from the project:

```text
AI-generated suggestions are candidate actions.
They are not accepted facts.
```

AI can help produce explanations, designs, documents, and implementation options quickly.

But in this project, an AI-generated answer does not automatically become architecture.

It must still pass the project boundary:

```text
Does this match the actual schema?
Does this match the dependency direction?
Does this preserve the authority model?
Does this introduce a misleading path?
```

Only after that review can the suggestion become accepted project documentation or code.

---

## Core Principle

```text
AI output is a candidate action.
Repository-aligned review is the admission boundary.
Committed design is the accepted fact.
```

This mirrors the project’s runtime model:

```text
candidate event
→ Compass admission
→ accepted history
```

In the development workflow, the same pattern appears as:

```text
candidate explanation
→ human semantic review
→ accepted repository change
```

This is not a decorative metaphor.

It is how the project avoids letting fluent but misaligned explanations become permanent architecture.

---

## Multi-Agent Review Is Useful, But Not Semantic Admission

This project does not follow a single-AI-output acceptance model.

In practice, I often ask one AI to produce a candidate explanation, candidate design, or candidate document, then ask another AI to review it.

Sometimes the second AI finds issues.

Sometimes it confirms the first output.

And sometimes, if the issue looks ordinary enough, I may accept the result directly.

That is part of the practical workflow.

This is close in spirit to modern loop-engineering patterns:

```text
generate
→ review
→ revise
→ test
→ merge
```

That kind of loop can catch many useful classes of problems:

```text
syntax errors
type errors
missing tests
inconsistent naming
obvious contract violations
general architectural concerns
```

But loop completion is not semantic admission.

A multi-agent review loop may still miss project-specific semantic misalignment.

The reason is simple:

```text
a design can be plausible in general
and still be wrong for this repository
```

That is the important failure mode.

The problem is not always that an AI suggestion is obviously wrong.

The more dangerous case is when the suggestion is locally coherent, commonly used, and technically reasonable under a different architectural model.

In that situation, another AI reviewer may also approve it, because the suggestion is not generally absurd.

It is only wrong when checked against the project’s actual schema, dependency direction, and authority model.

This is why multi-agent review can reduce ordinary errors, but it cannot replace project-specific semantic ownership.

The final question is still:

```text
Does this candidate preserve the project-specific boundary?
```

If not, it should not become accepted project truth.

---

## Why This Matters

Many AI-generated answers are locally reasonable.

They may describe a pattern that works in many systems.

They may sound coherent.

They may even be technically correct in a general context.

But this project is not governed by general plausibility.

It is governed by project-specific boundaries:

```text
accepted history = authority
idempotency receipt = successful request-effect memory
projection state = derived read model
checkpoint = operational progress metadata
snapshot = derived compression evidence
```

A suggestion that ignores these boundaries can be fluent and still wrong for this repository.

That is why AI assistance must be treated as candidate reasoning, not final authority.

---

## Case 1 — The Idempotency Record That Looked Mutable

During Stage 3.5E permission design, one candidate direction was to grant the application writer role `UPDATE` access to `idempotency_records`.

The reasoning was generally plausible:

```text
an idempotency table may track request lifecycle
request status may move from pending to succeeded, failed, or conflicted
therefore the write-side runtime may need UPDATE
```

That model can be valid in systems that store request attempts or retry lifecycle state.

But it did not match the current repository schema.

In this project, the current `idempotency_records` table stores only successful request-to-accepted-event mappings.

It records:

```text
request_id
semantic_fingerprint
accepted_event_id
result_sequence
status = SUCCEEDED
```

It does not record:

```text
pending requests
failed attempts
retry lifecycle
conflict history
rejected candidates
runtime decision attempts
```

Therefore, the earlier candidate design was rejected.

The corrected boundary is:

```text
idempotency_records
= successful request-effect receipt
= request_id → accepted_event_id mapping
= insert-once / restricted rewrite under the current schema
```

The application writer may insert a successful idempotency receipt as part of the same write-side transaction that appends the accepted event.

But under the current design, it should not receive normal `UPDATE` or `DELETE` privileges on `idempotency_records`.

The future retry or failed-attempt lifecycle may require another table.

That belongs to a later governance layer, not to the current successful idempotency receipt table.

---

## Case 2 — The App Writer That Should Not Read Projection State

Another candidate direction was to allow the application writer role to read `projection_states`.

This was also generally plausible.

Some systems may let write-side services read read-side models for diagnostics, post-write readback, or convenience.

But this project has a stricter dependency direction.

The write-side command path is:

```text
read accepted history / event log
→ rehydrate aggregate
→ run Compass Layer 1 validation
→ produce candidate event
→ append accepted event
→ insert successful idempotency receipt
```

The write side does not use projection state for command admission.

Projection state is a derived read model.

It is not accepted history.

Granting the application writer `SELECT` access to projection state would risk suggesting a dependency that the project intentionally avoids:

```text
projection state
→ command admission
```

That path is not part of the current architecture.

Therefore, the candidate permission was rejected.

The corrected boundary is:

```text
compass_app_writer
= reads and appends accepted history
= inserts successful idempotency receipts
= does not read projection state by default
```

The read side may use `projection_states` for efficient queries.

But the write side must continue to make admission decisions from accepted history, not from derived read models.

---

## What These Two Cases Have in Common

Both rejected suggestions were reasonable in a generic system.

Neither was absurd.

Neither was obviously broken.

That is exactly why they were risky.

The problem was not that the AI generated nonsense.

The problem was that the suggestions were not yet aligned with the repository’s actual boundaries.

The failure mode was subtle:

```text
general architectural plausibility
was mistaken for
project-specific correctness
```

This is the exact kind of semantic drift the project tries to prevent.

---

## The Admission Boundary in Development

This project uses AI heavily, but it does not let AI bypass ownership.

The development process is closer to:

```text
AI proposes a candidate explanation.
AI review may challenge or confirm it.
The repository boundary still has to test it.
The human owner checks it against actual code, schema, and architecture.
Only then can it become documentation or implementation.
```

The review questions are usually simple:

```text
Is this true for this repository?
Does the current schema support this interpretation?
Does this introduce a dependency that the architecture avoids?
Does this preserve accepted history as authority?
Does this confuse derived state with truth?
Does this accidentally import future-stage complexity into the current stage?
```

If the answer is no, the candidate is rejected or rewritten.

This is not because human judgment is always correct.

It is because someone must own the project-specific semantic boundary.

For this repository, that ownership cannot be replaced by fluency, agreement between tools, or loop completion.

---

## Relationship to Compass

This working method mirrors the system’s own design.

Compass Layer 1 does not accept every candidate event.

It validates whether a candidate event is allowed to become accepted history.

The development workflow follows the same discipline:

```text
not every candidate explanation becomes accepted documentation
not every candidate design becomes accepted architecture
not every generated implementation becomes accepted code
```

The repository itself becomes the admission boundary.

The commit becomes the accepted fact.

In practical terms:

```text
AI output
→ candidate design

repository-specific review
→ admission boundary

committed documentation or code
→ accepted project fact
```

---

## Why This Is Useful

This approach is slower than blindly accepting generated output.

It is also slower than delegating the entire process to an automated loop.

But it prevents several failure modes:

```text
fluent explanations that do not match the schema
permission models that imply the wrong dependency direction
future-stage concerns leaking into the current stage
read-side artifacts being treated as write-side authority
mutable lifecycle assumptions being applied to insert-once receipts
general AI agreement being mistaken for repository-specific correctness
```

In a project focused on semantic correctness under failure, these are not cosmetic mistakes.

They are architecture risks.

---

## General Rule

```text
Fluency is not alignment.
Agreement is not admission.
Loop completion is not project truth.
```

AI can accelerate clarification.

AI can produce useful candidate language.

AI can pressure-test assumptions.

AI can participate in review loops.

But AI does not own the architecture.

The final responsibility remains with the project owner:

```text
choose the boundary
reject misleading abstractions
preserve dependency direction
keep the repository semantically consistent
```

---

## Final Summary

This case study records a practical rule for AI-assisted engineering:

```text
AI suggestions are candidate actions, not accepted facts.
```

The same discipline that protects runtime truth also protects the development process.

A candidate event must pass admission before it becomes accepted history.

A candidate design must pass repository-specific review before it becomes accepted architecture.

That remains true even when more than one AI participates in the workflow.

That is why this project uses AI as a reasoning partner and pressure-testing tool, not as an authority.
