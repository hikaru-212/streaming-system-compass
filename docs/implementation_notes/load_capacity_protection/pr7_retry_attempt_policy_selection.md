# PR7 — Retry / Attempt-Pressure Policy Selection

[← Back to Load / Capacity Protection](README.md)

```text
PR0–PR6 — COMPLETE (PR6 architectural separation accepted in ADR 0031)
PR7 — COMPLETE / policy selection internally resolved; ready for human review
PR8 production implementation — NOT STARTED

Selected production policy class — opt-in bounded retry with delayed backoff
Production numerical policy — NOT SELECTED
```

## 1. Purpose

Which smallest explicit retry / attempt-pressure policy class is justified for
the first production implementation?

**Select an explicit finite retry budget plus delayed retry/backoff**, applied
only by a configured caller/orchestration policy to verified pre-body capacity
refusal. Preserve a disabled, no-retry path. Select no mandatory fixed or
exponential schedule and no production numerical values. Defer jitter, rate
limiting and queueing from the first implementation.

This is a workstream-specific policy selection under
[ADR 0031](../../adr/0031_separate_resource_occupancy_retry_and_arrival_protection.md).
It is not an implementation, deployment decision, new accepted ADR or claim that
all callers should retry. Observations below retain their fixture scope; the
policy constraints are PR7's explicitly identified interpretation of them.

## 2. Evidence Inherited from PR4 / PR5

The complete current workstream documentation was read from PR0 through PR6,
including methods, reports, the implementation note and delivery navigation.
The immediate quantitative basis is the
[PR4 report](pr4_protected_vs_unprotected_report.md),
[PR5 method](pr5_retry_refusal_amplification_method.md),
[PR5 report](pr5_retry_refusal_amplification_report.md),
[tracked PR5 CSV](../../../experiments/load_capacity_protection/results/pr5_recorded_policy_comparisons.csv)
and [PR5 manifest](../../../experiments/load_capacity_protection/results/pr5_evidence_manifest.json).
Historical method/status banners retain their original meaning; reports and
current navigation own subsequent closeout status.

PR5 recorded five cells per policy, each with K=128 independent CREATEs, N=32
retained lanes and one shared writer bound of eight. Each policy therefore has
640 recorded logical requests. NO_RETRY permits one attempt; all retry-enabled
conditions permit at most eight attempts, including the first. Warmups are
excluded from the following exact totals.

| Policy | Attempts | Accepted logical requests | Attempt amplification | Logical completion | Accepted first / after refusal retry |
|---|---:|---:|---:|---:|---:|
| NO_RETRY | 640 | 40 | 1.0000× | 6.25% | 40 / 0 |
| IMMEDIATE_RETRY | 4840 | 40 | 7.5625× | 6.25% | 40 / 0 |
| FIXED_BACKOFF | 2768 | 400 | 4.3250× | 62.5% | 280 / 120 |
| EXPONENTIAL_BACKOFF | 2600 | 402 | 4.0625× | 62.8125% | 322 / 80 |
| EXPONENTIAL_BACKOFF_WITH_JITTER | 2292 | 467 | 3.58125× | 72.96875% | 400 / 67 |

Amplification is attempts / 640; completion is acknowledged accepted logical
requests / 640. Budget exhaustion is terminal accounting, not useful completion.
All 25 recorded cells have maximum protected writer-body overlap exactly eight.
The report/manifest additionally establish eight across all 30 cells, including
warmups. This is application body overlap, not physical PostgreSQL transaction
concurrency or server utilization.

PR7 recomputed the recorded counts, ratios, medians and ranges from the CSV and
matched the manifest. Its 25 rows, 53 columns, execution order, generating source
`5084b12a177db4bdebd9dfad5597fe229677ed15`, size of 13,019 bytes and SHA-256
`b05bef39410c305033f1b6691d2f3dd8f22ac04b46dd01a87401bda09dfca5fe`
were verified. Raw trajectories, warmup overlap and durable verification remain
inherited report/manifest evidence; no raw archive, Release or database was
rechecked and no experiment was rerun.

