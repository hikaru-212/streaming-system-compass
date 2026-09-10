# PR2 — Capacity Interpretation and Operating Headroom

[← Back to Load / Capacity Protection](README.md)

```text
PR0 — COMPLETE
PR1 — COMPLETE / EVIDENCE COLLECTION CLOSED
PR2 — COMPLETE
PR3 — NOT STARTED

First protected experimental point — N=8
First candidate mechanism class — bounded in-flight writer admission
Production mechanism / universal capacity constant — NOT SELECTED
```

This is workstream-specific evidence interpretation and an experimental design
boundary. It introduces no production behavior, stable universal architecture
decision, or authorization to execute PR3 or PR4. Historical PR0/PR1 status and
non-selection statements retain their meaning at those stages' closeouts.

## 1. Purpose

PR2 answers:

> Given the observed unprotected degradation region, what operating-headroom
> conclusion is justified strongly enough to permit a bounded in-flight
> protection experiment?

The evidence supports testing admission bounded at eight simultaneous writer
calls in the characterized composition. This is a policy/design choice for a
reversible experiment, informed by throughput, elapsed cost, and distance from
observed degradation. It is not the result of taking a benchmark argmax.

```text
observed throughput maximum
!= observed degradation transition
!= candidate operating region
!= selected experimental protection point
!= universal production capacity
```

## 2. Evidence Inherited from PR1

The primary interpretation sources are the
[PR1 report](pr1_unprotected_characterization_report.md),
[compact recorded-repetition CSV](../../../experiments/load_capacity_protection/results/pr1_recorded_repetitions.csv),
and [evidence manifest](../../../experiments/load_capacity_protection/results/pr1_evidence_manifest.json).
The [PR1 method](pr1_unprotected_characterization_method.md) defines observation
boundaries; the [PR0 boundary](pr0_research_and_responsibility_boundary.md)
defines responsibility and authority exclusions.

PR2 verified the compact CSV's 13,415 bytes and SHA-256 identity against the
manifest, its 55 recorded rows, run/source identities, declared ordering, and
five repetitions per level. Recomputed medians match every metric in the
report's exploratory and refinement result tables at the displayed precision.
The generating source is `0a68333f86307e96a42e736254b8e047a7284f5a`, with method
`pr1-unprotected-finite-load-v1` and evidence schema version `1`.

The manifest and report identify the same published GitHub Release. Raw archive
availability, archive hashes, and request-level evidence were not independently
revalidated for PR2: no inconsistency in the compact evidence required a raw
download or another experiment. Durable correctness and detailed environment
facts below are inherited from the PR1 report, not newly observed database facts.

| Cohort | N | Accepted writes/s | Writer p50 ms | Business UOW p50 ms | Append admission p50 ms | Commit finalization p50 ms |
|---|---:|---:|---:|---:|---:|---:|
| Exploratory | 1 | 360.35 | 2.441 | 1.503 | 0.499 | 0.269 |
| Exploratory | 2 | 549.90 | 3.474 | 2.018 | 0.588 | 0.328 |
| Exploratory | 4 | 830.17 | 4.630 | 2.855 | 0.801 | 0.467 |
| Exploratory | 8 | 1147.71 | 6.660 | 4.069 | 1.245 | 0.750 |
| Exploratory | 16 | 1096.47 | 14.455 | 8.688 | 2.773 | 1.593 |
| Exploratory | 32 | 1100.17 | 28.479 | 16.923 | 5.386 | 2.806 |
| Refinement | 8 | 1120.96 | 6.892 | 4.260 | 1.268 | 0.825 |
| Refinement | 10 | 1169.68 | 8.395 | 5.090 | 1.587 | 0.942 |
| Refinement | 12 | 1121.37 | 10.488 | 6.362 | 2.022 | 1.206 |
| Refinement | 14 | 1070.99 | 12.823 | 7.731 | 2.453 | 1.481 |
| Refinement | 16 | 1027.18 | 14.682 | 8.896 | 2.850 | 1.644 |

Each value is the median of five per-repetition statistics, calculated before
rounding. Each repetition contains K=512 requests; p50/p95 use the PR1 type-7
estimator within each repetition. This is not a pooled request percentile or
five independent estimates of production capacity. Throughput counts
acknowledged accepted writes over finite offer-to-last-terminal elapsed.

