# Stage 4E Successive Re-invocation Resolution Experiment

## Question

Can a fresh same-request PostgreSQL writer invocation, performed only after a
competing transaction terminates, observe authoritative information that A1
and A2 could not observe while that transaction was unresolved?

This experiment characterizes physical PostgreSQL behavior. It is not Stage 4E
PR3 and is not a production architecture proposal.

## Physical Model

The actor uses the normal `PostgresTransactionalWriteSide` entry and the real
`PostgresPessimisticAdmissionGate`. B owns the matching transaction-scoped
advisory lock on a separate PostgreSQL connection. A1 and A2 execute while B is
known to be unresolved. Each result is evaluated separately by the production
Stage 4E PR1 evaluator. Only the authorization derived from fresh A2 evidence
is used to schedule the experiment-only A3 call.

Two schedules are characterized:

1. B holds the lock without writing, A1 and A2 return preparation
   `LOCK_TIMEOUT`, B rolls back, and A3 executes after rollback confirmation.
2. B is a real writer for the same `RequestSignature`, pauses after acquiring
   the lock, A1 and A2 return preparation `LOCK_TIMEOUT`, B resumes and commits,
   and A3 executes after B completion is confirmed.

## Deterministic Synchronization

The rollback schedule is sequential: successful holder admission proves lock
ownership, synchronous A1 and A2 complete before the explicit rollback, and
the holder connection reports an idle transaction before A3 begins.

The same-request commit schedule uses `threading.Event` barriers and separate
connections. A test-only gate delegates to the real pessimistic gate, publishes
an acquired event only after `ADMITTED`, and waits for an explicit release
event. The test confirms B is not finished during both A invocations, releases
B only after the independent A2 evaluation, joins B, checks its real accepted
result and completed transaction, and only then invokes A3. Event wait limits
are failure deadlines, not timing inputs to the schedule. There are no sleeps.

## Evidence Boundary

The characterization succeeds only if the normal writer produces the expected
post-resolution outcomes and real database effects:

- rollback: A3 is `ACCEPTED`, with one event and one idempotency record;
- same-request commit: B is `ACCEPTED`, A3 is the real `REPLAY`, and the
  database still contains one event and one idempotency record.

A1 authority does not contain a retry budget and does not pre-authorize A3.
The PR2 invocation owner spends A1-derived authority on A2. The fresh A2 result
is then evaluated independently. A second `LOCK_TIMEOUT` is a new temporal
observation that lock unavailability persisted; it is not a resolved business
outcome and does not reveal whether B will commit or roll back.

## Non-claims

This experiment does not determine a retry count, retry timing, polling cost,
backoff policy, reconciliation design, or production A3 lifecycle. It does not
show that retrying forever is correct or that re-invocation is preferable to an
authoritative reconciliation read. No experiment-only concept is promoted to
production.

## Result

The hypothesis is supported by both deterministic PostgreSQL
characterizations.

While B remained unresolved, both A1 and A2 independently observed
preparation LOCK_TIMEOUT.

After crossing B's transaction-resolution boundary:

- B rollback allowed A3 to proceed to ACCEPTED;
- B commit of the same request allowed A3 to resolve through the real
  idempotency path as REPLAY.

Therefore successive fresh re-invocation demonstrated information value:
a later invocation observed authoritative state that earlier invocations
could not observe while the competing transaction remained unresolved.

This does not establish retry timing, retry count, polling efficiency,
backoff policy, reconciliation strategy, or a production A3 lifecycle.