# Stage 4B.1 — Write-Side Traced Execution

[← Write-side trace contract](write_side_execution_trace_contract.md)

## Status

```text
PR4 executable characterization
= complete and accepted

PR5 immutable write-side DiagnosticTrace contract
= complete and accepted

PR6 design
= frozen and implemented

PR6 production integration
= complete

PR6 pure-unit validation
= complete / 82 focused PR5 + PR6 tests passed

PR6 PostgreSQL validation
= complete through repository-wide test execution

PR6 overall acceptance
= accepted / 1650 tests passed in 30.93s
```

This note records the implemented design for connecting the accepted PR5 trace
contract to the current PostgreSQL write side. Production integration, focused
pure-unit evidence, and PostgreSQL integration coverage are complete. Final
repository-wide validation executed the full `tests` tree successfully:

```text
pytest tests -q
1650 passed in 30.93s
```

PR6 is accepted for the current repository state.

## 1. Purpose and Responsibility

PR6 adds bounded diagnostic delivery for one current write-side execution:

```text
existing PostgresWriteSideResult
+ accepted PostgresWriteSideExecutionTrace
→ PostgresWriteSideExecution
```

The primary result continues to own how the producer execution ended. The trace
owns only which bounded execution topology was traversed. The execution envelope
composes those two artifacts without becoming a new source of business truth,
transaction durability, retry authorization, or runtime policy.

The implemented PR6 scope is limited to:

```text
immutable producer-specific execution envelope
invocation-local checkpoint collection
shared-core checkpoint instrumentation
parallel traced write-side APIs
narrow terminal compatibility
pre-commit construction safety
focused unit and PostgreSQL integration evidence
```

PR6 does not change accepted-history authority, idempotency semantics,
validation placement, admission behavior, transaction ownership, current
result semantics, or current exception propagation.

## 2. Accepted PR5 Boundary

The accepted producer-specific trace stores exactly:

```text
PostgresWriteSideExecutionTrace
├── validation_placement
└── checkpoints
```

and derives:

```text
terminal_checkpoint = checkpoints[-1]
```

Every trace is a non-empty exact canonical prefix for its actual
`ValidationPlacement`. The exact checkpoint vocabulary is:

```text
PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED
ACCEPTED_HISTORY_OBSERVED
VALIDATION_RETURNED
BUSINESS_UOW_REACHED
AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED
CONCURRENCY_PREPARATION_RETURNED
APPEND_ADMISSION_RETURNED
IDEMPOTENCY_PERSISTENCE_RETURNED
```

Before the PR5 freeze, `CLEAN_COMMIT_RETURNED` was considered and intentionally
omitted. It is not part of the accepted checkpoint vocabulary and PR6 must not
restore it under that or another name.

### PRE_TRANSACTION canonical sequence

```text
PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED
→ ACCEPTED_HISTORY_OBSERVED
→ VALIDATION_RETURNED
→ BUSINESS_UOW_REACHED
→ AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED
→ CONCURRENCY_PREPARATION_RETURNED
→ APPEND_ADMISSION_RETURNED
→ IDEMPOTENCY_PERSISTENCE_RETURNED
```

### IN_TRANSACTION canonical sequence

```text
BUSINESS_UOW_REACHED
→ AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED
→ CONCURRENCY_PREPARATION_RETURNED
→ ACCEPTED_HISTORY_OBSERVED
→ VALIDATION_RETURNED
→ APPEND_ADMISSION_RETURNED
→ IDEMPOTENCY_PERSISTENCE_RETURNED
```

PR6 adds no checkpoint, stored trace field, serializer, persistence behavior,
or transaction-finality classification to this contract.

## 3. Current Execution Model

### PRE_TRANSACTION

```text
request signature
→ preliminary idempotency check
→ preliminary history load
→ preliminary read-transaction rollback
→ aggregate reconstruction and candidate construction
→ validation outside the business UOW
→ business UOW entry
→ authoritative idempotency check
→ concurrency preparation
→ append-time admission / continuity arbitration
→ idempotency persistence
→ accepted result construction
→ clean UOW exit / commit
→ result delivery
```

### IN_TRANSACTION

```text
request signature
→ business UOW entry
→ authoritative idempotency check
→ concurrency preparation
→ accepted-history load
→ aggregate reconstruction and candidate construction
→ validation inside the business UOW
→ append-time admission / continuity arbitration
→ idempotency persistence
→ accepted result construction
→ clean UOW exit / commit
→ result delivery
```

