# PR5 — Retry / Refusal Amplification Characterization Report

[← Back to Load / Capacity Protection](README.md)

```text
PR0–PR4 — COMPLETE
PR5 — COMPLETE / EVIDENCE COLLECTION CLOSED
Closeout package — internally verified; ready for human review
Raw archive publication — not_published
Next — ADR / architecture interpretation, separately authorized
```

## 1. Purpose

Can the PostgreSQL writer remain protected by bounded occupancy while caller
retry behavior amplifies attempts and pressure outside that protected region?

The [PR1 report](pr1_unprotected_characterization_report.md) supplies unprotected
degradation evidence. The [PR4 report](pr4_protected_vs_unprotected_report.md)
establishes occupancy protection and rapid refusal displacement without retries.
This report closes PR5 using the accepted run below, comparing experiment-owned
caller reactions under the same protected composition and committed source.

```text
logical request != execution attempt
resource-occupancy protection != retry / arrival-pressure protection
experiment retry != production retry authority
```

## 2. Environment / Provenance

All raw cells agree on the following recorded facts. No new database inspection
or environment-variable access was performed for this closeout.

| Fact | Recorded value |
|---|---|
| Source commit | `5084b12a177db4bdebd9dfad5597fe229677ed15` |
| Run ID | `pr5-retry-amplification-20260910T235547117546Z-5084b12a177d` |
| Working-tree qualification | tracked_clean;untracked_not_inspected |
| Python / psycopg | 3.12.7 / 3.3.4 |
| PostgreSQL / database | 16.15 (160015) / compass_test |
| Platform / architecture / logical CPUs | Darwin / arm64 / 12 |
| Isolation / autocommit | read committed / false |
| Writer / concurrency admission | PRE_TRANSACTION / PostgresOptimisticAdmissionGate (OCC) |
| Validation runtime / mode / validator | ValidationRuntime / strict / FullProofValidator |
| Validation policy | src.compass.transition.runtime.ValidationPolicy |
| Clock | time.monotonic_ns |
| Evidence schema / method | 1 / pr5-retry-refusal-amplification-v1 |
| Topology | 32 distinct retained lane connections plus one distinct control connection per cell |

Source identifies the generating implementation, not this later closeout.
The manifest records full composition names. No credentials, DSNs, raw provider
messages or hostnames are retained. Database settings beyond recorded facts and
host interference were not independently measured.

## 3. Experiment Method

The [PR5 method](pr5_retry_refusal_amplification_method.md),
[model](../../../experiments/load_capacity_protection/pr5_model.py),
[scheduler](../../../experiments/load_capacity_protection/pr5_characterization.py),
[runner](../../../experiments/load_capacity_protection/pr5_runner.py) and
[PostgreSQL adapter](../../../experiments/load_capacity_protection/pr5_postgres_runtime.py)
define the accepted execution. The method's pre-run status remains historical;
this report and current navigation own closeout status.

| Parameter | Recorded value |
|---|---|
| Logical workload / amount | K=128 independent CREATEs / Decimal("10.00") |
| Offered concurrency / shared real writer bound | N=32 / 8 |
| NO_RETRY attempt limit | 1, including first attempt |
| Retry-enabled attempt limit | 8, including first attempt |
| FIXED_BACKOFF | 5 ms |
| EXPONENTIAL_BACKOFF | base 1 ms; cap 8 ms |
| EXPONENTIAL_BACKOFF_WITH_JITTER | base 1 ms; cap 8 ms; additive jitter maximum 4 ms; seed 0 |
| Warmups / recorded repetitions | 1 / 5 per policy |
| Workload ordering seed | 0 |
| Policy ordering | rotating_policy_blocks |
| Connection budget / setup timeout | 33 / 10 seconds |
| Stop policy | stop_claims_and_drain_without_deadline |
| Cleanup policy | delete_verified_cell_rows; exact verified accepted identities only |

