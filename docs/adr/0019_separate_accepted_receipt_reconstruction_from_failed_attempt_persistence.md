# ADR 0019: Separate Accepted-Result Receipt Reconstruction from Immediate Typed-Observation Evidence Persistence

[← Back to ADR Index](README.md)

## Status

Accepted

## Implementation Status

Partially implemented.

Stage 4B PR6 implements the foundational persistence boundary:

- explicit DecisionReceipt serializer version 1;
- storage-neutral persistence-envelope contracts;
- materialization provenance;
- generic PostgreSQL DecisionReceipt persistence;
- nullable accepted-event correlation;
- admitted write-side partial uniqueness;
- PR4 and PR5 mapper-produced receipt round trips.

The following remain deferred:

- automatic live-result materialization;
- accepted-history scanning;
- missing-receipt reconciliation;
- reconstruction recipe/version ownership;
- background scheduling;
- transactional outbox;
- publication workflow.

A later PR1–PR3 runtime-composition increment implements explicit live
PostgreSQL receipt composition without changing this accepted decision:

- `PostgresWriteSideDecisionReceiptRuntimeOwner` binds one normally completed
  invocation to one retained live materialization/persistence graph;
- callers explicitly enter receipt work through the completed handle's
  `compose_receipt()` method;
- business and receipt transactions remain separate;
- accepted-history scanning and missing-receipt reconciliation remain deferred;
  and
- technical, append-time, infrastructure, and unreviewed profiles remain
  fail-closed unless their reason/evidence contracts are separately approved for
  durable persistence.

This status update does not make receipt persistence implicit in business
invocation and does not alter the historical context or decision below.

---

## Context

`DecisionReceipt` is intended to become durable, reviewable governance evidence.

However, accepted results and later typed observations do not leave the same
durable source material behind.

For this ADR, an accepted result means exactly:

```text
PostgresWriteSideOutcome.ACCEPTED
+
EventAdmissionDisposition.ADMITTED_TO_ACCEPTED_HISTORY
```

The presence of an accepted event on another result does not make that result
accepted. In particular, `REPLAY` is a later typed observation about an
existing accepted event.

For an accepted result, the current PostgreSQL write-side already commits:

```text
accepted event
+
idempotency record
```

inside one local transaction.

Those records preserve authoritative business facts that can later support a
narrower, versioned canonical accepted-result receipt, even when the process
crashes after the business transaction commits but before a `DecisionReceipt`
row is persisted.

They do not preserve the original caller-supplied `receipt_id` or `outcome_id`,
and they do not preserve every transient field from the live PR4 result.
Accepted-history reconstruction therefore cannot reproduce the original live
PR4 receipt bit-for-bit.

A later typed observation is different.

Examples include:

```text
REPLAY
CONFLICT
VALIDATION_BLOCKED
stream-level ADMISSION_REJECTED
append-level ADMISSION_REJECTED
```

These observations do not append a new accepted event for the observed
occurrence. Some roll back the write transaction, some terminate before a write
transaction exists, and `REPLAY` only reads the accepted event and idempotency
record created by the original accepted request.

If their typed runtime result is lost before governance evidence is persisted,
accepted history alone cannot prove that the later observation occurred.

The completed PR4 and PR5 producer adapters make this distinction concrete.
PR4 write-side receipts may carry accepted-event identity and typed admission
evidence. PR5 replay, snapshot-validation, and snapshot-assisted-resolution
receipts instead preserve typed observation evidence. Accepted history cannot
reconstruct failed attempts or every read-side and snapshot observation merely
because an order has accepted events.

Receipt persistence stores evidence that a producer has already created. It
does not reconstruct, reinterpret, or authorize that evidence. Foundational
PR6 therefore remains generic across PR4 and PR5 receipts, while runtime
materialization orchestration remains deferred.

The system therefore needs different persistence behavior for:

```text
accepted results
```

and:

```text
typed non-ACCEPTED observations
```

A transactional outbox may later be required to guarantee eventual receipt
materialization across process crashes. The current stage does not yet have
enough downstream policy, trace, measurement, and delivery requirements to
design that outbox responsibly.

---

## Decision

The project proposes a split receipt-persistence model.

This decision defines the target persistence model. It does not imply that
foundational PR6 implements runtime materialization orchestration, typed
observation persistence orchestration, or accepted-history reconciliation.

### 1. Accepted results target eventual receipt materialization

In this section, accepted result means only:

```text
PostgresWriteSideOutcome.ACCEPTED
+
EventAdmissionDisposition.ADMITTED_TO_ACCEPTED_HISTORY
```

