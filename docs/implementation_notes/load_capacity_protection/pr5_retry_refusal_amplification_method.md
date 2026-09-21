# PR5 — Retry / Refusal Amplification Characterization

[← Back to Load / Capacity Protection](README.md)

```text
PR4 — COMPLETE / EVIDENCE COLLECTION CLOSED
PR5 — ACTIVE
Characterization machinery — implemented for human review
Live retry matrix — NOT SELECTED / NOT RUN
Production retry / Rate Limiter — NOT IMPLEMENTED
```

## 1. Question and Historical Baseline

Can a protected PostgreSQL writer remain within its occupancy bound while caller
retry behavior amplifies execution attempts and pressure outside that region?

The [PR4 report](pr4_protected_vs_unprotected_report.md) records K=512, eight
accepted items and 504 terminal capacity refusals in every recorded protected
overload cell at N=10/12/16/32. In all 24 such cells, the last refusal preceded
the first admitted body completion. PR4 bounded local writer occupancy and
displaced excess work into rapid refusal. Every logical item had one attempt;
these observations do not establish retry amplification.

PR5 compares caller reactions under its own source revision, including NO_RETRY
as a contemporaneous control. It does not define success as eventual acceptance
of every request. More completion can coexist with extreme attempt amplification;
fewer refusals can coexist with excessive logical completion latency. No policy
winner, acceptable pressure threshold or production setting is encoded.

## 2. Source-Grounded Ownership Audit

The inspected baseline is `ac591e17ce6e80163b2e92f2668b94ad25dfd434`; this identifies
the audit source, not a committed PR5 implementation or experimental result.
The complete PR0–PR4 workstream notes, PR3 capacity implementation, PR4 model,
scheduler, runner, codec, PostgreSQL adapter and their deterministic tests were
read. Historical stage statuses remain historical.

The [public writer wrapper](../../../src/pipeline/transactional/postgres_write_side.py)
passes the complete original public method body to
[BoundedWriterAdmission.run](../../../src/pipeline/transactional/writer_capacity.py).
Nonblocking refusal occurs before SQL, preliminary reads, validation, business
UOW, trace or measurement construction. Successful acquisition is released by
`finally` before the caller receives a result or exception.

The unchanged [PR4 observer](../../../experiments/load_capacity_protection/pr4_characterization.py)
delegates once to that real mechanism and records thread-local attempt facts.
PR5 gives every execution attempt a fresh observer journal. An exception named
WriterCapacityRefused raised inside an admitted body remains a native writer
failure; only observed pre-body refusal can reach the experiment retry policy.

The [retained lane](../../../experiments/load_capacity_protection/postgres_runtime.py)
forwards the supplied CREATE signature to its measured writer unchanged. This
allows the [PR5 scheduler](../../../experiments/load_capacity_protection/pr5_characterization.py)
to own retries outside production:

```text
experiment logical-request runner
→ attempt with original RequestSignature
→ retained lane / measured public writer
→ one shared real observed BoundedWriterAdmission(explicit bound)
→ original PostgreSQL writer body if admitted
→ released capacity / terminal attempt observation
→ experiment refusal policy, if eligible
```

The [Stage 4E invocation owner](../../../src/pipeline/transactional/postgres_write_side_invocation_owner.py)
still spends AVAILABLE authority before A2 dispatch and never refunds it after
an exception. PR5 directly invokes experiment lanes; no invocation owner,
DecisionReceipt runtime or Stage 4C/4E authority participates. No production seam
was missing, and no production code changed.

```text
logical request != execution attempt
capacity refusal != retry authority
resource-occupancy protection != retry/arrival protection
experiment retry policy != Stage 4E Re-invocation Authority
```

## 3. Identity and Logical Terminal States

The [PR5 model](../../../experiments/load_capacity_protection/pr5_model.py) prepares
one immutable LoadWorkItem per logical request. Request ID, Order ID, amount and
complete RequestSignature remain identical across its attempts. Distinct cells,
policies, warmups and repetitions have disjoint business identities. The same
seeded workload-index permutation is used for compared cells.

