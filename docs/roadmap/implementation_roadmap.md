# Implementation Roadmap

[← Back to Roadmaps Index](README.md)

## Purpose

This roadmap describes the intended implementation order of the project.

It is not merely a list of desired features.  
It is a sequencing guide for building the system without losing semantic clarity.

This version updates the roadmap to reflect the current Stage 3.5B direction:

- durable write-side schema now uses `order_events` and `idempotency_records`
- accepted event identity is represented as PostgreSQL `UUID`
- previous accepted event identity claims use `proof_prev_event_id UUID NULL`
- event format evolution is represented through `event_schema_version`
- runtime metadata is separated into `metadata_json`
- database append time is represented as `appended_at`
- Stage 3.5C PR0 hardens durable order-event vocabulary before read-side persistence begins
- Stage 3.5D is introduced as a persistence optimization / replay-efficiency stage after the durable read-side baseline
- Stage 3.5D snapshot work is clarified as a **Snapshot Trust Contract**, not only replay optimization
- Stage 3.5E is introduced as a durable history and permission-hardening stage before broader runtime semantic governance
- Stage 4 is not only an error taxonomy stage; it becomes a structured semantic outcome and runtime decision boundary
- Stage 4 explicitly includes retry reason classification and intent consistency as part of SemanticOutcome / runtime evidence design
- Stage 4 may introduce a minimal Order Domain Policy Contract v0 so SemanticOutcome can reference rule IDs and recovery strategies without turning the project into a full policy-authoring system
- Stage 5 becomes the dual-dimension governance demo: semantic correctness × operational freshness → action safety
- Stage 5+ may later evaluate isolated derived-state runtime / oblivious agent runtime as an agent-governance hardening direction

---

## Current Position

The project has completed an executable baseline across:

- transactional semantic core
- accepted-history persistence and replay in the current baseline
- request-level idempotency with replay / conflict distinction
- optimistic admission with stale-write rejection
- event-level Compass validation before persistence
- Stage 3 projection runtime in a deterministic in-memory form
- Stage 3.5A Decimal / exact-money hardening before durable persistence
- ADR 0008 event identity lifecycle decision before durable write-side persistence
- event identity boundary naming cleanup before durable storage expansion
- Stage 3.5B PR1 schema / local PostgreSQL / migration setup checkpoint
- Stage 3.5B PR2 PostgresEventStore baseline
- Stage 3.5B PR3 PostgresIdempotencyStore baseline
- Stage 3.5B PR4 transactional semantic write-side boundary
- Stage 3.5B PR5 PostgreSQL concurrency admission boundary
- Stage 3.5B PR6 validation placement strategy baseline
- Stage 3.5C PR0 durable order-event vocabulary hardening
- Stage 3.5C PR1 durable read-side schema baseline
- Stage 3.5C PR2 PostgresProjectionStore baseline
- Stage 3.5C PR3 PostgresCheckpointStore baseline
- Stage 3.5C PR4 Global-Position Projection Worker baseline
- Stage 3.5C PR5 Durable Replay / Rebuild Validation baseline

This means:

- Stage 1 is complete at a baseline level
- Stage 2 is complete at a baseline level
- Stage 3 exists as a minimal executable read-side runtime baseline
- Stage 3.5A is complete as the pre-persistence money / exact-value hardening step
- pre-Stage 3.5B event identity semantics are documented and reflected in boundary naming
- Stage 3.5B PR1 has established the durable write-side schema and local PostgreSQL setup baseline
- Stage 3.5B PR4 has established the first PostgreSQL-backed transactional semantic write-side flow
- Stage 3.5B PR5 has established PostgreSQL-backed two-phase concurrency admission
- Stage 3.5B PR6 has established validation placement strategy as a Stage 4 prelude
- Stage 3.5C PR0 has normalized durable `event_type` vocabulary, added `proof_prev_status` database constraint enforcement, and renamed the order stream-position unique constraint before durable read-side work begins
- Stage 3.5C PR1 has established `projection_states` and `projection_checkpoints` as the durable read-side schema baseline, including physical shape constraints and checkpoint cursor alignment
- Stage 3.5C PR2 has implemented `PostgresProjectionStore`, making `projection_states` usable through the Python storage boundary while preserving projection state as derived and rebuildable
- Stage 3.5C PR3 has implemented `PostgresCheckpointStore`, making `projection_checkpoints` usable through the Python storage boundary while preserving checkpoint state as operational progress metadata
- Stage 3.5C PR4 has introduced `order_events.global_position`, `PostgresProjectionEventSource`, and `PostgresProjectionWorker`, connecting accepted history, the canonical reducer, durable projection state, and durable checkpoint progress through one PostgreSQL-backed read-side transaction boundary
- Stage 3.5C PR5 has introduced durable replay / rebuild validation, comparing accepted-history replay with persisted projection state
- Stage 3.5C is complete at the durable read-side baseline level

The current major focus is:

- **Stage 3.5D — Snapshot Trust Contract / Replay Efficiency**

After the completed Stage 3.5C durable read-side baseline, the project can proceed toward:

- Stage 3.5D persistence optimization / replay efficiency
- Stage 3.5D Snapshot Trust Contract
- Stage 3.5E durable history and permission hardening
- Stage 4 runtime semantic validation, structured semantic outcomes, and runtime decision policy
- Stage 5 dual-dimension governance demo
- Stage 5+ isolated derived-state runtime / oblivious agent runtime evaluation

---

## Guiding Principle

The project should evolve from:

1. semantic truth
2. transactional execution
3. concurrency-safe admission
4. event truth validation
5. projection / runtime correctness
6. exact durable money semantics
7. candidate / accepted event identity boundary cleanup
8. durable write-side persistence semantics
9. durable read-side persistence semantics
10. persistence optimization / replay efficiency
11. snapshot trust qualification for fast-path replay
12. durable history immutability and permission hardening
13. runtime semantic outcomes
14. runtime decision policy
15. action safety gate
16. dual-dimension governance demo
17. later isolated derived-state runtime and adversarial hardening

This order is intentional.

The system should not attempt to solve chaos, analytics, broad governance, or distributed complexity before its semantic core, write-side safety boundaries, runtime semantics, and durable persistence boundaries are clear.

---

## Stage 1: Transactional Semantic Core

### Goal

Establish the write-side meaning of the system.

### Deliverable

A deterministic transactional baseline capable of:

- producing candidate events
- conditionally admitting accepted events
- persisting accepted history in the current baseline
- replaying aggregate state
- preventing duplicate semantic effects
- preventing stale writes through conditional admission

### Status

Implemented as the current write-side baseline.

---

## Stage 2: Event Truth Validation

### Goal

Integrate the first Compass layer into the transactional path.

### Deliverable

A write-side flow that can reject semantically inconsistent events before they enter accepted history, while preserving the distinction between:

- semantic validation through Compass
- conditional admission through the persistence / concurrency boundary
- idempotency replay / conflict classification

### Status

Implemented at a baseline level as the current Compass Layer 1 path.

---

## Stage 3: Projection Runtime Baseline

### Goal

Upgrade projection from replay helper into a real runtime subsystem.

### Deliverable

A read-side runtime capable of incremental state derivation and replay / rebuild through the same runtime path.

### Status

Implemented at a deterministic in-memory baseline level.

### Current Note

The current Stage 3 baseline establishes:

- reducer / worker separation
- projection-state and checkpoint-store separation
- replay-safe projection sequencing
- deterministic in-memory replay / rebuild behavior

It does not yet establish durable storage-backed runtime semantics.

---

## Stage 3.5A: Decimal Hardening Before Durable Persistence

### Goal

Ensure that money-like values are represented exactly before write-side or read-side durable persistence grows larger.

### Deliverable

An exact-money baseline that preserves semantic correctness before persistent storage is introduced more deeply.

### Status

Completed.

---

# Stage 3.5B: Durable Write-Side Baseline

## Goal

Move the current write-side baseline from in-memory persistence toward durable PostgreSQL-backed semantics.

## Why

After Stage 3.5A, the next meaningful step is durable write-side evolution.

Accepted-history durability, idempotency durability, transaction grouping, append-only event-store shape, exact money persistence, and candidate / accepted event identity must be clarified before the rest of the runtime grows larger.

## Stage 3.5B PR Breakdown

### PR1 — Physical Schema + Local PostgreSQL + Migration Skeleton

#### Status

Completed.

#### Scope

This PR establishes the durable write-side storage contract and local development environment.

It includes:

- write-side schema baseline architecture note
- Python-to-database schema translation boundary note
- Docker-based local PostgreSQL setup
- local development setup documentation
- initial write-side migration skeleton

#### Durable Tables

The first durable write-side tables are:

- `order_events`
- `idempotency_records`

#### `order_events` baseline

Core columns:

- `accepted_event_id UUID PRIMARY KEY`
- `event_schema_version INTEGER NOT NULL DEFAULT 1`
- `order_id TEXT NOT NULL`
- `sequence INTEGER NOT NULL`
- `event_type TEXT NOT NULL`
- `request_id TEXT NOT NULL`
- `amount NUMERIC(18, 2) NOT NULL`
- `occurred_at_ms BIGINT NOT NULL`
- `proof_prev_event_id UUID NULL`
- `proof_prev_version INTEGER NOT NULL`
- `proof_prev_status TEXT NOT NULL`
- `payload_json JSONB NOT NULL DEFAULT '{}'::jsonb`
- `proof_json JSONB NOT NULL DEFAULT '{}'::jsonb`
- `metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb`
- `appended_at TIMESTAMPTZ NOT NULL DEFAULT now()`

Core constraints:

- `UNIQUE (order_id, sequence)` using `uq_order_events_order_id_sequence`
- `event_type IN ('CREATED', 'PAID')`
- `proof_prev_status IN ('INIT', 'CREATED', 'PAID')`
- `amount >= 0`
- `sequence > 0`
- `event_schema_version > 0`
- `payload_json`, `proof_json`, and `metadata_json` must be JSON objects

#### `idempotency_records` baseline

Core columns:

- `request_id TEXT PRIMARY KEY`
- `order_id TEXT NOT NULL`
- `command_type TEXT NOT NULL`
- `amount NUMERIC(18, 2) NOT NULL`
- `fingerprint_version INTEGER NOT NULL DEFAULT 1`
- `semantic_fingerprint TEXT NOT NULL`
- `accepted_event_id UUID NOT NULL`
- `result_sequence INTEGER NOT NULL`
- `status TEXT NOT NULL DEFAULT 'SUCCEEDED'`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`

Core constraints:

- `accepted_event_id` references `order_events.accepted_event_id`
- `command_type IN ('create', 'pay')`
- `semantic_fingerprint` cannot be empty after trimming
- `fingerprint_version > 0`
- `result_sequence > 0`
- `amount >= 0`

#### Key Boundary Decisions

- `accepted_event_id` is UUID because it represents accepted history identity.
- `proof_prev_event_id` is also UUID because it represents a previous accepted event identity claim.
- `proof_prev_event_id` is not yet a foreign key because previous-event truth belongs to Compass / replay logic, not a partial relational constraint.
- `event_schema_version` protects durable event format evolution.
- Durable `event_type` values use uppercase enum-style accepted-event vocabulary: `CREATED`, `PAID`.
- `proof_prev_status` uses uppercase domain-state vocabulary: `INIT`, `CREATED`, `PAID`.
- `command_type` remains lowercase because it represents request/action identity for idempotency records, not accepted event identity.
- `metadata_json` is reserved for non-domain runtime metadata, including future validation timing, registry-stage timing, validator identity, validation mode, and runtime trace metadata.
- `appended_at` is database append time and remains distinct from `occurred_at_ms`.

#### Non-goals

This PR does not implement:

- `PostgresEventStore`
- `PostgresIdempotencyStore`
- transactional write-side unit of work
- registry-stage timing collection
- UUIDv7 generation
- append-only trigger enforcement
- production DB role hardening
- table partitioning
- idempotency conflict audit table

#### Related Postmortems

These postmortems explain why Stage 3.5B is not merely a database setup step:

- [From In-Memory Correctness to Durable Consistency](../postmortems/from_in_memory_correctness_to_durable_consistency.md)  
  Explains why persistence is not a backend swap and why durable systems must handle restart and partial failure explicitly.

- [From Git Local–Remote Drift to Database Immutability Boundaries](../postmortems/from_git_sync_to_db_immutability.md)  
  Explains why Python-side guarantees such as `frozen=True` and append-only history must be re-declared at the PostgreSQL boundary.

- [From Local PostgreSQL Setup to Defense-in-Depth Boundaries](../postmortems/from_local_postgres_to_defense_in_depth.md)  
  Explains why Docker Compose, `.env`, least privilege, SQL migrations, Compass validation, and transactions each protect different boundaries.

- [From Runtime Behavior to Durable Evidence](../postmortems/from_runtime_behavior_to_durable_evidence.md)  
  Explains why Python runtime behavior is not durable evidence unless selected facts are persisted into database records, metadata, logs, metrics, traces, or audit channels.

---

### PR2 — Python Store / Repository Layer: PostgresEventStore

#### Status

Completed.

#### Goal

Make accepted event history durable through `order_events`.

#### Main Work

- add PostgreSQL client dependency, likely `psycopg`
- add PostgreSQL connection helper
- add centralized event id generator under `src/core/common/`
- evaluate and align `OrderEvent.event_id` with UUID semantics
- implement `PostgresEventStore`
- support append / load / last event behavior
- preserve Decimal amount and UUID identity across write / read
- support `metadata_json` write / read
- keep `event_schema_version` defaulted to v1

#### UUID Direction

The schema already supports PostgreSQL `UUID`.

PR2 should centralize event identity generation:

```python
import uuid

def generate_event_id() -> uuid.UUID:
    return uuid.uuid4()
```

The purpose is not to force UUIDv7 immediately.

The purpose is to avoid scattering ID generation across domain logic.  
When Python runtime support or dependency policy is ready, this function can later switch to UUIDv7-compatible generation without changing the database schema.

#### Tests

PR2 should verify:

- append first event succeeds
- append second event succeeds
- load returns accepted events ordered by sequence
- last event returns latest accepted event
- duplicate `(order_id, sequence)` rejects
- stale expected version rejects
- loaded event preserves UUID identity
- loaded event preserves Decimal amount
- `metadata_json` can be written and read
- `event_schema_version` defaults to 1

#### Non-goals

PR2 does not implement:

- `PostgresIdempotencyStore`
- same-transaction event append + idempotency record write
- registry-stage timing collection
- UUIDv7 rollout
- append-only trigger enforcement

---

### PR3 — PostgresIdempotencyStore Baseline

#### Status

Completed.

#### Goal

Make request-level idempotency durable through `idempotency_records`.

#### Main Work

- implement `PostgresIdempotencyStore`
- support durable MISS / REPLAY / CONFLICT classification
- write successful request-to-accepted-event mappings
- preserve semantic fingerprint and fingerprint version
- ensure command type values align with Python enum values such as `create` and `pay`
- ensure replay returns a previously accepted event result rather than a new candidate

#### Tests

PR3 should verify:

- new request produces MISS
- same `request_id` + same semantic fingerprint produces REPLAY
- same `request_id` + different semantic fingerprint produces CONFLICT
- successful accepted-event result can be recorded
- idempotency record survives restart / new connection
- `accepted_event_id` must reference an existing accepted event
- conflict does not overwrite an existing idempotency record

#### Non-goals

PR3 does not implement:

- full transactional write-side boundary
- registry-stage timing
- conflict audit table
- retry attempt history
- observability framework

---

### PR4 — Transactional Semantic Write-Side Boundary

#### Status

Completed after PR4 merge.

#### Goal

Coordinate durable event append, durable idempotency recording, and Compass Layer 1 validation inside a PostgreSQL-backed transactional write-side flow.

#### Why

The durable write-side baseline is incomplete unless physical transaction safety and semantic gate preservation are both explicit.

PR4 protects against two different failure modes:

- partial durable writes, such as an event being persisted without its idempotency record
- semantic drift during persistence hardening, where the durable PostgreSQL path accidentally bypasses Compass Layer 1 validation

#### Main Work

- introduce `PostgresWriteSideUnitOfWork`
- coordinate `PostgresEventStore` and `PostgresIdempotencyStore` through one PostgreSQL transaction
- introduce `PostgresTransactionalWriteSide`
- check idempotency before command execution
- rehydrate aggregate state from durable accepted history
- build Compass Layer 1 `ValidationContext` from accepted history
- create candidate events through the aggregate
- run Compass Layer 1 validation before accepted history mutation
- append accepted events only after validation allows the candidate
- record idempotency results in the same transaction as accepted event append
- rollback on validation block, domain legality failure, or idempotency-record failure
- isolate destructive PostgreSQL integration tests through `TEST_DATABASE_URL`
- reorganize integration tests by execution boundary
- document transactional integration tests as executable architecture claims

#### Minimal Flow

```text
BEGIN

check idempotency

if REPLAY:
    rollback / no write
    return previous accepted result

if CONFLICT:
    rollback / no write
    return conflict result

if MISS:
    load durable accepted history
    rehydrate aggregate
    build validation context
    create candidate event
    run Compass Layer 1 validation

    if BLOCK:
        rollback / no write
        return validation-blocked result

    append event into order_events
    record idempotency result into idempotency_records

