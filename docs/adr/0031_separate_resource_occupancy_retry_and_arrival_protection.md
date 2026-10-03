# ADR 0031 — Separate Resource Occupancy, Retry, and Arrival Protection

[← Back to ADR Index](README.md)

## Status

Accepted

## Implementation Status

Accepted as a responsibility-separation decision. PR3's opt-in, shared,
process-local `BoundedWriterAdmission` remains the implemented writer-occupancy
mechanism. No production implementation change is required by this ADR.

Acceptance decides the boundaries below. It does not select or implement a
production retry policy, Rate Limiter, Token Bucket, queue, backoff or jitter
algorithm. The next production mechanism is NOT STARTED.

---

## Context

The [Load / Capacity Protection workstream](../implementation_notes/load_capacity_protection/README.md)
progressed from unprotected characterization through occupancy protection to
retry/refusal characterization. Useful writer throughput, admitted occupancy,
attempt pressure and logical completion proved to be different observations.
A correctly bounded writer region can coexist with rapid refusal and repeated
attempts outside that region.

This ADR promotes the evidenced responsibility separation. The reports retain
ownership of their methods, measurements and historical closeouts; this decision
does not reinterpret their experiment policies as production authorization.

## Evidence Chain

### PR1 — Unprotected degradation

The [PR1 report](../implementation_notes/load_capacity_protection/pr1_unprotected_characterization_report.md)
shows that increasing writer concurrency eventually stops increasing useful
acknowledged-write throughput while writer and PostgreSQL-backed elapsed time
rise. Exploratory median throughput at N=8/16/32 is respectively
1147.71/1096.47/1100.17 accepted writes/s, while writer-call p50 rises from
6.660 to 14.455 to 28.479 ms. This is not a strictly monotonic throughput decline.

Refinement places the descriptive degradation transition around N=10–12;
it establishes neither an exact change point nor universal production capacity.
Application-side PostgreSQL-backed elapsed intervals include client execution,
scheduling and waits; they do not identify server CPU, I/O, WAL or lock costs.

### PR2 — Experimental operating headroom

The [PR2 interpretation](../implementation_notes/load_capacity_protection/pr2_capacity_interpretation.md)
selects N=8 only as the first protected experimental operating point below that
observed degradation region. It retains 95.83% of N=10's refinement median
throughput with lower writer and DB-backed elapsed cost. This is an experimental
design choice, not a production default, proven safety margin or optimal bound.

### PR3 — Explicit shared occupancy mechanism

The [PR3 implementation note](../implementation_notes/load_capacity_protection/pr3_bounded_inflight_admission.md)
and current [capacity primitive](../../src/pipeline/transactional/writer_capacity.py)
establish one explicitly shared, process-local `BoundedWriterAdmission` across
the composing caller's writer population. It attempts nonblocking acquisition
once, invokes the supplied synchronous operation once if admitted, and releases
in `finally` before returning its result or propagating its exception.

The public writer boundary covers the original body, including preliminary
PostgreSQL reads, validation, UOW/finalization and applicable delivery construction.
The configured bound has no numerical default. Separate objects or processes
have separate budgets; open connections and work outside the body are not bounded.

### PR4 — Local protection and refusal displacement

The [PR4 report](../implementation_notes/load_capacity_protection/pr4_protected_vs_unprotected_report.md)
records protected writer-body maximum overlap of eight. In all 24 recorded
protected overload cells at offered N=10/12/16/32, observed public-call overlap
exceeded eight, but only eight of 512 logical items were accepted and 504 were
terminally refused before the first admitted body completed.

UOW and append median elapsed amplification fell at those offered levels.
Commit improved at N=12/16/32 but worsened at N=10; the complete admitted body
also remained slower than at protected N=8. Thus the evidence establishes
scoped local resource protection, not uniformly faster execution or end-to-end
overload resolution. PR4 had no retries and does not establish retry amplification.

### PR5 — Attempt amplification outside bounded writer occupancy

The [PR5 report](../implementation_notes/load_capacity_protection/pr5_retry_refusal_amplification_report.md)
compares five policies under K=128 independent CREATEs per cell, N=32 retained
lanes and one shared bound of eight. Each policy has five recorded cells and
640 logical requests. NO_RETRY permits one attempt; retry-enabled policies permit
at most eight attempts, including the first. These are experiment parameters.

The following are exact recorded totals and ratios, excluding warmups:

| Policy | Attempts | Acknowledged accepted logical requests | Attempt amplification | Logical completion |
|---|---:|---:|---:|---:|
| NO_RETRY | 640 | 40 | 1.0000× | 6.25% |
| IMMEDIATE_RETRY | 4840 | 40 | 7.5625× | 6.25% |
| FIXED_BACKOFF | 2768 | 400 | 4.3250× | 62.5% |
| EXPONENTIAL_BACKOFF | 2600 | 402 | 4.0625× | 62.8125% |
| EXPONENTIAL_BACKOFF_WITH_JITTER | 2292 | 467 | 3.58125× | 72.96875% |

