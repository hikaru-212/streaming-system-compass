# Post-Stage 4B — DecisionReceipt Transaction-Owner Liveness Hardening

[← Back to Stage 4B Notes](README.md)

## Status

```text
Stage 4B runtime contract
= complete

Level 1 PostgreSQL owner-liveness mechanism
= experimentally verified

production transaction-owner contract
= implemented, tested, and merged

repository-supported runtime owner-liveness implementation
= `PostgresDecisionReceiptTransactionOwner`

production timeout value
= not selected

automatic production materialization caller
= not implemented
```

This document is a **post-Stage 4B implementation note**.

It does not reopen the completed Stage 4B `DecisionReceipt` contract, and it is
not part of Stage 4B.1 DiagnosticTrace / ResolutionTrace.

Its purpose is to preserve the verified PostgreSQL mechanism, the approved
first-version transaction-owner boundary, and the implementation that now owns
one explicitly invoked receipt-governance transaction.

Current source is
`src/storage/postgres_decision_receipt_transaction_owner.py`. The owner accepts
an already-complete receipt, acquires a dedicated connection, applies the
required transaction-local timeout, owns commit or rollback, and closes or
discards the connection. It does not construct receipts, select a production
timeout, or provide an automatic materialization caller.

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

The approved objective is a transaction-owner lifecycle with bounded
live-but-idle cleanup that:

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

Those guarantees do not establish bounded live-but-idle cleanup.

The distinction is:

```text
safety
= conflicting durable receipt facts are not both preserved

conditional progress
= a contender resumes after a tested owner-resolution path

bounded live-but-idle abnormal-path cleanup
= an owner that becomes idle in an open transaction is forced to resolve
  within the configured idle bound
```

This mechanism does not bound connection acquisition, actively executing
statements, total transaction wall-clock duration, contender lock wait, commit
invocation or response, deadlock resolution, or the complete transaction
lifecycle. The owner still owns that complete lifecycle as a responsibility
boundary.

The current repository has safety and selected conditional-progress evidence.

The Level 1 experiment adds evidence for one physical cleanup mechanism. This
note now defines the production contract, but the supported runtime owner and
production timeout duration remain unimplemented.

---

## ADR 0019 Materialization Boundary

ADR 0019 already defines the target split materialization model.

This follow-up does not reopen the question of whether accepted business facts
and complete `DecisionReceipt` rows must commit in one transaction.

### Accepted results

For an admitted accepted result:

```text
accepted event
+
idempotency record
```

remain the authoritative business facts.

They commit atomically in the existing business transaction.

The complete `DecisionReceipt` is not a precondition for that commit.

The target flow is:

```text
commit authoritative business transaction
→ build the live accepted-result DecisionReceipt
→ attempt receipt persistence through a separate governance transaction
```

If the immediate receipt is absent later:

```text
accepted history
→ detect missing accepted receipt
→ reconstruct a narrower versioned canonical receipt
→ persist through reconciliation
```

### Typed non-ACCEPTED observations

For typed non-`ACCEPTED` observations such as:

- `REPLAY`;
- `CONFLICT`;
- `VALIDATION_BLOCKED`;
- stream-level `ADMISSION_REJECTED`;
- append-level `ADMISSION_REJECTED`;

the target flow is:

```text
typed runtime observation
→ SemanticOutcome
→ DecisionReceipt
→ separate governance transaction
→ report receipt-persistence outcome separately
→ preserve the original business result
```

These observations do not gain authority merely because a related accepted
event exists.

### Owner-liveness relationship

The Level 1 owner-liveness experiment applies to the separate governance
transactions defined by ADR 0019.

It protects future:

- accepted live-result receipt materialization;
- typed non-`ACCEPTED` observation persistence;
- accepted-history receipt reconciliation.

It does not apply the receipt timeout to the authoritative accepted-event and
idempotency transaction.

The relationship is:

```text
ADR 0019
= selects the split materialization and authority model

owner-liveness hardening
= bounds live-but-idle abnormal-path cleanup inside separate governance
  transactions

implemented transaction owner
= implements connection, transaction, timeout, commit, rollback, and discard

later governance
= interprets failure and decides policy or retry
```

Therefore:

```text
idle-owner hardening
≠ reopening accepted-event atomicity

idle-owner hardening
≠ coupling receipt availability to business availability

idle-owner hardening
= resilience for separate governance persistence
```


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

