# Post-Stage 4B — DecisionReceipt Transaction-Owner Liveness Hardening

[← Back to Stage 4B Notes](README.md)

## Status

```text
Stage 4B runtime contract
= complete

Level 1 PostgreSQL owner-liveness mechanism
= experimentally verified

repository-supported runtime owner-liveness policy
= not implemented

production timeout value
= not selected
```

This document is a **post-Stage 4B implementation note**.

It does not reopen the completed Stage 4B `DecisionReceipt` contract, and it is
not part of Stage 4B.1 DiagnosticTrace / ResolutionTrace.

Its purpose is to guide the transition from a verified PostgreSQL mechanism to
a possible repository-supported runtime transaction-owner boundary.

---

## Purpose

Stage 4B PR6 established explicit caller-owned PostgreSQL persistence for
`DecisionReceipt`.

The current store boundary is intentionally narrow:

```text
PostgresDecisionReceiptStore
= execute receipt insert/load statements
≠ begin the transaction
≠ configure the connection
≠ commit
≠ roll back
≠ authorize retry
```

That boundary protects transaction ownership, but it leaves one abnormal-path
liveness question unresolved:

```text
owner inserts a receipt without committing
→ a uniqueness-conflicting contender waits
→ owner remains alive but idle
→ no commit, rollback, or connection close occurs
→ contender progress has no explicit bound
```

The implementation objective is not merely to enable a PostgreSQL setting.

The objective is to define whether the repository should support a bounded
transaction-owner lifecycle that:

```text
establishes a transaction-local liveness policy
→ invokes the statement-only receipt store
→ completes through commit or rollback
→ discards a server-terminated connection
→ preserves technical failure evidence
→ does not invent semantic or retry policy
```

---

## Why This Follow-up Exists

The existing Stage 4B persistence contract proves important safety properties:

- the store rejects autocommit connections;
- the caller owns commit and rollback;
- statement-level `INSERTED` does not claim commit durability;
- identical durable identities remain idempotent;
- conflicting receipt content fails closed;
- conflicting admitted-producer identity fails closed;
- tested commit, rollback, and connection-close paths release waiting
  contenders.

Those guarantees do not establish bounded progress when an owner remains live
but idle.

The distinction is:

```text
safety
= conflicting durable receipt facts are not both preserved

conditional progress
= a contender resumes after a tested owner-resolution path

bounded abnormal-path liveness
= an unresolved owner is forced to resolve within an explicit bound
```

The current repository has safety and selected conditional-progress evidence.

The Level 1 experiment adds evidence for one physical cleanup mechanism, but it
does not yet establish a supported production policy.

---

## Verified Level 1 Evidence

The experiment in:

`tests/integration/storage/test_postgres_decision_receipt_store.py`

characterizes PostgreSQL transaction-local
`idle_in_transaction_session_timeout` behavior.

The verified schedule is:

```text
owner inserts a DecisionReceipt without commit
→ contender attempts a conflicting admitted-producer insertion
→ pg_stat_activity proves the contender reached a real Lock wait
→ owner transaction applies a transaction-local idle timeout
→ owner sends no further work
→ PostgreSQL terminates the owner backend
→ owner transaction is rolled back
→ contender resumes and returns INSERTED
→ contender commits
→ fresh connection verifies only the contender receipt is durable
→ owner connection is broken and unusable
```

The focused live PostgreSQL result is:

```text
2 passed
48 deselected
```

The experiment verifies:

- `set_config(..., true)` can scope the setting to one transaction;
- rollback restores the previous session value;
- a live-but-idle owner can be terminated by PostgreSQL;
- the owner transaction is rolled back by server termination;
- the uniqueness-conflicting contender can resume;
- the rolled-back owner receipt is absent;
- the contender receipt can become the sole durable record;
- psycopg surfaces
  `psycopg.errors.IdleInTransactionSessionTimeout`;
- the observed SQLSTATE is `25P03`;
- the terminated owner connection reports
  `TransactionStatus.UNKNOWN`;
- the terminated connection is closed and broken and must be discarded.

The test-only timeout value is evidence-fixture configuration.

It is not a production recommendation.

---

## What the Experiment Does Not Prove

The experiment does not prove that production runtime behavior is protected.

Only the test explicitly applies the transaction-local setting.

The current runtime does not yet guarantee:

- that every DecisionReceipt transaction has a declared owner;
- that an owner applies a timeout before receipt work begins;
- that timeout configuration is available or validated;
- that a broken connection is discarded by an application or pool;
- that the timeout is safe for all application-writer transactions;
- that the setting is applied to every receipt persistence path;
- that a production timeout value has been calibrated;
- that timeout evidence becomes a `SemanticOutcome`;
- that timeout evidence becomes a durable `DecisionReceipt`;
- that retry is safe or authorized;
- that DiagnosticTrace or AttemptLog records the failure;
- that monitoring, alerting, or operational recovery exists.

