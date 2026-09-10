# PR4 — Protected vs Unprotected Characterization Report

[← Back to Load / Capacity Protection](README.md)

```text
PR0–PR3 — COMPLETE
PR4 — COMPLETE / EVIDENCE COLLECTION CLOSED
PR5 — NOT STARTED
Raw PR4 archive publication — PENDING; no further experiment authorized
```

## 1. Purpose

PR4 asks whether bounded in-flight writer admission improves the behavior and
cost of useful PostgreSQL writer work, or merely displaces overload into rapid
pre-entry capacity refusal. The accepted run below compares the same committed
source and composition contemporaneously. [PR1](pr1_unprotected_characterization_report.md)
motivated protection; [PR2](pr2_capacity_interpretation.md) selected experimental
bound eight; [PR3](pr3_bounded_inflight_admission.md) implemented the mechanism.

```text
mechanism correctness
!= local database protection
!= end-to-end overload resolution
```

These are separately assessed below. This report does not declare fail-fast
production readiness, a universal bound, a production SLA/SLO, or a requirement
for rate limiting.

## 2. Environment / Provenance

All 70 raw cells agree on the following facts, read from their provenance.

| Fact | Recorded value |
|---|---|
| Source commit | `e08b79801f9f2c28ad050902700287df5c4968bf` |
| Run ID | `pr4-20260910T114905838802Z-e08b79801f9f` |
| Working-tree qualification before/after cells | `tracked_clean;untracked_not_inspected` |
| Python / psycopg | `3.12.7` / `3.3.4` |
| PostgreSQL / database | `16.15` (160015) / `compass_test` |
| Platform / architecture / logical CPUs | Darwin / arm64 / 12 |
| Isolation / autocommit | read committed / false on every connection |
| Writer / gate | PRE_TRANSACTION / `src.pipeline.transactional.postgres_admission.PostgresOptimisticAdmissionGate` |
| Validation | strict / `src.compass.transition.runtime.ValidationRuntime` / `src.compass.transition.validators.FullProofValidator` |
| Validation policy | `src.compass.transition.runtime.ValidationPolicy` |
| Clock | `time.monotonic_ns` |
| Evidence schema / method | 1 / `pr4-protected-vs-unprotected-v1` |
| Topology | N distinct retained lane connections plus one distinct control/verification connection |
| Protected mechanism | One shared process-local observed PR3 admission object per protected cell, bound 8 |
| Unprotected mechanism | `capacity_admission=None`; no synthetic capacity admission |

The source commit identifies the implementation that produced the measurements,
not this later closeout package. The actual run ID is shorter than the evidence
directory name. No credentials, DSNs or environment-variable contents are included.
Prior session counts, max_connections and reserved slots are not recorded raw
provenance fields and are not asserted as measurements of this run.

At offered N=32 both modes retain 32 lane connections plus one control connection:
33 connections even when protected bodies are bounded at eight. This characterizes
writer-work admission, not connection-count, pool-checkout or max_connections protection.

## 3. A/B Method

The [PR4 method](pr4_protected_vs_unprotected_method.md),
[plan](../../../experiments/load_capacity_protection/pr4_model.py),
[runner](../../../experiments/load_capacity_protection/pr4_runner.py) and
[factory](../../../experiments/load_capacity_protection/pr4_postgres_runtime.py)
define the measured execution. The method's pre-run status remains historical;
this report and the current workstream navigation own closeout status.

| Parameter | Actual recorded configuration |
|---|---|
| K / amount | 512 / Decimal("10.00") per cell |
| Offered N order | (8, 10, 12, 16, 32) |
| Conditions | UNPROTECTED; PROTECTED(bound=8) |
| Warmups / recorded repetitions | 1 / 6 per level and mode |
| Ordering / first mode | alternating_adjacent_pairs / unprotected |
| Workload-index seed | 0 |
| Control connections / connection budget | 1 / 33 |
| Connection setup timeout | 10 seconds |
| Stop policy | stop_claims_and_drain_without_deadline |
| Cleanup policy | delete_verified_cell_rows; accepted identities only |

Each item is a fresh independent CREATE with one logical attempt. All K items
become eligible at a common offer boundary; N persistent lanes replenish after
terminal observations, including refusals. No retry, replacement, requeue or
pacing extends the workload. Setup, verification, cleanup and serialization are
outside offer-to-last-terminal cell time; minimal observation affects scheduling.