COMMIT
```

#### Boundary Clarified During PR4

PR4 clarified three important boundaries:

```text
transaction atomicity
≠ concurrency admission
```

```text
validation mode
≠ validation placement
```

```text
durable persistence hardening
must preserve Compass semantic gates
```

These boundaries are documented in:

- [ADR 0010 — Separate Transaction Atomicity from Concurrency Admission](../adr/0010_transaction_atomicity_vs_concurrency_admission.md)
- [ADR 0011 — Separate Validation Mode from Validation Placement Strategy](../adr/0011_validation_mode_vs_validation_placement.md)
- [Postmortem — From Durable Persistence to Semantic Gate Preservation](../postmortems/from_durable_persistence_to_semantic_gate_preservation.md)

#### Tests

PR4 verifies:

- successful `create_order` writes both `order_events` and `idempotency_records`
- successful `pay_order` writes the second accepted event and corresponding idempotency record
- replay same request returns the previous accepted result
- conflict same `request_id` with different semantic fingerprint creates no new rows
- validation `BLOCK` creates no `order_events` row
- validation `BLOCK` creates no `idempotency_records` row
- domain legality failures leave no partial durable writes
- if idempotency record persistence fails after event append, the event append is rolled back
- transactional tests run against `TEST_DATABASE_URL`, not the development database

#### Non-goals

PR4 does not implement:

- PostgreSQL-backed concurrency admission
- optimistic admission gate
- pessimistic admission gate
- durable read-side projection store
- durable checkpoint store
- Layer 2 validator
- structured `SemanticOutcome` / Error Model family
- validation result persistence table
- registry-stage timing implementation
- OpenTelemetry / Datadog / Monte Carlo integration
- production DB roles
- append-only trigger enforcement

---

### PR5 — PostgreSQL Concurrency Admission Boundary

#### Status

Completed after PR5 merge into the Stage 3.5B baseline.

#### Goal

Introduce explicit PostgreSQL-backed admission control for concurrent writers and integrate it into the durable transactional write-side flow.

#### Why

PR4 guarantees that related durable writes commit or roll back together.

However, transaction atomicity does not answer whether a writer should be admitted to occupy the next stream sequence when multiple workers compete for the same aggregate stream.

PR5 restores the admission-boundary idea from the earlier in-memory `ConcurrencyGate` / `OptimisticVersionGate` design into the durable PostgreSQL write-side.

During implementation, PR5 also clarifies that optimistic and pessimistic admission do not acquire protection at the same physical moment.

This leads to a two-phase admission model:

```text
prepare_stream(order_id)
→ append_if_admitted(candidate_event, expected_current_version)
```

#### Main Work

- introduce storage-level stale-write / concurrency errors
- map raw PostgreSQL constraint or version conflicts into stable application-level admission results
- extend admission vocabulary with:
  - `ADMITTED`
  - `STALE_WRITE`
  - `LOCK_TIMEOUT`
  - `INFRASTRUCTURE_ERROR`
- add `StreamAdmissionResult` for stream-preparation decisions
- keep `AdmissionResult` for append-time candidate-event admission
- implement `PostgresOptimisticAdmissionGate`
- implement `PostgresPessimisticAdmissionGate`
- move pessimistic advisory-lock acquisition into `prepare_stream(order_id)`
- reject `autocommit=True` for transaction-scoped pessimistic admission
- integrate two-phase admission into `PostgresTransactionalWriteSide`
- preserve idempotency-before-prepare ordering
- keep admission rejection distinct from idempotency conflict, validation block, and domain legality failure
- keep append-time expected-version admission as the final accepted-history continuity check

#### Expected Tests

PR5 should verify:

- one writer can append the next stream event
- a stale writer is rejected without mutating accepted history
- optimistic admission maps stale writes into stable results
- pessimistic admission can acquire a transaction-scoped stream lock during `prepare_stream(order_id)`
- pessimistic admission returns `LOCK_TIMEOUT` when the stream lock is unavailable
- pessimistic admission rejects `autocommit=True`
- replay / conflict paths do not acquire stream locks
- prepare-time rejection does not run validation or create durable rows
- append-time admission rejection does not record idempotency
- admission rejection does not pollute accepted history or idempotency memory
- the write side stores an admission gate factory, not a reusable gate singleton
- PR4 event append + idempotency atomicity tests still pass

#### Related Decisions and Notes

- [ADR 0010 — Separate Transaction Atomicity from Concurrency Admission](../adr/0010_transaction_atomicity_vs_concurrency_admission.md)
- [ADR 0011 — Separate Validation Mode from Validation Placement Strategy](../adr/0011_validation_mode_vs_validation_placement.md)
- [ADR 0012 — Two-Phase Concurrency Admission for PostgreSQL Write-Side](../adr/0012_two_phase_concurrency_admission.md)
- [Postmortem — Autocommit, Transaction Boundaries, and Partial-Write Risk](../postmortems/autocommit_boundary_and_partial_write_risk.md)

#### Non-goals

PR5 does not implement:

- Stage 4 `SemanticOutcome`
- runtime decision policy
- validation placement strategy
- full production locking framework
- connection pooling
- retry orchestration
- hot-stream routing policy
- durable admission audit table
- durable lock table
- cross-aggregate locking model
- operational alerting

---

### PR6 / Stage 4 Prelude — Validation Placement Strategy

#### Status

Completed after PR6 merge into the Stage 3.5B baseline.

#### Goal

Introduce a configurable validation placement strategy after PostgreSQL concurrency admission exists.

#### Why

PR4 establishes an in-transaction Compass validation baseline.

PR5 establishes two-phase PostgreSQL concurrency admission.

Only after PR5 can the project safely support a second orchestration mode:

```text
pre-transaction Compass validation + append-time admission
```

This strategy allows the system to compare latency and safety trade-offs between:

- in-transaction Compass validation
- pre-transaction Compass validation + append-time admission
- validation-off baseline for measurement

Without validation placement strategy, Stage 4 timing or evidence tables would only measure one fixed orchestration path. They would not be able to compare in-transaction validation against pre-transaction validation plus append-time concurrency admission.

#### Main Work

- define `ValidationPlacement`
- keep `ValidationMode` separate from `ValidationPlacement`
- preserve `IN_TRANSACTION` as the default validation placement
- support a minimal `PRE_TRANSACTION` validation + append-time admission path
- introduce `PostgresWriteSideConfig` / `ValidationPlacement` as the configuration boundary
- ensure stale pre-validated candidates cannot enter accepted history
- preserve `IN_TRANSACTION` as the default behavior
- keep `append_if_admitted(...)` as the final accepted-history mutation boundary
- clean up implicit read transactions before CPU-side `PRE_TRANSACTION` validation
- enable latency and safety comparison without duplicating storage logic

#### Candidate Future API

```python
PostgresWriteSideConfig(
    validation_mode=ValidationMode.STRICT,
    validation_placement=ValidationPlacement.IN_TRANSACTION,
    admission_strategy=AdmissionStrategy.OPTIMISTIC,
)
```

or:

```python
PostgresWriteSideConfig(
    validation_mode=ValidationMode.STRICT,
    validation_placement=ValidationPlacement.PRE_TRANSACTION,
    admission_strategy=AdmissionStrategy.OPTIMISTIC,
)
```

#### Related Notes

- [Validation Placement Strategy Boundary](../boundary_notes/validation_placement_strategy_boundary.md)
- [Pre-Transaction Read Cleanup Boundary](../postmortems/pre_transaction_read_cleanup_boundary.md)

The cleanup boundary records why `PRE_TRANSACTION` validation must not accidentally carry an implicit PostgreSQL read transaction into CPU-side validation.

#### Non-goals

PR6 / Stage 4 Prelude does not implement:

- full DAG node model
- risk scoring
- async audit pipeline
- Stage 4 `SemanticOutcome` tables
- validation attempt persistence tables
- registry-stage timing persistence tables
- Stage 5 governance metrics

---

## Stage 3.5B Completion Criteria

Stage 3.5B is complete at the durable write-side baseline level when:

- accepted events are persisted in PostgreSQL
- accepted history can be replayed from durable storage
- idempotency records survive restart / new connection
- replay / conflict semantics work against durable storage
- event append and idempotency record write are transactionally coordinated
- Compass Layer 1 remains on the durable write-side path before accepted history mutation
- validation `BLOCK` does not pollute accepted history or idempotency memory
- PostgreSQL-backed concurrency admission rejects stale writers explicitly
- validation placement can be configured between `IN_TRANSACTION` and minimal `PRE_TRANSACTION` baseline
- `PRE_TRANSACTION` validation remains guarded by append-time admission before accepted-history mutation
- preliminary read transactions are cleaned up before CPU-side pre-transaction validation
- exact money persistence is preserved
- UUID event identity is preserved
- candidate / accepted event identity semantics remain clear
- destructive PostgreSQL tests run against `TEST_DATABASE_URL`, not the development database

### Current Status

Completed at the durable write-side baseline level after PR6 merge into the Stage 3.5B baseline branch.

Stage 3.5B may still receive optional future hardening items, but Stage 3.5C PR0 has completed the immediate durable order-event vocabulary hardening pass before durable read-side persistence begins.

---

# Stage 3.5C PR0: Durable Order Event Vocabulary Hardening

## Goal

Finalize the durable `order_events` vocabulary and selected schema constraints before Stage 3.5C durable read-side persistence starts depending on stored event records.

## Why

Stage 3.5B established the durable write-side baseline. Before read-side projection and checkpoint persistence consume durable accepted events, the stored event vocabulary should be explicit and stable.

This PR0 is a schema-hardening pass, not the durable read-side baseline itself.

## Completed Scope

- normalize durable `event_type` values from lowercase to uppercase:
  - `created` → `CREATED`
  - `paid` → `PAID`
- align Python `OrderEventType` enum values with the database vocabulary
- update the `order_events.event_type` CHECK constraint
- add `proof_prev_status` CHECK constraint for `INIT`, `CREATED`, and `PAID`
- rename the order stream-position unique constraint to `uq_order_events_order_id_sequence`
- add PostgreSQL schema-constraint tests for rejected lowercase event types and invalid proof statuses

## Boundary Decision

Durable accepted-event vocabulary now uses uppercase enum-style values:

```text
CREATED
PAID
```

`CommandType` remains lowercase because it represents request/action identity for idempotency records, not accepted event identity.

## Non-goals

This PR0 does not implement:

- durable projection state
- durable checkpoint state
- `PostgresProjectionStore`
- `PostgresCheckpointStore`
- snapshot or replay optimization
- Compass Layer 2 validation

---

# Stage 3.5C: Durable Read-Side Baseline

## Goal

Move the current Stage 3 read-side baseline from in-memory stores toward durable persistence-backed semantics.

## Why

After the write-side durable baseline is clear, the read-side can safely evolve toward durable projection-state storage and durable checkpoint storage.

Read-side state is not the source of truth.

```text
event log = accepted history truth
projection state = derived runtime state
checkpoint = operational progress metadata
```

## Main Work

- durable projection-state schema
- durable checkpoint schema
- `PostgresProjectionStore`
- `PostgresCheckpointStore`
- persistence-backed projection worker tests
- replay / rebuild validation against durable read-side state


## Stage 3.5C PR Breakdown

### PR1 — Durable Read-Side Schema Baseline

#### Status

Completed.

#### Goal

Define the PostgreSQL schema boundary for durable read-side state before implementing PostgreSQL-backed read-side stores.

#### Why

Stage 3.5C should first clarify what durable derived state and checkpoint progress look like at the database boundary.

This PR should answer:

```text
Where does derived projection state live?
Where does worker progress live?
Which database constraints protect the minimum valid shape of read-side state?
```

It should not yet answer:

```text
How does the Python projection store persist state?
How does the PostgreSQL-backed worker scan accepted history?
How does Compass Layer 2 validate projection drift?
```

#### Completed Scope

- add `projection_states` table
- add `projection_checkpoints` table
- define schema constraints for projection status, money values, version, sequence, and identity fields
- define checkpoint `cursor_kind` / `cursor_value` alignment constraints
- add schema-constraint integration tests
- update CI to apply the durable read-side migration
- document the durable read-side schema boundary
- keep accepted history as the source of truth
- preserve the distinction between physical shape constraints and future Compass Layer 2 semantic-drift validation

#### Candidate Tables

`projection_states` may include:

```text
order_id
status
total_amount
paid_amount
version
last_sequence
updated_at
```

`projection_checkpoints` includes:

```text
worker_name
cursor_kind
cursor_value
updated_at
```

PR1 deliberately avoids `last_processed_sequence` because `order_events.sequence` is aggregate-local, not a global worker offset.

The final checkpoint scanning strategy is deferred until the PostgreSQL-backed projection worker is introduced. The schema supports `UNSPECIFIED`, `APPENDED_AT`, `EVENT_ID`, and `GLOBAL_POSITION` cursor kinds without committing PR1 to one worker strategy.

#### Boundary Decision

PR1 lets PostgreSQL protect physical shape and checkpoint cursor consistency.

It intentionally does not add cross-field domain constraints such as:

```text
CREATED implies paid_amount = 0
PAID implies paid_amount = total_amount
```

Those are semantic projection-drift concerns for the canonical reducer and future Compass Layer 2 validation, not PR1 database CHECK constraints.

#### Non-goals

PR1 does not implement:

- `PostgresProjectionStore`
- `PostgresCheckpointStore`
- PostgreSQL-backed projection worker
- durable replay / rebuild flow
- Compass Layer 2 validation
- Snapshot Trust Contract
- retry reason classification
- Stage 3.5E database role hardening

---

### PR2 — PostgresProjectionStore

#### Status

Completed.

#### Goal

Implement PostgreSQL-backed persistence for derived projection state.

#### Why

The current Stage 3 projection state exists only in the in-memory baseline.

PR2 moves projection state toward durable persistence while preserving the rule that projection state is derived and rebuildable, not the source of truth.

#### Completed Scope

- implement `PostgresProjectionStore`
- support loading projection state by `order_id`
- support inserting or updating projection state through `projection_states`
- preserve Decimal money values across write / read
- preserve status and version semantics
- persist `projection_states.last_sequence` from `OrderState.version`
- support `clear()` for tests and future rebuild paths
- add integration tests for save / load / upsert / clear behavior
- verify multiple orders remain independent
- verify stored projection state survives the PostgreSQL round trip
- verify caller-owned rollback restores connection usability after constraint failure

#### Boundary Decision

`PostgresProjectionStore` persists derived projection state only.

It does not:

- run the projection reducer
- decide event sequencing policy
- manage checkpoint progress
- validate semantic drift
- decide replay / rebuild orchestration
- commit or rollback transactions

Transaction ownership remains outside the store so that a later PostgreSQL-backed projection worker can commit projection-state updates and checkpoint progress atomically.

At the current projection model level:

```text
OrderState.version
= last aggregate-local accepted event sequence reflected by this projection state
```

Therefore PR2 persists:

```text
projection_states.last_sequence = state.version
```

This mapping should be revisited during Stage 3.5D if snapshot trust, reducer-version tracking, projection schema versioning, or projection-row versioning require separating source event sequence from projection version metadata.

#### Non-goals

PR2 does not implement:

- checkpoint persistence
- PostgreSQL-backed projection worker
- replay / rebuild orchestration
- Layer 2 validation
- snapshot optimization
- production database roles

---

### PR3 — PostgresCheckpointStore

#### Status

Completed.

#### Goal

Implement PostgreSQL-backed persistence for projection worker progress.

#### Why

A durable projection worker needs a durable checkpoint boundary so it can resume processing after restart.

Checkpoint state is operational progress metadata.

It is not business truth.

#### Main Work

- implement `PostgresCheckpointStore`
- support loading checkpoint by worker name
- support inserting or updating checkpoint progress
- support missing-checkpoint behavior
- add integration tests for checkpoint persistence
- verify checkpoint state survives a new database connection

#### Non-goals

PR3 does not implement:

- projection-state persistence
- full PostgreSQL-backed worker orchestration
- global ordering redesign
- Layer 2 validation
- snapshot optimization
- production database roles

---

### PR4 — Global-Position Projection Worker Baseline

#### Status

Completed.

#### Goal

Connect accepted history, the canonical reducer, durable projection state, and durable checkpoint progress into the first PostgreSQL-backed read-side worker path.

#### Why

Stage 3 already established the reducer / worker model in memory.

PR4 proves that the same conceptual read-side runtime can operate against durable storage without turning PostgreSQL into a second reconstruction algorithm.

This PR also makes the worker cursor strategy explicit before durable replay / rebuild validation and future Compass Layer 2 projection-drift validation are introduced.

#### Completed Scope

- add `order_events.global_position`
- add a migration for the global event-log position
- update CI migration setup
- document the global-position worker cursor boundary
- add `PostgresProjectionEventSource`
- add `ProjectionEventRecord` as the envelope between storage metadata and domain event meaning
- add shared order-event hydration through `order_event_hydration.py`
- load accepted events after a global position
- order accepted-history consumption by `global_position`
- add `PostgresProjectionWorker`
- apply the canonical projection reducer
- persist projection state through `PostgresProjectionStore`
- persist checkpoint progress through `PostgresCheckpointStore`
- store checkpoint progress as `cursor_kind = GLOBAL_POSITION`
- persist projection state and checkpoint progress in one PostgreSQL transaction
- add integration tests for global-position event loading
- add integration tests for worker processing
- add rollback tests for projection-state / checkpoint atomicity
- document the single-worker baseline and defer worker leasing / checkpoint locking

#### Cursor Boundary

PR4 preserves this distinction:

```text
aggregate-local sequence
≠
global event-log position
≠
worker checkpoint cursor
```

`order_events.sequence` remains aggregate-local and protects per-order continuity.

`order_events.global_position` provides a durable total order for accepted-history consumption.

`projection_checkpoints.cursor_value` records where a worker should resume.

#### Transaction Boundary

The PostgreSQL-backed projection worker owns the read-side transaction boundary.

It commits:

```text
projection state
+
checkpoint progress
```

together.

If either write fails, both writes roll back.

This is the read-side equivalent of the Stage 3.5B write-side atomicity boundary:

```text
accepted event append
+
idempotency record write
```

#### Design Boundary

`reducer.py` remains storage-agnostic.

`PostgresProjectionWorker` orchestrates storage access and reducer execution.

It does not duplicate reduction rules.

#### Non-goals

PR4 does not implement:

- durable replay / rebuild validation
- Compass Layer 2 validation
- Snapshot Trust Contract
- structured `SemanticOutcome`
- runtime decision policy
- out-of-order buffering
- DLQ
- watermark semantics
- distributed multi-worker coordination
- worker leasing / checkpoint row locking
- multi-region / sharded / multi-primary event-log cursor models
- production database role hardening
- append-only trigger enforcement

---

### PR5 — Durable Replay / Rebuild Validation

#### Goal

Prove that durable read-side state can be discarded and rebuilt deterministically from accepted history.

#### Why

Projection state is derived state.

If it becomes corrupted, stale, or inconsistent, the recovery path should be:

```text
accepted history
→ canonical reducer
→ rebuilt projection state
```

This PR proves that durable read-side persistence does not redefine the source of truth.

#### Main Work

- add durable replay / rebuild tests
- reset or rebuild projection state from `order_events`
- verify rebuilt state equals expected reducer output
- verify checkpoint behavior during rebuild
- verify projection state remains derived and replaceable
- document replay / rebuild assumptions

#### Non-goals

PR5 does not implement:

- Layer 2 drift validator
- `SemanticOutcome`
- runtime decision policy
- snapshot optimization
- production database role hardening

---

### PR6 — Stage 3.5C Documentation and Completion Alignment

#### Goal

Mark the durable read-side baseline as complete and align documentation, test guides, and roadmap state.

#### Why

Stage 3.5C changes the project from:

```text
durable write-side only
```

to:

```text
durable write-side + durable read-side baseline
```

The documentation should reflect that the project now has a minimal durable closed loop:

```text
accepted history
→ projection worker
→ durable projection state
→ durable checkpoint
→ replay / rebuild from accepted history
```

#### Main Work

- update project README
- update docs README
- update implementation roadmap
- update Compass runtime roadmap
- update test documentation
- update development setup if new migrations are required
- mark Stage 3.5C completion criteria as satisfied
- prepare transition notes for Stage 3.5D Snapshot Trust Contract / replay efficiency

#### Non-goals

PR6 does not implement:

- new runtime behavior
- snapshot schema
- Layer 2 validation
- `SemanticOutcome`
- Stage 3.5E database role hardening

## Candidate Tables

### `projection_states`

Possible fields:

- `order_id`
- `status`
- `total_amount`
- `paid_amount`
- `version`
- `last_sequence`
- `updated_at`

### `projection_checkpoints`

Current fields:

- `worker_name`
- `cursor_kind`
- `cursor_value`
- `updated_at`

For the Stage 3.5C PR4 worker baseline, checkpoint progress is stored as:

```text
cursor_kind = GLOBAL_POSITION
cursor_value = latest processed order_events.global_position
```

This keeps worker progress as operational metadata rather than business truth.

## Completion Criteria

- projection state survives restart
- checkpoint survives restart
- worker can consume accepted history through `GLOBAL_POSITION`
- worker can persist projection state and checkpoint progress atomically
- worker can resume from checkpoint
- projection can rebuild from accepted history
- read-side persistence does not redefine source of truth
- replay from durable `order_events` can rebuild the projection deterministically

## Boundary Statement

Stage 3.5C does not implement snapshot trust, aggregate snapshots, Layer 2 validation, retry reason classification, or agent-facing isolation.

Stage 3.5C only establishes the durable read-side target:

```text
event log
→ projection worker
→ durable projection state
→ durable checkpoint
```

This durable read-side target is required before later stages can validate, rebuild, optimize, or isolate derived state.


---


### PR5 — Durable Replay / Rebuild Validation Baseline

#### Status

Completed at the baseline level.

#### Goal

Validate persisted projection state against accepted-history replay.

#### Main Work

- add durable replay / rebuild validation boundary note
- introduce minimal replay validation statuses
- introduce replay validation result object
- implement durable replay validator for one `order_id`
- load accepted history through the existing accepted-history store path
- replay accepted events through the canonical reducer
- compare replay-derived `OrderState` with persisted projection state
- detect `MATCH`
- detect `MISSING_PROJECTION`
- detect `DRIFT`
- detect `NO_ACCEPTED_HISTORY`
- prove replay validation does not mutate accepted history
- prove replay validation does not advance checkpoint progress

#### Boundary

PR5 does not implement Compass Layer 2.

It provides the durable comparison substrate that future Layer 2 validation can consume:

```text
accepted-history replay
vs
persisted projection state
```

#### Non-goals

PR5 does not implement:

- structured `SemanticOutcome`
- runtime decision policy
- automatic repair policy
- Snapshot Trust Contract
- snapshot-assisted replay
- worker leasing
- checkpoint row locking
- distributed multi-worker coordination

---

# Stage 3.5D: Persistence Optimization & Replay Efficiency

## Subtitle

Snapshot Trust Contract and Replay Efficiency.

## Goal

Establish snapshot and replay-efficiency mechanisms after the durable write-side and read-side baselines are complete.

Stage 3.5D treats snapshots as derived state-compression artifacts, not as replacements for accepted event history.

It also defines when a snapshot is qualified to be used on the fast path.

## Why

Stage 3.5B establishes the durable write-side baseline.

Stage 3.5C establishes the durable read-side baseline.

Together, they answer:

```text
Can the system form a durable closed loop?
```

Stage 3.5D answers two different but related questions:

```text
As accepted history grows, how can replay, rehydrate, and rebuild costs be reduced without weakening source-of-truth semantics?
```

```text
When can a snapshot be trusted enough for the normal fast path without performing full replay every time?
```

Snapshots are therefore not part of the correctness baseline.

They are persistence, recovery, trust-qualification, and replay-efficiency hardening.

The accepted event log remains the source of truth.

```text
accepted history = source of truth
snapshot = derived state compression
projection state = derived runtime view
checkpoint = operational progress metadata
```

## Fast Path vs Authority Path

Stage 3.5D should distinguish two paths:

```text
fast path:
snapshot + tail replay + trust checks
```

```text
authority path:
full accepted-history replay for audit, rebuild, suspicious cases, reducer upgrades, or high-risk verification
```

The system should not full-replay on every normal request.

But the system should always preserve the ability to ignore an invalid snapshot and return to accepted history.

## Main Work

Stage 3.5D may include:

- aggregate snapshot schema
- aggregate snapshot store
- aggregate rehydration from latest valid snapshot plus tail events
- projection rebuild optimization
- snapshot metadata and lineage
- snapshot validity rules
- replay cost measurement
- tests proving that snapshot-assisted replay produces the same state as full accepted-history replay
- snapshot lineage check:
  - aggregate_id / order_id
  - snapshot_version
  - source_event_id
  - source_event_sequence
- tail continuity check:
  - events after snapshot_version must be continuous up to the latest accepted version
- snapshot schema and reducer version tracking:
  - snapshot_schema_version
  - reducer_version
  - invalidation behavior when a reducer version is no longer trusted
- payload integrity baseline:
  - payload_hash or checksum
  - invalid snapshot must be ignored or rejected
- snapshot trust-level concept:
  - invalid / untrusted
  - fast-path eligible
  - high-confidence
  - recently audited
- fallback behavior:
  - if snapshot trust checks fail, ignore snapshot and fall back to full replay
- evidence hooks for future Stage 4 SemanticOutcome:
  - why snapshot was rejected
  - which trust check failed
  - whether full replay was required

## Completion Criteria

Stage 3.5D is complete at the baseline level when:

- aggregate rehydration can use a valid snapshot plus tail events
- full replay and snapshot-assisted replay produce equivalent aggregate state
- invalid snapshots are rejected or ignored safely
- snapshot lineage points back to accepted history
- snapshot trust checks can reject invalid metadata, unsupported schema, broken tail continuity, or payload hash mismatch
- snapshot-assisted rehydration falls back to full replay when trust checks fail
- snapshot trust failures are represented in a way that Stage 4 can later convert into `SemanticOutcome`
- reducer_version and snapshot_schema_version are recorded or explicitly deferred
- replay-cost metrics can show how many events were skipped or replayed
- Stage 4 Layer 2 work can rely on a clearer persistence and replay-efficiency substrate

## Non-goals

Stage 3.5D does not implement:

- Compass Layer 2 full validation
- structured `SemanticOutcome`
- runtime decision policy
- action safety gate
- dual-dimension governance
- complex policy engine
- agent blocking semantics
- HMAC / digital signatures
- cryptographic hash chains
- isolated read-side DB
- agent sandbox
- sealed milestone snapshots
- Stage 4 SemanticOutcome persistence

Those belong to Stage 4, Stage 5, or later governance hardening.

## Boundary Statement

Stage 3.5D improves replay and persistence efficiency.

It qualifies snapshots for the fast path, but it does not change the source of truth.

```text
Snapshots compress accepted history.
Snapshots do not replace accepted history.
A snapshot may be used for speed only if it remains traceable, checkable, discardable, and rebuildable.
```

---


# Stage 3.5E: Durable History and Permission Hardening

## Goal

Harden the durable storage authority boundary after the durable write-side, durable read-side, and replay-efficiency baselines are clear.

Stage 3.5E focuses on making accepted history harder to rewrite accidentally or improperly at the database boundary.

## Why

Stage 3.5B establishes PostgreSQL-backed accepted history.

Stage 3.5C establishes PostgreSQL-backed durable read-side state.

Stage 3.5D improves replay, rehydrate, and rebuild efficiency without replacing accepted history.

After these baselines exist, the project can define database-level authority more accurately:

```text
order_events = accepted history / source of truth
idempotency_records = successful request-result memory
projection_states = mutable derived runtime view
projection_checkpoints = mutable worker progress metadata
```

This stage exists because these tables do not have the same mutability requirements.

`order_events` should move toward append-only accepted history.

`projection_states` and `projection_checkpoints` must remain mutable enough to support upsert, resume, reset, and rebuild.

If Stage 3.5D introduces aggregate snapshot tables, Stage 3.5E may also evaluate whether snapshot rows should follow append-only derived-artifact discipline. This is different from making snapshots the source of truth. It only protects derived artifact integrity.

## Main Work

Stage 3.5E may include:

- database role boundary documentation
- migration owner vs runtime role separation
- write-side runtime permission baseline
- projection worker permission baseline
- read-only observer permission baseline
- revoking runtime `UPDATE` / `DELETE` authority from `order_events`
- optional trigger-based rejection of `UPDATE` / `DELETE` on `order_events`
- tests proving runtime roles cannot rewrite accepted history
- documentation explaining why read-side tables remain mutable while accepted history is hardened
- optional snapshot table permission review if snapshot tables exist:
  - restrict casual UPDATE / DELETE on snapshot rows
  - preserve insert-only snapshot history if chosen
  - document why snapshot append-only protects derived artifact integrity, not source-of-truth authority

## Candidate Role Model

A minimal role model may distinguish:

```text
migration_owner
write_side_runtime
projection_worker
read_only_observer
```

Possible baseline permissions:

| Role | `order_events` | `idempotency_records` | `projection_states` | `projection_checkpoints` |
|---|---|---|---|---|
| `migration_owner` | schema owner | schema owner | schema owner | schema owner |
| `write_side_runtime` | SELECT / INSERT | SELECT / INSERT | no access or SELECT only | no access |
| `projection_worker` | SELECT | no access or SELECT | SELECT / INSERT / UPDATE | SELECT / INSERT / UPDATE |
| `read_only_observer` | SELECT | SELECT | SELECT | SELECT |

The exact grants should follow the final Stage 3.5C / 3.5D runtime shape.

## Completion Criteria

Stage 3.5E is complete at the baseline level when:

- accepted history is protected by database-level permission boundaries
- runtime roles cannot casually update or delete `order_events`
- projection worker permissions are separated from write-side event admission authority
- read-only observer access is separated from mutation authority
- mutable read-side tables remain able to support projection upsert, checkpoint updates, reset, and rebuild
- tests verify the core permission / append-only assumptions in local PostgreSQL
- documentation clearly states that append-only hardening protects accepted history, not derived read-side views

## Non-goals

Stage 3.5E does not implement:

- cloud IAM
- production secret-manager integration
- full deployment security architecture
- multi-tenant access control
- complex audit policy framework
- Compass Layer 2 validation
- structured `SemanticOutcome`
- runtime decision policy
- action safety gate
- cryptographic snapshot sealing
- HMAC signatures
- hash chains
- agent runtime isolation

Those belong to later production hardening or Stage 4 / Stage 5 runtime governance work.

## Boundary Statement

Stage 3.5E hardens storage authority.

It does not change the source of truth.

```text
accepted history remains the source of truth
permission hardening limits who can mutate storage
append-only enforcement reduces accidental or improper history rewrites
read-side state remains derived and rebuildable
```

---

# Stage 4: Runtime Semantic Validation and Runtime Decision Boundary

Stage 4 is not only an error classification stage.

It is the transition from:

```text
semantic failure detection
```

to:

```text
structured semantic outcome
→ runtime decision policy
→ action safety boundary
```

The core idea is:

> Error semantics are not only for observation.  
> They should give the runtime authority to continue, retry, rebuild, block, quarantine, stop, or escalate.

## Reasoning Bridge

Stage 4 follows from the limitation that raw exception strings, boolean results, and ad hoc rejection reasons are not enough for runtime governance.

For the reasoning behind this transition, see:

- [From Exception Strings to Governable Outcomes](../postmortems/from_exception_strings_to_governable_outcomes.md)

That postmortem explains why the project must evolve from:

```text
raise ValueError(...)
→ structured semantic outcome
→ runtime decision policy
→ runtime decision
→ action safety gate
→ layered trust / governance
```

The purpose is not to claim that Stage 4 is already implemented.

---

## Stage 4A — Layer 2 Minimal Validator

### Goal

Add the first read-side / state-level Compass validator.

Layer 1 protects:

```text
candidate event → accepted history
```

Layer 2 protects:

```text
accepted history → derived runtime state
```

### Detects

- projection drift
- replay vs persisted projection mismatch
- reducer mismatch
- checkpoint / state mismatch
- snapshot metadata invalidity
- snapshot hash mismatch
- unsupported snapshot schema
- untrusted snapshot reducer version
- snapshot tail discontinuity
- snapshot replay mismatch

### Minimal Flow

```text
accepted event history
        ↓
