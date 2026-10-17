# PR9 — Production Retry Validation Report

[← Back to Load / Capacity Protection](README.md)

```text
PR9 — COMPLETE / EVIDENCE COLLECTION CLOSED
Canonical live matrix — reconciled offline; no rerun
Closeout package — ready for human review
Canonical raw archive — PUBLISHED via GitHub Release load-capacity-pr9-evidence-v1
Production numerical defaults / deployment acceptance — NOT SELECTED
```

## 1. Question and Conclusion

Does the real PR8 `PostgresWriterRequest` bounded-retry path reproduce useful
retry-pressure behavior without violating protected writer occupancy or authority,
and what resources remain retained during synchronous backoff?

The contemporaneous comparison supports higher eventual completion under overload
with finite attempt amplification and protected body overlap bounded at eight.
It does **not** show higher protected writer capacity: paired completion-throughput
changes are small and cross zero, while cohort drain time grows substantially.
Waiting retains existing threads and idle connections. Completion gains include
changed pacing of later fresh work on retained lanes, not only recovery of refused
requests. The next decision is whether that retained-resource trade-off is
acceptable for an intended caller and workload.

## 2. Source and Evidence Provenance

- Evidence-generating revision: `41e33d3a855caa03afbf0b10fe4b2ee01c478a33`.
- Matrix run UUID: `8164f5d8-e1e2-4c4b-9232-44fb899a7c56`.
- Method: `pr9-production-retry-validation-v1`; raw schema: `1`.
- Canonical raw file:
  `experiments/load_capacity_protection/evidence/pr9/matrix-8164f5d8-e1e2-4c4b-9232-44fb899a7c56/final.json`.
- Canonical size: **128,632,396 bytes**.
- Canonical SHA-256:
  `ce0179f8090b3cb0a6307ffc7edd9b4a4608c02bbde634589f078e8c41f18cb0`.
- Runtime recorded in evidence: Python 3.12.7, psycopg 3.3.4,
  Darwin 25.5.0 arm64; PostgreSQL server version 160015 (16.15), read committed,
  autocommit false, declared fixture `compass_test`.
- Every cell's before/after source record matches, with clean tracked files and
  committed production/PR9 machinery. The protected untracked `scripts/` was
  outside the source check and remains untouched.

The [method](pr9_production_retry_validation_method.md) is retained unchanged as
the pre-run machinery/approval record. Its NOT RUN / unselected-parameter labels
describe that earlier task. This report records the subsequently authorized matrix
and its results; it does not rewrite the historical method.

The [compact CSV](../../../experiments/load_capacity_protection/results/pr9_recorded_repetitions.csv)
contains exactly 30 recorded-cell rows. The
[manifest](../../../experiments/load_capacity_protection/results/pr9_evidence_manifest.json)
identifies the source, raw file, archive, parameters, reconciliation and descriptive
aggregates. Neither includes raw request/attempt/wait arrays.

### Raw Evidence Publication