The first ten execution indices are warmups. Recorded indices 10–69 contain six
rounds, each visiting the declared N order with adjacent opposite conditions.
For even repetitions, pair orders are U/P, P/U, U/P, P/U, U/P; odd repetitions
reverse them. Each N has three recorded pairs led by each condition. All stored
pair indices, positions, cell identities, repetitions and full execution orders
match the declared plan. Seed zero controls item order, not adaptive cell ordering.

Statistics below are medians of six per-cell statistics, computed before display
rounding. Each per-cell percentile uses Hyndman–Fan type 7 linear interpolation:
sort samples x, let h=(n-1)p and i=floor(h), then interpolate between x[i] and
x[min(i+1,n-1)]. No requests are pooled across repetitions. No confidence,
significance, production threshold or automatic success criterion is inferred.

Public-call p50 includes all 512 attempts, including refusals. Accepted-public-call,
protected-body and production-phase statistics use acknowledged accepted work;
phase samples include only MEASURED values. Protected overload cells have only
eight accepted/body/phase samples each, versus 512 at protected N=8 and every
unprotected cell. Their p95 values are descriptive interpolations over eight
samples, not stable tail estimates. The CSV retains these cohort sizes.

Accepted writes/s is acknowledged accepted count divided by offer-to-last-terminal
elapsed. Acceptance/refusal proportions use offered count, not elapsed time.
Unprotected capacity fields/proportions are absent/N/A, represented as empty CSV
fields and “—” here; zero observed refusal events does not imply an admission gate.

## 4. Evidence Integrity

All 70 raw JSON files were decoded through the unchanged
[PR4 reader](../../../experiments/load_capacity_protection/pr4_evidence.py).
Envelope identity, immutable contracts, reconstructed accounting and overlap
summaries agreed. Independent raw checks also verified every signature, durable
witness, identity uniqueness, timestamp relation and pair/order identity.

| Cohort / mode | Cells | Offered | Acknowledged accepted | Observed capacity refusals |
|---|---:|---:|---:|---:|
| Warmup U | 5 | 2,560 | 2,560 | 0 (gate N/A) |
| Warmup P | 5 | 2,560 | 544 | 2,016 |
| Recorded U | 30 | 15,360 | 15,360 | 0 (gate N/A) |
| Recorded P | 30 | 15,360 | 3,264 | 12,096 |
| All cells | 70 | 35,840 | 21,728 | 14,112 |

All cells have K=512 planned, offered, dispatched and terminal observations.
Protected-only capacity attempts total 17,920, with 3,808 admissions and 14,112
refusals. There are zero native failures, harness failures, evidence problems,
incomplete cells or residual items. All 70 record completed cleanup. All 35,840
request IDs and order IDs are unique; all 21,728 accepted event IDs are unique.
Every acknowledged accepted observation delivers production measurement.

The 70 untouched raw files total **443,193,992 bytes** beneath:

```text
experiments/load_capacity_protection/evidence/
  pr4-protected-vs-unprotected-20260910T114905838802Z-e08b79801f9f/
```

The tracked [compact CSV](../../../experiments/load_capacity_protection/results/pr4_recorded_comparisons.csv)
contains exactly 60 recorded rows in execution-index order and no warmups. It
retains all six individual values per N/mode, counts, cohort sizes, timing,
overlap and refusal/completion ordering. Its 57 columns and estimator/cohort/null
semantics are described in the [manifest](../../../experiments/load_capacity_protection/results/pr4_evidence_manifest.json).
CSV size: **29,832 bytes**; SHA-256:

```text
5532c79b5702eca4cce2bca1bfe3e5a02a15bfaa5505fefa4ec92bbe1a67139f
```

The exact archive is **9,997,962 bytes**, named:

```text
pr4-protected-vs-unprotected-20260910T114905838802Z-e08b79801f9f.zip
```

SHA-256:

```text
930816e2c35f0e039513a85a69588daf46a0910f37b5dadce0c981d07f67c1c2
```

This archive already existed at the requested local staging path. Exclusive-create
refused to overwrite it; it was reused unchanged after validation. Its 71 entries
are one directory entry plus 70 JSON members under the repository-relative raw
directory prefix. ZIP CRC integrity passed, and every member matched its source
byte-for-byte, by size and SHA-256. The manifest records the exact staging path,
archive identity and each raw file hash. **No raw archive publication is claimed**;
publication of this exact ZIP remains a separate final action.

## 5. N=8 Protection-Path Overhead

