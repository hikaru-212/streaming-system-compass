# Stage 4B.2 — Controlled PostgreSQL Strategy Comparison Method

[← Back to Stage 4B.2](README.md)

## Status

```text
PR6
= COMPLETE

Comparison method
= DEFINED

Experiment infrastructure
= COMPLETE

Untimed preflight capability
= IMPLEMENTED

PostgreSQL preflight execution
= PASS

Preflight structural cells
= 6 / 6 PASS

Same-connection sequential reuse
= PASS

Frozen/current compatibility
= PASS

Canonical PRE/OCC compatibility
= PASS

Canonical IN/pessimistic compatibility
= PASS

Current measured availability
= PASS

Canonical PostgreSQL comparison
= COMPLETE / VALID

Recorded samples
= 450

Canonical evidence
= RECORDED

Empirical report
= COMPLETE
```

This note records the method used for the Stage 4B.2 PR6 controlled PostgreSQL
comparison. The resulting Level-B descriptive evidence is reported separately
in the [PostgreSQL Strategy Comparison Report](postgres_strategy_comparison_report.md).
This method does not choose a production strategy or claim universal
superiority for either composition.

## 1. Responsibility and Boundary

PR6 is Level-B descriptive evidence for these two current compositions:

```text
PRE_OCC
= PRE_TRANSACTION
+ current optimistic/OCC append-time admission

IN_PESSIMISTIC
= IN_TRANSACTION
+ current concrete PostgreSQL pessimistic admission
```

The comparison asks what each composition costs in one recorded, sanitized
environment; where measured cost is paid; how matched normal-return cohorts
differ; and whether measurement changes externally observed invocation time.
Measurement remains producer-specific, execution-local, in-memory evidence.
It is not a strategy decision, capacity policy, retry authorization, telemetry
system, or persistence contract.

PR6 does not change production behavior, populate receipt cost fields,
introduce `AttemptLog`, implement retry or automatic switching, define a rate
limit, or characterize saturation. PR7 owns worker-count variation and bounded
scaling characterization.

## 2. Exact Fair-Comparison Unit

One comparable unit is a normal-return public producer invocation with the
same:

- PostgreSQL instance, schema or migration identity, and isolation assumptions;
- canonical command and domain inputs;
- initial accepted-history depth and expected sequence;
- real `FullProofValidator` pipeline and `STRICT` validation mode;
- validation runtime, dispatcher, policy, and validator work;
- connection preparation and reuse policy;
- setup, warmup, cleanup, and verification exclusions;
- scenario schedule, stream distribution, and outcome cohort; and
- measured API surface when phase attribution is claimed, or unmeasured API
  surface when the low-observation control is claimed.

The primary Level-B phase-attributed unit is a matched
`CURRENT_MEASURED/PRE_OCC` and `CURRENT_MEASURED/IN_PESSIMISTIC` invocation.
The independent low-observation control matches
`CURRENT_UNMEASURED/PRE_OCC` against
`CURRENT_UNMEASURED/IN_PESSIMISTIC`. A frozen baseline is used only for the
observer-effect comparison described below.

Comparisons never pool different producer outcomes. A mean across accepted,
stale-write, and lock-non-acquisition results is not a strategy comparison.

## 3. Primary Workload

The primary command is `CREATE` with:

```text
amount
= Decimal("100.00")

initial accepted-history depth
= 0

expected accepted sequence
= 1

validation
= current real FullProofValidator pipeline

validation mode
= STRICT
```

Here `STRICT` means identity with the `ValidationMode.STRICT` enum member. Its
current serialized `Enum.value` remains lowercase `"strict"`; the preflight
does not require an uppercase serialized representation.

Fresh command identifiers and scenario-appropriate fresh stream identifiers
prevent replay from entering an accepted comparison. `PAY` is excluded from
the first comparison because it requires pre-existing accepted history and
would introduce history construction and depth as additional variables without
adding independent evidence needed by PR6.

## 4. Lifecycle Ownership

Each assigned lane and composition owns one persistent connection. That
connection is never shared concurrently, is returned to `IDLE` after every
invocation, and is reused sequentially by the surfaces assigned to the lane.
For Scenario A, one current writer and one frozen writer are constructed on the
same lane/composition connection:

```text
current writer
= one current PostgresTransactionalWriteSide
+ serves CURRENT_UNMEASURED
+ serves CURRENT_MEASURED through its measured public method

frozen writer
= one separate writer instance from the verified isolated historical module
+ serves FROZEN_BASELINE only
```

The current and frozen writers do not share a writer instance or writer class.
They may use separate validation runtime objects, and the accepted lifecycle
does so to avoid hidden cross-surface state. Their `FullProofValidator`,
`NoOpValidator`, dispatcher, policy, `ValidationRuntime`, and `STRICT` mode are
preconstructed before warmup and configuration-equivalent. Domain and input
work remain identical.

Current source makes this reuse safe: `PostgresTransactionalWriteSide` retains
the connection, validation runtime, admission-factory configuration, and
placement configuration, while the unit of work, admission gate, candidate,
result, and PR4 measurement recorder are invocation-local. The concrete
PostgreSQL pessimistic gate's prepared-order set is gate-local because the gate
is created for the invocation. `ValidationRuntime`, its dispatcher and policy,
and `FullProofValidator` retain configuration rather than producer-invocation
state. The frozen source has the same writer-level ownership shape.

The preferred Scenario-A observer policy is one connection per composition,
used sequentially by the frozen and current writers to reduce
connection-to-connection variance. Static source inspection is not sufficient
proof. The untimed preflight must execute frozen-to-current and
current-to-frozen sequences on fresh streams, prove `IDLE` after every call,
and prove `SELECT 1` reuse. Failure stops PR6 for human review; it must not
silently select separate frozen/current connections. B/C retain one distinct
connection per worker lane and never share a connection concurrently.

Writer, runtime, validator, or connection construction per timed sample is
therefore forbidden. If a future source change adds retained invocation-local
mutable state, the preflight must stop for human review rather than silently
changing this lifecycle.

## 5. Timer Boundaries

The experiment owns an independent `perf_counter_ns()` timer. It starts
immediately before exactly one public producer call. It stops immediately after
a normal return or, for an ordinary `Exception`, immediately when that
exception propagates to the experiment boundary. It excludes:

- barrier waiting and batch coordination;
- stream and command identifier generation;
- connection, writer, runtime, and validator construction;
- stream reset, seed data, connection preparation, and warmup;
- outcome classification and persistence verification;
- serialization, aggregation, and cleanup.

An ordinary invocation exception is externally timed raw invalid evidence. The
observation retains only `elapsed_ns` and the exception class name. It retains
no producer value, producer outcome, latency cohort, traceback, message, or
arbitrary representation. A measured invocation that raises has no normal PR4
measurement delivery, so `measurement_availability` and `phases` are JSON
`null`; it is not called `UNAVAILABLE`. `KeyboardInterrupt`, `SystemExit`, and
`GeneratorExit` are not caught. Exception samples make the run `INVALID_RUN`
and are refused by aggregation.

For concurrent batches, both workers pass the release barrier before their
external timer starts. `start_offset_ns` records each lane's timer start
relative to a batch-level reference; no universal skew threshold is defined.
Skew comparable to invocation duration is a methodological review condition in
the recorded environment.

PR4 internal measurement answers phase-attribution questions. Its thirteen
fields are retained individually:

```text
producer_write_invocation
business_uow
validation_runtime_call
preliminary_idempotency_check
preliminary_read_cleanup
authoritative_idempotency_check
accepted_history_load
concurrency_preparation_call
pessimistic_advisory_try_lock_call
append_admission_call
idempotency_record_call
commit_finalization
rollback_finalization
```

Each field retains its state and optional `elapsed_ns`. Parent and child
intervals overlap and must not be added. The external timer answers independent
end-to-end and observer-effect questions; the measurement module never proves
its own overhead.

## 6. Scenario A — Uncontended Accepted Baseline

Scenario A invokes `CREATE` on a fresh stream without a competing invocation.
Only `ACCEPTED` samples belong to the comparison cohort. Setup creates the
fresh identity and establishes connection state before timing; persistence
verification and cleanup occur after timing.

The recorded schedule contains 30 samples per surface per composition. For the
measured primary comparison this yields matched PRE and IN accepted samples.
The current-unmeasured surface supplies the low-observation control, and the
frozen surface participates only in observer-effect analysis.

## 7. Observer-Effect A/B/C Model