Normal non-accepted returns preserve their current early-exit placement and
explicit business-UOW rollback where applicable. Currently propagating
exceptions continue to propagate through the existing UOW lifecycle.

## 4. Checkpoint Recording Semantics

The stable recording rule is:

```text
bounded operation returns normally
→ checkpoint is recorded immediately
→ returned verdict is interpreted afterward
```

For example:

```text
prepare_stream(...) returns
→ CONCURRENCY_PREPARATION_RETURNED
→ then inspect whether preparation admitted the stream

append_if_admitted(...) returns
→ APPEND_ADMISSION_RETURNED
→ then inspect whether append admission admitted or rejected the candidate
```

`CONCURRENCY_PREPARATION_RETURNED` means only that `prepare_stream(...)`
returned normally. Optimistic preparation may be an intentional admitted no-op.
Pessimistic preparation may attempt a transaction-scoped advisory lock and may
return `LOCK_TIMEOUT`. The checkpoint does not mean that a lock was acquired or
that preparation admitted the stream.

`APPEND_ADMISSION_RETURNED` means only that `append_if_admitted(...)` returned
normally. It may represent `STALE_WRITE` or another typed rejection and does
not establish durable accepted-history authority.

`IDEMPOTENCY_PERSISTENCE_RETURNED` means only that
`PostgresIdempotencyStore.record(...)` returned normally inside the current
business transaction. It does not establish transaction commit, durable
idempotency authority, cross-transaction visibility, or successful
primary-result delivery.

All checkpoint instrumentation must immediately follow its bounded operation.
Verdict interpretation and the current normal-return branch remain afterward.

Checkpoint ownership is fixed at these placement-specific source boundaries:

| Checkpoint | Bounded operation that must return first | Placement |
|---|---|---|
| `PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED` | preliminary `PostgresIdempotencyStore.check(...)` | PRE only |
| `ACCEPTED_HISTORY_OBSERVED` | accepted-history `PostgresEventStore.load(...)` | PRE and IN |
| `VALIDATION_RETURNED` | `ValidationRuntime.decide(...)` | PRE and IN |
| `BUSINESS_UOW_REACHED` | guarded `PostgresWriteSideUnitOfWork.__enter__()` | PRE and IN |
| `AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED` | business-UOW `PostgresIdempotencyStore.check(...)` | PRE and IN |
| `CONCURRENCY_PREPARATION_RETURNED` | `ConcurrencyGate.prepare_stream(...)` | PRE and IN |
| `APPEND_ADMISSION_RETURNED` | `ConcurrencyGate.append_if_admitted(...)` | PRE and IN |
| `IDEMPOTENCY_PERSISTENCE_RETURNED` | `PostgresIdempotencyStore.record(...)` | PRE and IN accepted prefixes |

`PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED` is not authoritative business-UOW
idempotency evidence. `ACCEPTED_HISTORY_OBSERVED` may represent empty history
and does not claim global completeness. `VALIDATION_RETURNED` does not imply
`ALLOW`. `BUSINESS_UOW_REACHED` means guarded UOW entry returned; it is not an
exact PostgreSQL `BEGIN` timestamp.

### IN history observation

For `IN_TRANSACTION`, `ACCEPTED_HISTORY_OBSERVED` corresponds to successful
history loading itself, not successful completion of aggregate reconstruction.
Current helper behavior combines:

```text
history load
→ aggregate reconstruction through OrderAggregate.apply(...)
```

The implementation distinguishes those boundaries only as far as required to
record:

```text
history load returns
→ ACCEPTED_HISTORY_OBSERVED
→ aggregate reconstruction may continue or still raise
```

This does not authorize a wider aggregate-reconstruction redesign.

## 5. Invocation-Local Trace Collector

Collection uses one private collector per traced invocation:

```text
one invocation
→ one collector
→ actual ValidationPlacement
→ latest valid immutable trace prefix
```

The collector is not stored on `PostgresTransactionalWriteSide`, shared across
calls, global, serialized, or persisted.

For each checkpoint, the collector must:

1. extend the current candidate checkpoint tuple;
2. construct `PostgresWriteSideExecutionTrace` with the actual placement and
   candidate tuple;
3. rely on the accepted PR5 constructor to validate type, non-emptiness,
   duplicates, order, and placement-specific canonical-prefix coherence; and
4. retain the resulting latest valid immutable trace.

Conceptually:

```text
current validated prefix
+ new checkpoint
→ PostgresWriteSideExecutionTrace(...)
→ latest valid trace
```

PR6 does not duplicate the PRE and IN canonical sequences in a second private
validator. The accepted PR5 constructor remains the structural authority, so
duplicate, skipped, reordered, or wrong-placement checkpoints fail at the
instrumentation boundary rather than after execution completes.

The ownership rule is:

```text
one checkpoint
= one instrumentation site per placement path
= one invocation-local collector
```

Current production has no internal retry or repeated checkpoint phase. If a
later implementation legitimately repeats a PR5 phase within one execution,
the PR5 canonical-prefix contract requires human re-review; the current
implementation does not silently permit duplicate checkpoints.

## 6. Result + Trace Envelope

PR6 adds the immutable producer-specific envelope:

```text
PostgresWriteSideExecution
├── result: PostgresWriteSideResult
└── trace: PostgresWriteSideExecutionTrace
```

Those are its only fields. The envelope belongs beside the current producer
result unless implementation evidence requires a different cycle-free
placement.

The envelope does not add or duplicate `SemanticOutcome`, `DecisionReceipt`,
retry decision, strategy, policy, cost, timing, metadata, arbitrary context, or
transaction-durability evidence.

## 7. Bounded Result / Trace Coherence

`PostgresWriteSideExecution` must not become a second
`PostgresWriteSideResult` validator. Its constructor validates the two field
types and enforces only narrow source-grounded compatibility among:

```text
trace.validation_placement
+ PostgresWriteSideOutcome
+ trace.terminal_checkpoint
```

The invocation-local collector is created from the writer's actual
`ValidationPlacement`. The focused integration suite asserts that emitted
`trace.validation_placement` matches the placement used for dispatch. That
coverage executed successfully as part of the final repository-wide
`pytest tests -q` run.

The existing primary result remains responsible for its business-result
evidence. Nested semantics such as `IdempotencyVerdict`,
`ValidationDecision.action`, `StreamAdmissionResult.admitted`,
`AdmissionResult.admitted`, and accepted-event presence remain existing result
responsibilities and focused PR6 integration-test evidence. The envelope does
not parse result reasons, reinterpret payloads, or reproduce those nested
invariants.

Current normal-return terminal compatibility is:

### PRE_TRANSACTION

| `PostgresWriteSideOutcome` | Allowed `terminal_checkpoint` |
|---|---|
| `REPLAY` | `PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED` or `AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED` |
| `CONFLICT` | `PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED` or `AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED` |
| `VALIDATION_BLOCKED` | `VALIDATION_RETURNED` |
| `ADMISSION_REJECTED` | `CONCURRENCY_PREPARATION_RETURNED` or `APPEND_ADMISSION_RETURNED` |
| `ACCEPTED` | `IDEMPOTENCY_PERSISTENCE_RETURNED` |

### IN_TRANSACTION

| `PostgresWriteSideOutcome` | Allowed `terminal_checkpoint` |
|---|---|
| `REPLAY` | `AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED` |
| `CONFLICT` | `AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED` |
| `VALIDATION_BLOCKED` | `VALIDATION_RETURNED` |
| `ADMISSION_REJECTED` | `CONCURRENCY_PREPARATION_RETURNED` or `APPEND_ADMISSION_RETURNED` |
| `ACCEPTED` | `IDEMPOTENCY_PERSISTENCE_RETURNED` |

A structurally valid PR5 prefix does not prove that a current normal-returning
primary result exists at that terminal. For example:

```text
PRE history-only
PRE business-UOW-only
IN history-only
```

remain valid structural prefixes but are not current normal Result + Trace
envelope terminals. PR6 does not manufacture synthetic results for those
prefixes.

## 8. Mandatory Pre-Commit Construction

No accepted traced execution constructs its trace or envelope in the outer
dispatcher after a placement-specific execution method has returned from a
successful business UOW.

Accepted finalization must occur while execution is still inside the business
UOW body:

```text
idempotency persistence returns
→ IDEMPOTENCY_PERSISTENCE_RETURNED is validated
→ PostgresWriteSideResult(ACCEPTED) is constructed
→ PostgresWriteSideExecution is constructed and coherence-validated
→ the return expression is fully evaluated
→ PostgresWriteSideUnitOfWork.__exit__() runs
→ commit() runs
→ caller receives the already-constructed execution
```

Python evaluates the return expression inside the `with` body before invoking
the context manager's `__exit__`. PR6 uses that ordering to eliminate ordinary
post-commit diagnostic-construction work.

