# PR1 — Unprotected Load Characterization Report

[← Back to Load / Capacity Protection](README.md)

```text
PR0 — COMPLETE
PR1 — COMPLETE / EVIDENCE COLLECTION CLOSED
PR2 — NOT STARTED
Capacity mechanism and numerical policy — NOT SELECTED
```

## 1. Purpose

PR1 collects and reports unprotected load-characterization evidence for the
current PostgreSQL writer. The research question is:

> For a fixed current writer composition and independent finite CREATE
> workload, when does increasing offered concurrent execution cease to
> improve acknowledged accepted-write throughput and predominantly
> increase waiting, latency, or failures?

This report closes PR1 using the two accepted runs below. It does not select a
safe operating limit, headroom, CapacityGate threshold, rate policy, or final
capacity-knee interpretation. Those remain PR2 or later responsibilities.

## 2. Environment / Provenance

The following facts agree across every cell in both raw evidence directories.

| Fact | Recorded value |
|---|---|
| Source commit | `0a68333f86307e96a42e736254b8e047a7284f5a` |
| Working-tree qualification | `tracked_clean;untracked_not_inspected` |
| Python | `3.12.7` |
| psycopg | `3.3.4` |
| PostgreSQL | `16.15` (`server_version` integer `160015`) |
| Platform / architecture | `Darwin` / `arm64` |
| Logical CPUs | `12` |
| Database | `compass_test` |
| Transaction isolation / autocommit | `read committed` / `false` on all recorded connections |
| Writer placement | `PRE_TRANSACTION` |
| Admission gate | `src.pipeline.transactional.postgres_admission.PostgresOptimisticAdmissionGate` (OCC) |
| Validation runtime | `src.compass.transition.runtime.ValidationRuntime` |
| Validation mode / validator | `strict` / `src.compass.transition.validators.FullProofValidator` |
| Connection topology | N distinct retained lane connections plus one distinct control/verification connection per cell |
| Clock | `time.monotonic_ns` |
| Evidence schema / method version | `1` / `pr1-unprotected-finite-load-v1` |

The source commit identifies the implementation that generated the evidence;
it does not include these generated files or this later report. The working-tree
qualification explicitly excludes inspection of untracked files. Server settings
such as `max_connections`, WAL settings, session occupancy, and host interference
are not fields of this recorded provenance; this report does not infer them.

### Raw evidence ownership

| Run | Exact directory / run ID | JSON files | File bytes | Allocated disk usage (`du -sh`) |
|---|---|---:|---:|---:|
| Exploratory | `experiments/load_capacity_protection/evidence/pr1-exploratory-20260906T041421533734Z-0a68333f8630/` | 36 | 277,951,460 | 265M |
| Refinement | `experiments/load_capacity_protection/evidence/pr1-refinement-20260906T042421699478Z-0a68333f8630/` | 30 | 231,490,047 | 221M |

These 66 files remain ignored generated experiment evidence, totaling
509,441,507 file bytes. The paths identify their current worktree locations;
availability in a fresh checkout requires a separately reviewed archival
decision. The compact tables and provenance here do not replace the raw
observations.

### Evidence publication model

```text
this report
→ compact 55-recorded-repetition CSV
→ evidence manifest
→ separately published raw ZIP archives
```

The repository tracks the
[recorded-repetition CSV](../../../experiments/load_capacity_protection/results/pr1_recorded_repetitions.csv)
and its [evidence manifest](../../../experiments/load_capacity_protection/results/pr1_evidence_manifest.json).
The CSV contains one raw-derived summary row for each recorded repetition;
warmups are excluded. The manifest identifies both source runs, the CSV, and
the intended archive filenames, byte sizes, and SHA-256 hashes.

The manifest identities and hashes define the exact raw archive publication
artifacts. Those ZIP archives are not claimed to be publicly available. Their
publication is a separate repository-release action, and reviewers need the
matching published archives for complete raw-evidence readback.

## 3. Experimental Method