Accepted business facts remain authoritative in:

```text
accepted event
+
idempotency record
```

These records continue to commit atomically inside the existing local
PostgreSQL transaction.

The complete `DecisionReceipt` is not a precondition for that business commit.

After the accepted result is known, a future materialization orchestrator should
target:

```text
PostgresWriteSideResult
→ SemanticOutcome
→ DecisionReceipt
→ persist DecisionReceipt
```

If immediate receipt persistence fails or the process crashes after business
commit, a future accepted-receipt reconciler may identify accepted results that
lack a corresponding receipt and materialize a narrower, versioned canonical
receipt from durable authority.

That reconciled receipt requires canonical replacement values for
`receipt_id` and `outcome_id`. Its complete live `evidence_summary` is not
reconstructible. Other fields may be derived from durable authority or
regenerated only through a pinned canonical mapper version.

The target accepted-path authority rule is therefore:

```text
accepted history is authoritative
+
accepted receipts may become consistent later
```

### 2. Typed non-ACCEPTED observations target immediate separate persistence

A typed non-`ACCEPTED` observation has no newly appended accepted event that
proves the observed occurrence. This includes:

```text
REPLAY
CONFLICT
VALIDATION_BLOCKED
stream-level ADMISSION_REJECTED
append-level ADMISSION_REJECTED
```

Once a normal typed observation exists, a future orchestration layer should
target:

```text
PostgresWriteSideResult
→ SemanticOutcome
→ DecisionReceipt
→ persist in a separate governance transaction
→ report receipt persistence separately
→ return the original business result
```

Receipt persistence is separate from the original business transaction or read
observation.

The persistence attempt should occur before the normal typed observation
response is returned whenever practical once that future orchestration exists.

For a non-`ACCEPTED` mutation attempt, the persisted receipt records why the
attempt did not enter accepted history. For `REPLAY`, it records that a later
request was observed and matched an existing accepted event; the original
accepted event and idempotency row do not prove that this later observation
occurred.

Foundational PR6 provides persistence infrastructure only. It does not wire
this target orchestration into the PostgreSQL write side.

### 3. Business outcome and receipt persistence outcome remain separate

Receipt persistence failure must not rewrite the authoritative business result.

For example:

```text
business_outcome = ACCEPTED
receipt_persistence = FAILED
```

must not be exposed as though the payment or order mutation failed.

Likewise, retrying receipt persistence is not the same operation as retrying the
business command.

### 4. No transactional outbox is introduced in the initial version

The first durable-persistence implementation will not require a transactional
outbox.

The future accepted path can use accepted history as its reconciliation source
for a narrower canonical receipt.

The future typed-observation path targets immediate, separate governance
persistence.

The project accepts that an accepted business transaction can commit and the
process can crash before immediate receipt persistence. The accepted fact
survives, but the original live receipt identity and transient evidence can be
lost.

The project also accepts that a process crash after a typed observation is
produced but before its separate governance transaction commits can lose that
observation evidence.

A durable outbox, materialization job, governance event log, or attempt log
should be introduced later when concrete consumers require guaranteed eventual
evidence creation.

Outbox deferral is not permanent rejection. The decision must be revisited when
the project requires guaranteed eventual governance-evidence creation across
process crashes.

---

## Rationale

### Accepted results and later typed observations have different reconstructability

An accepted result leaves durable authority behind.

For reconstruction purposes, this ADR uses four classifications:

```text
DURABLE-AUTHORITY DERIVED
= directly supported by stored accepted event or idempotency facts

MAPPER-CANONICAL RECONSTRUCTIBLE
= regenerated through an explicitly pinned mapper version

CANONICAL REPLACEMENT REQUIRED
= the original value is absent, but a new documented canonical value can be created

NOT RECONSTRUCTIBLE
= transient live evidence cannot truthfully be recovered
```

For the current accepted-result receipt:

```text
DURABLE-AUTHORITY DERIVED
→ accepted event identity
→ request and order correlation
→ accepted-history membership

MAPPER-CANONICAL RECONSTRUCTIBLE
→ accepted semantic tuple
→ accepted reason text
→ write-side evidence source
→ subject and correlation construction
→ accepted admission disposition
→ producer flag defaults
→ current empty actor, cost_summary, and metadata defaults

CANONICAL REPLACEMENT REQUIRED
→ receipt_id
→ outcome_id

NOT RECONSTRUCTIBLE
→ complete live evidence_summary
→ transient validation, timing, lock-wait, or future live-only actor evidence
```

