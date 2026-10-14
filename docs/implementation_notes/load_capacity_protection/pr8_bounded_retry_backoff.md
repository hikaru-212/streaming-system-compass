# PR8 — Production Bounded Retry with Delayed Backoff

[← Back to Load / Capacity Protection](README.md)

```text
PR8 — COMPLETE / mechanism checked; ready for human review
Production numerical policy — NOT SELECTED
Production performance / deployment qualification — NOT ESTABLISHED
```

## 1. Responsibility and Placement Audit

This implements the opt-in policy class selected by
[PR7](pr7_retry_attempt_policy_selection.md), under
[ADR 0031](../../adr/0031_separate_resource_occupancy_retry_and_arrival_protection.md).
The [PR5 report](pr5_retry_refusal_amplification_report.md) remains historical
characterization evidence; its constants are not production defaults.

| Audited candidate | Actual CREATE/PAY path and ownership | PR8 disposition |
|---|---|---|
| [BoundedWriterAdmission](../../../src/pipeline/transactional/writer_capacity.py) | Public writer decorators call `run`, which acquires once, calls once and releases in `finally`; saturation raises before calling the body. | Unchanged. Occupancy only; no cross-attempt policy. |
| [PostgresTransactionalWriteSide](../../../src/pipeline/transactional/postgres_write_side.py) | All public CREATE/PAY variants wrap the complete body before preliminary reads, validation, UOW and delivery. | Unchanged. Retains one execution attempt and result semantics. |
| [PostgresWriteSideInvocationOwner](../../../src/pipeline/transactional/postgres_write_side_invocation_owner.py) | `_dispatch_retained_request` selects `create_order` or `pay_order` for A1/A2. A1 is marked started and A2 authority is spent before dispatch. Its own lock is released during execution. | Ineligible for this loop: refusal consumes availability, and another method call cannot restore it. |
| [DecisionReceipt runtime owner](../../../src/pipeline/transactional/postgres_write_side_decision_receipt_runtime_owner.py) | Calls that invocation owner while holding its outer lifecycle lock through completion publication. | Ineligible for delayed retry: a nested wait would retain that lock. |
| [Existing PostgreSQL runtime builder](../../../src/bootstrap/build_postgres_write_side_decision_receipt_runtime.py) | Constructs the DecisionReceipt/A1/A2 graph with a supplied connection and optional shared gate. | Unchanged; it supplies no independent direct-request retry lifecycle. |
| [In-memory builder](../../../src/bootstrap/build_transactional_runtime.py) | Constructs `OrderRegistry` with in-memory storage. | Not a PostgreSQL capacity-refusal consumer. |

The tracked production-source call audit found no existing safe direct-writer
orchestration consumer. Direct PostgreSQL experiment callers are not production
owners. PR8 therefore adds the separate direct-writer composition expressly
scoped by PR7 Section 11, without redesigning any existing lifecycle:

```text
build_postgres_writer_request(...)
→ PostgresWriterRequest.invoke()
→ retained concrete writer.create_order(...) / pay_order(...)
→ private per-request admission view
→ caller-shared BoundedWriterAdmission.run(body)
→ exact writer result or original exception
```

The exact production retry owner is
[PostgresWriterRequest](../../../src/pipeline/postgres_writer_request.py), at the
outer pipeline layer, composed by
[build_postgres_writer_request](../../../src/bootstrap/build_postgres_writer_request.py).
CREATE/PAY selection comes from its retained `RequestSignature.command_type`.
Neither A1 nor A2 flows through this new owner. Existing callers are not migrated
or automatically enabled. The consumer is this explicit direct-writer API, not
a claimed existing traffic-facing service.

## 2. Configuration and Budget

[WriterRetryPolicy](../../../src/pipeline/writer_retry_policy.py) is immutable:

```text
retry_policy=None → disabled / exactly one existing public-writer attempt
WriterRetryPolicy(max_attempts=M, retry_delays_seconds=(...)) → explicit policy
```

`max_attempts` is a positive integer **including the initial attempt**. There
is no additional `max_retries` setting. A tuple of exactly M−1 positive finite
float durations in seconds supplies every additional attempt's delay. No
enabled numerical values have defaults. M=1 with an empty tuple explicitly
permits no additional attempt; unlike disabled mode, it reports configured
budget exhaustion on a verified capacity refusal.

Configuration rejects booleans/non-integer budgets, nonpositive budgets, mutable
or incorrectly sized schedules, non-float delays, zero, negative and nonfinite
delays. Composition validates request structure, policy type, gate provenance
and timing/lifetime controls before constructing the writer or performing I/O.
Business payload validation remains the writer's responsibility.

Each request owns its counter. The initial dispatch and every retry spend one
unit immediately before the synchronous public call, including refused attempts.
Eligibility and waiting spend nothing. A one-shot guard is marked before the
logical request starts and is never reset, including after failure, cancellation
or exhaustion. Concurrent/repeated `invoke()` calls are rejected. Shared policy
and capacity objects do not share request budgets.

