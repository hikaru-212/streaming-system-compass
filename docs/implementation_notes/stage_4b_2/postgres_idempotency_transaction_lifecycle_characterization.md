# Stage 4B.2 — PostgreSQL Idempotency and Transaction-Lifecycle Characterization

[← Back to Stage 4B.2](README.md)

## Status

```text
Post-PR6 supplemental characterization
!= reopening PR6

PR6 canonical comparison
= COMPLETE / CLOSED / UNCHANGED

Post-PR6 supplemental characterization
= COMPLETE / CLOSED

Supplement purpose
= explain which current production-path costs plausibly account for the
  recorded PRE/OCC accepted-path overhead

Dedicated path-E real-PostgreSQL correctness test
= IMPLEMENTED

Layer 1 supplemental characterization
= IMPLEMENTED / EXECUTED / VALID / EVIDENCE RECORDED

Layer 2 factorial characterization
= IMPLEMENTED / EXECUTED / VALID / EVIDENCE RECORDED

Layer 2 recorded source commit
= 9d2e4ac80cdf33b5dcd3638fa29ceb74d54bc8fd

Layer 2 evidence commit
= ba5224168802ed9b59c14fe0ff511d8af739d46a

Layer 3 methodology
= COMPLETE

Layer 3 runtime / tests / evidence
= IMPLEMENTED / EXECUTED / VALID / EVIDENCE RECORDED

Layer 3 recorded source commit
= b5e57f1b18eb8f484225d0dc745e9c9cc1f620aa

Layer 3 evidence commit
= 8b3c50c20068eb74279d8cee6770ac3af1fccac0

Counterfactuals
= DEFERRED / NOT REQUIRED FOR CLOSEOUT
```

This method defines separate post-PR6 explanatory characterization. It is not
part of the canonical PR6 evidence, does not alter the accepted PR6 report, and
does not reinterpret the canonical PR6 samples.

The completed evidence and bounded interpretation are recorded in the
[supplemental report](postgres_idempotency_transaction_lifecycle_report.md).

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

Layer 3 is the final planned explanatory control layer. Its responsibility is
limited to:

1. establishing an idle-cleanup baseline; and
2. characterizing one isolated PRE-like preliminary read-transaction
   lifecycle.

Layer 3 does not compare PRE and IN strategies, define a production
optimization, prove that preliminary idempotency should be removed, or alter
production semantics. It invokes current production read primitives but does
not create a new production composition.

### 8.1 `CONTROL_A_IDLE_ROLLBACK`

Initial state:

```text
PostgreSQL TransactionStatus.IDLE
```

No SQL statement is executed inside the measured control before rollback. The
only measured operation is:

```text
connection.rollback()
```

The control retains:

```text
status_before_cleanup = IDLE
status_after_cleanup  = IDLE
cleanup_elapsed_ns    = elapsed time of connection.rollback()
```

Its purpose is to measure the application/client cleanup-call baseline when no
PostgreSQL transaction is active. It is not an observation of active-transaction
rollback cost, PRE cleanup cost, total database cost, or business-UOW cost.

### 8.2 `CONTROL_B_PRELIMINARY_READ_LIFECYCLE`

Every sample begins with a fresh `request_id` and fresh `order_id` for which no
idempotency record or accepted event exists. The control uses the same
production `PostgresIdempotencyStore.check(...)` and
`PostgresEventStore.load(...)` read primitives used by the actual PRE path:

```text
TransactionStatus.IDLE
→ production PostgresIdempotencyStore.check(...)
→ IdempotencyVerdict.MISS
→ TransactionStatus.INTRANS
→ production PostgresEventStore.load(...) for the fresh order
→ accepted history = empty
→ TransactionStatus.INTRANS
→ direct connection.rollback()
→ TransactionStatus.IDLE
```

The history read is the actual accepted-history load, not `SELECT 1` or
synthetic SQL. No fake accepted event is inserted to manufacture the empty
history condition.

