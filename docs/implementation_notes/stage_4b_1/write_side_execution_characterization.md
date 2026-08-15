# Stage 4B.1 — Write-Side Execution Characterization

[← Back to Stage 4B.1](README.md)

## Status

```text
this note
= accepted PR4 source-grounded characterization

production write-side trace contract
= defined later by PR5; not owned by this note

characterization scenarios
= ten focused PostgreSQL integration scenarios complete

focused executable characterization
= complete

PR5 relationship
= accepted execution-topology evidence baseline
```

This note preserves the PR4 characterization of the current PostgreSQL
write-side execution topology established before the producer-specific PR5
contract. It is not a public trace vocabulary, does not authorize a traced API,
and does not change current write-side behavior.

## 1. Purpose

The current write-side result, Stage 4A `SemanticOutcome`, and Stage 4B
`DecisionReceipt` already preserve terminal outcome and compact evidence. They
do not preserve enough topology to distinguish where one execution ran or which
bounded checkpoints preceded its terminal result.

The missing evidence is principally:

```text
actual validation placement
preliminary vs authoritative idempotency provenance
business-unit-of-work reach
ordered bounded execution checkpoints
producer-specific terminal checkpoint
```

This characterization established which of those distinctions are grounded in
current source and executable tests. It deliberately did not decide the later
PR5 contract.

## 2. Source-Grounded Baseline

The current authority for this characterization is:

- [`postgres_write_side.py`](../../../src/pipeline/transactional/postgres_write_side.py);
- [`postgres_write_side_config.py`](../../../src/pipeline/transactional/postgres_write_side_config.py);
- [`postgres_admission.py`](../../../src/pipeline/transactional/postgres_admission.py);
- [`postgres_unit_of_work.py`](../../../src/pipeline/transactional/postgres_unit_of_work.py);
- [`postgres_idempotency_store.py`](../../../src/storage/postgres_idempotency_store.py);
- [`postgres_event_store.py`](../../../src/storage/postgres_event_store.py);
- [`runtime.py`](../../../src/compass/transition/runtime.py);
- [`write_side_outcome_mapping.py`](../../../src/compass/runtime/write_side_outcome_mapping.py);
- [`write_side_decision_receipt_mapping.py`](../../../src/compass/runtime/write_side_decision_receipt_mapping.py);
- [`test_postgres_write_side.py`](../../../tests/integration/pipeline/transactional/test_postgres_write_side.py);
- [`test_postgres_pessimistic_admission.py`](../../../tests/integration/pipeline/transactional/test_postgres_pessimistic_admission.py).

Current source governs implemented ordering when historical ADR language is
broader or describes future recovery behavior.

## 3. Current Concrete Compositions

### PRE_TRANSACTION + OCC

The default `PostgresTransactionalWriteSide` composition is:

```text
ValidationPlacement.PRE_TRANSACTION
+ default admission-gate factory
→ PostgresOptimisticAdmissionGate
```

The optimistic gate does not pre-lock the stream. Its append delegates to the
event store, whose current-version and continuity checks arbitrate OCC at the
append boundary.

### IN_TRANSACTION + concrete pessimistic admission

The current injection seam permits:

```text
ValidationPlacement.IN_TRANSACTION
+ admission-gate factory
→ PostgresPessimisticAdmissionGate(
      connection=uow.connection,
      event_store=uow.event_store,
  )
```

This composition is executable without production changes. The Stage 4B.1
characterization suite exercises that exact full-write-side composition.

### Effective placement and validation mode

`PostgresWriteSideConfig.validation_placement` controls dispatch between the
two orchestration methods. `PostgresWriteSideConfig.validation_mode` is
declared, but current orchestration does not pass it into or otherwise change
the injected `ValidationRuntime`. Effective validation mode therefore comes
from the runtime's actual `ValidationDecision`, not from the config field.

This experiment records the discrepancy and does not repair it.

### Mixed-strategy coexistence boundary

Strategy selection is per `PostgresTransactionalWriteSide` instance rather than
process-global. Separate writer instances can therefore use separate PostgreSQL
connections and different valid compositions at the same time:

```text
writer A
= PRE_TRANSACTION + PostgresOptimisticAdmissionGate

writer B
= IN_TRANSACTION + PostgresPessimisticAdmissionGate
```