Stored durable facts and mapper-canonical values are not the same authority
class. For example, the database stores the accepted event identity but does
not directly store the `DecisionReceipt` semantic tuple, reason, evidence
source, subject type, flags, or admission-disposition enum.

The system must therefore distinguish:

```text
live-result materialization
```

from:

```text
accepted-history reconciliation
```

and must not claim that a reconciled receipt reproduces the original live PR4
receipt bit-for-bit.

A later `REPLAY` observation is not reconstructible merely because its original
accepted event exists. The accepted event and idempotency record prove the
original accepted result, but not that a later replay request was observed.

Other typed non-`ACCEPTED` attempts may leave no new accepted event and no
durable attempt record. Without separate governance persistence, there may be
nothing from which to prove that the later observation occurred.

### Full receipt atomicity would couple governance availability to business availability

If a complete receipt were inserted in the same transaction as the accepted
event and idempotency record, then receipt serialization, schema, index, or
storage failure could roll back an otherwise valid business mutation.

That would make:

```text
governance evidence availability
```

a precondition for:

```text
business mutation availability
```

The project does not currently adopt that requirement.

### The split preserves authority boundaries

The selected model keeps:

```text
accepted history
= business authority
```

and:

```text
DecisionReceipt
= durable governance evidence about the completed result
```

Receipt persistence does not grant or revoke accepted-history membership.

---

## Accepted-Path Flow

The following is the target flow for later orchestration and reconciliation,
not functionality delivered by foundational PR6:

```text
BEGIN business transaction

append accepted event
record idempotency result

COMMIT

build live DecisionReceipt
attempt immediate receipt persistence

if receipt is missing later:
    scan accepted authority
    detect missing accepted receipt
    reconstruct narrower versioned canonical accepted receipt
    attempt persistence with explicit duplicate/conflict handling
```

The recommended stable producer identity for one newly admitted write-side
receipt is:

```text
WRITE_SIDE_ADMISSION
+
ADMITTED_TO_ACCEPTED_HISTORY
+
accepted_event_id
```

`receipt_id` alone is insufficient for reconciliation identity because the
original caller-generated value is not present in accepted history.

The foundational store must treat:

```text
same accepted producer identity
+
different receipt_id or different serialized content
→ explicit conflict
```

It must not upsert, automatically replace an existing receipt, or enrich one
receipt with evidence from another materialization. Deterministic receipt and
outcome UUID generation remains a reconciliation-stage decision. A later
reconciliation design may refine equivalence only after canonical identity and
payload rules are adopted.

---

## Typed Non-ACCEPTED Observation Flow

The following is the target flow for a later orchestration sub-PR, not
foundational PR6 behavior:

```text
write-side lifecycle reaches a normal typed observation:
    REPLAY
    CONFLICT
    VALIDATION_BLOCKED
    stream-level ADMISSION_REJECTED
    append-level ADMISSION_REJECTED

business write transaction is rolled back
or no write transaction was entered
or REPLAY completed as a read observation

map typed result to SemanticOutcome
map typed result and outcome to DecisionReceipt

BEGIN governance transaction
persist DecisionReceipt
COMMIT

report receipt persistence outcome separately
return the original typed result
```

This is not an atomic transaction with the original business mutation or read
observation.

It is a separate durable record of why an attempted mutation did not become
accepted history or, for `REPLAY`, that a later request matched an existing
accepted event.

## Reason and Evidence Safety Prerequisite

Typed technical-failure orchestration must not be wired into durable receipt
persistence until it can supply safe semantic reason text or a stable reason
code.

The durable receipt must not receive:

```text
raw database exception text
SQL details
constraint diagnostics
stack traces
arbitrary producer or validation metadata
```

Those details remain operational logging evidence or belong to a future
`DiagnosticTrace` or equivalent diagnostic boundary. Persistence does not
broaden the existing compact receipt-safe evidence allowlist.

---

## Untyped and Ambiguous Failures

This ADR does not claim that every execution attempt can already produce a
receipt.

An exception may escape without a `PostgresWriteSideResult`.

A commit outcome may also become ambiguous when the client cannot determine
whether commit succeeded.

Those cases require a different evidence boundary, such as:

```text
AttemptLog
RuntimeObservation
DiagnosticTrace
commit reconciliation record
```

A future producer may emit:

```text
COMMIT_OUTCOME_UNRESOLVED
```

only when it carries truthful ambiguity and reconciliation evidence.

The current receipt mapper must not infer that disposition from an arbitrary
exception or infrastructure failure.

---

## Materialization Provenance

Durable receipt storage should preserve how the receipt was materialized.