The experiment therefore changes repository evidence, not production behavior.

---

## Current Production Gap

The current call shape is effectively:

```text
caller creates connection
→ caller or psycopg begins transaction
→ PostgresDecisionReceiptStore executes statements
→ caller is expected to commit, roll back, or close
```

There is no dedicated production abstraction that owns the complete
DecisionReceipt transaction lifecycle.

The missing responsibilities are:

| Responsibility | Current owner | Gap |
|---|---|---|
| Connection creation | Caller | No purpose-specific receipt connection policy |
| Transaction begin | Caller / implicit psycopg behavior | No explicit receipt transaction boundary |
| Transaction-local timeout | Nobody in production | Level 1 test only |
| Receipt statement execution | `PostgresDecisionReceiptStore` | Intentionally statement-only |
| Commit | Caller | No supported receipt orchestration contract |
| Rollback after ordinary failure | Caller | No centralized cleanup path |
| Discard after server termination | Caller | No explicit broken-connection contract |
| Technical failure evidence | Raw psycopg exception | No stable repository result contract |
| Semantic interpretation | Not assigned | Must not be inferred automatically |
| Retry authorization | Future governance | Explicitly out of scope |

---

## Responsibility Boundary

### `PostgresDecisionReceiptStore`

The store should remain responsible for:

- validating public store arguments;
- serializing the receipt through the strict serializer;
- executing insert and load statements;
- classifying supported durable identity and content outcomes;
- returning statement-level persistence results;
- preserving raw PostgreSQL failure behavior outside its explicit conflict
  contract.

The store should not become responsible for:

- selecting timeout values;
- applying session or transaction policy;
- beginning transactions;
- committing or rolling back;
- closing or discarding connections;
- retrying;
- mapping infrastructure failure into semantic meaning;
- writing a second receipt about its own failed receipt transaction.

### Explicit transaction owner

A future repository-supported transaction owner may be responsible for:

```text
obtain an approved connection
→ establish the transaction boundary
→ apply the transaction-local owner-liveness policy
→ invoke PostgresDecisionReceiptStore
→ commit on successful completion
→ roll back recoverable failures
→ discard a server-terminated connection
→ return neutral technical completion or failure evidence
```

The transaction owner must not:

- authorize retry;
- evaluate DecisionReceipt governance flags;
- create policy decisions;
- modify the receipt schema;
- convert every PostgreSQL error into a semantic outcome;
- silently absorb a broken connection;
- apply the receipt timeout to unrelated write-side transactions.

### Connection factory or pool

A connection factory may provide construction and environment validation, but
a generic repository-wide factory should not silently apply receipt-specific
transaction policy.

If pooling is introduced later, the pool integration must distinguish:

```text
transaction can be rolled back and reused
≠
backend was terminated and connection must be discarded
```

Adding a pool is not required to complete the first runtime owner-liveness
implementation.

---

## Preferred Design Direction to Audit

The preferred first production direction is an explicit, purpose-specific
DecisionReceipt transaction-owner abstraction.

A candidate shape is:

```text
DecisionReceiptTransactionOwner
```

or:

```text
PostgresDecisionReceiptTransaction
```

The name is not yet accepted.

The abstraction would own lifecycle, not storage semantics.

A possible call shape is:

```python
result = transaction_owner.persist(
    receipt,
    materialization_provenance=...,
)
```

Internally:

```text
validate configured timeout
→ begin or establish transaction scope
→ apply transaction-local setting
→ call PostgresDecisionReceiptStore.insert(...)
→ commit
→ return durable-completion result
```

On failure:

```text
ordinary transaction failure
→ roll back
→ preserve technical failure

server-terminated owner connection
→ do not attempt reuse
→ close/discard
→ preserve exact technical failure
```

This direction is preferred over role-wide or database-wide configuration
because the existing application-writer role also participates in accepted
event and idempotency transactions whose expected duration may differ.

This direction remains a candidate until the production impact audit resolves
configuration ownership, call-site integration, and failure-result shape.

---

## Configuration Boundary

A production timeout cannot be copied from the test fixture.

The repository must decide:

- whether the timeout is mandatory or optional;
- whether the value is configured in milliseconds, seconds, or a duration
  object;
- where configuration is loaded and validated;
- whether zero disables the policy;
- whether invalid or unsafe values fail fast;
- whether each environment may select its own value;
- whether the transaction owner receives an already validated value;
- whether the repository provides a default at all.

