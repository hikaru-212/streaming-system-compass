# Write-Side Schema Baseline

[← Back to Architectures Index](README.md)

## Purpose

This document defines the first durable schema baseline for the write-side path in Stage 3.5.

Its purpose is to explain why the initial PostgreSQL schema for the write-side should be shaped the way it is, before implementation details grow larger.

This note focuses on two durable write-side boundaries:

- accepted event history
- request-level idempotency persistence

It does **not** define the entire runtime implementation.
It defines the schema-level reasoning that supports that implementation.

---

## Why This Note Exists

The move from an in-memory write-side baseline to a persistence-backed write-side baseline is not a simple backend replacement.

Once write-side state must survive:

- process lifetime
- restart
- retry after timeout
- partial persistence failure

the system must make some previously implicit runtime assumptions explicit.

That is why the durable write-side schema must answer not only:

- what data should be stored

but also:

- what semantic boundary this data belongs to
- how replay / conflict classification should remain stable
- how future semantic evolution should be handled

---

## Scope

This document covers the first write-side durable schema baseline for:

- `events`
- `idempotency_records`

It does **not yet** cover:

- projection state schema
- checkpoint schema
- advanced operational monitoring tables
- conflict audit tables
- DLQ or out-of-order runtime structures

Those belong to later stages.

---

## Core Write-Side Principle

The durable write-side must preserve two distinct but related boundaries:

### 1. Accepted History Boundary

This answers:

> what event facts have been admitted into the system?

This belongs to the `events` table.

### 2. Idempotency Boundary

This answers:

> how should repeated external requests be classified across time?

This belongs to the `idempotency_records` table.

These two boundaries are related, but they must not be collapsed.

They may require coordinated transaction grouping,
but they do not represent the same semantic responsibility.

---

## Current Durable Write-Side Targets

The baseline write-side schema should support:

- durable accepted-history append
- durable request replay / conflict classification
- aggregate-local replay
- idempotency survival across restart
- future evolution of semantic fingerprint rules

---

# Table 1: `events`

## Purpose

The `events` table stores accepted event history.

It is the durable source of truth for the write-side and the durable replay source for later aggregate reconstruction.

---

## Proposed Core Columns

- `event_id`
- `aggregate_id`
- `sequence`
- `event_type`
- `payload_json`
- `proof_json`
- `created_at`

---

## Why These Columns Exist

### `event_id`
Stable event identity.

### `aggregate_id`
Required for aggregate-local replay and event-stream loading.

### `sequence`
Required for aggregate-local ordering and continuity protection.

### `event_type`
Required for replay interpretation, dispatch clarity, and debugging.

### `payload_json`
Stores event payload while leaving room for payload evolution.

### `proof_json`
Stores proof / provenance claims in a form that can evolve without forcing excessive schema churn.

### `created_at`
Provides durable traceability and time-based debugging support.

---

## Proposed Core Constraint

The initial durable write-side baseline should require:

- uniqueness of `(aggregate_id, sequence)`

This protects aggregate-local accepted-history continuity.

---

## Baseline Role of `events`

The `events` table is:

- append-oriented
- replayable
- aggregate-local ordered
- the durable accepted-history boundary

It is **not**:

- the idempotency boundary
- the projection boundary
- the checkpoint boundary
- the conflict audit boundary

---

# Table 2: `idempotency_records`

## Purpose

The `idempotency_records` table stores durable request-level classification support.

Its purpose is to preserve request replay / conflict semantics across time.

It exists because the system must be able to answer, after restart:

- has this request already been processed?
- if so, was it the same semantic request?
- if so, what prior accepted result should be replayed?

---

## Proposed Core Columns

- `request_id`
- `aggregate_id`
- `command_type`
- `fingerprint_version`
- `semantic_fingerprint`
- `result_event_id`
- `result_sequence`
- `status`
- `created_at`
- `updated_at`

---

## Why These Columns Exist

### `request_id`
Stable request identity used for lookup.

### `aggregate_id`
Durable traceability for which aggregate this request targeted.

### `command_type`
Improves semantic readability, debugging, and operational queryability.
This should not remain hidden inside a payload blob.

### `fingerprint_version`
Tracks which semantic-basis rules were used to generate the fingerprint.

This is important because semantic basis may evolve over time.
Future additions such as `currency` may change which fields define semantic equivalence.

Without `fingerprint_version`, old and new fingerprints may be compared as if they were produced under the same semantic rules when they were not.

### `semantic_fingerprint`
The durable signature of the command's semantic basis.

It is not the full raw request payload.
It is the stable representation of the fields that define the semantic effect of the request.

### `result_event_id`
Links the durable idempotency result to the accepted event that satisfied the request.

### `result_sequence`
Provides durable traceability and simpler replay/result lookup.

### `status`
Represents the durable classification state stored in the baseline table.

### `created_at`, `updated_at`
Support auditability and durable change tracking.

---

## Why `fingerprint_version` Is Necessary

