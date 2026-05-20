# Write-Side Schema Baseline

[← Back to Architectures Index](README.md)

## Purpose

This document defines the first durable schema baseline for the write-side path in Stage 3.5B.

Its purpose is to explain why the initial PostgreSQL schema for the write-side should be shaped the way it is before implementation details grow larger.

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
- how accepted history should remain append-oriented after crossing into PostgreSQL

---

## Scope

This document covers the first write-side durable schema baseline for:

- `order_events`
- `idempotency_records`

It does **not yet** cover:

- projection state schema
- checkpoint schema
- advanced operational monitoring tables
- conflict audit tables
- DLQ or out-of-order runtime structures
- structured semantic outcome persistence
- Layer 2 validation tables

Those belong to later stages.

---

## Core Write-Side Principle

The durable write-side must preserve two distinct but related boundaries.

### 1. Accepted History Boundary

This answers:

> what event facts have been admitted into the system?

This belongs to the `order_events` table.

### 2. Idempotency Boundary

This answers:

> how should repeated external requests be classified across time?

This belongs to the `idempotency_records` table.

These two boundaries are related, but they must not be collapsed.

They may require coordinated transaction grouping, but they do not represent the same semantic responsibility.

---

## Current Durable Write-Side Targets

The baseline write-side schema should support:

- durable accepted-history append
- durable request replay / conflict classification
- aggregate-local replay
- idempotency survival across restart
- future evolution of semantic fingerprint rules
- exact money persistence
- future-safe transition into transactional write-side persistence

---

# Table 1: `order_events`

## Purpose

The `order_events` table stores accepted event history for the current order domain.

It is the durable source of truth for the write-side and the durable replay source for later aggregate reconstruction.

In this stage, `order_id` is the aggregate-local stream identity.

A future generalized event store may rename this concept to `aggregate_id`, but Stage 3.5B should stay aligned with the current domain model.

---

## Proposed Core Columns

- `accepted_event_id`
- `order_id`
- `sequence`
- `event_type`
- `request_id`
- `amount`
- `occurred_at_ms`
- `proof_prev_event_id`
- `proof_prev_version`
- `proof_prev_status`
- `payload_json`
- `proof_json`
- `created_at`

---

## Why These Columns Exist

### `accepted_event_id`

Stable event identity after the event has entered accepted history.

This name is intentional.

Before append, the same UUID-like value should be interpreted as `candidate_event_id`.

After successful append into `order_events`, it may be referenced as `accepted_event_id`.

The key boundary rule is:

> `event_id` alone does not imply accepted history.  
> Only event-log membership grants accepted-event status.

### `order_id`

The current aggregate-local stream identity.

This supports order-level replay and event-stream loading.

### `sequence`

Required for aggregate-local ordering and continuity protection.

This is the stream-local position of the event.

### `event_type`

Required for replay interpretation, dispatch clarity, and debugging.

### `request_id`

Connects the accepted event back to the external request that produced it.

This is useful for traceability and idempotency reasoning.

### `amount`

Stores exact money-like value in PostgreSQL using exact numeric representation.

This should not use floating-point storage.

### `occurred_at_ms`

Preserves the event occurrence timestamp carried by the domain event.

### `proof_prev_event_id`, `proof_prev_version`, `proof_prev_status`

Stores the minimal proof / predecessor claims needed by the current write-side model.

These fields make important proof values queryable without requiring every validation or debugging path to parse JSON.

### `payload_json`

Stores event payload details while leaving room for payload evolution.

This should not hide fields needed for stream identity, replay ordering, or write-side safety checks.

### `proof_json`

Stores supplemental proof / provenance details in a form that can evolve without excessive schema churn.

### `created_at`

Provides durable insertion traceability and time-based debugging support.

This is a persistence timestamp, not a replacement for `occurred_at_ms`.

---

## Proposed Core Constraints

The initial durable write-side baseline should require:

- primary key on `accepted_event_id`
- uniqueness of `(order_id, sequence)`
- positive sequence values
- exact non-negative money storage
- event-type check for currently supported event types
- proof version presence
- foreign-key linkage from idempotency records back to accepted events

The most important stream-level constraint is:

```sql
UNIQUE (order_id, sequence)
```

This protects aggregate-local accepted-history identity.

It prevents two accepted rows from occupying the same logical event slot.

---

## Suggested Draft Shape

A first migration may look conceptually like:

```sql
CREATE TABLE order_events (
    accepted_event_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    request_id TEXT NOT NULL,
    amount NUMERIC(18, 2) NOT NULL,
    occurred_at_ms BIGINT NOT NULL,

    proof_prev_event_id TEXT,
    proof_prev_version INTEGER NOT NULL,
    proof_prev_status TEXT NOT NULL,

    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    proof_json JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_order_events_order_sequence UNIQUE (order_id, sequence),
    CONSTRAINT ck_order_events_sequence_positive CHECK (sequence > 0),
    CONSTRAINT ck_order_events_event_type CHECK (event_type IN ('CREATED', 'PAID')),
    CONSTRAINT ck_order_events_amount_non_negative CHECK (amount >= 0)
);
```

This is a baseline draft, not the final implementation contract.

The final migration should be reviewed together with the Python storage implementation.

---

## Baseline Role of `order_events`

The `order_events` table is:

- append-oriented
- replayable
- aggregate-local ordered
- the durable accepted-history boundary

It is **not**:

- the idempotency boundary
- the projection boundary
- the checkpoint boundary
- the conflict audit boundary
- a mutable current-state table

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
- `order_id`
- `command_type`
- `amount`
- `fingerprint_version`
- `semantic_fingerprint`
- `accepted_event_id`
- `result_sequence`
- `status`
- `created_at`

---

## Why These Columns Exist

### `request_id`

