# PR3 — Bounded In-Flight PostgreSQL Writer Admission

[← Back to Load / Capacity Protection](README.md)

```text
PR0 — COMPLETE
PR1 — COMPLETE / EVIDENCE COLLECTION CLOSED
PR2 — COMPLETE
PR3 — COMPLETE
PR4 — NOT STARTED

Mechanism — opt-in, shared, process-local, fail-fast writer admission
Configured bound — explicitly supplied; no default numerical limit
N=8 — PR2's first protected experimental configuration only
```

## 1. Purpose and Inherited Boundary

PR3 implements the smallest mechanism supported by the
[PR2 interpretation](pr2_capacity_interpretation.md) and its entry criteria.
The [PR0 boundary](pr0_research_and_responsibility_boundary.md),
[PR1 method](pr1_unprotected_characterization_method.md), and
[PR1 report](pr1_unprotected_characterization_report.md) remain historical
sources; their evidence and statuses at closeout are unchanged.

PR1 varied simultaneous public writer calls. PR2 selected N=8 for a first
protected experiment below the descriptive N=10–12 degradation transition,
retaining 95.83% of N=10's refinement median throughput with lower writer and
DB-backed elapsed cost. PR3 separates the mechanism from that experimental
number. It makes no production throughput, safe-capacity, or latency promise.

```text
capacity admission
!= Semantic Admission / semantic validation
!= OCC / pessimistic locking
!= transaction atomicity
!= Stage 4C Current-Response Authority
!= Stage 4E Re-invocation Authority
!= semantic replanning authority
```

## 2. Source-Grounded Placement Audit

The inspected production construction root is
[`build_postgres_write_side_decision_receipt_runtime`](../../../src/bootstrap/build_postgres_write_side_decision_receipt_runtime.py).
It retains a supplied business connection in one writer, then composes the
runtime/invocation owners and a separate receipt transaction owner. It does not
open a business connection or own a service-wide writer population.

The actual paths are:

```text
PR1 scheduler: run_characterization
→ PostgresLoadLane.__call__
→ PostgresTransactionalWriteSide.create_order_with_measurement
→ _execute_command_with_measurement
→ _execute_command
→ PRE_TRANSACTION or IN_TRANSACTION algorithm

production runtime: invoke_initial / invoke_authorized_reinvocation
→ PostgresWriteSideInvocationOwner
→ _dispatch_retained_request
→ same retained writer.create_order / writer.pay_order
→ _execute_command
→ PRE_TRANSACTION or IN_TRANSACTION algorithm
```

Sources:

- [PR1 scheduler](../../../experiments/load_capacity_protection/postgres_characterization.py)
  brackets its supplied lane callable immediately with outer entry/exit readings.
- [PostgresLoadLane](../../../experiments/load_capacity_protection/postgres_runtime.py)
  forwards the prepared CREATE signature to its retained measured writer.
- [Writer](../../../src/pipeline/transactional/postgres_write_side.py) exposes
  eight public methods: CREATE/PAY, each plain, traced, measured, or traced and
  measured. Their bodies do not call another public writer variant.
- [Invocation owner](../../../src/pipeline/transactional/postgres_write_side_invocation_owner.py)
  dispatches A1 and A2 through the same retained public CREATE/PAY methods.
- [DecisionReceipt runtime owner](../../../src/pipeline/transactional/postgres_write_side_decision_receipt_runtime_owner.py)
  publishes completion only after normal writer return.

