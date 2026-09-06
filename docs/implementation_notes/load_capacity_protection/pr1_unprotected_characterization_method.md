# PR1 — Unprotected Finite-Load Characterization Method

[← Back to Load / Capacity Protection](README.md)

```text
PR0 — COMPLETE
PR1 — ACTIVE / METHOD DOCUMENTATION

Experiment implementation and live characterization
= NOT STARTED

Capacity mechanism and numerical policy
= NOT SELECTED
```

This document records the method accepted for PR1 following the read-only audit
of repository source at `0bb379a`. It defines requirements for future
experiment implementation and evidence, not experimental results or permission
to execute a database workload. Future execution must retain its own source
and environment provenance.

## 1. Purpose

PR1 characterizes the current unprotected PostgreSQL writer before any capacity
protection exists. Its research question is:

> For a fixed current writer composition and independent finite CREATE
> workload, when does increasing offered concurrent execution cease to improve
> acknowledged accepted-write throughput and predominantly increase waiting,
> latency, or failures?

PR1 collects trustworthy characterization evidence. PR2 separately interprets
degradation, a possible knee, saturation, and operating implications. PR1 does
not attempt to prove that a capacity knee exists. A later conclusion of:

```text
no useful knee established in tested range
```

is explicitly valid when supported by credible characterization.

## 2. Relationship to PR0 and Stage 4B.2

```text
PR0
= responsibility / research boundary

Stage 4B.2
= existing bounded measurement and concurrency evidence

PR1
= new separately owned capacity characterization experiment
```

The [PR0 boundary](pr0_research_and_responsibility_boundary.md) remains the
workstream responsibility contract. The
[Stage 4B.2 closeout](../stage_4b_2/stage_4b_2_closeout.md),
[PR7 method](../stage_4b_2/postgres_bounded_concurrency_method.md), and
[PR7 report](../stage_4b_2/postgres_bounded_concurrency_report.md) remain frozen
historical evidence with their own source, schedule, environment, and claims.

PR1 may reuse the production measurement API as-is and selected PR7 harness
patterns, including persistent lane ownership and external call timing. It
must not modify Stage 4B.2 experiment code, rewrite its evidence, or relabel
historical measurements as PR1 results. PR7's fixed schedule, schemas, and
unexpected-exception invalidation rules are not automatically PR1 contracts.

## 3. Experiment Ownership

Future implementation is expected to live in the separately owned namespace:

```text
experiments/load_capacity_protection/
```

This method does not create that namespace or freeze exact implementation
files beyond the reviewed prospective plan. Scheduling, outer observations,
raw evidence, and experiment validity belong to PR1. Production code remains
unchanged.

This document belongs in implementation notes because it owns workstream- and
PR-specific method reasoning. No new cross-cutting production boundary or
accepted architectural alternative requires a boundary note or ADR here.

## 4. Fixed Workload Fixture

The initial fixture is:

```text
CREATE
fresh independent Order IDs
unique Request IDs
fixed valid amount
PRE_TRANSACTION
optimistic admission / OCC
STRICT FullProof validation
one retained distinct PostgreSQL connection per active lane
```

| Choice | Method justification |
|---|---|
| CREATE | A fresh aggregate starts at INIT / version 0 and produces one sequence-1 CREATED event. PAY requires an already-created order, accepted history, and the existing full-payment rule, adding fixture variables. |
| Fresh independent Order IDs | Remove intentional same-stream conflict as the primary variable while preserving competition for shared backend resources. |
| Unique Request IDs | Avoid replay and idempotency conflict, which change work performed and useful-write accounting. Identities must remain distinct across warmup, recorded cells, and repetitions. |
| Fixed valid amount | Hold payload and domain work constant under the existing positive-money rules. The value is recorded later; no amount is selected here. |
| PRE_TRANSACTION and OCC | Follow the current writer default and current-source / Stage 4B.2 precedent. This is not a claim that PRE/OCC is universally faster, safer, or better. |
| STRICT FullProof validation | Exercise the current real validation composition rather than OFF or a synthetic allow-all substitute. |
| Retained distinct lane connections | Preserve supplied-connection ownership and isolate writer timing from connection creation without concurrent connection sharing. |

