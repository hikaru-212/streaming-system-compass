# PR4 — Protected vs Unprotected PostgreSQL Writer Characterization

[← Back to Load / Capacity Protection](README.md)

```text
PR4 — ACTIVE
Measurement/comparison machinery — implemented for human review
Live PostgreSQL comparison — NOT RUN
Performance interpretation / evidence report — PENDING
```

## 1. Question and Authority

Does enforcing PR3's capacity boundary improve the cost and behavior of useful
acknowledged accepted work, or merely move pressure into pre-entry refusals
and/or add enough overhead to negate the benefit?

[PR1](pr1_unprotected_characterization_report.md) established the motivating
degradation evidence. [PR2](pr2_capacity_interpretation.md) selected eight as the
first experimental protected point. [PR3](pr3_bounded_inflight_admission.md)
implemented the opt-in, shared, process-local, fail-fast mechanism. PR4 owns the
comparison and subsequent empirical evaluation. Eight is not a universal constant,
production SLA/SLO, rate limit or PostgreSQL global limit.

No success threshold is implemented. Reduced DB-backed latency must be reported
alongside refused work, accepted count, accepted proportion and useful throughput.
A collapse in useful throughput cannot be hidden behind faster surviving calls.
Interpretation remains human-reviewed after collection. PR4 stays ACTIVE until
real evidence has been collected, reviewed and reported.

## 2. Source-Grounded Audit

The audit used source commit `8eebff1e219f4ff0089052fe81718def1aa7d409`. This is
the baseline inspected, not a claim that PR4 machinery or future evidence was
committed there.

The frozen [PR1 scheduler](../../../experiments/load_capacity_protection/postgres_characterization.py)
records `writer_entry_ns` immediately before invoking its retained lane callable.
The [lane](../../../experiments/load_capacity_protection/postgres_runtime.py)
forwards to the measured public CREATE method. Its historical writer interval
is therefore an outer public-call interval.

The current [writer wrapper](../../../src/pipeline/transactional/postgres_write_side.py)
calls the original method directly for `capacity_admission=None`, or supplies
its body to [BoundedWriterAdmission.run](../../../src/pipeline/transactional/writer_capacity.py).
That primitive acquires once, fails immediately when unavailable, and releases
in `finally`. The admitted body includes PRE preliminary reads and rollback,
validation, business UOW/finalization, and final measurement delivery. Admission
precedes that work. The [runtime builder](../../../src/bootstrap/build_postgres_write_side_decision_receipt_runtime.py)
retains a supplied gate; it does not create a shared population budget.

PR1's unchanged ledger would count refusal as outer writer entry and escaping
writer failure. That is its historical meaning, not protected-body measurement.
PR4 therefore owns distinct models, scheduler, runner and codec. It reuses only
unchanged identities, safe producer facts, phase measurements, durable accepted
checks, connection guards and exact-pair cleanup patterns. No PR1 module, schema,
method, archived JSON, compact evidence or Release changes.

## 3. Conditions and Shared Ownership

| Condition | Configuration | Scope |
|---|---|---|
| UNPROTECTED | `capacity_admission=None` in every lane | Current PR3 public wrapper remains present; no synthetic admission. |
| PROTECTED | One `ObservedAdmission(bound=explicit_bound)` shared by all N lanes | Experiment subclass of real PR3 `BoundedWriterAdmission`, delegating once to `super().run`. |

The [observer](../../../experiments/load_capacity_protection/pr4_characterization.py)
owns only a per-thread attempt journal; it does not duplicate acquisition or
release. The [runner](../../../experiments/load_capacity_protection/pr4_runner.py)
creates one gate outside the per-lane loop for each protected cell. Every lane
must retain that exact object. The [PostgreSQL factory](../../../experiments/load_capacity_protection/pr4_postgres_runtime.py)
injects it unchanged into N distinct `PostgresLoadLane` writers.

The bound is a required positive integer in
[ComparisonPlan](../../../experiments/load_capacity_protection/pr4_model.py),
with no default eight. Different cells get fresh gates. Tests offer five lanes
against bound two, observing public-call overlap above two and protected-body
overlap of two. Live evidence must establish its own overlap; configured N alone
does not prove that the offered execution opportunity was exercised.