### 8.3 Measurement boundaries

`CONTROL_A_IDLE_ROLLBACK` directly measures only:

- `cleanup_elapsed_ns`: immediately before to immediately after the direct
  `connection.rollback()` call.

`CONTROL_B_PRELIMINARY_READ_LIFECYCLE` directly measures four independent
fields:

- `idempotency_check_elapsed_ns`: immediately before to immediately after the
  exact production `check(...)` call;
- `accepted_history_load_elapsed_ns`: immediately before to immediately after
  the exact production accepted-history `load(...)` call;
- `cleanup_elapsed_ns`: immediately before to immediately after the direct
  `connection.rollback()` call; and
- `lifecycle_elapsed_ns`: independently from immediately before the
  idempotency check until immediately after cleanup completes.

The three component timers are nested observations within the direct lifecycle
timer. `lifecycle_elapsed_ns` is not derived by adding them. The component
values are never summed or labeled as synthetic "database time"; their purpose
is to describe where elapsed time is observed within the directly timed
lifecycle.

All elapsed fields use `time.perf_counter_ns()` or the same injected monotonic
nanosecond clock seam. Wall-clock timestamps are not latency measurements.

### 8.4 Transaction-status and reuse evidence

`CONTROL_A_IDLE_ROLLBACK` retains:

```text
status_before_cleanup
status_after_cleanup

expected lifecycle
IDLE → IDLE
```

`CONTROL_B_PRELIMINARY_READ_LIFECYCLE` retains:

```text
status_before_check
status_after_check
status_after_history
status_after_cleanup

expected lifecycle
IDLE → INTRANS → INTRANS → IDLE
```

After the measured Control-B lifecycle, `SELECT 1` must succeed on the same
connection. That reuse verification is outside the lifecycle timer, and its
cleanup must restore the connection to `TransactionStatus.IDLE`. Any status or
reuse mismatch invalidates the sample and the run.

### 8.5 Fixed recorded schedule

The first Layer-3 recorded schedule is frozen as:

```text
30 rounds
× CONTROL_A_IDLE_ROLLBACK, CONTROL_B_PRELIMINARY_READ_LIFECYCLE
= 30 samples per control
= 60 recorded samples total
```

The declared order and count are fixed before PostgreSQL execution. There is no
adaptive extension, retry, replacement sample, or run-more-until-stable
behavior. A failed sample is retained as invalid evidence rather than replaced.

### 8.6 Identity and setup boundary

Identity generation, connection construction, store construction, database
reset or verification, and all other preparation occur outside measurement.
Each Control-B sample uses experiment-local unique identities and must prove
before timing that its request and order conditions are fresh:

```text
request_id has no idempotency record
order_id has no accepted event
```

The timed calls themselves must establish `MISS` and empty history. Setup may
not seed a fake event or execute substitute SQL inside the measured lifecycle.

### 8.7 Run validity and stop rule

A Layer-3 recorded run is valid only when all 60 planned samples execute exactly
once and satisfy their control-specific invariants.

For `CONTROL_A_IDLE_ROLLBACK`, every sample must:

- start in `IDLE`;
- execute no measured SQL before rollback;
- complete the direct rollback normally; and
- end in `IDLE`.

For `CONTROL_B_PRELIMINARY_READ_LIFECYCLE`, every sample must:

- start in `IDLE`;
- return exact `IdempotencyVerdict.MISS` from `check(...)`;
- be `INTRANS` after the check;
- return empty accepted history from `load(...)`;
- remain `INTRANS` after history;
- complete the direct rollback normally;
- be `IDLE` after cleanup;
- succeed at the post-measurement reuse `SELECT 1`; and
- return to `IDLE` after reuse verification.

Any unexpected ordinary exception, wrong count, wrong verdict, non-empty
history, lifecycle mismatch, reuse failure, or missing required observation
invalidates the complete run. Execution stops for human review. No sample is
retried or replaced.