replay using canonical reducer
        ↓
expected_state
        ↓ compare
persisted_projection_state
        ↓
Layer 2 validation result
```

### Completion Criteria

- deterministically create at least 1–2 projection drift cases
- replay accepted history into expected state
- compare expected state vs persisted projection state
- emit a clear validation result

### Non-goal

Stage 4A should not yet decide what the runtime should do.

It only answers:

> Is derived state semantically correct?

---

## Stage 4B — Structured Semantic Outcome / Error Model v1

### Goal

Convert validation results from bool / exception / string forms into machine-readable semantic outcomes.

### Preferred Name

Use `SemanticOutcome` rather than only `ErrorModel`.

Reason:

Some outcomes are not exceptions.  
They may represent semantic drift, trust issues, violations, or action-safety risks.

### Minimal Structure

```python
@dataclass(frozen=True)
class SemanticOutcome:
    outcome_id: str
    ok: bool
    layer: str
    error_code: str | None
    error_type: str | None
    severity: str
    reversibility: str
    risk_level: str
    context: dict
    evidence: dict
    message: str
```

### Retry Reason Classification and Intent Consistency

Stage 4B should explicitly classify retry-like situations.

Retry is not a single category.

A retry-like situation may represent:

- idempotent replay of the same request identity
- idempotency conflict where the same request identity carries different command meaning
- stale-write retry caused by concurrency admission
- transient infrastructure retry
- rebuild-oriented retry caused by projection / snapshot drift
- future agent intent drift where the agent claims to retry the same task but changes the intended meaning

This classification should belong to `SemanticOutcome` / request-attempt evidence design.

It should not be added to `idempotency_records`.

Candidate context fields:

```text
retry_observed
retry_class
retry_cause
retry_safety
intent_consistency
idempotency_verdict
admission_verdict
validation_verdict
stored_fingerprint
incoming_fingerprint
expected_version
actual_version
```

Candidate values:

```text
retry_class:
- IDEMPOTENT_REPLAY
- CONCURRENCY_RETRY
- INFRASTRUCTURE_RETRY
- SEMANTIC_CONFLICT
- SEMANTIC_DRIFT
- REBUILD_REQUIRED
- UNKNOWN