The canonical archive is published in the
[PR9 Production Retry Validation Evidence GitHub Release](https://github.com/hikaru-212/streaming-system-compass/releases/tag/load-capacity-pr9-evidence-v1)
under tag `load-capacity-pr9-evidence-v1`.

- Published asset: `pr9-matrix-8164f5d8-e1e2-4c4b-9232-44fb899a7c56-canonical-final.tar.gz`.
- Filename: `experiments/load_capacity_protection/evidence/pr9/pr9-matrix-8164f5d8-e1e2-4c4b-9232-44fb899a7c56-canonical-final.tar.gz`.
- Compressed size: **3,464,235 bytes**.
- SHA-256: `cc654c6f0c240d44767f3df27efc63fd6410c8c9178a622bf1a8f0c8d576268c`.
- Sole member: `final.json`, containing the original canonical bytes. Its
  decompressed hash was verified against the canonical SHA-256.
- The complete raw matrix includes warmup for provenance; analysis excludes it.
  Smoke and cumulative snapshots are not archived. Earlier Releases remain unchanged.

The approximately 2.3 GB cumulative snapshot directory is checkpoint persistence,
not independent samples. Snapshot files were neither read for this analysis nor
copied/tracked; only the canonical final.json was read.

## 3. Matrix and Aggregation Contract

| Property | Experimental configuration |
|---|---|
| Work | 128 independent CREATE logical requests per cell; amount 10.00 |
| Offered concurrency | N=8, 16, 32 |
| Shared concrete capacity gate | Bound 8 |
| Disabled | Same owner/composition, `retry_policy=None`, one attempt |
| Enabled | `max_attempts=8`, including initial; seven explicit 0.005-second delays |
| Cohorts | One warmup pair and five recorded pairs at each N |
| Total / analyzed | 36 cells / 30 recorded cells; 4,608 total / 3,840 analyzed logical requests |
| Topology | N retained lane connections plus one control: 9 / 17 / 33 |
| Lifecycle | Stop later claims on invalid evidence; drain without deadline; retain generated rows |
| Connection settings | Explicit budget 33; connect timeout 5 seconds |
| Composition | `real-builder/measured/PRE_TRANSACTION/OCC/STRICT/FullProof/retained-lanes-v1` |

The numerical policy deliberately matches the fixed-backoff shape characterized
by PR5, but remains an **experimental validation configuration**, not a deployment
default or optimality decision. PR5 is historical context, not the A/B control.

The real builder creates the real owner, invoking the measured transactional
writer through the exact concrete `BoundedWriterAdmission`. Both modes use the
same observation and measurement settings, PRE_TRANSACTION / OCC / STRICT
FullProof, logical content and retained topology. Each cell has fresh disjoint
Request/Order IDs; attempts within a logical request preserve its full signature.

Only this matrix UUID and `cohort == "recorded"` enter aggregates. There are five
repetitions per N × mode. Within each N, recorded pair indices 0–4 use D/E, E/D,
D/E, E/D, D/E order. Pairing is adjacent and counterbalanced, not randomized or
perfectly position-balanced with five pairs; N blocks are ordered 8, 16, 32.

Unless stated otherwise, tables show **median [minimum, maximum] across five
cell statistics**. D/E mean retry disabled/enabled. Ratios use each cell's original
128 logical requests. Throughput is acknowledged accepts divided by common-offer
to final-logical-terminal drain time. Paired differences are computed first as
enabled minus disabled for matching N and `pair_index`, then summarized; they are
not differences of independent group medians.

Phase/latency tables summarize per-cell statistics with equal repetition weight,
not pooled requests. Within-cell p95 uses linear interpolation, h=(n−1)×0.95
(Hyndman–Fan type 7). CSV scalar values retain numerical precision; report values
are rounded to three decimals. CSV blank timing values would mean unavailable,
never zero. State and missing-delivery counts remain separate. Five repetitions
support descriptive comparisons, not statistical significance or equivalence.

## 4. Integrity and Offline Reconciliation

The exact canonical hash passed before decoding with the committed strict PR9
codec. The full 36-cell schedule and source/configuration metadata reconcile;
all performance/correctness summaries below use only the 30 recorded cells.

Recorded-cell reconciliation passed for all 3,840 logical requests:

- 30 valid cells, five per N × mode, complete expected workload identities.
- 5,920 execution attempts, serial within each logical invocation: 2,854
  admitted/accepted attempts + 3,066 capacity-refused attempts; 2,080 beyond initial
  dispatch.
- 2,854 unique acknowledged accepted events = 2,854 durable accepted effects.
- 986 refusal-only terminal requests have verified absence: 800 disabled refusals
  and 186 enabled budget exhaustions. No accepted effects are inferred from absence.
- All recorded body intervals are complete, and every cell's maximum overlap is 8.
- All 2,080 actual wait calls preserve open connection/thread identity and have
  `IDLE → IDLE` transaction samples. No observation/measurement failure invalidates
  a cell; no incomplete/unobserved logical request is hidden.
- Distinct lane/control connections, matching paired database/version/isolation
  facts and completed connection-close evidence reconcile.

The offline check reuses `summarize`, `request_problems`, `verify_durable`,
`refused_only`, `schedule` and `workload`, with independent identity/count,
topology, wait-boundary and effect-uniqueness checks. These inspect stored live
verification evidence; they do not issue fresh database queries.

## 5. N=8 Control

Both modes accept all 128 requests in every repetition. There are no capacity
refusals, retry attempts, budget exhaustions or waits; amplification is exactly
1.0×. Retry is dormant. Throughput variation, including a positive median paired
difference, cannot be attributed to retry recovery and is not evidence that
enabling retry improves throughput.

## 6. N=16 Moderate Overload

Disabled accepts 64/128 (50%) in every repetition. Enabled accepts 118–120/128
(92.188–93.750%), with median 119 (92.969%). Its 227–244 total attempts correspond
to 1.773–1.906× amplification. Eight to ten requests exhaust their budget per
enabled cell. Protected writer overlap remains 8; peak concurrent waiting
requests/retained connections is 8.

## 7. N=32 Stronger Overload

Disabled accepts 32/128 (25%) in every repetition. Enabled accepts 98–103/128
(76.563–80.469%), with median 100 (78.125%). Its 430–443 attempts correspond to
3.359–3.461× amplification. Twenty-five to thirty requests exhaust per enabled
cell. Protected writer overlap remains 8; waiting request/connection peak is 24.

## 8. Logical Completion and Attempt Amplification

| Metric | N=8 D | N=8 E | N=16 D | N=16 E | N=32 D | N=32 E |
|---|---|---|---|---|---|---|
| Logical requests | 128 [128, 128] | 128 [128, 128] | 128 [128, 128] | 128 [128, 128] | 128 [128, 128] | 128 [128, 128] |
| Acknowledged accepted | 128 [128, 128] | 128 [128, 128] | 64 [64, 64] | 119 [118, 120] | 32 [32, 32] | 100 [98, 103] |
| Completion (%) | 100 [100, 100] | 100 [100, 100] | 50 [50, 50] | 92.969 [92.188, 93.750] | 25 [25, 25] | 78.125 [76.563, 80.469] |
| Total attempts | 128 [128, 128] | 128 [128, 128] | 128 [128, 128] | 237 [227, 244] | 128 [128, 128] | 438 [430, 443] |
| Attempt amplification (×) | 1 [1, 1] | 1 [1, 1] | 1 [1, 1] | 1.852 [1.773, 1.906] | 1 [1, 1] | 3.422 [3.359, 3.461] |
| Capacity refusals | 0 [0, 0] | 0 [0, 0] | 64 [64, 64] | 118 [108, 126] | 96 [96, 96] | 340 [330, 343] |
| Retry attempts | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 109 [99, 116] | 0 [0, 0] | 310 [302, 315] |
| Accepted after retry | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 10 [9, 11] | 0 [0, 0] | 25 [24, 28] |
| Budget exhaustion | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 9 [8, 10] | 0 [0, 0] | 28 [25, 30] |

The CSV supplies each repetition's scalar counts and reconciliation. Disabled
capacity refusals are terminal single attempts, not enabled-policy budget
exhaustions; hence the disabled exhaustion count is correctly zero. Every
nonfinal retry attempt is a verified pre-body capacity refusal. This live fixture
observed accepted results or capacity-specific terminal conditions, not injected
native/semantic failures; failure-class regression guarantees remain PR8's
deterministic evidence rather than new live witnesses.

## 9. Completion Latency and Body Timing

| Metric | N=8 D | N=8 E | N=16 D | N=16 E | N=32 D | N=32 E |
|---|---|---|---|---|---|---|
| Accepted completion p50 (ms) | 70.239 [63.916, 73.863] | 65.850 [62.703, 67.353] | 38.430 [36.861, 41.020] | 68.769 [64.161, 70.711] | 24.252 [22.131, 26.230] | 67.137 [62.122, 69.030] |
| Accepted completion p95 (ms) | 124.387 [115.857, 126.972] | 117.507 [111.564, 129.584] | 68.111 [62.067, 68.842] | 120.855 [115.463, 126.709] | 37.869 [35.277, 38.630] | 111.654 [111.307, 114.297] |
| Protected body p50 (ms) | 7.577 [7.236, 7.775] | 7.244 [7.063, 7.990] | 8.072 [7.352, 8.177] | 7.686 [7.343, 8.063] | 8.537 [7.227, 8.949] | 8.486 [8.290, 9.125] |
| Protected body p95 (ms) | 10.133 [8.938, 14.537] | 9.510 [8.961, 11.339] | 11.135 [10.741, 12.307] | 9.980 [9.337, 11.303] | 12.385 [12.190, 12.891] | 11.965 [10.832, 12.666] |

Accepted completion latency starts at the common logical cohort offer, so it
includes delay before a lane first invokes later work. It is not just protected
body service time. Disabled and enabled accepted cohorts differ in size and
trajectory; their latency distributions are conditional on acceptance.

## 10. Throughput Versus Drain Time and Paired Comparisons

| Metric | N=8 D | N=8 E | N=16 D | N=16 E | N=32 D | N=32 E |
|---|---|---|---|---|---|---|
| Completion throughput (accepted/s) | 1001.860 [969.342, 1074.857] | 1064.581 [964.208, 1111.545] | 929.475 [914.791, 1025.093] | 938.830 [888.574, 967.022] | 841.332 [817.074, 903.304] | 855.081 [829.481, 872.801] |
| Time to drain (ms) | 127.762 [119.086, 132.048] | 120.235 [115.155, 132.751] | 68.856 [62.433, 69.961] | 125.688 [123.058, 133.922] | 38.035 [35.425, 39.164] | 118.011 [113.835, 118.973] |

| Enabled − disabled | N=8 | N=16 | N=32 |
|---|---|---|---|
| Accepted gain | 0 [0, 0] | 55 [54, 56] | 68 [66, 71] |
| Completion gain (percentage points) | 0 [0, 0] | 42.969 [42.188, 43.750] | 53.125 [51.563, 55.469] |
| Additional attempts | 0 [0, 0] | 109 [99, 116] | 310 [302, 315] |
| Amplification difference (×) | 0 [0, 0] | 0.852 [0.773, 0.906] | 2.422 [2.359, 2.461] |
| Additional refusal events | 0 [0, 0] | 54 [44, 62] | 244 [234, 247] |
| Retry-attempt difference | 0 [0, 0] | 109 [99, 116] | 310 [302, 315] |
| Accepted-after-retry difference | 0 [0, 0] | 10 [9, 11] | 25 [24, 28] |
| Exhaustion difference | 0 [0, 0] | 9 [8, 10] | 28 [25, 30] |
| Throughput difference (accepted/s) | 44.978 [-8.001, 85.135] | -9.874 [-63.138, 51.595] | -11.851 [-33.580, 38.007] |
| Throughput relative change (%) | 4.489 [-0.744, 8.294] | -1.057 [-6.159, 5.636] | -1.409 [-3.754, 4.652] |
| Drain-time difference (ms) | -5.489 [-9.918, 0.893] | 61.273 [53.145, 63.961] | 80.111 [77.784, 82.585] |
| Writer overlap difference | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] |
| Waiting logical peak difference | 0 [0, 0] | 8 [8, 8] | 24 [24, 24] |
| Waiting connection peak difference | 0 [0, 0] | 8 [8, 8] | 24 [24, 24] |
| Waiting connection-time difference (connection-ms) | 0 [0, 0] | 586.997 [535.416, 631.236] | 1713.310 [1667.035, 1746.074] |
| Actual wait-duration difference (ms) | 0 [0, 0] | 585.585 [534.148, 629.885] | 1709.792 [1663.582, 1742.016] |