Exponential delay after refused attempt a is min(cap, base × 2^(a−1)).
Jitter uses `sha256-ascii-seed:index:attempt-mod-span-plus-one-v1`: hash ASCII
`seed:logical_request_index:attempt_index`, interpret the digest as an unsigned
big-endian integer, reduce modulo jitter_max_ns+1, then add to capped exponential
delay. The cap precedes jitter, so the largest configured scheduled delay is
12 ms. Actual dispatch can occur later. No system randomness or adaptive tuning
is inferred.

The initial policy order is NO_RETRY, IMMEDIATE_RETRY, FIXED_BACKOFF,
EXPONENTIAL_BACKOFF, EXPONENTIAL_BACKOFF_WITH_JITTER. Execution indices 0–4 are
warmups. Recorded indices 5–29 rotate the policy tuple left by repetition modulo
five, independently of warmup rotation. Each policy occupies each recorded
position once. Exact order remains in every raw file and the manifest. This is
position counterbalancing, not complete carryover balancing.

All logical requests are offered together. Retained lanes keep their current
logical request across retries and claim fresh work only after a terminal state.
Delay occurs after release, outside writer capacity. The finite method therefore
changes retry spacing and effective pacing of later fresh requests together.
The maximum full-run attempt ceiling was 25,344; actual attempts are outcomes.

Quantiles use Hyndman–Fan type 7 linear interpolation within each cell:
h=(n−1)p, i=floor(h), q=x[i]+(h−i)(x[min(i+1,n−1)]−x[i]).
Report timing/phase tables show the median of five per-cell statistics, rounded
to three decimals. Counts and policy ratios are exact sums; requests are not
pooled for those timing tables. The explicitly labeled retry-pair table is a
separate pooled descriptive sample, not independent experimental replicates.

## 4. Evidence Integrity

All 30 raw JSON files passed the unchanged
[PR5 reader](../../../experiments/load_capacity_protection/pr5_evidence.py),
including schema/method, trajectory and stored-summary checks. Independent
raw-derived accounting, identity, timing, overlap and durable checks reconciled.

| Cohort | Cells | Logical requests | Attempts | Accepted | Budget exhausted | Capacity refusals |
|---|---|---|---|---|---|---|
| all | 30 | 3840 | 15755 | 1626 | 2214 | 14129 |
| recorded | 25 | 3200 | 13140 | 1349 | 1851 | 11791 |
| warmup | 5 | 640 | 2615 | 277 | 363 | 2338 |

There are zero native writer failures, harness failures, evidence problems,
incomplete cells or residual requests. All 30 cells record completed cleanup.
All 1,626 admitted attempts returned acknowledged ACCEPTED with delivered
measurements; there were no writer REPLAY or other normal non-accepted outcomes.
Each of the 3,840 logical requests has a distinct Request ID and Order ID, retained
unchanged across its attempts.

Recorded post-quiescence verification establishes one exact sequence-1 CREATED
event per acknowledged accepted request, exact request/order/amount and returned
event, exact idempotency REPLAY signature/event linkage and one raw matching
idempotency row. All 1,626 accepted event IDs are distinct. All 2,214 exhausted
refusal-only logical requests have no accepted event by order/request, idempotency
MISS with no signature/event mapping and zero raw idempotency rows matching
request OR order. These are readback evidence checks, not newly executed SQL.

Raw evidence path:

```text
experiments/load_capacity_protection/evidence/
  pr5-retry-amplification-20260910T235547117546Z-5084b12a177d/
```

The untouched JSON files total **97,632,272 bytes**. The
[compact CSV](../../../experiments/load_capacity_protection/results/pr5_recorded_policy_comparisons.csv)
contains **25 recorded rows**, excluding warmups, in execution order.
CSV size: **13,019 bytes**; SHA-256:

```text
b05bef39410c305033f1b6691d2f3dd8f22ac04b46dd01a87401bda09dfca5fe
```

The [manifest](../../../experiments/load_capacity_protection/results/pr5_evidence_manifest.json)
records all raw file sizes/hashes, parameters, provenance, cohort/policy totals,
the 53-column CSV/estimator/window contracts and archive identity. Publication
status is `not_published`; no Release URL is assigned.