| Boundary | Actual source behavior and placement implication |
|---|---|
| Connection acquisition | The caller supplies an already-open retained connection. The [connection helper](../../../src/storage/postgres_connection.py) opens connections separately. Capacity does not bound connection creation or open connection count. |
| PRE preliminary reads | The writer calls [idempotency storage](../../../src/storage/postgres_idempotency_store.py) and accepted-history storage before validation and business-UOW entry. With autocommit disabled, SQL starts an implicit transaction. A gate only at UOW entry would be too late. |
| PRE read cleanup / validation | A finally block rolls back the preliminary read transaction, including replay/conflict exits, before candidate creation and validation. Validation rejection returns without business-UOW entry. |
| Business UOW | [PostgresWriteSideUnitOfWork](../../../src/pipeline/transactional/postgres_unit_of_work.py) constructs stores and checks autocommit in `__enter__`; entry itself does not issue SQL BEGIN. First database work starts the physical transaction. PRE then rechecks idempotency, prepares concurrency, appends, and records idempotency. |
| IN_TRANSACTION | UOW entry precedes the authoritative idempotency check, concurrency preparation, history load, candidate creation, validation, append, and idempotency persistence. |
| PostgreSQL locks | [Pessimistic preparation](../../../src/pipeline/transactional/postgres_admission.py) acquires a transaction-scoped advisory lock inside the UOW. OCC preparation is a no-op. Both occur after capacity admission. |
| Normal exits | ACCEPTED, REPLAY, CONFLICT, VALIDATION_BLOCKED, and ADMISSION_REJECTED remain existing results. UOW early non-accepted exits explicitly roll back; clean unfinished UOW exit commits. PRE-only exits perform preliminary cleanup. |
| Exceptional exits | SQL, validation, candidate construction, trace, UOW, commit/rollback, and unexpected ordinary exceptions propagate through the protected boundary. UOW behavior is unchanged. Measured delivery construction occurs after producer return and remains inside the capacity permit. |
| Scarce resources before entry | Lanes already retain connections. The real PR1 factory restores lane connections to IDLE before composition. Direct writer/builder callers have no universal idle-state guard and may supply an existing transaction; capacity does not inspect or clean it up. |
| Lifecycle locks | The invocation owner releases its lifecycle lock before dispatch. The outer DecisionReceipt runtime holds its own lifecycle lock across dispatch and completion publication. This rules out adding capacity waiting there without a separate lifecycle redesign. |

The [PR1 runtime factory](../../../experiments/load_capacity_protection/runner.py)
constructs multiple distinct lanes/writers and connections in one prepared
runtime. Its setup/control transaction is rolled back before workload release;
verification and cleanup follow quiescence. There is no application-wide
production service owner or distributed scheduler in the inspected composition.
Historical Stage 4B.2 construction roots remain unprotected and unchanged.

## 3. Selected Capacity Boundary

[`_capacity_protected`](../../../src/pipeline/transactional/postgres_write_side.py)
wraps all eight public method bodies:

```text
caller enters public method wrapper
→ try capacity acquisition once
  → unavailable: raise WriterCapacityRefused; original body never begins
  → acquired: invoke original public method body
      → preliminary reads / validation / UOW / finalization as applicable
      → construct normal trace/measurement delivery as applicable
      → return original value or propagate original exception
→ finally release capacity once
→ public wrapper returns or raises
```

The permit covers the complete original public method body, including final
measurement delivery, before returning control to invocation owners. It does
not extend to Stage 4C evaluation, receipt composition/persistence, or other
business/API work. It is acquired before any measured PostgreSQL-backed work.
There is no nested acquisition between public variants.

PR1's original `[writer_entry_ns, writer_exit_ns)` includes public call-edge
uncertainty and delivery overhead. With protection enabled, the outer attempted
call also includes the admission wrapper. The admitted operation passed to
`BoundedWriterAdmission.run` is the original public body; this is the protected
writer-work interval. PR4 must observe that inner interval separately, retaining
outer offered-call timing instead of silently redefining historical timestamps.

## 4. Shared Ownership and Configuration

[`BoundedWriterAdmission`](../../../src/pipeline/transactional/writer_capacity.py)
is caller-owned. The narrowest existing composition owner spanning concurrent
writers is the caller constructing the writer/runtime population, not an
individual connection, invocation owner, runtime builder call, or lane.

The writer constructor, production runtime builder, and retained-lane adapter
accept the same keyword-only `capacity_admission` object. They retain it without
copying it or constructing an independent budget. A caller composes one object
outside its per-writer construction loop, then injects it into every relevant
writer. The tests exercise this sharing across distinct writers, separately
built production runtimes, and distinct retained lanes.

```python
# Explicit configuration for a later authorized experiment, not a default.
shared_admission = BoundedWriterAdmission(bound=8)
# Supply capacity_admission=shared_admission to every writer/lane in that group.
```

| Configuration | Behavior |
|---|---|
| Explicit shared object | At most its configured bound of original public writer bodies execute simultaneously. |
| Omitted or `None` | Existing unprotected behavior; no gate is constructed and no numerical default is inferred. |
| Positive integer bound | Accepted; exposed through read-only `bound` configuration property. |
| Boolean or other non-integer | TypeError at budget construction. |
| Zero or negative integer | ValueError at budget construction. |
| Invalid injected object | TypeError at writer construction. |

Scope is process-local and limited to callers sharing the exact object. Separate
objects and processes establish separate budgets. No module-global singleton,
distributed/cluster limit, dynamic tuning, fairness guarantee, or connection
sharing is introduced. Callers must continue exclusive connection ownership.
Reversibility means composing with `None` for unprotected execution; there is no
live budget resizing or in-flight reconfiguration contract.