PR4's [CSV](../../../experiments/load_capacity_protection/results/pr4_recorded_comparisons.csv)
and [manifest](../../../experiments/load_capacity_protection/results/pr4_evidence_manifest.json)
were also checked for identity and the relevant counts: all 24 recorded protected
overload cells at N=10/12/16/32 accepted eight of 512 logical items and terminally
refused 504 before the first protected body completed. PR4 had no retries. This
is evidence of fail-fast shedding and pressure displacement, not retry recovery
or a production queue evaluation.

The PR5 finite, closed-loop schedule retains each logical request on its lane
until terminal. Backoff changes both retry timing and that lane's access to
later fresh requests. The first/after-retry counts above rule out attributing
all additional completion solely to recovery of refused requests. They also
prevent a pure jitter-only causal interpretation.

Limits remain local independent CREATE, PRE_TRANSACTION/OCC/STRICT FullProof,
retained connections, one parameter set per condition, one jitter seed and five
recorded repetitions. Instrumentation, scheduling and database drift remain
competing explanations. No production arrival distribution, PAY/hot-key result,
fairness, distributed enforcement, host-failure cause or production SLO follows.

## 3. Decision Constraints from ADR 0031

```text
Resource Occupancy Protection
!= Retry Pressure Protection
!= Arrival-Rate Protection

WriterCapacityRefused
!= automatic retry authority
```

`BoundedWriterAdmission` retains acquire-once, execute-once, release ownership
for admitted synchronous writer bodies sharing its process-local instance.
It controls occupancy, not starts per unit time, backlog or retries. A per-request
retry budget and backoff do not establish an aggregate attempt-rate ceiling.

Capacity refusal is neither a semantic outcome nor `STALE_WRITE`, `LOCK_TIMEOUT`,
validation failure or semantic replanning authority. PR7 cannot refund, reuse
or invent Stage 4E authority. The accepted ADR's architectural boundary remains
unchanged; this note answers its next policy-selection question.

## 4. Retry Budget

**Decision: every enabled production retry policy in this first mechanism must
have an explicit finite per-logical-request attempt budget.**

PR5's immediate retry added 4,200 recorded retries while acceptance remained
40/640. Every refusal-only request exhausted its already finite experimental
budget before an admitted body could release capacity. This is sufficient
evidence for a conservative production invariant preventing unrestricted
attempt multiplication. It does not empirically prove an unbounded loop's
behavior: PR5 tested bounded retry, not unbounded retry or host failure.

```text
retry budget = how many additional attempts may exist?
backoff schedule = when may an eligible additional attempt occur?
```

PR8 must make the counting convention explicit. With a finite maximum M total
attempts including the first, at most M−1 additional attempts may be dispatched.
The initial attempt counts toward M; every dispatched retry consumes another
unit even if refused. No refund or budget reset follows refusal. A configuration
expressed as additional retries must preserve the equivalent total ceiling.
These are counting rules, not a selection of M.

Budget custody belongs to one live logical-request lifecycle, with serial
attempts and explicit exhaustion. Constructing a fresh controller or nesting
retry layers must not silently refresh that lifecycle's budget. Backoff alone
cannot replace this bound, and the bound alone does not provide useful timing.
Finite attempts also do not bound a stuck writer's elapsed time, total waiting
callers, retained connections or aggregate traffic. Durable budget continuity
across restarts is not selected here.

## 5. Retry Timing / Backoff

**Decision: select intentional delayed retry/backoff over immediate retry for
the enabled first production policy.**

Under the same experimental attempt ceiling, fixed, exponential and jittered
backoff reduced amplification from immediate retry's 7.5625× to
4.3250×, 4.0625× and 3.58125×, while completion rose from 6.25% to
62.5%, 62.8125% and 72.96875%. This supports selecting the shared delayed-policy
class. Retained-lane pacing qualifies the reason for the improvement and limits
production transfer; it does not turn immediate retry into an equally supported
first choice for this refusal-recovery objective.

