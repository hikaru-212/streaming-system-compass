# Stage 4B.5 Runtime Governance Overhead Characterization Report

[← Back to Stage 4B.5](README.md)

## Status

```text
canonical micro characterization
= COMPLETE

micro bootstrap-estimand correction
= COMPLETE / PUBLISHED AS SEPARATE IMMUTABLE DERIVED EVIDENCE

canonical PostgreSQL characterization
= COMPLETE

Stage 4B.5 runtime-governance overhead characterization
= COMPLETE
```

This report answers one bounded question:

```text
How much incremental runtime cost does the Stage 4B.5 machine-readable
governance path introduce in the measured Order workload?
```

In the semantic-path micro characterization, evidence-aware propagation added
about `1–2 µs`, explicit semantic composition added about `13 µs`, and the full
path added about `14–15 µs`. In the PostgreSQL characterization, the historical
source control had median latency of about `1–3 ms`; the full path added median
estimates of about `50–100 µs`, or `2.18–6.79%` against the corresponding A
batch baselines. The measured cost is therefore non-zero and visible, but it is
tens of microseconds rather than milliseconds in this workload.

These findings characterize this fixed workload and environment. They do not
establish universal production performance, an SLO, statistical significance,
or permission to weaken governance.

---

## Comparison Surfaces

The numerical comparisons use three surfaces produced under each new fixed
characterization environment:

```text
A
= historical Stage 4B.2 source behavior reconstructed from the pinned Git blobs

B
= current Stage 4B.5 evidence-aware validation/runtime/write-side propagation

C
= B followed by Stage 4A SemanticOutcome mapping and PR7 terminal
  rule-refinement composition
```

The comparison meanings are:

```text
B-A_END_TO_END
= matched block/permutation batch-median comparison

C-B_COMPOSITION_LAP
= directly timed same-invocation C composition lap

C-A_END_TO_END
= matched block/permutation batch-median comparison

C-B_TOTAL_SECONDARY
= noise-sensitive comparison of independently executed full B and C paths
```

Repetition indexes are schedule coordinates, not paired invocations. Historical
Stage 4B.2 committed timings are context only; this report does not subtract
those historical absolute values from a new B or C result.

---

## Micro Characterization

The micro run contains `216,000` recorded samples across four unpooled
CREATE/PAY × ACCEPTED/VALIDATION_BLOCKED scenarios. Times in the following
tables are microseconds. Absolute values are raw invocation distributions;
comparison values are distributions of the declared block/permutation units.

### Absolute latency

| Scenario | A p50 | A p95 | A p99 | B p50 | C p50 |
| --- | ---: | ---: | ---: | ---: | ---: |
| CREATE accepted | 3.292 | 4.667 | 12.375 | 4.458 | 17.667 |
| CREATE validation blocked | 2.292 | 3.250 | 9.250 | 4.125 | 17.584 |
| PAY accepted | 3.375 | 4.792 | 12.583 | 4.500 | 18.166 |
| PAY validation blocked | 2.334 | 3.333 | 9.250 | 4.125 | 18.125 |

The A median is only `2.292–3.375 µs`. That small denominator is essential to
interpreting the relative results.

### Incremental latency

All `95% CI` values in this table come from the immutable
bootstrap-estimand correction artifact, not from the superseded bootstrap
intervals in the original micro `aggregates.json`.

| Scenario | B-A p50 (95% CI) | C-B composition p50 (95% CI) | C-A p50 (95% CI) | C-A relative p50 |
| --- | ---: | ---: | ---: | ---: |
| CREATE accepted | 1.166 (1.125–1.167) | 12.833 (12.667–13.042) | 14.250 (14.000–14.542) | 431.3% |
| CREATE validation blocked | 1.833 (1.791–1.834) | 13.083 (12.916–13.333) | 15.125 (14.917–15.667) | 653.7% |
| PAY accepted | 1.125 (1.083–1.167) | 13.167 (13.042–13.292) | 14.666 (14.500–14.833) | 433.8% |
| PAY validation blocked | 1.792 (1.750–1.834) | 13.292 (13.083–13.542) | 15.417 (15.209–15.709) | 656.1% |

The evidence-aware B path therefore adds roughly `1–2 µs` at this boundary.
The clearer incremental component is the directly timed C composition lap at
roughly `13 µs`. Together they produce a roughly `14–15 µs` C-A estimate.

The approximately `400–650%` C-A relative medians do not mean that hundreds of
microseconds were added. They are large because the A denominator is only
`2–3 µs`. Micro relative percentages must be read together with the absolute
microsecond values.

Micro p99 is reported because the fixed raw population supports the
predeclared micro p99 treatment. Across the twelve A/B/C distributions, IQR is
`0.291–2.333 µs`, MAD is `0.124–1.167 µs`, and the span of per-block absolute
medians is `0.167–2.291 µs`; the larger dispersion belongs mainly to C.