Consequences:

```text
trace validation failure before commit
→ exception
→ exceptional UOW exit
→ rollback

execution-envelope coherence failure before commit
→ exception
→ exceptional UOW exit
→ rollback

commit failure
→ already-constructed execution is not delivered

successful commit
→ no trace or envelope constructor remains to run afterward
```

This avoids:

```text
business mutation committed
+ diagnostic construction failure
→ misleading generic caller failure
```

PR6 does not construct the accepted trace or envelope after commit. Any later
change that cannot preserve this ordering requires human review.

### Synchronous composition is not atomic persistence

`PostgresWriteSideResult`, `PostgresWriteSideExecutionTrace`, and
`PostgresWriteSideExecution` are Python in-memory artifacts. They do not
participate in the PostgreSQL business transaction and are not durably or
atomically stored with it. Only business state such as the accepted event and
idempotency record participates in that transaction.

The traced APIs instead establish a synchronous fail-closed return boundary:

```text
valid Result
+ valid Trace
+ valid PostgresWriteSideExecution
= synchronously composed before clean UOW exit

accepted event
+ idempotency record
= durably committed by the business transaction
```

Trace or envelope construction failure therefore occurs before commit and
drives exceptional UOW rollback. A commit exception prevents caller-visible
execution delivery, but PR6 does not classify the transaction as `COMMITTED`,
`NOT_COMMITTED`, or `UNKNOWN` and does not reinterpret the exception as a known
business failure.

## 9. Normal-Return Finalization

Private function names remain an implementation detail, but every normal-return
site follows this conceptual shape:

```text
result = PostgresWriteSideResult(...)

if no trace collector:
    return result

return PostgresWriteSideExecution(
    result=result,
    trace=current validated trace,
)
```

For normal returns inside a business UOW, Result + Trace finalization occurs
inside the UOW before context exit. Existing explicit rollback remains before
each non-accepted return. For PRE early returns outside the business UOW,
traced finalization may occur at the existing normal-return boundary.

No outer post-return wrapper is required or authorized for accepted envelope
construction.

## 10. Public API Preservation

Existing APIs remain unchanged:

```text
create_order(...) -> PostgresWriteSideResult
pay_order(...) -> PostgresWriteSideResult
```

PR6 adds parallel APIs:

```text
create_order_with_trace(...) -> PostgresWriteSideExecution
pay_order_with_trace(...) -> PostgresWriteSideExecution
```

Legacy and traced entry points share the same PRE and IN write algorithms. PR6
does not duplicate either algorithm.

Legacy calls:

- create no trace collector;
- perform no trace or envelope construction;
- retain their existing arguments and return type;
- retain current result values and nested evidence;
- retain current call ordering, transaction behavior, and commit/rollback
  ownership; and
- retain current exception propagation.

## 11. Exception Boundary

PR6 preserves:

```text
currently propagating exception
→ still propagates
→ no PostgresWriteSideResult
→ no guaranteed PostgresWriteSideExecution delivery
```

PR6 does not add an exception wrapper, exception-carried trace, callback, trace
sink, persistence transport, catch-all result conversion, operational event, or
automatic error translation merely to guarantee diagnostic delivery.

## 12. Authority, Commit, and Retry Boundaries

The accepted ownership remains:

```text
PostgresWriteSideExecutionTrace
= bounded execution topology

successful PostgresWriteSideResult delivery
= clean committed producer completion
```

Therefore:

```text
IDEMPOTENCY_PERSISTENCE_RETURNED
≠ transaction committed

PostgresWriteSideExecution
≠ RetryDecision

DiagnosticTrace
≠ AttemptLog

one invocation
= one execution

later invocation
= another execution
```

The trace and envelope add no transaction-durability enum. Successful clean
commit finality is established by successful primary-result delivery. The trace
adds bounded topology context only; commit finality never follows from
`IDEMPOTENCY_PERSISTENCE_RETURNED` or from the trace itself.

PR6 does not authorize another attempt, relate attempts, select an execution
strategy, or recover a failed process.

## 13. Validation Evidence

Focused PR5-contract and PR6 pure-unit validation completed during the PR6
implementation review:

```text
./.venv/bin/python -m pytest -q \
  tests/unit/pipeline/transactional/test_postgres_write_side_execution_trace.py \
  tests/unit/pipeline/transactional/test_postgres_write_side_traced_execution_unit.py

82 passed in 0.11s
```