Exact publication artifact:

```text
/tmp/pr5-retry-amplification-20260910T235547117546Z-5084b12a177d.zip
```

ZIP size: **2,545,966 bytes**; SHA-256:

```text
6e25b699475adeea394f38240b186a6cccde7a4d6f5c272bc22ea6e2024a39bd
```

It was created exclusively outside the repository. ZIP CRC integrity passed.
Its one directory entry and 30 JSON members use the repository-relative raw
directory prefix. Every archived JSON matches its raw source byte-for-byte,
by length and SHA-256. Publication remains a separate authorized action.

## 5. Policy Comparison

Each policy has five recorded cells and 640 logical requests. Completion means
acknowledged accepted logical requests, not generic terminal observations.

| Policy | Logical requests | Attempts | Retries | Amplification | Accepted | Completion % | Budget exhausted | Exhaustion % |
|---|---|---|---|---|---|---|---|---|
| NO_RETRY | 640 | 640 | 0 | 1× | 40 | 6.25 | 600 | 93.75 |
| IMMEDIATE_RETRY | 640 | 4840 | 4200 | 7.5625× | 40 | 6.25 | 600 | 93.75 |
| FIXED_BACKOFF | 640 | 2768 | 2128 | 4.325× | 400 | 62.5 | 240 | 37.5 |
| EXPONENTIAL_BACKOFF | 640 | 2600 | 1960 | 4.0625× | 402 | 62.8125 | 238 | 37.1875 |
| EXPONENTIAL_BACKOFF_WITH_JITTER | 640 | 2292 | 1652 | 3.58125× | 467 | 72.96875 | 173 | 27.03125 |

Individual counts, in recorded repetition order:

| Policy | Attempts, repetitions 0–4 | Accepted, repetitions 0–4 |
|---|---|---|
| NO_RETRY | 128, 128, 128, 128, 128 | 8, 8, 8, 8, 8 |
| IMMEDIATE_RETRY | 968, 968, 968, 968, 968 | 8, 8, 8, 8, 8 |
| FIXED_BACKOFF | 569, 561, 537, 549, 552 | 80, 80, 80, 80, 80 |
| EXPONENTIAL_BACKOFF | 513, 532, 517, 508, 530 | 82, 80, 80, 80, 80 |
| EXPONENTIAL_BACKOFF_WITH_JITTER | 460, 451, 464, 460, 457 | 96, 99, 80, 93, 99 |

These totals match the previously reported approximate values after direct raw
recomputation. Amplification is total attempts divided by logical requests,
not admitted attempts or accepted requests. No policy is required to reach its
attempt ceiling.

## 6. Immediate Retry Amplification

Every recorded NO_RETRY cell has 128 attempts, eight accepted requests and 120
terminal refusals. Every IMMEDIATE_RETRY cell has 968 attempts, eight accepted
requests and 120 budget-exhausted requests: eight admitted first attempts plus
120 × eight refused attempts. Immediate retry adds 4,200 recorded retries while
completion stays at 40/640 = 6.25%. Amplification rises from 1× to 7.5625×.

In all five cells of each of these two policies, the last capacity refusal and
the final refusal-only logical exhaustion precede the first protected body exit.
For immediate retry, first body exit minus last refusal ranges from
6.801
to 12.385 ms.
Because body exit precedes permit release, these callers exhaust their budgets
before an admitted body can release capacity. This directly supports rapid
budget consumption before capacity recovery in this fixture.

This is not idempotency replay: refused calls never entered the protected body
and delivered no writer result or measurement. There were zero writer REPLAY
outcomes. Idempotency REPLAY in durable readback is a verification lookup, not
another writer invocation or the cause of attempt amplification.

## 7. Backoff and Completion Behavior

| Policy | Accepted on first attempt | Accepted after refusal retry | Capacity-refused attempts |
|---|---|---|---|
| NO_RETRY | 40 | 0 | 600 |
| IMMEDIATE_RETRY | 40 | 0 | 4800 |
| FIXED_BACKOFF | 280 | 120 | 2368 |
| EXPONENTIAL_BACKOFF | 322 | 80 | 2198 |
| EXPONENTIAL_BACKOFF_WITH_JITTER | 400 | 67 | 1825 |