Each condition has six recorded K=512 repetitions: 3,072 accepted writes per
condition and no refusal events. The protected warmup also accepted all 512.

| Metric | Unprotected N=8 | Protected N=8, bound 8 | P versus U |
|---|---|---|---|
| Accepted writes/s | 1164.77 | 1178.00 | +1.14% |
| Public-call p50 ms | 6.623 | 6.578 | -0.68% |
| Business UOW p50 ms | 4.056 | 4.014 | -1.03% |
| Append p50 ms | 1.218 | 1.198 | -1.62% |
| Commit p50 ms | 0.732 | 0.734 | 0.32% |
| Accepted proportion | 100% | 100% | unchanged |
| Observed refusal events | 0 | 0 | capacity fields remain N/A in U |

Protected-body p50 is 6.572 ms, versus protected public-call p50
6.578 ms. Unprotected public-call timing remains a body proxy; no
unprotected inner-body timestamp is fabricated. These separately aggregated
medians are not an exact per-call gate-overhead subtraction.

Five of six matched repetitions have higher protected accepted throughput;
paired changes range from -3.45% to +4.50%. The ratio of the two reported median
throughputs is +1.14%, not the median of paired percentage changes. In this small,
counterbalanced cohort, no material instrumented protection-path penalty was
observed in the central metrics. This is a descriptive qualification, not an
equivalence test, zero-overhead claim or isolated semaphore benchmark. Both the
gate and extra PR4 observation work belong to the protected path.

## 6. Protected vs Unprotected Results

U means unprotected; P means protected with bound eight. Each row is the median
of six recorded whole-cell statistics.

| N | Mode | Accepted writes/s | Accepted % | Refused % | Public-call p50 ms (all calls) | Body p50 ms (accepted) | Public max overlap | Body max overlap |
|---|---|---|---|---|---|---|---|---|
| 8 | U | 1164.77 | 100.0000 | — | 6.622615 | — | 8 | — |
| 8 | P | 1178.00 | 100.0000 | 0.0000 | 6.577614 | 6.572 | 8 | 8 |
| 10 | U | 1156.94 | 100.0000 | — | 8.380729 | — | 10 | — |
| 10 | P | 355.09 | 1.5625 | 98.4375 | 0.001625 | 21.517 | 9 | 8 |
| 12 | U | 1104.95 | 100.0000 | — | 10.609084 | — | 12 | — |
| 12 | P | 373.17 | 1.5625 | 98.4375 | 0.001688 | 20.685 | 9 | 8 |
| 16 | U | 1107.77 | 100.0000 | — | 14.163948 | — | 16 | — |
| 16 | P | 384.98 | 1.5625 | 98.4375 | 0.001708 | 20.051 | 9 | 8 |
| 32 | U | 1104.10 | 100.0000 | — | 28.454959 | — | 32 | — |
| 32 | P | 344.60 | 1.5625 | 98.4375 | 0.001834 | 22.228 | 9 | 8 |

The approximately 0.002 ms protected-overload public-call medians are dominated
by 504 refused calls; they are not the latency of the eight useful writes.
Accepted protected bodies instead have approximately 20–22 ms p50. The CSV
also retains accepted-public-call p50 to prevent this cohort distinction being lost.

The six individual accepted-throughput values (writes/s), in repetition order:

| N | Mode | Rep 0 | Rep 1 | Rep 2 | Rep 3 | Rep 4 | Rep 5 |
|---|---|---|---|---|---|---|---|
| 8 | U | 1169.51 | 1135.58 | 1142.69 | 1220.65 | 1160.02 | 1176.09 |
| 8 | P | 1222.12 | 1177.50 | 1175.29 | 1178.50 | 1174.96 | 1195.74 |
| 10 | U | 1154.97 | 1134.02 | 1158.91 | 1168.93 | 1151.89 | 1177.66 |
| 10 | P | 350.69 | 343.17 | 419.13 | 345.54 | 361.04 | 359.49 |
| 12 | U | 1102.56 | 1125.93 | 1099.27 | 1143.57 | 1107.35 | 1087.58 |
| 12 | P | 369.54 | 392.60 | 386.49 | 375.17 | 341.01 | 371.16 |
| 16 | U | 1100.71 | 1133.72 | 1091.69 | 1116.12 | 1030.21 | 1114.83 |
| 16 | P | 384.87 | 364.75 | 371.21 | 385.09 | 409.63 | 434.50 |
| 32 | U | 1109.10 | 1099.94 | 1114.19 | 1093.85 | 1060.61 | 1108.25 |
| 32 | P | 368.16 | 342.73 | 316.75 | 414.38 | 343.72 | 345.48 |