Waiting has a cost. The median of five per-cell drain times is 19.214 ms for
NO_RETRY, 86.108 ms for IMMEDIATE_RETRY, 123.227 ms for FIXED_BACKOFF,
118.890 ms for EXPONENTIAL_BACKOFF and 132.046 ms for the jittered condition.
These values were recomputed from the CSV; they are not pooled request latency
or production targets. Completion gain must be assessed with latency, waiting
resources, refusals and exhaustion, not accepted count alone.

Fixed backoff already demonstrates delayed-policy benefit. Exponential backoff
records fewer attempts, but only 402 versus 400 accepted requests; this single
parameter comparison does not establish that an exponential shape is necessary
or universally better. PR7 therefore stops at **bounded retry with backoff**.
Selection of a concrete fixed or exponential schedule remains a PR8 design and
configuration obligation within that class, before implementation of that choice.

An enabled schedule must express a positive intentional delay following eligible
refusal, with finite configured values and a defined maximum delay. Incidental
call/observer overhead does not count as selected backoff. Dispatch must respect
the declared monotonic eligibility time after the prior call has ended; waiting
occurs outside writer capacity ownership. Neither a per-request delay nor a
delay cap implies rate limiting or an end-to-end deadline.

## 6. Jitter

**Decision C: DEFER jitter from the first production implementation pending a
more isolated comparison.** It is neither mandatory nor a required configurable
feature of PR8.

The jittered condition has the lowest recorded amplification and highest
completion among the tested retry policies. That is positive candidate evidence,
not evidence that randomization itself supplied the gain. It adds delay to the
exponential schedule, changes attempt counts and retained-lane pacing, and was
tested with one deterministic jitter seed. Its accepted first/after-retry split
is 400/67, versus 322/80 for exponential backoff. PR5 report Section 8 also
qualifies concentration by window width; no universal dispersion claim follows.

Making jitter mandatory would require stronger evidence of necessity than this
comparison supplies. Requiring a configurable extension now would add a
distribution, cap and randomness contract beyond the smallest selected class.
PR8 does not implement jitter; adding it requires separately reviewed evidence
and scope. Re-entry should separate added delay from dispersion and control
fresh-request pacing, while preserving
logical completion, amplification and latency observations. This describes an
evidence question, not authorization to rerun PR5 or start a new experiment.

## 7. Rate Limiting

**Decision: DEFER both retry-attempt rate limiting and general arrival/rate
protection. No Rate Limiter or Token Bucket is selected.**

| Concern | Responsibility and missing selection evidence |
|---|---|
| Retry-attempt Rate Limiter | Bounds aggregate retry starts per time interval within an explicit population. PR5 establishes attempt amplification outside writer occupancy, but did not compare a backoff-only production policy with backoff plus retry-attempt rate limiting. No incremental benefit, rate, burst allowance, enforcement scope or exhaustion behavior is established. |
| General ingress/API Rate Limiter | Controls fresh external arrivals, possibly alongside retries, at a declared ingress boundary. PR5's finite retained-lane fixture establishes no general ingress/API traffic failure mode or production arrival envelope. |
| Token Bucket | Chooses replenishment and burst semantics for a rate-control responsibility. Neither PR4 nor PR5 compares algorithms or uniquely supports those semantics or numerical settings. |

Backoff may reduce observed attempt pressure without guaranteeing an aggregate
rate. That remaining limitation preserves a future evidence gate; it does not
uniquely select a limiter now. Re-entry needs a named consumer/boundary, observed
residual pressure under the selected retry policy, a comparative benefit and
explicit rate/burst/sharing requirements. General ingress protection also needs
evidence about fresh arrivals. No hidden rate/burst control belongs in PR8.

## 8. Queueing / Backpressure

**Decision: DEFER a bounded queue/backpressure mechanism.**

