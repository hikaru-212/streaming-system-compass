# Stage 4B.2 PR6 — PostgreSQL Strategy Comparison Report

[← Back to Stage 4B.2](README.md)

## Status

```text
PR6
= COMPLETE

Canonical run
= VALID

Recorded samples
= 450

Exceptions
= 0
```

This is a Level-B descriptive empirical report. It is not an ADR, a production
strategy decision, a capacity result, or a retry-policy recommendation.

## Purpose

PR6 compares the current correctness-preserving PostgreSQL write compositions
under the fixed protocol defined by the [comparison
method](postgres_strategy_comparison_method.md):

```text
PRE_OCC
= PRE_TRANSACTION validation placement
+ optimistic/OCC append-time admission

IN_PESSIMISTIC
= IN_TRANSACTION validation placement
+ PostgreSQL pessimistic advisory-lock admission
```

The report describes external invocation cost, reached phase cost, outcome
cohorts, and observer effect in one recorded environment. It keeps accepted,
stale-write, and lock-non-acquisition paths separate.

## Canonical Evidence Identity

| Field | Recorded value |
|---|---|
| Run ID | `stage4b2-pr6-canonical-0bd2f51` |
| Recorded source commit | `0bd2f515bcc49e8e1f0e9d2f9dba4a294adadd0d` |
| Evidence commit | `16d436670ac5fb502e7740fb4b40f5e87fa3069e` |
| Source tree clean before run | `true` |
| Validation | `FullProofValidator` / `STRICT` |
| Command | `CREATE` |
| Initial history depth | `0` |
| Worker count | `2` |
| Run validation | `VALID` |

The canonical artifacts are the recorded
[manifest](../../../experiments/stage4b2/evidence/stage4b2-pr6-canonical-0bd2f51/manifest.json),
[raw samples](../../../experiments/stage4b2/evidence/stage4b2-pr6-canonical-0bd2f51/samples.jsonl),
and [aggregates](../../../experiments/stage4b2/evidence/stage4b2-pr6-canonical-0bd2f51/aggregates.json).

## Fixed Protocol

The run used the accepted default protocol without adaptive extension:

| Protocol part | Fixed value |
|---|---:|
| Sequential warmup | 5 cycles |
| Concurrent warmup | 3 batches per composition |
| Observer-schedule repetitions | 5 |
| Scenario A | 30 samples per surface per composition |
| Scenario B | 30 two-worker batches per composition |
| Scenario C | 30 two-worker batches per composition |
| Scenario E | 30 IN samples |
| Scenario B core-cohort minimum | 20 |
| Worker count | 2 |

The workload was fresh `CREATE`, amount `Decimal("100.00")`, empty accepted
history, expected sequence 1, and the real `FullProofValidator` in
`ValidationMode.STRICT`.

## Structural Results

| Scenario and cohort | PRE_OCC | IN_PESSIMISTIC | Total |
|---|---:|---:|---:|
| A — `ACCEPTED` | 90 | 90 | 180 |
| B — `ACCEPTED` | 30 | 30 | 60 |
| B — `APPEND_STALE_WRITE` | 30 | 0 | 30 |
| B — `PREPARE_LOCK_TIMEOUT` | 0 | 30 | 30 |
| C — `ACCEPTED` | 60 | 60 | 120 |
| E — `PREPARE_LOCK_TIMEOUT` | 0 | 30 | 30 |
| **Total** | **210** | **240** | **450** |

All 450 plans executed exactly once. There were no exception samples. All 330
normal current-measured samples delivered `AVAILABLE` evidence, and every such
sample contained all thirteen phase records.

## Scenario A — Accepted PRE vs IN

For the primary `CURRENT_MEASURED` surface, external invocation time was:

| Composition | Count | Min | Mean | Median | Max |
|---|---:|---:|---:|---:|---:|
| PRE_OCC | 30 | 2.163 ms | 2.986 ms | 2.862 ms | 5.299 ms |
| IN_PESSIMISTIC | 30 | 2.013 ms | 2.610 ms | 2.509 ms | 3.499 ms |

The paired `IN - PRE` difference had mean `-0.376 ms` and median
`-0.320 ms`. The paired median difference was `-11.18%` relative to the PRE
median. IN therefore had lower observed accepted external central cost in this
recorded Scenario-A measured cohort. This is an environment-qualified
observation, not a universal ranking.

The low-observation `CURRENT_UNMEASURED` control was directionally consistent:

| Composition | Count | Min | Mean | Median | Max |
|---|---:|---:|---:|---:|---:|
| PRE_OCC | 30 | 2.312 ms | 2.887 ms | 2.706 ms | 4.626 ms |
| IN_PESSIMISTIC | 30 | 1.990 ms | 2.410 ms | 2.227 ms | 3.611 ms |