All per-repetition phase, body, refusal and overlap values remain in the CSV.
Variation and source/environment scope prevent treating these values as independent
estimates of production capacity or pooling requests into a larger replicate count.

## 7. Writer-Occupancy Protection

Every unprotected recorded cell reaches public-call maximum overlap equal to
its offered N. Every protected recorded cell reaches protected-body maximum
overlap exactly eight. All intervals close.

| N | Recorded cells | Accepted / refused per cell | Public overlap range | Body overlap | Last refusal before first body completion | Gap range ms |
|---|---|---|---|---|---|---|
| 10 | 6 | 8 / 504 | 9 | 8 | 6 / 6 | 6.054–10.790 |
| 12 | 6 | 8 / 504 | 9 | 8 | 6 / 6 | 7.697–10.700 |
| 16 | 6 | 8 / 504 | 9 | 8 | 6 / 6 | 7.613–9.084 |
| 32 | 6 | 8 / 504 | 9–10 | 8 | 6 / 6 | 7.509–11.754 |

Thus all **24/24** recorded protected overload cells credibly exercise public-call
overlap above eight while body overlap remains eight. Configured N=10/12/16/32
must not be substituted for observed public overlap: it is nine in 23 cells and
ten in one N=32 cell. The excess execution opportunity is demonstrated, but a
sustained plateau at each configured N is not.

These are application intervals, not physical PostgreSQL transaction overlap,
CPU concurrency or server utilization. The result supports the shared mechanism's
writer-occupancy boundary in this actual run.

## 8. PostgreSQL-Backed Timing

All phase rows below use acknowledged accepted calls only, with MEASURED samples
and the existing production phase boundaries.

| N | Mode | UOW p50 ms | Append p50 ms | Commit p50 ms | Validation p50 µs |
|---|---|---|---|---|---|
| 8 | U | 4.056 | 1.218 | 0.732 | 6.625 |
| 8 | P | 4.014 | 1.198 | 0.734 | 6.594 |
| 10 | U | 5.087 | 1.636 | 0.941 | 6.646 |
| 10 | P | 4.662 | 1.344 | 1.167 | 8.875 |
| 12 | U | 6.424 | 2.041 | 1.194 | 6.636 |
| 12 | P | 4.957 | 1.346 | 1.134 | 10.094 |
| 16 | U | 8.586 | 2.775 | 1.573 | 6.740 |
| 16 | P | 4.670 | 1.519 | 0.894 | 8.187 |
| 32 | U | 16.835 | 5.507 | 2.863 | 6.833 |
| 32 | P | 4.755 | 1.343 | 1.347 | 10.114 |

Relative changes in the six-repetition medians (P/U - 1):

| N | UOW P vs U | Append P vs U | Commit P vs U |
|---|---|---|---|
| 10 | -8.35% | -17.83% | 23.99% |
| 12 | -22.83% | -34.03% | -5.02% |
| 16 | -45.62% | -45.28% | -43.19% |
| 32 | -71.75% | -75.61% | -52.93% |

UOW and append medians fall at all four offered overload levels. Commit falls
at N=12/16/32 but **increases 23.99% at N=10**; the evidence does not establish
uniform improvement in all PostgreSQL-backed phases. At N=32, UOW falls from
16.835 to 4.755 ms and append from 5.507 to 1.343 ms, alongside 98.4375% refusal.

These are observed application-side PostgreSQL-backed elapsed reductions, with
less amplification in the later write path. They do not prove lower server CPU,
WAL contention, storage I/O or lock contention. Business UOW is an application
interval; append includes persistence/translation work. Overlapping durations
cannot be summed into independent cost components.

Protected admitted bodies remain much slower above the bound than at protected
N=8, despite equal maximum body overlap:

| Offered N (protected) | Body p50 ms | Body p95 ms | Preliminary idempotency p50 ms | History load p50 ms | PRE cleanup p50 ms | Authoritative idempotency p50 ms |
|---|---|---|---|---|---|---|
| 8 | 6.572 | 8.500 | 1.148 | 0.544 | 0.474 | 1.101 |
| 10 | 21.517 | 22.260 | 15.171 | 0.747 | 0.685 | 1.484 |
| 12 | 20.685 | 21.175 | 13.781 | 0.797 | 0.601 | 1.393 |
| 16 | 20.051 | 20.265 | 13.211 | 0.650 | 0.715 | 1.278 |
| 32 | 22.228 | 22.727 | 14.864 | 0.871 | 0.689 | 1.664 |

