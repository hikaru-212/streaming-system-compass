# Stage 4B PR6 — DecisionReceipt Durable Persistence

[← Back to Stage 4B](README.md)

## Purpose

PR6 establishes this explicit persistence path:

```text
DecisionReceipt
→ explicit serializer v1
→ persistence envelope
→ PostgreSQL decision_receipts row
→ exact hydration
```

The durable row preserves the shared semantic receipt and keeps storage-owned
materialization evidence in a separate envelope. The store does not map
producer results, reinterpret receipt meaning, or orchestrate when receipts are
created.

## Serialization Boundary

`decision_receipt_serialization.py` owns one fixed portable format:

- `receipt_serialization_version` is exactly `1`;
- every current `DecisionReceipt` field and supporting-contract field is owned
  explicitly;
- UUIDs are serialized as strings and enums as their stable values;
- optional fields remain present and use JSON `null` when absent;
- every object rejects missing and unknown keys;
- all integers, including nested evidence values, must fit the signed 64-bit
  range;
- booleans, integers, and floats remain distinct types and are never coerced;
- flexible JSON rejects non-finite numbers and values deeper than the shared
  maximum JSON depth;
- the payload contains no Python UUID, enum, tuple, dataclass, or other runtime
  object; and
- deserialization performs no semantic reinterpretation. It reconstructs the
  typed contract and lets `DecisionReceipt` enforce its existing invariants.

The serializer is a portability boundary, not a PostgreSQL row mapper,
persistence envelope, policy engine, or materialization workflow.

## Persistence Envelope

`DecisionReceiptMaterializationProvenance` records how a row was materialized,
separately from the semantic payload:

- `LIVE_RESULT` identifies a row materialized from an already produced live
  typed result;
- `ACCEPTED_HISTORY_RECONCILIATION` reserves explicit provenance for a future
  narrower accepted-history reconciliation path. Defining the value does not
  implement that path.

`DecisionReceiptInsertStatus` has two statement-level values:

- `INSERTED` means this SQL statement inserted a row in the caller's current
  transaction;
- `ALREADY_PRESENT` means the same receipt identity already owns an identical
  complete versioned semantic payload.

Most importantly:

```text
INSERTED
= this SQL statement inserted a row in the caller transaction

INSERTED
≠ durable commit already completed
```

The caller owns commit and rollback. No `PERSISTED` status exists at this store
boundary.

## Store Transaction Boundary

`PostgresDecisionReceiptStore` accepts an injected `psycopg.Connection` only.
The connection must have `autocommit=False`; the store rejects an autocommit
connection without changing its setting.

The store:

- never commits internally;
- never rolls back internally;
- leaves an inserted row removable by caller rollback;
- makes the row visible to other transactions only after caller commit;
- does not commit while loading; and
- leaves the connection reusable after classified duplicate and conflict
  outcomes.

A native SQL failure can still put the caller transaction into PostgreSQL's
failed state. The caller remains responsible for the required rollback.

The tested progress boundary is conditional rather than globally bounded:

```text
owner commits
→ waiting contender classifies the committed row

owner rolls back
→ waiting contender may insert

owner connection closes without commit
→ PostgreSQL rolls back the owner transaction and releases the waiter
```

PR6 does not guarantee a bounded wait when an owner remains alive but idle, a
statement never completes, a connection pool returns an open transaction
incorrectly, or a genuine deadlock requires operational handling.

## Duplicate and Conflict Semantics

The completed insert contract is:

```text
identical receipt ID + identical versioned payload
→ ALREADY_PRESENT

same receipt ID + different payload
→ RECEIPT_ID_CONTENT_CONFLICT

same admitted accepted-event producer + another admitted receipt
→ ACCEPTED_PRODUCER_IDENTITY_CONFLICT
```

The admitted-producer identity is narrowly scoped to
`WRITE_SIDE_ADMISSION` plus `ADMITTED_TO_ACCEPTED_HISTORY`. Non-admitted receipt
families may share accepted-event correlation.

Payload equality is JSON-type-aware: `true`, `1`, and `1.0` are distinct.
Object-key order is irrelevant, while list order remains significant. Envelope
fields such as provenance and materialization time do not participate in
versioned semantic-payload equality, and existing rows are never updated,
replaced, or enriched.