### Bootstrap correction history

The original timing namespace remains immutable. Its raw samples, timing laps,
batch summaries, batch comparisons, empirical p50/p95/p99, IQR, MAD, scenario
semantics, provenance, and timing boundaries remain accepted.

The original generated bootstrap logic first reduced the six permutation units
inside a block to one block median, which changed the estimand. The separate
correction artifact uses a recorded-block cluster bootstrap: it samples blocks
with replacement, retains all six permutation units in every selected block,
reconstructs the pooled population, and computes that population's empirical
nearest-rank median. Only bootstrap confidence intervals were superseded. No
timing execution was rerun and no original evidence file was changed.

---

## PostgreSQL Characterization

The PostgreSQL run contains `43,200` recorded samples across eight unpooled
CREATE/PAY × PRE_TRANSACTION/IN_TRANSACTION ×
ACCEPTED/VALIDATION_BLOCKED cells. PAY accepted-history setup, reset, and
verification remained outside timing. PostgreSQL p99 is withheld according to
the predeclared fixed-population methodology.

### Eight-cell result

`A p50` is in milliseconds. All deltas and confidence intervals are in
microseconds. The C-B column is the primary same-invocation composition lap.

| Scenario | A p50 | B-A p50 (95% bootstrap CI) | C-B composition p50 (95% bootstrap CI) | C-A p50 (95% bootstrap CI) | C-A relative p50 |
| --- | ---: | ---: | ---: | ---: | ---: |
| CREATE / PRE / accepted | 2.904 ms | 9.083 µs (-19.333–44.125) | 57.250 µs (52.875–62.459) | 61.584 µs (9.583–122.000) | 2.18% |
| CREATE / PRE / validation blocked | 1.202 ms | 21.708 µs (9.875–40.209) | 47.125 µs (45.167–49.833) | 49.542 µs (36.792–72.458) | 4.24% |
| CREATE / IN / accepted | 2.192 ms | 50.834 µs (22.292–75.084) | 50.291 µs (46.667–53.791) | 76.916 µs (32.541–128.208) | 3.41% |
| CREATE / IN / validation blocked | 1.478 ms | 21.208 µs (7.042–37.834) | 49.458 µs (47.833–51.042) | 70.500 µs (54.167–88.833) | 5.02% |
| PAY / PRE / accepted | 2.740 ms | -15.959 µs (-48.041–51.916) | 69.625 µs (64.667–74.208) | 97.000 µs (39.084–140.959) | 3.78% |
| PAY / PRE / validation blocked | 1.053 ms | 23.458 µs (1.083–42.042) | 55.875 µs (50.666–59.750) | 77.000 µs (54.208–90.124) | 6.79% |
| PAY / IN / accepted | 2.384 ms | 30.083 µs (-3.000–65.583) | 67.833 µs (60.125–70.500) | 98.584 µs (67.874–124.668) | 3.86% |
| PAY / IN / validation blocked | 1.340 ms | 30.500 µs (5.708–47.958) | 58.500 µs (54.958–61.584) | 80.458 µs (58.083–94.708) | 5.94% |

The A median varies from `1.053 ms` to `2.904 ms` by command, transaction
placement, and terminal path. B-A medians range from `-15.959 µs` to
`50.834 µs`. Three accepted-path B-A intervals—CREATE/PRE, PAY/PRE, and
PAY/IN—include zero. The PAY/PRE accepted B-A median is negative, and many
individual block/permutation differences are negative in every end-to-end
comparison family. These are retained measurement outcomes from independently
executed surfaces. They are neither clamped nor interpreted as true speedups.

The directly timed C composition median is `47.125–69.625 µs`. The full C-A
median estimate is `49.542–98.584 µs`, or `2.18–6.79%` against its matched A
batch baseline. The secondary independent full-path C-B medians range from
`27.583 µs` to `111.458 µs`; they remain descriptive and noise-sensitive, not
the primary estimate of composition cost.

PostgreSQL variation is visibly larger than the small B-A effect. Across the
24 A/B/C absolute distributions, invocation IQR is `0.225–0.725 ms`, MAD is
`0.098–0.343 ms`, and the span of per-block absolute medians is
`0.193–0.955 ms`. That variation can dominate evidence-propagation differences
of only a few tens of microseconds. No confidence interval here is described as
a statistical-significance result.

---

## Cross-Layer Interpretation

The micro and PostgreSQL relative percentages are not contradictory. They use
radically different denominators:

```text
micro A baseline
≈ 2–3 µs

PostgreSQL A baseline
≈ 1–3 ms
```

A `14–15 µs` micro C-A delta is therefore several times the micro A baseline,
while a `50–100 µs` PostgreSQL C-A estimate is only low- to mid-single-digit
percent of the millisecond-scale PostgreSQL baseline. Percentages must not be
compared across these layers without preserving those denominators.

