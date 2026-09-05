# Load / Capacity Protection PR0 — Research and Responsibility Boundary

[← Back to Load / Capacity Protection](README.md)

```text
PR0
= responsibility / research boundary documentation

Load / Capacity Protection
= separately owned investigation

Production capacity mechanism and numerical policy
= NOT SELECTED
```

This note records the boundary established by the reviewed read-only PR0 audit
at repository base `c5b8aec`. Current-execution claims below refer to that source
baseline. Historical Stage 4B.2 observations retain their own source and
environment qualifications. Future experiment requirements are research scope,
not implemented behavior or production policy.

## 1. Purpose

The repository currently lacks a general application/backend capacity-protection
boundary in its inspected production composition. Existing transaction,
concurrency, and invocation-lifecycle mechanisms have narrower responsibilities.

The new research problem is:

> How much application work may enter a specified resource-consuming backend
> execution boundary when offered demand exceeds useful capacity?

PR0 does not answer this question numerically. It freezes what must be understood
before a capacity mechanism or operating policy can be justified.

This work continues the separately owned capacity handoff in
[Why Bounded Concurrency Evidence Precedes Load Admission](../stage_4b_2/why_bounded_concurrency_evidence_precedes_load_admission.md)
and the [Stage 4B.2 closeout](../stage_4b_2/stage_4b_2_closeout.md).
It does not reopen Stage 4B.2.

## 2. Responsibility Boundary

```text
Capacity Admission
!= Semantic Admission

Capacity Admission
!= OCC

Capacity Admission
!= Pessimistic Locking

Capacity Admission
!= Transaction Atomicity

Capacity Admission
!= Stage 4C Current-Response Authority

Capacity Admission
!= Stage 4E Re-invocation Authority
```

The conceptual question for capacity admission is:

```text
Capacity Admission
= may this work consume the specified backend capacity now?
```

Capacity admission is conceptual workstream terminology at PR0. No production
type, result vocabulary, refusal policy, or enforcement mechanism is introduced.

| Responsibility | Question |
|---|---|
| Capacity admission | May application work enter the specified resource-consuming execution boundary now, under a separately justified capacity policy? |
| Semantic Admission | May this candidate become accepted business truth? |
| Concurrency correctness | Can this write still proceed against current authoritative state and occupy the intended stream position? |
| Transaction atomicity | Do related durable writes commit or roll back together? |
| Stage 4C Current-Response Authority | How may the caller handle an already-completed semantic outcome? |
| Stage 4E Re-invocation Authority | May eligible completed evidence authorize one additional invocation of the owner-retained same complete request? |

These distinctions preserve the existing
[concurrency boundary](../../boundary_notes/concurrency_boundary.md),
[transaction atomicity decision](../../adr/0010_transaction_atomicity_vs_concurrency_admission.md),
[Semantic Admission vocabulary](../../semantic_admission/glossary.md),
[Stage 4C invariants](../stage_4c/stage_4c_closeout.md), and
[Stage 4E responsibility](../stage_4e/stage_4e_closeout.md).
Passing a capacity boundary cannot make candidate work accepted history.

```text
capacity refusal
!= semantic invalidity
!= concurrency conflict
!= retry/replanning authority
```

## 3. Current Execution Surface

The current explicit PostgreSQL composition is:

```text
caller
→ runtime owner
→ invocation owner
→ public PostgreSQL writer
→ PRE_TRANSACTION / IN_TRANSACTION path
→ UOW / storage / concurrency gate
→ caller-owned psycopg connection
→ PostgreSQL
```

The
[runtime builder](../../../src/bootstrap/build_postgres_write_side_decision_receipt_runtime.py)
constructs the writer around a supplied business connection. The
[runtime owner](../../../src/pipeline/transactional/postgres_write_side_decision_receipt_runtime_owner.py)
delegates through the
[invocation owner](../../../src/pipeline/transactional/postgres_write_side_invocation_owner.py)
to the public writer. This is a callable composition, not an established
traffic-facing server or general request scheduler.

Capacity-relevant facts at the audited baseline are:

- The business connection is caller-owned. The
  [connection helper](../../../src/storage/postgres_connection.py) creates a direct
  connection with a finite connection timeout; it does not establish a capacity
  policy.
- The [writer](../../../src/pipeline/transactional/postgres_write_side.py) retains
  its supplied connection. No general business connection pool exists in the
  inspected source.
- PRE performs preliminary idempotency and history reads before validation.
  Its cleanup rolls back the implicit read transaction without closing or
  releasing the retained connection. PostgreSQL work therefore begins before
  the later business UOW.
- The [UOW](../../../src/pipeline/transactional/postgres_unit_of_work.py) owns
  business commit/rollback, not connection lifetime. Application UOW entry is
  not itself an SQL statement or an exact physical transaction-start marker.
