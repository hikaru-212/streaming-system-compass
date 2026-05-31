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
- Stage 4 is not only an error taxonomy stage; it becomes a structured semantic outcome and runtime decision boundary
- Stage 5 becomes the dual-dimension governance demo: semantic correctness × operational freshness → action safety

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

This means:

- Stage 1 is complete at a baseline level
- Stage 2 is complete at a baseline level
- Stage 3 exists as a minimal executable read-side runtime baseline
- Stage 3.5A is complete as the pre-persistence money / exact-value hardening step
- pre-Stage 3.5B event identity semantics are documented and reflected in boundary naming
- Stage 3.5B PR1 has established the durable write-side schema and local PostgreSQL setup baseline
- Stage 3.5B PR4 has established the first PostgreSQL-backed transactional semantic write-side flow

The next major focus is:

- **Stage 3.5B PR5 — PostgreSQL concurrency admission boundary**

Only after transaction atomicity and PostgreSQL-backed concurrency admission are clarified should the project proceed toward:

- PR6 / Stage 4 Prelude validation placement strategy
- Stage 3.5C durable read-side baseline
- Stage 4 runtime semantic validation, structured semantic outcomes, and runtime decision policy
- Stage 5 dual-dimension governance demo

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
10. runtime semantic outcomes
11. runtime decision policy
12. action safety gate
13. dual-dimension governance demo
14. later governance and adversarial hardening

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

- `UNIQUE (order_id, sequence)`
- `event_type IN ('created', 'paid')`
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

In progress / closing implementation.

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
→ admit(candidate_event, expected_current_version)
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

Deferred.

#### Goal

Introduce a configurable validation placement strategy after PostgreSQL concurrency admission exists.

#### Why

PR4 establishes an in-transaction Compass validation baseline.

PR5 establishes two-phase PostgreSQL concurrency admission.

Only after PR5 can the project safely support a second orchestration mode:

```text
pre-transaction Compass validation + OCC
```

This future strategy allows the system to compare latency and safety trade-offs between:

- in-transaction Compass validation
- pre-transaction Compass validation + OCC
- validation-off baseline for measurement

#### Main Work

- define `ValidationPlacement`
- keep `ValidationMode` separate from `ValidationPlacement`
- support `IN_TRANSACTION` validation placement
- support `PRE_TRANSACTION` validation + OCC
- prepare a future write-side factory / config layer
- enable future latency comparison without duplicating storage logic

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

#### Non-goals

PR6 / Stage 4 Prelude does not implement:

- full DAG node model
- risk scoring
- async audit pipeline
- Stage 4 `SemanticOutcome` tables
- Stage 5 governance metrics

---

## Stage 3.5B Completion Criteria

Stage 3.5B is complete when:

- accepted events are persisted in PostgreSQL
- accepted history can be replayed from durable storage
- idempotency records survive restart / new connection
- replay / conflict semantics work against durable storage
- event append and idempotency record write are transactionally coordinated
- Compass Layer 1 remains on the durable write-side path before accepted history mutation
- validation `BLOCK` does not pollute accepted history or idempotency memory
- PostgreSQL-backed concurrency admission rejects stale writers explicitly
- exact money persistence is preserved
- UUID event identity is preserved
- candidate / accepted event identity semantics remain clear
- destructive PostgreSQL tests run against `TEST_DATABASE_URL`, not the development database
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

Possible fields:

- `worker_name`
- `last_consumed_order_id` or stream position
- `last_processed_sequence`
- `updated_at`

Exact shape should follow the current projection worker and checkpoint model.

## Completion Criteria

- projection state survives restart
- checkpoint survives restart
- worker can resume from checkpoint
- projection can rebuild from accepted history
- read-side persistence does not redefine source of truth
- replay from durable `order_events` can rebuild the projection deterministically

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

### Completion Criteria

- projection drift emits `SemanticOutcome`
- outcome contains context and evidence
- tests assert structured fields
- tests do not depend only on exception message strings

### Boundary

Stage 4B classifies what happened.

It does not decide what the runtime should do.

---

## Stage 4C — Runtime Decision Policy v1

### Goal

Convert `SemanticOutcome` into `RuntimeDecision`.

This is the detect → classify → decide step.

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
  PR5 PostgreSQL Concurrency Admission Boundary

PR6 / Stage 4 Prelude:
Validation Placement Strategy
  IN_TRANSACTION vs PRE_TRANSACTION + OCC

Stage 3.5C:
Durable Read-side Baseline

Stage 4:
Runtime Semantic Validation and Runtime Decision Boundary
  4A Layer 2 Minimal Validator
  4B Structured Semantic Outcome / Error Model v1
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
→ structured semantic outcome
→ runtime decision policy
→ action safety gate
→ dual-dimension governance demo
```

The project is not only trying to know that something failed.

It is trying to make semantic failure understandable enough that the runtime can decide whether to continue, rebuild, block, quarantine, stop, or escalate.