The historical `postgres_runtime` runner still constructs unprotected lanes.
PR3 does not add a protected live-run switch to a runner whose evidence schema
cannot yet express pre-entry refusal accurately. PR4 can use the existing
`PreparedRuntime`/factory seam and configured lanes after adapting its accounting.

## 5. Why Fail-Fast Refusal

| Candidate | Consequence in this source |
|---|---|
| Bounded waiting | Would wait while the outer runtime lifecycle lock is held. Avoiding that requires changing lifecycle scope; waiting also needs a timeout/ownership and evidence contract. Retained connections and caller-supplied transaction state complicate resource ownership further. |
| Fail-fast refusal | One nonblocking capacity attempt before the body, one distinct exception, no capacity queue/wait or lifecycle refactor, and unchanged normal result types. Excess offer is directly testable. |

PR3 selects fail-fast refusal only. The implementation uses a bounded semaphore
with `acquire(blocking=False)` and a finally-owned release. Internal semaphore
bookkeeping still uses synchronization; this is not a lock-free or hard real-time
promise. Callers never wait for another writer to finish to obtain capacity.

`WriterCapacityRefused` is separate from SemanticOutcome and every write-side
result/verdict. It carries no producer evidence, acknowledgement, retryability,
retry/reinvocation/replanning authority, or result mapping. It is not
STALE_WRITE, LOCK_TIMEOUT, VALIDATION_BLOCKED, or semantic invalidity. Refusal
performs no SQL, rollback, validation, trace, or measurement construction.
The caller owns handling it; there is no automatic resubmission or new queue.

## 6. Permit and Stage 4E Lifecycles

Admission has one ownership path: successful acquisition, exactly one
synchronous operation, finally release. Normal non-ACCEPTED results release just
like ACCEPTED. Ordinary and PostgreSQL exceptions preserve object identity and
release; process-level exceptions unwind through finally without reinterpretation.
No public manual release operation can accidentally double-release a permit.
Abrupt process termination and detached/asynchronous work are outside the
synchronous lifetime guarantee.

Stage 4E's owner still marks positive authorization SPENT before A2 dispatch.
The capacity object neither grants nor spends authority. Both A1 and A2 use
the same configured public writer wrapper. A2 cannot bypass it on the inspected
real owner path. No owner or evaluator production code changed.

If A2 is refused, the existing owner has already spent its authorization; it
remains spent, with no refund, no completed A2 handle, no new current-response
result, and no A3. A1 refusal similarly leaves A1 started without a normally
completed result, so it cannot issue authority from that failed attempt. This
is the existing exception lifecycle, now exercised by a capacity-specific
exception; it is not a new eligibility or retry rule.

Tests also exercise successfully admitted CREATE/PAY A2, checking that the
permit is held during execution and released before completion publication.
The guarantee covers the concrete public writer methods. Replacing/overriding
those methods or supplying an admission subclass that bypasses `super().run`
can deliberately bypass the contract, just as replacing production execution
can bypass other invariants; such substitutions are not supported enforcement.

## 7. Observability and PR4 Handoff

The mechanism allocates no production timing framework. Its synchronous
`run(operation)` seam permits an experiment-owned adapter to:

1. record offered/admission-attempt time around `run`;
2. delegate once to `super().run` with a wrapper around `operation`;
3. record admitted entry/exit inside that wrapper;
4. record refusal when acquisition fails without operation entry;
5. record terminal return/raise outside `super().run`, after permit release for
   admitted work, or without acquisition for refused work.

Callbacks/observers must preserve exact values/exceptions and never invoke the
operation outside admission. Observed entry distinguishes pre-entry refusal
from any exception raised after admitted work begins. Adapter overhead belongs
in the experiment's provenance and comparability analysis.

A deterministic test uses this seam with real retained-lane/public-writer
composition and the existing PR1 scheduler. Two callers are offered against
bound one; one protected body stays active until the other is refused. The
adapter observes one entry/exit and one refusal with no entry/exit.

The test also confirms the frozen PR1 ledger still counts two outer call
entries and classifies the refusal as a writer-call failure with unknown
acknowledgement. That is faithful to PR1's unprotected contract but insufficient
for PR4. Do not report those outer intervals as protected overlap, reinterpret
refusal as a DB failure, or run a protected sweep through unchanged PR1 accounting.

PR4 must adapt the existing outer scheduler/evidence projection to retain
pre-entry refusal, absence of writer evidence, and no new acknowledged write;
preserve residual/failed work and durable verification; review continuation
and cleanup conditions for refused cells; and record offered versus admitted
intervals. The existing stop-on-exception rule is not a selected protected
refusal policy. Historical schema/evidence remains frozen; PR4 owns any new
version and comparison schedule.