For N=16 the median paired throughput change is −1.057% [−6.159%, +5.636%],
while paired drain time increases by 61.273 ms [53.145, 63.961], a median ratio
of 1.895× [1.760, 1.981]. For N=32 the throughput change is −1.409%
[−3.754%, +4.652%], with drain increasing 80.111 ms [77.784, 82.585], a
median ratio of 3.106× [2.986, 3.331].

Thus completion throughput is broadly similar descriptively while enabled
cells stay active much longer and eventually complete substantially more work.
The group median throughput is slightly higher for enabled at both overload
levels, whereas median paired differences are slightly negative; both calculations
are correct and answer different descriptive questions. Neither establishes
statistical superiority or equivalence. More eventual completions do not imply
higher protected writer capacity or increased database capacity.

## 11. Writer Occupancy

All 30 recorded maxima equal the configured bound of eight. Verified refusals
show CALL_STARTED → REFUSED → CALL_COMPLETED, without admitted body entry.
Admitted attempts show BODY_ENTERED → BODY_EXITED → RELEASED → CALL_COMPLETED.
The retry wait starts after the refusing admission call completes. The waiting
request never acquired a capacity permit for that attempt; no permit spans its
backoff. Other logical requests may execute concurrently.

This is application protected-body overlap backed by the real gate, not a
measurement of physical PostgreSQL transaction overlap or database capacity.