### 8.8 Interpretation boundary

Layer 3 may report:

- the observed IDLE rollback baseline;
- the observed isolated PRE-like preliminary read lifecycle; and
- the elapsed time descriptively associated with its exact idempotency check,
  accepted-history load, and active read-transaction cleanup boundaries.

Those observations may be compared descriptively with the Layer-1 PRE
preliminary-read observations and the Layer-2 P-context check and cleanup
observations. Exact equality is not required across runs; environment and run
jitter remain expected.

Layer 3 must not claim:

- a causal percentage of the PR6 end-to-end difference;
- a synthetic total database time;
- a universal physical-transaction-start cost;
- PRE strategy inferiority or IN strategy superiority;
- safe removal of preliminary idempotency; or
- a production performance prediction.

### 8.9 Supplemental closeout rule

The post-PR6 supplemental investigation is sufficient to close if valid
Layer-3 evidence forms a coherent bounded explanation with Layers 1 and 2:

```text
observed PR6 environment
→ PRE accepted end-to-end elapsed was slightly higher
→ PRE application business-UOW elapsed was shorter
→ current PRE performs additional pre-UOW durable read-lifecycle work
→ Layer 2 shows that the exact idempotency check and its transaction context
  have non-negligible observed cost
→ Layer 3 directly characterizes the isolated PRE-like preliminary read
  lifecycle
```

Closure does not require a causal percentage-of-explanation threshold,
`PRE_NO_PRELIMINARY`, `IN_OCC`, or another strategy matrix. Those remain
optional future questions. Further characterization requires a specific
contradictory or unexplained observation and a separate human checkpoint.

The valid Layer-1, Layer-2, and Layer-3 evidence satisfies this rule. The
supplement is complete and closed; this method authorizes no further run.

### 8.10 Layer-3 evidence contract and recorded namespace

Layer-3 evidence uses this distinct supplemental namespace:

```text
experiments/stage4b2/evidence/
stage4b2-post-pr6-idempotency-read-lifecycle-layer3/<run_id>/
```

It publishes exactly:

```text
manifest.json
samples.jsonl
aggregates.json
```

The manifest retains only the supplemental schema name/version, run ID, full
source commit, clean-source fact, fixed control/sample schedule, clock identity,
sanitized PostgreSQL server version, and validation status. It does not retain
a DSN, endpoint, credential, database identity, or environment-variable value.

Sample records retain only the control identity and exact control-specific
timing, transaction-status, verdict/history, reuse, final-IDLE, and
exception-class facts required by this method. Exception messages and
connection identity are not evidence.

Aggregates remain separate by control and timing field and report only:

```text
count
min
mean
median
max
```

There is no p95, pooled control score, summed component metric, or strategy
ranking. This contract governed the completed valid Layer-3 run and does not
authorize another execution.

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

Any Layer-1/2/3 recorded run is invalid if:

- an unexpected exception occurs;
- any producer connection is not `IDLE` after normal finalization;
- durable event or idempotency-row invariants disagree with the expected path;
- a sample lands in a different A–H cell than planned;
- a required measurement is unavailable or has an unexpected phase state;
- structural SQL identity differs from current source expectations; or
- coordination work enters a boundary later claimed as uncontaminated cost.

## 11. Explicitly Deferred Counterfactuals

The following remain explicitly deferred after the valid Layers 1–3 evidence
and are not required for supplemental closeout:

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

## 12. Historical Initial Implementation Boundary

This section records the originally authorized first implementation slice. It
is historical chronology, not the current supplemental status reported at the
top of this document.

That first implementation slice contained only:

- this supplemental method document; and
- the dedicated real-PostgreSQL path-E correctness test.

At that checkpoint, it did not implement the full Layer-1 runner, the Layer-2
factorial, the Layer-3 timed controls, performance execution, aggregation,
serialization, or supplemental evidence persistence.
