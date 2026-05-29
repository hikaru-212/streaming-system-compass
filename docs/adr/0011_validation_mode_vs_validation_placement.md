# ADR 0011: Separate Validation Mode from Validation Placement Strategy

[← Back to ADR Index](README.md)

## Status

Proposed

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

Both execution models still require an append-time concurrency admission boundary to reject stale or competing writers.

In this ADR, append-time concurrency admission means checking, at the moment a candidate event attempts to enter accepted history, whether the writer is still allowed to occupy the next stream position.

This distinction matters because the project now has two legitimate validation placement models.

### 1. In-transaction Compass validation + append-time concurrency admission

```text
BEGIN
→ load durable accepted history
→ rehydrate aggregate
→ create candidate event
→ run Compass validation
→ run append-time concurrency admission / expected_version check
→ append accepted event
→ record idempotency result
→ COMMIT
```

This keeps Compass validation inside the same transactional write-side flow.

It provides a high-defense baseline because the candidate event is validated before accepted history is mutated in the same write-side transaction.

However, it still requires append-time concurrency admission to reject stale writers or competing writers.

In other words:

```text
in-transaction validation
≠
concurrency safety by itself
```

Concurrency safety still belongs to the admission boundary defined separately from transaction atomicity.

### 2. Pre-transaction Compass validation + append-time concurrency admission

```text
load accepted history
→ rehydrate aggregate
→ create candidate event
→ run Compass validation

BEGIN
→ run append-time concurrency admission / expected_version check
→ append accepted event
→ record idempotency result
→ COMMIT
```

This keeps the database transaction shorter.

Because validation happens before the transaction, append-time concurrency admission becomes mandatory to verify that the validated base version is still current.

Without this admission step, the flow would have a TOCTOU risk:

```text
the candidate was valid when checked
but the accepted history changed before append
```

The first model provides stronger semantic coupling at the cost of a longer transaction.

The second model provides a shorter transaction, but relies more explicitly on PR5-style append-time concurrency admission.

The difference between the two models is not whether concurrency control exists.

The difference is where Compass validation runs relative to the transaction boundary.

This discussion also clarified a future direction for DAG / agent workflows:

```text
Not every node needs the same validation placement or validation strength.
```

High-risk or irreversible nodes may require strict in-transaction validation.

Lower-risk, reversible, or compensatable nodes may use pre-transaction validation with optimistic concurrency control, partial validation, or asynchronous audit.

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

### ValidationMode

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

### ValidationPlacement

`ValidationPlacement` describes where validation occurs relative to the transaction boundary.

Future planned values:

```text
IN_TRANSACTION
PRE_TRANSACTION
ASYNC_AUDIT
```

### ConcurrencyAdmission

`ConcurrencyAdmission` describes how the system handles competing writers.

Future planned strategies may include:

```text
OPTIMISTIC
PESSIMISTIC
```

This ADR does not implement concurrency admission.

It explicitly depends on ADR 0010 for the separation between transaction atomicity and concurrency admission.

---

## Current PR4 Scope

Stage 3.5B PR4 keeps the PostgreSQL-backed write-side flow as the **in-transaction validation baseline**.

That means:

```text
Compass Layer 1 validation participates in the transactional write-side flow.
Only ALLOW can append accepted history and record idempotency.
BLOCK rolls back without mutating durable accepted history or idempotency memory.
```

However, PR4 should not be interpreted as solving full concurrent writer admission.

PR4 provides:

```text
transaction atomicity
+ in-transaction validation placement
```

PR5 is still needed for:

```text
explicit PostgreSQL-backed concurrency admission
+ stale writer rejection
+ stable admission results
```

PR4 may still use the current append path and expected-version behavior as a minimal transactional baseline.

PR5 is responsible for turning append-time expected-version behavior into an explicit PostgreSQL admission boundary with stable application-level results.

---

## PR5 Dependency

Pre-transaction validation is not safe without append-time concurrency admission.

Therefore, before implementing a pre-transaction validation flow, the project should first complete PR5:

```text
PostgreSQL-backed concurrency admission boundary
```

PR5 should provide:

```text
storage-level stale write / concurrency admission errors
optimistic PostgreSQL admission gate
pessimistic PostgreSQL admission gate
stable admission results
tests proving only one writer occupies the next stream position
```

Only after that can the project safely support:

```text
PRE_TRANSACTION validation + append-time concurrency admission / OCC
```

---

## Future Validation Placement Strategy

After PR5, the project may introduce a write-side configuration / factory such as:

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

This allows the system to switch between validation placement strategies without rewriting the storage layer.

The goal is not to create unrelated write-side implementations.

The goal is to share:

```text
PostgresEventStore
PostgresIdempotencyStore
PostgresWriteSideUnitOfWork
ValidationRuntime
OrderAggregate
ValidationContext construction
AdmissionGate
PostgresWriteSideResult
```

while allowing different orchestration strategies.

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

It may also run partial validation before a transaction:

```text
PARTIAL + PRE_TRANSACTION
```

or no semantic validation for benchmarking / baseline comparison:

```text
OFF + IN_TRANSACTION
OFF + PRE_TRANSACTION
```

Treating validation strength and validation placement as separate concepts prevents confusion.

---

### 2. Validation placement and concurrency admission are also independent

Moving validation inside a transaction does not automatically make the system concurrency-safe.

A transaction can protect related writes from partial persistence.

It does not by itself decide which writer should be admitted when multiple writers compete for the same aggregate stream.

That question belongs to concurrency admission.

This ADR therefore depends on the boundary established by ADR 0010:

```text
transaction atomicity
≠
concurrency admission
```

This ADR adds another separation:

```text
validation placement
≠
concurrency admission
```

---

### 3. In-transaction validation is the safest semantic baseline

In-transaction validation ensures that candidate event validation and accepted-history mutation are tightly coupled.

This is appropriate for:

```text
irreversible operations
payments
settlement
core ledger transitions
high-value state mutations
critical DAG checkpoints
```

The trade-off is increased transaction duration.

It still needs append-time concurrency admission once concurrent writer safety becomes part of the durable baseline.

---

### 4. Pre-transaction validation is a valid high-throughput strategy only with OCC

Pre-transaction validation keeps the transaction short.

However, validation and append are separated in time.

Therefore, append-time concurrency admission must verify that the validated base version is still current.

Without PR5-style concurrency admission, pre-transaction validation has a TOCTOU risk:

```text
validated state may no longer be current at write time
```

---

### 5. Validation placement enables latency and safety experimentation

Separating validation placement from validation mode also creates a measurable architecture boundary.

The project should eventually be able to compare different write-side execution strategies under the same domain scenario:

```text
STRICT + IN_TRANSACTION
STRICT + PRE_TRANSACTION + append-time concurrency admission
OFF + append-time concurrency admission
```

This makes it possible to measure:

- validation latency
- transaction duration
- retry frequency
- stale-write rejection rate
- lock contention
- throughput impact
- semantic safety trade-offs

The goal is not to prove that one placement is always better.

The goal is to allow the system to choose the appropriate validation placement based on risk, reversibility, contention level, and latency budget.

For example:

```text
high-risk / irreversible operation
→ prefer STRICT + IN_TRANSACTION

high-throughput / compensatable operation
→ prefer PRE_TRANSACTION + append-time concurrency admission

baseline benchmark
→ use OFF mode with the same admission boundary
```

This keeps Compass from becoming a fixed execution pattern.

Instead, Compass becomes a configurable semantic gate whose cost and protection level can be measured.

---

### 6. DAG / agent workflows need selective validation placement

Future agent or DAG pipelines may contain multiple nodes:

```text
node1 → node2 → node3 → node4 → node5 → node6
```

It may be unnecessary or too expensive to run strict in-transaction validation at every node.

A more scalable model is selective semantic gate placement:

```text
high-risk / irreversible nodes:
    STRICT + IN_TRANSACTION

medium-risk nodes:
    STRICT or PARTIAL + PRE_TRANSACTION + OCC

low-risk / reversible nodes:
    LOW or OFF + OCC or async audit

observability-only nodes:
    OFF or ASYNC_AUDIT
```

