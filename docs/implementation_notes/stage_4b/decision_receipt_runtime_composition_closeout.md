# DecisionReceipt Runtime Composition Closeout

[← Back to Stage 4B Notes](README.md)

## 1. Purpose and Authority Scope

This note records the current PostgreSQL runtime-composition increment built
after the completed Stage 4B `DecisionReceipt` contracts. It does not rewrite
the historical [Stage 4B closeout](stage_4b_closeout.md). Current source and
tests govern executable behavior; accepted
[ADR 0019](../../adr/0019_separate_accepted_receipt_reconstruction_from_failed_attempt_persistence.md)
and
[ADR 0030](../../adr/0030_preserve_legacy_stale_write_carrier_and_normalize_at_the_semantic_abstraction_boundary.md)
continue to govern transaction separation, evidence safety, and authority.

The increment provides explicit live PostgreSQL composition. It does not make
receipt persistence implicit in a business invocation.

## 2. Final Runtime Chain

```text
RequestSignature
→ build_postgres_write_side_decision_receipt_runtime(...)
→ PostgresWriteSideDecisionReceiptRuntimeOwner
→ PostgresWriteSideInvocationOwner
→ PostgresTransactionalWriteSide
→ normal PostgresWriteSideResult
→ PostgresWriteSideDecisionReceiptCompletedInvocation
→ explicit compose_receipt()
→ PostgresWriteSideDecisionReceiptMaterializationOwner
→ DecisionReceipt
→ PostgresWriteSideDecisionReceiptPersistenceCompositionOwner
→ PostgresDecisionReceiptTransactionOwner
→ separate PostgreSQL governance transaction
→ commit-aware receipt-persistence evidence
```

`invoke_initial()` completes the existing business invocation and publishes a
completed-invocation handle. It does not materialize or persist a receipt.
Receipt work begins only when the caller explicitly invokes
`compose_receipt()` on that handle.

## 3. PR1 / PR2 / PR3 Responsibilities

PR1 owns one stable live materialization lifecycle for one exact completed
`PostgresWriteSideResult`. It allocates receipt-local identities lazily, calls
the established write-side receipt mapper once for a terminal normal delivery,
and retains the exact business result independently of materialization success.

PR2 composes that exact PR1 lifecycle with one
`PostgresDecisionReceiptTransactionOwner`. It preserves separate business,
materialization, and persistence evidence and carries the existing commit-aware
transaction result without reinterpretation.

PR3 owns application composition. It binds each normally completed invocation
to one retained handle and one canonical live PR1/PR2 graph, selects persistence
eligibility through a closed allowlist, reduces unexpected composition
exceptions to bounded live evidence, and supplies the repository-level
PostgreSQL builder.

## 4. Business vs Receipt Transaction Ownership

```text
business result
!= receipt materialization
!= receipt persistence

business transaction
!= receipt governance transaction
```

The business writer returns its normal result only after its existing unit of
work has completed. Eligible receipt persistence begins later, through a
dedicated governance connection acquired by
`PostgresDecisionReceiptTransactionOwner`. Receipt failure does not roll back or
reclassify an already completed business result.

Examples include:

```text
ACCEPTED + receipt NOT_COMMITTED
→ business remains ACCEPTED

ACCEPTED + receipt UNKNOWN
→ business remains ACCEPTED

VALIDATION_BLOCKED + receipt COMMITTED
→ no accepted business effect was created
```

This is not a distributed transaction and provides no atomic business-plus-
receipt commit guarantee.

## 5. One-Completion / One-Live-Graph Custody

The canonical runtime path guarantees:

```text
one normal completion
→ one canonical owner-local live receipt graph
→ one cached terminal runtime delivery
```

Repeated or concurrent `compose_receipt()` access on the same completed handle
returns the identical terminal delivery. This prevents lower-level owner
reconstruction through the canonical application path.

The guarantee is owner-local. It is not global exactly-once receipt creation,
process-independent uniqueness, a durable receipt identity, or a durable
attempt identity. Arbitrary code can still construct lower-level owners outside
the canonical runtime path.

## 6. Persistence Eligibility

Materializability and automatic durable-persistence eligibility are distinct:

```text
materializable
!= persistence-eligible
```

The current reviewed positive profiles are:

- `ACCEPTED`;
- `REPLAY`;
- `CONFLICT`;
- `VALIDATION_BLOCKED`; and
- preparation-phase `LOCK_TIMEOUT`, identified by typed lifecycle position.

Every unmatched or unreviewed profile fails closed. Current append-time
rejections and infrastructure profiles are persistence-ineligible because
their current reason/evidence contracts are not approved for automatic durable
receipt persistence. Eligibility never parses reason strings.

```text
PERSISTENCE_INELIGIBLE
= persistence deliberately not reached

NOT_COMMITTED
= persistence attempted and known not committed

UNKNOWN
= persistence attempted but durability unresolved
```

An append-time `STALE_WRITE` result may be representable by the receipt mapper,
but it remains persistence-ineligible in the current PR3 runtime. Under ADR
0030, `STALE_WRITE` alone is not proof of concurrency, retryability, or
re-invocation authority.