This is a live in-process lifecycle, not durable deduplication of controller
construction. Callers must not rebuild/nest owners to refresh the same live
request's budget or route existing Stage 4E invocations around their owner.

## 3. Refusal Provenance and Eligibility

```text
capacity-refusal evidence
!= explicit policy configuration
!= retry eligibility
!= budget spend
!= execution attempt
```

Enabled composition requires the concrete `BoundedWriterAdmission` class;
custom subclasses have unreviewed provenance and are rejected. A private
`_AttemptAdmission` view satisfies the writer's existing admission interface,
delegates once to that exact shared object, and wraps its supplied body with an
entry marker. It allocates no second semaphore and makes no retry decision.

Only an exception retained by that adapter from a call that never entered its
body, identical to the exception reaching this request owner, is verified
pre-body refusal. Explicit configuration then permits consideration of another
attempt. Remaining budget and caller lifetime independently determine dispatch.
The exception itself contains no semantic or retry authority.

The same exception type raised inside the admitted body is not eligible.
Subclass-based/instrumentation adapters cannot masquerade as the reviewed gate.
Native exceptions, ambiguous commit/effect, validation exceptions, arbitrary
exceptions and timing failures terminate. Every normal writer result terminates
unchanged, including ACCEPTED, REPLAY, CONFLICT, VALIDATION_BLOCKED and
ADMISSION_REJECTED with STALE_WRITE or LOCK_TIMEOUT evidence.

There is no result-to-retry mapping and no exception-message classifier. The
private marker is source-grounded in-process evidence, not a security boundary
against monkeypatching or malicious mutation of retained Python objects.

## 4. Backoff, Waiting and Retained Resources

`delay_before_retry(retry_index)` uses a one-based additional-attempt index:
index one precedes total attempt two. The finite tuple permits equal, increasing
or other explicitly reviewed durations without choosing a fixed/exponential
algorithm. `max_delay_seconds` derives its maximum from the supplied tuple;
there is no hidden base, cap, randomization or generated schedule.

After the refused public call unwinds, the owner computes a monotonic
`not_before` time. An injected `wait(seconds)` seam defaults to platform sleep;
the clock defaults to platform monotonic time. Early wakes are rechecked and
cannot dispatch early. Backward/nonfinite clocks or a waiter making no clock
progress fail terminally. Unrepresentable delay arithmetic also fails before
any additional dispatch. Tests inject clocks/waiters and never sleep for backoff.

Resource proof has two separate parts:

- The unchanged capacity gate raises before operation entry when saturated.
  The adapter observes that exact boundary. No permit was acquired by the
  refused attempt; no preliminary SQL, transaction, validation or concurrency
  gate was reached. Admitted-body exceptions release through `finally` and
  are terminal, so they cannot lead to backoff.
- Enabled composition checks `connection.info.transaction_status == IDLE`
  before the first/each dispatch and before every wait. This rejects a
  caller's pre-existing transaction, including failed/unknown state. It never
  commits, rolls back or otherwise repairs that state. Source-owned
  [pessimistic advisory locks](../../../src/pipeline/transactional/postgres_admission.py)
  are transaction-scoped and cannot have been acquired by a refused body.

The request lock protects only initial entry and observation snapshots. It is
released during writer execution, clock/cancellation callbacks and waiting.
Deterministic tests acquire that lock during backoff and prove another caller
can use the shared capacity gate before the next retry.

The composing caller must grant exclusive connection custody for the complete
request and enter without external lifecycle/execution locks or session advisory
locks. IDLE proves transaction state, not absence of arbitrary caller-held or
session-level locks. Injected callbacks/waiters must respect that custody.
This precondition is explicit; no pool lease, connection-close or external-lock
introspection is invented. The synchronous thread and open connection remain
retained while waiting. Waiting caller count and connection count are unbounded
by this mechanism.

## 5. Cancellation, Expiry and Terminals

Optional `cancelled()` is checked before dispatch and around waits. Cancellation
raises `WriterRetryCancelled`; no unexecuted next attempt is charged. Platform
sleep itself is not interruptible by that predicate: cancellation during sleep
is observed on return. Callers needing quicker cancellation can supply an
interruptible waiter. Predicate/waiter failures are terminal, never retryable.

Optional `expires_at` is a finite monotonic deadline in the supplied clock's
domain. Waiting is clipped to it; expiry raises `WriterRetryExpired` and prevents
further dispatch. These controls require an explicit retry policy. Neither
interrupts or reinterprets a running writer; a completed result remains terminal.
Finite attempts are not a hard elapsed-time writer deadline.

After M eligible refusals, `WriterCapacityRetryExhausted` retains total
`attempts_spent` and `final_refusal`, chaining the identical final exception as
its cause. It is deliberately not another `WriterCapacityRefused` eligible for
an outer loop. No accepted result, SemanticOutcome, concurrency verdict or
Stage 4E no-authority result is fabricated. Disabled mode surfaces the original
capacity exception and performs no retry-specific clock/wait/connection check.

