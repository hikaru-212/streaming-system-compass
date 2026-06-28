# ADR 0011: Separate Validation Mode from Validation Placement Strategy

[← Back to ADR Index](README.md)

## Status

Accepted

---

## Implementation Status

Accepted and implemented at baseline level in Stage 3.5B PR6.

Implemented by:

- Stage 3.5B PR4 — Transactional Semantic Write-Side Boundary
- Stage 3.5B PR5 — PostgreSQL Concurrency Admission Boundary
- Stage 3.5B PR6 — Validation Placement Strategy Boundary / Stage 4 Prelude

Related implementation notes:

- [Stage 3.5B Implementation Notes](../implementation_notes/stage_3_5b/)
- [Stage 3.5B PR Breakdown](../implementation_notes/stage_3_5b/pr_breakdown.md)

Related boundary notes:

- [Validation Placement Strategy Boundary](../boundary_notes/validation_placement_strategy_boundary.md)
- [Pre-Transaction Read Cleanup Boundary](../postmortems/pre_transaction_read_cleanup_boundary.md)

Related source files:

- `src/compass/transition/runtime.py`
- `src/compass/transition/types.py`
- `src/pipeline/postgres_transactional_write_side.py`
- `src/pipeline/postgres_write_side_config.py`
- `src/storage/postgres_optimistic_admission_gate.py`
- `src/storage/postgres_pessimistic_admission_gate.py`

Related tests:

- `tests/integration/pipeline/test_postgres_transactional_write_side.py`
- `tests/integration/storage/test_postgres_admission_gate.py`

This ADR is accepted because the project now supports validation placement as an explicit write-side configuration boundary at the Stage 3.5B baseline level.

The accepted baseline intentionally supports only two meaningful placement / admission combinations:

```text
PRE_TRANSACTION + OPTIMISTIC admission
IN_TRANSACTION  + PESSIMISTIC admission
```

The other two theoretical combinations are documented below as rejected or non-preferred compositions because they combine the cost profile of one strategy with the protection model of the other.

---

## Context

During Stage 3.5B PR4, the project introduced a PostgreSQL-backed transactional write-side flow.

The initial focus of PR4 was transaction atomicity:

```text
PostgresEventStore
+ PostgresIdempotencyStore
+ PostgresWriteSideUnitOfWork
= event append and idempotency record commit or roll back together
```

While integrating Compass Layer 1 into the durable PostgreSQL write-side flow, an important distinction became clear:

```text
Validation mode
≠
Validation placement
```

The existing Compass runtime already supports validation mode selection.

For example:

```text
STRICT
OFF
```

A strict mode can run full semantic transition validation, while an off mode can preserve the validation runtime interface without performing semantic validation.

However, validation mode only answers:

```text
How strong is the validation?
```

It does not answer:

```text
Where is validation executed relative to the database transaction?
```

That second question is validation placement.

A second boundary also needs to remain explicit:

```text
Validation placement
≠
concurrency admission
```

Moving Compass validation inside a transaction does not automatically solve concurrent writer admission.

Likewise, moving Compass validation before a transaction does not remove the need for append-time concurrency admission.

Both execution models still require an admission boundary to reject stale or competing writers.

In this ADR, concurrency admission means checking whether the writer may occupy the next accepted-history stream position. The check may happen as an optimistic append-time version check, or as a pessimistic stream preparation lock followed by append-time continuity protection.

---

## Decision

The project will distinguish between:

```text
ValidationMode
```

and:

```text
ValidationPlacement
```

The project will also keep both of them separate from:

```text
ConcurrencyAdmission
```

This gives the durable write-side four separate design axes:

```text
ValidationMode
= how strong validation is

ValidationPlacement
= where validation runs relative to the transaction

TransactionAtomicity
= whether related writes commit or roll back together

ConcurrencyAdmission
= whether a writer may occupy the next accepted-history position
```

The accepted Stage 3.5B baseline supports only two meaningful composition patterns:

```text
1. PRE_TRANSACTION + OPTIMISTIC admission
2. IN_TRANSACTION  + PESSIMISTIC admission
```

These are not arbitrary pairings.

They follow from the timing of validation, version observation, transaction duration, and lock ownership.

---

## ValidationMode

`ValidationMode` describes validation strength or behavior.

Current implemented modes include:

```text
STRICT
OFF
```

Future modes may include:

```text
PARTIAL
LOW
RISK_BASED
AUDIT_ONLY
```

Validation mode answers:

```text
How strong is the semantic check?
```

It does not answer where the validation runs.

---

## ValidationPlacement

`ValidationPlacement` describes where validation occurs relative to the transaction boundary.

Current baseline values are:

```text
IN_TRANSACTION
PRE_TRANSACTION
```

Future values may include:

```text
ASYNC_AUDIT
```