These choices follow the
[aggregate CREATE/PAY rules](../../../src/core/order/aggregate.py),
[writer defaults and measured API](../../../src/pipeline/transactional/postgres_write_side.py),
[writer configuration](../../../src/pipeline/transactional/postgres_write_side_config.py),
[idempotency store](../../../src/storage/postgres_idempotency_store.py), and
[PR7 runtime composition](../../../experiments/stage4b2/postgres_bounded_concurrency_runtime.py).

Record the actual supplied validation runtime, mode, validator, policy, and
gate identity, not merely a configuration label. The
[current runtime](../../../src/compass/transition/runtime.py) supports the
evidence-aware validation path used by the current writer. Historical timing
values do not establish current-source performance.

## 5. Fixed Total Work

```text
K
= predetermined finite workload size for one recorded cell/repetition
```

K remains fixed across compared concurrency levels. It counts planned
requests, not a target number of successful writes. Failure does not authorize
replacement requests or retries to reach K successes. No K is selected here.

Historical PR7 recorded thirty synchronized bursts per exact cell, each with N
invocations, so recorded work was `30N`. Its warmup work also varied with N.
The [PR7 schedule](../../../experiments/stage4b2/postgres_bounded_concurrency_runtime.py)
was fixed, but its total work was not constant across concurrency levels.

```text
PR7: total recorded work varied with N
PR1: total work K remains fixed while offered concurrency changes
```

PR1 must not copy the `30N` schedule. Warmup is separately identified and
excluded from K. A stopped cell with residual work is incomplete evidence,
not a completed K-request characterization.

## 6. Scheduling Model

The first method is a finite closed-loop worker model:

```text
prepare K workload items
→ make all K eligible at one declared offer/release boundary
→ N persistent workers / lanes
→ each available lane claims one item
→ execute writer
→ terminal observation
→ same lane claims next pending item
→ continue until workload drains or stop rule applies
```

Connections, writers, validators, request identities, and request inputs are
prepared before recorded release. An initial synchronized release may provide
one common clock reference. Replenishment must not require all lanes to finish
one global batch before an available lane claims another item.

The finite work queue is experiment scheduling, not a production waiting or
capacity-admission policy. There is no automatic retry, replacement sample,
outcome-driven extension, or silent connection replacement.

```text
offered concurrency
!= configured worker count
!= observed writer overlap
```

Offered concurrency is the declared simultaneous execution opportunity while
pending work remains. Configured worker count is the number of workers created.
The initial implementation may configure worker count equal to offered
concurrency, but that configuration does not prove actual overlap. Offering
all K items does not claim K simultaneous writer calls.

## 7. What This Method Does Not Model

Completion-driven replenishment slows dispatch when writer calls slow. The
finite closed-loop protocol does not establish:

- open-loop production arrivals;
- sustained external RPS;
- production queue growth;
- production burst tolerance;
- connection-pool checkout behavior;
- connection-acquisition pressure under uncontrolled arrivals;
- distributed admission scope;
- production latency SLA/SLO; or
- real production capacity.

Finite scheduling wait is evidence about this declared experiment, not a
production arrival distribution. Initial backlog alone is not overload proof.

## 8. Outer Execution Ledger

The outer ledger is experiment-owned evidence, not a production state machine.
Immutable per-request observations are the primary truth source; aggregate
counts and occupancy are derived from them later.

| Observation | Meaning |
|---|---|
| Planned | Item belongs to the predetermined K-item workload. |
| Offered | Item became eligible at the declared offer/release boundary. |
| Dispatched | A lane claimed the item for execution. |
| Writer entered | The experiment crossed the declared public writer call boundary. |
| Terminal observation | The experiment retained a normal return or safely observed failure; this does not imply acceptance. |
| Unfinished / residual | Planned or offered work remains unexecuted, or an entered call has no observed exit when observation stops. |

