# ADR 0022: Traced Write-Side Execution Fails Closed Before Business Commit

[← Back to ADR Index](README.md)

## Status

Accepted

## Implementation Status

Implemented by Stage 4B.1 PR6 for the current PostgreSQL write-side traced
APIs. Stage 4B.1 PR7 records the accepted decision without changing runtime
behavior.

The implementation record is:

- [Stage 4B.1 — Write-Side Traced Execution](../implementation_notes/stage_4b_1/write_side_traced_execution.md)

---

## Decision Scope

This ADR applies only to:

```text
PostgresTransactionalWriteSide.create_order_with_trace(...)
PostgresTransactionalWriteSide.pay_order_with_trace(...)
```

and their current returned envelope:

```text
PostgresWriteSideExecution
= PostgresWriteSideResult
+ PostgresWriteSideExecutionTrace
```

It does not establish a repository-wide rule for every current or future
`DiagnosticTrace` producer. Snapshot-assisted trace contracts and any later
producer remain independently reviewable.

---

## Context

Stage 4B.1 PR5 established the immutable producer-specific write-side trace
contract. PR6 integrated that contract through parallel traced APIs while
preserving the existing untraced APIs and shared PRE_TRANSACTION and
IN_TRANSACTION execution algorithms.

For accepted traced execution, the current ordering is:

```text
business operations
→ final trace validation
→ PostgresWriteSideResult construction
→ PostgresWriteSideExecution construction
→ return expression ready
→ business UOW __exit__
→ commit
→ caller delivery
```

Python evaluates the return expression inside the unit-of-work body before the
context manager exits. The current implementation uses that ordering so no
final trace or execution-envelope constructor remains to run after commit.

Therefore:

```text
trace invariant failure
or execution-envelope invariant failure
→ exception before clean UOW exit
→ exceptional UOW exit
→ rollback
→ no caller-visible PostgresWriteSideExecution
```

The architecture must preserve whether trace correctness is part of successful
traced-call correctness or merely best-effort diagnostic enrichment.

---

## Decision

The current PostgreSQL `*_with_trace(...)` APIs use:

```text
STRICT / FAIL-CLOSED SYNCHRONOUS TRACE COMPOSITION
```

A traced call is not successfully completed unless:

```text
valid PostgresWriteSideResult
+ valid final PostgresWriteSideExecutionTrace
+ valid PostgresWriteSideExecution
```

have been constructed before clean business-unit-of-work exit.

For an accepted traced execution, a trace invariant or execution-envelope
invariant failure propagates before commit and causes exceptional rollback. The
caller receives neither a primary result nor a traced execution envelope.

The existing untraced APIs remain outside this decision's diagnostic-construction
path:

```text
create_order(...)
pay_order(...)
```

They construct no trace collector or execution envelope and therefore do not
take on the traced APIs' availability trade-off.

---

## Synchronous Composition Is Not Atomic Persistence

The decision does not make diagnostic artifacts part of PostgreSQL durable
state.

```text
PostgresWriteSideResult
PostgresWriteSideExecutionTrace
PostgresWriteSideExecution
= in-memory Python artifacts
```

Only business state such as:

```text
accepted event
+ idempotency record
```

participates in the PostgreSQL business transaction.

The pre-commit construction order provides a strict synchronous return
contract. It does not atomically store Result + Trace, add trace durability, or
make `IDEMPOTENCY_PERSISTENCE_RETURNED` evidence of transaction commit.

---

## Rationale

The traced APIs promise one coherent normal-return artifact rather than an
optional trace attached after business success.

Constructing and validating the final trace and envelope before commit prevents
this caller-visible state:

```text
business mutation committed
+ required synchronous trace construction failed
→ traced call raises without delivering its promised artifact
```

Failing before clean UOW exit keeps the traced API's success condition explicit:

```text
successful traced delivery
→ valid Result + valid Trace + valid Execution envelope
```

