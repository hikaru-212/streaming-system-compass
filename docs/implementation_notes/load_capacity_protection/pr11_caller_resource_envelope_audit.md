# PR11 — Caller Resource Envelope and Deployment Qualification Audit

[← Back to Load / Capacity Protection](README.md)

```text
PR11 — COMPLETE / investigation; ready for human review
Production retry-enabled consumer — NONE FOUND in the audited repository
Caller resource envelope / deployment qualification — NOT ESTABLISHED / NOT QUALIFIED
ADR 0032 — Accepted; conditional Option A remains unchanged
Production implementation / new live execution — NOT AUTHORIZED
```

## 1. Purpose

Determine whether an actual production caller satisfies
[ADR 0032](../../adr/0032_keep_capacity_retry_synchronous_under_explicit_caller_resource_budgets.md).
The source baseline is `27b6db2012a0b9ad9cff8abe0e53c89e42c73cb8`, inspected on
2026-11-14. Source line references below refer to that revision.

**Disposition D: the component is production-capable, but no in-repository
production retry-enabled caller or qualified deployment is established.**
Disposition B describes the continuing architecture: synchronous retained
ownership is acceptable only under an explicit caller/deployment contract.
There is no identified caller requirement that justifies selecting a new
mechanism in this audit.

```text
mechanism implemented
!= mechanism validated
!= caller resource envelope established
!= deployment qualified
```

[PR8](pr8_bounded_retry_backoff.md) establishes the mechanism;
[PR9](pr9_production_retry_validation_report.md) characterizes it on the real
production-capable composition. [PR10](pr10_retry_waiting_ownership_decision.md)
and ADR 0032 accept its ownership model conditionally. Neither experimental
completion nor architectural acceptance supplies the missing deployment contract.
[ADR 0031](../../adr/0031_separate_resource_occupancy_retry_and_arrival_protection.md)
continues to separate occupancy, retry and arrival protection.

## 2. Current Production Integration

The opt-in path is:

```text
external composing caller supplies signature, connection and optional policy
→ build_postgres_writer_request
→ PostgresWriterRequest.invoke
→ private PostgresTransactionalWriteSide.create_order / pay_order
→ capacity boundary → protected writer body
```

The [builder](../../../src/bootstrap/build_postgres_writer_request.py), lines
17–72, performs no I/O and forwards an already-owned connection. Its default
`retry_policy=None` preserves one attempt. It neither constructs a shared gate
nor reads deployment configuration. The sole production-source construction of
`PostgresWriterRequest` is this builder, line 58. There is no production-source
call to the builder, or construction of `WriterRetryPolicy` or
`BoundedWriterAdmission`.

The existing PostgreSQL runtime is a separate graph. Its
[DecisionReceipt builder](../../../src/bootstrap/build_postgres_write_side_decision_receipt_runtime.py),
lines 34–44 and 98–126, constructs `PostgresTransactionalWriteSide` directly and
accepts only optional occupancy protection, with no retry-policy argument.
[PostgresWriteSideInvocationOwner](../../../src/pipeline/transactional/postgres_write_side_invocation_owner.py),
lines 213–238 and 456–480, requires that writer type and dispatches retained
CREATE/PAY arguments directly. A1 and Stage 4E-authorized A2 do not pass through
`PostgresWriterRequest`.

The [generic transactional builder](../../../src/bootstrap/build_transactional_runtime.py),
lines 14–61, constructs in-memory `OrderRegistry` storage and admission. It also
does not route requests through the PostgreSQL retry composition. No audited
application entry point wires the retry builder into either runtime.

## 3. Caller Inventory

The audit searched tracked, non-secret files for all five requested names:
`PostgresWriterRequest`, `build_postgres_writer_request`, `WriterRetryPolicy`,
`retry_policy`, and `BoundedWriterAdmission`. It also traced module imports,
constructors, connection helpers and adjacent runtime dispatch. Untracked
`scripts/`, ignored raw evidence and environment/credential files were excluded.
This is a repository integration finding, not inspection of an external running
deployment or proof that no external consumer exists.