## 12. Retained Thread and Connection Cost

| Metric | N=8 D | N=8 E | N=16 D | N=16 E | N=32 D | N=32 E |
|---|---|---|---|---|---|---|
| Protected writer max overlap | 8 [8, 8] | 8 [8, 8] | 8 [8, 8] | 8 [8, 8] | 8 [8, 8] | 8 [8, 8] |
| Configured retained connections incl. control | 9 [9, 9] | 9 [9, 9] | 17 [17, 17] | 17 [17, 17] | 33 [33, 33] | 33 [33, 33] |
| Waiting logical peak | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 8 [8, 8] | 0 [0, 0] | 24 [24, 24] |
| Waiting retained connection peak | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 8 [8, 8] | 0 [0, 0] | 24 [24, 24] |
| Waiting-retained connection-time (connection-ms) | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 586.997 [535.416, 631.236] | 0 [0, 0] | 1713.310 [1667.035, 1746.074] |
| Aggregate actual wait-call duration (ms) | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 585.585 [534.148, 629.885] | 0 [0, 0] | 1709.792 [1663.582, 1742.016] |
| Actual wait calls | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 109 [99, 116] | 0 [0, 0] | 310 [302, 315] |
| Distinct waiting lanes | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 10 [9, 11] | 0 [0, 0] | 25 [24, 26] |
| Distinct waiting threads | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 10 [9, 11] | 0 [0, 0] | 25 [24, 26] |
| Distinct waiting lane connections | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 10 [9, 11] | 0 [0, 0] | 25 [24, 26] |

