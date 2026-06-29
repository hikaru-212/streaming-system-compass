# ADR 0006: Use Decimal for Money Values Before Durable Persistence

[← Back to ADR Index](README.md)

## Status

Accepted

---

## Implementation Status

Implemented at baseline level.

This decision is reflected in the current domain event model and the durable write-side PostgreSQL schema.

Related implementation files:
- `src/core/order/events.py`
- `src/core/common/money.py`
- `db/migrations/001_create_write_side_tables.sql`

Implementation evidence:

- `OrderEvent.amount` is represented as `Decimal`
- event creation normalizes money values through `normalize_money(...)`
- durable write-side money fields use `NUMERIC(18, 2)` rather than floating-point database types
- both `order_events.amount` and `idempotency_records.amount` are stored as exact numeric values
- database constraints reject negative money values at the durable write-side boundary

This ADR is accepted because the baseline decision has already been implemented in the Stage 3.5A / Stage 3.5B transition.

Future hardening may still refine canonical decimal formatting, semantic fingerprint inputs, or domain-specific money rules, but the core decision to reject `float` as the durable baseline is complete.

---

## Context

The project originally used `float` for money-like values in the earlier in-memory baseline.

That was acceptable only as an early-stage simplification while the main focus remained on:

- semantic write-side flow
- event admission
- replayability
- Compass Layer 1 transition-truth validation
- Stage 3 in-memory projection baseline

However, Stage 3.5 introduces a different set of pressures:

- durable write-side persistence
- request-level idempotency persistence
- semantic fingerprint stability
- future schema hardening
- replay / rebuild correctness across time

At that point, approximate floating-point money values become more dangerous than before.

The system is no longer only comparing values inside one short-lived process.
It is beginning to depend on those values for:

- durable payload representation
- replay trust
- semantic fingerprint generation
- future SQL schema evolution
- later hardening into exact database numeric types

The repository therefore needs an explicit decision about whether to keep `float` for money values or introduce an exact decimal representation before durable persistence expands further.

---

## Decision

The project will migrate money-like values from `float` to `Decimal` before or alongside the first durable write-side persistence implementation.

The baseline decision is:

1. Python domain-level money values should use `Decimal`
2. JSON payload serialization should preserve exact decimal meaning, typically by using string representation
3. future hard SQL money columns should use exact numeric database types such as `NUMERIC(...)`
4. this migration should happen before the durable write-side baseline grows larger, rather than after persistence code is already widely introduced
5. a canonical decimal formatting rule must be defined before semantic fingerprint generation depends on money fields

---

## Rationale

### Why not keep `float`

`float` is a binary floating-point approximation, not an exact decimal money representation.

That makes it risky for a project that is about to depend on:

- durable replayability
- semantic fingerprint stability
- long-lived event payloads
- later schema and migration correctness

Even if the earlier in-memory baseline could tolerate approximate money representation, Stage 3.5 should not treat that simplification as durable truth.

### Why `Decimal`

`Decimal` gives the Python domain layer an exact decimal representation that is much better aligned with money semantics.

This strengthens:

- equality reasoning
- replay consistency
- durable semantic fingerprint generation
- future migration from JSON payloads into exact SQL numeric columns

### Why now

This migration should happen now because Stage 3.5 is the point where the project is formalizing durable write-side persistence.

If the project introduces durable persistence first while still using `float`, it risks carrying approximate money semantics into:

- event payloads
- replay data
- idempotency fingerprint inputs
- future schema assumptions

That would make later correction more expensive and more invasive.

---

## Consequences

### Positive Consequences

- money semantics become exact in the Python domain layer
- replay / rebuild reasoning becomes more trustworthy
- semantic fingerprint inputs become more stable
- future schema hardening toward `NUMERIC(...)` becomes cleaner
- the durable write-side baseline becomes semantically stronger before persistence grows

### Negative Consequences

- short-term refactoring is required now
- command objects, aggregate state, payload serialization, replay logic, and tests may all need updates
- Stage 3.5 implementation may appear slower in the short term because a representation correction happens before more visible persistence code

### Neutral but Important Consequence

The project is explicitly treating money representation as part of semantic correctness, not just as a later implementation detail.

---

## Alternatives Considered

### Alternative A: Keep `float` for now and migrate later

Rejected because it would allow approximate money semantics to leak into the durable write-side baseline, increasing future refactor cost.

### Alternative B: Convert to exact money representation only at the database layer

Rejected because the domain layer, payload layer, replay layer, and semantic fingerprint layer would still be working from approximate Python values before persistence.

That is too late.

### Alternative C: Keep money only inside JSON payloads and ignore exactness until later

Rejected because Stage 3.5 is specifically the stage where durable replay and durable idempotency begin to matter more.
Approximate money semantics would weaken those efforts.

### Alternative D: Use minor-unit integers immediately for all money values

Not rejected in principle, but not chosen as the baseline decision here.

That approach may still be valid later depending on domain needs.
For now, moving from `float` to `Decimal` is the most direct and conservative correction compatible with the existing project structure.

---

## Follow-Up Work

Expected follow-up work includes:

- update command-layer money fields from `float` to `Decimal`
- update aggregate state money fields from `float` to `Decimal`
- update payload serialization to preserve exact decimal meaning
- update replay / reconstruction logic to rebuild `Decimal`
- update semantic fingerprint generation to use exact canonical decimal forms
- update tests
- later consider whether some money values should be promoted into hard SQL `NUMERIC(...)` columns

Completed baseline work includes:

- domain event amount representation through `Decimal`
- money normalization through `src/core/common/money.py`
- durable write-side SQL `NUMERIC(18, 2)` columns in `order_events` and `idempotency_records`

Remaining future work should focus on canonical fingerprint formatting and domain-specific money policy only if the domain grows beyond the current order/payment baseline.

---

## Summary

The project will stop using `float` for money-like values before the durable write-side baseline grows larger.

This decision was made because Stage 3.5 shifts the project from short-lived in-memory correctness toward durable persistence, replay trust, and future schema hardening.

In that setting, approximate float-based money representation is no longer an acceptable baseline.

The decision has been accepted and implemented at the baseline level through `Decimal` in the domain event model and `NUMERIC(18, 2)` in the durable write-side PostgreSQL schema.