The [accepted method](pr1_unprotected_characterization_method.md),
[runner](../../../experiments/load_capacity_protection/runner.py), and
[retained PostgreSQL lane composition](../../../experiments/load_capacity_protection/postgres_runtime.py)
define the execution boundary.

| Parameter | Exploratory | Refinement |
|---|---|---|
| Fixed K per cell/repetition | 512 | 512 |
| Concurrency order | `(1, 8, 2, 16, 4, 32)` | `(12, 8, 16, 10, 14)` |
| Warmups per level | 1 | 1 |
| Recorded repetitions per level | 5 | 5 |
| Workload ordering seed | 0 | 0 |
| Fixed amount | `10.00` | `10.00` |
| Declared peak connection budget | 33 (32 lanes + 1 control) | 17 (16 lanes + 1 control) |
| Connection-setup timeout | 10 seconds | 10 seconds |
| Stop policy | `stop_claims_and_drain_without_deadline` | `stop_claims_and_drain_without_deadline` |
| Cleanup policy | `delete_verified_cell_rows` | `delete_verified_cell_rows` |

Every item is CREATE with a fresh independent Order ID and unique Request ID.
All cells use PRE_TRANSACTION, OCC, and STRICT FullProof validation. The finite
closed-loop scheduler offers all K items at one boundary; persistent lanes
replenish after terminal observation without a global per-batch barrier.
Connections are prepared before release and retained across calls within a cell.

The runner executes the declared level order, with one warmup followed by five
recorded repetitions at each level. Seed 0 shuffles item order identically by
index across cells; it does not randomize cell order. Run/level/cohort/repetition
namespaces keep request and order identities distinct. Repetitions were grouped
by level, not interleaved or counterbalanced. No additional repetitions are
inferred from favorable outcomes.

After quiescence, durable verification and scoped cleanup run outside workload
timing. Cleanup deletes only the exact declared request/order pairs from
`idempotency_records` first, then `order_events`, and checks their absence.
There is no pre-run deletion, TRUNCATE, CASCADE, VACUUM, or sequence reset.
Global-position allocation is not reset; cache, WAL, and dead-tuple state are not
restored. The evidence records successful scoped cleanup, not a live database
inspection performed during this report.

### Calculation and cohort definition

All result tables exclude warmups. Each level has five whole-cell repetitions
and 512 observations per repetition (2,560 recorded requests per level).
Each table entry is the median of the five per-repetition statistics, calculated
before display rounding. Requests are not pooled to calculate a single percentile.

- Acknowledged accepted throughput per repetition is
  `512 × 1e9 / (max(terminal_observation_ns) - common offer_ns)`. It includes
  finite scheduling, ramp, and drain, but excludes setup, post-run verification,
  cleanup, and serialization.
- Writer-call latency is `writer_exit_ns - writer_entry_ns`.
- Scheduler wait is `dispatch_ns - offer_ns`, including the finite backlog.
- Phase samples use the named production measurement's `elapsed_ns` only when
  its state is `MEASURED`; absence is never converted to zero.
- For p50 and p95, sort each repetition's 512 samples as `x[0..511]` and use
  linear interpolation: `h = (512 - 1) × p`, `i = floor(h)`,
  `q(p) = x[i] + (h - i) × (x[min(i + 1, 511)] - x[i])`.
  This is the type-7 estimator. Take the median of the five resulting values.
- Overlap is derived from half-open `[writer_entry_ns, writer_exit_ns)`
  intervals. Every cell's maximum equals N, so its five-repetition median also
  equals N.

Throughput is displayed to two decimals; latency to three. Validation-runtime
latency is in microseconds; other timing columns are in milliseconds. No p99,
confidence interval, operating recommendation, or capacity threshold is derived.

## 4. Correctness / Evidence Integrity

All 66 files were decoded through the existing
[evidence reader](../../../experiments/load_capacity_protection/evidence.py).
Schema/method validation, immutable model invariants, and recomputed accounting
and overlap matched the stored summaries. Raw observations were additionally
checked for exact accepted-event and idempotency linkage.

