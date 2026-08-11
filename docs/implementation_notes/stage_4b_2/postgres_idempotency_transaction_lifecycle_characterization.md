# Stage 4B.2 — PostgreSQL Idempotency and Transaction-Lifecycle Characterization

[← Back to Stage 4B.2](README.md)

## Status

```text
Post-PR6 supplemental characterization
!= reopening PR6

PR6
= COMPLETE

Supplement purpose
= explain which current production-path costs plausibly account for the
  recorded PRE/OCC accepted-path overhead

Supplemental method
= DEFINED

Dedicated path-E real-PostgreSQL correctness test
= IMPLEMENTED

Full Layer-1 measured runner
= NOT IMPLEMENTED

Layer-2 factorial runner
= NOT IMPLEMENTED

Layer-3 cleanup-control runner
= NOT IMPLEMENTED
```

This method is separate post-PR6 explanatory characterization. It is not part
of the canonical PR6 evidence, does not alter the accepted PR6 report, and does
not reinterpret the canonical PR6 samples.

No architecture change is authorized. In particular, this method does not
remove, bypass, conditionally disable, or reorder either current idempotency
check. It does not implement a shadow write algorithm or change current
production transaction ownership.

## 1. Responsibility and Boundary

The accepted PR6 evidence observed higher central external accepted-path cost
for the recorded PRE/OCC composition than for the recorded IN/pessimistic
composition. PR6 did not causally attribute that difference to validation
placement or to any one physical operation.

The source-supported explanatory hypothesis is narrower:

```text
PRE/OCC accepted path
= preliminary durable idempotency SELECT
+ accepted-history SELECT
+ rollback of the implicit preliminary read transaction
+ validation outside the business UOW
+ business UOW
+ authoritative idempotency SELECT
+ append / record / commit

IN/pessimistic accepted path
= one business UOW
+ authoritative idempotency SELECT
+ advisory try-lock
+ accepted-history SELECT
+ validation
+ append / record / commit
```

This supplement characterizes those existing paths before any counterfactual
algorithm is considered. It asks:

- which current operations are reached for MISS, REPLAY, and CONFLICT;
- how application-UOW and physical PostgreSQL transaction boundaries differ;
- what the exact production `PostgresIdempotencyStore.check()` call costs under
  matched connection contexts;
- what current rollback cleanup costs under bounded controls; and
- which observations plausibly explain the recorded PRE/OCC overhead without
  promoting correlation into causation.

This supplement does not perform load, capacity, saturation, worker-count,
retry, or strategy-selection characterization. Stage 4B.2 PR7 remains out of
scope.

## 2. Exact Current SQL Vocabulary

The following abbreviations apply only to this method:

| Abbreviation | Current operation |
|---|---|
| `I` | `PostgresIdempotencyStore.check(...)`: joined `SELECT` from `idempotency_records` and `order_events` by `request_id` |
| `H` | `PostgresEventStore.load(...)`: ordered accepted-history `SELECT` by `order_id` |
| `L` | Concrete pessimistic `SELECT pg_try_advisory_xact_lock(...)` |
| `S` | Event-store `SELECT COALESCE(MAX(sequence), 0)` by `order_id` |
| `E` | `INSERT INTO order_events (...)` |
| `R` | `INSERT INTO idempotency_records (...)` |
| `CM` | Caller/UOW `connection.commit()` finalization |
| `RB` | Caller/UOW `connection.rollback()` finalization |

`CM` and `RB` are connection finalization calls, not `cursor.execute(...)`
statements. `PostgresWriteSideUnitOfWork.__enter__()` does not issue `BEGIN`.
On the current non-autocommit connection, the first SQL statement lazily opens
the physical PostgreSQL transaction.

The PRE optimistic `prepare_stream(order_id)` call is reached on accepted and
late append paths but currently executes no SQL. The IN rows below refer to the
Stage 4B.2 measured composition using the current concrete PostgreSQL
pessimistic gate. IN REPLAY and CONFLICT terminate before gate construction, so
their database path is independent of the configured gate.

## 3. Exact A–H Production-Path Matrix

The current measurement field abbreviations are:

| Abbreviation | Exact measurement field |
|---|---|
| `W` | `producer_write_invocation` |
| `U` | `business_uow` |
| `V` | `validation_runtime_call` |
| `PI` | `preliminary_idempotency_check` |
| `PC` | `preliminary_read_cleanup` |
| `AI` | `authoritative_idempotency_check` |
| `MH` | `accepted_history_load` |
| `C` | `concurrency_preparation_call` |
| `ML` | `pessimistic_advisory_try_lock_call` |
| `A` | `append_admission_call` |
| `IR` | `idempotency_record_call` |
| `MCM` | `commit_finalization` |
| `MRB` | `rollback_finalization` |

Every available measurement snapshot contains all thirteen fields. `M` below
means `MEASURED` on a normal run with successful clock collection, `NA` means
`NOT_APPLICABLE`, and `NR` means `NOT_REACHED`.

### A — PRE preliminary MISS → ACCEPTED

```text
physical transaction 1, not UOW-owned
implicit transaction start at I
→ I = MISS
→ H
→ direct RB in the PRE finally block

no PostgreSQL transaction
→ aggregate and candidate construction
→ validation

physical transaction 2, application UOW-owned
UOW entry while connection is IDLE
→ implicit transaction start at I
→ I = MISS
→ optimistic preparation, no SQL
→ S
→ E
→ R
→ clean UOW exit CM
```

| History | Validation | Append | Record | Finalization |
|---:|---:|---:|---:|---|
| yes | yes | yes | yes | preliminary RB, then business CM |

```text
M  = W, U, V, PI, PC, AI, MH, C, A, IR, MCM
NA = ML
NR = MRB
```

### B — PRE preliminary REPLAY

```text
physical transaction 1, not UOW-owned
implicit transaction start at I
→ I = REPLAY
→ early return passes through finally
→ direct RB

business UOW is not reached
```

| History | Validation | Append | Record | Finalization |
|---:|---:|---:|---:|---|
| no | no | no | no | preliminary RB only |

```text
M  = W, PI, PC
NA = ML
NR = U, V, AI, MH, C, A, IR, MCM, MRB
```

### C — PRE preliminary CONFLICT

```text
physical transaction 1, not UOW-owned
implicit transaction start at I
→ I = CONFLICT
→ early return passes through finally
→ direct RB

business UOW is not reached
```

| History | Validation | Append | Record | Finalization |
|---:|---:|---:|---:|---|
| no | no | no | no | preliminary RB only |

```text
M  = W, PI, PC
NA = ML
NR = U, V, AI, MH, C, A, IR, MCM, MRB
```

B and C remain separate outcome cohorts even though their phase shapes match.

### D — PRE preliminary MISS → authoritative REPLAY

```text
physical transaction 1, not UOW-owned
implicit transaction start at I
→ I = MISS
→ H
→ direct RB

no PostgreSQL transaction
→ aggregate and candidate construction
→ validation = ALLOW

physical transaction 2, application UOW-owned
UOW entry while connection is IDLE
→ implicit transaction start at I
→ I = REPLAY
→ explicit UOW RB
→ no preparation, append, or record
```

| History | Validation | Append | Record | Finalization |
|---:|---:|---:|---:|---|
| yes | yes | no | no | preliminary RB, then business RB |

```text
M  = W, U, V, PI, PC, AI, MH, MRB
NA = ML
NR = C, A, IR, MCM
```

### E — PRE preliminary MISS → authoritative CONFLICT

```text
physical transaction 1, not UOW-owned
implicit transaction start at I
→ I = MISS
→ H
→ direct RB

no PostgreSQL transaction
→ aggregate and candidate construction
→ validation = ALLOW
→ a competing connection commits the same request_id with a different
  semantic fingerprint

physical transaction 2, application UOW-owned
UOW entry while connection is IDLE
→ implicit transaction start at I
→ I = CONFLICT
→ explicit UOW RB
→ no preparation, append, or record from the losing invocation
```

| History | Validation | Append | Record | Finalization |
|---:|---:|---:|---:|---|
| yes | yes | no | no | preliminary RB, then business RB |

```text
M  = W, U, V, PI, PC, AI, MH, MRB
NA = ML
NR = C, A, IR, MCM
```

D and E remain separate outcome cohorts even though their phase shapes match.

### F — IN authoritative MISS → ACCEPTED

```text
one application UOW-owned transaction
UOW entry while connection is IDLE
→ implicit physical transaction start at I
→ I = MISS
→ L = acquired
→ H
→ aggregate and candidate construction
→ validation
→ S
→ E
→ R
→ clean UOW exit CM
```

| History | Validation | Append | Record | Finalization |
|---:|---:|---:|---:|---|
| yes | yes | yes | yes | business CM |