| Classification | Inventory at the source baseline | Finding |
|---|---|---|
| Production application caller enabling retry | None found | No caller-owned concurrency, lifetime or shutdown configuration is wired to this composition. |
| Bootstrap/composition | `build_postgres_writer_request.py`; `build_postgres_write_side_decision_receipt_runtime.py` | Two of the six matching `src/` files. The former exposes opt-in retry; the latter forwards a capacity gate only. |
| Production mechanism definitions | `postgres_writer_request.py`; `writer_retry_policy.py`; `transactional/writer_capacity.py`; `transactional/postgres_write_side.py` | Remaining four matching `src/` files; implementing/consuming the primitive is not application enablement. |
| Unit tests | `test_build_postgres_writer_request.py`, `test_postgres_writer_request.py`, `test_postgres_writer_request_observation.py`, `test_writer_retry_policy.py`, `test_postgres_writer_capacity.py`, `test_writer_capacity_observation.py` | Six files under `tests/unit/`; explicit test compositions, not deployments. |
| Experiment tests | `test_capacity_admission.py`, `test_pr4_characterization.py`, `test_pr5_characterization.py`, `test_pr9_characterization.py`, `test_pr9_runner.py` | Five files under `tests/experiments/load_capacity_protection/`; test-only callers. |
| Experiment execution | `postgres_runtime.py`, `pr4_characterization.py`, `pr9_characterization.py`, `pr9_runner.py` | Four files under `experiments/load_capacity_protection/`; capacity use in earlier experiments and explicit enabled/disabled PR9 composition. |
| Experiment configuration / serialization / metadata | `pr9_model.py`, `pr9_evidence.py`, `results/pr9_evidence_manifest.json` | Three further experiment files; policy representation and evidence are not production enablement. |
| Documentation | ADR 0031/0032; workstream README, breakdown, PR3, PR4 method, PR5 method, PR7, PR8, PR9 method/report, PR10 | Twelve matching documentation files before PR11; descriptions and historical evidence are not executable wiring. |

PR9's [runner](../../../experiments/load_capacity_protection/pr9_runner.py), lines
95–149, explicitly creates the shared gate and selects policy versus `None`.
Its [adapter](../../../experiments/load_capacity_protection/pr9_characterization.py),
lines 86–95, calls the real builder and invokes the owner. Its
[runtime](../../../experiments/load_capacity_protection/pr9_postgres_runtime.py),
lines 68–121, opens N exclusive lane connections plus one control connection,
then closes them after the cell. The N-worker executor and retained lanes are
experiment-owned bounds. They cannot qualify a production caller. Historical
PR5 scheduling is likewise experiment-only, not another production retry owner.

## 4. Resource Envelope

Let B be permits on one shared concrete gate, C an externally bounded population
of concurrent logical callers, and H a bound on all other PostgreSQL connections.
These are independent quantities; none is assigned a production value here.

| Invariant / demand | What source establishes | Missing caller condition |
|---|---|---|
| Active protected writer bodies ≤ B | [BoundedWriterAdmission](../../../src/pipeline/transactional/writer_capacity.py), lines 127–149 and 174–227, uses a nonblocking semaphore and finally-based release. | All intended writers must share that exact gate; unprotected writers and other gate instances are outside its bound. |
| Concurrent logical callers ≤ C | No aggregate logical-caller limiter in the request or builder. | A named caller must enforce and document C before retaining resources. B does not supply C. |
| Retained caller connections ≤ C | Conditional on one exclusively owned connection per bounded caller/retained lane. The request retains one supplied connection (lines 242–257). | Budget lanes holding idle connections before/after `invoke()` too. An active-invocation limit alone does not bound such retained idle inventory. |
| Total connections ≤ C + H | Conditional accounting identity under the preceding custody/topology assumptions, not enforced by the retry mechanism. | Define H for every other consumer and idle retained connection outside C; account across processes/instances and reserve headroom. |
| Waiting connections / waiting threads ≤ C | Each synchronous waiting request retains its existing connection and invoking thread. | Requires the external C bound; there is no independent waiter or thread budget. |
| Total application threads | No thread creation or worker-pool limit in the request/builder. | Include active, waiting, idle worker threads and other application threads in a separate budget. |