The PostgreSQL-path C composition medians (`47–70 µs`) are also higher than the
micro composition medians (about `13 µs`). The evidence establishes that the
same explicit composition boundary measured differently in these two workload
contexts. It does not isolate an object-level cause for the difference; process
state, surrounding workload, cache state, scheduling, and timer/runtime context
remain plausible contributors.

The bounded conclusion is:

- The B-A evidence-aware validation/runtime/write-side propagation difference is small compared with the PostgreSQL execution surface and can be dominated by database/runtime noise.
- Explicit semantic composition is the clearer incremental cost measured in this characterization.
- The full governance path adds tens of microseconds, rather than milliseconds, in this measured Order workload.

This conclusion is limited to the fixed workload, environment, and implementation path characterized in this report. It does not establish universal production performance behavior or imply that governance overhead is negligible under all workloads.

---

## Method and Evidence Integrity

Both layers used five untimed warmup blocks/cycles, 30 recorded blocks, all six
A/B/C order permutations under fixed schedule seed `4500617`, no adaptive
extension, and empirical nearest-rank percentiles. Micro used 100 repetitions
per permutation; PostgreSQL used 10. The comparison unit was the
scenario/block/permutation batch median, giving 180 units per scenario and
comparison. Confidence intervals used 2,000 fixed-seed recorded-block cluster
bootstrap repetitions and retained every within-block permutation unit.

A executed exact historical Git blobs pinned to commit
`0bd2f515bcc49e8e1f0e9d2f9dba4a294adadd0d` in an isolated subprocess. The
pinned validator, runtime, and PostgreSQL writer blobs and SHA-256 identities
are recorded in both manifests. B and C used the same current production source
within each run; the recorded production `src` tree identity is
`e608a3214b636a68ff1f2a2e39f726cd99906909` in both canonical runs.

All A/B/C workers recorded the same CPython `3.12.7` executable. The
PostgreSQL run used the guarded `_test` database with database OID `181689`,
PostgreSQL `160014`, psycopg `3.3.4`, `read committed` isolation,
`autocommit=false`, and migrations through `007`. Those facts match across the
A/B/C workers. The timer was monotonic, non-adjustable
`time.perf_counter_ns()` backed by `mach_absolute_time()`, with recorded
resolution of about `41.7 ns`.

YAML parsing was not measured because no production YAML parsing exists.
Detailed Stage 4B.2 measurement and trace wrappers were not used as the primary
end-to-end timer.

---

## Limitations

- This is a single-host, fixed-workload characterization, not a universal
  production-performance claim.
- The A surface preserves exact historical bytes for the three protected
  modules but shares audited-unchanged transitive modules from the current
  checkout.
- A/B/C execute in separate processes; runtime scheduling, garbage collection,
  CPU frequency, thermal state, background activity, and cache state can
  contribute noise.
- B-A and C-A are matched batch comparisons, not per-invocation causal pairs.
- The same-invocation C composition lap is the primary C-B evidence; independent
  total B/C subtraction is secondary.
- Accepted and blocked paths, commands, and transaction placements remain
  unpooled; no result is generalized across them.
- Negative differences are measurement outcomes, not proof that Stage 4B.5 is
  faster.
- Confidence intervals characterize the fixed bootstrap procedure; this report
  does not claim statistical significance.
- Historical Stage 4B.2 recorded values are not direct numerical controls.

---

## Evidence References

- [Characterization method](runtime_governance_overhead_method.md)
- [Canonical micro manifest](../../../experiments/stage4b5/evidence/runtime-governance-overhead-micro/stage4b5-runtime-overhead-micro-20260815-e3193f3/manifest.json)
- [Canonical micro aggregates](../../../experiments/stage4b5/evidence/runtime-governance-overhead-micro/stage4b5-runtime-overhead-micro-20260815-e3193f3/aggregates.json)
- [Micro bootstrap correction manifest](../../../experiments/stage4b5/evidence/runtime-governance-overhead-micro-corrections/stage4b5-runtime-overhead-micro-20260815-e3193f3/bootstrap-estimand-v1/manifest.json)
- [Corrected micro bootstrap intervals](../../../experiments/stage4b5/evidence/runtime-governance-overhead-micro-corrections/stage4b5-runtime-overhead-micro-20260815-e3193f3/bootstrap-estimand-v1/bootstrap_ci_corrections.json)
- [Canonical PostgreSQL manifest](../../../experiments/stage4b5/evidence/runtime-governance-overhead-postgres/stage4b5-runtime-overhead-postgres-20260815-543b98f/manifest.json)
- [Canonical PostgreSQL aggregates](../../../experiments/stage4b5/evidence/runtime-governance-overhead-postgres/stage4b5-runtime-overhead-postgres-20260815-543b98f/aggregates.json)