The observer-effect comparison is performed per composition with an external
experiment-owned timer:

```text
A = frozen pre-PR4 source
B = current PR4/PR5 unmeasured shared-code surface
C = current measured surface

B - A = inactive seam / recorder-absence branch tax
C - B = active collection cost
C - A = total observer effect
```

The three surfaces use all six execution permutations. Five seeded repetitions
of the permutation set produce 30 sequential samples per surface and
composition. Within matched rounds, PRE-first and IN-first order alternates.
This prevents one surface or composition from systematically receiving the
warmest execution position.

The frozen file is immutable historical evidence. Before a run, the loader
must verify the accepted provenance metadata, SHA-256, and Git blob identity,
then compile it under a unique experiment-only module name. It is loaded before
timing and never imported as the current production module. Any integrity,
compilation, isolated-load, or untimed PostgreSQL compatibility failure stops
the preflight. The baseline must never be patched or replaced with current code
while retaining the pre-PR4 label.

## 8. Scenario B — Same-Order Competition

Scenario B uses exactly two lanes and one fixed competition pattern. In each
batch both invocations use distinct command identifiers but target the same
fresh order at expected sequence 1. The release barrier creates an opportunity
for overlap and occurs outside both invocation timers.

Composition blocks alternate:

```text
PRE then IN
IN then PRE
```

Lane-to-connection assignment swaps on alternating batches. The recorded
protocol is exactly 30 two-worker batches per composition. It never varies
worker count and never searches for saturation.

Scenario B target rejection cohorts are observational. They are not guaranteed
by two-worker release:

- PRE targets `ACCEPTED` and a naturally observed append `STALE_WRITE`;
- IN targets `ACCEPTED` and a naturally observed preparation `LOCK_TIMEOUT`.

Scheduler interleaving can prevent either rejection. Unexpected late-domain
exceptions invalidate the block or run; they are not latency cohorts. A
required retained cohort below 20 samples after the fixed schedule yields
`INSUFFICIENT_EVIDENCE`.

```text
30 fixed batches
!= run until 20 rejection samples
```

There is no adaptive extension, automatic retry, or run-more policy.

## 9. Scenario C — Different-Order Concurrent Execution

Scenario C also uses exactly two lanes, but each lane targets a different fresh
order. Its purpose is a fixed concurrent independent-stream comparison, not a
worker-count study. It uses the same outside-timer release barrier, alternating
PRE/IN composition-block order, rotating lane-to-connection assignment, and
start-skew accounting as Scenario B.

The recorded protocol is exactly 30 two-worker batches per composition. The
retained comparison cohort is `ACCEPTED`; replay, conflict, unsupported normal
returns, measurement loss, or exceptions do not silently enter it.

## 10. Scenario E — Advisory Try-Lock Non-Acquisition

Scenario E is an IN-only mechanism-explanation case. Untimed setup holds the
target order's advisory transaction lock on a separate setup connection. The
timed public IN invocation uses the production concrete pessimistic admission
path and naturally returns preparation `LOCK_TIMEOUT` when its advisory
try-lock does not acquire. Lock release and cleanup occur after timing.

The recorded protocol is exactly 30 IN measured samples. It explains where
non-acquisition cost is paid; it is not a matched PRE/IN performance ranking.

## 11. D Is Derived, Not Scheduled

There is no Scenario D executor or schedule entry. D is only the derived
interpretation:

```text
Scenario B
+ PRE_OCC
+ producer outcome ADMISSION_REJECTED
+ rejection stage append
+ append verdict STALE_WRITE
```

It explains cost after PRE validation completed and append admission returned
stale. Production semantics are not changed to manufacture it.

## 12. Outcome Stratification

The retained PR6 cohorts are:

| Cohort | Producer outcome | Rejection stage | Stream verdict | Append verdict |
|---|---|---|---|---|
| `ACCEPTED` | `ACCEPTED` | none | `ADMITTED` | `ADMITTED` |
| `APPEND_STALE_WRITE` | `ADMISSION_REJECTED` | `append` | `ADMITTED` | `STALE_WRITE` |
| `PREPARE_LOCK_TIMEOUT` | `ADMISSION_REJECTED` | `prepare_stream` | `LOCK_TIMEOUT` | none |

