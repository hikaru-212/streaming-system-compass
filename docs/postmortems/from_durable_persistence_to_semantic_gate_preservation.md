# From Durable Persistence to Semantic Gate Preservation

[← Back to Postmortems Index](README.md)

**Recorded on:** 2026-05-27

## Purpose

This postmortem records a Stage 3.5B PR4 implementation lesson discovered while moving the write-side flow from in-memory execution toward PostgreSQL-backed durable persistence.

The issue was not a production incident. It was an architecture drift risk caught during review:

> Persistence hardening can accidentally preserve physical transaction correctness while bypassing semantic governance.

The purpose of this note is to preserve the lesson before the implementation continues into PostgreSQL concurrency admission and future validation placement strategies.

---

## Context

Before Stage 3.5B, the in-memory write-side registry already defined the canonical semantic flow:

```text
idempotency check
→ aggregate rehydration
→ candidate event creation
→ Compass Layer 1 validation
→ admission / persistence boundary
→ accepted history update
→ idempotency record
```

That flow made one project invariant explicit:

```text
No candidate event should become accepted history without Compass Layer 1 validation.
```

Stage 3.5B then introduced durable write-side persistence in several smaller PRs:

```text
PR1 — PostgreSQL schema / local setup / migration baseline
PR2 — PostgresEventStore baseline
PR3 — PostgresIdempotencyStore baseline
PR4 — transactional semantic write-side boundary
```

PR4 introduced the PostgreSQL write-side unit of work and began wiring together:

```text
PostgresEventStore
PostgresIdempotencyStore
PostgresWriteSideUnitOfWork
PostgresTransactionalWriteSide
```

The initial PR4 implementation focus was transaction atomicity:

```text
event append and idempotency record
must commit together or roll back together
```

That focus was necessary, but not sufficient.

---

## What Almost Went Wrong

The first durable write-side design risked becoming physically correct but semantically incomplete.

It correctly focused on:

- durable event append
- durable idempotency record persistence
- shared PostgreSQL transaction boundary
- commit / rollback behavior
- no partial durable write-side result

However, if the durable flow appended accepted events without calling Compass Layer 1, the PostgreSQL path would have bypassed the semantic gate that the in-memory registry already enforced.

That would have created two different write-side meanings:

```text
in-memory registry path
→ semantic guarded

PostgreSQL durable path
→ physically transactional but semantically unguarded
```

This would have been architectural drift.

The database transaction would have protected physical consistency, but the accepted event history would no longer have been guaranteed to contain only Compass-validated candidate events.

---

## Why This Matters

The project treats accepted history as more than a database log.

Accepted history is a semantic truth boundary.

That means an event entering `order_events` is not merely "inserted data." It is a claim that the candidate event has been admitted as trusted history.

If the durable write-side bypasses Compass Layer 1:

- `order_events` becomes a durable log, but not a governed accepted history
- proof fields become stored metadata rather than verified evidence
- Compass Layer 1 remains active only in the old in-memory path
- Stage 4 `SemanticOutcome` work loses the write-side validation source it should build on
- invalid candidate events may become durable before the future error model even exists

The risk is not that PostgreSQL persistence fails.

The risk is that persistence succeeds while semantic governance is skipped.

---

## Root Cause

The root cause was not a single code bug.

It was a local optimization risk during infrastructure hardening.

When implementing persistence, the design naturally focuses on:

```text
tables
transactions
foreign keys
connection boundaries
commit
rollback
idempotency rows
```

Those are necessary physical concerns.

But this project has a higher-level invariant:

```text
accepted history must remain semantically governed
```

The initial durable implementation focused on the physical transaction boundary so strongly that it risked under-preserving the semantic gate already present in the in-memory registry.

This is a common infrastructure refactor risk:

> A durable rewrite may preserve storage mechanics while accidentally bypassing application-level semantic boundaries.

---

## Correction

PR4 should preserve the canonical semantic order in the PostgreSQL-backed write-side flow:

```text
idempotency check
→ durable accepted-history load
→ aggregate rehydration
→ candidate event creation
→ ValidationContext construction
→ Compass Layer 1 validation
→ append accepted event
→ record idempotency result
→ commit
```

The corrected PR4 direction is:

```text
PostgresTransactionalWriteSide
= transactionally safe
+ Compass-guarded
+ durable write-side baseline
```

This means:

- Compass Layer 1 participates in the durable write-side path
- validation `BLOCK` happens before append
- blocked candidate events do not enter `order_events`
- blocked requests do not enter `idempotency_records`
- accepted event append and idempotency record persistence still share one transaction
- physical append + idempotency atomicity is tested separately from validation-before-admission

---

## Boundary Clarification

This postmortem clarified three different boundaries.

### 1. Validation-before-admission

This boundary answers:

```text
Can this candidate event become accepted history?
```

If Compass returns `BLOCK`, append should not happen.

This is not primarily a rollback test, because no accepted event should have been inserted yet.

---

### 2. Physical transaction atomicity

This boundary answers:

```text
If append succeeds but idempotency record persistence fails,
does the database roll back the whole write-side result?
```

This is a true physical transaction test.

It proves:

```text
order_events
+
idempotency_records
=
one atomic durable write-side result
```

---

### 3. Concurrency admission

This boundary answers:

```text
If multiple writers compete for the same stream position,
which writer is admitted and which writer is rejected?
```

This is not solved by PR4 transaction atomicity alone.

It is deferred to PR5 and recorded separately in:

- [ADR 0010 — Separate Transaction Atomicity from Concurrency Admission](../adr/0010_transaction_atomicity_vs_concurrency_admission.md)

---

## Related Decisions

This postmortem directly led to a follow-up validation architecture decision:

- [ADR 0011 — Separate Validation Mode from Validation Placement Strategy](../adr/0011_validation_mode_vs_validation_placement.md)

The lesson showed that preserving Compass validation in the durable write-side flow is not only about enabling or disabling validation.

It also requires explicitly modeling where validation happens relative to the database transaction boundary.

This postmortem is also related to:

- [ADR 0010 — Separate Transaction Atomicity from Concurrency Admission](../adr/0010_transaction_atomicity_vs_concurrency_admission.md)

ADR 0010 records why PR4 transaction atomicity does not eliminate the need for PR5 PostgreSQL concurrency admission.

Together, the three documents form the Stage 3.5B PR4 boundary chain:

```text
Postmortem
→ persistence hardening must preserve semantic gates

ADR 0010
→ transaction atomicity is not concurrency admission

ADR 0011
→ validation mode is not validation placement
```

---

## AI-Assisted Development Lesson

This was also an AI-assisted development lesson.

AI assistance can correctly optimize a local engineering task, such as transaction atomicity, while still missing a project-specific global invariant.

The human review responsibility is to preserve the architecture-level invariant:

```text
No candidate event should become accepted history without Compass Layer 1 validation.
```

The lesson is not:

```text
AI-generated code is unreliable.
```

The better lesson is:

```text
AI-generated local solutions must be reviewed against the project’s global semantic invariants.
```

In this project, the most important invariant is not only that writes commit safely.

It is that durable accepted history remains semantically governed.

---

## Future Implications

This postmortem influences the next stages:

### PR5 — PostgreSQL Concurrency Admission

PR5 should add PostgreSQL-backed admission so the durable write-side can reject stale writers explicitly.

PR5 should not collapse admission into raw database exceptions.

---

### Future Validation Placement Strategy

After PR5, the project may support both:

```text
IN_TRANSACTION validation
```

and:

```text
PRE_TRANSACTION validation + OCC
```

This should be treated as a validation placement strategy, not as a replacement for Compass.

The distinction is recorded in ADR 0011.

---

### Stage 4 — Structured Outcomes

Stage 4 may structure validation, admission, domain, and runtime decisions into `SemanticOutcome` / `RuntimeDecision` style objects.

That work depends on the write-side flow actually producing validation decisions.

Therefore, PR4 must preserve Compass Layer 1 in the durable path before Stage 4 outcome modeling begins.

---

## Non-Goals

This postmortem does not implement:

- PostgreSQL concurrency admission
- validation result persistence
- `SemanticOutcome`
- `RuntimeDecision`
- validation placement strategy
- DAG node validation
- async audit
- production-grade locking or retry policy

Those are future implementation concerns.

This postmortem only records the architecture lesson and the correction to PR4 direction.

---

## Summary

PR4 is not only about making PostgreSQL writes atomic.

It is about making the durable write-side:

```text
transactionally safe
+
semantically guarded
```

The final lesson is:

```text
Persistence hardening must preserve Compass governance.
```

A durable write-side path is only correct for this project if it preserves the semantic gate before accepted history is mutated.