retry_safety:
- SAFE_TO_REPLAY
- SAFE_TO_RETRY_AFTER_RELOAD
- RETRY_WITH_BACKOFF
- REBUILD_REQUIRED
- NOT_RETRYABLE
- BLOCK_AND_ESCALATE
- UNKNOWN

intent_consistency:
- SAME_INTENT
- SAME_IDENTITY_DIFFERENT_MEANING
- NOT_AN_IDEMPOTENCY_REPLAY
- AGENT_INTENT_DRIFT
- NOT_APPLICABLE
- UNKNOWN
```

### Why `reversibility` Matters

Policy must know whether the failure is:

- reversible
- rebuildable
- recoverable
- irreversible boundary risk

Examples:

- projection drift → reversible / rebuildable
- invalid transition before event append → irreversible boundary risk
- stale checkpoint → operational risk
- reducer mismatch → high severity semantic risk

### Minimal Error Types

- `SEMANTIC_PROJECTION_DRIFT`
- `CHECKPOINT_STATE_MISMATCH`
- `REPLAY_REDUCER_MISMATCH`
- `DOMAIN_TRANSITION_VIOLATION`
- `IRREVERSIBLE_BOUNDARY_RISK`
- `OPERATIONAL_STALENESS`
- `SNAPSHOT_METADATA_INVALID`
- `SNAPSHOT_HASH_MISMATCH`
- `SNAPSHOT_SCHEMA_UNSUPPORTED`
- `SNAPSHOT_REDUCER_VERSION_UNTRUSTED`
- `SNAPSHOT_TAIL_DISCONTINUITY`
- `SNAPSHOT_REPLAY_MISMATCH`
- `IDEMPOTENCY_CONFLICT`
- `STALE_WRITE`
- `AGENT_INTENT_DRIFT`

### Completion Criteria

- projection drift emits `SemanticOutcome`
- outcome contains context and evidence
- tests assert structured fields
- tests do not depend only on exception message strings

### Boundary

Stage 4B classifies what happened.

It does not decide what the runtime should do.

---


## Stage 4B.5 — Order Domain Policy Contract v0

### Goal

Add a small domain-specific policy contract for the current order/payment model so that `SemanticOutcome` can reference stable rule IDs and recovery strategies.

This stage should be treated as an optional Stage 4 extension between structured outcomes and runtime decisions.

It should not become a general-purpose policy framework.

### Why

Stage 4B gives the system structured semantic outcomes.

However, an outcome that only says:

```text
what failed
why it failed
```

is still not enough for governed agentic retry.

A retrying agent or workflow also needs to know:

```text
which rule was violated
whether retry is allowed
which recovery path is semantically valid
whether replay is allowed
whether the action must be blocked or escalated
```

Without a rule / recovery source, retry can degrade into blind trial-and-error against Compass.

The purpose of Stage 4B.5 is to provide a minimal comparison source for policy-guided recovery.

### Candidate Artifact

Introduce a narrow contract file such as:

```text
contracts/order_domain_policy_contract_v1.yaml
```

The contract should be derived from the existing Order Domain v1 rules and should cover only the current minimal commerce model.

Candidate scope:

- allowed transitions: `INIT → CREATED`, `CREATED → PAID`
- forbidden transitions: `INIT → PAID`, `PAID → PAID` for new requests
- positive amount rules
- full-payment semantics for v1
- idempotent replay with same request identity and same semantic fingerprint
- idempotency conflict for same request identity with different semantic fingerprint
- stale-write recovery by reloading accepted history and rebuilding the candidate once
- projection drift recovery by rebuild / quarantine decision

### Candidate YAML Shape

```yaml
contract_id: order_domain_v1
domain: order
version: 1