This decision does not claim that diagnostics are business authority. It says
only that trace correctness is part of the current synchronous traced-call
contract.

---

## Consequences

### Positive

- A caller never receives a successful traced execution with a missing or
  invalid trace.
- Result/trace terminal compatibility is validated before delivery.
- Ordinary post-commit diagnostic-construction failure is excluded from the
  current accepted path.
- The traced APIs expose one strong and testable synchronous contract.
- The untraced APIs retain their existing behavior and availability boundary.

### Negative

- A systematic tracing or instrumentation invariant defect can reduce
  availability of traced writes.
- An otherwise-valid business path may roll back because the traced API could
  not construct its promised diagnostic artifact.
- Future instrumentation changes must preserve canonical ordering and envelope
  compatibility or fail before commit.

The accepted trade-off is:

```text
otherwise-valid traced business path
→ trace or envelope invariant failure
→ rollback
→ no caller-visible Result or Execution
```

### Neutral but Important

- Commit failure still prevents delivery of an already-constructed in-memory
  execution; this ADR does not classify business commit ambiguity.
- Currently propagating producer exceptions still propagate without guaranteed
  trace delivery.
- Trace evidence remains topology evidence, not retry authorization, policy,
  transaction durability, or business authority.

---

## Alternative Considered — Best-Effort Tracing

Under a best-effort model:

```text
business mutation may commit
even when diagnostic trace construction fails
```

This alternative is rejected for the current synchronous PostgreSQL traced
APIs and is not implemented by this ADR.

Adopting best-effort behavior would require:

- a concrete production-consumer requirement;
- a separate contract for unavailable, incomplete, or failed trace evidence;
- explicit reconsideration of caller-visible result and error semantics;
- review of whether a new API or asynchronous transport is required; and
- focused transaction and delivery tests for the new boundary.

Best-effort behavior must not be introduced by silently catching trace
construction failures or moving required envelope construction after commit.

---

## Revisit Conditions

Revisit this decision if a concrete production consumer demonstrates that:

```text
preserving business-write availability
must take precedence over
guaranteed synchronous traced delivery
```

or if trace evidence becomes asynchronous or explicitly best effort rather
than part of the synchronous `*_with_trace(...)` return contract.

Any revisit must decide the new evidence-unavailability contract and
caller-visible semantics before changing transaction ordering.

---

## Non-Goals

This ADR does not decide or introduce:

- same-execution provenance identity;
- `execution_id`, `attempt_id`, or an opaque provenance token;
- trace persistence, serialization, retention, or publication;
- `SemanticOutcome + Trace` composition;
- `DecisionReceipt` construction or orchestration;
- retry candidacy, retry authorization, or `AttemptLog`;
- measurement or cost evidence;
- business commit-ambiguity classification or reconciliation;
- exception-carried traces;
- snapshot traced-resolver integration; or
- a generic cross-producer `DiagnosticTrace` abstraction.

---

## Relationship to Existing Decisions

- ADR 0010 keeps transaction atomicity separate from concurrency admission.
  This ADR does not change either boundary; it decides when the current traced
  return artifact must be valid relative to business commit.
- ADR 0016 keeps `DecisionReceipt`, diagnostic traces, application logging, and
  attempt records separate. This ADR preserves that separation.
- ADR 0019 keeps receipt materialization and persistence failure separate from
  the authoritative business result. This ADR adds no receipt orchestration.
- ADR 0021 keeps snapshot-specific runtime expansion evidence-gated. This ADR
  does not apply the PostgreSQL write-side decision to snapshot producers.

---

## Current Decision Summary

```text
current PostgreSQL *_with_trace APIs
= strict / fail-closed synchronous composition

successful traced call
= valid Result + valid final Trace + valid Execution before clean UOW exit

trace or envelope invariant failure before commit
= exception + rollback + no traced delivery

Result / Trace / Execution
= in-memory, not transaction-durable

best-effort tracing
= rejected for the current APIs
+ requires a separate future consumer and contract decision
```