Protected-overload body p50 is 20.051–22.228 ms versus 6.572 ms at N=8.
Preliminary idempotency p50 grows from 1.148 ms to 13.211–15.171 ms; later
UOW stays at 4.662–4.957 ms versus 4.014 ms. History load, preliminary rollback
and authoritative idempotency are separately visible above and in the CSV.

The timing is consistent with surrounding application-side refusal/admission
churn continuing to interfere with admitted work. It is not proof of the GIL,
scheduler, CPU contention or any unique root cause. Phase measurements contain
elapsed durations, not absolute timestamps proving overlap of a particular SQL
operation with refusals. Different ramp/drain shape, scheduling, measurement and
database physical state are alternative contributors. Local protection is
therefore stage-specific and does not make the whole admitted path uniformly fast.

## 9. Fail-Fast Refusal / Pressure Displacement

Every recorded protected overload repetition at N=10/12/16/32 has:

```text
offered / capacity attempted = 512
capacity admitted / protected body entered = 8
acknowledged accepted = 8
capacity refused = 504
terminal observations = 512
acceptance proportion = 8/512 = 1.5625%
refusal proportion = 504/512 = 98.4375%
```

Across those 24 cells: 12,288 offered/attempted, 192 admitted and acknowledged
accepted, and 12,096 refused. N=8 remains separate; it has no refusal.

In **all 24/24** recorded protected overload cells:

```text
max(capacity_refused_ns) < min(protected_writer_exit_ns)
```

The positive gap ranges from 6.0545 to 11.75425 ms; per-N ranges appear in
Section 7 and exact raw timestamps/gaps are retained in the CSV. Body exit
precedes permit release, so all refused work is already terminally refused
before the first admitted body can release its permit. No permit reuse admits
a second group of logical items.

Fail-fast persistent lanes consume the finite backlog through rapid refusal
while the first eight writers remain active. This is a capacity-refusal burst
and pressure displacement, not successful completion of the refused demand.
Lower later DB-backed latency alone cannot establish better end-to-end overload behavior.

## 10. Why This Is Not Retry Storm Evidence Yet

All 35,840 unique logical items have one dispatch and one public call. Protected
work has one capacity attempt per item; no item is retried, reinvoked or replaced.
A refusal grants no retry, replanning or Stage 4E authority.

The evidence establishes admission-attempt churn across distinct logical items.
It does **not** establish retry amplification or a retry storm. Neither a refusal
count nor the short duration of a refused call is evidence of repeated attempts
for the same logical work.

## 11. Useful-Work Interpretation

Protected-overload median accepted throughput is 344.60–384.98 writes/s, versus
1,104.10–1,156.94 in its contemporaneous unprotected cells: approximately
65.25–69.31% lower by matched N median comparison. This is measured finite-cell
throughput, not a claimed sustained capacity ceiling of the eight-permit writer.

Only the initial eight logical items are admitted, and all 504 others are refused
before the first body finishes. The cells consequently measure finite synchronized
offered work under terminal fail-fast shedding. They do not measure sustained
eight-permit throughput under queued demand, since no pending logical items remain
to enter when a permit becomes free. A refusal does not disappear from the useful
work denominator or become success merely because its terminal latency is short.

PR1 measured a different historical source and continuously replenished successful
unprotected work. It remains motivation, not a substitute control or a compatible
cohort for claiming sustained protected throughput. This report uses current-source
A/B controls and preserves offered, admitted, refused and accepted separately.

## 12. Correctness Verification

Durable evidence is checked independently of acknowledgement:

- All **21,728** acknowledged accepted items (18,624 recorded, 3,104 warmup) have
  exactly one matching CREATED event, sequence 1, exact request/order/amount,
  the returned event, matching idempotency REPLAY signature/event, and one raw
  idempotency row matching request/order identity. No duplicate accepted effects
  or accepted event identities are observed.
- All **14,112** capacity-refused items (12,096 recorded, 2,016 warmup) have no
  event by order/request, idempotency MISS with no signature/event mapping, and
  zero raw idempotency rows matching request or order.