rules:
  - id: order.transition.init_to_created
    type: transition
    from: INIT
    to: CREATED
    allowed: true

  - id: order.transition.created_to_paid
    type: transition
    from: CREATED
    to: PAID
    allowed: true

  - id: order.transition.init_to_paid
    type: transition
    from: INIT
    to: PAID
    allowed: false
    violation: DOMAIN_TRANSITION_VIOLATION
    recovery: BLOCK

  - id: order.transition.paid_to_paid_new_request
    type: transition
    from: PAID
    to: PAID
    allowed: false
    violation: DUPLICATE_PAYMENT_ATTEMPT
    recovery: BLOCK

  - id: order.request.same_id_same_fingerprint
    type: idempotency
    outcome: IDEMPOTENT_REPLAY
    recovery: ALLOW_REPLAY

  - id: order.request.same_id_different_fingerprint
    type: idempotency
    violation: IDEMPOTENCY_CONFLICT
    recovery: BLOCK

  - id: order.admission.requires_fresh_version
    type: admission
    violation: STALE_WRITE
    recovery: REFRESH_ACCEPTED_HISTORY_AND_REBUILD_ONCE

recovery_strategies:
  BLOCK:
    retryable: false
    human_required: false

  REFRESH_ACCEPTED_HISTORY_AND_REBUILD_ONCE:
    retryable: true
    max_attempts: 1
    required_action: reload_accepted_history

  ALLOW_REPLAY:
    retryable: false
    required_action: return_prior_accepted_result

  BLOCK_AND_ESCALATE:
    retryable: false
    human_required: true