The preferred mechanism remains transaction-local:

```text
set_config(
    'idle_in_transaction_session_timeout',
    configured_value,
    true
)
```

The current evidence does not justify:

- `ALTER DATABASE`;
- `ALTER ROLE`;
- a repository-wide session setting;
- a shared timeout for all `compass_app_writer` transactions;
- a migration-owned production value.

No migration is currently expected.

---

## Failure and Connection-State Contract

The verified timeout failure is a technical infrastructure event.

Observed evidence includes:

```text
exception class
= psycopg.errors.IdleInTransactionSessionTimeout

SQLSTATE
= 25P03

transaction status
= UNKNOWN

connection state
= closed and broken
```

The production owner must distinguish this from a transaction that merely
entered `INERROR`.

For an ordinary transaction failure:

```text
connection remains live
→ rollback may restore reuse
```

For an idle-owner server termination:

```text
backend is gone
→ server already rolled back the open transaction
→ connection cannot be recovered by rollback
→ connection must be discarded
```

A future neutral technical error contract may be useful, but it must not imply:

- semantic invalidity;
- safe replay;
- retry candidacy;
- retry authorization;
- operator action;
- fallback selection.

---

## SemanticOutcome Boundary

The timeout does not automatically require a new `SemanticOutcome` contract.

The physical event establishes facts such as:

- the transaction owner did not complete normally;
- the server terminated the backend;
- the pending receipt transaction was rolled back;
- the connection became unusable;
- a blocked contender may have progressed.

Those facts may later be interpreted by a producer-specific semantic adapter,
DiagnosticTrace, AttemptLog, metrics, or operational logging.

The repository must first decide what object has enough context to interpret
the failure truthfully.

The following mapping is not approved:

```text
IdleInTransactionSessionTimeout
→ retry candidate
```

The following is also not approved:

```text
IdleInTransactionSessionTimeout
→ semantically invalid business operation
```

A technical cleanup mechanism must remain separate from semantic and policy
authority.

---

## DecisionReceipt Boundary

The timeout does not currently require changing:

- the `DecisionReceipt` dataclass;
- strict serializer v1;
- the PostgreSQL receipt table;
- persistence-envelope contracts;
- migration 007.

A receipt-persistence transaction that is rolled back cannot durably preserve
the receipt it was attempting to write.

Therefore, this design must not assume that the failed transaction can record
its own failure through the same receipt row.

Possible future evidence owners include:

- caller-visible technical results;
- DiagnosticTrace / ResolutionTrace;
- AttemptLog;
- operational metrics or logs;
- a separately owned durable failure-evidence transaction.

No evidence owner is selected by this note.

---

## Interaction with Stage 4B.1

Stage 4B.1 DiagnosticTrace / ResolutionTrace remains the next formal
runtime-governance stage.

The owner-liveness work is an independent PostgreSQL hardening follow-up.

It may proceed before Stage 4B.1 when isolated, but it must not:

- redefine DiagnosticTrace early;
- require Stage 4B.1 to release database resources;
- encode trace or resolution policy into the transaction owner;
- delay Stage 4B.1 through unnecessary production-hardening expansion.

Later traces may consume the resulting technical evidence.

The physical cleanup mechanism must remain usable without trace support.

---

## Capacity-Pressure Boundary

Idle-owner liveness is separate from capacity pressure.

```text
idle owner / blocked contender
= one unresolved transaction lifecycle
= abnormal-path liveness

rate limiting / bounded concurrency / queues / backpressure
= too much work entering or propagating through the system
= capacity pressure
```

A timeout does not provide rate limiting.

Rate limiting does not guarantee transaction-owner resolution.

The two concerns should remain separate in roadmap and implementation work.

---

## Expected Production File Impact

The exact files depend on the impact audit, but a repository-supported
implementation may involve:

| Candidate file | Likely responsibility | Status |
|---|---|---|
| `src/storage/postgres_decision_receipt_transaction.py` | Explicit receipt transaction owner | Candidate |
| `src/storage/postgres_connection.py` | Purpose-specific construction or validated configuration input | Possible |
| Existing runtime/bootstrap call site | Use supported transaction owner | Audit required |
| `tests/unit/storage/test_postgres_decision_receipt_transaction.py` | Lifecycle and failure-contract unit tests | Candidate |
| `tests/integration/storage/test_postgres_decision_receipt_store.py` | Physical PostgreSQL evidence | Already extended |
| New transaction-owner integration tests | Commit, rollback, timeout, discard | Candidate |
| `.env.example` | Public configuration contract | Only if configuration is approved |
| Development PostgreSQL docs | Local configuration and validation | Later |
| Current boundary and reasoning notes | Updated runtime guarantee | Later |
| Migration 008 | Role/database policy | Not expected |