An attempt is identified by its enclosing cell, `logical_request_index`
(LoadWorkItem.workload_index), and 1-based `attempt_index`. The index increases
by one. All attempts for one logical request remain on one lane, run serially,
and follow terminal refusal plus retry eligibility. No later attempt follows
acceptance, another normal writer result, or a writer failure.

| Experiment logical terminal state | Meaning |
|---|---|
| ACKNOWLEDGED_ACCEPTED | Normal writer ACCEPTED return after finalization; no further attempts. |
| RETRY_BUDGET_EXHAUSTED_AFTER_CAPACITY_REFUSAL | Every attempt was refused and the explicit attempt limit was reached; no fabricated writer result. |
| NATIVE_WRITER_FAILURE | Exception escaped an observed admitted body; acknowledgement remains UNKNOWN and no retry follows. |
| NON_ACCEPTED_WRITER_RESULT | Existing REPLAY, CONFLICT, VALIDATION_BLOCKED or ADMISSION_REJECTED result; terminal and invalid for ordinary fresh-CREATE comparison. |
| INCOMPLETE | Unclaimed work, partial attempt, pending retry cancelled by a stop, or harness failure; missing timestamps remain absent. |

These are experiment records, never SemanticOutcome. STALE_WRITE, LOCK_TIMEOUT,
validation failure, ambiguous effects, harness failures and durable-verification
failures do not authorize retries. Existing result and failure evidence remains
separately represented.

## 4. Explicit Policies and Safety Bound

Every RetryConfig requires a policy, `max_attempts_per_logical_request`, and all
delay/jitter fields. Unused fields must explicitly be None; hidden defaults and
unused contradictory values are rejected. Durations use integer nanoseconds.

| Policy | Intentional delay following eligible refusal |
|---|---|
| NO_RETRY | No next attempt; requires max_attempts_per_logical_request = 1. |
| IMMEDIATE_RETRY | Zero. Observed scheduler/observation overhead is still real. |
| FIXED_BACKOFF | Explicit fixed_delay_ns. |
| EXPONENTIAL_BACKOFF | min(backoff_cap_ns, base_delay_ns × 2^(a−1)), where a is the refused 1-based attempt index. |
| EXPONENTIAL_BACKOFF_WITH_JITTER | The same capped exponential delay plus explicit deterministic additive jitter. |

The mandatory positive integer M includes the first attempt. A refusal at
attempt M ends that logical request as budget exhausted; acceptance on attempt
M remains accepted. NO_RETRY uses the same refusal-exhaustion state after its
single attempt. Budget exhaustion is normal experiment evidence and does not
abort other logical requests or later cells.

No second cell-wide budget is implemented: K and M already imply a maximum of
K×M attempts for the cell. The full schedule's upper bound is the sum of K×M
over its declared cells, including warmups. This bounds attempts, not elapsed
execution or evidence memory to a universal safe value. Human review must assess
the chosen attempt ceiling, data volume and resource headroom. An unresolved
writer can still prevent quiescence; no writer cancellation or deadline is added.

## 5. Timing and Jitter Contract

After refused attempt a:

```text
eligible_ns = capacity_refused_ns + scheduled_retry_delay_ns
actual next dispatch >= eligible_ns
actual next dispatch >= previous terminal observation
```

Policy calculation occurs after public return and terminal observation. A delay
shorter than that overhead can already be eligible; it adds no further waiting.
The refused attempt retains its refusal timestamp, delay and eligibility. The
next attempt retains actual dispatch and capacity-attempt timestamps. A stopped
pending retry retains its schedule without inventing an actual next attempt.

Jitter algorithm identity is
`sha256-ascii-seed:index:attempt-mod-span-plus-one-v1`:

1. Encode the decimal integers `seed:logical_request_index:attempt_index` as ASCII.
2. Hash with SHA-256 and interpret the complete digest as an unsigned big-endian integer.
3. Take the remainder modulo `jitter_max_ns + 1`.
4. Add that value to the capped exponential delay.

The seed and span are mandatory for jitter. The exponential cap applies before
jitter, so total scheduled delay is at most cap + jitter_max_ns. Cap must be at
least base; delays and spans may explicitly be zero. No system randomness or
outcome-adaptive adjustment is used. Hash reduction can have modulo bias; no
uniformity claim is made. The same seed/index/attempt yields the same jitter
across repetitions regardless of thread scheduling. It does not make the live
thread schedule deterministic.

The scheduler requires an injected thread-safe, non-raising monotonic ns clock
and `wait_until(eligible_ns, stop_event)`. The provided elapsed_waiter uses
interruptible elapsed waiting; pure tests inject clocks and event-based waiters.
The pure delay function also exposes a jitter-source seam, while runner evidence
uses the documented algorithm and validates reconstructed delays. No generic
workflow scheduler or wall-clock-sleep correctness test is introduced.

## 6. Lane Scheduling, Occupancy and Fairness

All K logical requests are offered at one common release boundary. N persistent
lanes claim requests under a brief lock. Each lane retains its current logical
request through refusal and backoff until accepted, exhausted, otherwise terminal
or stopped. Only then may it claim fresh work.

Waiting occurs outside the claim lock and after the public call and admission
return. Other lanes continue claiming and executing. A lane waiting on refusal
holds no capacity permit, transaction or writer lifecycle lock. If all lanes are
waiting, unclaimed work waits for a lane; this is an explicit consequence of
retained ownership, not a fairness or general queueing policy.

One fresh ObservedAdmission, derived from the actual PR3 mechanism, is shared
unchanged across all N lanes per cell. There is no experiment-only replacement
gate. Raw half-open body intervals must show overlap no greater than the explicit
bound. Tests exercise excess attempts against that real gate. A future live run
must establish its own overlap; configured concurrency is not observed occupancy.

Immediate retries can consume CPU and observation work while admitted writers
remain active. Persistent lane ownership may delay fresh requests or produce
unequal attempt counts. No fairness or starvation-freedom guarantee is made.
Offer, first dispatch, all attempts, lane identities, final times and residual
identities allow inspection of these effects without adding a fairness scheduler.

## 7. Connection Topology and Durable Verification

The [PR5 PostgreSQL adapter](../../../experiments/load_capacity_protection/pr5_postgres_runtime.py)
preserves N distinct retained lane connections plus one distinct control
connection. Repeated attempts reuse their lane's existing writer and connection.
Even when writer occupancy is bounded below N, the N lane connections remain
open. PR5 does not characterize connection creation storms or pool checkout.

Construction checks the declared test database, backend identity uniqueness,
autocommit disabled and idle lane connections. Preflight refuses existing request
or order identities in either business table without deleting them. Importing
the adapter performs no I/O. No live credentials are read in pure validation.

After every worker joins, the [runner](../../../experiments/load_capacity_protection/pr5_runner.py)
verifies each logical request in fresh control read transactions, outside workload
timing. Earlier refused attempts have not entered the body and carry no write
result or idempotency persistence.

| Logical trajectory | Required durable witness |
|---|---|
| Refusals followed by acknowledged acceptance | Exactly one CREATED event, sequence 1, exact request/order/amount and returned event, one event by request, matching complete signature and event through idempotency REPLAY, and exactly one raw idempotency row matching request OR order. |
| Refusal-only exhaustion | No order history or request event, idempotency MISS with no signature/event mapping, and zero raw idempotency rows matching request OR order. |
| Native or ambiguous failure | Preserve present/absent/unknown reconciliation separately from acknowledgement; never retry or retrospectively count it as acknowledged acceptance. |