| Check | Exploratory | Refinement |
|---|---:|---:|
| Recorded / warmup cells | 30 / 6 | 25 / 5 |
| Recorded acknowledged accepted requests | 15,360 | 12,800 |
| Warmup acknowledged accepted requests | 3,072 | 2,560 |
| All planned/offered/dispatched/entered/terminal/acknowledged accepted counts | 18,432 each | 15,360 each |
| Native request failures / harness failures / evidence problems | 0 / 0 / 0 | 0 / 0 / 0 |
| Residual work / unclosed writer intervals | 0 / 0 | 0 / 0 |
| Delivered production measurements | 18,432 | 15,360 |
| Successful durable verification | 18,432 | 15,360 |
| Cells with completed scoped cleanup | 36 / 36 | 30 / 30 |
| Cells with maximum writer-call overlap = configured N | 36 / 36 | 30 / 30 |

All 33,792 request IDs, order IDs, and accepted event IDs are distinct across
both runs, including warmups. Each planned item appears exactly once with normal
ACCEPTED return and acknowledged-accepted knowledge. Each has one matching
sequence-1 CREATED event, exact request/order/amount identity, and idempotency
readback resolving to that same signature and accepted event. There are no
duplicate accepted effects in the recorded verification evidence. Validation
reports STRICT, passed, and FullProofValidator throughout.

Within every cell, the recorded backend identities show N distinct lane
connections plus one distinct control connection. All writer intervals close;
the maximum application-call overlap reaches N. This proves observed writer-call
overlap, not physical PostgreSQL CPU concurrency or exact transaction overlap.
It does not prove sustained overlap at N throughout each cell.

## 5. Exploratory Results

Rows are sorted by N for comparison; execution order remains `(1, 8, 2, 16, 4, 32)`.
Values are five-recorded-repetition medians as defined in Section 3.

| N | Accepted writes/s | Writer p50 ms | Writer p95 ms | Scheduler wait p50 ms | Business UOW p50 ms | Append admission p50 ms | Commit finalization p50 ms | Validation runtime p50 µs | Max writer-call overlap |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 360.35 | 2.441 | 4.157 | 696.526 | 1.503 | 0.499 | 0.269 | 5.792 | 1 |
| 2 | 549.90 | 3.474 | 4.985 | 458.155 | 2.018 | 0.588 | 0.328 | 5.417 | 2 |
| 4 | 830.17 | 4.630 | 6.377 | 309.708 | 2.855 | 0.801 | 0.467 | 6.104 | 4 |
| 8 | 1147.71 | 6.660 | 9.016 | 217.928 | 4.069 | 1.245 | 0.750 | 6.875 | 8 |
| 16 | 1096.47 | 14.455 | 17.446 | 230.732 | 8.688 | 2.773 | 1.593 | 6.792 | 16 |
| 32 | 1100.17 | 28.479 | 35.406 | 221.378 | 16.923 | 5.386 | 2.806 | 6.834 | 32 |

## 6. Refinement Results

Rows are sorted by N for comparison; execution order remains `(12, 8, 16, 10, 14)`.
Values use the same cohort and estimator as Section 5.

| N | Accepted writes/s | Writer p50 ms | Writer p95 ms | Scheduler wait p50 ms | Business UOW p50 ms | Append admission p50 ms | Commit finalization p50 ms | Validation runtime p50 µs | Max writer-call overlap |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | 1120.96 | 6.892 | 9.141 | 230.268 | 4.260 | 1.268 | 0.825 | 7.792 | 8 |
| 10 | 1169.68 | 8.395 | 10.770 | 220.423 | 5.090 | 1.587 | 0.942 | 6.666 | 10 |
| 12 | 1121.37 | 10.488 | 13.206 | 230.118 | 6.362 | 2.022 | 1.206 | 6.917 | 12 |
| 14 | 1070.99 | 12.823 | 15.819 | 235.859 | 7.731 | 2.453 | 1.481 | 7.125 | 14 |
| 16 | 1027.18 | 14.682 | 18.690 | 240.972 | 8.896 | 2.850 | 1.644 | 6.979 | 16 |