Fixed, exponential and jittered backoff accept respectively 400, 402 and 467
requests, but only 120, 80 and 67 of those succeed after a refusal retry.
Their first-attempt accepted counts are 280, 322 and 400, versus 40 for both
NO_RETRY and IMMEDIATE_RETRY. Backoff delays a retained lane's access to later
fresh work as well as its retry; all improvement cannot be attributed solely
to recovery of previously refused requests.

Jitter repetition 2 is particularly instructive: 80 requests succeed on their
first attempt and none succeeds after refusal, despite 464 total attempts.
The pooled policy result would hide this trajectory distinction.

| Policy | Accepted logical p50 ms | Accepted logical p95 ms | Drain ms | Accepted logical/s | First-dispatch wait p50 ms |
|---|---|---|---|---|---|
| NO_RETRY | 18.819 | 19.174 | 19.214 | 416.356 | 4.169 |
| IMMEDIATE_RETRY | 85.685 | 86.072 | 86.108 | 92.906 | 37.947 |
| FIXED_BACKOFF | 73.818 | 116.641 | 123.227 | 649.210 | 42.937 |
| EXPONENTIAL_BACKOFF | 72.295 | 115.447 | 118.890 | 672.892 | 47.638 |
| EXPONENTIAL_BACKOFF_WITH_JITTER | 74.041 | 127.177 | 132.046 | 706.637 | 53.201 |

Drain and accepted-completion latency are different quantities. Backoff policies
take longer to drain than NO_RETRY and IMMEDIATE_RETRY. Their median accepted
logical p50 latency exceeds NO_RETRY's but is below IMMEDIATE_RETRY's in these
cells. Higher accepted counts coexist with longer finite-workload elapsed time.
The CSV retains generic terminal latency separately, including exhausted work.

Throughput is acknowledged accepted count divided by offer-to-final-logical
elapsed, with setup/verification/cleanup/serialization excluded. It is neither
attempt throughput nor inverse median latency. Raw per-cell values and cohort
sizes remain available; no production target or significance test is implied.

## 8. Retry Timing / Temporal Concentration

The following are exact-timestamp sliding-window maxima per cell, then the
median and range across five recorded cells. For width W, count capacity-attempt
timestamps in [t,t+W) and maximize over each observed timestamp t. Windows are
cell-local, half-open and not fixed-origin bins. Both admitted and refused
attempts count; these are not retry-only windows.

| Policy | 5 ms peak: median [min–max] | 10 ms peak: median [min–max] |
|---|---|---|
| NO_RETRY | 90 [63–116] | 128 [101–128] |
| IMMEDIATE_RETRY | 76 [71–76] | 148 [138–149] |
| FIXED_BACKOFF | 45 [45–48] | 75 [73–75] |
| EXPONENTIAL_BACKOFF | 57 [54–58] | 95 [90–100] |
| EXPONENTIAL_BACKOFF_WITH_JITTER | 44 [41–45] | 72 [71–74] |

Immediate retry has the largest 10 ms peak in every matched recorded repetition:
its range is 138–149, above NO_RETRY's maximum of 128 and every backoff cell.
It does **not** have the largest 5 ms peak overall: NO_RETRY reaches 116 and
has median 90, versus immediate retry's maximum/median 76. Thus an unqualified
claim that immediate retry has the highest concentration is unsupported.
The selected temporal resolution materially changes that comparison.

Retry-pair spacing below pools only the five recorded cells of each policy;
NO_RETRY has no retry pairs, so spacing is absent rather than zero.

| Policy | Retry pairs | Refusal→next dispatch p50 µs | p95 µs | Dispatch→next dispatch p50 µs |
|---|---|---|---|---|
| NO_RETRY | 0 | — | — | — |
| IMMEDIATE_RETRY | 4200 | 54.292 | 85.217 | 72.250 |
| FIXED_BACKOFF | 2128 | 5546.208 | 6457.375 | 5573.916 |
| EXPONENTIAL_BACKOFF | 1960 | 8083.750 | 9872.006 | 8114.292 |
| EXPONENTIAL_BACKOFF_WITH_JITTER | 1652 | 9210.230 | 12652.252 | 9245.708 |