The experiment classifier accepts only these exact combinations. Unexpected
exceptions have a separate marker and invalidate the run. Replay,
`VALIDATION_BLOCKED`, conflict, unavailable measurement, unsupported outcomes,
and inconsistent outcome/verdict combinations are not silently converted to
latency cohorts. A later separately justified extension could add another
typed cohort, but it could not pool it with these cohorts.

## 13. Fixed Protocol and Ordering

The current protocol defaults are experiment configuration, not repository
performance invariants:

| Part | Fixed default |
|---|---:|
| Sequential warmup | 5 cycles |
| Concurrent warmup | 3 batches per composition |
| Scenario A | 30 samples per surface per composition |
| Scenario B | 30 two-worker batches per composition |
| Scenario C | 30 two-worker batches per composition |
| Scenario E | 30 IN samples |
| Scenario B retained-core minimum | 20 samples |
| B/C worker count | exactly 2 |

Warmup uses the already-constructed lane lifecycle and is never serialized as
recorded evidence. The explicit schedule seed deterministically orders all six
observer permutations, alternates PRE-first and IN-first matched rounds,
alternates B/C composition-block order, and rotates lane/connection assignment.
Recorded sample indexes and block/batch/lane indexes are experiment accounting,
not runtime governance identities.

The recorded executor consumes the schedule once, exactly as fixed. It must
not append samples in response to observed cohort counts.

## 14. Raw Sample and Manifest Evidence

The canonical evidence layout is:

```text
manifest.json
samples.jsonl
aggregates.json
```

`samples.jsonl` contains exactly one deterministic JSON object per raw sample.
Each object carries the schema version, run and sample accounting, scenario,
composition, surface, command/history shape, outcome evidence, exact cohort,
measurement availability, external elapsed nanoseconds, concurrent start
offset, and optional phase map. Measured phase maps contain all thirteen PR3
fields as `{state, elapsed_ns}`. Frozen and current-unmeasured samples serialize
measurement availability and phases as JSON `null`.

For an ordinary invocation exception, `producer_outcome`, `cohort`,
`measurement_availability`, and `phases` are JSON `null`; `exception_type` is
the exception class name and `external_elapsed_ns` remains present. Schema
version 1 is the schema used by the first canonical real evidence. This shape
must not change without an explicit schema-version decision.

No `execution_id` or `attempt_id` is introduced. A real evidence directory may
be created only by a separately authorized, structurally valid PostgreSQL run;
the canonical directory was published only after validation returned `VALID`.

The sanitized manifest records source commit, whether the source tree was clean
before evidence generation, verified baseline identities, Python and psycopg
versions, sanitized platform and architecture, PostgreSQL server version when
available after preflight, topology label, schema/migration identity, isolation
and autocommit assumptions, connection arrangement, validator/runtime/mode,
workload shape, timer, counts, seed, ordering, fixed worker count, and stop
rules.

It must not record a DSN, environment-variable value, database name, host,
port, hostname, username, password, or credential. The field
`source_tree_clean_before_run` is deliberately temporal: generated evidence may
make the tree dirty after that fact is captured.

## 15. Aggregation

Default descriptive groups include the exact run, scenario, surface,
composition, command, initial history depth, expected sequence, and cohort.
Each elapsed field retains:

```text
count
min_ns
max_ns
mean_ns
median_ns
```

No p95 is produced by default. No latency threshold, pass/fail performance
claim, capacity inference, or universal production conclusion is defined.
Internal phases are aggregated separately and never summed. Matched sequential
PRE/IN rounds additionally support paired mean and median differences, with the
sign declared as `IN_PESSIMISTIC - PRE_OCC`; the difference remains descriptive
evidence from the recorded environment, not a strategy decision.

## 16. Validation and Stop Conditions

Pure accounting validation rejects missing or duplicate samples, incomplete
matched blocks, exception markers, unavailable required measured evidence,
unexpected `NOT_COLLECTED` required phases, unbalanced composition schedules,
invalid worker count, unexpected sample-plan identities, and recorded counts
beyond the fixed protocol. Start offsets are structurally retained for B/C,
without inventing a universal skew threshold.

`INVALID_RUN` is distinct from `INSUFFICIENT_EVIDENCE`. The latter is used when
the fixed Scenario B run completes coherently but a required observational
cohort remains below its accepted minimum. Neither status authorizes more
samples automatically.

The preflight or run stops for human review if:

- baseline integrity or isolated loading fails;
- the frozen source cannot execute credibly against current dependencies;
- lifecycle, validation, domain work, or workload equivalence cannot be held;
- setup, barrier coordination, verification, or cleanup enters timed scope;
- connection state or connection reuse cannot be made equivalent;
- measured evidence loses a required phase;
- outcome cohorts would need to be mixed;
- concurrency coordination or start skew dominates the claimed producer cost;
- an unexpected late-domain exception occurs;
- fixed B cohorts are insufficient after the recorded schedule;
- production algorithms, PR3/PR4/PR5 contracts, migrations, or dependencies
  would need to change; or
- the method begins varying worker count, extending by outcome, searching for
  saturation, or otherwise becoming PR7.

## 17. Untimed PostgreSQL Preflight

The guarded preflight is a compatibility check, not a benchmark. It uses only
the inherited `TEST_DATABASE_URL`, refuses a connected database whose name does
not end in `_test`, and never prints or serializes connection metadata. It
performs exactly six untimed accepted CREATE calls:

```text
FROZEN_BASELINE      × PRE_OCC
CURRENT_UNMEASURED   × PRE_OCC
CURRENT_MEASURED     × PRE_OCC
FROZEN_BASELINE      × IN_PESSIMISTIC
CURRENT_UNMEASURED   × IN_PESSIMISTIC
CURRENT_MEASURED     × IN_PESSIMISTIC
```

Each cell uses a fresh request/order, amount `Decimal("100.00")`, empty history,
expected sequence 1, the real configuration-equivalent STRICT validation
stack, and the exact current optimistic or concrete pessimistic gate. It
verifies accepted result shape, durable event persistence, connection `IDLE`,
post-call `SELECT 1`, reuse by the next surface, frozen namespace identity, and
AVAILABLE current measurement shape where applicable.

The preflight performs no timing, warmup, concurrency, evidence serialization,
aggregation, cleanup truncation, latency comparison, or recorded protocol. If
the current process lacks `TEST_DATABASE_URL`, the capability remains ready but
execution is reported as not executed rather than treated as an implementation
failure.

From an already configured project shell, the exact preflight command is:

```bash
./.venv/bin/python -m experiments.stage4b2.postgres_strategy_comparison --preflight
```

### Recorded preflight evidence

The guarded six-cell preflight has now executed successfully against the
configured project test database.

```text
FROZEN_BASELINE    × PRE_OCC         = PASS
CURRENT_UNMEASURED × PRE_OCC         = PASS
CURRENT_MEASURED   × PRE_OCC         = PASS

CURRENT_UNMEASURED × IN_PESSIMISTIC  = PASS
CURRENT_MEASURED   × IN_PESSIMISTIC  = PASS
FROZEN_BASELINE    × IN_PESSIMISTIC  = PASS
```

The run established:

```text
same_connection_sequential_reuse
= PASS

frozen_current_compatible
= PASS

canonical_pre_compatible
= PASS

canonical_in_pessimistic_compatible
= PASS

current_measured_available
= PASS
```

Every cell returned `ACCEPTED`, persisted the expected sequence-one CREATE
event, returned its connection to `IDLE`, and remained reusable through
`SELECT 1`. Frozen cells verified the isolated historical baseline identity;
current measured cells returned `AVAILABLE` measurement evidence.

This preflight is compatibility evidence only. It establishes that the accepted
PR6 comparison surfaces and lifecycle can execute credibly against real
PostgreSQL. It does not establish any latency ranking or performance result.

### Final validation record

PR6 completed the following validation and recorded execution:

```text
focused PR6 deterministic experiment tests
= 79 passed

complete unit suite
= 1163 passed

untimed PostgreSQL preflight
= PASS

real PostgreSQL executor smoke
= VALID

canonical recorded samples
= 450

canonical run validation
= VALID

exception samples
= 0

current measured delivery
= 330 / 330 AVAILABLE
```

PR6 is `COMPLETE`. The canonical evidence is recorded under
`experiments/stage4b2/evidence/stage4b2-pr6-canonical-0bd2f51/`; the accepted
interpretation and limitations are in the [PostgreSQL Strategy Comparison
Report](postgres_strategy_comparison_report.md). The recorded result remains
Level-B descriptive evidence and does not select a production strategy.