The persistence envelope or receipt table should use a dedicated
`materialization_provenance` column with these values:

```text
LIVE_RESULT
ACCEPTED_HISTORY_RECONCILIATION
```

Materialization provenance must not be placed inside:

```text
DecisionReceipt
DecisionReceipt.metadata
DecisionReceipt.evidence_summary
```

It describes how a row was materialized, not the semantic meaning of the
receipt.

A receipt created from accepted-history reconciliation may contain a narrower
evidence set than one created from the original live typed result.

The persistence envelope should make that difference explicit rather than
silently claiming equivalent evidence richness.

Foundational PR6 must establish serializer/deserializer version 1. The first
accepted-history reconciler must also record or otherwise pin its canonical
reconstruction version. The exact reconstruction version representation remains
part of the later reconciliation design.

### Versioned payload equality

For foundational duplicate and conflict classification, an identical versioned
`DecisionReceipt` payload means:

```text
receipt_serialization_version
+
every explicitly serialized DecisionReceipt semantic field
```

It does not include:

```text
materialization_provenance
materialized_at
database-generated values
other persistence-envelope fields
```

If an identical versioned receipt payload already exists under the same
`receipt_id`, a second materializer receives `ALREADY_PRESENT` even when it
supplies a different materialization provenance. The existing row retains the
provenance and materialization time of the successful inserting materializer.

The foundational store must not update, replace, or enrich that row.

### Numeric persistence portability boundary

Foundational serialization version 1 proposes that every integer in the
versioned persisted payload, including integers inside flexible JSON evidence
and metadata, must fit the signed 64-bit range.

This is a persistence portability boundary. It is deliberately narrower than
Python's unbounded integer range. A `DecisionReceipt` that is valid under the
shared runtime contract may therefore still be rejected as not persistable by
the version 1 serializer or persistence boundary.

Booleans remain distinct from integers and must not be admitted through integer
validation merely because Python represents `bool` as a subclass of `int`.

This persistence rule does not change the shared `DecisionReceipt` contract or
its runtime validation behavior.

---

## Transactional Outbox Deferral

A transactional outbox is likely to become necessary when one or more of the
following become true:

```text
every accepted result must eventually have a receipt
every typed observation must survive process crash
policy engines depend on durable receipt availability
receipt-backed snapshot trust is used in production
operator review requires complete attempt coverage
receipt materialization failure requires automatic retry
cross-process delivery latency must be bounded
multiple downstream consumers require reliable publication
```

At that point, the project should evaluate:

```text
receipt materialization outbox
governance event log
durable attempt log
delivery state or consumer cursor
```

The outbox remains a reliability and delivery mechanism.

It must not be treated as the policy engine itself.

The policy engine decides what action is semantically allowed.

The outbox guarantees that required downstream work is not lost across crashes.

---

## Consequences

### Positive

- Accepted business writes do not depend on receipt-table availability.
- Accepted history remains the business authority.
- The target model permits narrower accepted receipts to be repaired through
  eventual consistency.
- The target model gives typed non-`ACCEPTED` observations a separate
  governance-persistence path.
- Accepted-result and typed-observation paths use one receipt contract without
  pretending they have identical reconstructability.
- Receipt schema and storage can evolve separately from the core event and
  idempotency transaction.
- Retry of governance persistence remains distinct from retry of the business
  command.
- The design does not prematurely invent an outbox payload before policy,
  measurement, trace, and delivery consumers are known.

### Negative

- An accepted business transaction can commit before a receipt exists.
- A process crash in that gap can lose the original live receipt identifiers
  and transient evidence.
- Reconciled accepted receipts may contain less transient evidence than
  live-result receipts.
- A typed observation can still be lost if the process crashes before its
  separate governance transaction commits.
- Consumers must not interpret a missing accepted receipt as proof that no
  accepted result exists.
- Consumers must not interpret a missing typed-observation receipt as proof
  that no replay, conflict, validation block, or admission rejection occurred.
- Reconciliation requires stable producer identity, missing-receipt discovery,
  and explicit duplicate/conflict rules.
- The foundational store treats different receipt identity or content for the
  same accepted producer identity as a conflict until later equivalence rules
  are adopted.
- A future outbox or durable attempt log will still be needed for stronger
  completeness guarantees.

### Neutral but Important

```text
eventual accepted-receipt consistency
```

does not mean:

```text
eventual business consistency
```

The business event is already authoritative after its original commit.

Only the governance representation is materialized later.

---

## Persistence Failure Semantics

The future persistence API should keep these dimensions separate:

```text
business_outcome
receipt_mapping_outcome
receipt_persistence_outcome
```

