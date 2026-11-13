# ADR 0032 — Keep Capacity Retry Synchronous Under Explicit Caller Resource Budgets

[← Back to ADR Index](README.md)

## Status

Accepted

## Implementation Status

The synchronous capacity-retry mechanism is already implemented in
[PR8](../implementation_notes/load_capacity_protection/pr8_bounded_retry_backoff.md)
and characterized in
[PR9](../implementation_notes/load_capacity_protection/pr9_production_retry_validation_report.md).
Both PRs are complete and merged into `feat/load-capacity-protection`.
This ADR accepts conditional retention of that ownership model; it requires no
production behavior change and does not establish deployment qualification.
Caller resource/lifetime preconditions are not automatically enforced by the
writer permit bound.

---

## Context

[ADR 0031](0031_separate_resource_occupancy_retry_and_arrival_protection.md)
separates writer occupancy, retry pressure and arrival-rate protection.
`PostgresWriterRequest` receives an already-owned PostgreSQL connection and
executes serial attempts synchronously. The caller owns connection acquisition
and closure; the invoking thread and connection remain retained during backoff.

PR9 observed useful eventual completion under overload while protected writer
overlap remained bounded at eight. Waiting retained existing threads and idle
connections: waiting connection peaks were eight at N=16 and 24 at N=32, with
IDLE → IDLE at every observed wait boundary. Retry did not increase configured
connection count. Completion gains also included pacing of later fresh work on
retained lanes, not solely recovery of refused requests.

These observations establish a resource trade-off, but not connection/thread
exhaustion requiring redesign or an acceptable deployment resource envelope.
The [PR10 investigation](../implementation_notes/load_capacity_protection/pr10_retry_waiting_ownership_decision.md)
contains the source audit, option comparison, failure modes and resource model.
Its pre-acceptance review labels remain historical; this ADR records the
subsequently human-approved decision.

## Decision

**Keep the current synchronous capacity-retry ownership model only when the
caller establishes explicit bounded logical concurrency, connection/thread
budgets, finite retry lifetime, exclusive connection custody, and adequate
shutdown/cancellation ownership.** This accepts PR10 Option A conditionally.
No-retry remains a valid explicit disabled policy.

The composing caller must establish:

1. A bounded logical-request population and the scope of the shared writer gate,
   accounting for all participating instances/processes.
2. Connection and thread budgets covering active work, waiting callers, retained
   idle lanes and other consumers, with explicit headroom. The writer bound does
   not supply these budgets.
3. A finite retry lifetime: an explicit total-attempt ceiling and delay schedule,
   with a caller-owned end condition for further retry waiting/dispatch that
   meets its latency and shutdown requirements. Reconstructing an owner must not
   reset the same live logical request's budget.
4. Exclusive connection custody throughout invocation, IDLE transaction state
   before attempts and waits, and no external execution/lifecycle or session
   advisory locks held during waiting. IDLE alone does not prove session locks
   are absent. Business execution retains its non-autocommit UOW contract.
5. Ownership of cancellation, shutdown and connection disposition on every
   terminal path, with observability of attempts, waits and retained resources.

A finite attempt ceiling or sum of configured delays is not a hard wall-clock
deadline. Current cancellation is cooperative; default sleep notices cancellation
on return, and dispatch expiry does not interrupt an executing writer. A caller
requiring stronger termination/resource-release guarantees must establish them
separately before treating this model as acceptable. This ADR adds no enforcement
or hard cancellation mechanism.

Acceptance is architectural and conditional, **not deployment qualification**.
An unspecified caller concurrency, resource budget or lifetime requirement does
not satisfy these conditions merely because PR9 completed successfully.

## Ownership and Semantic Boundaries

```text
writer permit bound
!= caller concurrency bound
!= connection/thread resource bound

logical request identity
!= physical PostgreSQL connection identity
```

Retaining the same connection across retries is **not a semantic requirement**
of the audited CREATE/PAY path. RequestSignature and durable idempotency identify
business intent without connection identity. Verified pre-body capacity refusal
precedes SQL, candidate construction and UOW/session-local writer state. Within
an admitted attempt, event append and idempotency persistence must still share
one business transaction. Caller-established session context must not be silently
discarded; any future reacquisition must preserve equivalent execution context.

The current retention is accepted for correctness simplicity, serial ownership,
synchronous API compatibility and avoidance of new reacquisition/cleanup failure
paths. PR9 supplies no evidence of resource exhaustion requiring that redesign.
It does not prove that retained connection identity caused the completion gain
or that another ownership model would preserve the same performance.

With an externally bounded caller population C, one retained connection per
lane and H other connections, retained connection demand can reach C+H even
when protected writer bodies are bounded by B. Waiting threads/connections are
bounded by the caller population, not B. Without that caller bound the retry
mechanism supplies no finite aggregate resource bound.

Capacity refusal remains evidence, not retry authority. Only explicit policy
plus verified pre-body refusal, remaining budget and lifetime eligibility can
permit another serial attempt with the same complete RequestSignature. Normal
results and native/semantic/ambiguous failures remain terminal to this policy.
No permit or active business transaction may span backoff. Stage 4E authority,
A1/A2 consumption, no-refund behavior and the absence of A3 remain unchanged.

## Alternatives and Re-entry Conditions

| PR10 option | Disposition |
|---|---|
| A — retain synchronous thread and connection | Accepted only under the caller preconditions above. |
| B — release/reacquire inside the current request owner | Not selected. The owner borrows its connection and its private writer retains it; closing/replacing it requires a new ownership contract and additional lifecycle branches. |
| C — retry above per-attempt resource acquisition | Preferred separately designed candidate if connection-free waiting becomes a requirement. Separate logical retry lifetime from acquisition/execution/release of each attempt's resources while preserving one logical budget and refusal provenance. No implementation is selected here. |
| D — scheduler / queue / async ownership | Deferred. Avoiding dedicated waiting threads requires separate evidence and a lifecycle design covering pending-work bounds, cancellation, fairness, shutdown and restart. |

C does not imply a pool: a purpose-specific provider/factory could acquire and
close a fresh connection per attempt. Pool reuse, checkout and physical connection
budgets are separate decisions. Acquisition before the existing writer boundary
can still reach caller concurrency; connection-free waiting does not imply peak
connection demand is bounded by writer permits.

Any later C design must specify acquisition blocking/timeouts, cancellation
during acquisition, equivalent session setup and cleanup failure disposition.
Infrastructure/provider failures must not become `WriterCapacityRefused` or
uncharged reconnect loops. Primary results and original exceptions must survive
cleanup failures. New behavior and its characterization require separate scope
and approval; PR9 results cannot be assumed to transfer unchanged.

## Consequences and Non-Decisions

Current direct callers retain a simple synchronous result contract and explicit
ownership costs. Callers unable to meet the conditions must resolve their
resource/lifetime requirements before deployment acceptance; this ADR neither
automatically enables retry nor silently changes an existing policy.

Production capacity bounds, caller budgets, attempt counts, delay values and
schedule shape remain separately owned configuration/deployment decisions.
PR9's eight attempts and fixed 5 ms delay are experimental parameters, not
production defaults or optimal settings.

No Rate Limiter, Token Bucket, connection pool, queue, async scheduler, jitter,
arrival shaping or Stage 4E change is selected. No claim is made that any of
these is permanently unnecessary, or that pooling/async would improve throughput.
Production code, tests, experiments and historical evidence remain unchanged.