The CSV contains 28,160 recorded acknowledged accepted writes, K=512 in every
row, zero recorded problems, no incomplete cells, completed cleanup, and maximum
writer-call overlap equal to N throughout the recorded cells. PR1 additionally
reports successful durable verification, no duplicate effects, matching
sequence-1 CREATED events and idempotency mappings, and no native or harness
failures across all 33,792 requests including warmups. Maximum overlap does not
prove sustained overlap at N or physical PostgreSQL transaction concurrency.

## 3. Observed Peak vs Degradation Transition

The strongest observed median-throughput region is approximately N=8–10.
Exploratory throughput grows through N=8; N=16 and N=32 add elapsed cost without
improving that median. The slight N=16-to-32 throughput increase means the
exploratory decline is not strictly monotonic.

N=10 has the highest refinement median, 1169.68 writes/s. Here, observed peak
means this aggregate comparison, not the maximum individual repetition. The
next measured refinement point, N=12, falls to 1121.37 writes/s: 4.13% lower,
while writer p50 rises 24.93% and UOW p50 rises 24.98%, relative to N=10.
N=14 and N=16 continue the throughput decline and elapsed-cost growth. This
supports the descriptive transition around N=10–12 inherited from PR1.

It does not establish an exact change point. There are no N=9 or N=11
measurements, and PR2 interpolates neither their throughput nor their latency.
Degradation appears immediately above the peak in the sampled sequence; its
precise onset between samples remains unknown.

Selecting N=10 automatically would overlook:

- Measurement variation: refinement N=8 spans 927.44–1196.02 writes/s; N=10
  spans 1133.76–1182.25. These ranges overlap. Five grouped repetitions do not
  establish a stable optimum, confidence interval, or significance claim.
- Environment scope: local Darwin/arm64 hardware and this PostgreSQL fixture
  do not establish capacity in another deployment or under environment drift.
- Finite closed-loop execution: replenishment slows with writer completion;
  K=512 includes ramp/drain and does not test sustained external arrivals.
- Proximity to degradation: N=10 is at the lower sampled edge of the 10–12
  transition, leaving less concurrency-distance tolerance than N=8.
- Missing operating objectives: no production traffic mix or latency SLA/SLO
  determines whether the extra throughput is worth the added execution cost.
- Cost growth before correctness failure: all calls completed correctly, yet
  more concurrent work increased writer and DB-backed elapsed cost. Correctness
  success alone is insufficient to define a useful operating point.

Protection headroom is therefore a separate design decision. These observations
justify testing that decision without claiming an optimal or safe production
threshold.

## 4. Candidate Comparison: N=8 vs N=10

The direct comparison uses refinement only, avoiding a favorable cross-run
selection. Differences and percentages below use unrounded CSV-derived medians.
The last column is `(N10 - N8) / N8 × 100`; it expresses the change when moving
from eight to ten lanes, not a confidence estimate.

| Metric | N=8 | N=10 | N10 minus N8 | Change relative to N8 |
|---|---:|---:|---:|---:|
| Accepted writes/s | 1120.96 | 1169.68 | +48.72 | +4.35% |
| Writer p50 ms | 6.892 | 8.395 | +1.503 | +21.81% |
| Writer p95 ms | 9.141 | 10.770 | +1.630 | +17.83% |
| Business UOW p50 ms | 4.260 | 5.090 | +0.830 | +19.49% |
| Append admission p50 ms | 1.268 | 1.587 | +0.319 | +25.13% |
| Commit finalization p50 ms | 0.825 | 0.942 | +0.116 | +14.11% |
| Scheduler wait p50 ms | 230.268 | 220.423 | -9.845 | -4.28% |

N=8 retains `1120.961793976746 / 1169.680154160189 = 95.83%` of N=10's
refinement median throughput. Using N=10 as the denominator, the throughput
trade-off is 4.17%, while N=8 has 17.90% lower writer p50, 16.31% lower UOW p50,
20.09% lower append p50, and 12.36% lower commit p50. Those DB-backed elapsed
reductions are material to the experimental objective, not a statistical
significance or production-SLO claim. Phase intervals overlap and must not be
summed; they include application execution, client scheduling, and waits.