## 6. Logical Identity and Observability

The owner retains the exact frozen `RequestSignature`; every serial attempt
uses the same Request ID, command, Order ID and amount. Retry does not create
business intent. A generated technical `logical_invocation_id` correlates the
bounded immutable observation snapshots; it is distinct from the Request ID.

`WriterRetryObservation` reports logical start, attempt dispatch, capacity
refusal, eligibility decision, scheduled delay/not-before time, actual ready
time, terminal writer outcome, terminal failure, exhaustion, cancellation and
expiry. Attempt numbers are one-based on dispatch and also represent total
budget spent; logical start has zero. Schedule/ready events retain the refused
attempt number, followed by the next increment at dispatch.

`pre_body_refusal=True` is verified adapter evidence, False means the enabled
adapter did not establish it, and None means the disabled path did not observe
body provenance. Eligibility is a separate field/event. Only normal terminals
carry the writer's outcome enum; the exact result remains the return value.
Observations retain no amount, Order ID, raw provider errors, credentials or
SQL details. They are bounded by the explicit attempt ceiling and expose no
callback able to replace a result or manufacture retry eligibility. No durable
ledger, metrics exporter or PR5 experiment evidence framework is reproduced.

## 7. Stage 4E Separation

Production capacity retry is not Stage 4E reinvocation authority. This first
slice supports direct calls only; it does not retry a refused A1 or A2 through
their current owners. Existing A1 refusal still uses the initial invocation;
A2 refusal still leaves authority spent and publishes no normal completion.

The existing builder, invocation owner, DecisionReceipt runtime owner and
authority evaluators are unchanged. The direct request owner is not a
`PostgresTransactionalWriteSide`, so the existing Stage 4E writer type check
rejects it. There is no authority evaluation API, refund, A1 reset or A3.

## 8. Validation and Review Boundary

The repository-local interpreter resolved under this repository's `.venv`.
Focused validation executed:

```bash
PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/unit/pipeline/test_writer_retry_policy.py \
  tests/unit/pipeline/test_postgres_writer_request.py \
  tests/unit/pipeline/transactional/test_postgres_writer_capacity.py \
  tests/unit/pipeline/transactional/test_postgres_write_side_invocation_owner.py \
  tests/unit/pipeline/transactional/test_postgres_write_side_decision_receipt_runtime_owner.py \
  tests/unit/bootstrap/test_build_postgres_write_side_decision_receipt_runtime.py \
  tests/unit/compass/runtime/test_reinvocation_authority.py \
  tests/unit/compass/runtime/test_postgres_write_side_reinvocation_authority.py
```

Result: **298 passed**. New tests cover configuration, the actual new composition
through the real public writer/capacity boundary, complete CREATE/PAY algorithms
with fake I/O in both validation placements, resource-free waiting, stable
identity, increasing serial attempt numbers, independent budgets, finite
exhaustion, disabled behavior, native/body exceptions, normal terminal paths,
clock/wait failure, cancellation/expiry and Stage 4E type separation. Existing
capacity and Stage 4E regression files are unchanged.

No live PostgreSQL or load experiment ran. The placement boundary is before SQL
and is witnessed with real production control flow and fake I/O; this does not
claim physical PostgreSQL performance or a live database integration result.
No full suite, lint, build, static type checker or manual deployment verification
was run. `git diff --check` passed. A repository-local Python check passed all
56 local Markdown links/anchors in the three changed notes, parsed all five new
Python files, checked whitespace/final newlines in all eight authorized files,
and matched final status to that exact change set plus protected `scripts/`.
Nothing was staged. The tracked documentation diff and added source/tests were
reviewed; no generated files, dependencies or environment configuration changed.

Human review should confirm the new direct-only composition placement, caller
connection/lock preconditions, refusal provenance and budget convention. A later
separately authorized characterization must evaluate deployment-specific attempt
amplification, logical completion, latency/drain time, retained connections and
waiting callers before enabling reviewed numerical settings. No production
performance improvement or optimal budget/delay is established by these tests.

## 9. Non-Goals and Deferred Decisions

No production attempt count, delay, exponential base/cap or jitter magnitude is
selected. PR5's eight attempts, five-millisecond fixed delay, one-millisecond
base, eight-millisecond cap and four-millisecond jitter remain experiment values.

No Rate Limiter, Token Bucket, requests-per-second/burst allowance, queue,
ingress throttling, jitter algorithm, generic retry framework, async scheduler,
connection pool, semantic replanning, native/ambiguous-failure recovery or
Stage 4E integration is introduced. Their permanent necessity or lack of
necessity is not established. PR1–PR5 source/evidence, historical PR7/ADR records,
Releases, dependencies, environment files and protected local `scripts/` remain
untouched. No staging, commit, push or remote operation belongs to this change.