## Pre-Implementation Production Gap

Before the dedicated owner was implemented, the supported store call shape was:

```text
caller creates connection
→ caller or psycopg begins transaction
→ PostgresDecisionReceiptStore executes statements
→ caller is expected to commit, roll back, or close
```

There was no dedicated production abstraction that owned the complete
DecisionReceipt transaction lifecycle.

The approved contract below resolved the first-version identity, connection
ownership, timeout input, ordering, and outer technical-result meanings. This
table preserves the gap against which the implemented owner was reviewed.

The pre-implementation missing responsibilities were:

| Responsibility | Pre-implementation owner | Gap |
|---|---|---|
| Connection creation | Caller | No implemented purpose-specific receipt factory |
| Transaction begin | Caller / implicit psycopg behavior | No implemented receipt owner boundary |
| Transaction-local timeout | Nobody in production | Level 1 test only |
| Receipt statement execution | `PostgresDecisionReceiptStore` | Intentionally statement-only |
| Commit | Caller | No implemented receipt owner |
| Rollback after ordinary failure | Caller | No centralized cleanup path |
| Discard after server termination | Caller | No explicit broken-connection contract |
| Technical failure evidence | Raw psycopg exception | No implemented stable outer result type |
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

`DecisionReceiptInsertResult` remains statement-level evidence:

```text
INSERTED
≠ committed

ALREADY_PRESENT
≠ owner transaction completed
```

The store should not become responsible for:

- acquiring connections;
- selecting timeout values;
- applying session or transaction policy;
- beginning transactions;
- committing or rolling back;
- closing or discarding connections;
- reporting durable transaction completion;
- retrying;
- mapping infrastructure failure into semantic meaning;
- writing a second receipt about its own failed receipt transaction.

### Explicit transaction owner

The implemented class responsibility and placement are:

```text
PostgresDecisionReceiptTransactionOwner
→ src/storage/postgres_decision_receipt_transaction_owner.py
```

The owner persists an already-complete `DecisionReceipt` plus the required
storage-envelope provenance, including
`DecisionReceiptMaterializationProvenance`. It owns lifecycle, not receipt
semantics.

The owner is responsible for:

```text
validate the mandatory timeout input
→ obtain a dedicated governance connection
→ require an exclusive clean transaction entry state
→ apply the transaction-local owner-liveness setting
→ invoke PostgresDecisionReceiptStore.insert(...)
→ commit on successful completion
→ roll back ordinary pre-commit failures
→ discard a server-terminated or commit-ambiguous connection
→ return neutral commit-aware technical evidence
```

The owner does not:

- authorize retry;
- construct or semantically map a `DecisionReceipt`;
- allocate receipt or outcome identity;
- schedule materialization or discover reconciliation work;
- evaluate DecisionReceipt governance flags;
- create policy decisions;
- create `DiagnosticTrace` or `AttemptLog`;
- own the accepted-event transaction;
- modify the receipt schema;
- convert every PostgreSQL error into a semantic outcome;
- silently absorb a broken connection;
- apply the receipt timeout to unrelated write-side transactions.

### Dedicated connection factory

The first production version uses a purpose-specific dedicated connection
factory. The public owner API does not accept an arbitrary caller-owned
PostgreSQL connection.

The owner owns the complete connection lifecycle:

```text
acquire
→ use for one governance transaction
  with transaction-local idle-owner protection
→ commit or roll back
→ close or discard
```

This call shape structurally prevents accidental reuse of the accepted-event
business transaction connection.

The first version does not support or define connection-pool lease semantics.
If pooling is introduced later, its separate integration must distinguish:

```text
transaction can be rolled back and reused
≠
backend was terminated and connection must be discarded
```

No pool abstraction is introduced by this contract.

---

## Approved First-Version Design Direction

The approved direction is the explicit, purpose-specific
`PostgresDecisionReceiptTransactionOwner` described above.

The public persistence operation receives:

- an already-complete `DecisionReceipt`;
- the required storage-envelope provenance, including
  `DecisionReceiptMaterializationProvenance`.

Exact method and result symbol names remain implementation-review details. The
operation does not accept an arbitrary caller-owned connection.

Internally:

```text
validate configuration before connection acquisition
→ acquire a dedicated PostgreSQL connection
→ require autocommit=False
→ require clean TransactionStatus.IDLE
→ apply transaction-local idle_in_transaction_session_timeout
→ call PostgresDecisionReceiptStore.insert(...)
→ attempt commit
→ classify a commit-aware technical outcome
→ close or discard the connection
```