The waiting-retained connection integral uses production RETRY_SCHEDULED →
RETRY_READY intervals, converted from monotonic seconds to nanoseconds by the
existing summarizer. Actual wait duration sums integer-nanosecond waiter-call
intervals. Their small difference includes surrounding scheduling/bookkeeping;
neither should be substituted for the other or interpreted as CPU consumption.

Across the five enabled cells, N=16 retains 2.903575 connection-seconds during
scheduled waiting; N=32 retains 8.565199 connection-seconds. Corresponding actual
wait-call duration sums are 2.896870 and 8.547360 seconds. These are sums across
concurrent retained resources/repetitions, not one cell's wall-clock duration.

The topology remains 17 connections at N=16 and 33 at N=32 in **both** modes,
including control. Retry retains existing lane/thread/connection ownership longer;
it does not increase the configured connection count. Distinct waiting identities
over the whole cell can exceed the simultaneous waiting peak. Recorded thread
mapping is one distinct thread per lane; every observed wait stays on that lane's
thread and connection. No CPU cost, scheduler contention, connection-pool behavior
or full-lifecycle resource utilization is inferred from these observations.

## 13. IDLE Transaction Evidence

N=16 enabled has 533 actual wait calls and N=32 enabled has 1,547. All 2,080
before/after transaction-status pairs are IDLE → IDLE, with the same open
connection before and after. Source ownership and verified pre-body refusal
establish that the waiting invocation holds no writer permit or active business
transaction. The normal waiter performs no SQL. These are boundary samples plus
exclusive connection ownership, not continuous server-side monitoring.

N=8 and disabled cells have no wait calls; their zero wait counts/integrals are
observed absence, not replacement of unavailable measurements. No wait-status,
identity, permit or occupancy violation was found.

## 14. Retained-Lane Pacing Qualification

| N | Disabled accepted (five cells) | Enabled accepted | Accepted gain | Enabled accepted after retry | Additional first-attempt accepts |
|---|---|---|---|---|---|
| 8 | 640 | 640 | 0 | 0 | 0 |
| 16 | 320 | 595 | 275 | 50 | 225 |
| 32 | 160 | 499 | 339 | 127 | 212 |

The following uses matching pair indices, without equating different cells'
fresh business identities:

| N | Pair index | Accepted gain | Enabled accepted after retry | Gain beyond accepted-after-retry count |
|---|---|---|---|---|
| 16 | 0 | 55 | 9 | 46 |
| 16 | 1 | 56 | 9 | 47 |
| 16 | 2 | 55 | 10 | 45 |
| 16 | 3 | 54 | 11 | 43 |
| 16 | 4 | 55 | 11 | 44 |
| 32 | 0 | 66 | 24 | 42 |
| 32 | 1 | 68 | 24 | 44 |
| 32 | 2 | 68 | 26 | 42 |
| 32 | 3 | 66 | 28 | 38 |
| 32 | 4 | 71 | 25 | 46 |