A key baseline rule of Stage 3.5 is:

> semantic basis is tied to current domain meaning, not frozen forever.

This means future semantic expansion is expected.

For example:

- today, `PayOrder` may be defined by:
  - `command_type`
  - `aggregate_id`
  - `payment_amount`

- later, if `currency` becomes part of domain meaning, the semantic basis may evolve to:
  - `command_type`
  - `aggregate_id`
  - `payment_amount`
  - `currency`

That future change should not silently invalidate the meaning of previously stored fingerprints.

So the schema must preserve not only the fingerprint itself, but also the version of the basis that produced it.

---

## Baseline Meaning of `semantic_fingerprint`

The durable idempotency baseline uses the following distinction:

- same `request_id` + same `fingerprint_version` + same `semantic_fingerprint` → replay
- same `request_id` + same `fingerprint_version` + different `semantic_fingerprint` → conflict
- future basis versions must not be treated as if they were generated under the same semantic rules

This keeps the system honest about semantic evolution.

---

## Baseline Conflict Policy

The current write-side durable baseline may start with the following direction:

- successful processed requests are persisted in `idempotency_records`
- conflict is detected explicitly
- conflict persistence is not yet required in the main baseline table

This keeps the first durable idempotency baseline narrower and easier to reason about.

If richer audit or abuse-tracing behavior becomes necessary later, conflict logging may be introduced as a separate concern.

---

## Baseline Role of `idempotency_records`

The `idempotency_records` table is:

- a durable replay / conflict classification support boundary
- a durable request-to-result mapping boundary
- a restart-safe idempotency boundary

It is **not**:

- the accepted-history source of truth
- the event payload archive
- the projection state boundary
- the checkpoint boundary

---

# Semantic Fingerprint Basis (v1)

## Current Purpose

The initial `semantic_fingerprint` must reflect the **current** domain meaning, not hypothetical future meaning.

That means the first baseline should only include fields that already define semantic effect in the current domain.

Money values included in the semantic basis must use a canonical decimal representation before fingerprint generation, so that semantically equal monetary inputs do not produce different fingerprints merely because of formatting differences.

---

## `CreateOrder` v1 Basis

Included fields:

- `command_type`
- `aggregate_id`
- `total_amount`

Excluded fields:

- `request_id`
- tracing metadata
- timing metadata
- retry metadata
- transport-specific noise

Example semantic basis:

```json
{
  "command_type": "CREATE_ORDER",
  "aggregate_id": "<order_id>",
  "total_amount": "<amount>"
}
```

---

## `PayOrder` v1 Basis

Included fields:

- `command_type`
- `aggregate_id`
- `payment_amount`

Excluded fields:

- `request_id`
- tracing metadata
- timing metadata
- retry metadata
- transport-specific noise

Example semantic basis:

```json
{
  "command_type": "PAY_ORDER",
  "aggregate_id": "<order_id>",
  "payment_amount": "<amount>"
}
```

---

## Future Evolution Rule

If the domain later introduces new semantic dimensions, the semantic basis must evolve explicitly.

For example, if `currency` later becomes part of `PayOrder` meaning, then a future basis version may become:

```json
{
  "command_type": "PAY_ORDER",
  "aggregate_id": "<order_id>",
  "payment_amount": "<amount>",
  "currency": "<currency>"
}
```

At that point:

- `fingerprint_version` must advance
- comparison logic must respect basis version
- old records must not be treated as though they were generated under the new basis rules

---

# Transaction Grouping Requirement

The write-side baseline should treat the following as one consistency group:

- event append
- idempotency record write

This does **not** mean the two boundaries are semantically merged.

It means they require coordinated durability.

The reason is simple:

- event persisted without idempotency record → retry semantics become unstable
- idempotency record persisted without event → accepted-history semantics become unstable

So the write-side baseline must preserve both:

- boundary separation
- transactional consistency

---

# Current Design Decisions

At the current stage, the following are already directionally accepted:

- PostgreSQL is the primary durable storage target
- accepted history remains the durable source of truth
- idempotency remains a separate semantic boundary
- `semantic_fingerprint` must be durable and explicit
- `fingerprint_version` is necessary for future semantic evolution
- write-side durability should be implemented before read-side durability

---

# Questions Still Open

The following still require final implementation decisions:

- exact SQL types for each identifier column
- whether `status` should remain minimal in the baseline
- whether conflict should remain non-persistent in the first durable iteration
- exact Python-side storage interface shape
- exact migration file layout
- exact transaction handling code

---

# Summary

The first write-side schema baseline should not merely store data.

It should preserve:

- accepted-history durability
- replayability
- request-level idempotency semantics
- future-safe semantic fingerprint evolution

That is why the initial durable write-side schema must include not only `semantic_fingerprint`, but also `fingerprint_version`.

Without that, the system would have no durable way to distinguish:

- same semantic rule set applied twice
- versus fingerprints generated under different semantic worlds