PR4's 504/512 refusal outcome makes retention of excess finite work a meaningful
alternative to shedding. PR4 did not test a production queue, and PR5's retained
lanes do not supply one. Retry waiting retains the current logical request; it
does not select how a service accepts and owns a backlog of fresh requests.

A queue proposal must identify ownership and admission, queue bound, timeout,
memory growth, head-of-line behavior, cancellation and fairness, together with
connection/transaction lifetime while waiting. Current evidence does not resolve
these choices or compare their benefit and latency/resource cost against the
selected policy. A backoff waiter must not silently become an unbounded queue,
background worker service or replacement for fail-fast writer admission.

## 9. Candidate Dispositions

Dispositions apply to the first production retry-pressure scope. SELECT can
identify the disabled mode as well as the enabled policy class; it does not
require retry for every caller. DEFER means a concrete selection is unresolved
or unnecessary for this first class, not that the mechanism can never be useful.
No arbitrary scores or universal policy ranking are used.

| Candidate | Evidence support | Responsibility owned | Benefit | Unresolved risk | Disposition |
|---|---|---|---|---|---|
| A. No production retry | NO_RETRY: 1.0000× attempts, 6.25% completion. | Caller declines additional attempts; occupancy protection continues separately. | No added retry pressure or wait; reversible disabled baseline. | Excess finite work remains refused; does not provide enabled refusal recovery. | SELECT as disabled/unconfigured mode, not the enabled recovery mechanism. |
| B. Bounded immediate retry | 7.5625× attempts, unchanged 6.25% completion. | Finite attempt count without intentional delay. | Explicit ceiling prevents unrestricted repetition. | Rapid budget consumption before capacity recovery; no observed completion benefit. | REJECT for the first enabled policy. |
| C. Bounded retry + fixed backoff | 4.3250× attempts, 62.5% completion. | Budget plus constant per-request retry delay. | Demonstrates that delayed retry need not be exponential to improve this fixture. | Delay adequacy, synchronization, waiting cost and lane pacing remain deployment-dependent. | DEFER exact schedule selection; admissible realization of the selected class, not a frozen production choice. |
| D. Bounded retry + exponential backoff | 4.0625× attempts, 62.8125% completion. | Budget plus increasing, capped per-request delay. | Fewer observed attempts than fixed under tested parameters. | Shape necessity and production base/cap are not established. | DEFER exact schedule selection; admissible realization, not a mandatory shape. |
| E. Bounded retry + exponential backoff + jitter | 3.58125× attempts, 72.96875% completion. | Budget and timing with an additional dispersion contract. | Best observed amplification/completion among tested retry conditions. | Added delay and fresh-work pacing confound a jitter-only effect; distribution unselected. | DEFER jitter; Section 6 decision C. |
| F. Retry-attempt Rate Limiter | Repeated-attempt pressure exists; no backoff versus backoff-plus-limiter comparison. | Aggregate retry starts per time interval. | Could constrain pressure across many logical requests. | Incremental benefit, scope, rate and burst policy unestablished. | DEFER. |
| G. General Rate Limiter / Token Bucket | No general ingress failure mode or algorithm comparison in PR4/PR5. | Arrival rate and optional burst allowance at a specified boundary. | Could address a separately observed arrival problem. | Missing arrival evidence, consumer, scope and numerical/algorithm justification. | DEFER. |
| H. Bounded queue/backpressure | PR4 sheds most excess finite work; no queue comparison. | Backlog custody, waiting and release of pending work. | Could retain work that fail-fast shedding discards. | Ownership, bound, timeout, memory, head-of-line behavior, cancellation and fairness. | DEFER. |
| Minimum shared class: bounded retry with delayed backoff | All tested delayed conditions improve completion and reduce attempts relative to immediate retry, with the stated pacing qualification. | Explicit per-logical-request retry budget and timing, outside writer occupancy. | Smallest evidenced enabled mechanism without freezing a schedule family or adding aggregate admission. | Production benefit, numerical settings and waiting-resource cost require composition-specific review. | SELECT, subject to the PR8 entry contract. |