- No application-wide capacity semaphore, general traffic-facing queue, or
  load-shedding boundary was found in the inspected production path.
- Owner-local locks synchronize lifecycle state and, in the outer runtime
  owner, invocation delegation. They are not backend capacity budgets across
  independent owners.

Independent callers with distinct writer connections have no shared application
capacity decision in this composition. This observation does not establish safe
concurrent sharing of one writer/connection.

Same-stream contention must remain separate from aggregate overload. The
[pessimistic gate](../../../src/pipeline/transactional/postgres_admission.py) can
return preparation `LOCK_TIMEOUT` when a nonblocking advisory try-lock returns
false. Append-time lock failure has a separate translation path. `STALE_WRITE`
describes append continuity/conflict evidence. Neither status alone establishes
backend capacity exhaustion.

## 4. What Stage 4B.2 Already Established

Stage 4B.2 supplies a useful measured starting point. The workstream does not
start from zero.

| Accepted evidence | Relevance to capacity research |
|---|---|
| Opt-in writer measurement | Explicit measured APIs preserve producer results separately from measurement delivery. |
| Phase applicability, reach, and availability | Thirteen producer-specific intervals distinguish measured work from absent, unreached, or uncollected evidence. |
| PRE/OCC and IN/pessimistic controlled comparison | Complete current compositions were compared under fixed workloads without selecting a universal winner. |
| Observer-effect discipline | External controls exposed visible, variable measurement overhead; phase timings are not used to estimate their own observer cost. |
| Supplemental lifecycle characterization | Preliminary reads, cleanup, business-UOW placement, and normal-return connection reuse were characterized separately from policy. |
| Bounded workers and lanes | PR7 used fixed persistent lane ownership, with one distinct retained PostgreSQL connection per lane. |
| Independent-order concurrency | Accepted work across different streams was observed separately from same-order contention. |
| Same-order contention | Exact accepted, append stale-write, and preparation lock-timeout cohorts preserved termination-placement distinctions. |
| Historical bounded-concurrency evidence | Worker levels `1/2/4/8` showed rising latency and diminishing burst-completion gains without a clear plateau or decline in the recorded range. |

Evidence sources:

- [Write measurement contract](../stage_4b_2/postgres_write_measurement_contract.md)
  and [correctness validation](../stage_4b_2/postgres_write_measurement_correctness_validation.md).
- [Controlled comparison report](../stage_4b_2/postgres_strategy_comparison_report.md)
  and [supplemental lifecycle report](../stage_4b_2/postgres_idempotency_transaction_lifecycle_report.md).
- [Bounded concurrency method](../stage_4b_2/postgres_bounded_concurrency_method.md)
  and [bounded concurrency report](../stage_4b_2/postgres_bounded_concurrency_report.md).
- [PR7 runtime](../../../experiments/stage4b2/postgres_bounded_concurrency_runtime.py)
  and [canonical manifest](../../../experiments/stage4b2/evidence/stage4b2-pr7-canonical-levelc/stage4b2-pr7-canonical-cdbe542/manifest.json).

The recorded worker levels are historical experiment points, not selected
settings for this workstream. Synchronized-burst completion is not sustained or
open-loop production throughput. These are not current PR0 benchmark results.

## 5. What Stage 4B.2 Did Not Establish

Stage 4B.2 did not establish:

- safe production concurrency;
- a capacity knee or saturation threshold;
- an application arrival-rate limit or burst policy;
- a production queueing or backpressure policy;
- load shedding;
- connection-pool policy or optimal pool size;
- a production or optimal worker count;
- production operating headroom; or
- capacity-admission scope across processes, keys, or other resource boundaries.

Its retained-connection protocol also does not characterize connection
acquisition under uncontrolled demand or traffic waiting before writer entry.
Experiment connection-budget feasibility and reviewed experimental headroom do
not establish production operating headroom.

These are separately owned questions, not incomplete Stage 4B.2 deliverables.
Historical values remain environment-qualified observations, not production
limits. The [closeout](../stage_4b_2/stage_4b_2_closeout.md) and
[future capacity handoff](../stage_4b_2/why_bounded_concurrency_evidence_precedes_load_admission.md)
explicitly preserve this separation.

## 6. Measure Before Protect

The intended research order is:

```text
measurement
→ load characterization
→ observed degradation / knee / saturation evidence
→ operating-headroom decision
→ capacity mechanism
→ optional rate/burst shaping if separately justified
```

This workstream rejects:

```text
arbitrary limiter number
→ benchmark afterward
```