```

### SemanticOutcome Extension

Stage 4B.5 may add a small policy reference type:

```python
@dataclass(frozen=True)
class PolicyRuleRef:
    contract_id: str
    rule_id: str
    version: int
```

`SemanticOutcome` may then include optional fields such as:

```python
policy_ref: PolicyRuleRef | None
recovery_hint: str | None
```

The important point is that `SemanticOutcome` remains descriptive.

It may identify the violated or relevant rule, but it should not directly execute the recovery decision.

### Relationship to Stage 4C

Stage 4C can consume:

```text
SemanticOutcome.error_type
SemanticOutcome.policy_ref
SemanticOutcome.recovery_hint
```

and produce:

```text
RuntimeDecision
```

This keeps the flow explicit:

```text
Domain Policy Contract
→ SemanticOutcome
→ RuntimeDecisionPolicy
→ RuntimeDecision
→ ActionSafetyGate
```

### Completion Criteria

Stage 4B.5 is minimally complete when:

- `contracts/order_domain_policy_contract_v1.yaml` exists
- it contains rule IDs for the current v1 order/payment model
- it contains recovery strategies for block, replay, reload/rebuild-once, and escalate
- `SemanticOutcome` can optionally reference `policy_ref`
- tests prove at least a few outcomes are linked to rule IDs
- runtime decision tests can consume recovery hints without hardcoding every rule directly in the decision policy

### Non-goals

Stage 4B.5 does not implement:

- a general policy authoring platform
- compiled execution plans
- release packs
- policy promotion workflow
- policy diff tooling
- cross-domain governance
- agent workflow orchestration

---

## Stage 4C — Runtime Decision Policy v1

### Goal

Convert `SemanticOutcome` into `RuntimeDecision`.

This is the detect → classify → decide step.

If Stage 4B.5 is implemented, this policy may also consume `policy_ref` and `recovery_hint` from `SemanticOutcome` so that decisions are guided by the order-domain contract rather than only by hardcoded error-code mapping.

### Minimal Structure

```python
class RuntimeAction(Enum):
    ALLOW = "allow"
    BLOCK = "block"
    REBUILD = "rebuild"
    ESCALATE = "escalate"
    QUARANTINE = "quarantine"
```

```python
@dataclass(frozen=True)
class RuntimeDecision:
    action: RuntimeAction
    allowed: bool
    reason: str
    outcome_id: str
    requires_human_review: bool = False
```

```python
class RuntimeDecisionPolicy:
    def decide(self, outcome: SemanticOutcome) -> RuntimeDecision:
        ...
```

### Minimal Policy Rules

- `ok=True` → `ALLOW`
- `SEMANTIC_PROJECTION_DRIFT` + `severity=ERROR` → `REBUILD` or `QUARANTINE`
- `CHECKPOINT_STATE_MISMATCH` → `REBUILD` or `ESCALATE`
- `REPLAY_REDUCER_MISMATCH` → `BLOCK` or `ESCALATE`
- `DOMAIN_TRANSITION_VIOLATION` → `BLOCK`
- `IRREVERSIBLE_BOUNDARY_RISK` → `BLOCK`

Retry-related mappings may include:

```text
IDEMPOTENT_REPLAY
→ ALLOW_REPLAY

IDEMPOTENCY_CONFLICT / SEMANTIC_CONFLICT
→ BLOCK

CONCURRENCY_RETRY
→ RETRY_AFTER_RELOAD or BLOCK

INFRASTRUCTURE_RETRY
→ RETRY_WITH_BACKOFF or ESCALATE

REBUILD_REQUIRED
→ REBUILD or QUARANTINE

AGENT_INTENT_DRIFT
→ BLOCK_AND_ESCALATE
```

`SemanticOutcome` describes why the retry-like situation occurred.

`RuntimeDecisionPolicy` decides whether the system should replay, retry, reload, rebuild, block, quarantine, or escalate.

### Completion Criteria

- policy converts projection drift outcome into `REBUILD` / `QUARANTINE` / `ESCALATE`
- policy converts irreversible semantic violation into `BLOCK`
- tests assert `decision.action`
- tests assert `allowed=True / False`
- irreversible action does not proceed when decision is `BLOCK`

---

## Stage 4D — Layer 1 / Layer 2 Outcome + Decision Alignment

### Goal

Align write-side Layer 1 and read-side Layer 2 around the same flow:

```text
SemanticOutcome
        ↓
RuntimeDecisionPolicy
        ↓
RuntimeDecision
```

### Why This Comes After Stage 4C

Layer 1 already works.

The safer order is:

1. build Layer 2 validation
2. define structured outcomes
3. define decision policy
4. backport / align Layer 1 with the same outcome + decision family

### Target Flow

Layer 1:

```text
candidate event violates transition truth
        ↓
