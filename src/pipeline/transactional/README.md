# Transactional Pipeline

[← Back to Pipeline README](../README.md)

This module defines the write-side transactional execution path.

The transactional pipeline is the runtime boundary where commands become candidate events, candidate events are validated, and admitted events become accepted history.

```text
command
→ idempotency check
→ accepted-history rehydration
→ candidate event creation
→ Compass validation
→ admission
→ accepted-history append
→ idempotency record
```

---

## Purpose

The purpose of this module is to coordinate write-side execution without moving domain meaning, persistence authority, or Compass validation semantics into the wrong layer.

The transactional pipeline answers:

- how a command moves through the system
- when idempotency is checked
- when accepted history is loaded
- when a candidate event is created
- when Compass validation runs
- when admission happens
- when accepted history is mutated
- when idempotency memory is recorded
- which writes must commit or roll back together

---

## Responsible For

This module is responsible for:

- write-side command orchestration
- idempotency-first request handling
- aggregate rehydration from accepted history
- validation context construction
- Compass Layer 1 invocation
- persistence admission coordination
- transactional write-side commit / rollback boundary
- validation placement strategy
- optimistic / pessimistic PostgreSQL admission strategy integration

---

## Not Responsible For

This module is **not** responsible for:

- defining domain legality rules
- deciding business state transitions inside the aggregate
- defining Compass validation semantics
- acting as the storage layer itself
- defining Stage 4 `SemanticOutcome`
- defining runtime decision policy
- implementing production retry orchestration
- implementing full production locking infrastructure
- implementing cross-aggregate distributed transaction policy

Those responsibilities belong to:

- `src/core/`
- `src/compass/`
- `src/storage/`
- future runtime governance layers

---

## Current Files

### `registry.py`

Defines the original in-memory transactional orchestration boundary.

It coordinates:

```text
idempotency
→ aggregate rehydration
→ candidate event creation
→ Compass validation
→ admission gate
→ local aggregate apply
→ idempotency record
```

This file remains useful as the simplest conceptual version of the write-side flow.

It does not own domain legality or validation semantics.

---

### `admission.py`

Defines the persistence admission vocabulary and structural admission boundary.

Important types include:

- `AdmissionVerdict`
- `StreamAdmissionResult`
- `AdmissionResult`
- `ConcurrencyGate`
- `OptimisticVersionGate`

The important distinction is:

```text
StreamAdmissionResult
≠
AdmissionResult
```

`StreamAdmissionResult` answers whether a writer may enter the stream-preparation boundary.

`AdmissionResult` answers whether a candidate event may occupy the next accepted-history stream position.

This separation exists because optimistic and pessimistic strategies acquire protection at different physical moments.

---

### `postgres_admission.py`

Defines PostgreSQL-backed admission gates.

Current strategies include:

- `PostgresOptimisticAdmissionGate`
- `PostgresPessimisticAdmissionGate`

The optimistic strategy does not pre-lock the stream. It relies on append-time continuity protection.

The pessimistic strategy acquires a transaction-scoped advisory lock during stream preparation.

Both strategies translate storage-level conflicts into stable `AdmissionResult` / `StreamAdmissionResult` values instead of leaking raw PostgreSQL exceptions into the write-side orchestration layer.

---

### `postgres_unit_of_work.py`

Defines the PostgreSQL write-side transaction boundary.

It coordinates the durable write-side stores that must participate in the same transaction:

- `PostgresEventStore`
- `PostgresIdempotencyStore`

Its responsibility is physical transaction control:

```text
commit all write-side persistence changes together
rollback all write-side persistence changes together
```

It does not own domain semantics, Compass validation, command creation, or retry policy.

---

### `postgres_write_side_config.py`

Defines write-side orchestration configuration.

Current configuration includes:

- `ValidationPlacement.IN_TRANSACTION`
- `ValidationPlacement.PRE_TRANSACTION`
- `PostgresWriteSideConfig`

This file keeps validation strength separate from validation placement.