The current production bootstrap does not compose either PostgreSQL write-side
variant, so this is a constructable runtime composition rather than a claim
about the current deployed graph. No singleton, global strategy registry, or
runtime guard makes the two compositions mutually exclusive.

The pessimistic advisory lock is cooperative. It protects against participants
that acquire the same transaction-scoped advisory lock, but the optimistic gate
does not acquire that lock. Mixed-strategy correctness therefore still depends
on the authoritative idempotency boundary and append-time stream-position
arbitration.

## 4. One Execution Boundary

One Stage 4B.1 write-side execution is one call to:

```text
create_order(...)
```

or:

```text
pay_order(...)
```

The execution ends when that call returns its current
`PostgresWriteSideResult` or propagates its current exception.

PRE's preliminary read phase and later authoritative business UOW are two
checkpoints inside one execution. They are not two attempts. A later invocation
after conflict, timeout, replay, or operator action is a different execution;
its relationship to this execution belongs to Stage 4E `AttemptLog` and retry
governance.

## 5. PRE_TRANSACTION + OCC Topology

The current successful-prefix order is:

```text
request signature
→ preliminary idempotency check
→ preliminary accepted-history observation
→ close preliminary read transaction
→ aggregate rehydration and candidate preparation
→ validation outside the business UOW
→ business UOW reached
→ authoritative idempotency check
→ optimistic concurrency preparation
→ append-time OCC and continuity arbitration
→ idempotency persistence
→ clean UOW commit
→ ACCEPTED returned
```

Important boundaries:

- preliminary REPLAY or CONFLICT returns before history loading, validation,
  the business UOW, stream preparation, or append;
- validation BLOCK returns before the business UOW;
- authoritative REPLAY or CONFLICT occurs only after validation ALLOW and after
  the business UOW is reached;
- an append-time stale result rolls back and returns
  `ADMISSION_REJECTED`; current source does not reload authority, retry, or
  start a second attempt;
- append success and idempotency persistence are transaction-local until the
  clean UOW exit commits;
- ACCEPTED reaches the caller only after the current `commit()` call returns.

The append translator converts its enumerated stale-write, stream-position,
lock, and storage failures into typed `AdmissionResult` verdicts. Other store,
validation, domain, idempotency, transaction, and commit exceptions continue to
propagate without a `PostgresWriteSideResult`.

## 6. IN_TRANSACTION + Concrete Pessimistic Topology

The current successful-prefix order is:

```text
request signature
→ business UOW reached
→ authoritative idempotency check
→ concrete pessimistic stream preparation
→ protected accepted-history observation
→ aggregate rehydration and candidate preparation
→ validation inside the UOW while the transaction-scoped lock is held
→ append-time continuity arbitration
→ idempotency persistence
→ clean UOW commit and lock release
→ ACCEPTED returned
```

Important boundaries:

- authoritative REPLAY or CONFLICT rolls back before gate construction,
  locking, history loading, candidate preparation, or validation;
- pessimistic lock non-acquisition returns `LOCK_TIMEOUT`, then rolls back
  before protected history loading, validation, or append;
- validation BLOCK after successful preparation rolls back before append;
- append or idempotency-record failure remains inside the same business UOW;
- transaction commit or rollback releases the transaction-scoped advisory lock.

The concrete gate locally knows whether `pg_try_advisory_xact_lock` returned
true. The shared `StreamAdmissionResult(ADMITTED)` does not expose that fact,
and the optimistic gate returns the same verdict without taking a lock.
Therefore generic `ADMITTED` must not be interpreted as public lock-acquisition
evidence.

## 7. Existing Evidence Ownership

### PostgresWriteSideResult and nested results

The primary result already owns:

- terminal `PostgresWriteSideOutcome`;
- the accepted event when applicable;
- final `IdempotencyDecision`;
- optional `StreamAdmissionResult`;
- optional `ValidationDecision`;
- optional append-time `AdmissionResult`.

Those nested results already preserve idempotency, validation, stream, and
append verdicts and relevant identities. Their presence proves completion of
the corresponding normal-return boundary. A future trace should not copy their
reasons, payloads, verdicts, timings, or arbitrary metadata merely for
convenience.