SemanticOutcome(
  error_type=DOMAIN_TRANSITION_VIOLATION,
  layer=LAYER_1_WRITE_SIDE,
  reversibility=IRREVERSIBLE_BOUNDARY_RISK
)
        ↓
RuntimeDecision(BLOCK)
        ↓
event does not enter EventStore
```

Layer 2:

```text
persisted projection state differs from replay expected state
        ↓
SemanticOutcome(
  error_type=SEMANTIC_PROJECTION_DRIFT,
  layer=LAYER_2_READ_SIDE,
  reversibility=REVERSIBLE
)
        ↓
RuntimeDecision(REBUILD or QUARANTINE)
```

### Completion Criteria

- Layer 1 invalid transition emits `SemanticOutcome`
- Layer 1 invalid transition maps to `RuntimeDecision(BLOCK)`
- Layer 2 drift maps to `RuntimeDecision(REBUILD / QUARANTINE / ESCALATE)`
- both layers can be described as Compass semantic runtime control

---

## Stage 4E — Domain Action Safety Gate

### Goal

Add the first domain-level safety gate before dependent actions.

Do not start with an agent protocol.  
Do not start with a universal executor.

Start with the project domain and define a minimal action-safety boundary.

### Candidate Domain Actions

These can be simulations rather than real external calls:

- `EMIT_DOWNSTREAM_SIGNAL`
- `GENERATE_SETTLEMENT_REPORT`
- `MARK_PROJECTION_TRUSTED`
- `ADVANCE_EXTERNAL_EXPORT`

### Minimal Flow

```text
requested action
        ↓
semantic state check
        ↓
SemanticOutcome
        ↓
RuntimeDecisionPolicy
        ↓
RuntimeDecision
        ↓
ActionSafetyGate
        ↓
execute or block
```

### Completion Criteria

- unsafe semantic outcome blocks dependent action
- projection drift can block or quarantine downstream action
- clean semantic state allows action
- tests prove blocked action is not executed

---

# Stage 5: Dual-Dimension Governance Demo

## Goal

Create a reviewer-facing demo that evaluates system trust using two dimensions:

```text
semantic correctness × operational freshness
```

The purpose of this stage is not only to observe whether the system is correct after the fact.

The purpose is to decide whether a dependent action is safe before it executes.

Snapshot / projection trust should contribute to the semantic correctness signal. A state may be operationally fresh but semantically untrusted if projection differs from accepted-history replay, snapshot trust checks fail, reducer version is untrusted, or checkpoint and projection state disagree.

This is especially important for irreversible or high-risk actions, where post-hoc monitoring is too late.

The final question is:

> Is this state true enough, fresh enough, and safe enough to act on?

## Core Matrix

|  | Operational Fresh | Operational Stale |
|---|---|---|
| Semantic Correct | Safe to act | Semantically correct but stale |
| Semantic Incorrect | Operationally healthy but semantically unsafe | Unsafe / stop / escalate |

## Four Required Cases

### Case 1 — Semantic Correct + Operational Fresh

Signals:

- accepted history replay equals persisted projection state
- checkpoint recent
- worker healthy

Decision:

- `SAFE_TO_ACT`

### Case 2 — Semantic Correct + Operational Stale

Signals:

- accepted history replay equals persisted projection state
- checkpoint too old
- worker heartbeat stale

Decision:

- `STALE_BUT_SEMANTICALLY_VALID`
- `REFRESH_BEFORE_ACTION`
- or `ESCALATE`

### Case 3 — Semantic Incorrect + Operational Fresh

Signals:

- worker recently ran
- checkpoint fresh
- projection state differs from replay expected state

Decision:

- `BLOCK_ACTION`
- `REBUILD_PROJECTION`

This is a key project insight:

> Freshness does not imply correctness.

### Case 4 — Semantic Incorrect + Operational Stale

Signals:

- projection drift exists
- checkpoint stale
- worker heartbeat stale

Decision:

- `STOP`
- `QUARANTINE`
- `ESCALATE`

## Minimal Structures

```python
@dataclass(frozen=True)
class SemanticSignal:
    correct: bool
    outcome: SemanticOutcome | None
```

```python
@dataclass(frozen=True)
class OperationalSignal:
    fresh: bool
    checkpoint_age_ms: int
    worker_lag: int
    reason: str
```

```python
@dataclass(frozen=True)
class ActionSafetyVerdict:
    semantic_correct: bool
    operational_fresh: bool
    action: str
    safe_to_act: bool
    reason: str
```

```python
class DualDimensionTrustEvaluator:
    def evaluate(
        self,
        semantic_signal: SemanticSignal,
        operational_signal: OperationalSignal,
    ) -> ActionSafetyVerdict:
        ...
```

## Demo Story

The final demo should show:

1. Layer 1 blocks invalid event truth before accepted history.
2. Layer 2 detects projection drift from accepted history replay.
3. `SemanticOutcome` explains the failure with evidence.
4. `RuntimeDecisionPolicy` converts semantic outcome into `BLOCK` / `REBUILD` / `ESCALATE`.
5. `DualDimensionTrustEvaluator` combines semantic correctness and operational freshness.
6. `ActionSafetyGate` blocks unsafe dependent action when semantic correctness or operational freshness is insufficient.

## Completion Criteria

- README can explain the demo in 3–5 minutes
- demo script can produce all 4 matrix cases
- tests cover the 4 matrix cases
- semantic incorrect + operational fresh case is clearly shown
- semantic correct + operational stale case is clearly shown
- action-safety verdict is explicit
- docs clearly separate implemented vs future work

---

# Later Work: Governance and Chaos Hardening

After Stage 5, later work may include:

- DLQ
- out-of-order buffering
- watermark semantics
- multi-worker coordination
- stronger transaction boundaries
- real observability integration
- richer policy engine
- chaos testing
- agent tool interface
- generalized semantic governance protocol

These are intentionally deferred until the core semantic and runtime-decision model is stable.

---

## Summary View

```text
Stage 1:
Transactional Semantic Core ✅

Stage 2:
Compass Layer 1 Write-side Validation ✅

Stage 3:
Projection Runtime Baseline ✅

Stage 3.5A:
Decimal / Money Hardening ✅

Stage 3.5B:
Durable Write-side Baseline
  PR1 Schema + Docker + Migration ✅
  PR2 PostgresEventStore ✅
  PR3 PostgresIdempotencyStore ✅
  PR4 Transactional Semantic Write-side Boundary ✅
  PR5 PostgreSQL Concurrency Admission Boundary ✅
  PR6 Validation Placement Strategy ✅

Stage 3.5C PR0:
Durable Order Event Vocabulary Hardening ✅

Stage 3.5C:
Durable Read-side Baseline
  PR1 Durable Read-Side Schema Baseline
  PR2 PostgresProjectionStore
  PR3 PostgresCheckpointStore
  PR4 PostgreSQL-Backed Projection Worker
  PR5 Durable Replay / Rebuild Validation
  PR6 Documentation and Completion Alignment

Stage 3.5D:
Persistence Optimization & Replay Efficiency

Stage 3.5E:
Durable History and Permission Hardening

Stage 4:
Runtime Semantic Validation and Runtime Decision Boundary
  4A Layer 2 Minimal Validator
  4B Structured Semantic Outcome / Error Model v1
  4B.5 Order Domain Policy Contract v0
  4C Runtime Decision Policy v1
  4D Layer 1 / Layer 2 Outcome + Decision Alignment
  4E Domain Action Safety Gate

Stage 5:
Dual-Dimension Governance Demo
  semantic correctness × operational freshness
  action safety verdict
```

---

## Final Summary

The intended evolution is:

```text
durable truth
→ derived truth validation
→ replay-efficiency hardening
→ durable history hardening
→ structured semantic outcome
→ runtime decision policy
→ action safety gate
→ dual-dimension governance demo
```

The project is not only trying to know that something failed.

It is trying to make semantic failure understandable enough that the runtime can decide whether to continue, rebuild, block, quarantine, stop, or escalate.


---

# Stage 5+ / Later Governance Hardening

## Isolated Derived-State Runtime / Oblivious Agent Runtime

Future versions of Compass may isolate untrusted agents from the sovereign event store.

This is not a Stage 3.5C, Stage 3.5D, or Stage 4 requirement.

The future model is:

```text
Sovereign Event Store
→ Projection Pipeline
→ Isolated Derived-State DB / controlled read boundary
→ Agent observes derived state
→ Agent proposes candidate action
→ Compass validates against accepted history
→ accepted event is appended only by the system kernel
```

Core principles:

- agents should not directly read or write accepted history
- agents should observe only derived state through a controlled read boundary
- agents should submit candidate actions rather than mutate truth directly
- Compass remains the admission authority
- accepted event history remains the source of truth
- the derived-state DB can be discarded and rebuilt from accepted history

This should be revisited only after the Stage 5 dual-dimension governance demo is stable, ActionSafetyGate exists, and an agent-facing tool interface becomes concrete.