Pending work means offered but not yet dispatched. A request-specific failure
before writer entry remains a failure-before-entry observation, not a refusal.
Connection preparation before offering is recorded separately: a setup failure
can leave planned work with no offered requests, and must not manufacture K
request failures.

```text
capacity refusal mechanism = absent
```

Do not manufacture REFUSED records. A reported zero capacity-refusal count
means no capacity-refusal mechanism was present, not that a CapacityGate
admitted every request. Experiment dispatch does not establish Semantic
Admission or concurrency admission.

## 9. Timing Boundaries

Use one declared monotonic clock domain for outer timestamps:

| Timestamp | Observed boundary |
|---|---|
| `offer_ns` | The common boundary making the recorded workload eligible. |
| `dispatch_ns` | The lane claims this item. |
| `writer_entry_ns` | Immediately before invoking the prepared public writer method. |
| `writer_exit_ns` | Immediately after public return or when an escaping exception reaches the outer boundary. |
| `terminal_observation_ns` | Minimal outer return/failure evidence has been retained. |

Preserve absence when a timestamp is unavailable. The public-call boundary is
an application observation, not an instrument inserted at a PostgreSQL
statement or inside production code. Entry/exit bracketing includes call-edge
observation uncertainty and measured-API delivery overhead.

| Derived timing | Definition |
|---|---|
| Scheduler queue wait | `dispatch_ns - offer_ns` |
| Dispatch-to-entry delay | `writer_entry_ns - dispatch_ns` |
| External writer-call elapsed | `writer_exit_ns - writer_entry_ns` |
| Terminal-observation overhead | `terminal_observation_ns - writer_exit_ns` |
| Total outer latency | `terminal_observation_ns - offer_ns` |

Derive an interval only when both boundaries are known and ordered. Total
outer latency includes finite-experiment scheduling delay. It is not
PostgreSQL service time, writer service time, or backend latency.

For a fully drained recorded cell, recorded-run elapsed spans the common offer
boundary through the last terminal observation. Preserve any earlier stop
boundary and unfinished intervals separately for an incomplete cell. Setup,
warmup, durable verification, aggregation, and evidence serialization are
outside this recorded workload window. Minimal observation work between calls
still affects replenishment and must remain visible.

## 10. Actual Concurrency Evidence

Derive observed application-call concurrency from complete intervals:

```text
[writer_entry_ns, writer_exit_ns)
```

Retain enough raw evidence to derive maximum overlap, time-weighted overlap,
time spent at each overlap level, initial ramp, final drain, lane utilization
and gaps, and pending backlog while overlap is below configured concurrency.
Report the observation window used for time-weighted values. An unfinished
call must not receive a fabricated exit timestamp or disappear from residual
accounting.

```text
writer-call overlap != physical PostgreSQL CPU concurrency
writer-call overlap != exact physical transaction overlap
```

Only observable application-call overlap is claimed. Existing production
phase durations do not supply absolute phase timestamps and cannot establish
exact business-UOW overlap on their own.

## 11. Connection Topology

The initial method retains one distinct PostgreSQL connection per active lane.
No connection is shared concurrently between lanes. Connection creation and
writer/runtime construction occur outside recorded writer timing, with
separate setup elapsed, success/failure, and readiness evidence. Distinguish
direct connection creation from database guards and other preparation work.

The [connection helper](../../../src/storage/postgres_connection.py) gives
connection lifetime to the caller. The writer retains that supplied
connection; the [UOW](../../../src/pipeline/transactional/postgres_unit_of_work.py)
owns business finalization, not connection lifetime.

```text
PRE rollback = ends the implicit read transaction
PRE rollback != connection release
```

This retained-connection method does not characterize pool checkout or
uncontrolled connection-acquisition demand. If setup reaches the first
resource ceiling, retain it as a connection-topology/resource boundary, not
a demonstrated writer-capacity knee. Do not silently run the cell with fewer
lanes than declared.

## 12. Existing Production Measurement Reuse