N=8 was measured in both runs: exploratory throughput is 1147.71 writes/s with
writer p50 6.660 ms and UOW p50 4.069 ms. It remains in the useful-scaling
region, close to the strongest observed throughput region and below the
descriptive degradation bracket. The two extra admitted calls at N=10 provide
only a modest median throughput gain with substantially higher elapsed cost.

N=10 nevertheless has real advantages: its refinement median throughput is
highest, every repetition completed correctly, scheduler wait is lower, and
its observed throughput range is narrower than N=8's. N=8 is not demonstrated
to be more stable. Its advantage for this experiment is lower measured writer
cost and greater distance from degradation, not dominance on every metric.
Higher finite scheduler wait at N=8 also prevents treating lower writer latency
as proof of better end-to-end latency. PR4 must preserve that distinction.

## 5. Operating Headroom

For this workstream, operating headroom primarily means distance between the
selected admitted writer-work region and the observed degradation region,
together with tolerance sought for run-to-run variation, environment drift,
and workload variation absent from the fixture.

Selecting eight simultaneous writer calls places the experimental bound two
calls below N=10, the lower sampled edge of the descriptive 10–12 transition,
and four below the degraded N=12 sample. The arithmetic
`(10 - 8) / 10 = 20%` describes concurrency-distance from one observed sample
point only. It is not a statistically established 20% capacity reserve,
20% throughput reserve, probability of safety, or measured drift budget.
Tolerance is the design intent; its sufficiency remains to be tested.

`PostgreSQL max_connections - currently used connections` describes connection
availability, not this operating headroom. PR1 retained one connection per lane
and did not establish a connection ceiling or record those server settings.
A writer admission bound does not by itself bound already-open connections or
waiting callers. Resource scope and waiting/refusal ownership require PR3 review.

## 6. Capacity Admission Responsibility

PR1 provides sufficient evidence for a separate capacity-protection
responsibility: increasing observed writer overlap can reduce useful throughput
and amplify elapsed cost while semantic validation, concurrency correctness,
and atomic commits continue to succeed.

| Responsibility | Question answered |
|---|---|
| Semantic validation / Semantic Admission | Is the business transition acceptable, and may the candidate become accepted business truth? |
| OCC / pessimistic concurrency correctness | Does concurrent authoritative state permit this write and its intended stream position? |
| Transaction atomicity | Do the related writes commit or roll back together? |
| Capacity admission | May another unit of writer work enter the currently bounded execution region now? |

Passing capacity admission proves none of the other three properties. Refusal
before writer entry must remain a capacity observation; it must not imply
semantic invalidity, `STALE_WRITE`, `LOCK_TIMEOUT`, validation failure, retry
authorization, or semantic replanning authorization. PR2 defines no production
result type, exception, refusal status, or automatic retry behavior.

The PR0 Stage 4C / Stage 4E constraints remain intact. Capacity handling must
not fabricate a writer result or completed-invocation handle, refund spent
authority, authorize another A2, or alter `AVAILABLE → SPENT` before A2 writer
entry. PR3 must audit placement against those constraints; Stage 4E integration
and semantic replanning are not implicit in the first experiment.

## 7. First Mechanism Candidate

Bounded in-flight writer admission most directly matches the characterized
variable: simultaneous writer work, with actual public-call overlap observed.
The candidate boundary is before the public writer call, covering its complete
execution through return or escaping failure. PR0 records PostgreSQL-backed
PRE work before business-UOW entry, so bounding only the later UOW would not
cover the same execution region that PR1 measured.

| Mechanism class | Controlled variable and evidence boundary |
|---|---|
| Bounded in-flight writer admission | Simultaneously admitted writer calls; directly corresponds to PR1's observed overlap. First candidate class. |
| RPS rate limiting | Starts per time interval; a fixed rate does not directly bound overlap when execution duration varies. PR1 has no open-loop arrival evidence. |
| Token bucket | Admission tokens replenished over time, with a burst allowance; selects rate and burst variables absent from PR1. |
| Burst shaping | Temporal distribution of arrivals or releases; requires arrival/burst objectives beyond the finite backlog. |
| Connection pool tuning | Connection availability, checkout waiting, and reuse; PR1 used retained distinct connections without a pool. |
| External queue policy | Backlog storage, ordering, waiting, expiry, and refusal ownership; finite experiment scheduling does not select those production policies. |