## 7. Source-Grounded Findings

Useful acknowledged-write scaling improves through the tested low-concurrency
region: exploratory medians rise from 360.35 writes/s at N=1 to 1147.71 at N=8.
N=16 and N=32 do not improve that median, while writer-call p50 increases from
6.660 ms at N=8 to 14.455 ms and 28.479 ms respectively. N=32 is slightly higher
in throughput than N=16; exploratory evidence does not show a strictly monotonic
throughput decline beyond N=8.

The strongest observed median-throughput area is around N=8–10. Refinement's
highest median is 1169.68 writes/s at N=10. At N=12 it falls to 1121.37, then to
1070.99 at N=14 and 1027.18 at N=16, while writer-call and PostgreSQL-backed phase
latency rises. Median scheduler wait also rises from N=10 through N=16 in the
refinement, reflecting the finite offered backlog rather than production queue
growth.

As a descriptive comparison of these tested medians, refinement narrows the
observed degradation transition from the exploratory 8–16 bracket to
approximately the 10–12 region. This is not a statistically established change
point or a universal knee. Repetition variation, different run conditions over
time, and grouped execution order qualify the observation. No failures were
needed to observe this throughput/latency degradation, and no crash or
connection-refusal boundary was established.

These findings do not imply `production capacity = 10`, `safe limit = 10`, or
`limiter threshold = 10`. PR2 retains capacity-policy interpretation.

## 8. PostgreSQL-Backed Cost Attribution

Validation-runtime medians remain in a small microsecond band: 5.417–6.875 µs
across exploratory levels and 6.666–7.792 µs across refinement levels. They do
not show the millisecond growth seen in the writer/UOW phases. Approximately
stable here means relative to that larger growth, not constant cost.

For example, exploratory N=8 to N=32 increases business-UOW p50 from 4.069 to
16.923 ms, append-admission p50 from 1.245 to 5.386 ms, and commit-finalization
p50 from 0.750 to 2.806 ms. Refinement N=10 to N=16 increases the same medians
from 5.090 to 8.896 ms, 1.587 to 2.850 ms, and 0.942 to 1.644 ms.

Other measured database-backed phases show the same direction in refinement:

| N | Accepted history load p50 ms | Authoritative idempotency check p50 ms | Idempotency persistence p50 ms |
|---:|---:|---:|---:|
| 8 | 0.597 | 1.262 | 0.631 |
| 10 | 0.743 | 1.541 | 0.762 |
| 12 | 0.978 | 1.957 | 0.983 |
| 14 | 1.217 | 2.375 | 1.183 |
| 16 | 1.376 | 2.801 | 1.384 |

These are application-side elapsed intervals around PostgreSQL-backed work.
They include client execution, scheduling and waits; they are not server CPU,
I/O, lock-wait, or WAL attribution. Business UOW is an application UOW interval,
not exact physical transaction lifetime. Append admission includes persistence
and translation work, not isolated OCC or INSERT cost. The
[production phase boundaries](../../../src/pipeline/transactional/postgres_write_side_measurement_instrumentation.py)
remain authoritative. Phase intervals overlap and must not be summed as
independent cost components. Missing/non-applicable phases remain absent.

## 9. Run-to-Run Variation

The five acknowledged accepted throughput values below are in recorded
repetition order 0–4 for each level (writes/s). Warmups are excluded.