The existing
[measurement rationale](../stage_4b_2/measurement_vocabulary_and_ownership.md)
already separates capacity engineering from future policy. The
[bounded-concurrency rationale](../stage_4b_2/why_bounded_concurrency_evidence_precedes_load_admission.md)
requires separately owned arrival assumptions, resource constraints, service
objectives, safety margin, and admission scope before mechanism selection.

PR0 makes the interpretation boundary explicit:

```text
observed failure point
!= chosen operating limit

observed knee
!= automatic admission policy
```

Any capacity result remains scoped to its actual hardware, PostgreSQL
configuration, connection topology, workload, writer strategy, validation
placement, database state, experiment fixture, and source and measurement
version. One observation cannot become a universal production capacity constant.

## 7. Missing Observation Surface

The minimum future addition is an experiment-owned outer execution ledger:

```text
offered
dispatched / experiment-admitted
pending
writer entered
completed
refused
failed before writer entry
```

These labels describe observation requirements, not a production state machine.
Experiment-admitted means dispatched into the experiment's execution boundary;
it does not mean semantic acceptance or a concurrency gate's admitted verdict.
An unprotected run has no capacity-refusal mechanism. It must distinguish zero
capacity refusals from failures before entry and other terminal observations.

PR1 needs to observe:

- actual in-flight writer overlap, rather than infer it from configured lanes;
- offer, dispatch, writer-entry, and terminal observation timing;
- outer latency and scheduling wait, with the offer boundary explicitly defined;
- business connection setup/acquisition elapsed and failures;
- escaping exception class, safe SQLSTATE where available, known writer-entry
  status, and the outer failure phase actually observed;
- acknowledged accepted writes separately from other completions and ambiguous
  commit outcomes;
- durable post-run verification; and
- raw latency samples and experiment provenance sufficient to assess the
  distributions and compare equivalent workloads.

With retained connections, setup/acquisition is observed separately from writer
timing. Such a run does not measure acquisition waiting under uncontrolled
arrivals. Scheduling wait in a finite experiment is not evidence of a production
queue or production arrival distribution.

Existing
[producer measurement](../../../src/pipeline/transactional/postgres_write_side_measurement.py)
is delivered after normal return, including normal-return rejection paths.
An escaping producer or finalization exception yields no normal phase delivery;
measurement-construction failure instead preserves the producer value with
unavailable measurement. The
[measured writer boundary](../../../src/pipeline/transactional/postgres_write_side.py)
and [exception tests](../../../tests/unit/pipeline/transactional/test_postgres_write_side_measurement_instrumentation.py)
preserve that distinction.

PR7's outer timer retains elapsed time and exception class, but its frozen
method treats unexpected exceptions as invalid-run evidence. A future overload
experiment therefore needs its own failure-complete observation and validity
rules. It must retain failures without manufacturing writer results or changing
the historical PR7 contract. Internal database failure phase remains unknown
unless independently observed. Phase durations overlap and must not be summed;
missing evidence must not be converted to zero.

CPU, I/O, WAL, server wait events, and production pool metrics are optional later
telemetry concerns. They are not part of a production telemetry design in PR0.

## 8. Next Experiment Question

> For a fixed current writer composition and independent finite CREATE workload,
> when does increasing offered concurrent execution cease to improve
> acknowledged accepted-write throughput and predominantly increase waiting,
> latency, or failures?

The initial experimental boundary is:

```text
fresh independent Order IDs
+ unique request IDs
+ fixed finite total workload
+ PRE_TRANSACTION
+ optimistic admission / OCC
+ STRICT validation
+ retained distinct connection per active lane

independent variable
= offered concurrency

actual writer overlap
= must be observed
```

PRE/OCC is first because it is the
[current writer default](../../../src/pipeline/transactional/postgres_write_side.py)
and has Stage 4B.2 precedent. It is not selected as a proven superior strategy.
The historical comparison observed lower external central latency for
IN/pessimistic in its recorded environment without establishing a universal
winner.

Independent streams remove same-stream conflict as the primary fixture while
preserving competition for shared backend resources. Keep amount, the current
STRICT FullProof validation stack, and equivalent initial database conditions
fixed and record their identities.

PR1 must hold total workload fixed across concurrency levels. PR7 instead used
N invocations per synchronized burst; its schedule is not automatically the
new experiment's method. Release/replenishment protocol and timing boundaries
require an explicit PR1 method. A finite closed-loop protocol cannot establish
open-loop production capacity.

PR0 freezes this question and initial research boundary only. It chooses no
concurrency levels, execution implementation, or production settings.

## 9. Interpretation Discipline

The qualitative regions of interest are:

```text
healthy scaling
↓
degradation region
↓
possible capacity knee
↓
saturation
```

This is an interpretation guide, not a mathematical law or guaranteed sequence
of observations. PR0 freezes no estimator or numerical threshold.

Evidence for a possible knee may include repeated comparable observations of:

- little or negative marginal gain in acknowledged accepted-write throughput;
- increasing outer and upper-tail latency;
- increasing scheduling/resource wait;
- increasing writer or business-UOW elapsed; and
- increasing failures or timeouts.

Actual concurrency must rise and the generator must remain credible. Failures
can support interpretation but are not required to observe degradation.
Upper-tail claims require adequate raw samples; PR7's descriptive aggregates
contain median, not p95/p99 estimates.

```text
no knee established in tested range
= valid research result
```

The experiment must not be forced to discover saturation. A bounded degradation
observation can be useful without establishing either a knee or an operating
limit.

## 10. Falsification / Invalid Interpretation

| Observation | Interpretation boundary |
|---|---|
| Configured concurrency rises but actual writer overlap does not | The intended variable was not exercised; do not infer backend saturation. |
| Throughput continues improving without a meaningful waiting/failure trade-off | No useful knee has been established in that range. |
| Supposedly independent requests unexpectedly produce stale/conflict outcomes | Investigate fixture, identity, or correctness assumptions before capacity interpretation. |
| Generator scheduling or instrumentation dominates | The result does not isolate a backend capacity boundary. |
| Connection setup becomes the first ceiling | Report a connection-topology/resource boundary, not a demonstrated writer-capacity knee. |
| Equivalent workload/database state cannot be maintained | The cells are not comparable for the intended claim. |
| Commit outcome is ambiguous | Do not count it as known success or known absence without evidence. |

These observations must not be converted into unsupported capacity claims.
A valid negative finding differs from an invalid experiment. Native failures
may be retained as observations under the future method without treating
correctness violations or harness defects as ordinary saturation evidence.

## 11. Stage 4E Future Composition Constraint

The existing lifecycle is:

```text
Stage 4E authorization
AVAILABLE
→ SPENT
before A2 writer entry
```

In
[PostgresWriteSideInvocationOwner.invoke_authorized_reinvocation](../../../src/pipeline/transactional/postgres_write_side_invocation_owner.py),
the owner marks authority spent and clears current-response state under its
lifecycle lock before dispatching the retained request into the public writer.
Neither a normal return nor an exception restores availability. The
[owner tests](../../../tests/unit/pipeline/transactional/test_postgres_write_side_invocation_owner.py)
cover concurrent one-shot consumption and terminal spend after an A2 exception.

A future capacity layer must not silently:

- refund spent Stage 4E authority;
- fabricate a writer result or completed-invocation handle;
- reinterpret pre-entry capacity refusal as a semantic writer outcome;
- authorize another A2; or
- change existing Stage 4E one-shot semantics.

This is a future composition constraint, not a redesign proposal. Placement and
lifecycle integration remain unresolved. The first load-characterization
experiment uses direct writer execution and avoids Stage 4E A2 integration.

## 12. Parallel Workstream Boundary

Load / Capacity Protection remains independent from the separately planned:

```text
VALIDATION_BLOCKED
→ semantic replanning
→ new RequestSignature
→ full governance
```

This sequence describes the parallel research boundary, not a claim that the
replanning path is implemented at the PR0 baseline. Shared source dependencies
may include the writer, strict validation, request identity, and result types;
capacity research does not own their semantic redesign.

Source worktrees isolate source edits, not shared PostgreSQL or host resources.
Existing [integration database fixtures](../../../tests/integration/conftest.py)
and the [PR7 runtime](../../../experiments/stage4b2/postgres_bounded_concurrency_runtime.py)
include shared-table reset operations. Independent Order IDs do not isolate
those operations or CPU, I/O, connections, and cache effects.

Performance experiments must not be assumed isolated merely because they run
from different worktrees. PR0 selects no operational isolation mechanism and
authorizes no database execution.

## 13. Delivery Sequencing Ownership

Delivery sequencing and PR-level responsibilities are maintained in the
[PR Breakdown](pr_breakdown.md). Later mechanism work remains evidence-gated;
PR3 and PR5 are not guaranteed. That plan does not authorize later work or make
Stage 4E integration implicit in a capacity mechanism.

## 14. Non-Goals

PR0 does not:

- implement load protection, a limiter, semaphore, queue, capacity gate, or load
  shedding;
- choose a threshold, RPS value, burst allowance, queue policy, or refusal
  semantics;
- choose a production worker count or pool size, or introduce pooling;
- define a production SLO/SLA or claim production capacity;
- redesign OCC or pessimistic locking, or change transaction atomicity;
- change Semantic Admission, Stage 4C, Stage 4E, or semantic replanning;
- rewrite Stage 4B.2 evidence, reports, or conclusions;
- create an ADR or a new production type;
- run database experiments, migrations, or performance optimization; or
- implement PR1 or any later PR.