These alternatives may become useful under separately obtained evidence.
PR2 does not declare them unnecessary forever. It selects no semaphore,
CapacityGate implementation, token bucket, RPS target, connection pool size,
external queue policy, or distributed enforcement scope.

## 8. Candidate Experimental Operating Point

**Select N=8 for the first protected experiment**, subject to the PR3 entry
criteria. It is below the observed 10–12 transition, appears in both accepted
runs, retains 95.83% of the strongest refinement median throughput, and reduces
writer and DB-backed elapsed cost while leaving explicit concurrency-distance
headroom below N=10.

The candidate operating region is the measured lower-cost area around the
N=8 sample within the observed N=8–10 useful-throughput region. Only N=8 is
selected for experimentation; unmeasured neighboring values receive no implied
qualification. This is not a production default or a proven optimal setting.
Run variation, especially at N=8, remains a reason to validate rather than a
reason to assert a safety margin numerically.

PR4 must be allowed to find no benefit or reject this choice. If useful
throughput falls materially, DB-backed amplification persists, or waiting is
merely moved without achieving the reviewed objective, the experiment does not
establish successful protection. Reconsideration must retain that negative
evidence rather than retune silently until a favorable comparison appears.

## 9. PR3 Entry Criteria

PR2 resolves the evidence-interpretation gate. PR3 remains NOT STARTED and
requires separate authorization and a fresh source-grounded placement audit.
Implementation may proceed only with all of these conditions satisfied:

| Criterion | PR2 basis / required PR3 obligation |
|---|---|
| 1. Observed unprotected degradation | The measured 10–12 transition and higher-level cost amplification supply the bounded evidence. No exact knee is required. |
| 2. Useful lower-cost operating region | N=8 retains 95.83% of N=10 median throughput with lower writer/UOW/append/commit elapsed cost; accept the documented finite-wait trade-off. |
| 3. Direct control-variable mapping | Bound simultaneous public writer calls, not RPS or only business-UOW overlap. Define sharing scope across independent writer owners and retain exclusive per-lane connection ownership. |
| 4. Separate capacity responsibility | Review entry/exit placement and waiting/refusal representation without changing semantic validation, concurrency verdicts, transaction ownership, or Stage 4C / Stage 4E authority. |
| 5. No new retry/replanning authority | A refused attempt must not manufacture semantic outcomes, completed-invocation evidence, another invocation, or refund/reuse of authority. |
| 6. Reversible and testable mechanism | Keep an explicit unprotected comparison path. Demonstrate the overlap bound, release on normal and exceptional exits, no leaked admission slots, and visible waiting/refusal without production semantic changes. Review cancellation and ownership where applicable. |
| 7. Comparable later validation | Preserve reuse of PR1's finite K, retained-lane topology, measurement boundaries, outer ledger, provenance, and durable verification. PR4 must distinguish offered execution opportunity from admitted writer overlap. |

The experimental objective is retaining useful throughput with less writer and
DB-backed elapsed amplification, accepting that pressure may move before entry.
PR3 must concretely define the bounded resource scope, configuration/bypass,
waiting versus refusal ownership, and failure handling before implementation.
PR2 establishes their constraints, not a completed implementation audit. No
production policy or live PostgreSQL execution is authorized by this note.

## 10. PR4 Validation Contract

PR4 must compare equivalent protected and unprotected offered work using the
existing PR1 characterization machinery, with separately reviewed extensions
only where needed to observe admission. Its run plan and database execution
require separate approval under the PR1 live-run gate.

- Offer execution opportunities above eight, including measured degradation
  levels, while keeping K, composition, identities, observation boundaries,
  and relevant topology/environment conditions comparable. Merely configuring
  eight workers would not test protection under excess offered concurrency.
- Derive actual overlap from writer entry/exit intervals. The protected case
  must stay at or below eight even when more than eight callers seek entry;
  the unprotected comparison must credibly exercise the higher offered level.