The PR2 contract remains mandatory: offered concurrency above the configured
bound; observed protected overlap within it; unchanged correctness; complete
waiting/refusal/failure accounting; and evaluation of useful throughput,
DB-backed latency amplification, and displaced pressure. Bounding overlap alone
is not success, refused work cannot disappear, and throughput need not increase.
PR4 requires a reviewed run plan and separately authorized database execution.

## 8. Validation and Limits

New focused tests:

- [Writer capacity tests](../../../tests/unit/pipeline/transactional/test_postgres_writer_capacity.py):
  invalid configuration, all eight entry variants, unchanged normal outcomes,
  ordinary/PostgreSQL/process-level exception identity and release, disabled
  behavior, source-boundary validation/OCC/finalization witnesses, shared runtime
  composition, A1 refusal, and both refused and admitted CREATE/PAY A2.
- [Experiment seam tests](../../../tests/experiments/load_capacity_protection/test_capacity_admission.py):
  shared retained-lane configuration, exact measured delivery, subsequent entry,
  and separate offered/admitted/refused timing through the existing scheduler.

The core overlap test configures bound two, starts two distinct writers, and
holds them inside their public bodies using events/barriers. Three additional
writers synchronize their offers while those two remain active. All three
receive immediate capacity refusal, maximum protected overlap equals two, and
a previously refused writer can enter after release. No sleep establishes
correctness; bounded waits only fail a broken test schedule.

The final focused suite passed **414 tests**, covering both new test files,
existing runtime builder and invocation/runtime owner tests, writer measurement
instrumentation/correctness/contracts, traced execution, and all load-capacity
experiment unit regressions. No full pytest suite, live PostgreSQL test, load
sweep, or performance claim is included. Database operations in these tests are
fakes; they establish application placement and lifecycle, not new physical
PostgreSQL correctness or capacity evidence.

The focused command actually executed was:

```bash
./.venv/bin/python -m pytest -q \
  tests/unit/pipeline/transactional/test_postgres_writer_capacity.py \
  tests/unit/bootstrap/test_build_postgres_write_side_decision_receipt_runtime.py \
  tests/unit/pipeline/transactional/test_postgres_write_side_invocation_owner.py \
  tests/unit/pipeline/transactional/test_postgres_write_side_decision_receipt_runtime_owner.py \
  tests/unit/pipeline/transactional/test_postgres_write_side_measurement_instrumentation.py \
  tests/unit/pipeline/transactional/test_postgres_write_side_measurement_correctness.py \
  tests/unit/pipeline/transactional/test_postgres_write_side_measurement_contract.py \
  tests/unit/pipeline/transactional/test_postgres_write_side_traced_execution_unit.py \
  tests/experiments/load_capacity_protection
```

The repository-local interpreter path was verified before testing.
`git diff --check` passed. Read-only Python validation checked all 65 local
Markdown links/anchors in changed documents, parsed all six changed/added Python
files, checked whitespace including new untracked files, and verified unchanged
PR0–PR2 historical notes and PR1 compact evidence/manifest against HEAD. The CSV
still matches its manifest SHA-256. No lint, build, static type checker, remote
Release verification, or rendered-document check was run. Human review should
focus on the shared ownership contract, fail-fast A2 consequences, and PR4's
required offered/admitted accounting distinction.

The inherited limitations remain: local Darwin/arm64, 12 logical CPUs,
PostgreSQL 16.15; independent CREATE with PRE_TRANSACTION/OCC/STRICT FullProof;
finite closed-loop K=512; retained connections without a pool; no production
arrival/SLO, PAY/hot-key capacity evidence, or pessimistic capacity fixture;
grouped repetitions/time drift, incomplete physical reset, and no server
CPU/I/O/WAL root-cause proof. Applying protection to PAY and traced variants
preserves execution responsibility; it does not establish their operating bound.

## 9. PR3 Conclusion

Placement, sharing, exception safety, configuration, and A2 composition have
no unresolved implementation blocker in this scope. PR3 is COMPLETE and ready
for human review. PR4 is NOT STARTED; it owns protected evidence adaptation and
protected/unprotected performance validation. Eight remains an explicit first
experimental configuration, never a universal safe or production capacity.

No semantic mappings, validation rules, OCC/pessimistic meaning, transaction
atomicity, idempotency, receipts, Stage 4C/4E eligibility, retry scheduling, or
semantic replanning changed. No PR1 raw/compact evidence, manifest, Release,
local scripts, dependency, or database state was modified by PR3.