## PostgreSQL Schema

Migration `db/migrations/007_create_decision_receipts.sql` creates
`decision_receipts` with:

- explicit first-class typed columns for receipt identity, semantic outcome,
  subject, correlation, actor, costs, flags, and admission evidence;
- JSONB objects for `evidence_summary` and `metadata`;
- a nullable `accepted_event_id` foreign key to accepted history;
- nullable, non-negative `source_global_position`, explicitly including zero;
- four independent tri-state flag columns;
- a partial unique index for the admitted write-side producer identity;
- a separate materialization-provenance value and database-generated,
  timezone-aware materialization time; and
- no cascading foreign-key action.

The foreign key proves only that a referenced accepted event exists. The
generic persistence layer does not re-evaluate producer-owned order/request
correlation or grant accepted-history authority to receipt rows.

The current permission baseline is:

```text
compass_app_writer        SELECT, INSERT
compass_readonly          SELECT
compass_projection_worker no access
compass_snapshot_worker   no access
```

Normal runtime roles have no `UPDATE` or `DELETE` permission.

## PR4 / PR5 Compatibility

The serializer and PostgreSQL store cover these eight actual mapper-produced
round trips:

1. write accepted;
2. write validation blocked;
3. replay match;
4. replay no history with persisted projection;
5. snapshot match with lineage;
6. snapshot no history with lineage and zero position;
7. assisted resolved; and
8. assisted tail replay failed.

Persistence preserves evidence source, subject, correlation, lineage, flags,
summaries, and nullable admission evidence. It does not reinterpret PR4 or PR5
meaning, derive flags or action, or require PR5-specific indexes.

In particular, accepted history cannot reconstruct every PR5 observation. PR6
stores evidence already produced by the mappers; it does not reconstruct lost
receipts or automatically persist mapper outputs.

## Concurrency and Isolation

Under `READ COMMITTED`, a contender waiting on a uniqueness winner classifies
an identical duplicate or conflict after the winner commits. If the winner
rolls back or its connection closes without commit, the contender can insert
its own row after PostgreSQL releases the provisional uniqueness ownership.

Under `REPEATABLE READ` or `SERIALIZABLE`, PostgreSQL may expose native
`psycopg.errors.SerializationFailure`. PR6 neither classifies nor retries these
stronger-isolation failures. The caller must roll back before reusing the
failed transaction.

## Permissions

Migration 007 grants:

- `compass_app_writer`: `SELECT`, `INSERT`;
- `compass_readonly`: `SELECT`;
- `compass_projection_worker`: no access; and
- `compass_snapshot_worker`: no access.

No normal runtime role receives `UPDATE` or `DELETE`. This initial grant set
does not resolve future runtime producer permissions, projection/snapshot
worker writes, or materialization orchestration.

## Validation

The completed PR6 validation covered:

- the full repository pytest suite;
- focused serializer and storage-neutral persistence-contract unit tests;
- PostgreSQL schema, store, transaction, concurrency, and permission tests;
- actual PR4 / PR5 mapper-produced receipt round trips;
- winner commit, winner rollback, and owner connection-close concurrency paths;
- stronger-isolation failure behavior;
- direct trailing-whitespace checks; and
- `git diff --check`.

All requested test suites passed before the PR6 implementation commits were
prepared.

Exact execution counts are intentionally omitted here because the current
closeout note does not embed the final terminal transcript. Collection counts
must not be presented as execution pass counts.

## Non-Goals

PR6 explicitly defers:

- automatic receipt materialization;
- producer invocation wiring;
- a background scheduler;
- accepted-history scanning;
- missing-receipt reconciliation;
- a transactional outbox;
- a publication cursor;
- retry or stronger-isolation retry classification;
- bounded idle-owner timeout policy;
- connection-pool cleanup policy;
- deadlock recovery;
- automatic retry orchestration;
- policy;
- `DiagnosticTrace`;
- `AttemptLog`;
- PR5-specific query indexes; and
- projection/snapshot-worker write grants.

The persistence foundation also does not execute fallback, rebuild, operator
review, strategy selection, or runtime actions.