## 10. Selected Production Policy Class

```text
explicit opt-in caller policy
+ finite retry budget
+ delayed retry/backoff
+ verified pre-body capacity-refusal eligibility
= first production retry-pressure policy class
```

The selected minimum is neither unconditional retry nor a complete overload
solution. It gives an explicitly authorized caller bounded opportunities to
recover from capacity refusal while avoiding the tested immediate churn.
NO_RETRY remains the behavior when that caller has not enabled the policy.

```text
selected mechanism class
!= selected production numerical policy
!= proven production performance
```

The choice is internally resolved at class level. Deferring fixed versus
exponential configuration, numerical values and independent mechanisms does
not leave PR7 ACTIVE: those are expressly bounded PR8 design/configuration or
later evidence questions. Implementation remains separately authorized.

## 11. Ownership / Authority Boundary

### Current-source placement

The [capacity primitive](../../../src/pipeline/transactional/writer_capacity.py)
acquires once, calls once and releases in `finally`. The
[public writer wrapper](../../../src/pipeline/transactional/postgres_write_side.py)
supplies its complete body to that primitive, so returned control is outside
permit ownership. Neither component owns a cross-attempt lifecycle.

The [runtime builder](../../../src/bootstrap/build_postgres_write_side_decision_receipt_runtime.py)
composes one writer with a caller-supplied connection and optional shared gate.
It does not own a service-wide request scheduler. The
[invocation owner](../../../src/pipeline/transactional/postgres_write_side_invocation_owner.py)
marks A1 started before dispatch and spends Stage 4E authority before A2 dispatch;
exceptions do not restore either availability. The outer
[DecisionReceipt runtime owner](../../../src/pipeline/transactional/postgres_write_side_decision_receipt_runtime_owner.py)
holds its lifecycle lock across delegation. Wrapping those one-shot methods in
a general retry loop is not an eligible PR8 integration.

**Future owner: an explicit caller/orchestration policy layer outside the
protected writer and outside the Stage 4E invocation/runtime owners.** Its first
consumer is an opt-in direct-writer composition with caller-owned request and
connection lifetime. PR8 must name that concrete composition before integration;
PR7 does not invent a traffic-facing service or auto-enable existing callers.
Do not put retry in `BoundedWriterAdmission`, `PostgresTransactionalWriteSide`,
Stage 4E evaluation or invocation custody.

### Policy authority and required interfaces

Authority to consider another capacity attempt comes from the composing
caller's explicit policy configuration for that direct-writer operation. It is
limited to verified pre-body refusal and the retained logical request. The
exception is input evidence, not an issuer of authority. Where an existing
invocation-authority lifecycle applies, this policy cannot bypass it; Stage 4E
composition is excluded from the first slice.

```text
failure evidence
→ explicit policy configuration + eligibility decision
→ configured delay / continued request lifetime
→ explicit retry budget spend at dispatch
→ one execution attempt
```

These are separate responsibilities even if a small implementation co-locates
them. PR8 needs the following interfaces; names and concrete Python APIs are
not frozen here:

| Interface | Required responsibility |
|---|---|
| Policy configuration | Explicit enablement, capacity-refusal eligibility, finite attempt ceiling, positive finite delayed schedule and maximum delay; no implicit numerical defaults. |
| Logical-request custody | Retain the same complete [RequestSignature](../../../src/storage/idempotency_store.py), exclusive connection ownership and serial attempt/budget state. |
| Single-attempt adapter | Invoke the unchanged public writer once; preserve its exact normal result or original failure and establish whether refusal occurred before body entry. |
| Eligibility decision | Permit only explicitly configured, verified pre-body `WriterCapacityRefused`; uncertain provenance and every other failure/result stop this policy. |
| Timing / lifetime seam | Monotonic eligibility and an independently testable waiter, with explicit cancellation/expiry handling; no writer permit, transaction or owner lifecycle lock held while waiting. |
| Budget / dispatch seam | Check remaining allowance and spend once immediately before dispatch; count refused attempts, prevent parallel attempts or implicit lifecycle reset, and expose exhaustion separately. |
| Observation seam | Correlate logical identity, attempt identity, refusal, eligibility, scheduled/actual timing, budget spend and terminal disposition without changing semantic results or storing secrets. |