Validation placement answers:

```text
When does validation run relative to BEGIN / COMMIT?
```

It does not answer whether competing writers are serialized or rejected.

---

## ConcurrencyAdmission

`ConcurrencyAdmission` describes how the system handles competing writers.

Current baseline strategies are:

```text
OPTIMISTIC
PESSIMISTIC
```

Optimistic admission is naturally late:

```text
read
→ validate
→ try append with expected version
→ accept or reject stale writer
```

Pessimistic admission is naturally early:

```text
BEGIN
→ acquire stream lock
→ read
→ validate
→ append while lock is held
→ COMMIT
```

This distinction is why not every validation placement combines cleanly with every admission strategy.

---

## Supported Strategy Combinations

### 1. `PRE_TRANSACTION + OPTIMISTIC`

This is the high-throughput / shorter-transaction strategy.

The flow is:

```text
load accepted history
→ rehydrate aggregate
→ create candidate event
→ run Compass validation outside the write transaction

BEGIN
→ append-time optimistic admission using expected version
→ append accepted event if still current
→ record idempotency result
→ COMMIT
```

This combination is coherent because optimistic admission expects that the world may change between read/validation and append.

The safety boundary is the append-time expected-version check:

```text
validated base version == current accepted-history version
```

If the stream advanced after validation, the append is rejected as stale.

The benefit is that expensive semantic validation does not hold a database transaction open.

The cost is that validation may be wasted if the candidate becomes stale before append.

That waste is acceptable for this strategy because it happens outside the transaction and therefore does not directly hold database locks or long-lived transaction resources during validation.

---

### 2. `IN_TRANSACTION + PESSIMISTIC`

This is the high-defense / serialized-stream strategy.

The flow is:

```text
BEGIN
→ check idempotency
→ acquire stream lock through prepare_stream(order_id)
→ load accepted history while protected
→ rehydrate aggregate
→ create candidate event
→ run Compass validation while protected
→ append-time continuity check
→ append accepted event
→ record idempotency result
→ COMMIT
```

This combination is coherent because pessimistic admission protects the expensive read / rehydrate / validation section.

Once the stream lock is acquired, competing writers for the same stream should not be able to advance the stream concurrently.

Therefore, the validation work is less likely to be wasted by a same-stream version change.

The cost is that the transaction and stream lock are held longer.

That cost is acceptable only for high-risk, high-value, irreversible, or high-contention operations where preventing duplicated work and enforcing serialized stream access is worth the throughput cost.

Even under pessimistic admission, append-time expected-version checking remains necessary as a final continuity guard.

The lock protects the stream critical section.

The append-time check protects accepted-history continuity.

---

## Rejected / Non-Preferred Strategy Combinations

The following combinations are not part of the accepted Stage 3.5B baseline.

They are not impossible in the abstract, but they are rejected as default compositions for this project because their cost and protection models do not align.

---

### Rejected Combination A: `IN_TRANSACTION + OPTIMISTIC`

At first glance, this looks safe because validation runs inside a transaction.

However, optimistic admission does not acquire a stream lock before expensive validation work.

The flow would be:

```text
BEGIN
→ load accepted history
→ rehydrate aggregate
→ create candidate event
→ run Compass validation inside transaction
→ append-time optimistic admission
→ discover version changed
→ rollback / reject stale writer
```

The problem is not that this is logically invalid.

The problem is that it combines the long transaction cost of in-transaction validation with the late-rejection behavior of optimistic admission.

If validation is expensive, the system may hold a database transaction open while doing semantic work, only to discover at the final append-time admission step that the stream version has already changed.

That means:

```text
expensive validation time
+ transaction duration
+ database resource occupancy
→ wasted when append-time OCC rejects the candidate
```

This is worse than `PRE_TRANSACTION + OPTIMISTIC` because the same possible validation waste occurs while a database transaction is open.

It can reduce database throughput by keeping transactions alive during CPU-side or I/O-heavy validation without receiving the main benefit of pessimistic locking.

Therefore:

```text
IN_TRANSACTION + OPTIMISTIC
= not the preferred baseline
```

Use `PRE_TRANSACTION + OPTIMISTIC` if the goal is a shorter transaction with late stale-write rejection.

Use `IN_TRANSACTION + PESSIMISTIC` if the goal is to protect validation work under a stream lock.

---

### Rejected Combination B: `PRE_TRANSACTION + PESSIMISTIC`

This combination is also misaligned.

The flow would be:

```text
load accepted history
→ rehydrate aggregate
→ create candidate event
→ run Compass validation outside transaction

BEGIN
→ acquire stream lock
→ append while lock is held
```

The problem is the gap between validation and lock acquisition.

During that gap, another writer may advance the stream.

If that happens, acquiring the lock afterward does not rescue the prevalidated candidate.

