# Postmortem: From Generic Validation to Authority-Based Reasoning

[← Back to Postmortems Index](README.md)

**Recorded on:** 2026-06-24

---

## Purpose

This note records a reasoning correction discovered during **Stage 3.5D PR4 — Projection Snapshot-Assisted Replay Validator**.

The issue was not a syntax bug or a broken implementation.

The issue was a semantic-priority mistake: a generic validation instinct was almost applied to an authority-based validator.

The incorrect instinct was:

```text
If a snapshot exists but is structurally invalid,
return INVALID_SNAPSHOT_BOUNDARY first.
```

That sounds reasonable in a normal input-validation context.

But PR4 is not a generic input validator.

PR4 validates whether a snapshot-assisted replay path can reconstruct the same state implied by accepted history.

Therefore the corrected rule is:

```text
accepted history must exist before snapshot trust can be evaluated.
```

This postmortem records the broader lesson:

```text
generic validation intuition
≠
authority-based semantic reasoning
```

A suggestion can be locally reasonable and still be globally wrong if it violates the project’s authority model.

---

## Context

Stage 3.5D introduces snapshot trust without allowing snapshots to become source of truth.

The governing rule is:

```text
accepted history = authority
projection snapshot = derived compression
snapshot-assisted replay = fast path candidate
authority replay = correctness baseline
```

PR4 introduces a validator that compares:

```text
authority path:
accepted history → full replay → authority_state

snapshot-assisted path:
projection snapshot → hydrate state → replay tail events → snapshot_assisted_state
```

Then it evaluates:

```text
snapshot_assisted_state == authority_state
```

This means the validator is not asking:

```text
Is this snapshot row independently meaningful?
```

It is asking:

```text
Can this snapshot-assisted replay path be trusted because it agrees with accepted history?
```

The difference matters.

---

## The Confusing Case

The confusing case was:

```text
snapshot exists
snapshot is structurally invalid
accepted history is missing
```

A generic validation habit says:

```text
bad input exists
→ INVALID_INPUT
```

Applied to this PR, that becomes:

```text
snapshot exists but structurally invalid
→ INVALID_SNAPSHOT_BOUNDARY
```

But that classification is not the best fit for PR4.

In PR4, the snapshot is not primary evidence.

It is only a derived candidate that can be judged against accepted history.

If accepted history is missing, the validator has no authority baseline.

Therefore the corrected classification is:

```text
snapshot exists
accepted history missing
→ NO_ACCEPTED_HISTORY_FOR_ORDER
```

The snapshot may also be malformed, but PR4 cannot establish snapshot trust without the authority path.

---

## The Corrected Classification Model

The corrected model is:

```text
accepted history missing
→ NO_ACCEPTED_HISTORY_FOR_ORDER
```

```text
accepted history exists
snapshot missing
→ MISSING_SNAPSHOT
```

```text
accepted history exists
snapshot exists
snapshot structurally invalid
→ INVALID_SNAPSHOT_BOUNDARY
```

```text
accepted history exists
snapshot exists
snapshot valid
snapshot-assisted replay differs from authority replay
→ SNAPSHOT_ASSISTED_DRIFT
```

```text
accepted history exists
snapshot exists
snapshot valid
snapshot-assisted replay matches authority replay
→ MATCH
```

This model preserves the Stage 3.5D rule:

```text
snapshot validation happens only after the authority foundation exists.
```

The validator may preserve snapshot identifiers as evidence when no accepted history exists, but it should not hydrate, trust, or semantically validate the snapshot as a replay candidate without accepted history.

---

## Why the Generic Rule Was Tempting

The generic rule is common in ordinary API design:

```text
validate input shape first
then execute business logic
```

That rule works well when the input itself is the object being validated.

For example:

```text
malformed request body
→ INVALID_REQUEST
```

or:

```text
invalid enum value
→ INVALID_INPUT
```

But PR4 is not validating a request body in isolation.

It is validating a relationship between two paths:

```text
snapshot-assisted path
vs
authority path
```

That means the authority path is not optional context.

It is the baseline that gives the validation meaning.

Without it, the system cannot answer whether the snapshot-assisted path is trustworthy.

---

## The Root Cause

The root cause was applying a generally reasonable engineering heuristic in the wrong semantic domain.

The heuristic was:

```text
if evidence looks invalid, classify it as invalid evidence first
```

The project-specific rule is:

```text
derived evidence can only be judged against authority evidence
```

The snapshot is derived evidence.

Accepted history is authority evidence.

Therefore the snapshot cannot lead the classification when accepted history is absent.

The corrected reasoning is:

```text
No accepted history
→ no authority baseline
→ no snapshot trust validation
→ NO_ACCEPTED_HISTORY_FOR_ORDER
```

not:

```text
Snapshot exists and looks invalid
→ INVALID_SNAPSHOT_BOUNDARY
```

---

## Why This Matters

If the generic rule were used, the validator would subtly invert the trust hierarchy.

It would allow the snapshot to dominate the failure classification even when the authority foundation is missing.

That would weaken the Stage 3.5D invariant:

```text
accepted history = authority
snapshot = derived / discardable / subordinate
```

The danger is not that the code would crash.

The danger is that the status vocabulary would encode the wrong semantic priority.

A validator result is not just a return value.

It is a machine-readable explanation of which boundary failed.

If the result says:

```text
INVALID_SNAPSHOT_BOUNDARY
```

when there is no accepted history, it suggests:

```text
we evaluated the snapshot as a replay candidate
```

But the system could not have done that legitimately, because the authority path was unavailable.