## 4. States, Timestamps and Counts

All K independent CREATE items are prepared before common release. Each can be
claimed once by a persistent lane. Raw evidence preserves:

| State / boundary | Representation |
|---|---|
| Planned | One fixed-K item with exact request/order/amount signature. |
| Offered | Common `offer_ns` makes the item eligible. |
| Dispatched | `lane_id`, `dispatch_ns`. |
| Outer public call | `public_call_entry_ns`, `public_call_exit_ns`. |
| Capacity attempted | `capacity_attempt_ns` at observed `run` entry. |
| Capacity admitted | `capacity_admitted_ns` inside the callback after acquisition. |
| Capacity refused | `capacity_refused_ns` after refusal without callback admission. |
| Protected body entered/exited | `protected_writer_entry_ns`, `protected_writer_exit_ns` around the original operation, after admission. |
| Admission returned/raised | `admission_return_ns`; for admitted work, after release. |
| Terminal observation | `terminal_observation_ns` after retaining normal facts, native failure or refusal. |
| Acknowledged accepted | Exact normal ACCEPTED return; existing acknowledgement meaning. |
| Native writer failure | Safe exception class/SQLSTATE, unknown acknowledgement and observed body entry. |
| Residual/incomplete | Planned item without terminal observation, including pending or partial work; no fabricated exit. |

For unprotected work, capacity and protected-body timestamps are `null`.
Capacity attempts/admitted/refused and protected-body-entry counts are also
`null`: **not applicable**, rather than zero permits or implicit admission.
Generic writer-entry/terminal counts use public entry for unprotected work and
body entry for protected work. Refusals count only as outer terminals.

Per-cell summaries retain K, offered N, mode, applicable bound, planned/offered/
dispatched counts, attempts/admitted/refused, protected-body entry, writer entry,
writer terminal, all terminals, acknowledged accepted, native failures, harness
failures, evidence problems and exact residual indices. Counts are recomputed
from observations. Preparation/setup/verification timing and quiescence are separate.

Admission/release observations include callback and scheduling uncertainty.
`admission_return_ns` is an upper observation boundary after release, not the
exact semaphore-release instant. Protected-body exit precedes release. The
existing seam does not independently observe the unprotected original body;
its public-call interval is the explicitly qualified body-latency proxy. No
production instrumentation or artificial unprotected gate is inserted.

## 5. Fail-Fast Behavior and Failure Policy

Refusal creates no production result, measurement, SemanticOutcome, verdict,
completed invocation or retry/reinvocation/replanning authority. It is not
STALE_WRITE, LOCK_TIMEOUT, VALIDATION_BLOCKED, native writer failure or harness
failure. No Stage 4C/4E path participates in this experiment.

The refused item completes once; its lane may immediately claim another item.
It does not retry, requeue, delay or replace the refused item. Many quick
refusals while admitted writers remain active are expected measurable behavior.
K is offered work, not a target accepted count.

An exception *inside* an admitted body remains a native failure even if its
class is `WriterCapacityRefused`. A bypassed/unobserved admission seam, multiple
attempts, bad delivery or observer defect is a harness problem. Native failures
stop subsequent claims while already claimed calls drain. Unexpected normal
outcomes, residuals, durable mismatches, verification uncertainty, source/runtime
drift or cleanup/close failure stop later cells. Refusals alone do not stop them.
The sink receives raw evidence after resource closure. Sink failure retains
raw cells in `EvidenceSinkError` and stops execution.

There is no hard cancellation or writer deadline. The setup timeout does not
bound writer duration. Verification and cleanup wait for every worker to join;
an unresolved call can block indefinitely. Durable effects after ambiguous
failure do not retroactively establish acknowledged acceptance.

## 6. Same-Source Plan and Counterbalanced Ordering

Both conditions run in one `run_plan` session with the same implementation,
source commit, test database, K, amount, index permutation, measurement surface
and writer/validation composition. Historical PR1 is motivation, not the sole
control: PR3's wrapper exists even when disabled, and environment behavior drifts.

