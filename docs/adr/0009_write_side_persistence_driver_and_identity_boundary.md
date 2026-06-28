# ADR 0009: Write-Side Persistence Driver and Identity Generation Boundary

[← Back to ADR Index](README.md)

## Status

Accepted

---

## Implementation Status

Accepted and implemented at baseline level.

This ADR is implemented by the Stage 3.5B durable write-side baseline. The project uses explicit PostgreSQL access for accepted-history persistence and centralizes event identity generation behind a small helper boundary.

Implemented by:

- Stage 3.5B PR1 — Physical Schema + Local PostgreSQL + Migration Skeleton
- Stage 3.5B PR2 — PostgresEventStore
- Stage 3.5B PR4 — Transactional Semantic Write-Side Boundary

Related implementation notes:

- [Stage 3.5B Implementation Notes](../implementation_notes/stage_3_5b/)
- [Stage 3.5B PR Breakdown](../implementation_notes/stage_3_5b/pr_breakdown.md)

Related source files:

- `src/core/common/ids.py`
- `src/storage/postgres_event_store.py`
- `src/storage/postgres_connection.py`
- `db/migrations/001_create_write_side_tables.sql`

Related tests:

- `tests/integration/storage/test_postgres_event_store.py`
- `tests/integration/pipeline/test_postgres_transactional_write_side.py`

Implemented baseline behavior:

- accepted event identity is stored as PostgreSQL `UUID`
- event identity generation is centralized instead of scattered across the codebase
- `PostgresEventStore` persists accepted history through explicit PostgreSQL operations
- Decimal / NUMERIC round-trip behavior is preserved at the durable write-side boundary
- JSONB evidence fields remain explicit durable containers
- UUIDv7 remains deferred until a concrete runtime or storage need justifies the migration

This ADR remains accepted because the write-side event-store boundary is now implemented as an explicit durable accepted-history boundary rather than a generic CRUD repository.

---

## Target Stage

Stage 3.5B — Durable Write-Side Baseline

---

## Depends On

- [ADR 0005: Persistent Storage Baseline Strategy](0005_persistent_storage_baseline_strategy.md)
- [ADR 0006: Use Decimal for Money Values Before Durable Persistence](0006_use_decimal_for_money_values_before_durable_persistence.md)
- [ADR 0008: Pre-Allocated Event Identity and Candidate/Accepted Event Naming Boundary](0008_pre_allocated_event_identity_and_candidate_accepted_boundary.md)

---

## Context

The project is entering Stage 3.5B, where the write-side baseline moves from in-memory execution into PostgreSQL-backed durable persistence.

PR1 established the physical database contract for the durable write-side baseline, including:

```text
order_events
idempotency_records
accepted_event_id UUID
amount NUMERIC(18,2)
payload_json JSONB
proof_json JSONB
metadata_json JSONB
event_schema_version
```

PR2 begins wiring Python runtime behavior into the `order_events` table through a PostgreSQL-backed event store.

This creates two closely related implementation questions:

```text
1. Which persistence access strategy should the write-side event store use?
2. How should event identity be generated before durable persistence grows larger?
```

These questions are not only package-selection questions.

They affect how clearly the system preserves:

- append-only event-store semantics
- accepted-history boundaries
- exact money representation
- UUID round-trip behavior
- expected-version checks
- future transaction boundaries
- future UUID strategy migration

The current project already established in ADR 0008 that:

```text
event_id alone does not imply accepted history.
Only presence in the event log grants accepted-event status.
```

ADR 0008 defines the lifecycle meaning of candidate and accepted event identity.

This ADR defines how the Stage 3.5B write-side persistence baseline should implement the persistence driver boundary and event identity generation boundary.

---

## Problem

The write-side event store is not a generic CRUD repository.

It is the durable boundary where accepted history becomes persistent.

For this project, the event store must preserve the following properties:

```text
- append-only writes
- no mutation of accepted history
- ordered loading by aggregate sequence
- uniqueness of accepted event identity
- uniqueness of aggregate sequence
- expected-version / stale-write rejection
- exact Decimal-to-NUMERIC behavior
- UUID identity preservation
- JSONB evidence preservation
```

Using a high-level ORM may be convenient for many application workflows, but it can also obscure the exact SQL executed at this boundary.

