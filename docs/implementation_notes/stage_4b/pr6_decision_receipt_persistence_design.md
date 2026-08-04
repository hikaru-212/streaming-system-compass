# Stage 4B PR6 — DecisionReceipt Persistence Design

[← Back to Stage 4B](README.md)

## Document Role

This note defines the design boundary implemented by Stage 4B PR6.

The PR6 source already exists in the current worktree, but this document records
the intended design before the implementation commits are created. It should be
read before the serializer, persistence contracts, migration, and PostgreSQL
store.

The completed implementation and validation evidence are recorded separately in:

```text
decision_receipt_persistence.md
```

The final cross-PR summary is [Stage 4B Closeout](stage_4b_closeout.md).

This note answers:

```text
Why is persistence split into a serializer, a storage-neutral contract,
a PostgreSQL schema, and a PostgreSQL store?

What does each layer own?

What must each layer refuse to infer or execute?
```

---

## Purpose

PR6 establishes the durable storage foundation for an already-created
`DecisionReceipt`.

The intended path is:

```text
typed producer result
→ SemanticOutcome
→ DecisionReceipt
→ serializer version 1
→ storage-neutral persistence envelope
→ PostgreSQL decision_receipts row
→ exact typed hydration
```

PR6 begins at the `DecisionReceipt` boundary.

It does not decide when a producer runs, when a receipt should be created, or
when the receipt should be persisted.

---

## Design Principle

The persistence design keeps four responsibilities separate:

```text
portable semantic payload
≠
storage materialization evidence
≠
physical PostgreSQL representation
≠
runtime orchestration
```

Therefore:

```text
DecisionReceipt serializer
= portable representation of semantic receipt evidence

persistence contracts
= storage-neutral materialization and conflict vocabulary

migration 007
= physical database invariants and permissions

PostgresDecisionReceiptStore
= PostgreSQL insert, load, hydration, and conflict classification

future orchestration
= decides when and why persistence is invoked
```

No layer may absorb the authority of another layer merely because the data is
available.

---

## Why a Separate Serializer Exists

`DecisionReceipt` is a Python runtime contract.

Durable evidence needs a stable representation that does not depend on Python
object identity or in-memory implementation details.

The serializer therefore owns:

```text
receipt_serialization_version
explicit field ownership
UUID string representation
stable enum values
explicit null representation
strict missing-key rejection
strict unknown-key rejection
JSON-safe flexible evidence
signed 64-bit integer limits
finite numeric values
maximum JSON depth
exact reconstruction of the typed receipt
```

The serializer must preserve:

```text
TRUE
FALSE
NOT_EVALUATED
```

as three distinct flag states.

It must also preserve the distinction between:

```text
true
1
1.0
```

The serializer does not own:

```text
SQL columns
database transactions
materialization provenance
duplicate classification
permissions
runtime policy
reconciliation
automatic persistence
```

The serializer is a portability boundary, not a database adapter.

---

## Why Storage-Neutral Persistence Contracts Exist

Persistence introduces evidence that does not belong inside the semantic
receipt itself.

For example:

```text
how the row was materialized
when the row was materialized
whether the current insert statement inserted a row
whether an identical row already existed
why a conflicting row was rejected
```

These are storage-envelope facts, not changes to the meaning of the
`DecisionReceipt`.

The storage-neutral contract therefore owns:

```text
DecisionReceiptMaterializationProvenance
DecisionReceiptInsertStatus
PersistedDecisionReceipt
DecisionReceiptInsertResult
DecisionReceiptConflictCategory
DecisionReceiptConflictError
```

The required provenance vocabulary is:

```text
LIVE_RESULT
ACCEPTED_HISTORY_RECONCILIATION
```

`LIVE_RESULT` means an already-created live receipt is being materialized.

`ACCEPTED_HISTORY_RECONCILIATION` reserves a distinct provenance for a future
narrower reconstruction path. Defining this value does not implement scanning,
reconstruction, or scheduling.

The insert vocabulary is statement-level:

```text
INSERTED
= this SQL statement inserted a row in the caller transaction

ALREADY_PRESENT
= the same receipt identity already owns an identical complete versioned payload
```

It must never imply:

```text
INSERTED
= caller commit already completed
```

No `PERSISTED` or `DURABLE` acknowledgement belongs at this store boundary.

---

## ADR 0019 Split

ADR 0019 distinguishes evidence that may be reconstructed from accepted history
from evidence that accepted history cannot prove occurred.

The design preserves four separate cases.

### Accepted-history reconstruction

A future process may reconstruct a narrower canonical receipt for an admitted
accepted event.

Accepted history may prove:

```text
an accepted event exists
its accepted identity
its accepted order and request relationship
```

Accepted history may not reproduce the complete original live observation,
receipt identifier, timing, or flexible evidence.

### Failed-attempt persistence