### SemanticOutcome

The Stage 4A mapper already preserves technical status, semantic tuple,
correlation context, presence flags, and typed nested-result evidence. It does
not preserve validation placement, checkpoint provenance, business-UOW reach,
or execution ordering.

### DecisionReceipt

The Stage 4B mapper already preserves the Stage 4A semantic tuple, write-side
evidence source, subject and correlation, identity provenance, admission
disposition, and a compact terminal lifecycle summary. It does not distinguish
preliminary from authoritative idempotency or expose the ordered producer path.

The separate `PostgresDecisionReceiptTransactionOwner` owns governance-receipt
durability, rollback, and connection disposition. Those are not authoritative
business-write transaction evidence and must not enter a write-side execution
trace.

## 8. Missing Execution-Topology Evidence

The current normal results do not directly preserve:

- actual `ValidationPlacement`;
- whether an idempotency result came from the PRE preliminary check or an
  authoritative business-UOW check;
- whether the business UOW was reached;
- ordered history-observation, validation, concurrency-preparation, append,
  and idempotency-persistence checkpoints;
- whether an accepted-history observation was preliminary or protected by the
  pessimistic stream lock;
- idempotency-record persistence reach;
- a producer-specific terminal checkpoint finer than the receipt's compact
  lifecycle phase;
- the cross-strategy handoff when one valid composition makes durable progress
  after the other composition has already crossed an earlier guard;
- the transaction-local interval after an event INSERT succeeds but before the
  owning business UOW commits or rolls back.

This is the evidence gap currently strong enough to justify a narrow
producer-specific trace slice and bounded write-side characterization.

## 9. Characterization Scenarios

The focused integration characterization covers:

1. PRE validation BLOCK before business-UOW, concurrency, or append reach.
2. PRE authoritative REPLAY after preliminary MISS, history observation,
   candidate preparation, validation ALLOW, and business-UOW reach.
3. PRE append-time OCC conflict after validation and optimistic preparation,
   with no reload, retry, or second attempt.
4. IN plus the actual concrete pessimistic gate on an accepted path through
   protected history, validation, append, idempotency persistence, and clean
   commit.
5. IN plus the actual concrete pessimistic gate when the stream lock cannot be
   acquired, proving protected history, validation, and append are not reached.
6. IN plus the actual concrete pessimistic gate when validation BLOCKS after
   successful preparation, proving append is not reached.
7. Mixed IN+pessimistic versus PRE+optimistic execution where IN has already
   observed authoritative idempotency `MISS`, acquired its cooperative stream
   protection, observed history, and completed validation, then PRE commits the
   same request before IN appends. IN must retain its earlier idempotency `MISS`
   and be rejected by append-time stale-write arbitration without reload,
   recheck, retry, or a second attempt.
8. Mixed PRE+optimistic versus IN+pessimistic execution where PRE has completed
   preliminary idempotency, history observation, candidate preparation, and
   validation but has not yet entered its business UOW, then IN commits the same
   request. PRE's later authoritative idempotency check must return `REPLAY`
   before optimistic preparation or append.
9. One PRE+optimistic writer successfully INSERTs the next stream position but
   pauses before idempotency persistence and commit. A second real writer cannot
   see that uncommitted event through ordinary `READ COMMITTED` history reads,
   reaches the same-position INSERT, and waits at PostgreSQL uniqueness
   arbitration. When the owner commits, the contender must resume as
   `STALE_WRITE` / `ADMISSION_REJECTED`, retain its earlier idempotency `MISS`,
   and roll back.
10. The same uncommitted-position arrangement, except the first writer rolls
    back after its append returned. The waiting contender must then be allowed
    to occupy the released stream position, persist its idempotency record, and
    become the only durable accepted writer.

### Mixed-strategy correctness handoff

Scenarios 7 and 8 deliberately place the competing commit on opposite sides of
the authoritative idempotency boundary:

```text
competitor durable before authoritative idempotency check
→ durable request memory is visible
→ REPLAY

competitor durable after authoritative idempotency MISS
but before append-time arbitration
→ idempotency is not re-run
→ stream-position arbitration must preserve correctness
→ STALE_WRITE
```