The one-shot guard in [invoke](../../../src/pipeline/postgres_writer_request.py),
lines 300–303, bounds use of one owner, not the number of owners or distinct
owners referencing one connection. A finite per-request budget is not a finite
aggregate budget. If multiple process-local gates are used, only each gate's
own bound is established; a global writer ceiling requires explicit composition
of their budgets. There is no distributed coordination here.

H cannot be inferred as zero. The DecisionReceipt builder supplies a distinct
purpose-specific connection factory (lines 106–125); its
[transaction owner](../../../src/storage/postgres_decision_receipt_transaction_owner.py),
lines 46–72, 667 and 1005, acquires and closes governance connections. The
[PostgresProjectionWorker](../../../src/pipeline/projection/postgres_worker.py),
lines 77–120 and 126–141, borrows a connection shared by its collaborators.
[Projection snapshot storage](../../../src/storage/postgres_projection_snapshot_store.py),
lines 42–48, also borrows a connection. These are potential consumers, not a
count of independently deployed connections: collaborators can share custody
within their own operation. Deployment must enumerate their actual topology,
including maintenance/control connections; no aggregate H is established.

PR9 supplies context, not a resource ceiling. At N=8 retry was dormant. At N=16
enabled median completion was 92.969%, amplification 1.852× and waiting connection
peak 8; at N=32 they were 78.125%, 3.422× and 24. Writer overlap stayed at 8 and all
2,080 observed wait boundary pairs were IDLE → IDLE. Connections remained N+1 in
both modes. These observations show attributable retention, not exhaustion or
deployment acceptability. Retained-lane pacing contributed to completion gains;
connection identity itself is not established as their cause.

## 5. Retry Lifetime / Cancellation

| Concern | Source / guarantee | Qualification |
|---|---|---|
| Attempt ceiling | [WriterRetryPolicy](../../../src/pipeline/writer_retry_policy.py), lines 8–51: positive integer `max_attempts` includes the initial attempt; exactly M−1 positive finite delays. Request lines 319–345 spend once per dispatch and terminate on exhaustion. | VERIFIED primitive. No production caller selects M or the schedule. |
| Configured waiting duration | The finite explicit sequence permits calculating S = sum of configured delays; M=1 has an empty sequence. | S is nominal scheduled waiting, not a measured or hard upper bound on elapsed waiting. No aggregate duration ceiling is validated by policy construction. |
| Dispatch expiry | Request lines 380–421: optional monotonic `expires_at`, checked before dispatch and around waits; requested wait is clipped to expiry. | VERIFIED cooperative primitive; CONDITIONAL caller deadline. It does not abort a running writer or a blocking callback/waiter. |
| Writer / SQL duration | [Write side](../../../src/pipeline/transactional/postgres_write_side.py), lines 72–88 and 620–625, and [UOW](../../../src/pipeline/transactional/postgres_unit_of_work.py), lines 37–68, synchronously execute and finalize. No business `statement_timeout` or SQL `lock_timeout` policy is installed by this composition. | MISSING end-to-end execution-duration guarantee. External SQL/network/validation and cleanup constraints would need a caller-specific contract. |
| Connection acquisition | [connect_postgres](../../../src/storage/postgres_connection.py), lines 20–21 and 37–53, forwards a configurable `connect_timeout` with an existing helper default of 10 seconds. It does not validate the override here. | Not a retry-owner lifetime guarantee: acquisition precedes construction and this helper is not wired to a production retry caller. No new default is selected by PR11. |
| Cancellation | Request lines 404–411 consult an optional boolean callback; default waiting is synchronous `sleep` (constructor line 187). | Cooperative only. Default sleep observes cancellation after returning; an interruptible waiter is possible but no production caller supplies one. |
| Shutdown / drain / disposal | The request owns no service intake stop, worker join, signal handling or connection close. | MISSING application lifecycle owner. No configured production drain deadline or cleanup contract is found. |