Amplification is attempts / 640; completion is acknowledged accepted logical
requests / 640. Generic terminal observations, including budget exhaustion, are
not useful completion. The report and manifest record maximum protected
writer-body overlap exactly eight in all 30 cells, including warmups and every
policy; the compact CSV independently supports all 25 recorded cells.

Immediate retry exhausted refusal-only budgets before the first admitted body
could release capacity, with no improvement over NO_RETRY's logical completion.
PR5 tested bounded immediate retry, not an unbounded loop or host failure.

Backoff changes both retry spacing and effective pacing of later fresh logical
requests: a retained lane keeps its current request through retry/backoff and
claims fresh work only after a terminal state. The fixed, exponential and
jittered policies accepted respectively 280/322/400 requests on their first
attempt and 120/80/67 after refusal retry. Successful retry recovery therefore
explains only part of their increased completion.

Timing policy materially affects attempt amplification and logical completion
in this fixture. Backoff increased drain time. Jitter's added delay, changed
attempt counts, lane pacing and temporal drift prevent isolating jitter alone
as the cause. Neither exponential backoff nor jitter is established as
universally optimal; no exact production timing parameters follow.

### Evidence provenance and limits

The tracked compact sources used to check the claims above are:

| Evidence | Recorded rows | Identity and interpretation contract |
|---|---:|---|
| [PR1 CSV](../../experiments/load_capacity_protection/results/pr1_recorded_repetitions.csv) | 55 | [PR1 manifest](../../experiments/load_capacity_protection/results/pr1_evidence_manifest.json) |
| [PR4 CSV](../../experiments/load_capacity_protection/results/pr4_recorded_comparisons.csv) | 60 | [PR4 manifest](../../experiments/load_capacity_protection/results/pr4_evidence_manifest.json) |
| [PR5 CSV](../../experiments/load_capacity_protection/results/pr5_recorded_policy_comparisons.csv) | 25 | [PR5 manifest](../../experiments/load_capacity_protection/results/pr5_evidence_manifest.json) |

PR6 checked CSV byte sizes and SHA-256 identities against those manifests and
recomputed the cited recorded aggregates. Raw trajectory, warmup and durable
verification claims are inherited from the tracked reports/manifests, not new
raw-archive checks or live database observations. Compact evidence does not
replace the raw archives. No experiment was rerun.

The finite, local CREATE fixture uses PRE_TRANSACTION/OCC/STRICT FullProof and
retained connections. It does not establish production arrivals, PAY or hot-key
capacity, distributed enforcement, fairness, a production SLO or a universal
bound. Observed application writer overlap is not physical PostgreSQL transaction
overlap. Repetition variation, instrumentation and physical database drift remain
limitations; phase intervals overlap and must not be summed.

## Decision

```text
Resource Occupancy Protection
!= Retry Pressure Protection
!= Arrival-Rate Protection
```

### 1. Keep writer admission responsible for occupancy

`BoundedWriterAdmission` owns simultaneous admitted PostgreSQL writer occupancy
within the explicitly shared process-local population. Preserve its current
acquire-once, execute-once, release lifecycle and explicit configuration.

It does not own retry timing, retry budgets, attempt-rate control, burst shaping,
queueing or general client traffic rate. Capacity admission also remains separate
from Semantic Admission, concurrency correctness and transaction atomicity.

### 2. Keep capacity refusal capacity-specific and authority-neutral

At the admission boundary, `WriterCapacityRefused` communicates only:

> No capacity permit was available at this execution boundary now.

The supplied writer body did not run. This says nothing about a caller's
pre-existing transaction state and does not promise later availability.

```text
WriterCapacityRefused
!= semantic outcome
!= retry authority
!= Stage 4E Re-invocation Authority
!= semantic replanning authority
```

Do not map refusal to semantic invalidity, `STALE_WRITE`, `LOCK_TIMEOUT`, a
fabricated writer result or a completed-invocation handle. Do not classify it as
automatically retryable. Any later retry requires a separate explicit policy
decision; the exception itself carries no such authority.

The existing Stage 4E lifecycle remains intact: authorization is spent before
A2 dispatch; a capacity-refused A2 does not refund that authority, complete A2
normally or authorize A3. PR5 used direct experiment lanes, not Stage 4E.
[ADR 0027](0027_separate_runtime_decision_strategy_and_retry_authority.md)
and the [Stage 4E closeout](../implementation_notes/stage_4e/stage_4e_closeout.md)
retain their authority boundaries. This ADR adds no positive eligibility profile.

### 3. Keep retry policy explicit and separate

Do not add automatic immediate retry at the capacity boundary. In particular,
reject immediate unbounded retry after `WriterCapacityRefused` as an implicit
default. Even bounded immediate retry amplified attempts without improving
completion in PR5; rejecting an unbounded default is an architectural decision,
not a claim that unbounded behavior was measured.

A future explicit retry layer owns the decision whether to retry and the retry
budget and timing. Its design may consider maximum attempt budget, backoff,
jitter, retry timing, refusal classification and logical-request lifetime.
Those responsibilities do not belong inside `BoundedWriterAdmission`,
`PostgresTransactionalWriteSide` or Stage 4E authority evaluation.