The [PR4 observer](../../../experiments/load_capacity_protection/pr4_characterization.py)
and [PR5 scheduler](../../../experiments/load_capacity_protection/pr5_characterization.py)
demonstrate why exception type alone is insufficient: the same exception raised
inside an admitted body is a native failure, not eligible capacity refusal.
PR8 must verify a production-safe observation/adapter contract at the existing
seam, preserve exact result/exception behavior and avoid importing experiment
machinery into production. It must not infer eligibility from exception text.

Refusal also says nothing about a caller's pre-existing transaction. PR8's
direct-writer composition must establish a suitable idle/no-transaction waiting
boundary and exclusive connection custody; the gate must not gain connection
cleanup responsibility. Backoff must not retain a business transaction merely
because no capacity permit was acquired. No connection-pool policy is selected.

## 12. PR8 Entry Contract

PR8 may implement only the selected caller-owned capacity-refusal retry class,
its narrow composition/observation interfaces and focused validation, after
separate authorization and a source-grounded entry audit. Required obligations:

| # | Contract | Required implementation/review witness |
|---|---|---|
| 1 | Explicit retry-policy object/configuration | A named caller supplies enablement, eligibility, finite budget and reviewed delayed schedule; missing configuration does not enable retry. |
| 2 | Finite retry budget | The total/additional counting convention is explicit; no retry dispatch exceeds the finite ceiling or silently resets the same live logical lifecycle. |
| 3 | Retry only configured capacity refusal | Verified pre-body `WriterCapacityRefused` plus explicit eligibility; type name or message alone is insufficient. |
| 4 | No retry for other failures | Native, ambiguous, semantic and unknown-provenance failures are terminal to this policy. `STALE_WRITE`, `LOCK_TIMEOUT`, validation failure and non-ACCEPTED normal results do not acquire eligibility. Preserve original evidence; further policies need separate authorization. |
| 5 | Delay outside writer capacity ownership | Schedule only after the prior public call has ended; use monotonic timing and never dispatch before eligibility. |
| 6 | No permit held while waiting | Witness release/no acquisition, no held business transaction or owner lifecycle lock, and independent progress of other callers. |
| 7 | Stable logical RequestSignature | Request ID, command type, Order ID and amount remain identical; no semantic replanning or payload mutation. |
| 8 | Distinct attempt identity | Increasing attempt identity correlates to one logical request without generating a new business Request ID; no overlapping attempts for that request. |
| 9 | Accepted completion terminates retry | No later dispatch after exact acknowledged ACCEPTED return. Other normal writer results also stop and retain their original meaning; exhaustion is not fabricated acceptance or a semantic result. |
| 10 | Explicit retry budget spend | Each dispatched retry spends once before its call, including a refused retry. Waiting, eligibility, spend and actual execution remain separately observable; cancellation cannot fabricate an executed attempt. |
| 11 | Logical-versus-attempt observability | Expose logical count/completion, attempt/refusal counts, budget/exhaustion and scheduled/actual timing. Preserve non-accepted, failed and cancelled terminals separately; no raw payload, credentials or provider-error logging. |
| 12 | Mechanism can be disabled | Disabled composition performs the existing single attempt and preserves its result/refusal/exception behavior. No implicit retries appear in existing call sites. |
| 13 | No hidden Rate Limiter | No shared starts-per-time allowance, token replenishment, burst shaping, fresh-work queue or ingress/API limiter. |
| 14 | Stage 4E remains untouched | No owner/evaluator changes, A1 reset, A2 retry, authority refund, new eligibility profile, completed handle fabrication or A3. |