| Run | N | Rep 0 | Rep 1 | Rep 2 | Rep 3 | Rep 4 |
|---|---:|---:|---:|---:|---:|---:|
| Exploratory | 1 | 417.95 | 337.60 | 380.33 | 351.66 | 360.35 |
| Exploratory | 2 | 549.60 | 549.90 | 560.43 | 539.92 | 557.28 |
| Exploratory | 4 | 824.23 | 853.42 | 859.28 | 829.91 | 830.17 |
| Exploratory | 8 | 1069.09 | 1147.71 | 1147.09 | 1227.57 | 1214.37 |
| Exploratory | 16 | 1116.66 | 1048.07 | 1096.47 | 1090.53 | 1099.67 |
| Exploratory | 32 | 1079.04 | 981.69 | 1100.17 | 1126.28 | 1107.99 |
| Refinement | 8 | 1196.02 | 1174.24 | 927.44 | 1120.96 | 1008.36 |
| Refinement | 10 | 1156.73 | 1173.44 | 1169.68 | 1133.76 | 1182.25 |
| Refinement | 12 | 1121.37 | 1109.15 | 1126.16 | 1134.91 | 1064.75 |
| Refinement | 14 | 1082.35 | 1070.99 | 1104.64 | 1034.71 | 1065.31 |
| Refinement | 16 | 1027.18 | 1018.39 | 1054.81 | 985.02 | 1072.87 |

Refinement N=8 spans 927.44–1196.02 writes/s, illustrating why a median alone
does not establish an optimum. N=8 and N=16 medians also differ between the
two runs; those cohorts are kept separate. Requests within one repetition are
not independent statistical replicates, and sequential repetitions need not
be independent either. No confidence intervals or significance claims are made.

## 10. Limitations

- This is a local Darwin/arm64, 12-logical-CPU environment, not production
  capacity or a production SLA/SLO measurement.
- The workload is finite, closed loop, and independent CREATE only. It does not
  model PAY, hot streams, replay traffic, mixed business work, or semantic
  replanning.
- Retained connections exclude pool checkout and uncontrolled connection
  acquisition behavior. Setup timing is separate; this is not a connection
  ceiling experiment.
- Finite completion throughput does not establish sustained open-loop arrival
  RPS, burst tolerance, external queue growth, or backend service time. Scheduler
  wait and total outer latency include finite-experiment backlog.
- Logical row cleanup does not restore physical WAL/cache/dead-tuple/sequence
  state. Global-position allocation is not reset or required to be contiguous.
- Cell order is recorded but repetitions are grouped by level. Nonascending
  order reduces simple ascending order correspondence; it does not remove
  time/cache/bloat drift or counterbalance the runs. No host-interference trace
  establishes otherwise.
- Maximum writer-call overlap demonstrates application-call overlap only. It
  does not measure physical PostgreSQL CPU concurrency, exact transaction
  concurrency, time-weighted utilization, or a sustained middle plateau. Fixed
  K still includes ramp/drain (only 16 requests per lane on average at N=32).
- Python scheduling, measurement, and observation overhead remain possible
  contributors. No instrumentation-off comparison or server-internal resource
  trace proves a unique cause of the latency growth.
- The scheduler has no hard cancellation for a stuck writer. The connection
  setup timeout is not a writer deadline. No escaping failures occurred, so
  these runs do not characterize native-failure frequency or ambiguous commits
  under more severe conditions.
- The report retains compact aggregates; complete reinterpretation requires
  the generated raw evidence and its eventual archival availability.

These limitations qualify the accepted exploratory evidence; they are not
silently repaired by this report or by another load run. PR1 collection is closed.

## 11. PR1 Conclusion

PR1 established a reproducible unprotected PostgreSQL characterization and
observed a degradation transition in the tested fixture.

PR2 may now interpret that evidence for operating headroom / capacity policy.

PR1 is COMPLETE and evidence collection is closed. PR2 is NOT STARTED. No safe
operating limit, headroom selection, CapacityGate threshold, rate limiter, or
production capacity guarantee is selected here. Production source, experiment
mechanics, tests, Stage 4B.2 historical evidence, and semantic-replanning work
remain unchanged by this closeout. Report validation used read-only evidence
analysis; no PostgreSQL command or additional workload was executed.