Thus **finite attempt count ≠ bounded total invocation/resource-retention
lifetime**. An admitted body, validation callback, SQL operation, commit/rollback
or wait provider can outlast dispatch expiry. Acquisition and connection closure
also lie outside `invoke()`. No actual caller currently guarantees a finite
overall interval covering these stages.

Connection acquisition failure, timeout or cancellation before construction lies
outside the attempt budget and is not pre-body capacity-refusal evidence. The
caller owns its terminal disposition; the request supplies no reconnect loop.
Blocking acquisition and terminal connection cleanup likewise need caller-owned
limits if required by the intended resource-retention contract.

The receipt transaction owner's transaction-local
`idle_in_transaction_session_timeout` (lines 35–43 and 575–595) belongs to
DecisionReceipt persistence. It is not a timeout for business writer execution,
an IDLE retry waiter, or the complete logical invocation. PR9's
[plan](../../../experiments/load_capacity_protection/pr9_model.py), lines 63–66,
requires `stop_claims_and_drain_without_deadline`; completing that experiment does
not establish a bounded shutdown interval for a service.

Cancellation/expiry callback failures are terminal, not capacity eligibility.
Checks occur outside the writer-refusal catch. After a normal writer return,
request lines 346–348 return the result without another cancellation/expiry
check. Consequently cooperative cancellation arriving during an accepted writer
call does not replace its normal result with cancellation. This is not a guarantee
against process termination, arbitrary interruption or lost acknowledgement after
commit. No shutdown integration exists to make a broader guarantee; ambiguous
effects must not be silently retried or declared absent.

## 6. Connection Custody and Session State

The acquisition owner opens and ultimately closes the connection. Both builder
and request receive it already owned. The request and private writer retain the
same object across attempts and waits; the request itself performs no connection
close, replacement, commit, rollback or repair. The writer's UOW owns transaction
finalization, not connection disposition. PRE_TRANSACTION history reads are
rolled back in the writer's `finally` (lines 910–920); UOW entry rejects autocommit
(UOW lines 37–41).

Enabled retry checks `connection.info.transaction_status == IDLE` before dispatch
and before each wait (request lines 323–325, 390–397 and 423–425). A violation
raises `RuntimeError` terminally, without repairing or closing the connection.
Disabled mode intentionally does not add these checks. IDLE is a status sample,
not a custody lock, health probe or proof that session advisory locks are absent.

Exclusive custody and absence of caller-held lifecycle/execution/session advisory
locks are documented preconditions (request lines 157–174; builder lines 46–50),
not enforced by a connection ownership registry. Two distinct owners can receive
the same connection. The per-owner lock does not prevent that violation; a check
may reject a visible non-IDLE state, but cannot establish exclusive use or prevent
subsequent concurrent transaction interference. Such use is outside the contract.

The audited pessimistic writer gate uses
[`pg_try_advisory_xact_lock`](../../../src/pipeline/transactional/postgres_admission.py),
lines 155–179, within the admitted business attempt. The default is optimistic
(write side lines 103–107). A verified refused attempt enters neither body nor
transaction and creates no writer advisory lock. A caller may nevertheless bring
pre-existing session locks or session settings. This composition neither detects
all such state nor resets it. Session context must be known and compatible with
exclusive custody; IDLE alone is insufficient evidence.

Retaining physical connection identity is **not a semantic requirement** of the
audited CREATE/PAY retry path. The same immutable
[RequestSignature](../../../src/storage/idempotency_store.py), lines 10–24, is used
on every attempt (request lines 351–378).
[Durable idempotency](../../../src/storage/postgres_idempotency_store.py), lines
24–95, uses request ID and the command/order/amount fingerprint, not connection
identity. Event and idempotency persistence still require one shared transaction
within an admitted attempt (UOW lines 31–35). Session-local writer state from an
admitted attempt is not carried into a capacity retry: that attempt's result or
exception is terminal. Any future connection replacement must preserve equivalent
caller-established execution context; this audit does not authorize replacement.

## 7. Authority Boundaries

The following are VERIFIED mechanism properties, conditional on correct caller
composition rather than evidence of a deployed caller:

- Explicit policy plus exact concrete-gate provenance is required. Request lines
  221–224 reject a substituted gate for enabled retry; `_AttemptAdmission`, lines
  137–154, records the exact refusal only when the protected body was not entered.
  `_execute`, lines 332–345, checks that identity, policy and remaining budget.
  `WriterCapacityRefused` by type alone grants no authority, including when raised
  from inside a body or a lifetime callback.
- Budget is spent immediately before each serial public call. The complete
  signature is stable; attempt number and logical invocation ID remain distinct.
  The one-shot owner cannot be invoked again. Preventing caller reconstruction
  or nesting from resetting the same live request's budget remains a caller duty.
- Every normal result is terminal, including ACCEPTED, REPLAY, STALE_WRITE,
  LOCK_TIMEOUT and semantic/validation results. Native errors and ambiguous
  failures do not authorize retry. Exhaustion raises
  `WriterCapacityRetryExhausted`, retaining attempts spent and the final refusal
  (request lines 80–94 and 342–344); it is not a fabricated semantic result.
- Waiting follows an unwound verified refusal, outside permit/body/UOW ownership.
  The request's short internal lock is not held while waiting or executing.
  External locks remain the caller's responsibility.
- Stage 4E and DecisionReceipt remain separate. The invocation owner spends A2
  authority before dispatch, never refunds it and creates no A3 (lines 370–419).
  The [outer receipt runtime](../../../src/pipeline/transactional/postgres_write_side_decision_receipt_runtime_owner.py),
  lines 559–613, holds its lifecycle lock across invocation. Its current graph
  must not be mistaken for the lock-free retry caller or wrapped in retry by
  inference. No such integration is present or selected.

Observations and optional measurements are separate deliveries, not authority
(request lines 270–289). They provide request/attempt evidence but do not define
an application resource budget or operational exporter. No deployed shutdown
path has been demonstrated to preserve result delivery and disposal on every
terminal path; that qualification remains open as described in Section 5.

## 8. Qualification Matrix

VERIFIED means a specific guarantee exists in current production source.
CONDITIONAL means a caller/deployment contract could establish it but is not
supplied here. MISSING / NOT QUALIFIED means the present implementation has no
identified integration or end-to-end guarantee satisfying that requirement.

| ADR 0032 precondition / supporting guarantee | Status | Exact evidence and remaining obligation |
|---|---|---|
| 1. Protected writer bound | VERIFIED, per shared gate | Capacity lines 127–149, 174–227; no global or cross-process bound. |
| 1. Bounded logical population C and participating-instance scope | MISSING / NOT QUALIFIED | Request lines 157–174 and builder lines 17–72 establish neither aggregate intake limit nor deployment topology. |
| 2. Connection/thread budgets, retained idle lanes, H and headroom | MISSING / NOT QUALIFIED | Borrowed connection at request lines 242–257; synchronous wait at 397. Other consumers in Section 4 are not globally budgeted. C+H is conditional, not enforced. |
| 3. Finite per-owner attempt budget and positive explicit schedule | VERIFIED, when enabled | Policy lines 25–51; request lines 319–345. Production values remain unselected. |
| 3. One-shot owner | VERIFIED | Request lines 300–303 reject repeated invocation of the same owner. |
| 3. No budget reset by reconstructing a caller | CONDITIONAL | Request lines 169–170 require this; no global live-request registry enforces it across owners. |
| 3. Caller-owned end condition for further waiting/dispatch | CONDITIONAL | Optional `cancelled` / `expires_at`, request lines 380–421; no production caller wires them to a latency or shutdown contract. |
| 3. Finite overall resource-retention interval | MISSING / NOT QUALIFIED | Dispatch expiry does not interrupt running work; UOW lines 45–68 has synchronous finalization without this end-to-end bound. Acquisition and close are external. |
| 4. IDLE checks / non-autocommit UOW | VERIFIED at the named boundaries | Request lines 323–325, 393 and 423–425; UOW lines 37–41. Not continuous session/custody enforcement. |
| 4. Exclusive custody; no external lifecycle/execution/session locks | CONDITIONAL | Request lines 157–174 and builder lines 46–50 are caller preconditions; no session-lock audit or exclusive-connection registry. |
| 5. Cooperative cancellation primitive | VERIFIED | Request lines 404–421; no executing-writer abort or service shutdown owner. |
| 5. Shutdown/drain and connection disposition on every terminal path | MISSING / NOT QUALIFIED | Builder retains external close ownership; request lines 291–317 returns/raises without closing. No production lifecycle integration found. |
| 5. Attempt/wait observation primitive | VERIFIED | Request lines 40–77, 270–289, 380–402; concrete capacity observation at capacity lines 156–227. |
| 5. Aggregate retained-resource observability and operational ownership | MISSING / NOT QUALIFIED | PR9 adapter lines 73–105 supplies experiment-only wait/connection/thread samples. No production caller exports or budgets these resources. |

