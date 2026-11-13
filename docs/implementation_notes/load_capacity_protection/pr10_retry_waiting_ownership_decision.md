# PR10 — Retry Waiting Ownership Architecture Decision

[← Back to Load / Capacity Protection](README.md)

```text
PR10 — COMPLETE / design investigation; ready for human review
Recommended disposition — A: retain synchronous thread + caller-owned connection,
                           subject to explicit caller resource/lifetime preconditions
Deployment acceptance / production numerical policy — NOT ESTABLISHED
Ownership redesign / implementation / new live execution — NOT AUTHORIZED
```

## 1. Question

When capacity retry is explicitly selected for completion objectives, who should
own resources while the logical request waits? This is an ownership decision,
not a reconsideration of retry's value. `retry_policy=None` remains a valid
single-attempt policy without redesign.

**Retain the current synchronous ownership contract for callers that can meet
Section 12's preconditions.** PR9 demonstrates attributable idle-resource cost,
but supplies no deployment resource ceiling or evidence requiring a scheduler
or a connection-lifetime change. It does not establish unconditional operational
acceptability. If a caller cannot budget retained connections, Option C is the
preferred candidate for a separately approved design, not an implemented fallback.

This recommendation preserves [ADR 0031](../../adr/0031_separate_resource_occupancy_retry_and_arrival_protection.md),
[PR7's policy-class selection](pr7_retry_attempt_policy_selection.md) and
[PR8's mechanism](pr8_bounded_retry_backoff.md). The complete PR0–PR9 workstream
was read, including the historical methods and reports. Their earlier status
labels retain their historical meaning; current navigation owns current status.
The production audit uses `3bdbf74d574e5759bcffb8aa4803adeee7e4d362`, distinct
from PR9's evidence-generating source below.

## 2. Evidence from PR9

Authority is the tracked [report](pr9_production_retry_validation_report.md),
[30-row CSV](../../../experiments/load_capacity_protection/results/pr9_recorded_repetitions.csv)
and [manifest](../../../experiments/load_capacity_protection/results/pr9_evidence_manifest.json),
under the [PR9 method](pr9_production_retry_validation_method.md).
Run `8164f5d8-e1e2-4c4b-9232-44fb899a7c56` used source
`41e33d3a855caa03afbf0b10fe4b2ee01c478a33`. Only its recorded cohort enters this
interpretation: five cells per N/mode, 30 cells, 3,840 logical requests.
Warmups, smoke and cumulative checkpoint snapshots are excluded.

The experimental configuration was K=128, writer bound 8, and, when enabled,
eight total attempts with seven 0.005-second delays. These remain experiment
parameters, not production defaults, delay optimality or a deployment budget.
The following are medians of five cell values; bracketed values are minima/maxima.

| N | Completion disabled → enabled | Enabled amplification | Enabled waiting connection peak | Enabled waiting connection-ms per cell | Retained connections, both modes |
|---|---|---|---|---|---|
| 8 | 100% → 100% | 1.000× | 0 | 0 | 9 |
| 16 | 50% → 92.969% [92.188, 93.750] | 1.852× [1.773, 1.906] | 8 | 586.997 [535.416, 631.236] | 17 |
| 32 | 25% → 78.125% [76.563, 80.469] | 3.422× [3.359, 3.461] | 24 | 1713.310 [1667.035, 1746.074] | 33 |

Waiting logical-request peaks equal the waiting connection peaks in this
exclusive-lane fixture. N=8 has no refusals, retries or waits: retry is dormant,
and ordinary throughput variation is not a retry benefit. Every recorded cell's
protected body maximum is 8. All 2,080 observed wait calls retain their original
thread and open connection, with IDLE → IDLE transaction boundary samples.

Paired enabled-minus-disabled throughput is −9.874 [−63.138, +51.595] accepted/s
at N=16 and −11.851 [−33.580, +38.007] at N=32. Paired drain time increases
61.273 [53.145, 63.961] ms and 80.111 [77.784, 82.585] ms respectively.
More eventual completion therefore does not establish more database capacity.
Five repetitions support descriptive comparison, not statistical equivalence.

Actual wait-call duration sums per cell have medians 585.585 ms at N=16 and
1709.792 ms at N=32. Waiting connection-time instead uses production
RETRY_SCHEDULED → RETRY_READY intervals. Both sum across concurrently retained
resources; neither is cell wall time, CPU time or scheduler-contention evidence.
Connection count is unchanged between modes. PR9 measures attribution of existing
connections to waiting work, not additional configured connections or pool cost.

Across the five pairs, N=16 gains 275 accepts but has only 50 accepted-after-retry
events; N=32 gains 339 with 127 accepted-after-retry events. Later first-attempt
accepts account arithmetically for the remainder. Lanes advance to fresh work
only after their current logical request terminates, so backoff changes fresh-work
pacing as well as retries. This preserves the
[PR5 pacing qualification](pr5_retry_refusal_amplification_report.md#12-fairness--retained-lane-qualification).
It does not prove that retaining a connection caused the improvement, or that
releasing connections would reproduce it.

All 2,854 acknowledgements reconcile to durable accepted effects; all 986
refusal-only terminal requests have verified absence, including 186 enabled
exhaustions. PR10 rechecked these per-cell scalars, CSV byte/hash identity,
cohort/pair counts and all six manifest group summaries. Detailed event linkage,
wait identity and raw observation validity are inherited from PR9's completed
reconciliation, not a new raw-archive inspection or live database observation.
Unavailable and non-measured phase values retain their original semantics.

## 3. Current Ownership

### Connection Acquisition, Custody and Lifetime

| Boundary | Source-grounded responsibility |
|---|---|
| [connect_postgres](../../../src/storage/postgres_connection.py) | Calls `psycopg.connect`, passing the connection timeout. Its caller owns closure. It supplies neither a pool nor a business-request lifecycle. |
| [build_postgres_writer_request](../../../src/bootstrap/build_postgres_writer_request.py) | Receives an already-owned `business_connection`; performs no connection acquisition or I/O. Constructs one request with that connection. |
| [PostgresWriterRequest](../../../src/pipeline/postgres_writer_request.py) | Retains the connection and constructs a private writer using it. Receives exclusive custody during `invoke()`, including backoff; never opens, closes, replaces, commits, rolls back or repairs the connection itself. |
| [PostgresTransactionalWriteSide](../../../src/pipeline/transactional/postgres_write_side.py) | Retains that supplied connection for preliminary reads and the business UOW. Its public capacity wrapper precedes the complete CREATE/PAY body. |
| [PostgresWriteSideUnitOfWork](../../../src/pipeline/transactional/postgres_unit_of_work.py) | Gives event and idempotency stores one transaction/connection; commits or rolls back. Does not close the connection. |
| [PR9 runtime](../../../experiments/load_capacity_protection/pr9_postgres_runtime.py) | Opens one control connection, verifies fresh identities, then opens N lane connections. Guards database/autocommit/isolation and rolls back to IDLE. Retains all connections through cell execution and durable verification, then closes them in `finally`. |

PR9 connection lifetime spans several logical requests on each lane and extends
beyond their completion to post-drain verification. A request's terminal return
does not close or release the lane connection. The
[ProductionLane adapter](../../../experiments/load_capacity_protection/pr9_characterization.py)
builds a new one-shot request for each logical item, passing the same lane
connection. Retry never increases the fixture's N+1 configured population.

The tracked `src/` call graph contains the direct-request API and builder, but no
traffic-facing service that supplies its caller-concurrency, connection or
shutdown budget. PR9's experiment is the concrete audited consumer; it is not a
deployment contract. The existing
[DecisionReceipt builder](../../../src/bootstrap/build_postgres_write_side_decision_receipt_runtime.py)
also receives an already-owned business connection. Its separate receipt
connection factory is purpose-specific governance ownership, not an existing
per-attempt business provider or permission to reuse that lifecycle.

### Thread and Lock Ownership

`invoke()` is synchronous and returns the primary `PostgresWriteSideResult`, or
raises a terminal exception. `_execute()` dispatches serial public calls;
`_backoff()` calls the injected `wait(seconds)`, defaulting to `time.sleep`, and
checks monotonic readiness before dispatching again. No internal worker is
created. The invoking thread remains occupied by the logical request throughout.

The request's short lock protects its one-shot guard and observation snapshots;
it is released across writer execution and waiting. The
[concrete capacity gate](../../../src/pipeline/transactional/writer_capacity.py) acquires once with
`blocking=False` and releases admitted calls in `finally`. Eligible refusal did
not acquire a permit. No protected body or lifecycle lock spans retry waiting.
Enabled mode checks IDLE before dispatch and before each wait, but cannot
introspect caller-held locks; exclusive custody and no external execution/session
advisory locks are explicit caller preconditions.

The [PR9 runner](../../../experiments/load_capacity_protection/pr9_runner.py)
uses `ThreadPoolExecutor(max_workers=N)`, one lane task per worker, and fixed
index-modulo-N assignments. Each lane synchronously completes its current
request before advancing. Workers join before verification. This is where the
experiment bounds callers and supplies the retained-lane pacing seen in PR9.
The production request and capacity gate do not bound waiting caller threads.

An interruptible waiter can improve cancellation responsiveness but cannot free
the calling thread while preserving this completion contract. A waiter that
returns early is checked again. Offloading `invoke()` to another thread leaves
a worker occupied; returning before terminal completion would require a future,
callback or async contract and an owner for suspended work. That is a broader
lifecycle change, not a local replacement of sleep.

## 4. Semantic Requirements

**Connection identity is not semantic identity in the audited CREATE/PAY path.**
The frozen [RequestSignature](../../../src/storage/idempotency_store.py) contains
Request ID, command type, Order ID and amount, with no connection/thread/backend
identity. [Durable idempotency](../../../src/storage/postgres_idempotency_store.py)
looks up Request ID and compares a versioned command/order/canonical-amount
fingerprint, linking the accepted event. The
[event store](../../../src/storage/postgres_event_store.py) loads accepted history
by Order ID. PAY rehydrates that history; it does not require the session that
previously executed CREATE.

Within an admitted attempt, append and idempotency persistence must share the
same business transaction. That requirement does not imply one connection
across different capacity-refused attempts. Refusal is before preliminary SQL,
candidate construction, validation, UOW creation and concurrency preparation;
there is no writer-created session or transaction state to carry to a retry.
Once an attempt enters the body, every normal result or escaping failure is
terminal to this policy, including ambiguous commit/effect.

| State | Across a permitted retry |
|---|---|
| PRE reads | Admitted PRE execution rolls back its implicit read transaction in `finally`, including replay/conflict exits. A pre-body refusal reaches none of it. PRE rollback is not connection release. |
| Business UOW / transaction snapshot | Created within an admitted body; normal non-accepted UOW paths explicitly roll back, clean unfinished exit commits. No transaction snapshot is a retry prerequisite. Exceptional finalization can fail; it remains terminal, not a reason to reconnect and retry. |
| Pessimistic preparation | [PostgresPessimisticAdmissionGate](../../../src/pipeline/transactional/postgres_admission.py) uses `pg_try_advisory_xact_lock`; commit/rollback releases it. Its prepared-order set belongs to the gate created for that UOW. Capacity refusal cannot reach it. OCC preparation takes no such lock. |
| Session state | The audited default writer establishes no required cross-attempt role, temporary-table, session advisory lock or session-setting continuity. A caller/custom composition may establish session state. IDLE does not prove its absence or permission to discard it. |
| Environment equivalence | A future fresh connection must reach the same authoritative database/schema with equivalent role/permissions, isolation, autocommit=False and required setup/settings. Recreating that context is a provider contract, not preservation of a backend PID. |

Caller-held session advisory locks are already disallowed for enabled waiting;
transaction idleness alone cannot enforce that condition. Reacquisition must not
silently lose a required caller session context or close a borrowed connection.
The conclusion is limited to this source-grounded default composition, not every
possible injected validator, gate factory or external caller.

All options must preserve:

- Explicit policy plus exact adapter-proven pre-body refusal, remaining budget
  and lifetime eligibility; exception type alone never authorizes retry.
- One complete unchanged RequestSignature and logical invocation identity,
  distinct increasing attempt identities, and no overlapping attempts for it.
- [WriterRetryPolicy](../../../src/pipeline/writer_retry_policy.py) keeps
  `max_attempts` inclusive of initial dispatch; spend immediately before the public
  call, with no budget reset by rebuilding owners and no implicit outer loop.
- Every normal result is terminal, including ACCEPTED, REPLAY, CONFLICT,
  VALIDATION_BLOCKED and ADMISSION_REJECTED/STALE_WRITE/LOCK_TIMEOUT. Native,
  validation, ambiguous and infrastructure failures get no capacity-retry grant.
- Measurement availability and observation failures remain separate from writer
  results and refusal eligibility. Missing measurement is never zero.
- Stage 4E remains separate. Its
  [invocation owner](../../../src/pipeline/transactional/postgres_write_side_invocation_owner.py)
  spends A2 authority before dispatch and does not refund it. The outer
  [DecisionReceipt runtime](../../../src/pipeline/transactional/postgres_write_side_decision_receipt_runtime_owner.py)
  holds its lifecycle lock across dispatch. Neither is a safe insertion point
  for this retry wait. No A1 reset, refused-A2 retry or A3 is selected.

## 5. Option A — Retain Thread + Connection

Keep the current borrowed-connection API. The caller owns acquisition/closure,
and gives one synchronous logical request exclusive connection custody across
attempts and delays. This is the only option already implemented and exercised
by PR9. Simple serial ownership, unchanged session context, no mid-request
reacquisition failure and stable lane correlation favor it. Its direct API
already separates logical retry from protected execution and Stage 4E.

The cost is explicit: idle connections and synchronous threads remain attributed
to waiting requests. The writer bound does not limit either. Finite delays and
attempts constrain requested retry work, but are insufficient without bounded
caller concurrency and an actual connection/thread budget. Fairness and hard
wall-clock termination are not provided. A caller requiring connection-free
waiting, prompt cancellation beyond the current seam, or unbounded intake cannot
treat PR9 as acceptance of this option.

## 6. Option B — Release / Reacquire Connection

After verified refusal, release the connection, wait synchronously, then acquire
another for the next attempt. Semantics permit this in principle under Section 4;
it removes connection ownership during the wait but retains the thread.
Fresh connection setup moves into logical completion time and can add connection
churn, infrastructure failures and blocking unrelated to writer occupancy.

The current owner cannot simply close `_connection`: it borrows that connection,
its private writer retains it, and PR9's lane reuses it for later requests.
Implementing B requires an explicit ownership-transfer/provider API and rebuilding
connection-bound writer/stores, not mutating a private connection field. Session
setup, release on all exits, cancellation and cleanup failure must be specified.
Adding retained and replaceable modes also adds lifecycle branches to this owner.

Distinguish three contracts: a retained dedicated connection; per-attempt fresh
acquisition/close through a provider or factory; and checkout/return to a pool.
A factory is not a pool. Pooling additionally owns reuse, maximum physical
connections, checkout waiting, reset and lease disposal. None is implied by B,
and no pool is selected here. Reacquisition provides no inherent fairness or
connection-exhaustion protection.

## 7. Option C — Retry Above Resource Acquisition

A potential future boundary is:

```text
one logical owner: signature, identity, finite budget, lifetime checks
→ eligible delayed wait without a business connection
→ acquire and validate one attempt's connection/resources
→ dispatch exactly one public writer call through the shared concrete gate
→ finish/release that attempt's resources
→ terminal result/failure, or consider the proven refusal for another attempt
```

This is cleaner than teaching a borrowed-connection object to replace someone
else's connection. Logical lifetime and attempt resource lifetime are explicit;
the resource provider can handle connection setup/close while retry owns only
policy and serial dispatch. Synchronous completion can remain unchanged.

There is a conceptual seam: the connection helper is already outside the
builder, and the public writer is one attempt. There is **no implemented business
attempt provider** at that seam. The current request eagerly constructs its
connection-bound private writer; a future design would need to separate that
construction from its single logical loop and preserve the private refusal proof.
Wrapping successive new `PostgresWriterRequest` objects would reset identity,
observations and budget and is not an acceptable shortcut. A generic callback
catching `WriterCapacityRefused` would lose concrete-gate provenance.

Connection acquisition would still precede the current public capacity boundary.
Peak acquisition/open-connection demand can therefore reach caller concurrency,
even when most writers are immediately refused. C removes waiting ownership;
it does not automatically reduce the peak to the writer bound. Moving the permit
around connection setup would change its protected scope and is not selected.

C is the preferred future candidate if connection-free waiting becomes an explicit
requirement. It is not necessary merely because retention is measurable, and its
performance, cancellation and cleanup behavior remain uncharacterized. Keeping
lane assignment could retain pacing of fresh work, but new setup timing prevents
assuming PR9's completion, amplification or throughput would remain identical.

## 8. Option D — Scheduler / Queue / Async

A scheduler could retain logical state without one synchronous execution thread
per wait. It must own suspended-work bounds, execution slots, cancellation,
deadlines, fairness, shutdown, restart and any persistence/recovery policy.
Returning completion asynchronously changes the caller contract. A synchronous
wrapper awaiting a future still occupies its caller thread.

PR9 supplies waiting durations and thread identity, not CPU cost, scheduler
contention or an exhausted thread budget. It does not justify this broader
complexity. Defer D; neither async throughput improvement nor a queue/pool is
inferred. Avoiding a connection during waiting and avoiding a thread during
waiting are separate decisions.

## 9. Failure-Mode Comparison

These are design obligations for B/C, not new production outcomes or exception
classes. A's acquisition is external and before request construction; B/C would
make it a repeated resource stage owned by the logical lifecycle/provider.

| Event | Current A | Required B/C disposition |
|---|---|---|
| Acquisition fails before public dispatch | External infrastructure failure; no request attempt was dispatched. | Infrastructure/resource-stage terminal failure, not capacity refusal. Preserve it separately; no capacity-budget spend or automatic reconnect loop. |
| Acquisition blocks / connections exhausted | Caller setup can block/fail outside the owner; capacity gate offers no protection. | Acquisition still occupies the synchronous thread and must have an explicit bounded-wait/timeout contract. Blocking itself is pending work, not refusal evidence. No fairness guarantee follows. |
| Acquisition times out | External infrastructure terminal; helper connect timeout is not a writer deadline. | Distinct infrastructure/acquisition-timeout terminal. No `WriterCapacityRefused`, refund, synthesized semantic result or fresh retry budget. |
| Shutdown/cancellation during backoff | Cooperative `cancelled()` before/after waits; default sleep notices only after return. `expires_at` clips waits and prevents later dispatch. Caller still owns closure. | Stop without a next dispatch or connection acquisition; preserve spent budget and cancellation/expiry separately. No suspended request restart authority is implied. |
| Shutdown/cancellation during acquisition | Outside the current owner contract. | Provider must define interruption/timeout and eventual disposal. If acquisition returns after cancellation/expiry, release the resource and do not dispatch. A cancel flag alone cannot interrupt a blocking connect. |
| Connection lost after acquisition, before execution | IDLE check may reject it; IDLE is not a health probe. Otherwise native failure can surface inside the public body and is terminal. | Infrastructure terminal, not eligible refusal. If public dispatch has occurred, its budget unit is spent; preserve unknown effect where evidence cannot prove absence. Never reconnect/retry merely because loss occurred near entry. |
| Release/close fails after an eligible refusal | Request does not close; caller owns cleanup. | Retain original refusal and separate cleanup failure; do not continue as though connection-free waiting were established. No new eligibility or hidden acquisition retry. |
| Release fails after accepted result or native writer exception | Caller cleanup is outside the primary writer result. | Preserve original result/exception and separate resource disposition; cleanup must not erase acknowledgement, mask the original failure or trigger another write. |
| Wait/clock/cancellation callback fails | Terminal owner failure; no retry. | Same separation; callback/provider errors, even if same-typed as refusal, cannot pass exact writer-boundary provenance. |

Acquisition attempts and public writer attempts must be separately observable.
Under B/C a resource failure before dispatch spends no writer-attempt unit, but
is terminal; that is not permission for unlimited uncharged acquisition retries.
Any future release-failure delivery contract needs explicit review before code.
Finite attempts do not bound a stuck connect, body, cleanup or waiter in wall time.
No option may replay an ambiguous accepted effect to recover its infrastructure.

## 10. Resource-Budget Comparison

Let B be one shared gate's bound, C an **externally enforced** maximum concurrent
caller lanes/logical invocations, W(t) the waiting logical requests, and H the
separately budgeted connections for control/governance/other work. Bounds below
assume exclusive custody, at most one business connection per lane/attempt, and
successful cleanup. They are scoped to that caller population, not the cluster.

| Resource / invariant | A: retained connection | B/C: per-attempt acquisition, synchronous wait | D: deferred scheduler |
|---|---|---|---|
| Protected writer bodies | ≤ B globally within the shared object; ≤ min(B,C) from this population | Same unchanged gate | Must preserve B independently of scheduler slots |
| Concurrent logical requests | ≤ C only if caller enforces it | Still needs C; factory does not supply it | Needs an explicit pending/running logical-work bound |
| Open business connections / peak incl. H | Up to C retained lanes; peak C+H, even outside active requests | Up to C simultaneous acquisitions/owned connections; peak still C+H under these assumptions | Unspecified until execution/resource limits are designed |
| Connections attributable to retry wait | W(t), with 0 ≤ W(t) ≤ C | 0 only after successful close/ownership return, before reacquisition | Depends on whether resources are released; async alone gives no guarantee |
| Threads retained by waiting requests | W(t) ≤ C | W(t) ≤ C; acquisition can also block threads | Could avoid a dedicated thread per wait, but needs executor and suspended-state bounds |
| Transaction / permit during eligible backoff | None under idle/exclusive-custody preconditions | None; release must complete before wait | Must preserve the same evidence and ordering |

Without C the current production mechanism supplies no finite global bound on
connections, logical callers or waiting threads. Distinct processes or distinct
gate objects have distinct B budgets; their resource demands must be aggregated
by deployment owners. An application writer bound does not establish database
connection headroom.

For PR9, C=N and H=1: 9/17/33 retained connections in both modes. Connection
ownership scales with configured caller lanes, not eight writer permits. Idle
lane connections remain open even after their logical work ends, until fixture
teardown. Peaks 8 and 24 waiting at N=16/32 are observations, not a universal
W=N−B bound; all C callers could wait at some instant or compete with other users
of the shared gate.

For M attempts and supplied delays d₁…d₍M−1₎, at most M−1 retry schedules request
nominal delay S=Σdᵢ per logical request. S is a configuration sum, **not** an upper
bound on actual elapsed wait, retained connection-time or request lifetime:
sleep overshoot, scheduling, callback stalls and writer duration remain. Aggregate
waiting connection-time in A is ∫W(t)dt; instantaneous C alone does not bound it
without a lifetime contract. In B/C that retry-wait integral is zero by design,
but connection setup/execution/cleanup cost remains and must be measured separately.
For a future pool, zero waiting-request leases would not mean zero open physical
connections; a pool's physical-connection bound is another contract entirely.

## 11. Decision

Select **A conditionally for the current direct synchronous API**. Correctness
simplicity, existing serial/cancellation/observation boundaries and actual PR9
evidence outweigh an unmeasured lifecycle redesign without a specified resource
constraint. This does not make connection identity semantic or declare retention
acceptable for arbitrary offered concurrency.

| Criterion | Decision consequence |
|---|---|
| Correctness simplicity | A preserves proven refusal and result boundaries; B/C need new acquisition and cleanup dispositions. |
| Independence from connection identity | Makes B/C feasible candidates, not mandatory changes. Equivalent execution context still matters. |
| Bounded ownership | A is acceptable only with caller C, connection/thread headroom and lifetime obligations; the writer gate cannot substitute. |
| Cancellation/shutdown | Accept A only when cooperative controls and external cleanup fit the caller's shutdown contract. No hard interruption is promised. |
| Scope / synchronous compatibility | A requires no behavior change. C can preserve synchronous completion but needs an explicit attempt-resource composition. D is a broader API/lifecycle decision. |
| Observability / evidence | A has production attempt/body seams and PR9 retained-resource witnesses. B/C acquisition/release and D scheduler evidence do not yet exist. |

Evidence is sufficient for this conditional architecture disposition, but
insufficient to approve a named deployment's resource envelope or numerical
settings. If that envelope cannot be supplied, deployment acceptance stays open;
do not silently accept A, silently switch to C, or automatically disable an
already selected caller policy. No-retry remains an explicit valid choice.

### ADR Disposition

The [ADR convention](../../adr/README.md) separates Proposed/Accepted decision
status from Implementation Status and favors a short durable choice among
alternatives. This PR-specific investigation remains an implementation note
pending human review. A durable ADR is warranted if this conditional ownership
policy is adopted beyond the workstream. Proposed title:
**Keep Capacity Retry Synchronous Under Explicit Caller Resource Budgets**;
placement: `docs/adr/`, using the next available numbered stable filename
(`0032_keep_capacity_retry_synchronous_under_explicit_caller_resource_budgets.md`
is a candidate, not a reserved number or existing link). It should link here
for evidence/options and distinguish existing mechanism from operational
preconditions. No ADR is created or marked Accepted in PR10.

## 12. Preconditions / Consequences

Before a caller treats A as operationally acceptable, it must establish:

1. A named synchronous caller and bounded concurrent logical population C,
   including all instances/processes and shared-gate scope. A new
   `PostgresWriterRequest` per arrival without an upstream bound does not qualify.
2. A known connection and thread budget covering retained idle lanes, active
   work, control/governance connections and other consumers with explicit
   headroom. PR9's N+1 topology is evidence, not the deployment allocation.
3. An explicitly chosen finite M and complete delay schedule whose nominal wait
   and observed latency/retention fit that caller's objectives. PR5/PR9 numbers
   do not supply this approval. No owner reconstruction may refresh the budget.
4. Exclusive connection custody, IDLE entry/waits, autocommit=False for business
   execution, equivalent intended session context, and no external lifecycle,
   execution or session advisory lock held during waiting. The caller and
   injected callbacks must respect these conditions; IDLE alone is insufficient.
5. A shutdown/cancellation owner and closure/disposition on every return or
   exception. Select cooperative lifetime controls/interruptible waiting when
   required; acknowledge that they do not abort an executing writer. If a hard
   resource-release deadline is required, current controls alone do not meet it.
6. Observability of logical requests, attempts, refusal/eligibility, exhaustion,
   actual waits, waiting population and attributable connection/thread retention.
   Keep infrastructure failures and missing measurements distinct. No fairness,
   crash recovery or CPU-cost guarantee is inferred from finite retries.

These are acceptability conditions, not newly implemented enforcement or a
production rollout checklist passed by PR9. No source consumer currently supplies
all the deployment facts. Caller budgets, latency/retention tolerance and shutdown
requirements are the remaining human decisions.

## 13. Explicit Non-Decisions

PR10 selects no production B, C, M, delay values, fixed/exponential optimum or
jitter algorithm. It adds no Rate Limiter, Token Bucket, pool, queue, async
scheduler, arrival shaping, native/ambiguous-effect retry or Stage 4E integration.
It makes no claim that pooling or async would improve throughput, that releasing
connections preserves PR9 results, or that rate limiting/jitter are permanently
unnecessary. Existing authority, validation, OCC/pessimistic, transaction,
idempotency and primary-result/measurement contracts remain unchanged.

## 14. Follow-up Implementation Boundary

There is no automatic implementation PR or live matrix. First identify the
intended caller and assess Section 12. If it meets those conditions, A needs no
ownership change; numerical/deployment qualification remains separately owned.
If connections must be released during waits, separately authorize a concrete
C design covering provider ownership, equivalent session setup, acquisition
timeouts/cancellation, release-failure evidence, and the unchanged one-shot
logical budget/refusal proof. Prefer a purpose-specific fresh-connection provider
as a possible composition; do not smuggle in pooling or a second retry loop.

Before such code, define deterministic witnesses for failure before/after
acquisition, cancellation races, cleanup/result separation, stable signature and
attempt identity, concrete-gate refusal provenance, and no resource spanning
backoff. A later separately approved comparison must include connection setup
and teardown, peak connection demand, wait attribution, logical latency/drain,
attempt amplification, durable correctness and fresh-work pacing. Existing PR9
evidence must remain unchanged. Thread-free waiting requires separate evidence
of an unacceptable thread/lifetime constraint and a broader D decision.

PR10 is **COMPLETE as a design investigation, ready for human review**; that
status does not claim human acceptance, a new ADR or deployment authorization.
Validation uses read-only source/CSV/manifest inspection, local Markdown links,
scoped diff/status review and `git diff --check`. No PostgreSQL, raw-evidence
download, pytest, lint, build or type checker is needed or run for these docs.
Only this note and current navigation change. Source, tests, experiment machinery
and results, historical documents, Releases, dependencies, environment files and
protected `scripts/` remain untouched. Nothing is staged, committed or pushed.
