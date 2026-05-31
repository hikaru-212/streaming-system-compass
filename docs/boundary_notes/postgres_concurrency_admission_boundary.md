# PostgreSQL Concurrency Admission Boundary

[← Back to Boundary Notes](README.md)

## Purpose

This note defines the Stage 3.5B PR5 PostgreSQL concurrency admission boundary.

PR4 established the transactional write-side boundary:

```text
accepted event append
+ idempotency record persistence
+ one PostgreSQL transaction
= commit or roll back together
```

PR5 introduces a different boundary:

```text
multiple writers
+ same aggregate stream
+ same next accepted-history position
= only one writer may be admitted
```

This note exists to prevent a common mistake:

```text
transaction atomicity
≠
concurrency admission
```

A database transaction can make related writes succeed or fail together.

It does not, by itself, define which competing writer should be allowed to occupy the next stream position.

---

## Boundary Definition

Concurrency admission decides whether a candidate event may occupy the next accepted-history position of an aggregate stream.

For an order stream, that means deciding whether a candidate event is still allowed to append at the expected next sequence.

Example:

```text
current accepted history:
order_id = order-123
latest sequence = 1

candidate event:
order_id = order-123
sequence = 2
expected_current_version = 1
```

The admission boundary answers:

```text
Is this writer still allowed to append sequence 2?
```

If another writer has already appended sequence 2, this writer must be rejected as stale or conflicting.

---

## What Admission Owns

Admission owns:

- stale writer detection
- append-time stream-position occupation
- expected-version verification
- sequence conflict translation
- lock timeout translation
- stable admission result production
- optimistic / pessimistic admission strategy boundaries

Admission should turn physical persistence conflicts into stable admission-level meaning.

For example:

```text
UNIQUE(order_id, sequence) violation
→ append-time sequence conflict
→ stale or conflicting writer
→ AdmissionResult(STALE_WRITE)
```

---

## What Admission Does Not Own

Admission does not own:

- domain legality
- aggregate transition rules
- idempotency replay / conflict classification
- Compass validation
- transaction atomicity
- retry policy
- Stage 4 SemanticOutcome mapping
- RuntimeDecisionPolicy
- user-facing error formatting

These are separate boundaries.

---

## Why Stable Admission Results Matter

Raw PostgreSQL exceptions are physical failure shapes.

Examples include:

```text
UniqueViolation
SerializationFailure
DeadlockDetected
LockNotAvailable
ForeignKeyViolation
```

These exceptions are useful inside the persistence boundary, but they are not stable orchestration semantics.

The write-side orchestration should not need to know:

- which PostgreSQL constraint failed
- which table produced the error
- whether the failure came from a unique index, lock timeout, or isolation conflict
- whether the same logical condition would look different under a future storage strategy

Instead, PR5 should translate low-level storage failures into stable admission results such as:

```text
ADMITTED
STALE_WRITE
LOCK_TIMEOUT
INFRASTRUCTURE_ERROR
```

The upper write-side flow should make decisions based on admission meaning, not database-driver details.

---

## Storage Errors vs Admission Results

PR5 should distinguish two layers.

### Storage-level errors

Storage-level errors describe persistence-boundary failures.

Examples:

```text
StorageError
StorageConflictError
StaleWriteError
AppendConflictError
StorageInfrastructureError
```

These errors are allowed near the storage / persistence boundary.

They should not become the public control language of the upper orchestration layer.

### Admission results

Admission results describe whether a candidate event was admitted.

Examples:

```text
AdmissionResult(ADMITTED)
AdmissionResult(STALE_WRITE)
AdmissionResult(LOCK_TIMEOUT)
AdmissionResult(INFRASTRUCTURE_ERROR)
```

The admission gate may catch storage-level errors and return an admission result.

This keeps the upper write-side flow stable.

---

## Why PR4 Could Tolerate Raw Exceptions More Easily

PR4 focused on transaction atomicity.

Its main question was:

```text
If one write fails, does the whole transaction roll back cleanly?
```

For PR4, a domain `ValueError` or forced persistence failure was acceptable as long as:

```text
exception occurs
→ transaction rolls back
→ no partial order_events row remains
→ no partial idempotency_records row remains
```

In PR4, the key requirement was rollback safety.

PR5 is different.

In PR5, stale writes are not rare bugs.

They are expected runtime outcomes under concurrent writers.

Therefore, PR5 must not treat every concurrency conflict as an unclassified exception.

It should classify the conflict into stable admission meaning.

