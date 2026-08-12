# ADR 0023: Measurement Availability Does Not Govern Business Truth

[← Back to ADR Index](README.md)

## Status

Accepted

## Implementation Status

Stage 4B.2 PR3 implements the immutable result-first availability contract.
PR4 implements the explicit production measurement collection and delivery
surface while preserving existing producer behavior. Stage 4B.2 is complete
and closed; this implementation status does not change the accepted decision.

---

## Decision Scope

This decision applies to the future explicit measurement-enabled surface for
the current PostgreSQL transactional write side. It governs how a normal
producer return is composed with Stage 4B.2 Level-A measurement evidence.

It does not change the existing legacy or traced APIs and does not govern
`PostgresWriteSideExecutionTrace` construction under ADR 0022.

## Context

Some Level-A values become complete only after the business unit of work has
finished:

```text
business-UOW elapsed
commit or rollback finalization elapsed
producer write invocation elapsed
```

PR2 proved that constructing a required final measurement artifact inside an
unfinished unit of work would change transaction semantics:

```text
measurement construction failure
→ exceptional UOW exit
→ rollback
```

That would make observation availability a condition of business success.

ADR 0022 intentionally makes final trace and traced-execution construction part
of successful current traced-call composition before commit. Its scope is
trace-specific. Measurement evidence has a different completion boundary and
must not inherit that decision automatically.

## Decision

For one normal-returning measurement-enabled PostgreSQL write execution, the
ordering is:

```text
existing legacy Result or traced Execution becomes final
→ current producer call finishes commit or rollback finalization
→ current producer call returns normally
→ producer-write-invocation timer stops
→ final measurement and delivery construction are attempted
```

If the explicitly measurement-owned final construction succeeds, delivery
contains:

```text
exact producer-returned value
+ available immutable measurement
```

If that narrowly owned construction fails after the producer returned
normally, delivery contains:

```text
exact producer-returned value
+ measurement unavailable
```

The failure must not:

- replace an accepted result;
- replace a normal typed non-accepted result;
- trigger a business rollback after normal finalization;
- reinterpret accepted-history or idempotency authority;
- mutate a traced execution or its trace; or
- escape over the already-established producer value.

The measurement-enabled owner must place only final measurement/delivery
construction inside the narrow unavailability-handling boundary. The existing
producer call remains outside it.

Therefore current producer, validation, idempotency, admission, trace, UOW,
commit, and rollback exceptions retain their existing types and propagation.
An exceptional producer execution does not manufacture a normal-return
measurement delivery.

## Result-First Ownership

The delivery envelope preserves, by identity, one of the existing values:

```text
PostgresWriteSideResult
or
PostgresWriteSideExecution
```

Measurement does not duplicate or reinterpret the nested business, validation,
admission, idempotency, accepted-event, or trace evidence.

Measurement unavailability is a delivery fact about the final Stage 4B.2
artifact. It is not a producer outcome, semantic outcome, admission result,
retry decision, or transaction status.

## Rationale

Business truth is established by the existing producer and transaction
boundaries. A later observation artifact cannot safely revoke or rewrite it.

Post-UOW construction also permits the whole producer interval and the selected
finalization interval to be complete without moving measurement correctness
inside the business transaction.

Keeping the producer call outside the construction-failure boundary prevents a
generic catch from swallowing existing exceptions. Keeping the returned value
unchanged prevents measurement availability from becoming a second business
result model.

## Alternatives Considered

### Apply ADR 0022 fail-closed ordering to measurement

Rejected. Final measurement construction needs post-UOW values. Moving that
construction before clean UOW exit would make measurement failure cause
rollback.

### Raise final measurement-construction failure after commit

Rejected. The caller could observe an exception even though an accepted write
committed, or lose a normal typed non-accepted result after rollback completed.

### Translate every producer exception into measurement unavailability

Rejected. Measurement unavailability is not an exception-normalization
mechanism. Existing producer exceptions continue to propagate.

### Fabricate zero or empty phase values when construction fails

Rejected. Zero is a valid measurement, and fabricated phase values would make
unavailable evidence appear complete.

## Consequences

### Positive

- Business commit and rollback semantics remain authoritative.
- Exact legacy and traced values remain available when measurement construction
  fails after normal producer return.
- Existing producer exceptions retain their behavior.
- Measurement availability has an explicit, typed representation.
- ADR 0022 remains intact and trace-specific.

### Negative

- A normal producer result can be delivered without the requested detailed
  measurement.
- Callers that require measurements must handle explicit unavailability.
- PR4 must keep the construction-failure boundary narrow and ordered after the
  producer call.

### Neutral but Important

This decision does not claim that measurement delivery is durable or that an
unavailable measurement can be reconstructed later.

## Non-Goals

This ADR does not introduce:

- production timing or a measurement-enabled method;
- a generic exception wrapper or generic evidence failure model;
- trace failure-behavior changes;
- commit ambiguity classification;
- persistence, migrations, event metadata, or DecisionReceipt population;
- retry, AttemptLog, policy, strategy selection, or rate limiting; or
- telemetry, sampling, or asynchronous delivery.

## Relationship to Existing Decisions

- ADR 0019 separates governance-evidence persistence failure from business
  truth. This ADR applies the same authority discipline to execution-local
  Stage 4B.2 measurement while defining its distinct synchronous boundary.
- ADR 0022 keeps current traced APIs fail-closed before commit. This ADR does
  not weaken that traced contract and does not generalize it to measurement.

## Current Decision Summary

```text
business truth
= existing producer value after current finalization

measurement delivery
= later execution-local evidence composition

measurement construction failure
!= business failure
!= permission to rewrite or hide the producer value
```