PR1 invokes the existing `create_order_with_measurement()` API unchanged.
The [production measurement contract](../../../src/pipeline/transactional/postgres_write_side_measurement.py)
and [instrumentation](../../../src/pipeline/transactional/postgres_write_side_measurement_instrumentation.py)
remain authoritative for the following fields; this summary does not redefine
their boundaries.

| Existing phase | Relevance |
|---|---|
| `producer_write_invocation` | Producer execution through normal finalization, excluding final measurement construction. |
| `business_uow` | Application UOW lifetime, not exact physical transaction lifetime. |
| `validation_runtime_call` | Current write-side validation-runtime call. |
| `preliminary_idempotency_check` | PRE preliminary lookup. |
| `preliminary_read_cleanup` | PRE implicit-read-transaction cleanup. |
| `authoritative_idempotency_check` | Idempotency check within the business UOW. |
| `accepted_history_load` | Event-store history loading. |
| `concurrency_preparation_call` | Current gate preparation; OCC preparation does not pre-lock. |
| `pessimistic_advisory_try_lock_call` | Concrete nonblocking try-lock; not applicable to the initial PRE/OCC fixture. |
| `append_admission_call` | Append admission including its persistence/translation work, not pure OCC or INSERT cost. |
| `idempotency_record_call` | Transaction-local idempotency persistence. |
| `commit_finalization` | Current UOW commit call. |
| `rollback_finalization` | Current UOW rollback call, distinct from preliminary read cleanup. |

Phase intervals overlap. Their durations must not be summed into total cost.
Preserve each phase's `state` and `elapsed_ns` without converting absence into
measured zero:

```text
missing != zero
NOT_REACHED != NOT_COLLECTED != NOT_APPLICABLE
```

Production measurement is optional internal explanatory evidence beneath the
outer ledger. Normal rejection can deliver measurements for reached phases.
An escaping producer/finalization exception does not guarantee normal delivery.
Post-return measurement-construction failure instead preserves the normal
producer value with measurement unavailable. Measurement unavailability limits
phase analysis; it must not erase an acknowledged accepted write.

## 13. Escaping Failure Observation

The experiment must retain evidence when normal measurement delivery does not
occur. Preserve only safely observable information:

- exception class;
- safe SQLSTATE, if directly available;
- whether writer entry occurred;
- known outer phase;
- available timestamps; and
- acknowledgement knowledge.

Do not retain raw traceback, raw connection representation, arbitrary exception
message, or parsed human admission reason. Do not infer SQLSTATE from prose.
Do not fabricate `PostgresWriteSideResult`, `PostgresWriteSideMeasurement`,
`SemanticOutcome`, or capacity refusal.

An outer failure during the writer call does not reveal its internal database
phase. Preserve unknowns. The
[existing exception tests](../../../tests/unit/pipeline/transactional/test_postgres_write_side_measurement_instrumentation.py)
establish that producer/finalization exceptions escape without normal
measurement delivery.

Preserve the original observation before subsequent classification, connection
verification, durable verification, or serialization failure can erase it.
Harness/correctness defects remain distinct from observed native failures, and
native failure alone does not establish overload as its cause.

If a lane becomes unusable or execution stops, retain prior observations and
all residual work. Do not disguise partial execution by silently retrying,
replacing a connection, or reducing concurrency. Exact stop/deadline rules
remain subject to the live-run gate. A deadline does not prove a writer stopped;
do not verify/reset as though the workload were quiescent while calls remain
unresolved. This method makes no evidence-survival guarantee for process or
host termination.

## 14. Acknowledgement Semantics

| Observation | Conservative acknowledgement knowledge |
|---|---|
| Normal exact writer ACCEPTED return | Commit returned normally before public writer return. |
| Normal replay, block, or rejection | No new acknowledged accepted write from this invocation. |
| Failure before writer entry | Writer was not entered. |
| Escaping writer/finalization exception | Acknowledgement is generally UNKNOWN at the outer boundary. |
| Later durable state found | Durable effect observed; client acknowledgement is not retroactively established. |