The more accurate result is:

```text
NO_ACCEPTED_HISTORY_FOR_ORDER
```

because the validation cannot even establish the baseline required to judge the snapshot.

---

## Relationship to Test Naming and Test Intent

This mistake is related to a broader testing hazard seen earlier in the project:

```text
test name says one variable is changing
but the test body changes two variables
```

That kind of mismatch creates false confidence.

The reader believes the test proves one boundary, while the implementation actually crosses multiple boundaries at once.

The same pattern appeared here at the semantic-status level:

```text
status name sounds locally reasonable
but the classification order violates the authority model
```

Both cases are examples of intent drift:

```text
surface description
≠
actual semantic proof
```

For tests, this means:

```text
test name
fixture setup
changed variables
asserted status
```

must all point to the same boundary.

For validator design, this means:

```text
failure status
classification order
system authority model
```

must all point to the same semantic boundary.

---

## The Collaboration Blind Spot

This was also a human-AI collaboration blind spot.

The AI suggestion was locally plausible because generic validation often checks malformed evidence first.

But the human reviewer noticed that this would violate the project’s central authority model.

The developer corrected the reasoning:

```text
snapshot is only a candidate derived state
accepted history is the authority foundation
therefore snapshot trust cannot be evaluated before authority exists
```

This exposed an important collaboration rule:

```text
AI suggestions must be checked against project-specific semantic axioms,
not only against local implementation plausibility.
```

The problem was not that the assistant made a syntax mistake.

The problem was that a generic engineering instinct overrode a domain-specific invariant.

That is more dangerous because it can produce code that looks clean, tested, and reasonable while still encoding the wrong meaning.

---

## Correct Review Questions

When reviewing an AI-generated implementation or suggestion, especially around validators and tests, ask:

```text
What is the authority source in this boundary?
```

```text
Is this status describing the authority boundary or a derived candidate boundary?
```

```text
Can this failure be classified without first establishing the authority baseline?
```

```text
Is a generic input-validation rule being applied to an authority-based validator?
```

```text
Does the test name match the exact semantic axis being changed?
```

```text
Does the test body change only the variable implied by the test name?
```

```text
Would this classification still make sense if the snapshot were removed entirely?
```

For Stage 3.5D, the key question is:

```text
Is snapshot being treated as subordinate evidence, or did it accidentally become primary evidence?
```

---

## Corrected Rule for PR4

The corrected PR4 rule is:

```text
A projection snapshot can only be evaluated as a replay candidate
when accepted history exists for the requested order.
```

Therefore:

```text
snapshot exists + accepted history missing
→ NO_ACCEPTED_HISTORY_FOR_ORDER
```

and:

```text
snapshot exists + accepted history exists + invalid snapshot boundary
→ INVALID_SNAPSHOT_BOUNDARY
```

These are not merely priority choices.

They represent different semantic failures:

```text
NO_ACCEPTED_HISTORY_FOR_ORDER
= no authority foundation exists
```

```text
INVALID_SNAPSHOT_BOUNDARY
= authority foundation exists, but snapshot candidate is structurally incompatible
```

This preserves the hierarchy:

```text
accepted history first
snapshot second
```

---

## Relationship to Snapshot Trust Contract

This postmortem belongs to Stage 3.5D because it reinforces the Snapshot Trust Contract.

A snapshot is not trusted because it exists.

A snapshot is not trusted because it has a plausible shape.

A snapshot is trusted only when it can be placed under accepted-history authority.

For PR4, that means:

```text
snapshot + tail replay
must match
accepted-history replay
```

The snapshot is useful only as a fast-path candidate.

It is not a standalone source of truth.

This is why the validator must not let snapshot-local invalidity outrank accepted-history absence.

The absence of accepted history means the validator cannot establish the trust comparison at all.

---

## Relationship to PR4.5

This lesson also matters for the planned PR4.5 resolver.

PR4.5 should use a trusted snapshot to avoid full accepted-history replay on the hot path.

But PR4.5 must not silently assume that any persisted snapshot is trusted.

The correct relationship is:

```text
PR4
= produce or verify trust evidence by comparing against authority replay
```

```text
PR4.5
= use an already trusted snapshot to resolve state through snapshot + tail replay
```

If PR4.5 treats snapshot existence as enough, it would repeat the same semantic mistake in a performance path.

The resolver must preserve the same hierarchy:

```text
snapshot is usable only under an explicit trust precondition
```

---

## Reusable Lesson

The reusable lesson is:

```text
generic validation says:
validate malformed input first
```

but authority-based validation says:

```text
establish the authority baseline first
then evaluate derived candidates against it
```

A locally reasonable status classification can still be globally wrong if it changes the trust hierarchy.

For this project:

```text
accepted history is authority
snapshots are subordinate derived evidence
```

Any validator, test, or status model that violates this ordering should be treated as suspicious, even if it looks clean in isolation.

---

## Summary

This postmortem records one key correction:

```text
PR4 is not a generic snapshot input validator.
It is an authority-based replay validator.
```

Therefore, the system should not classify snapshot structural invalidity before establishing whether accepted history exists.

The correct model is:

```text
no accepted history
→ no authority baseline
→ NO_ACCEPTED_HISTORY_FOR_ORDER
```

Only after accepted history exists should the validator classify:

```text
snapshot boundary invalid
→ INVALID_SNAPSHOT_BOUNDARY
```

The broader engineering lesson is:

```text
AI-assisted suggestions must be checked against project-specific semantic axioms.
```

Generic engineering intuition is useful, but it must not override the system’s source-of-truth model.