Absence is durable evidence, not a semantic outcome. Only fully accounted,
verified accepted/exhausted cells without problems may use the declared cleanup.
Cleanup deletes exact verified accepted request/order pairs, idempotency first
then events, and checks all workload identities for absence. Exhausted requests
need no deletes. Failed or uncertain cells retain rows. No broad reset, sequence
reset, cache restoration, DecisionReceipt or projection deletion is added.

## 8. Evidence and Metrics

The [PR5 codec](../../../experiments/load_capacity_protection/pr5_evidence.py) uses
schema 1, method `pr5-retry-refusal-amplification-v1`, and distinct PR5 record tags.
It reuses unchanged safe PR1 producer facts and PR4 call/verification facts without
changing either registry or archived meaning. Unsupported versions, duplicate
JSON keys, unknown/missing fields, wrong types, changed identities, impossible
retry timing, budget violations and inconsistent summaries fail closed.

Each logical record holds the immutable item, common offer, ordered attempts,
terminal state/time and durable verification. Each attempt retains lane, dispatch,
public entry/exit, capacity attempt/admitted/refused, protected body entry/exit,
post-release admission return, terminal observation, acknowledgement, safe normal
producer facts/measurement or native failure, and scheduled retry timing.

Serialized logical summaries include attempt/refusal counts, first attempt,
final terminal, offer-to-final completion latency, first-attempt-to-final elapsed,
and accepted event identity. Cell summaries derive counts from raw trajectories.

```text
attempt amplification factor = total attempts / planned logical requests (K)
total retries = sum(max(0, request attempt count − 1))
logical completion proportion = acknowledged accepted logical requests / K
```

Keep logical terminal proportion, including exhausted requests, separate from
useful completion. The helpers expose attempts per request, refusals per request,
accepted/exhausted counts, residuals, public/body overlap, exact dispatch and
capacity-attempt timestamps, retry lateness, per-request latency and raw measured
production phases. Unavailable phase measurements remain absent, never zero.

Completed-cell rates divide by common offer through final logical terminal:
attempt throughput, accepted writer throughput, useful logical completion
throughput and generic logical-terminal throughput are separately named.
Accepted writer and useful logical completion numerators coincide in this
CREATE-only fixture. Incomplete/problem cells retain counts but have no
completed-cell throughput or drain-time claim. Setup, verification, cleanup and
serialization are excluded; minimal evidence handling affects replenishment.

`attempt_windows` requires explicit window width and origin; bins are half-open
and sparse, with omitted bins representing zero attempts. Raw timestamps support
multiple analysis resolutions. Fixed-backoff waves and jitter dispersion need
source-grounded timing analysis, not a chart-only thundering-herd label. There
is no universal window, percentile, statistical significance or policy winner.

## 9. Matrix, Ordering and Provenance

RetryPlan requires explicit K, ordered N levels, bound, policy configurations,
amount, warmups, recorded repetitions, workload ordering seed, test database,
connection budget/control count, setup timeout and stop/cleanup policies.
NO_RETRY is mandatory; policies are distinct and their initial order is explicit.
This supports all five requested policies without selecting live values.

`rotating_policy_blocks` executes adjacent policy blocks at each declared N.
For P policies, rotate the declared policy tuple left by
`(repetition + level_index) modulo P`. Warmups precede recorded rounds; recorded
rotation starts independently of warmup count. P recorded rounds balance every
policy across all P positions per N; incomplete rotation retains a position
imbalance. This is position counterbalancing, not complete carryover balancing.
Every cell records the full predetermined schedule and exact execution index.
No result can alter ordering, add repetitions or retune policy parameters.

Provenance retains source commit and tracked-tree qualification before/after
each cell, Python/psycopg/PostgreSQL versions, platform/architecture/CPU count,
database identity, connection facts, writer/validation composition, capacity
bound, K/N, retry policy/budget/delays/jitter, topology, clock, order, warmups,
repetitions, cleanup and stop policy. Source/local and runtime drift stop later
execution. Raw messages, tracebacks, DSNs and database credentials are excluded.
Evidence files use exclusive creation; sink failure retains raw cells after
resource closure. Process/host termination survival is not guaranteed.