The lock protects only the future critical section.

It cannot retroactively protect the history snapshot used during pre-transaction validation.

So the flow becomes:

```text
validate candidate against version N
→ before lock acquisition, another writer commits version N+1
→ acquire lock
→ candidate is stale
→ append-time continuity check rejects
```

In that case, the pessimistic lock was acquired too late to protect the validation work.

The validation was still wasted, and the lock did not provide the key benefit of pessimistic admission.

This is worse than `PRE_TRANSACTION + OPTIMISTIC` because the late lock adds complexity without protecting the pre-transaction validation window.

It is also worse than `IN_TRANSACTION + PESSIMISTIC` because the validation does not run inside the protected stream critical section.

Therefore:

```text
PRE_TRANSACTION + PESSIMISTIC
= not the preferred baseline
```

Use `IN_TRANSACTION + PESSIMISTIC` if the goal is to acquire the stream lock before reading, rehydrating, and validating.

---

## Strategy Matrix

| Validation Placement | Admission Strategy | Baseline Decision | Reason |
|---|---|---|---|
| `PRE_TRANSACTION` | `OPTIMISTIC` | Supported | Keeps transaction short; append-time OCC detects stale validated candidates. |
| `IN_TRANSACTION` | `PESSIMISTIC` | Supported | Acquires lock before read / rehydrate / validation; protects expensive work under same stream critical section. |
| `IN_TRANSACTION` | `OPTIMISTIC` | Not preferred | Holds transaction during validation but still rejects stale candidates only at the end. |
| `PRE_TRANSACTION` | `PESSIMISTIC` | Not preferred | Acquires lock after validation, so it cannot protect the validation base version. |

This matrix is the core practical outcome of this ADR.

---

## Rationale

### 1. Validation mode and validation placement are independent design axes

A system may run strict validation inside a transaction:

```text
STRICT + IN_TRANSACTION
```

or strict validation before a transaction:

```text
STRICT + PRE_TRANSACTION
```

It may also run no semantic validation for benchmarking / baseline comparison:

```text
OFF + PRE_TRANSACTION + OPTIMISTIC
```

Treating validation strength and validation placement as separate concepts prevents confusion.

---

### 2. Validation placement and concurrency admission are separate but compositional

Moving validation inside a transaction does not automatically make the system concurrency-safe.

A transaction can protect related writes from partial persistence.

It does not by itself decide which writer should be admitted when multiple writers compete for the same aggregate stream.

That question belongs to concurrency admission.

This ADR therefore depends on ADR 0010:

```text
transaction atomicity
≠
concurrency admission
```

This ADR adds:

```text
validation placement
≠
concurrency admission
```

But separation does not mean every combination is equally useful.

The accepted baseline keeps only the combinations where placement timing and admission timing reinforce each other.

---

### 3. In-transaction validation is only worth the cost when the stream is protected

In-transaction validation can be appropriate for irreversible operations, payments, settlement, core ledger transitions, high-value state mutations, or high-risk DAG checkpoints.

But if the system chooses in-transaction validation, it should also choose an admission strategy that protects the expensive validation section.

That is why the accepted high-defense pairing is:

```text
IN_TRANSACTION + PESSIMISTIC
```

Without early stream protection, in-transaction validation risks spending expensive validation time inside an open database transaction and then losing at append-time OCC.

---

### 4. Pre-transaction validation is useful when late rejection is acceptable

Pre-transaction validation keeps database transactions short.

It is appropriate when the system prefers throughput and accepts that a prevalidated candidate may become stale before append.

That is why the accepted high-throughput pairing is:

```text
PRE_TRANSACTION + OPTIMISTIC
```

The append-time expected-version check remains mandatory.

Without it, pre-transaction validation would suffer a TOCTOU bug:

```text
validated state may no longer be current at write time
```

---

### 5. DAG / agent workflows need selective validation placement

Future agent or DAG pipelines may contain multiple nodes:

```text
node1 → node2 → node3 → node4 → node5 → node6
```

It may be unnecessary or too expensive to run strict in-transaction validation at every node.

A more scalable model is selective semantic gate placement:

```text
high-risk / irreversible nodes:
    IN_TRANSACTION + PESSIMISTIC

medium-risk / high-throughput nodes:
    PRE_TRANSACTION + OPTIMISTIC

low-risk / reversible nodes:
    PRE_TRANSACTION + OPTIMISTIC, OFF mode, or future ASYNC_AUDIT
```

This preserves Compass as a semantic governance mechanism while allowing performance-aware deployment.

---

## Consequences

### Positive