The foundational store may report these statement-level outcomes:

```text
INSERTED
ALREADY_PRESENT
```

`PostgresDecisionReceiptStore` is caller-transaction-owned. `INSERTED` reports
that the insert statement succeeded in the caller-owned transaction. It does
not by itself prove that the transaction committed or that the row is durably
persisted. `ALREADY_PRESENT` reports statement-level duplicate classification
against an existing identical versioned receipt payload.

Expected conflicting content must be classified explicitly, either through a
typed conflict result or a storage-owned conflict error. This ADR does not
freeze the final store result or error API beyond that ownership distinction.

The word `PERSISTED` is reserved for a later orchestration boundary that knows
the caller-owned transaction committed successfully.

These statement-level values and conflict classifications describe receipt
storage only. They do not decide whether a business command may be retried and
do not mutate the original business result.

Whether a missing accepted receipt can later be reconstructed is orchestration
context, not a generic persistence status.

A governance persistence failure must never be represented as permission to
repeat a business mutation that may already have succeeded.

---

## Non-Goals

This ADR does not implement:

```text
DecisionReceipt schema
PostgresDecisionReceiptStore
accepted-receipt reconciler
transactional outbox
governance event log
AttemptLog
DiagnosticTrace
commit reconciliation
policy engine
retry authorization
receipt retention
receipt publication
consumer cursors
cross-database delivery
```

The serializer, schema, and store belong to foundational PR6. Reconciliation,
runtime orchestration, outbox, attempt, diagnostic, policy, retention, and
delivery concerns belong to later work.

---

## PR6 Implementation Direction

PR6 should use this ADR as its opening boundary.

Foundational PR6 contains only:

```text
1. explicit DecisionReceipt serializer/deserializer version 1
2. typed decision_receipts schema and schema constraints
3. persistence-envelope materialization provenance
4. PostgresDecisionReceiptStore insert/load
5. identical duplicate and conflicting duplicate behavior
6. focused unit and PostgreSQL integration tests
```

The repaired repository already uses migrations through 006. The next
implementation migration for this foundation is:

```text
007_create_decision_receipts.sql
```

The complete SQL schema remains an implementation concern and is not embedded
in this ADR.

Foundational PR6 explicitly defers:

```text
runtime materialization orchestration
typed non-ACCEPTED persistence orchestration
accepted-history reconciliation
missing-receipt scanning
scheduling or background workers
transactional outbox
```

Foundational PR6 must not introduce an upsert, automatic receipt replacement,
or evidence enrichment path. It should document both the accepted-path and
typed-observation crash gaps.

Its duplicate contract is:

```text
same receipt_id + identical versioned DecisionReceipt payload
→ ALREADY_PRESENT

same receipt_id + different versioned DecisionReceipt payload
→ CONFLICT

same accepted producer identity + different receipt_id or versioned payload
→ CONFLICT
```

---

## Future Trigger Conditions

Revisit this decision when:

```text
1. accepted receipt lag becomes operationally unacceptable;
2. typed-observation evidence loss becomes unacceptable;
3. policy or strategy execution requires guaranteed durable receipts;
4. snapshot trust selection depends on persisted receipt availability;
5. operator review requires complete evidence coverage;
6. multiple consumers require reliable receipt publication;
7. process-crash recovery must guarantee every receipt is eventually created;
8. accepted-history reconciliation cannot recover sufficient evidence;
9. untyped or ambiguous attempts require durable tracking.
```

The likely evolution is:

```text
accepted-history reconciliation
+
immediate typed-observation persistence
→
durable materialization intent / outbox
+
AttemptLog or reconciliation boundary
```

---

## Final Principle

An admitted:

```text
PostgresWriteSideOutcome.ACCEPTED
+
EventAdmissionDisposition.ADMITTED_TO_ACCEPTED_HISTORY
```

leaves durable authority sufficient to construct a narrower, versioned
accepted-result receipt. It does not preserve the original live PR4 receipt
bit-for-bit.

Later `REPLAY` observations and typed non-`ACCEPTED` attempts are not proven to
have occurred merely because the original accepted event and idempotency row
exist.

Therefore, the proposed target model is:

```text
admitted ACCEPTED result
→ immediate materialization may be followed by narrower versioned reconciliation

REPLAY or typed non-ACCEPTED observation
→ target immediate separate governance persistence

untyped or ambiguous attempt
→ future durable attempt or reconciliation boundary
```

A transactional outbox is deferred, not rejected.

It should be introduced when the project requires guaranteed eventual
governance-evidence creation across process crashes.
