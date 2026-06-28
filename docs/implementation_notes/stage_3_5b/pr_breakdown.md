# Stage 3.5B PR Breakdown

[← Back to Stage 3.5B Notes](README.md)

## Purpose

This note preserves the completed implementation sequence for:

```text
Stage 3.5B — Durable Write-Side Baseline
```

The goal of Stage 3.5B was to move the write-side baseline from in-memory persistence toward durable PostgreSQL-backed semantics while preserving Compass Layer 1 before accepted-history mutation.

This note is intentionally more detailed than the project roadmap. It preserves PR-level implementation history, boundary decisions, related postmortems, tests, and non-goals that are too detailed for the roadmap.

---

## Stage Principle

```text
accepted history = authority
candidate event ≠ accepted fact
transaction atomicity ≠ concurrency admission
validation mode ≠ validation placement
```

---

## Completed PR Sequence

```text
PR1 — Physical Schema + Local PostgreSQL + Migration Skeleton
PR2 — PostgresEventStore
PR3 — PostgresIdempotencyStore
PR4 — Transactional Semantic Write-Side Boundary
PR5 — PostgreSQL Concurrency Admission Boundary
PR6 — Validation Placement Strategy Boundary / Stage 4 Prelude
```

---

## PR Details

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

- [From In-Memory Correctness to Durable Consistency](../../postmortems/from_in_memory_correctness_to_durable_consistency.md)  
  Explains why persistence is not a backend swap and why durable systems must handle restart and partial failure explicitly.

- [From Git Local–Remote Drift to Database Immutability Boundaries](../../postmortems/from_git_sync_to_db_immutability.md)  
  Explains why Python-side guarantees such as `frozen=True` and append-only history must be re-declared at the PostgreSQL boundary.

- [From Local PostgreSQL Setup to Defense-in-Depth Boundaries](../../postmortems/from_local_postgres_to_defense_in_depth.md)  
  Explains why Docker Compose, `.env`, least privilege, SQL migrations, Compass validation, and transactions each protect different boundaries.

- [From Runtime Behavior to Durable Evidence](../../postmortems/from_runtime_behavior_to_durable_evidence.md)  
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

- [ADR 0010 — Separate Transaction Atomicity from Concurrency Admission](../../adr/0010_transaction_atomicity_vs_concurrency_admission.md)
- [ADR 0011 — Separate Validation Mode from Validation Placement Strategy](../../adr/0011_validation_mode_vs_validation_placement.md)
- [Postmortem — From Durable Persistence to Semantic Gate Preservation](../../postmortems/from_durable_persistence_to_semantic_gate_preservation.md)

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

- [ADR 0010 — Separate Transaction Atomicity from Concurrency Admission](../../adr/0010_transaction_atomicity_vs_concurrency_admission.md)
- [ADR 0011 — Separate Validation Mode from Validation Placement Strategy](../../adr/0011_validation_mode_vs_validation_placement.md)
- [ADR 0012 — Two-Phase Concurrency Admission for PostgreSQL Write-Side](../../adr/0012_two_phase_concurrency_admission.md)
- [Postmortem — Autocommit, Transaction Boundaries, and Partial-Write Risk](../../postmortems/autocommit_boundary_and_partial_write_risk.md)

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

- [Validation Placement Strategy Boundary](../../boundary_notes/validation_placement_strategy_boundary.md)
- [Pre-Transaction Read Cleanup Boundary](../../postmortems/pre_transaction_read_cleanup_boundary.md)

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