This is not a performance comparison and does not select a preferred strategy.
It characterizes which existing guard owns correctness at two precise
cross-strategy race windows.

### Uncommitted stream-position arbitration

Scenarios 9 and 10 characterize a different boundary:

```text
append statement succeeds
≠
durable accepted authority
```

Under the repository's expected `READ COMMITTED` environment, an ordinary
reader cannot see another transaction's uncommitted `order_events` row. That
does not mean the physical stream position is free from database arbitration.

The contender may still reach its own same-position INSERT and block at the
unique `(order_id, sequence)` boundary until the owner transaction resolves:

```text
owner COMMIT
→ contender resumes
→ named stream-position UniqueViolation
→ STALE_WRITE
→ ADMISSION_REJECTED
→ rollback

owner ROLLBACK
→ conflicting index occupant disappears
→ contender INSERT may proceed
→ contender can become the durable winner
```

These tests must prove the wait through PostgreSQL lock-state observation, not
through elapsed time or probabilistic scheduling. `READ_COMMITTED` is set
explicitly in the characterization because the production write side currently
does not enforce an isolation level; stronger caller-selected isolation may
surface a different native failure class.

The tests may observe semantic collaborator and UOW method boundaries. They
must not assert private advisory-lock state, reason strings, exception text,
credentials, or prospective public trace-enum names. SQL used only to observe
PostgreSQL backend wait state is test-harness evidence, not production trace
vocabulary.

The test-only checkpoint name `pessimistic_preparation_returned` means only
that concrete preparation returned a typed result; that result may be
`LOCK_TIMEOUT`, so the checkpoint does not prove lock acquisition. Likewise,
`append_admission_returned` means the append-admission call returned a typed
result, including a possible `STALE_WRITE` rejection. It does not by itself
prove that an event row was durably committed.

## 10. Safety and Exception Boundaries

Characterization evidence must not contain or infer from:

- raw exception text or `str(exc)`;
- SQL or constraint diagnostics as future public trace payload;
- stack traces, credentials, or live connection objects;
- complete request signatures, candidates, accepted events, history, or
  aggregate state;
- validation metadata or arbitrary context;
- `DecisionReceipt` payloads;
- policy, strategy selection, retry authorization, or cost measurement.

Current append translation embeds some exception text in existing result
reasons. This is existing primary-result behavior, not safe source material for
a future trace.

Currently propagating exceptions must continue to propagate. This experiment
does not catch, wrap, convert, or attach diagnostics to them. A future traced
API cannot promise an execution artifact for those paths without a separate
explicit error-delivery decision.

## 11. Commit Boundary

The accepted result expression is constructed inside the UOW, but the caller
receives it only after clean context-manager exit calls `commit()` and that call
returns. Normal ACCEPTED delivery therefore implies acknowledged completion of
the current business commit.

A successful event append is weaker evidence:

```text
append returned ADMITTED
→ event INSERT succeeded inside the current transaction

but

commit not yet acknowledged
→ event is not yet durable accepted authority
```

A later idempotency-persistence failure or explicit test rollback can still
remove that event. Another transaction may be unable to read the row through
MVCC while the unique index still coordinates a conflicting INSERT.

Commit exceptions still propagate without a typed authoritative business
durability result. This characterization does not add `COMMITTED`,
`NOT_COMMITTED`, `UNKNOWN`, reconciliation, or generic commit-ambiguity
classification. Governance receipt-persistence lifecycle evidence remains a
different owner.

## 12. PR5-Safe Conceptual Vocabulary

PR4 identified a smaller subset of concepts for later PR5 consideration:

```text
observed validation placement
idempotency checkpoint provenance
business UOW reached
ordered bounded checkpoint progress
producer-specific terminal checkpoint
```

These were characterization concepts, not frozen names or fields. PR5
subsequently selected fewer semantically stable checkpoints and did not turn
every internal method call, database wait, or transaction-internal state into
public vocabulary.

No stable `PRE_OCC`, `IN_PESSIMISTIC`, or other strategy enum is introduced
here. Concrete compositions may be named in tests and documentation without
becoming runtime strategy identity.

## 13. Stage 4B.2 Relationship