- Reconcile planned, offered, dispatched, waiting, writer-entered, completed,
  refused, failed-before-entry, and residual work. Preserve unfinished calls
  and ambiguous acknowledgements. Requests must not disappear or be silently
  replaced/retried to maintain a success count.
- Retain acknowledged accepted throughput using the finite workload timing
  boundary, plus writer/DB-backed p50/p95, scheduler wait, separately visible
  capacity wait, total outer latency, refusals, failures, and residual work.
  Do not fold admission waiting into writer-call elapsed. Any new timestamps
  must distinguish admission waiting from the existing dispatch-to-entry delay.
- Determine whether useful throughput is preserved and DB-backed amplification
  decreases, and whether waiting moves before entry or pressure is merely
  relocated without benefit. Inspect repetitions and distributions, not only
  accepted-call latency or one favorable median. Agree comparison tolerances
  before execution; PR2 invents no SLO or statistical success threshold.
- Preserve unchanged correctness: exact accepted CREATE effects and matching
  idempotency linkage, no duplicates, and no accepted effect for pre-entry
  refused work. Keep durable reconciliation separate from acknowledgement;
  observed correctness does not grant retry or replanning authority.
- Record measured/unmeasured surfaces, instrumentation changes, connection
  ownership, grouped ordering/time drift, and logical versus physical database
  state. Expose any necessary differences from PR1 instead of treating a later
  environment as identical to the archived baseline.

A mechanism that bounds overlap may still fail the performance objective.
Protection need not increase throughput, and moving waiting/refusal earlier is
an intentional possible effect, not automatically a benefit. Connection counts,
waiting-caller resources, and end-to-end delay may remain pressured even when
writer execution is bounded. PR4 must report those trade-offs and may conclude
that the mechanism merely relocates pressure without sufficient benefit.

## 11. Non-Claims / Limitations

- Local Darwin/arm64, 12 logical CPUs, PostgreSQL 16.15 fixture; no universal
  system or PostgreSQL capacity constant.
- Independent CREATE only, PRE_TRANSACTION + OCC + STRICT FullProof; no PAY,
  hot-key contention, pessimistic capacity fixture, mixed production workload,
  or semantic-replanning characterization.
- Finite closed-loop K=512 with retained per-lane connections and one control
  connection; no connection pool, open-loop arrival process, sustained external
  RPS, burst model, or production queueing evidence.
- Five grouped recorded repetitions per level, different run conditions over
  time, and no counterbalancing or host-interference trace. Observed variation
  and time drift prevent an exact knee, statistical reserve, or stability claim.
- Incomplete physical DB reset: scoped row cleanup does not restore WAL, cache,
  dead-tuple state, or global-position allocation. Logical equivalence does not
  imply identical physical conditions.
- Writer-call overlap is application overlap, not physical database CPU or
  transaction concurrency. UOW is an application interval; append includes
  persistence/translation. Overlapping phase durations cannot be summed.
- No server CPU/I/O/WAL root-cause proof. Python scheduling, observation, and
  measurement overhead remain possible contributors; no instrumentation-off
  comparison isolates them. The evidence supports an experiment at the measured
  application boundary without proving server saturation.
- No native failures in PR1 establish severe-overload failure frequency or
  ambiguous-commit behavior; no writer deadline or cancellation guarantee is
  inferred from a connection-setup timeout.
- No production SLA/SLO, proven safe operating limit, distributed admission
  contract, or universal setting. N=10 is not an established true knee; eight
  is a first experimental bound, not a permanent production limiter value.

## 12. PR2 Conclusion

The tracked evidence is internally consistent for this interpretation. PR2
selects N=8 as a defensible first protected experimental point and bounded
in-flight writer admission as the mechanism class most directly aligned with
PR1. This conclusion separates useful-throughput preservation and lower
execution cost from correctness, authority, and universal capacity claims.

PR0 and PR1 remain COMPLETE; PR2 is COMPLETE as interpretation ready for human
review. PR3 is NOT STARTED. The entry criteria and PR4 comparison contract
constrain later work; they do not start it. No production implementation,
CapacityGate, semaphore, rate limiter, token bucket, PostgreSQL execution,
load rerun, or raw-evidence modification is part of PR2.