The current writer returns through UOW context exit. Its accepted result can
be constructed before commit, but public normal return follows successful
finalization. A result-shaped object or pre-commit checkpoint alone therefore
does not establish acknowledgement.

```text
durable effect observed
!= retroactive proof that client acknowledgement occurred
```

Retain acknowledgement and durable verification as separate evidence.

## 15. Useful Work Accounting

The primary useful-work numerator is acknowledged accepted writes. Keep
generic completed terminal observations and each producer outcome separate.
For a fully drained cell, acknowledged accepted throughput is that numerator
divided by recorded-run elapsed, expressed in seconds and qualified by this
finite closed-loop protocol.

Do not treat all completions as useful writes, invert mean latency to obtain
throughput, or average per-request reciprocal latencies. Incomplete cells retain
counts and elapsed evidence without being presented as completed K-request
comparisons.

Fresh independent CREATE should normally produce accepted writes. Unexpected
`STALE_WRITE`, REPLAY, idempotency CONFLICT, `VALIDATION_BLOCKED`, or preparation
`LOCK_TIMEOUT` under declared OCC requires fixture/composition investigation
before capacity interpretation.

Preserve preparation versus append rejection. The
[current admission translation](../../../src/pipeline/transactional/postgres_admission.py)
can translate native `LockNotAvailable` into append `LOCK_TIMEOUT`, including
under OCC. That is not the same observation as pessimistic preparation
non-acquisition and is not automatically a same-stream fixture defect or
proven overload. A translated verdict does not retain a native SQLSTATE that
was not delivered separately.

## 16. Durable Post-Run Verification

After a recorded cell/repetition becomes quiescent, verify durable state outside
workload timing, using a fresh verification transaction. Connection ownership
must remain exclusive during verification.

For acknowledged accepted requests, check the existing authoritative behavior:

- exactly one accepted CREATE effect, represented by a CREATED event;
- event sequence equals 1;
- event matches the returned event and planned request, order, and amount;
- matching durable idempotency mapping for the complete request signature;
- idempotency check resolves to the same accepted event; and
- no duplicate accepted effects.

The [write-side schema](../../../db/migrations/001_create_write_side_tables.sql)
and [existing measurement correctness tests](../../../tests/integration/pipeline/transactional/test_postgres_write_side_measurement_correctness_integration.py)
provide the correctness basis. Reading idempotency memory is not another writer
invocation.

Normal non-accepted requests and pre-entry failures must have no new accepted
effect attributable to that request. Reconcile ambiguous failures separately
as durable effect present, durable effect absent after reliable verification,
or still unknown. Durable effects found after ambiguous failure do not join
the acknowledged accepted numerator.

Do not add business invariants or require global-position commit ordering or
contiguous global positions. The
[global-position schema contract](../../../db/migrations/003_add_order_events_global_position.sql)
explicitly distinguishes allocation from commit order. If verification cannot
complete, preserve correctness as unverified rather than claiming it passed.

## 17. Raw Evidence First

PR1 retains raw observations before PR2 interpretation and does not discard
samples after aggregation. Every request needs experiment-local identity and
enough evidence for outer timestamps, outcome/verdict, acknowledgement status,
measurement availability and phase values, safe failure evidence, and
verification linkage. These are not new runtime-governance identities.

Each cell/repetition retains:

- planned, offered, dispatched, entered, and terminal counts;
- unfinished/residual work, including missing call exits;
- acknowledged accepted count and separate outcome counts;
- recorded-run elapsed and any incomplete-run stop boundary;
- overlap evidence and its observation window;
- connection/setup and workload-preparation elapsed;
- verification elapsed and result; and
- validity qualifications.

Derived counts must reconcile with request observations. Retain incomplete or
invalid-run evidence with explicit qualifications rather than publishing only
successful runs and losing degradation or defect evidence. Exact file formats
and retention mechanics belong to later experiment implementation.

## 18. Statistical Discipline