The first transaction-local PostgreSQL statement may open the top-level
transaction under normal psycopg behavior. This contract does not require a new
explicit `BEGIN` abstraction. The important entry invariant is a clean `IDLE`
connection owned exclusively by this governance transaction owner.

On failure:

```text
ordinary pre-commit transaction failure
→ roll back
→ preserve technical failure

server-terminated owner connection
→ do not attempt reuse
→ discard
→ preserve exact technical failure

commit invocation began without acknowledged success
→ classify durability as UNKNOWN
→ do not claim rollback proves non-commit
→ discard
```

This direction is preferred over role-wide or database-wide configuration
because the existing application-writer role also participates in accepted
event and idempotency transactions whose expected duration may differ.

The transaction owner remains infrastructure only until separately authorized
callers wire accepted live results, typed non-`ACCEPTED` observations, or
accepted-history reconciliation.

---

## Configuration Boundary

A production timeout cannot be copied from the test fixture.

The first-version application-level shape is conceptually:

```text
idle_in_transaction_session_timeout_ms: int
```

Its approved semantics are:

- explicit and mandatory;
- no production default;
- milliseconds as the only application-level unit;
- greater than zero;
- booleans rejected rather than accepted as integers;
- validation before connection acquisition;
- transaction-local application by the owner;
- server rejection fails closed before receipt insertion.

Zero and explicitly disabled values are not part of the first-version
owner-liveness contract. The contract does not select a production duration or
hard-code an application-side PostgreSQL maximum without repository evidence.
The external configuration source and production duration remain
implementation and deployment decisions.

The approved mechanism is transaction-local:

```text
set_config(
    'idle_in_transaction_session_timeout',
    configured_value,
    true
)
```

The first-version contract prohibits:

- `ALTER DATABASE`;
- `ALTER ROLE`;
- a repository-wide session setting;
- a shared timeout for all `compass_app_writer` transactions;
- a persistent session setting;
- a migration-owned production value.

No schema or migration change is permitted by the first-version contract.

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

### Commit-aware outer result

The implemented outer technical result carries at least:

```text
durability
= COMMITTED | NOT_COMMITTED | UNKNOWN

statement_result
= DecisionReceiptInsertResult | none

failure category
= stable technical category | none

typed conflict evidence
= preserved DecisionReceiptConflictError evidence | none

rollback disposition
= NOT_REQUIRED | CONFIRMED | FAILED | NOT_POSSIBLE

connection disposition
= CLOSED | DISCARDED | CLEANUP_FAILED
```

Connection disposition applies when a connection was acquired. A generic
failure category must not erase existing safe typed conflict category or
evidence. Exact Python symbol and field names may be finalized during
implementation review, but these meanings must not be weakened.

Expected operational PostgreSQL and connection outcomes are represented as
typed technical evidence. Constructor, configuration, and programmer-invariant
violations may remain exceptions.

SQLSTATE may be preserved as technical diagnostic metadata when available. It
does not become semantic or retry authority.

### Acknowledged commit

```text
commit acknowledgement received
→ COMMITTED
```

A later connection-close or cleanup failure adds cleanup evidence. It does not
overwrite an already established `COMMITTED` result.

### Failure before commit invocation

```text
commit has not been invoked
→ NOT_COMMITTED
```

This rule includes, when the phase is known:

- connection-acquisition failure;
- transaction-local timeout-configuration failure;
- INSERT or lookup failure;
- typed `DecisionReceiptConflictError`;
- ordinary pre-commit exception;
- rollback failure;
- the experimentally characterized
  `IdleInTransactionSessionTimeout`.

A rollback failure adds cleanup evidence and forces connection discard. It does
not create commit ambiguity when no commit request was sent.

For an ordinary live-connection failure:

```text
connection remains live
→ rollback may restore a clean state
→ close the dedicated connection
```

For the characterized idle-owner server termination:

```text
backend is gone
→ server already rolled back the open transaction
→ client rollback cannot recover the connection
→ durability = NOT_COMMITTED
→ rollback disposition = NOT_POSSIBLE
→ connection disposition = DISCARDED
```

### Failure after commit invocation begins

```text
commit invocation began
and acknowledged success did not return
→ UNKNOWN
```