The unit evidence covers the immutable envelope, bounded terminal
compatibility, invocation-local collector behavior, shared legacy/traced
execution paths, construction-before-commit ordering, construction-failure
rollback, commit-failure nondelivery, and history-checkpoint placement.

The committed focused PostgreSQL suite contains 15 legacy/traced cases for PRE
and IN normal-return prefixes, primary-result equivalence, persisted row
effects, and idempotency-record failure rollback.

Final repository-wide validation executed the complete `tests` tree, including
the focused PostgreSQL traced-execution suite, PR4 characterization, and
existing regression coverage:

```text
pytest tests -q

1650 passed in 30.93s
```

No test failure or skip is reported in the final run. This full-suite result is
the current PR6 acceptance evidence.

## 14. Explicit Non-Goals

PR6 does not add or change:

- current business authority or accepted-history authority;
- existing write-side result semantics;
- `SemanticOutcome` or `DecisionReceipt` contracts;
- trace persistence or serialization;
- retry, attempt count, `AttemptLog`, fallback, or strategy selection;
- `RuntimeDecisionPolicy` or retry governance;
- runtime action;
- measurement, cost, timing, or Stage 4B.2 evidence;
- observability-platform integration;
- business-UOW liveness policy;
- `statement_timeout`, `lock_timeout`, or
  `idle_in_transaction_session_timeout` policy;
- deadlock-recovery or commit-ambiguity redesign;
- process-crash recovery or reconciliation;
- transaction durability, rollback, or connection-disposition enums;
- migrations, database configuration, or dependencies; or
- a generic cross-producer `DiagnosticTrace` abstraction.

The deferred business-UOW bounded-liveness working material remains outside
PR6 and non-authoritative.

## 15. PR7 Handoff

PR6 establishes compatibility between the actual validation placement, primary
outcome, and terminal checkpoint for artifacts produced through one traced
invocation. It does not prove historical provenance for arbitrary manual
construction. A caller could manually combine a result from one execution with
a structurally compatible trace from another. PR7 or a later consumer review
must keep these questions separate:

```text
compatibility
= could these artifacts belong together?

provenance
= did these artifacts actually come from the same execution?
```

PR6 introduces no `execution_id`, `attempt_id`, or producer-certification
mechanism to answer the second question.

The parallel traced APIs also intentionally use strict, fail-closed synchronous
composition. A systematic trace invariant or instrumentation defect can roll
back an otherwise valid traced execution and prevent caller-visible result
delivery. The legacy APIs do not create tracing artifacts and are unaffected by
that availability trade-off. PR7 should record the implication and defer any
future best-effort tracing model to a separately justified consumer decision;
it must not retroactively change the accepted PR6 contract.

Finally, trusted producer-returned Result + Trace may support a later
consumer-driven `SemanticOutcome` + Trace composition. PR6 does not introduce
that envelope, an additional coherence validator, caller-independent pairing,
or `DecisionReceipt` orchestration. The likely reassessment point remains Stage
4C entry or another concrete consumer review.

## 16. Implementation Sequence and Remaining Acceptance

The PR6 delivery sequence is:

```text
Commit 1
= documentation / design freeze — complete

Commit 2
= production envelope
+ invocation-local collector
+ shared checkpoint instrumentation
+ parallel traced APIs
+ focused unit coverage
= complete

Commit 3
= focused PostgreSQL traced-execution integration suite
= complete / validated within the repository-wide test run

Commit 4
= PR6 documentation closeout
+ Stage 4B.1 status update
= this change
```

Current authority is:

```text
PR6 design
= frozen

PR6 production integration
= complete

PR6 pure-unit validation
= complete

PR6 PostgreSQL validation
= complete

PR6 full acceptance
= accepted / 1650 tests passed in 30.93s
```

PR6 validation is complete. PR7 may now close Stage 4B.1. Any future evidence
that requires one of the following changes must still stop for human review:

- accepted trace or envelope construction after commit;
- a change to existing result semantics or exception propagation;
- a second PRE or IN business algorithm;
- duplicate or repeated checkpoints within one current invocation;
- a wider aggregate-reconstruction redesign;
- nested business-result reinterpretation in the envelope;
- generic exception capture or guaranteed exceptional trace delivery;
- retry, strategy, policy, persistence, measurement, or liveness work; or
- changes to PR4 evidence, the accepted PR5 trace contract, `SemanticOutcome`,
  or `DecisionReceipt`.