Validation blocks, semantic rejection, append conflicts, technical failures,
and unresolved commit observations may never become accepted history.

Their occurrence cannot be reconstructed from accepted history.

They require live persistence if the system needs durable evidence that the
attempt occurred.

### Read-side and snapshot observation persistence

Replay validation, projection drift, missing projection state, snapshot
validation, and snapshot-assisted resolution are observations made at a
particular time.

Accepted history may allow a later validation to be performed again, but it
cannot prove that the original observation occurred.

### Live materialization

A future orchestration layer may persist a receipt immediately after a producer
result is mapped.

PR6 provides the storage foundation only.

It does not implement that orchestration.

---

## Physical PostgreSQL Boundary

Migration 007 decomposes the versioned receipt into explicit typed columns.

This supports:

```text
stable constraints
direct queries
typed indexes
permission boundaries
foreign-key protection
exact hydration
future non-Python consumers
```

First-class columns are appropriate for stable receipt fields such as:

```text
receipt and outcome identity
semantic tuple
evidence source
subject
correlation and lineage
actor
cost summary
governance flags
admission disposition
materialization provenance
materialization time
```

Flexible compact evidence remains in:

```text
evidence_summary JSONB
metadata JSONB
```

The schema must not become a generic log or trace table.

It must not store:

```text
exception objects
stack traces
large intermediate state
validator internals
resolver internals
retry attempt sequences
policy decisions
strategy execution
```

Those belong to later trace, attempt, policy, or strategy layers.

---

## Accepted-Event Foreign Key Boundary

`accepted_event_id` is nullable.

This is required because many valid receipts do not name accepted history:

```text
failed write attempts
validation-blocked candidates
read-side replay observations
snapshot-trust observations
snapshot-assisted observations
runtime evidence without accepted-event identity
```

When present, the foreign key proves only:

```text
the referenced accepted event exists
```

It does not prove:

```text
all receipt correlation fields came from accepted history
the receipt is authoritative accepted truth
the receipt may be reconstructed from history
the persistence layer may reinterpret producer identity
```

Producer mappers remain responsible for truthful correlation and lineage.

---

## Admitted-Producer Uniqueness Boundary

The partial unique index applies only to:

```text
evidence_source = WRITE_SIDE_ADMISSION

and

admission disposition = ADMITTED_TO_ACCEPTED_HISTORY
```

This protects one narrow producer identity:

```text
one admitted write-side receipt materialization
per accepted event
```

It must not apply to:

```text
idempotency-conflict receipts
validation-blocked receipts
failed write attempts
read-side receipts
snapshot receipts
non-admitted receipts that merely reference an accepted event
```

Receipt-ID identity remains separate from admitted-producer identity.

---

## Source Position Boundary

`source_global_position` is nullable and non-negative.

Zero remains valid evidence at the generic receipt and storage boundary.

Producer-specific adapters may require a positive value for statuses that were
reached only after successful validation.

The database must not replace those producer-specific rules with a global
positive-only constraint.

Therefore:

```text
generic persistence
→ allows null or position >= 0

producer mapper
→ owns status-specific positive-position requirements
```

---

## Transaction Ownership

`PostgresDecisionReceiptStore` receives an existing PostgreSQL connection.

The caller owns the transaction.

The store must:

```text
require autocommit=False
use the injected connection only
never commit
never roll back
return statement-level outcomes
leave caller commit to establish external visibility
leave caller rollback to remove the inserted row
```

This makes receipt insertion composable with a larger transaction while
avoiding a false durability acknowledgement.

A native database error may leave the transaction failed. The caller remains
responsible for rollback.

The current contract establishes safety and conditional progress:

```text
owner commits
→ contender can classify the committed row

owner rolls back
→ contender can insert

owner connection closes without commit
→ PostgreSQL rolls back the owner transaction and releases the waiter
```

It does not establish a bounded wait when the owner remains alive but idle, a
statement never completes, a pool returns an open transaction incorrectly, or a
genuine deadlock requires operational intervention. Timeout policy, pool
hygiene, deadlock handling, and retry orchestration remain outside PR6.

---

## Duplicate and Conflict Semantics

The required classification is:

```text
same receipt ID + identical complete versioned payload
→ ALREADY_PRESENT

same receipt ID + different payload
→ RECEIPT_ID_CONTENT_CONFLICT

same admitted accepted-event producer + another admitted receipt
→ ACCEPTED_PRODUCER_IDENTITY_CONFLICT
```

Semantic payload equality excludes:

```text
materialization provenance
materialized_at
```

Those fields describe the existing storage envelope, not receipt meaning.

The first successful row retains its original envelope. A later insert must not
replace, update, or enrich it.

Flexible JSON equality must preserve JSON scalar types:

```text
true ≠ 1
1 ≠ 1.0
```

Object-key order is irrelevant.

List order remains significant.

---