The caller supplies the plan, factory, monotonic clock, source-provenance provider
and sink. Every value is explicit: K, ordered concurrency levels, warmups,
repetitions, seed, amount, test database, connection budget, control count,
connect timeout, stop/cleanup policy, bound, pairing scheme and first mode.
The factory receives the scheduled condition, workload and shared gate or None.
No CLI or module import executes a workload.

`alternating_adjacent_pairs` runs all warmup rounds before recorded rounds.
Each round visits the declared N order, with adjacent U/P or P/U cells at each N.
The lead mode reverses by level index and repetition parity relative to
`first_mode`; recorded parity starts independently of warmup count. Every file
records the full schedule, cohort, repetition, pair index, pair position and
execution index. Seed controls the identical item-index shuffle only. Identities
are disjoint across conditions and cells. No order or repetition count depends
on outcomes. Odd repetition counts retain a one-pair leading-condition imbalance.

Source facts before/after each executed cell are compared with initial session
facts. The runner requires a named commit and clean tracked tree; untracked files
remain explicitly uninspected. A live operator must confirm the reviewed PR4
implementation is included in that revision. This task does not commit it.
Runtime checks compare database name, PostgreSQL version, isolation/autocommit
and writer/validation identities. N lane backend IDs plus one control ID must
be distinct within every cell.

Provenance includes Python, psycopg, platform, machine, CPU count, clock, source,
working-tree qualification, database identity/version, connection facts,
placement, OCC gate, validation runtime/mode/validator/policy, topology,
instrumentation, method/schema, plan values and exact order. No DSNs,
credentials, arbitrary error text or tracebacks are serialized. These checks
cannot prove host exclusivity or detect all database setting changes. Stable
endpoint and interference control remain reviewed operational obligations.

## 7. Connections, Durable Verification and Cleanup

Both conditions retain N lane connections plus one control/verification
connection. N=32 and bound eight still use approximately 33 connections.
This characterizes writer-work admission protection, not connection-count,
pool-checkout or `max_connections` protection. Setup is outside workload timing.

Preflight refuses identities already present in either business table and
never deletes them to start a cell. After quiescence, fresh control read
transactions verify:

- **Acknowledged accepted:** unchanged PR1 witness: exactly one CREATED event,
  sequence 1, exact request/order/amount and returned event, exactly one event
  by request, matching idempotency REPLAY signature/event.
- **Capacity refused:** no event by order or request, idempotency MISS without
  mapping evidence, and zero raw idempotency rows matching the exact request
  **or** order. This extra count detects orphan/mismatched records the store's
  request lookup/join could miss. Absence verifies no protected business effect;
  it is not a semantic outcome.
- **Native/ambiguous failure:** retain present/absent/unknown reconciliation
  separately from acknowledgement, preserving PR1's rules.

Only fully accounted, verified accepted/refused cells without problems proceed
to cleanup. The runner passes only accepted identities to exact-pair deletion,
idempotency first then events, and verifies workload absence. Refused work needs
no business-row deletion. Failed or uncertain cells retain rows. Cleanup is also
complete when verified absence requires no deletes. No TRUNCATE, CASCADE, VACUUM,
broad reset or sequence reset is added. Logical cleanup does not restore WAL,
cache, dead tuples or global-position allocation. Counterbalancing reduces simple
order bias; it does not eliminate physical drift.

## 8. Evidence and Metrics

The [PR4 codec](../../../experiments/load_capacity_protection/pr4_evidence.py)
owns schema `1` under method `pr4-protected-vs-unprotected-v1`. Its distinct
envelope/tags prevent accidental PR1 decoding. Unsupported versions, unknown or
missing fields, wrong types, duplicate keys and inconsistent summaries fail
closed. PR1 allowlists are unchanged. Shared fact codecs never reconstruct a
production result. Exclusive file creation prevents evidence overwrites.

Descriptive helpers retain raw samples and sample counts for all work,
acknowledged accepted work, refusals and native failures. Available metrics are:

- acknowledged accepted writes per offer-to-last-terminal wall-clock cell time;
- accepted proportion of offered work, admission/refusal ratios of attempts,
  and refusal proportion of offered work, with distinct denominators;
- public/body latency, scheduler wait, outer terminal latency, attempt-to-admitted/
  refused timing and observation/release-boundary overhead;