Every ADR precondition must hold for the same named caller and scope. Passing a
primitive-level row cannot substitute for an unestablished deployment-level row.

## 9. Findings

The source audit resolves the central question negatively: no actual production
retry consumer is present to qualify. The builder is an opt-in composition
surface, not application enablement. Existing PostgreSQL runtime wiring remains
outside it, and PR9's bounded worker/connection topology is experiment-owned.

The most consequential gaps are the missing aggregate caller/resource contract
and application lifetime/shutdown owner. These are not evidence that retained
ownership has exhausted resources or that ADR 0032 must be reversed. They are
reasons to withhold deployment qualification. A hard total deadline, if required
by a future caller, cannot be inferred from the existing dispatch-expiry seam.

## 10. Deployment Status

**NOT QUALIFIED.** Disposition D is supported; conditional architecture acceptance
(B) continues unchanged. Disposition A is not established. Disposition C, a new
implementation justified by a concrete caller requirement, is not selected.
There is no production numerical policy or documented caller C/H/thread/lifetime
envelope to approve. This conclusion does not disable an existing consumer: none
was found in the audited source. External deployments were not inspected.

**PR11 is COMPLETE as an investigation**, ready for human review. Deployment
qualification remains a separate obligation, not unfinished evidence collection
or authorization to begin another mechanism.

## 11. Smallest Justified Follow-up

Identify one intended production caller and write its explicit deployment and
lifecycle contract before authorizing enablement. That contract must name:

1. The request entry point, enforcement of C, shared gate scope, instance/process
   count, and all connection/thread consumers with headroom, including idle lanes.
2. The connection acquisition/closure owner, exclusive custody, session setup and
   absence of forbidden locks; preserve the non-autocommit business UOW contract.
3. Explicit retry configuration, nominal waiting budget, latency requirements,
   acquisition/execution/finalization constraints and whether cooperative dispatch
   expiry is sufficient. Keep one logical budget across the complete invocation.
4. Stop-intake, cancellation, drain and terminal cleanup/result-delivery ownership;
   distinguish refused/no-effect work from an ambiguous or accepted business effect.
5. Observability of attempts, waits, retained resources and terminal outcomes, with
   focused integration evidence for that actual caller and its claimed bounds.

Then map the contract back to Section 8. Existing seams may be enough for a caller
whose bounded work and shutdown requirements are established externally. If a
specific requirement cannot be met, authorize only that missing enforcement or
integration responsibility separately. No new implementation is justified solely
by the absence of a caller today.

If connection-free waiting becomes a demonstrated requirement, ADR 0032 retains
Option C (retry above per-attempt acquisition) as the preferred separately designed
candidate. It is not the automatic next step. Connection release does not itself
select pooling, and avoiding thread retention does not itself justify async work.

## 12. Explicit Non-Goals

No production code, tests, experiments, evidence, ADRs or historical notes change.
No PostgreSQL execution, PR9 evidence replay or external deployment inspection is
part of this audit. No Rate Limiter, Token Bucket, pool, queue, async scheduler,
jitter, Stage 4E change or numerical production default is introduced or selected.
Only this audit and current workstream navigation change; `scripts/` is untouched.