The exact owner, API and production policy remain unselected. A later composition
must respect any applicable invocation authority; scheduling policy cannot
refund, reuse or invent it. A repeated attempt and a new semantic plan remain
different responsibilities.

### 4. Keep arrival and attempt-pressure protection separable

A Rate Limiter controls a quantity such as attempts per unit time at a specified
boundary. Writer admission controls simultaneous resource occupancy:

```text
rate != concurrency
```

A rate allowance alone does not ensure a simultaneous writer bound when service
time varies: earlier admitted work can remain active as later starts become
eligible. Conversely, a writer-occupancy bound does not constrain how often
refused callers attempt entry. This is the architectural distinction illustrated
by PR4's refusal displacement and PR5's amplified attempts.

Retry-pressure policy concerns repeated attempts for logical work. Arrival-rate
or burst protection concerns the aggregate stream at its declared boundary,
which may include fresh attempts, retry attempts or both. They can interact and
eventually compose, but neither responsibility automatically owns the other.

Treat attempt-rate and burst protection as another separable concern. Later
evidence may justify rate limiting or pacing. PR5's timing-policy effects do not
uniquely select a general Rate Limiter or Token Bucket, nor do finite closed-loop
arrivals establish a general client-traffic policy. This ADR selects no production
Rate Limiter, token bucket, queue or retry algorithm.

## Alternatives Considered

| Alternative | Disposition and reason |
|---|---|
| Only use a Rate Limiter | Rejected as complete resource protection: rate alone does not guarantee simultaneous writer occupancy when execution duration varies. |
| Only use `BoundedWriterAdmission` | Retained for occupancy; rejected as a complete overload solution because PR4/PR5 leave refusal and attempt pressure outside the writer region. |
| Immediate retry on capacity refusal | Rejected as the automatic default for now: PR5's bounded policy produced 7.5625× attempt amplification with the same 6.25% logical completion as NO_RETRY. This is a fixture-scoped result, not proof about every explicitly reviewed timing policy. |
| Put retry inside `BoundedWriterAdmission` | Rejected: permit ownership and cross-attempt policy are different responsibilities; hidden retries would couple occupancy enforcement to budgets, timing and logical-request lifetime. |
| Select Token Bucket now | Deferred: the evidence establishes a separate attempt-pressure concern, but does not uniquely select token replenishment, a rate, a burst allowance or an enforcement scope. |
| Queue all excess work | Deferred: queue ownership, bounds, timeouts, memory growth and head-of-line behavior need separate design and evidence. The finite retained-lane fixture is not a production queue contract. |

## Consequences

### Positive

- Scarce-resource occupancy remains independently enforceable within its declared
  sharing scope.
- Retry policy can evolve without changing DB writer correctness semantics.
- Arrival shaping can be added and tested independently when justified.
- Capacity refusal cannot silently introduce a retry storm through hidden policy
  at the capacity boundary; caller behavior still needs explicit review.
- Evidence responsibilities remain separable: occupancy, attempts, refusal,
  logical completion and durable effects must each remain visible.

### Costs and Trade-offs

- More explicit policy boundaries require deliberate composition and ownership.
- Callers need overload/refusal handling and retry decisions; fail-fast alone can
  shed useful work before capacity becomes available.
- Waiting or queueing creates latency, queue-growth, timeout and resource-lifetime
  responsibilities; it cannot be added as a neutral implementation detail.
- Rate limiting does not guarantee writer occupancy, and the local occupancy
  bound does not protect open connection count or all caller-side resources.
- Retry backoff may increase completion latency and finite-workload drain time;
  better completion counts alone do not establish an acceptable production policy.

## Next Work and Re-entry Conditions

The next separately authorized implementation/research PR should answer:

> Which explicit retry / attempt-pressure mechanism should be promoted into
> production, if any?

It may compare retry budgets, bounded retry with backoff, jitter, retry-attempt
rate limiting, burst shaping and bounded queueing/backpressure. Its first
responsibility is comparing and selecting among these concerns before broad
production implementation, including the option to promote none.

A proposal must identify the consumer, owner and protected resource; distinguish
fresh logical arrivals from retry attempts; define budget/lifetime and timing or
queue bounds where applicable; and preserve refusal classification, request
identity, writer correctness and Stage 4E authority. Compare attempt amplification,
logical completion, latency/drain, writer occupancy and any waiting or refused work.
Account for retained-lane pacing when deriving a production design from PR5.

Any new experiment, chosen numerical parameters or production implementation
requires separate scope and authorization. This ADR does not start that work,
reopen PR1/PR4/PR5 evidence collection or name the next PR “Rate Limiter”.

## Workstream Status and Non-Goals

PR0–PR5 are COMPLETE; PR6 is ADR COMPLETE. The next production mechanism is
NOT STARTED. The [PR breakdown](../implementation_notes/load_capacity_protection/pr_breakdown.md)
owns delivery navigation.

This documentation-only decision changes no production code, capacity primitive,
writer semantics, Stage 4C/4E evaluation, semantic replanning, experiment machinery,
evidence, tests, database, dependency or environment configuration. No PostgreSQL
execution, experiment rerun or automatic next implementation belongs to PR6.