Stable request identity used for lookup.

This is the durable primary key for idempotency classification.

### `order_id`

Durable traceability for which order stream this request targeted.

### `command_type`

Improves semantic readability, debugging, and operational queryability.

This should not remain hidden inside a payload blob.

### `amount`

Stores the exact money-like value associated with the current command semantics.

The semantic fingerprint should still be generated from canonical decimal strings, but the durable table can store the value as exact PostgreSQL `NUMERIC`.

### `fingerprint_version`

Tracks which semantic-basis rules were used to generate the fingerprint.

This is important because semantic basis may evolve over time.

Future additions such as `currency` may change which fields define semantic equivalence.

Without `fingerprint_version`, old and new fingerprints may be compared as if they were produced under the same semantic rules when they were not.

### `semantic_fingerprint`

The durable signature of the command's semantic basis.

It is not the full raw request payload.

It is the stable representation of the fields that define the semantic effect of the request.

### `accepted_event_id`

Links the durable idempotency result to the accepted event that satisfied the request.

This should reference `order_events.accepted_event_id`.

### `result_sequence`

Provides durable traceability and simpler replay / result lookup.

### `status`

Represents the durable classification state stored in the baseline table.

For Stage 3.5B, this table should only persist successful accepted-event results.

A minimal baseline may therefore only support:

```text
SUCCEEDED
```

Conflict logging can be added later as a separate audit concern.

### `created_at`

Supports auditability and durable traceability.

The baseline table should avoid `updated_at` unless the implementation introduces a real state transition such as `PENDING -> SUCCEEDED`.

For the first baseline, idempotency records should be append-oriented successful result records, not mutable workflow rows.

---

## Suggested Draft Shape

A first migration may look conceptually like:

```sql
CREATE TABLE idempotency_records (
    request_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    command_type TEXT NOT NULL,
    amount NUMERIC(18, 2) NOT NULL,

    fingerprint_version INTEGER NOT NULL,
    semantic_fingerprint TEXT NOT NULL,

    accepted_event_id TEXT NOT NULL,
    result_sequence INTEGER NOT NULL,

    status TEXT NOT NULL DEFAULT 'SUCCEEDED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT fk_idempotency_accepted_event
        FOREIGN KEY (accepted_event_id)
        REFERENCES order_events (accepted_event_id),

    CONSTRAINT ck_idempotency_fingerprint_version_positive
        CHECK (fingerprint_version > 0),

    CONSTRAINT ck_idempotency_status
        CHECK (status IN ('SUCCEEDED'))
);
```

This is a baseline draft.

A later hardening stage may introduce conflict audit records, pending states, retry attempt metadata, or richer operational traces.

Those are not part of the Stage 3.5B minimal schema.

---

## Why `fingerprint_version` Is Necessary

A key baseline rule of Stage 3.5B is:

> semantic basis is tied to current domain meaning, not frozen forever.

This means future semantic expansion is expected.

For example:

- today, `PayOrder` may be defined by:
  - `command_type`
  - `order_id`
  - `payment_amount`

- later, if `currency` becomes part of domain meaning, the semantic basis may evolve to:
  - `command_type`
  - `order_id`
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
- a conflict audit table in the first baseline

---

# Semantic Fingerprint Basis v1

## Current Purpose

The initial `semantic_fingerprint` must reflect the current domain meaning, not hypothetical future meaning.

That means the first baseline should only include fields that already define semantic effect in the current domain.

Money values included in the semantic basis must use a canonical decimal representation before fingerprint generation, so that semantically equal monetary inputs do not produce different fingerprints merely because of formatting differences.

---

## `CreateOrder` v1 Basis

Included fields:

- `command_type`
- `order_id`
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
  "order_id": "<order_id>",
  "total_amount": "<amount>"
}
```

---

## `PayOrder` v1 Basis

Included fields:

- `command_type`
- `order_id`
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
  "order_id": "<order_id>",
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
  "order_id": "<order_id>",
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

# Append-Only Policy

The `order_events` table should be treated as append-oriented accepted history.

The first baseline should enforce this primarily through:

- schema shape
- repository API design
- transaction discipline
- tests

Runtime DB role / privilege restrictions may be added as a hardening step.

This means Stage 3.5B should document that the runtime application should not update or delete accepted history rows, but it does not need to implement the full permission model in the first schema PR.

---

# Current Design Decisions

At the current stage, the following are directionally accepted:

- PostgreSQL is the primary durable storage target
- accepted history remains the durable source of truth
- `order_events` stores accepted history
- `idempotency_records` stores durable replay / conflict classification support
- `accepted_event_id` should be used for persisted accepted history
- `order_id` remains the current aggregate-local stream identity
- exact money storage is required
- `semantic_fingerprint` must be durable and explicit
- `fingerprint_version` is necessary for future semantic evolution
- write-side durability should be implemented before read-side durability
- full permission hardening can follow after the minimal durable loop works

---

# Questions Still Open

The following still require final implementation decisions:

- exact SQL types for each identifier column
- whether conflict should remain non-persistent in the first durable iteration
- exact Python-side storage interface shape
- exact migration file layout
- exact transaction handling code
- whether permission hardening should be implemented in the same stage or a later hardening PR
- whether `payload_json` and `proof_json` should eventually store the full canonical event/proof body or only supplementary details

---

# Summary

The first write-side schema baseline should not merely store data.

It should preserve:

- accepted-history durability
- replayability
- request-level idempotency semantics
- exact money semantics
- future-safe semantic fingerprint evolution

That is why the initial durable write-side schema must include not only `semantic_fingerprint`, but also `fingerprint_version`.

Without that, the system would have no durable way to distinguish:

- same semantic rule set applied twice
- versus fingerprints generated under different semantic worlds