```text
M  = W, U, V, AI, MH, C, ML, A, IR, MCM
NA = PI, PC
NR = MRB
```

### G — IN authoritative REPLAY

```text
one application UOW-owned transaction
UOW entry while connection is IDLE
→ implicit physical transaction start at I
→ I = REPLAY
→ explicit UOW RB
→ no gate construction, lock, history, validation, append, or record
```

| History | Validation | Append | Record | Finalization |
|---:|---:|---:|---:|---|
| no | no | no | no | business RB |

```text
M  = W, U, AI, MRB
NA = PI, PC
NR = V, MH, C, ML, A, IR, MCM
```

### H — IN authoritative CONFLICT

```text
one application UOW-owned transaction
UOW entry while connection is IDLE
→ implicit physical transaction start at I
→ I = CONFLICT
→ explicit UOW RB
→ no gate construction, lock, history, validation, append, or record
```

| History | Validation | Append | Record | Finalization |
|---:|---:|---:|---:|---|
| no | no | no | no | business RB |

```text
M  = W, U, AI, MRB
NA = PI, PC
NR = V, MH, C, ML, A, IR, MCM
```

G and H remain separate outcome cohorts even though their phase shapes match.

## 4. Three Characterization Layers

The first supplement contains exactly three production-topology layers:

```text
Layer 1
= A–H production-path correctness and measured characterization

Layer 2
= exact PostgresIdempotencyStore.check() context factorial

Layer 3
= transaction / cleanup controls
```

No counterfactual production algorithm belongs to Layers 1–3. Every production
call uses the current source with both PRE idempotency checks intact.

## 5. Layer 1 — A–H Real-PostgreSQL Method

### 5.1 Bounded sample schedule

The first full runner should use a small fixed schedule:

```text
correctness smoke
= 1 invocation per A–H cell before recorded timing

recorded measured characterization
= 10 recorded invocations per A–H cell

total recorded Layer-1 invocations
= 80
```

The schedule is fixed before execution. It does not extend adaptively in
response to observed values or cohort counts. Increasing the counts requires a
new human checkpoint; this first supplement is path and cost characterization,
not load testing.

Each recorded invocation uses fresh scenario-appropriate identities. Fixture
creation, competing-writer setup, database cleanup, connection preparation,
writer/runtime construction, and durable verification occur outside timing.
Where validation is reached, the comparison uses the current real
`FullProofValidator` pipeline and `STRICT` mode unless a correctness-only path
test explicitly identifies its deterministic test runtime.

### 5.2 Required evidence for every cell

Every A–H sample must retain:

- exact `PostgresWriteSideOutcome`;
- every exact `IdempotencyVerdict` paired with its lifecycle position:
  `PRELIMINARY` or `AUTHORITATIVE`;
- independently observed external elapsed time;
- all thirteen measurement phase states;
- an elapsed value for every phase expected to be `MEASURED` in its A–H row;
- final psycopg `TransactionStatus`;
- final durable `order_events` and `idempotency_records` invariants; and
- zero unexpected exceptions.

The required ordered idempotency observations are:

| Path | Lifecycle-position/verdict sequence |
|---|---|
| A | `PRELIMINARY/MISS`, `AUTHORITATIVE/MISS` |
| B | `PRELIMINARY/REPLAY` |
| C | `PRELIMINARY/CONFLICT` |
| D | `PRELIMINARY/MISS`, `AUTHORITATIVE/REPLAY` |
| E | `PRELIMINARY/MISS`, `AUTHORITATIVE/CONFLICT` |
| F | `AUTHORITATIVE/MISS` |
| G | `AUTHORITATIVE/REPLAY` |
| H | `AUTHORITATIVE/CONFLICT` |

An expected reached phase with no elapsed value invalidates its sample rather
than reducing the required evidence.

An expected typed non-accepted result is a normal cohort member. An unexpected
exception invalidates its sample and stops the run for review; it is not
converted into a latency cohort.

The final status requirement is:

```text
normal producer return
→ TransactionStatus.IDLE
→ SELECT 1 succeeds on the same connection
→ cleanup returns the connection to TransactionStatus.IDLE
```

### 5.3 Cohort separation and matched contrasts

Paths are never pooled. In particular, REPLAY and CONFLICT remain distinct even
when phase presence is identical. No single PRE score, IN score, or combined
strategy score is calculated.

The bounded matched contrasts are:

```text
A vs F
= existing MISS accepted compositions
= still multi-axis: placement, transaction topology, and admission differ

B vs G
= PRE early REPLAY vs IN UOW REPLAY

C vs H
= PRE early CONFLICT vs IN UOW CONFLICT

B vs D
= early versus late REPLAY cost

C vs E
= early versus late CONFLICT cost

D vs E
= late REPLAY versus late CONFLICT classification/materialization cost
```

These are descriptive matched contrasts, not architecture decisions.

### 5.4 Late-path coordination boundary

The dedicated D/E correctness arrangement may synchronously execute the
competing committed write from a test-owned validation callback. That proves
ordering without sleeps or production hooks, but the competing invocation then
occurs inside the outer validation call.

Therefore:

```text
synchronous callback correctness sample
→ valid path/topology evidence
→ invalid latency evidence for W or V
```

The full Layer-1 runner must keep orchestration/coordination outside every
claimed timed boundary or explicitly mark the affected external and validation
values as coordination-contaminated and refuse them from B-vs-D or C-vs-E cost
aggregation. It must not subtract overlapping production phases or invent an
"avoided work" value from one invocation.

## 6. Dedicated Path-E Correctness Method

The missing real-PostgreSQL path-E test uses two independent connections and
the existing test-owned deterministic validation callback boundary:

```text
losing PRE writer, connection A
→ preliminary I = MISS
→ H = empty
→ preliminary RB
→ candidate amount = 100.00
→ validation begins

validation callback, connection B
→ current production writer
→ same request_id and order_id
→ conflicting amount = 999.00
→ ACCEPTED
→ event + idempotency record commit
→ connection B is IDLE

losing PRE writer resumes
→ validation = ALLOW
→ business UOW reached
→ authoritative I = CONFLICT
→ explicit UOW RB
→ typed CONFLICT return
```

The callback is synchronous: connection B's accepted result and clean commit
return before connection A enters its business UOW. No thread scheduling,
sleep, polling interval, artificial delay, or production hook determines the
race.

The required assertions are:

- exact outer checkpoint order through authoritative idempotency and rollback;
- exact `PostgresWriteSideOutcome.CONFLICT` and
  `IdempotencyVerdict.CONFLICT`;
- ALLOW validation was reached;
- stream preparation and append admission were not reached;
- no losing-candidate event or idempotency record exists;
- the competing accepted event is the sole durable event;
- the competing fingerprint returns REPLAY and the losing fingerprint returns
  CONFLICT from durable idempotency memory;
- both producer connections finish their producer call in `IDLE`;
- connection A remains reusable with `SELECT 1`; and
- no exception is caught, translated, or otherwise changed by the test.

This test is correctness evidence only. It makes no elapsed-time claim.

## 7. Layer 2 — Exact `check()` 3×3 Factorial

Layer 2 invokes the exact production `PostgresIdempotencyStore.check()` method.
It does not copy its SQL, replace its row hydration, or construct verdicts in
the experiment.

### 7.1 Contexts

| Context | Exact starting boundary |
|---|---|
| `P` | PRE-style direct `check()` beginning from `TransactionStatus.IDLE` |
| `U` | `PostgresWriteSideUnitOfWork` entered, while the physical connection is still `TransactionStatus.IDLE` immediately before `check()` |
| `T` | UOW entered and one fixed untimed neutral `SELECT 1` has already moved the physical connection to `TransactionStatus.INTRANS` before `check()` |

`U` is not called an already-open PostgreSQL transaction. It is an entered
application UOW whose first idempotency SQL may itself open the physical
transaction. `T` is the actual pre-opened physical-transaction control and is
not the current production IN topology.

### 7.2 Verdict fixtures

The contexts cross with:

```text
MISS
REPLAY
CONFLICT
```

This produces exactly nine cells:

| Context | MISS | REPLAY | CONFLICT |
|---|---:|---:|---:|
| `P` | P-MISS | P-REPLAY | P-CONFLICT |
| `U` | U-MISS | U-REPLAY | U-CONFLICT |
| `T` | T-MISS | T-REPLAY | T-CONFLICT |

REPLAY fixtures contain a committed accepted event and matching idempotency
record. CONFLICT fixtures contain a committed record for the same `request_id`
with a different semantic fingerprint. MISS fixtures contain no record for the
sample request. All event/record seeding and verification occurs outside timing.

### 7.3 Required observations

Every cell eventually measures and records separately:

- exact typed verdict;
- `check()` elapsed;
- finalization elapsed;
- `TransactionStatus` immediately before `check()`;
- `TransactionStatus` immediately after `check()`;
- `TransactionStatus` immediately after cleanup; and
- SQL statement count and normalized statement identity in a separate
  low-observation structural run.

The structural SQL observer does not run in the primary cost samples. The T
cell's neutral transaction-opening statement is recorded as untimed setup and
is not counted as an idempotency-check statement.

Context and verdict execution order should be counterbalanced. Connections,
stores, UOWs, fixture rows, identifiers, and verification are prepared outside
the measured `check()` and cleanup boundaries.

## 8. Layer 3 — Transaction and Cleanup Controls

### Control 1 — IDLE rollback

```text
connection TransactionStatus.IDLE
→ connection.rollback()
→ assert TransactionStatus.IDLE
```

Purpose:

```text
estimate driver/no-active-transaction rollback behavior
```

This is not treated as the cost of rolling back an active PostgreSQL read
transaction.

### Control 2 — Actual PRE preliminary read bundle

```text
connection TransactionStatus.IDLE
→ I = MISS
→ assert TransactionStatus.INTRANS
→ H on an empty order stream
→ separately timed connection.rollback()
→ assert TransactionStatus.IDLE
```

Purpose:

```text
characterize the actual preliminary read bundle used by A, D, and E
```

Idempotency lookup, history loading, and cleanup retain separate boundaries.
The control does not combine their elapsed values into one inferred server-side
transaction cost.

## 9. Measurement Interpretation Rules

The supplement adopts the following mandatory rules:

1. `check()` timing includes driver/client work, SQL execution and round trip,
   row fetch, fingerprint comparison, and REPLAY/CONFLICT row/event
   materialization where applicable.
2. `check()` timing is not server-side SQL execution time.
3. `business_uow` is application UOW lifetime, not exact PostgreSQL server
   transaction duration.
4. Parent and child intervals overlap and are never added.
5. A slower first SQL statement does not by itself expose or quantify implicit
   physical `BEGIN` cost.
6. Transaction lifecycle, SQL round trip, row hydration, fingerprint
   classification, and rollback cleanup are not conflated without independent
   evidence.
7. `preliminary_read_cleanup` times the current rollback call; it does not by
   itself decompose driver, protocol, or server cleanup work.
8. REPLAY and CONFLICT remain separate cohorts even when they reach the same
   measurement phases.
9. Setup, seeding, verification, connection preparation, statement tracing,
   and deterministic coordination are excluded from cost claims.
10. All results remain local, source-specific, PostgreSQL-environment-qualified
    descriptive evidence.

## 10. Evidence Ownership and Run Validity

Supplemental evidence must use a new run identity and a separate evidence
directory. It must not append to or rewrite:

```text
experiments/stage4b2/evidence/stage4b2-pr6-canonical-0bd2f51/
```

The canonical PR6 report and evidence remain complete historical evidence.

A future Layer-1/2/3 recorded run is invalid if:

- an unexpected exception occurs;
- any producer connection is not `IDLE` after normal finalization;
- durable event or idempotency-row invariants disagree with the expected path;
- a sample lands in a different A–H cell than planned;
- a required measurement is unavailable or has an unexpected phase state;
- structural SQL identity differs from current source expectations; or
- coordination work enters a boundary later claimed as uncontaminated cost.

## 11. Explicitly Deferred Counterfactuals

The following are explicitly deferred until Layers 1–3 are implemented,
executed, and interpreted at a separate human checkpoint:

```text
PRE_NO_PRELIMINARY
= experiment-only shadow PRE/OCC implementation without preliminary
  idempotency classification

IN_OCC
= current IN_TRANSACTION algorithm with optimistic/OCC gate
```

A possible later four-way decomposition is:

```text
current PRE/OCC
vs
PRE/OCC without preliminary idempotency
vs
IN/OCC
vs
IN/pessimistic
```

This method does not authorize that comparison. No counterfactual production
algorithm, shadow implementation, gate cross-comparison, or check-removal
experiment is implemented in this supplement.

## 12. Initial Implementation Boundary

The first implementation slice contains only:

- this supplemental method document; and
- the dedicated real-PostgreSQL path-E correctness test.

It does not implement the full Layer-1 runner, the Layer-2 factorial, the
Layer-3 timed controls, performance execution, aggregation, serialization, or
supplemental evidence persistence.