- Clarifies the difference between validation strength and validation placement.
- Keeps validation placement separate from transaction atomicity and concurrency admission.
- Prevents the project from treating every placement / admission combination as equally meaningful.
- Preserves `PRE_TRANSACTION + OPTIMISTIC` as the short-transaction, high-throughput baseline.
- Preserves `IN_TRANSACTION + PESSIMISTIC` as the high-defense, serialized-stream baseline.
- Explains why `IN_TRANSACTION + OPTIMISTIC` wastes validation work inside a transaction under stale-write rejection.
- Explains why `PRE_TRANSACTION + PESSIMISTIC` acquires the lock too late to protect pre-transaction validation.
- Supports future DAG / agent governance where only selected nodes require strict semantic gates.

### Negative / Trade-offs

- Adds another architectural dimension that must be documented carefully.
- Future write-side orchestration may require multiple strategy implementations.
- A factory / config layer may be needed to avoid scattering placement-specific conditionals.
- The guarantees of each supported combination must be documented clearly.
- The project must avoid implying that validation placement alone is concurrency admission.

---

## Implementation Direction

### Stage 3.5B PR4

PR4 established the transactional semantic write-side boundary:

```text
PostgresWriteSideUnitOfWork
PostgresTransactionalWriteSide
Compass Layer 1 participation
append + idempotency atomicity
rollback on validation block
```

PR4 should be read as the initial in-transaction validation baseline.

It should not be read as the final concurrency admission solution.

---

### Stage 3.5B PR5

PR5 implemented the PostgreSQL concurrency admission boundary:

```text
PostgresOptimisticAdmissionGate
PostgresPessimisticAdmissionGate
prepare_stream(order_id)
append_if_admitted(candidate_event, expected_current_version)
stale-write / concurrency conflict mapping
```

This made the two supported combinations possible.

---

### Stage 3.5B PR6

PR6 introduced validation placement as configuration:

```text
ValidationPlacement.IN_TRANSACTION
ValidationPlacement.PRE_TRANSACTION
```

Accepted baseline examples:

```python
PostgresWriteSideConfig(
    validation_mode=ValidationMode.STRICT,
    validation_placement=ValidationPlacement.PRE_TRANSACTION,
    admission_strategy=AdmissionStrategy.OPTIMISTIC,
)
```

and:

```python
PostgresWriteSideConfig(
    validation_mode=ValidationMode.STRICT,
    validation_placement=ValidationPlacement.IN_TRANSACTION,
    admission_strategy=AdmissionStrategy.PESSIMISTIC,
)
```

The project should avoid presenting the rejected combinations as normal supported configurations.

---

## Non-Goals

This ADR does not implement:

```text
DAG node model
DAGValidationContext
validation placement policy engine
risk scoring
async audit pipeline
SemanticOutcome table
RuntimeDecision table
automatic placement selection
```

Those belong to later stages.

This ADR also does not claim that `PRE_TRANSACTION + OPTIMISTIC` is always better than `IN_TRANSACTION + PESSIMISTIC`, or the reverse.

The correct choice depends on risk, reversibility, contention, validation cost, and latency budget.

---

## Related Context

This ADR follows the implementation lesson recorded in:

- [From Durable Persistence to Semantic Gate Preservation](../postmortems/from_durable_persistence_to_semantic_gate_preservation.md)

That postmortem records how PostgreSQL persistence hardening initially risked preserving physical transaction correctness while bypassing the existing Compass Layer 1 semantic gate.

For the PR6 implementation boundary that follows from this ADR, see:

- [Validation Placement Strategy Boundary](../boundary_notes/validation_placement_strategy_boundary.md)
- [Pre-Transaction Read Cleanup Boundary](../postmortems/pre_transaction_read_cleanup_boundary.md)

---

## Related ADRs

- [ADR 0010 — Separate Transaction Atomicity from Concurrency Admission](0010_transaction_atomicity_vs_concurrency_admission.md)
- [ADR 0012 — Two-Phase Concurrency Admission for PostgreSQL Write-Side](0012_two_phase_concurrency_admission.md)

ADR 0010 separates transaction atomicity from concurrency admission.

ADR 0012 explains why pessimistic admission needs `prepare_stream(order_id)` before expensive read / validation work.

This ADR combines those lessons into the accepted validation placement matrix.

---

## Final Principle

Compass should not be treated as one fixed execution mode.

Compass should be treated as a semantic gate whose:

```text
strength
```

and:

```text
placement
```

can be configured based on risk, reversibility, latency budget, and consistency requirements.

However, only two placement / admission combinations are accepted as the Stage 3.5B baseline:

```text
PRE_TRANSACTION + OPTIMISTIC
IN_TRANSACTION  + PESSIMISTIC
```

The first optimizes for short transactions and accepts late stale-write rejection.

The second optimizes for protected validation under a stream lock and accepts longer transaction / lock duration.

The durable write-side should support both without rewriting the core storage, idempotency, validation, and admission boundaries.