Immediate retry's refusal-to-next-dispatch spacing ranges from
26.958 to
66260.291 µs. Its short central
spacing coexists with a long scheduling tail; not every retry is equally rapid.
Fixed/exponential/jitter spacing includes intentional delay and actual scheduler
lateness. Eligibility and exact timestamps remain in raw evidence; CSV columns
retain median/p95 spacing and median lateness.

Jittered backoff shows lower central window peaks than non-jittered exponential
backoff at these two widths, but this does not isolate jitter dispersion from
its added delay, changed attempt count, retained-lane pacing or temporal drift.
No thundering-herd label, universal window, jitter-only causal claim or policy
winner follows from these counts.

## 9. Writer Occupancy Remains Protected

Independent half-open interval sweeps find maximum protected writer-body overlap
exactly eight in **all 30 cells**, including all 25 recorded cells and every policy.
All body intervals close; no cell exceeds the configured bound. The common real
PR3 mechanism therefore continues to protect writer occupancy even as immediate
retry multiplies attempted calls without increasing accepted completion.

Observed application body overlap is not exact physical PostgreSQL transaction
overlap, CPU concurrency or server utilization. The connection population remains
33 per cell; this is not protection against connection creation or pool pressure.
Capacity protection does not automatically bound work performed by refused callers.

## 10. Application-Side Timing Observation

These are acknowledged accepted per-cell p50 values, then five-cell medians.
NO_RETRY and immediate retry each have only eight admitted samples per cell;
backoff cohorts are larger. They are descriptive application intervals.

| Policy | Body p50 ms | PRE idempotency p50 ms | UOW p50 ms | Append p50 ms | Commit p50 ms | Validation p50 µs |
|---|---|---|---|---|---|---|
| NO_RETRY | 18.259 | 9.701 | 6.101 | 1.986 | 1.292 | 8.708 |
| IMMEDIATE_RETRY | 85.089 | 78.197 | 5.770 | 1.880 | 1.138 | 7.500 |
| FIXED_BACKOFF | 11.567 | 2.308 | 6.532 | 2.051 | 1.127 | 7.375 |
| EXPONENTIAL_BACKOFF | 10.951 | 2.216 | 6.372 | 1.756 | 1.126 | 7.250 |
| EXPONENTIAL_BACKOFF_WITH_JITTER | 9.294 | 1.910 | 5.609 | 1.785 | 0.982 | 7.730 |

| Policy | PRE cleanup p50 ms | History load p50 ms | Authoritative idempotency p50 ms |
|---|---|---|---|
| NO_RETRY | 0.755 | 1.002 | 1.741 |
| IMMEDIATE_RETRY | 0.726 | 0.735 | 1.535 |
| FIXED_BACKOFF | 0.867 | 0.906 | 1.835 |
| EXPONENTIAL_BACKOFF | 0.779 | 0.873 | 1.685 |
| EXPONENTIAL_BACKOFF_WITH_JITTER | 0.714 | 0.850 | 1.683 |

Immediate retry is associated with a much larger preliminary idempotency elapsed
interval: median-of-cell-p50 rises from 9.701
ms under NO_RETRY to 78.197 ms.
Protected body p50 likewise rises from 18.259
to 85.089 ms.
The later UOW, append and commit central timings do not show comparable
inflation; their values and repetition variation must remain visible.

The observation supports an association between immediate retry attempt churn
and inflation of application-side pre-UOW elapsed time, concentrated here in
preliminary idempotency lookup. It does not establish GIL, CPU scheduling,
thread contention, WAL, lock contention or any unique root cause. Production
phase values are durations, not absolute SQL timestamps. Client scheduling,
observer work and database physical state remain competing explanations.
Overlapping phase intervals must not be summed into independent cost components.