The first version conservatively classifies all commit-phase exceptions,
connection loss, and response ambiguity as `UNKNOWN`. It does not attempt to
classify a commit exception as confirmed non-commit unless a later executable
contract provides authoritative evidence.

For `UNKNOWN`:

- do not claim rollback can prove non-commit;
- discard the connection;
- preserve the technical evidence;
- leave later resolution to reconciliation or another authorized evidence
  layer.

### Typed conflict handling

The owner may catch the existing typed `DecisionReceiptConflictError` to:

```text
preserve typed conflict evidence
→ roll back the governance transaction
→ report NOT_COMMITTED
→ close or discard according to connection health
```

The existing conflict contract remains unchanged.

An identical duplicate that returns `ALREADY_PRESENT` is not a conflict.
`DecisionReceiptConflictError` represents the supported conflicting-content or
producer-identity path, and the outer result must preserve its existing safe
typed evidence separately from any generic failure category.

No technical result or conflict may imply:

- semantic invalidity;
- safe replay;
- retry candidacy;
- retry authorization;
- business-command failure;
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

The approved outer result is the immediate caller-visible technical evidence.
Possible later evidence owners include:

- caller-visible technical results;
- DiagnosticTrace / ResolutionTrace;
- AttemptLog;
- operational metrics or logs;
- a separately owned durable failure-evidence transaction.

No durable failure-evidence owner or semantic interpreter is selected by this
note.

---

## Interaction with Stage 4B.1

Stage 4B.1 DiagnosticTrace / ResolutionTrace is complete. Stage 4B.2
measurement / cost evidence is the next formal stage.

The owner-liveness work is an independent PostgreSQL hardening follow-up.

Its earlier ability to proceed before Stage 4B.1 depended on remaining isolated,
and it still must not:

- redefine DiagnosticTrace;
- require Stage 4B.1 to release database resources;
- encode trace or resolution policy into the transaction owner;
- reopen Stage 4B.1 through unnecessary production-hardening expansion.

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

## Pre-Implementation File-Impact Audit

The completed impact audit recorded this first-version production direction.
The status column is updated to current source while the original responsibility
split is preserved:

| Expected file | Likely responsibility | Status |
|---|---|---|
| `src/storage/postgres_decision_receipt_transaction_owner.py` | Approved dedicated receipt governance-transaction owner | Implemented |
| `src/storage/postgres_connection.py` | Existing generic low-level connection helper | No first-version change required |
| Existing runtime/bootstrap call site | Use supported transaction owner | Deferred; no caller selected |
| `tests/unit/storage/test_postgres_decision_receipt_transaction_owner.py` | Lifecycle and failure-contract unit tests | Implemented |
| `tests/integration/storage/test_postgres_decision_receipt_store.py` | Physical PostgreSQL evidence | Already extended |
| `tests/integration/storage/test_postgres_decision_receipt_transaction_owner_integration.py` | Commit, rollback, timeout, discard, and commit ambiguity | Implemented |
| External configuration source | Production duration input | Deferred; no file selected |
| Development PostgreSQL docs | Local configuration and validation | Later, after production duration ownership |
| Current boundary and implementation notes | Contract now; runtime guarantee after implementation | Current and later |
| Schema or migration files | Durable receipt structure or timeout policy | No change permitted |

The existing `PostgresDecisionReceiptStore` should not be modified merely to
apply the timeout or report commit-aware completion.

---

## Historical Delivery Sequence

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

### Commit 3 — Production contract decision — current documentation change

The read-only impact audit identified:

- current runtime call sites;
- transaction ownership;
- connection construction;
- configuration ownership;
- failure propagation;
- pool assumptions;
- exact source and test impact.

Suggested subject:

```text
docs(postgres): define DecisionReceipt transaction-owner contract
```

This documentation change approves the owner identity, dedicated connection
factory boundary, mandatory millisecond timeout input, transaction ordering,
commit-aware technical-result meanings, conservative durability rules, and
first-version non-goals. It does not implement production behavior.

### Commit 4 — Production implementation

Only after the documentation contract is reviewed and accepted.

Possible subject:

```text
feat(postgres): add DecisionReceipt transaction owner
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

Implemented boundary:

- mandatory positive integer-millisecond timeout validation before connection
  acquisition, including boolean rejection;
- dedicated purpose-specific connection acquisition;
- rejection of autocommit or non-`IDLE` entry state;
- transaction-local timeout applied before receipt work;
- commit-acknowledged `COMMITTED` path for statement-level `INSERTED` and
  `ALREADY_PRESENT`;
- ordinary rollback path;
- typed conflict rollback and `NOT_COMMITTED` reporting;
- server-terminated connection discard path;
- commit-phase exception and connection-loss classification as `UNKNOWN`;
- cleanup failure that does not overwrite established durability;
- no reuse of broken connections;
- no arbitrary caller-owned connection in the public API;
- no reuse of the accepted-event business transaction connection;
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

The first transaction-owner infrastructure does not include:

- a production timeout value;
- database-wide timeout configuration;
- role-wide timeout configuration;
- a migration;
- generic application-writer timeout policy;
- statement timeout;
- lock timeout;
- deadlock recovery;
- connection pooling;
- production caller wiring;
- automatic retry;
- retry candidacy or authorization;
- `SemanticOutcome` mapping or a new `SemanticOutcome`;
- `DecisionReceipt` construction;
- receipt or outcome identity allocation;
- a new `DecisionReceipt` field;
- serializer v2;
- receipt-table schema changes;
- accepted live-result orchestration;
- typed non-`ACCEPTED` orchestration;
- accepted-history reconciliation;
- DiagnosticTrace;
- ResolutionTrace;
- AttemptLog;
- metrics infrastructure;
- durable self-recording of owner failure;
- policy, strategy, or action execution;
- rate limiting, queues, or backpressure;
- monitoring, alerting, deployment, or operational runbooks.

The implemented owner may be used by future accepted live-result
materialization, typed non-`ACCEPTED` persistence, and accepted-history
reconciliation. It owns only their final separately owned
governance-persistence transaction.

---

## Historical Human Decisions Before Implementation

The following list is preserved as the pre-implementation review record. The
public symbol/result names, test seam, delivery ordering, and relationship to
Stage 4B.1 were resolved by the implementation and repository chronology.
Configuration ownership, production duration, automatic callers, identity
allocation, semantic interpretation, unsuccessful-attempt evidence,
reconciliation, and pooling remain future decisions.

Before production code was authorized, the review questions were:

1. Where the mandatory timeout configuration is loaded before the owner
   receives and validates it.
2. Which positive production timeout duration each environment supplies.
3. Whether later repository evidence justifies application-side validation of
   a PostgreSQL maximum beyond the approved greater-than-zero rule.
4. Exact Python symbol and field names for the approved outer technical-result
   meanings.
5. The narrow implementation seam used to unit-test lifecycle behavior while
   `PostgresDecisionReceiptStore` remains bound to a real psycopg connection.
6. Which runtime call sites invoke:
   - accepted live-result materialization;
   - typed non-`ACCEPTED` persistence;
   - accepted-history reconciliation.
7. Which component allocates receipt and outcome identity for each caller.
8. Which later layer may interpret the technical failure semantically.
9. Which later layer may durably preserve unsuccessful materialization
   attempts.
10. How future accepted-history reconciliation resolves `UNKNOWN` durability.
11. The future connection-pool lease, healthy-release, and invalidation
    contract, if pooling is introduced.
12. Whether Stage 4B.1 proceeds before, after, or in parallel with the
   infrastructure work.

---

## Completion Criteria

The current chronology is:

```text
Level 1 PostgreSQL mechanism
= experimentally verified

production owner contract
= defined by this documentation change

production owner implementation
= implemented, tested, and merged

automatic callers and reconciliation
= not implemented
```

The repository can now truthfully claim:

```text
a supported DecisionReceipt governance-transaction owner
applies an approved transaction-local liveness policy
and owns commit, rollback, and broken-connection discard
```

and executable tests prove:

```text
normal receipt materialization
→ governance transaction commits
→ commit-confirmed result is returned

ordinary receipt failure
→ governance transaction rolls back
→ live connection is left in a known clean state or closed

idle-owner termination
→ PostgreSQL rolls back the governance transaction
→ conflicting materializer can progress
→ broken connection is discarded
```

The implementation must preserve ADR 0019:

```text
accepted business transaction
≠
receipt governance transaction
```

Until production orchestration exists, the correct repository statement is:

```text
transaction-local owner cleanup mechanism characterized
→ implemented dedicated transaction owner

implemented dedicated transaction owner
≠
automatic receipt materialization or calibrated production policy
```