## 7. Terminal Receipt Outcomes

`PostgresWriteSideDecisionReceiptRuntimeDelivery` uses four terminal
application statuses:

- `PERSISTENCE_INELIGIBLE`: persistence was deliberately not reached;
- `MATERIALIZATION_FAILED`: bounded PR1 materialization failure, with
  persistence not reached;
- `PERSISTENCE_COMPLETED`: PR2 returned its exact normal persistence delivery;
  and
- `UNEXPECTED_COMPOSITION_EXCEPTION`: an unexpected receipt-composition
  exception escaped a lower boundary and was reduced to bounded live evidence.

Normal PR2 evidence remains unchanged beneath `PERSISTENCE_COMPLETED`, including
`COMMITTED`, `NOT_COMMITTED`, `UNKNOWN`, `ALREADY_PRESENT`, and typed conflict
evidence. PR3 neither retries nor resolves those results.

After `UNEXPECTED_COMPOSITION_EXCEPTION`, the completed handle remains terminal
and later access returns the same live delivery without automatically re-entering
PR2. The exact business result remains available. No raw exception text or
exception object is retained as durable receipt evidence, and this bounded
category is not a general diagnostic framework.

## 8. A1 / A2

The runtime owner retains exactly two bounded completion slots:

```text
A1 normal completion
→ receipt lifecycle A

Stage 4E-authorized A2 normal completion
→ receipt lifecycle B
```

A1 and A2 share the same complete `RequestSignature` but retain distinct
completed-invocation handles, PR1/PR2 graphs, receipt identities, and receipt-
path outcome identities. A1 remains accessible after A2 replaces the invocation
owner's current-response state.

This is not an `AttemptLog`, an unbounded attempt collection, or durable attempt
identity. Stage 4E permits at most one reviewed A2; no A3 exists.

## 9. Stage 4C / Stage 4E Independence

Receipt composition does not invoke Stage 4C. Receipt work may complete before
Stage 4C allocates its lazy current-response identity, and the receipt-path
`outcome_id` need not equal Stage 4C's identity.

Receipt materialization or persistence does not create Stage 4E authority.
Stage 4E remains the independent authority boundary for one reviewed
same-request A2, and the runtime owner only delegates that evaluation and
authorized invocation to the existing invocation owner.

There is no mandatory receipt → Stage 4C → Stage 4E → execution pipeline.

## 10. PostgreSQL Integration Coverage

Guarded real PostgreSQL integration coverage exercises the real builder,
transactional writer, stores, runtime owner, and receipt transaction owner. The
module covers:

- `ACCEPTED` business commit plus one `LIVE_RESULT` receipt;
- `VALIDATION_BLOCKED` with no accepted business effect plus a committed
  receipt;
- append-time `STALE_WRITE` persistence ineligibility plus no receipt row;
- receipt-side `NOT_COMMITTED` while accepted business state remains; and
- preparation `LOCK_TIMEOUT` A1 plus an authorized accepted A2 with two
  distinct receipt rows.

The fixture requires `TEST_DATABASE_URL` and rejects a database whose name does
not end in `_test`. This closeout records guarded integration coverage, not an
invented execution transcript or pass count.

## 11. Non-Goals / Remaining Gaps

This increment does not provide:

- process-crash recovery;
- accepted-history receipt reconciliation;
- a transactional outbox;
- a scheduler or background persistence;
- global exactly-once receipt creation;
- durable `AttemptLog` identity;
- automatic receipt retry;
- `UNKNOWN` resolution;
- arbitrary technical-failure durability safety;
- connection-pool ownership or production timeout calibration; or
- environment-driven deployment bootstrap.

## 12. Source / Test Map

Production sources:

- [PR1 materialization owner](../../../src/pipeline/transactional/postgres_write_side_decision_receipt_materialization_owner.py)
- [PR2 persistence-composition owner](../../../src/pipeline/transactional/postgres_write_side_decision_receipt_persistence_composition_owner.py)
- [PR3 runtime owner](../../../src/pipeline/transactional/postgres_write_side_decision_receipt_runtime_owner.py)
- [PostgreSQL runtime builder](../../../src/bootstrap/build_postgres_write_side_decision_receipt_runtime.py)

Focused tests:

- [PR1 unit tests](../../../tests/unit/pipeline/transactional/test_postgres_write_side_decision_receipt_materialization_owner.py)
- [PR2 unit tests](../../../tests/unit/pipeline/transactional/test_postgres_write_side_decision_receipt_persistence_composition_owner.py)
- [PR3 unit tests](../../../tests/unit/pipeline/transactional/test_postgres_write_side_decision_receipt_runtime_owner.py)
- [Builder unit tests](../../../tests/unit/bootstrap/test_build_postgres_write_side_decision_receipt_runtime.py)
- [Guarded PostgreSQL integration coverage](../../../tests/integration/pipeline/transactional/test_postgres_write_side_decision_receipt_runtime.py)