Future reports may include descriptive statistics with exact cohorts, sample
counts, and retained raw samples. Keep acknowledged accepted calls, other
normal outcomes, and failures distinguishable.

```text
p50 and p95
= only with explicit sample count and estimator

p99
= only when sample size and repetition support the claim
```

Thirty samples do not make a strong p99 estimate. One hundred samples is not
a universal adequacy threshold. Requests within one run are not automatically
independent replicates. Do not invent confidence claims or pool incompatible
cells merely to increase tail sample size.

Reuse historical discipline: predetermined warmups, recorded repetitions,
explicit ordering, and no outcome-driven extension. Repeat complete fixed-work
cells to expose variability and ordering effects. Do not adopt PR7's counts as
PR1 defaults; no sample counts, warmup counts, or repetition counts are chosen
here.

## 19. Generator Credibility

PR1 must preserve evidence capable of falsifying its own generator:

| Potential limitation | Required diagnostic evidence |
|---|---|
| Worker count rises but overlap does not | Overlap distribution, pending backlog, lane counts/utilization. |
| Scheduling or barrier overhead dominates | Initial release offsets/skew, dispatch-to-entry delay, replenishment gaps. |
| Measurement overhead materially changes results | Matched current-measured/current-unmeasured control observations using the same outer ledger, separately identified. |
| Connection setup dominates | Separate connection creation, readiness, failure, and total setup observations. |
| Workload preparation dominates | Preparation elapsed and proof that identities/inputs were prepared before recorded release. |
| Observation/recording dominates replenishment | Exit-to-terminal and terminal-to-next-dispatch gaps. |

The [historical observer-effect method](../stage_4b_2/postgres_strategy_comparison_method.md)
supplies a control pattern, not a current overhead estimate. Internal phase
timings cannot estimate their own observer cost, and historical overhead must
not be subtracted from current samples. If Python scheduling remains a credible
confounder, obtain separately scoped diagnostic evidence before claiming a
backend knee; call overlap alone does not locate the bottleneck.

Any controls are part of a separately approved execution schedule and must not
be pooled with primary measured cells. Do not introduce multiprocessing or
distributed generation unless future evidence requires it. The first
implementation remains the smallest credible local characterization.

## 20. Interpretation Boundary

PR1 may observe throughput, latency, overlap, waiting, and native failures. It
does not decide a capacity knee, safe operating limit, production headroom, or
admission threshold. PR2 owns degradation/capacity interpretation and operating
implications; any later mechanism still requires separate justification.

```text
Allowed PR1 conclusion:
characterization evidence collected

Possible later PR2 conclusions:
no useful knee established
possible degradation/knee region observed
```

Neither conclusion is asserted by this method document. Experimental connection
headroom needed to authorize a bounded run is separate from a production
operating-headroom decision.

## 21. Validity / Falsification Matrix

| Observation | Evidence qualification / interpretation boundary |
|---|---|
| Throughput keeps improving with credible overlap | Valid bounded observations; a later negative knee finding is allowed. |
| Throughput flattens while overlap and latency rise | Preserve for PR2 interpretation; no automatic knee or operating limit. |
| Worker count rises but overlap does not | Intended execution opportunity was not realized; no backend-saturation inference. |
| Generator scheduling, barrier, or recording dominates | Qualify or stop backend interpretation; the generator is a competing explanation. |
| Unexpected STALE_WRITE | Investigate fixture, identity, sequence, or external interference before capacity interpretation. |
| Unexpected replay or idempotency conflict | Request freshness or initial-state assumption failed. |
| Unexpected VALIDATION_BLOCKED | Investigate workload and actual validation composition. |
| Preparation LOCK_TIMEOUT under OCC | Inconsistent with current admitted no-op preparation; investigate composition/accounting. |
| Append LOCK_TIMEOUT or INFRASTRUCTURE_ERROR | Preserve exact stage and verdict; source-specific investigation is required. |
| Native infrastructure/resource failure | Retain observed failure; it is not automatically proven overload. Harness and fixture integrity still matter. |
| Connection ceiling during setup | Connection-topology/resource observation; that writer concurrency cell did not execute as planned. |
| Ambiguous commit | Exclude from acknowledged accepted numerator; reconcile durability separately. |
| Acknowledged effect or matching mapping missing durably | Correctness failure invalidates trustworthy throughput interpretation. |
| Verification unavailable | Timing/failure observations remain, but correctness is unverified. |
| Shared database or host interference | Equivalent-cell interpretation is unsupported unless interference was explicitly controlled and recorded. |
| Cell abort with residual work | Partial evidence, not a completed fixed-K cell. |
| Harness deadline | Unfinished observation; not a native DB timeout or proof that writer execution terminated. |