```text
ValidationMode
= how strong validation is

ValidationPlacement
= where validation runs relative to the PostgreSQL transaction
```

---

### `postgres_write_side.py`

Defines the PostgreSQL-backed transactional write-side flow.

It coordinates:

```text
PostgresWriteSideUnitOfWork
+ PostgresEventStore
+ PostgresIdempotencyStore
+ AdmissionGateFactory
+ ValidationRuntime
+ PostgresWriteSideConfig
```

The default behavior remains:

```text
ValidationMode.STRICT
ValidationPlacement.IN_TRANSACTION
PostgresOptimisticAdmissionGate
```

It also supports a minimal `PRE_TRANSACTION` validation path guarded by an authoritative in-transaction idempotency re-check and append-time admission.

---

## In-Transaction Write-Side Flow

The default durable write-side flow is:

```text
BEGIN

check idempotency

if REPLAY:
    rollback / no write
    return previous accepted result

if CONFLICT:
    rollback / no write
    return conflict result

prepare stream admission

if admission rejected:
    rollback / no write
    return ADMISSION_REJECTED

load accepted history
rehydrate aggregate
build validation context
create candidate event
run Compass Layer 1 validation

if validation BLOCK:
    rollback / no write
    return VALIDATION_BLOCKED

append candidate event through admission gate
record idempotency result

COMMIT
```

This path preserves the core Stage 3.5B invariant:

```text
accepted event append
+
idempotency record write
```

must commit or roll back together.

---

## Pre-Transaction Validation Flow

The `PRE_TRANSACTION` path intentionally separates CPU-side validation from the final write transaction.

It performs:

```text
1. preliminary idempotency check outside the write transaction
2. accepted-history loading outside the write transaction
3. candidate event creation and Compass validation outside the write transaction
4. authoritative idempotency re-check inside the write transaction
5. stream preparation and append-time admission inside the write transaction
6. accepted event append and idempotency record write inside the write transaction
```

The authoritative re-check and append-time admission are required because pre-transaction validation can become stale before append.

The connection is rolled back after preliminary read work so that CPU-side validation does not accidentally hold an open PostgreSQL read transaction.

---

## Admission Boundary

Admission is intentionally separate from:

- domain legality
- Compass validation truth
- idempotency replay / conflict classification
- transaction atomicity
- Stage 4 `SemanticOutcome`

This distinction matters because:

```text
transaction atomicity
≠
concurrency admission
```

Atomicity answers:

> Do related writes commit or roll back together?

Admission answers:

> Is this writer still allowed to occupy the next accepted-history position?

---

## Validation Placement Boundary

Validation placement is intentionally separate from validation mode.

```text
ValidationMode
≠
ValidationPlacement
```

`ValidationMode` answers how strong validation is.

`ValidationPlacement` answers where validation runs relative to the database transaction.

The current baseline supports:

```text
IN_TRANSACTION
PRE_TRANSACTION
```

`IN_TRANSACTION` remains the default.

---

## Current Stage Status

```text
Stage 3.5B PR4 — Transactional Semantic Write-Side Boundary ✅
Stage 3.5B PR5 — PostgreSQL Concurrency Admission Boundary ✅
Stage 3.5B PR6 — Validation Placement Strategy Boundary / Stage 4 Prelude ✅
```

This module is not part of the current Stage 3.5C PR4 implementation, but documenting it now helps complete the `src/pipeline/` documentation boundary while PR4 adds the read-side projection README.

---

## Current Non-goals

The transactional pipeline currently does not implement:

- Stage 4 `SemanticOutcome`
- runtime decision policy
- retry orchestration
- durable admission audit table
- durable validation attempt table
- full production locking framework
- hot-stream routing policy
- cross-aggregate locking model
- production observability / alerting

---

## Summary

The transactional pipeline turns write-side command intent into accepted history.

The aggregate owns business legality.

Compass owns transition-truth validation.

Storage preserves accepted history and idempotency memory.

Admission protects stream occupation.

The transactional pipeline coordinates their execution order and transaction boundary.
