# SemanticOutcome vs JSON Boundary

[← Back to Boundary Notes Index](README.md)

> **Status:** This is a current conceptual boundary note, not an external API
> compatibility contract. Current source, tests, and accepted ADRs govern the
> exact runtime vocabulary.

## Purpose

This note clarifies a Stage 4 runtime governance boundary:

```text
SemanticOutcome is not the same thing as JSON.
JSON is not semantic governance.
```

This distinction matters because agent-readable output is not automatically agent-safe output.

A runtime may produce valid JSON while still carrying ambiguous, unstable, or unsafe meaning.

---

## Core Boundary

```text
SemanticOutcome
= stable semantic interpretation

JSON
= serialization / envelope format
```

A shorter way to say it:

```text
SemanticOutcome makes a result judgeable.
JSON makes a result transmissible.
```

The system should define semantic meaning before it serializes that meaning.

---

## Why JSON Alone Is Not Enough

JSON can prove that data has fields.

It cannot prove that those fields are semantically stable.

For example:

```json
{
  "status": "failed",
  "reason": "bad input"
}
```

and:

```json
{
  "status": "failed",
  "reason": "database timeout"
}
```

are both valid JSON.

However, they may require very different runtime handling.

One may be a domain rejection.

The other may be a transient infrastructure failure.

An agent or policy layer should not infer governance behavior from the word `failed` alone.

---

## Layered Runtime Interpretation

A safer runtime governance pipeline separates responsibility boundaries and
operational steps:

```text
Raw evidence boundary
Semantic interpretation boundary — SemanticOutcome
Governance-evidence boundary — DecisionReceipt
Serialization boundary — optional strict JSON envelope
Persistence boundary — explicit caller-owned operation
```

Expanded:

```text
raw runtime evidence
→ SemanticOutcome
→ DecisionReceipt
→ optional strict JSON serialization
→ explicit caller-owned persistence
```

This means:

```text
raw evidence
= what happened

SemanticOutcome
= what the system says it means

DecisionReceipt
= which summary evidence is preserved for later governance

JSON
= how that preserved meaning may be represented for transmission or storage
```

The `DecisionReceipt` contract and its JSON envelope are separate
responsibilities. Serializing a receipt neither creates it nor persists it.

---

## Current Implementation Status

The current repository baseline is:

```text
Stage 4A
= complete
= technical runtime evidence → typed SemanticOutcome

Stage 4B
= complete
= DecisionReceipt contract, generic mapping, and producer mappings
= JSON-safe evidence contracts
= strict serializer v1
= explicit caller-owned PostgreSQL persistence

Stage 4B.1
= complete
= DiagnosticTrace / ResolutionTrace

Stage 4B.2
= complete
= bounded producer-specific Measurement Evidence

Stage 4B.3
= closed as not currently justified

Stage 4B.5
= complete
= Order Correctness Contract v0

Stage 4C
= Runtime Decision Authority — complete / closed

Stage 4D
= Strategy Selection Authority — responsibility retained / implementation deferred

Stage 4E
= Same-Request Re-Invocation Authority — complete / closed
= two reviewed production-positive profiles; one-shot owner custody
= not generic retry governance or execution

Stage 5 Action Safety
= future
```

The strict version 1 serializer is an internal serialization contract. It is
not a promise that one external public API representation will remain
compatible indefinitely.

Automatic `SemanticOutcome → DecisionReceipt` materialization is not
implemented. Accepted-history reconciliation into receipts is also absent.
Callers explicitly choose when to build, serialize, and persist a receipt.

See the [Stage 4A closeout](../implementation_notes/stage_4a/stage_4a_closeout.md),
the [Stage 4B closeout](../implementation_notes/stage_4b/stage_4b_closeout.md),
the [Runtime SemanticOutcome Boundary](runtime_semantic_outcome_boundary.md),
and the canonical [DecisionReceipt Boundary](decision_receipt_boundary.md) for
the owning current contracts.

## Stage Placement

Stage 4A does not need to be JSON-first.

It needs to be contract-first.

A typed internal contract is acceptable when it provides:

```text
closed vocabulary
explicit fields
deterministic mapping
test coverage
clear boundary separation
explicit serialization boundary
```

---

## DecisionReceipt Boundary

A `DecisionReceipt` preserves selected semantic governance evidence.

It does not preserve arbitrary operational detail.

Receipt-safe evidence is:

```text
compact
stable
machine-readable
reviewable
JSON-safe
safe to query later
```

Receipt evidence excludes:

```text
live Python objects
database connections
validator instances
callbacks
exception objects
mutable runtime state
arbitrary unbounded payloads
```

The Stage 4B receipt contract therefore uses a typed outer model plus JSON-safe
evidence containers.

---

## Important Non-Equivalences

```text
JSON-valid
≠
semantically valid

JSON-safe
≠
agent-safe

serializable
≠
authoritative

structured output
≠
governed evidence

SemanticOutcome
≠
DecisionReceipt

DecisionReceipt
≠
Runtime Decision Authority
```

A receipt can be serialized through the strict version 1 JSON contract.

But serialization should happen after the semantic boundary is defined.

---

## Example

A raw observation may say:

```text
snapshot mismatch
```

A naive JSON envelope might say:

```json
{
  "status": "error",
  "message": "snapshot mismatch"
}
```

That is not enough.

The current vocabulary can express selected fields of that semantic
interpretation as:

```text
category = DRIFT
semantic_code = DRIFT_DETECTED
boundary = SNAPSHOT_TRUST
```

The implemented Stage 4B mappings can preserve selected semantic governance
evidence in a `DecisionReceipt` when a caller explicitly invokes the
appropriate mapping.

Only after that does optional strict JSON serialization become useful. A
separate caller-owned persistence operation is required to store the receipt.

---

## Design Rule

```text
Do not confuse serialization format with semantic authority.
```

The preferred order is:

```text
define meaning
preserve selected evidence
serialize when needed
```

not:

```text
produce JSON
then hope the meaning is safe
```