```text
valid negative result != invalid experiment
native observed failure != proven overload cause
```

Missing/duplicate records, impossible timestamps, connection sharing, or other
harness/accounting defects invalidate affected evidence. Do not hide such
defects among native degradation observations or replace failed samples.

## 22. Database State / Isolation Requirement

Recorded cells/repetitions require equivalent initial business state,
especially accepted history, idempotency state, and relevant sequence/schema
conditions. Warmup effects must not silently change the recorded initial-state
contract. Logical state equivalence does not guarantee identical caches, WAL,
checkpoint activity, or physical storage conditions.

Historical PR7 and the
[shared integration fixture](../../../tests/integration/conftest.py) contain
shared-table reset operations covering decision receipts, projection state,
idempotency records, and accepted history. Their existence does not grant PR1
authority to run them or import their reset scope automatically.

```text
live database reset = separately approved execution action

worktree isolation != PostgreSQL isolation != host-resource isolation
```

The exact reset scope is not authorized by this document. Live characterization
requires an agreed exclusive execution window or otherwise explicitly
controlled interference. Independent Order IDs do not isolate table resets or
shared CPU, I/O, cache, and connection consumption. No operational isolation
procedure is selected here.

## 23. Provenance Requirements

Future recorded evidence must identify at least:

- source commit and working-tree qualification;
- experiment schema and method version;
- Python, psycopg, and PostgreSQL versions;
- sanitized platform/hardware and deployment topology;
- database schema/migration, isolation, and autocommit facts;
- relevant timeout and durability configuration facts;
- connection topology and preparation observations;
- writer configuration and gate identity;
- validation runtime, mode, policy, and validator identity;
- fixed amount and workload/identity-generation scheme;
- K and offered-concurrency / configured-worker levels;
- warmups, repetitions, ordering schedule, and seed;
- clock identity and measurement/control surface;
- reset protocol and initial-state qualification; and
- stop conditions and interference qualifications.

No numerical values are selected here. Capture relevant facts rather than
copying historical manifest values. Qualify intentional untracked local
tooling honestly without inspecting it or describing the whole tree as clean.
Do not retain DSNs, database endpoints/names, credentials, environment-variable
values, or arbitrary configuration dumps in evidence.

## 24. Stage 4 / Semantic Governance Exclusions

PR1 directly invokes the normal measured writer. It does not require Stage 4C,
Stage 4E, `ReinvocationAuthorization`, InvocationOwner A2 lifecycle,
DecisionReceipt, or semantic replanning.

The [existing Stage 4E owner](../../../src/pipeline/transactional/postgres_write_side_invocation_owner.py)
retains the future composition constraint:

```text
AVAILABLE → SPENT before A2 writer entry
```

Neither normal return nor exception restores authority. PR1 avoids this
composition and does not solve future capacity placement, refund authority,
or fabricate a completed invocation.

The parallel semantic-replanning responsibility remains outside PR1:

```text
VALIDATION_BLOCKED
→ failure evidence
→ new intent
→ new RequestSignature
→ governance again
```

Shared writer, request-identity, validation, result, and database infrastructure
does not transfer ownership of their semantics to capacity characterization.
Capacity Admission remains separate from Semantic Admission, Concurrency
Control, Transaction Atomicity, Stage 4C, and Stage 4E.

## 25. Implementation Boundary