The existing `PostgresDecisionReceiptStore` should not be modified merely to
apply the timeout.

---

## Proposed Delivery Sequence

### Commit 1 — Design baseline

```text
docs(postgres): design DecisionReceipt owner-liveness hardening
```

Files:

- this implementation note;
- the Stage 4B implementation-note index.

Purpose:

- preserve document-first sequencing;
- define the current evidence and production gap;
- establish responsibilities and non-goals;
- guide the production impact audit.

### Commit 2 — Level 1 executable evidence

```text
test(postgres): characterize idle DecisionReceipt owner cleanup
```

File:

- `tests/integration/storage/test_postgres_decision_receipt_store.py`

Purpose:

- preserve the verified PostgreSQL and psycopg behavior;
- prove transaction-local scope;
- prove owner rollback and contender progress;
- prove broken-connection discard requirements.

### Commit 3 — Production impact decision

This should be documentation-first and should occur only after a read-only
audit identifies:

- current runtime call sites;
- transaction ownership;
- connection construction;
- configuration ownership;
- failure propagation;
- pool assumptions;
- exact source and test impact.

Possible subject:

```text
docs(postgres): define DecisionReceipt transaction-owner contract
```

### Commit 4 — Production implementation

Only if the impact decision approves implementation.

Possible subject:

```text
feat(postgres): add bounded DecisionReceipt transaction owner
```

This commit would include production code and checklist-style PR validation.

### Commit 5 — Runtime evidence closeout

After production implementation and full validation:

```text
docs(postgres): close DecisionReceipt owner-liveness hardening
```

This would update current boundaries, development guidance, and backlog status.

---

## Validation Requirements

### Level 1 evidence

Required:

- transaction-local setting scope test;
- real PostgreSQL lock-wait observation;
- owner backend termination;
- server-side transaction rollback;
- contender resumption;
- durable final-state verification;
- exact psycopg exception and SQLSTATE;
- broken connection state;
- bounded thread and connection cleanup.

### Production transaction owner

Required if implemented:

- configured timeout validation;
- timeout applied before receipt work;
- successful commit path;
- ordinary rollback path;
- server-terminated connection discard path;
- no reuse of broken connections;
- no hidden store commit or rollback;
- no retry authorization;
- no role/database-wide setting;
- focused unit tests;
- PostgreSQL integration tests;
- full affected storage suite;
- documentation and configuration validation.

### Production hardening

Deferred:

- workload-based timeout calibration;
- connection-pool integration;
- monitoring and alerting;
- operational runbook;
- chaos and soak evidence;
- deployment-specific policy;
- deadlock and statement-timeout coordination.

---

## Explicit Non-goals

This follow-up does not currently implement:

- a production timeout value;
- database-wide timeout configuration;
- role-wide timeout configuration;
- a migration;
- generic application-writer timeout policy;
- statement timeout;
- lock timeout;
- deadlock recovery;
- connection pooling;
- automatic retry;
- retry candidacy or authorization;
- a new `SemanticOutcome`;
- a new `DecisionReceipt` field;
- serializer v2;
- receipt-table schema changes;
- automatic receipt materialization;
- accepted-history reconciliation;
- DiagnosticTrace;
- ResolutionTrace;
- AttemptLog;
- policy, strategy, or action execution;
- rate limiting, queues, or backpressure;
- monitoring, alerting, deployment, or operational runbooks.

---

## Human Decisions Required

Before production code is authorized, decide:

1. Whether the repository should adopt a supported receipt-specific
   transaction owner.
2. Which module owns the timeout configuration.
3. Whether configuration is mandatory and whether a default exists.
4. Which production call site invokes the owner.
5. Whether the owner returns raw psycopg failures or a neutral technical result.
6. How broken connections are discarded without assuming a pool.
7. Whether future pooling changes the owner contract.
8. Which layer may interpret the failure semantically.
9. Which layer may durably record the failed attempt.
10. Whether Level 2 implementation should occur before or after Stage 4B.1.

---

## Completion Criteria

This follow-up is complete only when the repository can truthfully claim:

```text
a supported DecisionReceipt transaction owner
applies an approved transaction-local liveness policy
and owns commit / rollback / broken-connection discard
```

and when executable tests prove:

```text
normal completion
→ durable receipt

ordinary failure
→ rollback and recoverable connection lifecycle

idle-owner termination
→ server rollback
→ contender progress
→ broken connection discarded
```

Until then, the correct repository statement remains:

```text
transaction-local owner cleanup mechanism characterized
≠
production owner-liveness policy implemented
```