## PostgreSQL Store Ownership

`PostgresDecisionReceiptStore` owns:

```text
explicit column mapping
insert execution
load by receipt identity
load of admitted write-side materialization
typed row hydration
receipt-ID duplicate classification
admitted-producer conflict classification
READ COMMITTED conflict observation
validation of hydrated portability
```

It deliberately does not own:

```text
producer-result mapping
semantic reinterpretation
receipt-ID generation
materialization-provenance inference
commit or rollback
retry
policy
strategy
reconciliation scheduling
missing-receipt scanning
```

The store may validate that a stored row can still satisfy serializer version 1
without literally storing the nested serializer payload as one JSON object.

The typed row is a decomposed representation of the same versioned receipt
contract.

---

## PR4 and PR5 Compatibility

The persistence foundation must remain generic across current producer families.

Representative compatibility proof should include:

```text
write accepted
write validation blocked
replay match
replay no accepted history with persisted projection
snapshot match with loaded lineage
snapshot no accepted history with loaded lineage and position zero
snapshot-assisted resolved
snapshot-assisted tail replay failed
```

These cases collectively prove preservation of:

```text
write-side admission evidence
read-side observation evidence
snapshot trust evidence
snapshot-assisted evidence
accepted and non-accepted identities
nullable admission evidence
ORDER / PROJECTION / SNAPSHOT / RUNTIME subjects
READ_SIDE_OBSERVATION / SNAPSHOT_LINEAGE provenance
zero and positive source positions
compact state-presence summaries
all-NOT_EVALUATED producer flags
```

Persistence must not derive policy or flags from these values.

---

## Permission Boundary

The initial database-role design is:

```text
compass_app_writer
→ SELECT, INSERT

compass_readonly
→ SELECT

compass_projection_worker
→ no access

compass_snapshot_worker
→ no access

normal runtime roles
→ no UPDATE or DELETE
```

These grants establish a foundational storage capability.

They do not decide which future runtime process will materialize PR4 or PR5
receipts.

Projection-worker, snapshot-worker, or dedicated-materializer permissions
remain separate future decisions.

---

## Files Introduced by the Design

### Portable contracts

```text
src/compass/runtime/decision_receipt_serialization.py
src/storage/decision_receipt_store.py
```

### Portable-contract tests

```text
tests/unit/compass/runtime/test_decision_receipt_serialization.py
tests/unit/storage/test_decision_receipt_store.py
```

### PostgreSQL mechanism

```text
db/migrations/007_create_decision_receipts.sql
src/storage/postgres_decision_receipt_store.py
```

### PostgreSQL validation

```text
tests/integration/storage/test_decision_receipt_schema_constraints.py
tests/integration/storage/test_postgres_decision_receipt_store.py
tests/integration/security/test_decision_receipt_permissions.py
```

### Test infrastructure and setup alignment

```text
tests/integration/conftest.py
tests/integration/security/conftest.py
tests/integration/storage/test_postgres_test_database.py
docs/development/README.md
docs/development/postgres_local_setup.md
tests/README.md
tests/integration/README.md
tests/integration/storage/README.md
tests/integration/security/README.md
```

---

## Acceptance Criteria

PR6 is complete only when:

```text
serializer version 1 round-trips all current receipt fields
malformed portable payloads fail closed
storage-envelope vocabulary does not overclaim durability
migration 007 preserves current receipt vocabulary
zero remains valid at the generic source-position boundary
accepted-event identity remains optional
admitted-producer uniqueness remains narrowly partial
the store never commits or rolls back
identical duplicates remain idempotent
content and producer conflicts remain typed
PR4 and PR5 mapper-produced receipts round-trip exactly
winner commit, rollback, and connection-close paths preserve the intended
statement-level conflict semantics
permissions match the initial role boundary
runtime materialization remains absent
```

---

## Non-Goals

PR6 does not implement:

```text
automatic receipt creation
automatic persistence after mapping
producer invocation wiring
accepted-history scanning
missing-receipt reconstruction
reconstruction recipes or version ownership
background scheduling
transactional outbox
publication cursor
DiagnosticTrace
ResolutionTrace
AttemptLog
RuntimeDecisionPolicy
StrategySelector
RetryGovernance
fallback execution
rebuild execution
operator-review execution
PR5-specific query indexes
projection-worker receipt writes
snapshot-worker receipt writes
bounded idle-owner timeout policy
connection-pool cleanup policy
deadlock recovery
automatic retry orchestration
```

---

## Relationship to Other Documents

```text
ADR 0019
→ explains reconstructible and non-reconstructible evidence ownership

this design note
→ defines the PR6 layer split and implementation constraints

decision_receipt_persistence.md
→ records the completed implementation and validation evidence

Stage 4B PR7 closeout
→ should later resolve canonical boundary-note versus historical
   implementation-note naming and ownership
```