Here the paired `IN - PRE` difference had mean `-0.476 ms` and median
`-0.440 ms`, or `-16.24%` relative to the PRE median. The direction agrees
with the measured surface, while the magnitude changes with observation mode.

## Validation Runtime Comparison

For Scenario A `CURRENT_MEASURED/ACCEPTED`, the observed
`validation_runtime_call` cost was:

| Placement | Count | Min | Mean | Median | Max |
|---|---:|---:|---:|---:|---:|
| PRE placement | 30 | 4.416 µs | 7.250 µs | 6.500 µs | 30.750 µs |
| IN placement | 30 | 4.542 µs | 7.250 µs | 6.958 µs | 12.583 µs |

The median difference was `+0.458 µs`, or `+7.05%` relative to the PRE
median. The relative percentage looks larger because the absolute phase lasts
only several microseconds. The absolute difference is small and does not
explain the millisecond-scale external difference. This compares observed
validation-runtime-call cost under PRE placement with observed
validation-runtime-call cost under IN placement; it does not establish an
intrinsic causal change in `FullProofValidator`.

## Accepted Phase-Level Comparison

The following Scenario-A phase values are reported independently. Parent and
child intervals overlap and must not be summed.

| Phase | PRE mean | PRE median | IN mean | IN median |
|---|---:|---:|---:|---:|
| `producer_write_invocation` | 2.950 ms | 2.827 ms | 2.574 ms | 2.469 ms |
| `business_uow` | 1.857 ms | 1.761 ms | 2.566 ms | 2.462 ms |
| `authoritative_idempotency_check` | 565.397 µs | 494.834 µs | 680.250 µs | 536.209 µs |
| `accepted_history_load` | 262.818 µs | 249.459 µs | 285.042 µs | 251.313 µs |
| `concurrency_preparation_call` | 2.801 µs | 1.896 µs | 254.986 µs | 248.729 µs |
| `append_admission_call` | 592.539 µs | 574.167 µs | 630.385 µs | 573.563 µs |
| `idempotency_record_call` | 285.735 µs | 271.813 µs | 284.474 µs | 278.021 µs |
| `commit_finalization` | 397.699 µs | 367.542 µs | 379.663 µs | 359.605 µs |

PRE additionally measured `preliminary_idempotency_check` at mean
`557.067 µs`, median `549.292 µs`, and `preliminary_read_cleanup` at mean
`227.285 µs`, median `193.396 µs`. IN instead measured
`pessimistic_advisory_try_lock_call` at mean `250.320 µs`, median
`244.709 µs`.

The largest visible placement-specific phase differences were IN's larger
`business_uow` and concurrency-preparation intervals, and PRE's extra durable
preliminary idempotency lookup plus read-transaction cleanup before its UoW.
Because the intervals overlap, these values do not decompose the external
difference additively.

The accepted-path PRE/OCC overhead may be materially influenced by the
additional durable preliminary idempotency lookup and read-transaction
cleanup. This is an open explanatory hypothesis, not a causal result. Whether
the preliminary or authoritative idempotency checks can be simplified is a
separate architecture investigation after PR6 closeout.

## Observer Effect

Scenario A used external invocation timing only for the accepted A/B/C model:

```text
A = FROZEN_BASELINE
B = CURRENT_UNMEASURED
C = CURRENT_MEASURED
```

| Composition | A mean / median | B mean / median | C mean / median |
|---|---:|---:|---:|
| PRE_OCC | 3.157 / 3.064 ms | 2.887 / 2.706 ms | 2.986 / 2.862 ms |
| IN_PESSIMISTIC | 2.532 / 2.430 ms | 2.410 / 2.227 ms | 2.610 / 2.509 ms |

Paired differences were:

| Composition | B - A inactive seam | C - B active collection | C - A total observer |
|---|---:|---:|---:|
| PRE_OCC mean / median | -0.270 / -0.210 ms | +0.100 / +0.125 ms | -0.170 / -0.229 ms |
| IN_PESSIMISTIC mean / median | -0.121 / -0.135 ms | +0.200 / +0.104 ms | +0.078 / +0.019 ms |

Active measurement therefore had a visible but variable central effect:
approximately `+0.10` to `+0.13 ms` for PRE and `+0.10` to `+0.20 ms` for IN.
The frozen/current totals are not monotonic for PRE, which reinforces that
small observer differences are environment- and schedule-sensitive. Internal
phase measurements are not used to estimate their own observer cost.

## Scenario B — Accepted Competition

Same-order, two-worker accepted samples remained separate from Scenario A:

| Composition | Count | Min | Mean | Median | Max |
|---|---:|---:|---:|---:|---:|
| PRE_OCC | 30 | 3.018 ms | 3.927 ms | 3.740 ms | 5.578 ms |
| IN_PESSIMISTIC | 30 | 2.166 ms | 2.820 ms | 2.614 ms | 3.767 ms |