- No native writer failure or ambiguous acknowledgement occurred. This run
  therefore adds no empirical native-failure or ambiguous-commit frequency evidence.

```text
capacity refusal != semantic outcome != native writer failure
```

Absence verifies that refused work left no protected business write effect; it
does not create a SemanticOutcome. Cleanup completion is recorded for every cell:
only exact verified accepted request/order pairs were eligible for deletion.
No new database verification or deletion was performed for this report. Existing
raw readback/cleanup evidence is the basis, not a fresh inspection of live state.

## 13. Limitations

- Local Darwin/arm64, 12 CPUs and PostgreSQL 16.15, independent CREATE only,
  PRE_TRANSACTION/OCC/STRICT FullProof; no universal bound or production workload.
- Finite closed-loop K=512 and terminal shedding, not open-loop arrivals, sustained
  queued demand, retry behavior, PAY/hot-key capacity or distributed admission.
- Retained connections persist above the bound; this does not protect connection
  count or pool checkout.
- Protected-overload admitted statistics use only eight observations per cell.
  Six counterbalanced repetitions remain a small dependent temporal sample; no
  confidence, significance, p99 or production-SLO claim.
- All-call latency mostly measures refusal above the bound. Accepted/body cohorts
  must stay separate; unprotected inner-body timing is unavailable.
- Callback timing and public-call edges add uncertainty and observer cost. The
  protected path includes measurement work; zero overhead is not demonstrated.
- Paired ordering reduces simple lead-order bias but does not eliminate host,
  cache, WAL, checkpoint or dead-tuple drift. Scoped logical cleanup does not
  reset physical state or global-position allocation.
- No server CPU/I/O/WAL/lock trace or direct GIL/scheduler evidence attributes the
  remaining preliminary-read or body latency causally.
- No hard writer deadline, production failure-rate evidence, native failure or
  ambiguous-commit behavior is established by a clean completed run.
- Raw files remain ignored generated evidence. The compact package is trackable;
  exact raw ZIP publication is pending. No PR1 evidence or Release was changed.

## 14. PR4 Conclusion

The shared bound correctly caps observed protected writer-body overlap at eight
under demonstrated excess public-call overlap. It reduces UOW and append elapsed
amplification versus contemporaneous unprotected overload cells; commit improves
at N=12/16/32 but worsens at N=10. No material instrumented protection-path penalty
was observed at offered N=8 in the reported central metrics.

Under this finite synchronized workload, however, all 24 recorded protected
overload cells terminally refuse 504 of 512 logical items before any admitted
body completes. Useful accepted count is only eight, and accepted finite-cell
throughput is much lower. Admitted body latency also remains elevated, concentrated
in preliminary idempotency timing.

PR4 therefore establishes a working writer-occupancy boundary and scoped local
DB-backed cost protection, **not end-to-end overload resolution**. Pressure is
displaced into rapid pre-entry refusal; no retry amplification was tested. This
does not establish fail-fast production readiness, bound eight as universal, or
a need for a Rate Limiter.

PR5 is a **NOT STARTED** candidate, “Retry / Refusal Amplification Characterization”:
can a protected database remain healthy while caller retry behavior amplifies
attempts and destabilizes the surrounding system? A separately approved experiment
could compare no retry, immediate retry, fixed backoff, exponential backoff, and
exponential backoff plus jitter. PR4 implements none of them. Rate limiting, retry
budgets, backoff/jitter and any final ADR remain future evidence-gated work.

A later ADR may distinguish resource-occupancy protection from retry/arrival
protection after PR5 provides the relevant evidence. PR4 documents only the
observed pressure displacement. Publication of the validated raw ZIP is a separate
final action, not authorization for another experiment.

Internal validation for this closeout passed all 70 raw decodes, independent
accounting/durable/overlap/timestamp checks, all 60 CSV rows and all report table
statistics (235 displayed numeric checks), manifest parsing and byte/hash checks,
complete ZIP/source comparison, local Markdown links, and `git diff --check`.
All 60 CSV rows and 57 columns were independently recomputed from raw observations
using Decimal type-7 interpolation and an independent interval sweep. No test suite, PostgreSQL command,
load execution, production change, retry or Rate Limiter implementation belongs
to this closeout. PR0–PR3 remain COMPLETE; PR4 is COMPLETE / EVIDENCE COLLECTION
CLOSED after internal package review, and the package is ready for human review.
PR5 remains NOT STARTED. Nothing is staged, committed, pushed or published by
this closeout.