That obscurity is undesirable for the Stage 3.5B write-side baseline because the current goal is not object-relational convenience.

The current goal is:

```text
make accepted event history durable while keeping the persistence contract visible, testable, and aligned with the event-sourcing boundary.
```

A second problem appears around event identity.

Before durable persistence, event IDs were mostly Python runtime identifiers.

After durable persistence, accepted event IDs become part of the database contract and event-log truth boundary.

The project currently can continue using UUIDv4, but future storage concerns may make a time-ordered UUID strategy such as UUIDv7 attractive.

However, adopting UUIDv7 immediately would create unnecessary coupling to Python version support or additional dependencies before PR2 has even established the PostgresEventStore baseline.

The project needs a small boundary now that keeps the current implementation simple while preserving a future migration path.

---

## Decision

We will make two decisions for the Stage 3.5B write-side persistence baseline.

### Decision 1 — Use `psycopg` for write-side persistence

For the Stage 3.5B write-side persistence baseline, the project will use `psycopg` as the PostgreSQL driver.

The write-side event store will use explicit SQL for core persistence operations.

This applies to the current write-side event-store path, especially:

```text
PostgresEventStore.append(...)
PostgresEventStore.load(...)
PostgresEventStore.last_event(...)
```

This decision does not reject ORMs as general-purpose tools.

It only states that the Stage 3.5B write-side event-store boundary should remain explicit and driver-level while the project is establishing durable accepted-history semantics.

### Decision 2 — Centralize event identity generation

The project will centralize event ID generation behind a small helper boundary.

The initial helper may use UUIDv4:

```python
import uuid

def generate_event_id() -> uuid.UUID:
    return uuid.uuid4()
```

The project will not adopt UUIDv7 immediately.

The purpose of the helper is to prevent scattered UUID generation and preserve a future migration path toward UUIDv7 or another time-ordered identity strategy.

---

## Chosen Approach

The selected approach is:

```text
- use psycopg for explicit PostgreSQL access in the write-side persistence baseline
- keep SQL visible at the event-store boundary
- preserve Decimal / NUMERIC and UUID round-trip behavior through tests
- centralize event ID generation in one helper
- keep UUIDv4 for now
- defer UUIDv7 until the project has a clear runtime or storage reason to adopt it
```

The recommended initial module is:

```text
src/core/common/ids.py
```

The recommended initial dependency is:

```text
psycopg[binary]
```

`psycopg[binary]` may be used for local development convenience.

If the project later moves toward stricter deployment packaging, the dependency choice can be revisited without changing the architecture decision that the write-side persistence boundary should remain explicit and testable.

---

## Rationale

### 1. The write-side event store should make append-only semantics visible

The event store is responsible for accepted history.

The core write operation should look like an append:

```sql
INSERT INTO order_events (...)
VALUES (...)
```

This is easier to review, test, and reason about when the SQL is explicit.

An ORM can still perform inserts, but its object-tracking model may introduce concepts that are not central to an append-only event log, such as entity mutation, dirty tracking, or object lifecycle persistence.

The project does not need those concepts for PR2.

### 2. Expected-version behavior should remain explicit

The write-side path must reject stale writes.

This can be implemented through explicit checks against the current aggregate sequence and database uniqueness constraints.

For this boundary, the system should make the relationship between:

```text
expected_current_version
current persisted sequence
new event sequence
unique(order_id, sequence)
```

easy to inspect.

Explicit SQL keeps that relationship close to the code and tests.

### 3. Decimal and UUID round-trips must be testable

Stage 3.5A moved money-like values to `Decimal`.

Stage 3.5B stores these values in PostgreSQL as `NUMERIC(18,2)`.

The event store must verify that money values do not silently degrade into float behavior.

Similarly, PR1 introduced UUID columns for durable accepted event identity.

PR2 must verify that Python event identity and PostgreSQL UUID values round-trip correctly.

Driver-level access makes these type boundaries visible and testable.

### 4. JSONB evidence should remain under project control

The write-side schema includes JSONB containers such as:

```text
payload_json
proof_json
metadata_json
```

These fields are part of the durable evidence model.

They should be written deliberately.

Using explicit SQL and explicit serialization boundaries helps preserve the distinction between:

```text
domain payload
validation proof
runtime metadata
```

### 5. UUIDv7 should be deferred, not ignored

Time-ordered UUIDs may be useful for future storage locality, operational inspection, or append-heavy event-log behavior.

However, PR2 should not be blocked by:

```text
- Python version upgrade decisions
- UUIDv7 library selection
- premature optimization
- broad event identity refactors
```

Centralized event ID generation is the correct small step now.

It prevents scattered UUID-generation logic and keeps the future UUIDv7 migration localized.

---

## Alternatives Considered

### Option A — Use `psycopg` with explicit SQL

This is the selected option for Stage 3.5B write-side persistence.

#### Benefits

```text
- SQL is visible and reviewable
- append-only semantics are explicit
- expected-version checks remain close to the persistence boundary
- Decimal / NUMERIC behavior can be tested directly
- UUID round-trip behavior can be tested directly
- JSONB evidence handling remains explicit
- future transaction boundary remains easier to reason about
```

#### Costs

```text
- more manual SQL
- more boilerplate
- less automatic object mapping
- more responsibility for connection and transaction handling
```

#### Why Accept the Cost

This project is currently optimizing for correctness, boundary clarity, and durable truth semantics rather than CRUD convenience.

The extra explicitness is valuable at the write-side event-store boundary.

---

### Option B — Use SQLAlchemy ORM

This option would represent event records through ORM models and use SQLAlchemy sessions for persistence.

#### Benefits

```text
- familiar application-level abstraction
- less manual SQL
- easier CRUD-style development
- useful for many read-side or admin workflows
```

#### Costs

```text
- generated SQL may become less visible
- object lifecycle concepts may obscure append-only event-log semantics
- session behavior may blur when data is staged vs persisted
- expected-version and immutability rules still require careful explicit design
- not necessary for the minimal PostgresEventStore baseline
```

#### Why Not Now

SQLAlchemy is not rejected permanently.

It may be useful later for read-side, admin, reporting, or query-heavy components.

It is not selected for the current write-side event store because PR2 needs explicit control over durable accepted-history semantics.

---

### Option C — Use SQLAlchemy Core only

This option would use SQLAlchemy Core expression language without the ORM.

#### Benefits

```text
- more explicit than ORM
- portable SQL construction
- avoids most object lifecycle issues
```

#### Costs

```text
- still adds abstraction before the raw persistence boundary is understood
- introduces another dependency and style before PR2 establishes the minimal baseline
- not necessary for the current event-store scope
```

#### Why Not Now

SQLAlchemy Core remains a possible future refactor.

For PR2, direct driver-level SQL is simpler and closer to the database contract already established in PR1.

---

### Option D — Adopt UUIDv7 immediately

This option would change event ID generation to UUIDv7 immediately.

#### Benefits

```text
- more time-ordered identity behavior
- potentially better insert locality and operational ordering
- closer to future event-log storage needs
```

#### Costs

```text
- may require newer Python version support or additional dependencies
- increases PR2 scope
- risks mixing event-store baseline work with identity strategy migration
- may create churn before the durable write-side loop exists
```

#### Why Not Now

UUIDv7 is deferred because PR2 should first establish:

```text
Python runtime → PostgresEventStore → order_events
```

The project should avoid blocking durable persistence on a Python version or dependency decision.

The selected approach keeps UUIDv4 now but centralizes generation so a future migration is localized.

---

### Option E — Keep scattered UUID generation

This option would continue generating UUIDs wherever event objects or tests need them.

#### Benefits

```text
- no immediate refactor
- smallest short-term change
```

#### Costs

```text
- future UUIDv7 migration becomes harder
- event identity policy becomes implicit
- tests and production code may drift
- candidate / accepted identity semantics become harder to audit
```

#### Why Not Now

This option conflicts with the project’s current move toward durable identity semantics.

Once event IDs become durable accepted-history identifiers, identity generation should become an explicit boundary.

---

## Consequences

### Positive Consequences

This decision keeps the write-side event-store boundary visible.

It makes the PR2 baseline easier to review because the SQL responsible for accepted history is explicit.

It also gives future PR3 and PR4 a cleaner foundation:

```text
PR2 — durable accepted event history
PR3 — durable idempotency records
PR4 — transactional event append + idempotency record write
```

The identity-generation helper prevents future UUID strategy changes from leaking across the domain model, event store, tests, and schema.

The decision aligns with ADR 0008 by treating identity as a lifecycle-aware concept rather than a generic string.

### Negative Consequences

This decision increases manual implementation work.

The project must explicitly handle:

```text
- SQL statements
- connection management
- transaction boundaries
- serialization / deserialization
- error mapping
- test database setup
```

The project also accepts that UUIDv4 remains in use for now, even though a time-ordered identity strategy may become preferable later.

That is an intentional trade-off.

The current priority is to establish a correct durable write-side baseline before optimizing event identity ordering.

---

## Impact on PR2

PR2 should include:

```text
- add psycopg dependency
- add event ID generation helper
- add PostgreSQL connection helper
- implement PostgresEventStore baseline
- test append / load / last_event
- test UUID round-trip
- test Decimal round-trip
- test JSONB metadata round-trip
- test duplicate order sequence rejection
- test stale expected-version rejection
```

PR2 should not include:

```text
- PostgresIdempotencyStore
- event append + idempotency record in one transaction
- UUIDv7 migration
- SQLAlchemy integration
- registry-stage timing
- SemanticOutcome
- Compass Layer 2 validation
```

---

## Impact on PR3 and PR4

PR3 can build `PostgresIdempotencyStore` using the same persistence style.

PR4 can introduce the transactional write-side boundary using explicit database transactions.

Because the write-side persistence path remains driver-level and explicit, PR4 should be able to reason clearly about:

```text
BEGIN
check idempotency
rehydrate aggregate
build validation context
create candidate event
Compass Layer 1 validation
append event
record idempotency result
COMMIT
```

If the project later introduces a higher-level persistence abstraction, it should preserve this transaction clarity.

---

## Impact on Future Read-Side Persistence

This ADR is specifically about the write-side durable baseline.

It does not prohibit using other persistence tools elsewhere.

For example, SQLAlchemy or another query abstraction may be considered later for:

```text
- read-side reporting
- admin tooling
- complex query views
- dashboard-oriented workflows
```

The key boundary is:

```text
write-side accepted-history persistence should remain explicit until the durable semantics are fully proven.
```

---

## Impact on Future UUIDv7 Migration

A future migration to UUIDv7 or another time-ordered identity strategy should modify the centralized generator instead of scattering changes across the system.

A future ADR or evolution note may be appropriate when the project actually decides to adopt UUIDv7.

That future decision should consider:

```text
- Python runtime version
- dependency policy
- database insert locality
- ordering semantics
- test determinism
- migration impact on existing records
```

Until then, UUIDv4 remains acceptable for the current baseline.

---

## Non-goals

This ADR does not introduce:

```text
- a general ban on ORMs
- a general persistence framework
- SQLAlchemy removal from all possible future components
- UUIDv7 migration
- a production packaging policy for psycopg
- a full transaction manager
- a PostgresIdempotencyStore
- a Unit of Work abstraction
- a generalized event protocol
- a read-side query framework
```

This ADR also does not change the rule defined in ADR 0008:

```text
event_id alone does not imply accepted history.
Only presence in the event log grants accepted-event status.
```

---

## Future Work

Potential future improvements:

```text
- evaluate UUIDv7 after the durable write-side baseline is complete
- consider whether read-side or admin tooling benefits from SQLAlchemy
- introduce structured database error mapping for duplicate sequence and stale-version cases
- document transaction ownership before PR4
- add a postmortem about moving from runtime UUID convenience to durable event identity
- add tests that prove event identity generation is centralized
- revisit psycopg packaging choice before deployment-oriented work
```

---

## Summary

This ADR records the write-side persistence driver and identity generation boundary for Stage 3.5B.

The project chooses explicit `psycopg`-based PostgreSQL access for the write-side event-store baseline because accepted history requires visible, testable, append-only persistence semantics.

The project also centralizes event ID generation while keeping UUIDv4 for now.

This preserves a future migration path toward UUIDv7 without blocking the current PostgresEventStore baseline.

The core principle is:

```text
For the write-side event store, persistence is not only storage.
It is the durable boundary where accepted history becomes truth.
```