IN again had lower observed accepted external central cost in this recorded
cohort. Contention increased several phase intervals and changed their
magnitudes, so these samples are not pooled with the uncontended baseline.

## PRE Stale-Write Mechanism

Scenario B produced 30 PRE `APPEND_STALE_WRITE` samples. External elapsed time
was min `3.343 ms`, mean `4.219 ms`, median `4.048 ms`, and max `5.930 ms`.

| Reached phase | Mean | Median |
|---|---:|---:|
| `producer_write_invocation` | 4.191 ms | 4.021 ms |
| `business_uow` | 2.640 ms | 2.367 ms |
| `preliminary_idempotency_check` | 801.919 µs | 604.167 µs |
| `preliminary_read_cleanup` | 324.487 µs | 246.792 µs |
| `authoritative_idempotency_check` | 787.315 µs | 581.500 µs |
| `accepted_history_load` | 373.572 µs | 307.250 µs |
| `validation_runtime_call` | 5.971 µs | 5.479 µs |
| `concurrency_preparation_call` | 1.421 µs | 1.188 µs |
| `append_admission_call` | 1.644 ms | 1.448 ms |
| `rollback_finalization` | 197.692 µs | 197.354 µs |

This is the derived Scenario-D mechanism evidence; there is no Scenario-D
executor or dataset. Before append returned stale, PRE had already paid the
preliminary and authoritative idempotency checks, preliminary read cleanup,
accepted-history load, validation, and append admission work. Idempotency
recording and commit finalization were not reached.

## IN Lock-Timeout Mechanism

Scenario B produced 30 IN `PREPARE_LOCK_TIMEOUT` samples. External elapsed
time was min `0.946 ms`, mean `1.439 ms`, median `1.244 ms`, and max
`2.239 ms`.

| Reached phase | Mean | Median |
|---|---:|---:|
| `producer_write_invocation` | 1.408 ms | 1.210 ms |
| `business_uow` | 1.403 ms | 1.206 ms |
| `authoritative_idempotency_check` | 716.169 µs | 619.625 µs |
| `concurrency_preparation_call` | 431.686 µs | 304.313 µs |
| `pessimistic_advisory_try_lock_call` | 428.676 µs | 300.917 µs |
| `rollback_finalization` | 244.997 µs | 218.313 µs |

This is an early rejection path. `validation_runtime_call`,
`accepted_history_load`, `append_admission_call`, `idempotency_record_call`,
and `commit_finalization` were consistently `NOT_REACHED`; preliminary
idempotency and read-cleanup phases were `NOT_APPLICABLE` for IN.

## Failure-Path Comparison

The PRE stale-write median was `4.048 ms`; the IN preparation lock-timeout
median was `1.244 ms`, a central difference of approximately `2.805 ms`.
These are not equivalent outcomes and are not pooled into a strategy score.

Mechanistically, PRE rejects late after validation, history, and append work.
IN rejects during preparation after the authoritative idempotency check and
the real advisory try-lock, avoiding validation, history load, append
admission, idempotency recording, and commit. Both paths perform rollback
finalization.

## Scenario C — Different-Order Concurrency

With two workers targeting independent orders, all 120 samples were accepted:

| Composition | Count | Min | Mean | Median | Max |
|---|---:|---:|---:|---:|---:|
| PRE_OCC | 60 | 3.176 ms | 4.340 ms | 4.183 ms | 6.028 ms |
| IN_PESSIMISTIC | 60 | 2.361 ms | 3.696 ms | 3.495 ms | 6.952 ms |

The direction agrees with Scenario A and Scenario-B accepted samples, while
the magnitude and variability differ under concurrent execution. Major median
phase contrasts included PRE `business_uow` at `2.780 ms` versus IN at
`3.459 ms`, and PRE `concurrency_preparation_call` at `1.771 µs` versus IN at
`305.063 µs`. PRE additionally paid preliminary idempotency and cleanup
medians of `675.521 µs` and `252.396 µs`; IN paid an advisory try-lock median
of `301.313 µs`. These overlapping phase intervals are not summed.

Worker count remained fixed at two. Scenario C is not scaling or saturation
evidence.

## Scenario E — Lock Non-Acquisition Corroboration

All 30 Scenario-E samples naturally returned `PREPARE_LOCK_TIMEOUT` while a
separate connection held the real PostgreSQL advisory transaction lock.
External elapsed time was min `0.960 ms`, mean `1.402 ms`, median `1.261 ms`,
and max `2.403 ms`.

| Reached phase | Mean | Median |
|---|---:|---:|
| `producer_write_invocation` | 1.366 ms | 1.228 ms |
| `business_uow` | 1.359 ms | 1.221 ms |
| `authoritative_idempotency_check` | 685.374 µs | 630.688 µs |
| `concurrency_preparation_call` | 370.513 µs | 301.896 µs |
| `pessimistic_advisory_try_lock_call` | 366.372 µs | 297.313 µs |
| `rollback_finalization` | 290.631 µs | 251.334 µs |