The source provider must describe the actual injected clock and reviewed committed
implementation. Host exclusivity, stable endpoint and all relevant environment
controls remain operator obligations; provenance equality cannot prove them.

## 10. Live Approval Boundary and Unresolved Decisions

No PostgreSQL retry/load experiment or new PR4 experiment ran in this task.
No TEST_DATABASE_URL was inspected. Adapter tests replace connections and stores
with fakes; this is application/SQL-intent evidence, not physical durability or
performance evidence. There is no new SQL behavior requiring a live witness.

Before live execution, human review must choose and approve:

- K, amount, N levels/order and shared capacity bound;
- policy order and each attempt budget, delay, cap, jitter span/seed;
- warmup and repetition counts, workload seed and ordering balance;
- committed PR5 source, exact test database, stable endpoint and exclusive window;
- connection budget/headroom, setup timeout and stop-and-drain limitation;
- exact accepted-pair cleanup scope and retention on uncertainty;
- attempt/evidence volume, destination and any later publication; and
- analysis windows and interpretation criteria, without an outcome-driven policy winner.

The often discussed bound eight and overload N=16/32 remain historical context
and possible future choices, not defaults or a frozen matrix here.

## 11. Validation and Non-Goals

Deterministic coverage lives in
[characterization tests](../../../tests/experiments/load_capacity_protection/test_pr5_characterization.py),
[runner/adapter tests](../../../tests/experiments/load_capacity_protection/test_pr5_runner.py), and
[evidence tests](../../../tests/experiments/load_capacity_protection/test_pr5_evidence.py).
It covers stable identities, increasing attempts, all five policies, exact delay
progression and jitter vectors, serial request execution, real shared occupancy,
independent lane progress during backoff, stop-cancelled pending retries, accepted
termination, native and non-accepted termination, logical durable effects,
exhaustion, amplification, warmups, ordering, strict readback and PR1/PR4 compatibility.
Events establish causal ordering; timeout waits only fail broken test schedules.

The final focused validation passed **347 tests**: 77 PR5 tests plus 270 unchanged
PR1/PR4 experiment and directly relevant PR3 capacity regressions:

```bash
PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/experiments/load_capacity_protection \
  tests/unit/pipeline/transactional/test_postgres_writer_capacity.py
```

The repository-local interpreter was verified before Python validation. All
eight added Python files parsed successfully; whitespace/newlines were checked
in all eleven added/changed files, and all 40 local Markdown links/anchors passed.
`git diff --check` passed. A read-only byte comparison confirmed that 133 tracked
production, prior experiment/evidence, test and historical workstream files
remain identical to HEAD. No files were staged or committed.

No full pytest, lint, build, static type check, live integration witness,
PostgreSQL/load execution, external Release check or rendered-document check
was run. Human review should focus on retained-lane starvation effects, the
additive jitter/cap contract, logical durable verification and the explicit
live-run gate. Pure correctness witnesses do not establish performance results.

No production retry, retry budget, backoff, jitter, queue, Rate Limiter, Token
Bucket, Leaky Bucket or arrival shaping is added. These policy implementations
are experiment-owned stimuli. No SemanticOutcome, OCC, pessimistic locking,
transaction semantics, DecisionReceipt, Stage 4C, Stage 4E eligibility/authority
or semantic replanning changes. No dependency, environment file, historical
evidence, Release, local developer script or other repository changes belong here.

PR5 remains ACTIVE: machinery is ready for human review; live evidence and its
interpretation are pending. Only after PR5 evidence may a separately approved
decision/ADR consider resource-occupancy versus retry/arrival protection, and
only a later explicitly authorized PR may implement a production mechanism.
No ADR is created here.