At N=16, direct accepted-after-retry events account numerically for only 50 of
275 additional completions; at N=32, 127 versus 339. The remaining arithmetic
difference is an increase in first-attempt accepts across the paired cohorts,
not a causal attribution to particular requests.

The source assigns finite work by index modulo N. A lane retains its current
logical request through synchronous backoff and advances to later fresh work
only after a terminal outcome. Backoff therefore changes fresh-work dispatch
timing as well as retry timing. This supports the same qualification in
[PR5 Sections 7 and 12](pr5_retry_refusal_amplification_report.md#7-backoff-and-completion-behavior):
the observed completion improvement belongs to the whole retained-lane composition
and cannot be attributed solely to retry recovery. This is not evidence of a
new production queue, fairness guarantee or isolated pacing intervention.

## 15. Production Phase Timing

Each entry is the median [minimum, maximum] of five **per-cell phase medians**,
in milliseconds. Individual phase minima/maxima and state counts are retained as
scalar CSV columns; raw samples remain only in canonical evidence.

| Metric | N=8 D | N=8 E | N=16 D | N=16 E | N=32 D | N=32 E |
|---|---|---|---|---|---|---|
| `producer_write_invocation` (ms) | 7.546 [7.203, 7.748] | 7.217 [7.038, 7.964] | 8.045 [7.325, 8.149] | 7.662 [7.316, 8.037] | 8.508 [7.200, 8.826] | 8.460 [8.265, 9.094] |
| `business_uow` (ms) | 4.518 [4.398, 4.579] | 4.377 [4.210, 4.859] | 4.938 [4.411, 5.028] | 4.545 [4.402, 4.899] | 5.123 [4.350, 5.389] | 5.064 [4.575, 5.441] |
| `append_admission_call` (ms) | 1.359 [1.314, 1.384] | 1.348 [1.319, 1.473] | 1.483 [1.187, 1.708] | 1.455 [1.308, 1.555] | 1.545 [1.186, 1.610] | 1.605 [1.404, 1.712] |
| `idempotency_record_call` (ms) | 0.586 [0.541, 0.615] | 0.617 [0.578, 0.701] | 0.623 [0.530, 0.712] | 0.628 [0.598, 0.686] | 0.665 [0.602, 0.691] | 0.742 [0.601, 0.828] |
| `commit_finalization` (ms) | 0.924 [0.850, 0.962] | 0.872 [0.808, 0.952] | 0.933 [0.801, 1.125] | 0.942 [0.822, 0.954] | 1.020 [0.819, 1.199] | 0.933 [0.900, 0.996] |

Measured sample counts per requested phase across the five cells are respectively
640 / 640 / 320 / 595 / 160 / 499 for the six columns. All five requested phases
are MEASURED on each of the 2,854 accepted writer returns: no NOT_COLLECTED,
NOT_REACHED, NOT_APPLICABLE or missing delivery appears for these five phases.

The broader measurement correctly retains 2,854 NOT_APPLICABLE
`pessimistic_advisory_try_lock_call` states and 2,854 NOT_REACHED
`rollback_finalization` states. Their elapsed values remain absent, not zero.
Pre-body refused attempts have no writer measurement delivery because the body
did not execute; they are not zero-duration measured writers.

Phase times are application elapsed observations. Producer invocation, UOW,
append, idempotency and commit intervals overlap and must not be summed into
SQL/CPU cost. UOW elapsed is not exact physical transaction lifetime; append is
the whole append-admission call, not pure INSERT cost. These samples do not
establish production phase improvements or optimal delay values.

## 16. Durable Correctness

| N | Mode | Recorded logical | Acknowledged | Durable effects | Refusal-only absent | Exhausted absent |
|---|---|---|---|---|---|---|
| 8 | disabled | 640 | 640 | 640 | 0 | 0 |
| 8 | enabled | 640 | 640 | 640 | 0 | 0 |
| 16 | disabled | 640 | 320 | 320 | 320 | 0 |
| 16 | enabled | 640 | 595 | 595 | 45 | 45 |
| 32 | disabled | 640 | 160 | 160 | 480 | 0 |
| 32 | enabled | 640 | 499 | 499 | 141 | 141 |

Every accepted request's stored live readback contains exactly its acknowledged
sequence-1 CREATED event with matching Request ID, Order ID and amount; raw
request event count and idempotency identity count are each one. The verification
lookup returns REPLAY with the exact RequestSignature and accepted event.
That REPLAY is readback evidence, not an extra writer execution or business effect.

Every refusal-only terminal request has empty accepted history, zero event and
idempotency identity counts and MISS with no record. This includes all 186
enabled exhaustions. No acceptance is fabricated for terminal refusal, and no
absence is inferred from an unavailable read. These equalities hold separately
for every recorded cell, not merely in pooled totals.

## 17. Limitations

- One approved matrix, one source revision, one retained-connection topology and
  one experimental fixed-backoff configuration; five repetitions per condition.
- Finite independent CREATE workload, not PAY, hot keys, distributed ingress,
  an open-loop arrival process or a deployment traffic model.
- Ordered N blocks and alternating adjacent pairs do not remove host/cache/WAL
  drift or carryover. Rows were retained; database physical state was not reset.
- Synchronous retained-lane pacing is inseparable from this treatment. Neither
  request-level causal recovery nor fairness/starvation freedom is established.
- Equal instrumentation settings preserve comparison symmetry but do not remove
  observation overhead; this is not an uninstrumented production benchmark.
- Body overlap, elapsed phase timing and IDLE boundary observations do not measure
  server CPU, continuous transaction occupancy, scheduler contention or pooling.
- A finite attempt budget does not impose a hard writer/drain deadline or provide
  cancellation/expiry behavior. Completed finite work here is not a universal
  termination or latency guarantee.
- Live outcomes contain acceptance and pre-body capacity refusal/exhaustion.
  PR8's other terminal/failure classes were not newly injected in this matrix.
- Raw evidence publication does not select deployment numerical policy or an
  operating SLO.

## 18. What PR9 Establishes

For this configuration and fixture, the actual production-capable owner supports
finite, serial, identity-preserving retry of verified pre-body refusal; it retains
the shared occupancy bound and exact accepted durable linkage. Under overload,
the complete retained-lane composition improves eventual logical completion while
increasing attempt work, drain time and attributable idle-resource retention.
It reproduces PR5's useful qualitative backoff behavior and its pacing caveat
through the real PR8 mechanism, using a contemporaneous disabled baseline.

## 19. What PR9 Does Not Establish

Eight attempts and fixed 5 ms delay are not production defaults or optimal
settings. The bound eight is experimental, not a universal capacity limit.
Fixed backoff is not proven globally optimal. Retry recovery did not directly
cause every extra completion. Configured connection count did not rise.
This evidence neither makes Rate Limiter or jitter permanently unnecessary nor
selects a queue, pool, async scheduler or new arrival policy. Stage 4E authority
and the A1/A2 lifecycle remain outside this composition and unchanged.

## 20. Status, Validation and Next Architecture Decision

**PR9 is COMPLETE / EVIDENCE COLLECTION CLOSED**, with the compact closeout ready
for human review. Production/experiment source and raw evidence are unchanged.
The closeout comprises results, report/navigation and the canonical archive,
now published at the Release above.

Offline validation checked the canonical hash/strict decode, recorded cohort and
pair identity, logical/attempt accounting, occupancy, wait resource/status evidence,
phase-state semantics, durable linkage/absence, scalar result reconciliation and
archive-member byte identity. All 2,490 CSV fields (30 rows × 83 columns), six
group summaries and 15 paired comparisons reconcile with independently re-decoded
canonical evidence. All 56 local documentation links, new/modified text whitespace
checks and `git diff --check` passed. Offline Python checks used the repository
interpreter with `PYTHONOPTIMIZE=0 PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python`.
No PostgreSQL execution or test-suite run occurred: these changes are data and
documentation only, with production and experiment machinery unchanged.

The next architecture question is whether retaining synchronous threads and
connections during backoff is acceptable for the intended caller's concurrency,
latency and connection budget. If it is not, a separately scoped architecture or
policy decision is warranted before implementation or deployment. This report
does not invent or authorize a PR10 implementation, additional experiments,
production parameters, lifecycle redesign, pooling, queueing or async retry.
