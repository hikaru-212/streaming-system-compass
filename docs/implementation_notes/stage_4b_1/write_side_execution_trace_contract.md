# Stage 4B.1 — Write-Side Execution Trace Contract

[← Write-side execution characterization](write_side_execution_characterization.md)

## Status

```text
PR4 write-side execution characterization
= complete and accepted

PR5 immutable trace contract
= frozen by the accepted contract decision

PR6 traced execution integration
= not implemented by this PR
```

This note records the accepted producer-specific PR5 contract. PR4 is the
source-grounded execution-topology evidence for this vocabulary. PR5 defines no
traced-delivery API and does not instrument the production write side.

## 1. Responsibility

`PostgresWriteSideExecutionTrace` owns only:

```text
actual ValidationPlacement
+ ordered bounded execution checkpoints
```

The trace describes one `create_order(...)` or `pay_order(...)` invocation that
returns its current primary result. It does not interpret that result, describe
another invocation, or establish relationships among attempts.

The contract is immutable and in-memory only. It contains an existing
`ValidationPlacement` and a non-empty tuple of typed checkpoints. Its
`terminal_checkpoint` property is derived from the tuple's final member and is
not stored independently.

The intended future consumption model is:

```text
PostgresWriteSideExecution
= PostgresWriteSideResult
+ PostgresWriteSideExecutionTrace
```

The trace records which bounded execution topology was traversed. The primary
result records how the producer execution ultimately ended. PR5 defines only
the trace side and does not make the trace a standalone authoritative
transaction-finality artifact.

## 2. Checkpoint Vocabulary

The implemented checkpoints are:

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

A `*_RETURNED` checkpoint means that the bounded operation returned normally.
It does not require the operation to return a typed value and does not preserve
or imply a favorable result verdict.

Checkpoint-specific meanings are:

- `PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED` applies only to PRE execution and
  means that the preliminary check returned. It is not authoritative
  business-UOW idempotency evidence.
- `ACCEPTED_HISTORY_OBSERVED` means the accepted-history load returned. The
  returned history may be empty, and the checkpoint does not claim global
  completeness.
- `VALIDATION_RETURNED` means the validation decision returned. It does not
  imply `ALLOW`.
- `BUSINESS_UOW_REACHED` means that guarded UOW entry returned. It is not an
  exact PostgreSQL `BEGIN` timestamp.
- `AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED` means the business-UOW
  idempotency check returned. It preserves checkpoint provenance, not the
  idempotency verdict.
- `CONCURRENCY_PREPARATION_RETURNED` means `prepare_stream()` returned. It does
  not imply lock acquisition or admission.
- `APPEND_ADMISSION_RETURNED` means `append_if_admitted()` returned. It may
  represent rejection and does not imply committed event durability.
- `IDEMPOTENCY_PERSISTENCE_RETURNED` means only that
  `PostgresIdempotencyStore.record(...)` returned normally inside the current
  business transaction. It does not establish transaction commit, durable
  idempotency authority, cross-transaction visibility, or successful
  primary-result delivery.

`CLEAN_COMMIT_RETURNED` is intentionally omitted. Normal `ACCEPTED` delivery is
caller-visible only after clean business-UOW exit and a normally returned
`commit()` call, so successful primary-result delivery already owns that final
producer-result evidence. The DiagnosticTrace retains only bounded execution
topology.

For a successful future result-plus-trace execution:

```text
trace terminal = IDEMPOTENCY_PERSISTENCE_RETURNED
+ PostgresWriteSideResult.outcome = ACCEPTED
```

Together these facts establish that idempotency persistence returned inside
the transaction and that execution subsequently completed clean UOW exit,
commit, and successful result delivery. The commit conclusion comes from the
primary result contract, never from `IDEMPOTENCY_PERSISTENCE_RETURNED` alone.

## 3. Canonical PRE_TRANSACTION Order

Every PRE trace must be a non-empty prefix of:

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

Separate preliminary and authoritative idempotency checkpoints preserve the two
different boundaries within one PRE execution. They are not separate attempts.

## 4. Canonical IN_TRANSACTION Order

Every IN trace must be a non-empty prefix of:

```text
BUSINESS_UOW_REACHED
→ AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED
→ CONCURRENCY_PREPARATION_RETURNED
→ ACCEPTED_HISTORY_OBSERVED
→ VALIDATION_RETURNED
→ APPEND_ADMISSION_RETURNED
→ IDEMPOTENCY_PERSISTENCE_RETURNED
```

The order applies without exposing whether the injected concurrency gate was
optimistic, pessimistic, or another implementation of the current gate
contract.

## 5. Structural Invariants

Construction requires:

1. an actual `ValidationPlacement`;
2. an exact tuple for `checkpoints`;
3. at least one checkpoint;
4. only `PostgresWriteSideExecutionCheckpoint` members;
5. no duplicate checkpoints; and
6. a tuple equal to a prefix of the canonical order for its placement.

The trace validates no primary-result semantics. It does not decide or check
validation action, idempotency verdict, stream verdict, append verdict, or
write-side outcome.

`terminal_checkpoint` is the final retained topology checkpoint in the trace.
It does not necessarily identify the physically final operation of the business
transaction. On accepted paths, commit occurs after the final retained trace
checkpoint and is owned by successful primary-result delivery.

## 6. Intentionally Omitted Evidence

The trace does not preserve:

- primary result outcome or accepted-event evidence;
- request, candidate, accepted-event, receipt, or outcome identities;
- idempotency, validation, stream, or append verdicts and reasons;
- validation mode, validation metadata, or arbitrary context;
- exceptions, exception text, SQL, connections, payloads, history, candidates,
  or aggregate state;
- strategy names, gate classes, lock-attempt or lock-acquisition evidence;
- `SemanticOutcome` or `DecisionReceipt` payloads;
- retry, attempt numbering, fallback, policy, or runtime action;
- cost, timings, or Stage 4B.2 measurement evidence; or
- transaction durability, rollback, cleanup, or connection disposition.

Those responsibilities remain with the current primary and nested results,
Stage 4A `SemanticOutcome`, Stage 4B `DecisionReceipt`, later retry governance,
or separately approved future contracts.

## 7. Propagated Exceptions

PR5 preserves the current boundary:

```text
currently propagating exception
→ no primary result
→ no guaranteed trace execution
```

The contract does not define partial traces, an error union, wrapper exceptions,
exception-carried traces, or generic exception capture.

## 8. Deferred Boundaries

### Typed lock evidence

Typed lock-attempt or acquisition evidence remains possible future gate
enrichment. It cannot be inferred from generic `ADMITTED` and is not present in
this contract.

### Result-plus-trace execution envelope

PR6 may define a producer-specific envelope that owns coherence between
`PostgresWriteSideResult` and this trace. PR5 introduces no execution envelope,
traced write-side API, production instrumentation, or post-commit delivery
semantics.

### Stage 4B.2

Execution checkpoints identify meaningful boundaries but contain no timing or
cost measurements. Stage 4B.2 vocabulary and measurement remain separate.

## 9. Acceptance Boundary

PR4 is complete and accepted. PR5 acceptance is limited to this immutable
producer-specific vocabulary, its structural invariants, and pure unit tests.
Traced execution, result-plus-trace coherence, production instrumentation, and
delivery failure semantics remain PR6 responsibilities.