Current execution boundaries make later measurement meaningful around:

- validation duration;
- business-transaction duration;
- pessimistic lock-acquisition call duration;
- append/OCC arbitration duration;
- idempotency-persistence duration;
- validation work wasted before a PRE append-time OCC conflict.

This note does not define measurement fields or add timing code. Execution
checkpoint evidence is not measurement evidence.

The current pessimistic implementation uses a nonblocking advisory try-lock.
Its future duration must not automatically be called `lock_wait_ms`; Stage 4B.2
must explicitly define the measurement vocabulary.

## 14. Unresolved Questions

- Whether a future consumer needs stable typed gate-strategy identity remains a
  human decision. Current factory or class identity is not a public contract.
- Lock attempt/acquisition could be future typed gate enrichment, but it is not
  derivable from generic `ADMITTED`.
- Whether progress from currently propagating exceptions should ever be
  delivered requires a separate error-contract decision.
- Commit ambiguity requires an authoritative business transaction design and
  is not solved by a trace.
- The production write side does not enforce transaction isolation. The
  uncommitted-position characterization intentionally fixes `READ_COMMITTED`
  rather than claiming identical behavior for stronger isolation.
- PR5 did not add checkpoints whose useful delivery would require changing
  current no-result exception behavior. Any future exception-path trace
  delivery still requires a separate error-contract decision.

## 15. Stop Conditions

Stop for human review if characterization or later contract work would require:

- production instrumentation or transaction-semantics changes;
- making `PostgresWriteSideConfig.validation_mode` authoritative;
- inventing strategy identity;
- treating generic `ADMITTED` as lock-acquisition evidence;
- parsing exception or reason strings into trace evidence;
- catching or wrapping currently propagating exceptions;
- business commit-ambiguity redesign;
- reload, retry, fallback, or multiple-attempt behavior;
- changes to `PostgresWriteSideResult`, `SemanticOutcome`, or
  `DecisionReceipt`;
- timing or cost implementation;
- a generic cross-producer `DiagnosticTrace` abstraction.

## 16. Characterization Evidence

The complete ten-scenario characterization suite executed successfully against
the current production baseline. PR4 is complete and accepted as the execution
topology evidence baseline used by PR5.

The concurrency proof for scenarios 9 and 10 must be deterministic:

```text
separate PostgreSQL connections
+ explicit READ_COMMITTED
+ thread/event synchronization
+ observed PostgreSQL Lock wait
```

Elapsed time may bound test cleanup, but it is not the proof of the race.

## 17. Deferred Hardening — Concurrent Idempotency MISS→Record Arbitration

The following concern is real and source-supported, but is deliberately outside
the current PR4 acceptance scope.

Two independent write-side executions may use the same `request_id` while
targeting different order streams:

```text
writer A
→ authoritative idempotency check = MISS

writer B
→ authoritative idempotency check = MISS

A event append
→ succeeds transaction-locally on order-A

B event append
→ succeeds transaction-locally on order-B

A idempotency record INSERT
B idempotency record INSERT
→ both target the same idempotency_records(request_id) primary key
```

There is currently no request-level lock or serialization between
`PostgresIdempotencyStore.check()` and `record()`. The physical
`idempotency_records.request_id` primary key therefore remains the final
request-identity arbiter if both executions already observed `MISS`.

Current source analysis indicates that when the first transaction commits, the
loser's `record()` can receive a raw PostgreSQL `UniqueViolation`. That
exception is not currently translated into typed `REPLAY` or `CONFLICT`; it
propagates, and exceptional UOW rollback removes the loser's already-inserted
event. The final durable state can remain internally consistent even though the
loser does not receive a typed idempotency result.

This gap should be treated as separate hardening because the open question is
not merely execution order. It is also a semantic-contract decision:

```text
should a concurrent request-identity loser remain an untyped persistence error

or

should the runtime reclassify it into stable idempotency semantics?
```

PR4 does not answer that question and must not silently freeze the current raw
exception behavior as the desired public contract.

Deferred follow-up:

```text
concurrent idempotency check→record TOCTOU
= source-supported
= exact two-connection characterization absent
= record as separate hardening gap
= do not pull into PR4 unless a later human decision explicitly re-scopes it
```