## 11. Logical Request vs Attempt Semantics

One CREATE intent retains its Request ID, Order ID, amount and RequestSignature
across 1-based increasing attempts. All attempts for a logical request use one
retained lane and execute serially. Every nonfinal attempt is an observed
pre-body capacity refusal; no next attempt precedes its terminal observation
or configured eligibility. No attempt follows acceptance or a native/other
writer terminal result.

Refused attempts have no production result, measurement or idempotency
persistence. Their eventual logical acceptance has one durable effect; their
refusal-only exhaustion has none. Exhaustion is normal experiment evidence,
not semantic failure or production retry authority. No Stage 4E invocation
owner or authority lifecycle is exercised or changed.

## 12. Fairness / Retained-Lane Qualification

Logical requests are offered together but reach their first attempt at different
times. The first-dispatch wait column exposes finite backlog and retained-lane
ownership. A lane keeps a refused request during its retry budget/backoff; other
lanes can continue, while later fresh requests wait for a free lane.

This schedule can favor some trajectories and defer others. The accepted-on-first
versus accepted-after-retry counts show why lane pacing matters. No fairness,
starvation-freedom or production queue property is claimed. The finite budgets
and completed terminal accounting show this workload drained, not that all
logical work succeeded or that the scheduler is fair.

## 13. Limitations

- Local Darwin/arm64, 12 CPUs, PostgreSQL 16.15; independent CREATE only with
  PRE_TRANSACTION/OCC/STRICT FullProof and retained connections.
- One fixed K/N/bound configuration, one parameter set per policy and one jitter
  seed. No production delays, retry budget, capacity constant or SLA is selected.
- Five recorded repetitions with positional rotation, not independent request
  replicates, complete carryover balance or proof against host/cache/WAL drift.
- Finite closed-loop logical backlog; retry delay also paces fresh work. No
  isolated jitter effect, open-loop production arrival process or distributed
  capacity result.
- Small admitted cohorts for NO_RETRY/immediate retry. Tail statistics are
  descriptive; no p99, confidence interval or statistical superiority claim.
- Instrumentation/observation bookkeeping between calls influences scheduling.
  Phase timing is application elapsed time, not server resource attribution.
- Scoped accepted-row cleanup does not restore caches, WAL, dead tuples or
  sequence allocation. No new cleanup or PostgreSQL command ran for closeout.
- No native/ambiguous failures occurred; this run adds no frequency estimate for
  those failures or host-failure behavior. No hard writer deadline is inferred.
- Raw archive is prepared and verified but not published. Compact results do not
  replace complete raw trajectories.

## 14. PR5 Conclusion

Bounded writer admission protected observed writer occupancy under every tested
policy. Immediate retry substantially amplified attempts without improving
logical completion. Backoff policies reduced amplification and increased
completion, while extending drain time and pacing later fresh logical work.
Successful retry recovery explains only part of the additional accepted work.

PR5 therefore supplies evidence that Resource Occupancy Protection and
Retry / Arrival Protection are separate responsibilities. It does not establish
that a Rate Limiter is mandatory, jitter is universally best, these exact delays
belong in production, or retry activity caused host failure.

PR0–PR4 remain COMPLETE; **PR5 is COMPLETE / EVIDENCE COLLECTION CLOSED** after
internal closeout checks, ready for human review. The next separately authorized
step is ADR / architecture interpretation using PR1 degradation, PR4 occupancy/
refusal-displacement and PR5 amplification evidence. No ADR or production
retry/rate/arrival mechanism is selected or implemented here.

Validation used all raw files: strict decode, independent counts and durable
identity/absence checks, exact CSV reconstruction, policy statistics, temporal
windows and body overlap, CSV/manifest hashes, archive CRC and complete member
comparison, local Markdown links and `git diff --check`. No tests, lint, build,
live database verification, experiment rerun or external Release inspection was
performed. Raw PR5 JSON, production/experiment source, PR1/PR4 results/manifests,
Releases and scripts remain untouched. Nothing was staged, committed or pushed.