---

## Why This Is Not Stage 4 SemanticOutcome

PR5 does not introduce the full Stage 4 SemanticOutcome model.

PR5 only introduces an intermediate admission boundary:

```text
raw PostgreSQL exception
→ storage/admission error
→ AdmissionResult
```

Stage 4 may later map admission results into:

```text
SemanticOutcome
→ RuntimeDecision
```

But PR5 should avoid pulling in the full Stage 4 runtime governance model.

The purpose of PR5 is narrower:

```text
make concurrency admission explicit and stable
```

not:

```text
complete semantic outcome governance
```

---

## Persistence of Admission Results

PR5 admission results do not need to be persisted by default.

At this stage, `AdmissionResult` is a runtime orchestration artifact.

It answers whether a candidate event was admitted during the current write attempt.

Future stages may introduce durable evidence for admission attempts, such as:

```text
attempt_id
trace_id
admission_verdict
rejected_expected_version
actual_version
lock_wait_ms
admission_strategy
```

That belongs to future observability, audit, or Stage 4 SemanticOutcome / runtime evidence work.

For PR5, the important rule is:

```text
do not mix admission result modeling with durable governance evidence too early
```

If a correlation identifier is needed for logging or tests, it should be treated as optional metadata rather than a required semantic field of the minimal admission result.

---

## Optimistic Admission

Optimistic admission is the default strategy for high-frequency / low-contention streams.

It assumes most writers are operating on different aggregate streams or that conflicts are rare.

Typical shape:

```text
load current history
build candidate event
attempt append with expected version
if append succeeds:
    ADMITTED
if version changed or sequence is occupied:
    STALE_WRITE
```

This strategy works well when many commands target different `order_id` values.

It does not prevent all contention.

It detects conflicts at append time and rejects stale writers.

---

## Pessimistic Admission

Pessimistic admission is a strategy for hot streams or high-contention aggregates.

It may use a transaction-scoped lock, such as a PostgreSQL advisory transaction lock or row-level locking strategy.

Typical shape:

```text
BEGIN
acquire stream-level lock
load current history
rehydrate aggregate
validate candidate
append event
record idempotency
COMMIT
```

This strategy can reduce retry storms under high contention, but it increases waiting time and transaction duration.

It should not be the default for every stream.

---

## Retry Storm Risk

Optimistic admission can produce retry storms under high contention.

Example:

```text
many writers read version 1
many writers build sequence 2
one writer appends sequence 2
all other writers become stale
all stale writers retry immediately
```

PR5 does not need to implement a full retry policy.

However, PR5 should make stale-write outcomes explicit so a future retry policy can reason about them.

Future retry policy may include:

- bounded retry
- exponential backoff
- jitter
- hot-stream detection
- switching to pessimistic admission for hot streams
- refusing automatic retry for irreversible operations

---

## Minimal PR5 Implementation Direction

PR5 should proceed in small steps.

### Step 1 — Vocabulary

Introduce:

```text
StorageError
StorageConflictError
StaleWriteError
AppendConflictError
StorageInfrastructureError

AdmissionVerdict
AdmissionResult
```

### Step 2 — Optimistic Gate

Introduce a PostgreSQL optimistic admission gate.

It should translate append conflicts into stable admission results.

### Step 3 — Pessimistic Gate

Introduce a PostgreSQL pessimistic admission gate.

It should provide a strategy for hot streams or explicitly serialized admission.

### Step 4 — Write-Side Integration

Replace direct append in the durable write-side flow with the admission boundary.

### Step 5 — Documentation and Roadmap Update

Document the final PR5 boundary and update roadmap status.

---

## Relationship to ADRs

This note is related to:

- [ADR 0010 — Separate Transaction Atomicity from Concurrency Admission](../adr/0010_transaction_atomicity_vs_concurrency_admission.md)
- [ADR 0011 — Separate Validation Mode from Validation Placement Strategy](../adr/0011_validation_mode_vs_validation_placement.md)

ADR 0010 explains why PR5 exists after PR4.

ADR 0011 explains why validation placement still depends on append-time concurrency admission.

This boundary note focuses on how PR5 should translate those architecture decisions into implementation boundaries.

---

## Final Principle

Admission is not just an exception handler.

Admission is the write-side boundary that decides whether a candidate event may become accepted history under concurrent writers.

The core rule is:

```text
raw database conflict
→ stable admission meaning
→ future runtime decision
```

PR5 should make that middle layer explicit.