The reviewed prospective ownership namespaces are:

```text
experiments/load_capacity_protection/
tests/experiments/load_capacity_protection/
tests/integration/experiments/load_capacity_protection/
```

The experiment-owned implementation now includes
[`runner.py`](../../../experiments/load_capacity_protection/runner.py) and
[`evidence.py`](../../../experiments/load_capacity_protection/evidence.py).
Production modules, Stage 4B.2 code/evidence, and shared integration fixtures
remain unchanged. PR1 remains ACTIVE; these entry points do not authorize a live run.

The runner requires an explicit `LoadRunPlan`: fixed K, ordered concurrency
levels, warmup and recorded repetition counts, ordering seed, canonical amount,
test database name, connection budget, one declared control connection,
connection timeout, stop policy, and cleanup policy. The implemented stop policy
stops claims and waits for quiescence without a hard deadline. Warmups are
separately labeled diagnostic cells. Per-cell identities include run, level,
cohort, repetition, and workload index; the explicit seed selects the same index
permutation for each cell. Declared peak connections are max(N) plus one.

The separately callable cleanup deletes only exact declared request/order pairs
from `idempotency_records`, then `order_events`, and verifies their absence.
Every cell first refuses pre-existing identities. Cleanup is used only after a
fully accepted, durably verified cell; incomplete, failed, or unverified cells
retain their rows and stop the remaining plan. No TRUNCATE, CASCADE, or sequence
reset occurs. This preserves equivalent logical state for this workload while
leaving global-position allocation, caches, and physical database effects visible.
The exact live cleanup scope and exclusive execution conditions still require
approval under Section 26.

Evidence schema version `1`, method version `pr1-unprotected-finite-load-v1`,
preserves raw timestamps, identities, acknowledgement, outcome/admission/validation
verdicts, event links, phase states and values, safe failures, durable readback,
residual work, and provenance. Readback produces immutable experiment facts,
not reconstructed production result objects. Reason strings, arbitrary validator
metadata, governance carriers, and live resources are excluded. Unsupported
versions, unknown types/fields, and inconsistent accounting summaries are rejected.
Optional provenance remains explicitly absent; local Git qualification covers
tracked changes and explicitly leaves untracked files uninspected.

Cells are delivered to an explicit evidence sink after resource closure and
before proceeding to another cell. File output uses exclusive creation and
never overwrites existing evidence. A sink failure retains raw cells in the
raised experiment exception. Descriptive helpers expose sample counts, raw
latency samples, acknowledged accepted throughput for completed finite cells,
and interval-based overlap. They do not calculate percentiles or capacity policy.

## 26. Live-Run Gate

Method documentation and later harness implementation do not themselves
authorize live PostgreSQL load characterization. Before any such execution,
explicit human approval must cover:

- K;
- concurrency levels;
- warmups;
- repetitions;
- order/seed schedule, including any control cells;
- stop/deadline rules;
- test database;
- exact reset scope;
- connection budget and experimental headroom; and
- exclusive execution conditions or explicitly controlled interference.

No numbers are selected by this document. Database correctness-test execution
also requires its own applicable authorization; it is not implied by writing
the tests. Finite work does not guarantee finite wall-clock completion, and
deadline behavior must preserve acknowledgement uncertainty and residual work.

## 27. Non-Goals

PR1 does not:

- implement rate limiting;
- implement CapacityGate;
- implement a semaphore or bulkhead;
- implement production queueing or backpressure;
- implement load shedding;
- introduce a connection pool;
- choose a capacity threshold;
- choose an RPS or burst policy;
- claim production capacity;
- modify the production writer;
- modify OCC or pessimistic behavior;
- modify Semantic Admission;
- modify Stage 4C or Stage 4E;
- modify semantic replanning;
- rewrite Stage 4B.2;
- interpret a final capacity knee; or
- begin PR2.

This step adds method documentation and navigation/status alignment only. It
contains no experiment implementation, recorded results, benchmark execution,
database reset authorization, or production policy.