Before implementing a concrete PR8 composition, name its files/consumer, define
the safe refusal-provenance seam, choose and justify its configuration contract
and define cancellation/expiry and retained-resource behavior. A finite attempt
budget is not a hard writer deadline. Additional resource limits or Stage 4E
integration require separately reviewed scope, not an implicit extension.

PR8 validation should use deterministic single-attempt fakes, clocks/waiters and
the unchanged real capacity boundary to witness counting, identity, termination,
release, refusal provenance and disabled behavior. Such tests establish mechanics,
not production performance. Numerical deployment qualification, PostgreSQL runs
and any new comparison require their own explicit scope and authorization.
No PR8 implementation or test execution starts in PR7.

## 13. Explicit Non-Decisions

The following PR5 values remain characterization probes, not production constants:

| Experimental setting | PR7 production disposition |
|---|---|
| `max_attempts = 8`, including first attempt | No count selected; only a finite explicit ceiling is required. |
| Fixed delay = 5 ms | No fixed delay selected. |
| Exponential base = 1 ms | No base or exponential mandate selected. |
| Exponential cap = 8 ms | No numerical delay cap selected. |
| Additive jitter maximum = 4 ms; seed 0 and hash/modulo algorithm | No jitter distribution, seed, algorithm or mandatory extension selected. |
| Writer bound = 8 | Remains PR2/PR5's experimental point; no new production capacity default. |

Production numerical policy needs explicit caller configuration justified by
the deployment's latency/lifetime objectives, refusal/recovery behavior and
resource constraints. PR5 alone does not supply that justification. PR8 must
not insert experiment values as defaults while claiming they were selected here;
if qualification needs additional evidence, request it separately.

No production Rate Limiter, Token Bucket, queue, backpressure service, pool size,
aggregate rate/burst setting, fairness guarantee, distributed budget, durable
retry ledger, restart-recovery authority or SLO is selected. No semantic outcome,
validation, OCC, transaction, idempotency or Stage 4C/4E contract changes.

## 14. PR7 Conclusion

The evidence supports **opt-in bounded retry with delayed backoff** as the
smallest first production retry-pressure policy class. Finite budget and timing
are separate requirements. Immediate retry is rejected for the enabled first
policy; no retry is retained as the disabled baseline. Fixed versus exponential
shape is left to explicit PR8 design/configuration. Jitter is deferred pending
more isolated evidence. Rate limiting and bounded queueing remain separate,
evidence-gated future mechanisms.

The source-grounded owner is a caller/orchestration layer outside the protected
writer and invocation owners. Its authority comes from explicit configuration
within the narrow refusal contract, never from `WriterCapacityRefused` itself.
PR8 is bounded by Section 12 and remains NOT STARTED.

PR0–PR6 remain COMPLETE; **PR7 is COMPLETE as internally resolved policy
selection, ready for human review**. This does not claim human acceptance or
production implementation. Current delivery status belongs to the
[workstream index](README.md) and [PR breakdown](pr_breakdown.md); historical
reports and ADR 0031 retain their own closeout/non-selection statements.

Documentation/read-only validation passed: repository-local Python interpreter
verification, PR5 CSV/manifest identity and quantitative reconciliation, PR4
compact evidence checks, all 84 local Markdown links including three fragment
anchors, and whitespace/final-newline checks in all four authorized Markdown
files, including the new untracked note. `git diff --check` passed; the scoped
diff and final Git status were reviewed. No pytest, lint, build, type checker,
rendered-document check, PostgreSQL execution, experiment rerun, raw-archive
inspection or external Release verification was run.

Only this note and current navigation change. Production code, capacity admission,
experiment source/results, historical documentation, tests, dependencies,
environment files and external resources remain untouched. The pre-existing
untracked `scripts/` directory is protected and uninspected. Nothing is staged,
committed or pushed. Human review should confirm the class-versus-configuration
boundary, deferred jitter and PR8's refusal-provenance/authority contract.