Validation, accepted-history load, append admission, idempotency recording,
and commit finalization were consistently avoided. Scenario E independently
corroborates the production lock-non-acquisition mechanism observed in
Scenario B; it is not a matched PRE/IN ranking.

## Start-Offset Assessment

| Scenario | Count | Min | Mean | Median | Max |
|---|---:|---:|---:|---:|---:|
| B | 120 | 1.920 µs | 16.440 µs | 16.150 µs | 41.920 µs |
| C | 120 | 1.960 µs | 19.070 µs | 18.130 µs | 74.580 µs |

Every B/C sample retained a start offset. The Scenario-B median offset was
about `0.51%` of its combined external median and its maximum was about
`1.31%`; the corresponding Scenario-C values were about `0.46%` and `1.91%`.
The offsets were small relative to invocation duration in this run and do not
present a material concurrency-interpretation concern. PR6 defines no
universal skew threshold.

## Strong Descriptive Signals

- IN had lower observed accepted external central cost in this recorded
  environment across measured Scenario A, unmeasured Scenario A, Scenario-B
  accepted competition, and Scenario-C different-order concurrency.
- PRE stale-write rejection was a late path that paid validation, history, and
  append work; IN preparation lock timeout was an early path that avoided that
  downstream work.
- Scenario E independently reproduced the real advisory-lock non-acquisition
  mechanism without manufactured outcomes.

## Moderate / Context-Sensitive Signals

- The size of the accepted PRE/IN external difference changed by scenario and
  by measured versus unmeasured observation surface.
- Active measurement added visible central external cost, approximately
  `+0.10` to `+0.13 ms` for PRE and `+0.10` to `+0.20 ms` for IN, but the
  observer-effect estimates varied across compositions and comparisons.
- Several PostgreSQL phase intervals changed under competition and
  different-order concurrency; these remain environment- and workload-bound.

## Weak / Noisy Signals

- The `validation_runtime_call` median differed by only `+0.458 µs`. Its
  `+7.05%` relative figure is large-looking only because the underlying phase
  is several microseconds, and it does not explain the external difference.
- Small differences among accepted history, append, record, commit, and
  validation phase medians are minor relative to their observed ranges and
  the end-to-end variability.
- The inactive-seam and total-observer comparisons are not consistently
  monotonic, so they should not be treated as stable standalone costs.

## What PR6 Supports

PR6 supports these environment-qualified conclusions:

- IN had lower observed accepted external central cost for the fixed CREATE,
  empty-history workloads and fixed two-worker scenarios recorded here.
- The magnitude of that observation is scenario- and observer-sensitive.
- Observed validation-runtime-call cost was very similar in absolute terms
  under PRE and IN placement and did not account for the millisecond-scale
  external difference.
- PRE stale-write rejection paid work that IN lock non-acquisition avoided.
- The Scenario-B and Scenario-E lock-timeout samples reflect the real
  PostgreSQL pessimistic admission mechanism.
- Measurement introduced a visible but variable observer effect.
- B/C release start offsets were small relative to invocation duration in this
  run.

## What PR6 Does Not Support

PR6 does not establish:

- universal superiority or inferiority of either composition;
- a production strategy switch or automatic strategy selection;
- intrinsic causal slowing or acceleration of `FullProofValidator`;
- causal attribution of the full PRE/IN difference to validation placement;
- an optimal worker count, saturation point, throughput capacity, rate limit,
  retry policy, or PR7 conclusion;
- `PAY`, replay, non-empty-history, or other unrecorded workload behavior; or
- simplification or removal of either idempotency check.

## Evidence Quality and Limitations

The run has strong structural quality for its fixed scope: committed clean
source identity, a valid preflight and smoke, a deterministic 450-sample
schedule, balanced retained cohorts, no exceptions, complete measured
delivery, full thirteen-phase records, and small B/C start offsets.

The evidence remains Level B and environment-qualified. It comes from one
local PostgreSQL environment, one source commit, one command, empty history,
and worker count two. The two compositions change multiple topology properties
at once. PRE performs an additional durable preliminary idempotency lookup and
read-transaction cleanup before validation, while IN performs only the
authoritative in-UoW idempotency check. That distinction is a plausible
explanatory factor but was not isolated causally. Phase intervals overlap,
and sample distributions include ordinary runtime variability.

## PR7 Boundary

PR7 is the next Stage 4B.2 responsibility. It may define a separately reviewed
bounded concurrency characterization, including its credible connection
budget and retained worker levels. PR6 does not vary worker count, characterize
saturation, infer capacity, select a strategy, or authorize production policy.