- public-call and protected-body overlap from half-open intervals, including
  complete and unclosed interval counts;
- raw production phases including business UOW, append admission and commit
  finalization, only when MEASURED; unavailable/unreached is not zero.

Incomplete/problem cells have no completed-cell throughput. Raw counts and
observed elapsed survive. `recorded_statistics` excludes warmups and does not
pool repetitions. Percentile estimators and interpretation tolerances require
explicit reporting. No confidence or success claim is built in. Overlapping
phase durations must not be summed or interpreted as server CPU time.

N=8 compares U with P(bound=8) for initial gate overhead: report actual refusals,
accepted throughput, public/body latency and UOW/append/commit cost. Refusal is
never assumed impossible. Protected callback/timestamp work adds observer cost,
so this estimates instrumented-path overhead, not isolated bare semaphore cost.
At N>8, report costs together with refusal/admission ratios, accepted counts and
useful throughput. A faster admitted body alone establishes no benefit.

## 9. Proposed Live Matrix — Not Authorized or Executed

| Parameter | Candidate for human review |
|---|---|
| K / amount | 512 / `10.00` per cell |
| Offered concurrency order | `(8, 10, 12, 16, 32)` |
| Conditions per N | UNPROTECTED; PROTECTED with explicit bound 8 |
| Warmups / recorded repetitions | 1 / 6 per N and condition; six permits equal leading-condition counts |
| Pairing / first condition | `alternating_adjacent_pairs` / UNPROTECTED |
| Workload index seed | 0 |
| Required connections | At most 33: 32 lane plus one control |
| Stop policy | `stop_claims_and_drain_without_deadline` |
| Cleanup policy | `delete_verified_cell_rows`, restricted to accepted identities |

This is 10 warmup and 60 recorded cells, 35,840 total offered items if the plan
drains. Accepted count is an outcome. These are documentation proposals, not
library constants. Human approval must still cover the matrix, exact test
database, connection budget/headroom, setup timeout, exclusive host/database
window, stable endpoint, cleanup scope, source revision and evidence destination/
publication. No live comparison ran here.

## 10. Validation and Limits

Deterministic tests use real PR3 public wrappers with fake operations, events
and thread-safe clocks; no sleeps or live PostgreSQL. They cover
[observation/scheduling](../../../tests/experiments/load_capacity_protection/test_pr4_characterization.py),
[runner/verification/factory](../../../tests/experiments/load_capacity_protection/test_pr4_runner.py),
and [evidence/metrics](../../../tests/experiments/load_capacity_protection/test_pr4_evidence.py).
Unchanged PR1 experiment and PR3 capacity tests remain regression witnesses.

The final focused command passed **270 tests** (58 new PR4 tests plus unchanged
PR1 experiment and PR3 capacity regressions):

```bash
PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/experiments/load_capacity_protection \
  tests/unit/pipeline/transactional/test_postgres_writer_capacity.py
```

The repository-local interpreter was verified before validation. Read-only
validation parsed all eight added Python files, checked whitespace/newlines in
all eleven added/changed files, and validated 38 local Markdown links/anchors.
`git diff --check` passed. Fifteen frozen source, PR1 infrastructure/evidence and
PR0–PR3 documentation files were byte-compared with HEAD; all matched. The
change set was checked against the declared paths, with only the pre-existing
untracked `scripts/` entry outside that set. Nothing was staged or committed.
No full pytest, lint, build, static type check, live integration witness,
PostgreSQL sweep, external Release check or rendered-document check was run.

These tests establish application mechanics and SQL intent, not live durability
or performance. No production behavior or instrumentation changed. Live adapter
behavior still requires review and authorized execution before empirical claims.

Inherited limitations remain finite closed-loop independent CREATE,
PRE_TRANSACTION/OCC/STRICT FullProof, retained connections, application timing,
Python scheduling, measurement observer cost, physical drift and no server
CPU/I/O/WAL attribution. No PAY/hot-key/mixed-workload, production arrival,
distributed capacity, retry policy or SLA/SLO is established. No Rate Limiter,
token bucket, burst shaping or queue pacing is implemented.