This preserves Compass as a semantic governance mechanism while allowing performance-aware deployment.

---

## Consequences

### Positive

- Clarifies the difference between validation strength and validation placement.
- Keeps validation placement separate from concurrency admission.
- Preserves PR4 as a strong correctness baseline without overstating concurrency guarantees.
- Makes PR5 more meaningful because OCC is required for safe pre-transaction validation.
- Enables future latency, retry, lock-contention, and throughput comparisons between validation placements under identical domain scenarios.
- Enables future comparisons between:
  - in-transaction Compass validation
  - pre-transaction Compass validation + append-time concurrency admission
  - validation-off baseline with the same admission boundary
- Supports future DAG / agent governance where only selected nodes require strict semantic gates.
- Avoids hard-coding one validation execution model as the only possible Compass architecture.

### Negative / Trade-offs

- Adds another architectural dimension that must be documented carefully.
- Future write-side orchestration may require multiple strategy implementations.
- A factory / config layer may be needed to avoid scattering placement-specific conditionals.
- The guarantees of each placement mode must be documented clearly.
- Pre-transaction validation requires robust concurrency admission before it can be considered safe.
- The project must avoid implying that in-transaction validation alone solves concurrent writer admission.

---

## Implementation Direction

### Stage 3.5B PR4

Keep the current implementation as:

```text
IN_TRANSACTION validation baseline
```

PR4 should focus on:

```text
PostgresWriteSideUnitOfWork
PostgresTransactionalWriteSide
Compass Layer 1 participation
append + idempotency atomicity
rollback on validation block
```

PR4 should not claim to complete:

```text
PostgreSQL concurrency admission
```

That belongs to PR5.

---

### Stage 3.5B PR5

Implement:

```text
PostgreSQL concurrency admission boundary
```

including:

```text
PostgresOptimisticAdmissionGate
PostgresPessimisticAdmissionGate
StaleWrite / concurrency conflict mapping
integration tests with multiple writers or simulated stale reads
```

This makes both in-transaction validation and pre-transaction validation safer under concurrent writers.

---

### Future PR / Stage 4 Prelude

Introduce validation placement strategy:

```text
ValidationPlacement.IN_TRANSACTION
ValidationPlacement.PRE_TRANSACTION
ValidationPlacement.ASYNC_AUDIT
```

Potential new files:

```text
src/pipeline/transactional/postgres_write_side_config.py
src/pipeline/transactional/postgres_write_side_factory.py
src/pipeline/transactional/postgres_prevalidated_write_side.py
```

Potential abstraction:

```python
class WriteSideFlow(Protocol):
    def create_order(...):
        ...

    def pay_order(...):
        ...
```

Potential implementations:

```text
InTransactionCompassWriteSide
PreTransactionCompassWriteSide
```

Both should share common stores, validation runtime, aggregate logic, result types, and admission gates.

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
PostgreSQL concurrency admission
```

Those belong to later stages.

This ADR also does not change the current PR4 implementation.

It records the architectural distinction and future implementation direction.

---

## Related Context

This ADR follows the implementation lesson recorded in:

- [From Durable Persistence to Semantic Gate Preservation](../postmortems/from_durable_persistence_to_semantic_gate_preservation.md)

That postmortem records how PostgreSQL persistence hardening initially risked preserving physical transaction correctness while bypassing the existing Compass Layer 1 semantic gate.

This ADR formalizes the follow-up design distinction between validation strength and validation placement.

---

## Related ADRs

- [ADR 0010 — Separate Transaction Atomicity from Concurrency Admission](0010_transaction_atomicity_vs_concurrency_admission.md)

ADR 0010 separates transaction atomicity from concurrency admission.

This ADR applies the same boundary-first reasoning to Compass validation by separating validation strength from validation placement, while also making clear that validation placement does not replace concurrency admission.

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

However, validation placement is not concurrency admission.

The durable write-side should eventually support both:

```text
high-defense semantic correctness
```

and:

```text
performance-aware validation placement
```

without rewriting the core storage, idempotency, and admission boundaries.
