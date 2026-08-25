# Stage 4E Append STALE_WRITE Re-invocation Resolution Experiment

## Question

Can a fresh full same-request invocation, started only after a real PostgreSQL
append-time `STALE_WRITE` and confirmed rollback, observe authoritative state
that the stale invocation could no longer safely use?

This remains an experimental PostgreSQL characterization. Stage 4E PR4 now
uses its schedules to assert the production typed evidence for the targeted
physical source, but neither the experiment nor PR4 changes the existing
production authorization profile.

## PR5 Promotion Addendum

The original question, schedules, result, conclusion, and experiment-only
non-claims below remain the historical PR4 characterization. Stage 4E PR5
separately promotes the existing evidence into one additional source-specific
production issuance profile; it does not reinterpret generic `STALE_WRITE`.

For both unchanged schedules, the integration test now passes the real A1
`PostgresWriteSideResult` and the same complete `RequestSignature` to the
production Stage 4E evaluator. The coherent forward-version shapes—`0 → 1` in
schedule A and `1 → 2` in schedule B—produce
`ReinvocationAuthorization`, retaining the exact supplied signature. Existing
fresh-invocation behavior then remains unchanged:

```text
schedule A: authority → fresh invocation → REPLAY
schedule B: authority → fresh invocation → current domain rejection
```

The promoted theorem is narrow: a completed trusted write-side result showing
a coherent append version advance, with no accepted A1 effect, may issue
authority for exactly one fresh invocation of the invocation owner's retained
complete `RequestSignature`. The result does not independently prove all four
request fields belong to A1; same-request identity comes from the unchanged
invocation owner's custody. PR5 relies on that custody together with the exact
trusted result, source-specific typed evidence, structural coherence, and known
write-side control flow.

Authority permits one re-entry through the full normal write-side boundary so
current authoritative state can be observed. It predicts neither replay nor
success, and it does not authorize candidate reuse, validation reuse, append
retry, domain acceptance, or accepted-history mutation. Stage 4C remains
unchanged and independently owns the current A1 response.

## Physical Model

Both schedules use `PostgresTransactionalWriteSide` configured with
`ValidationPlacement.PRE_TRANSACTION`, the real strict `ValidationRuntime`,
the real `PostgresOptimisticAdmissionGate`, `PostgresEventStore`, and
`PostgresIdempotencyStore`.

A test-only wrapper around each invocation's real optimistic gate records the
candidate and expected version. For A1 only, it publishes a `threading.Event`
immediately before the first real append and waits for an explicit release
event. It does not replace append behavior or manufacture a stale result.

The exact stale source targeted in both schedules is the production event
store's current-version check. B commits a new accepted stream position before
A1 delegates to `PostgresEventStore.append(...)`; A1 then observes
`store_version != expected_current_version`. The resulting
`AppendVersionMismatchError` transports both versions to the real PostgreSQL
admission gate, which returns `AdmissionVerdict.STALE_WRITE` with subordinate
`AppendVersionMismatchEvidence`.

This concrete physical source is now distinguished by subordinate evidence
while retaining the broader `STALE_WRITE` verdict. Other sources include
candidate continuity mismatch, explicit `StaleWriteError`,
`AppendConflictError`, and a recognized stream-position uniqueness conflict.

## Deterministic Schedule A — Same-request Winner

1. A1 starts CREATE with one complete `RequestSignature` on its own connection.
2. A1 observes idempotency MISS, loads empty history, constructs and validates
   its candidate as ALLOW, enters its business transaction, observes the
   authoritative MISS, is admitted to the stream, and pauses immediately before
   the real optimistic append with expected version 0.
3. B uses a separate PostgreSQL connection and executes the exact same complete
   `RequestSignature` through a normal full writer invocation. B commits one
   event and its idempotency record.
4. A1 is released. Its real append observes store version 1 rather than 0, the
   production gate returns `STALE_WRITE`, and the write side explicitly rolls
   back before A1 returns.
5. Only after A1 completion and idle transaction state are confirmed, fresh A2
   invokes the same public operation with the same complete `RequestSignature`
   through a newly constructed writer using the same PRE_TRANSACTION +
   optimistic configuration. The expected resolution is the repository's real
   preliminary idempotency `REPLAY`, without candidate construction,
   validation, or append.

## Deterministic Schedule B — Competing State Invalidates Old Work

1. A real CREATE is seeded and committed.
2. A1 starts PAY with its original request signature, loads CREATED history,
   constructs a PAY candidate, validates ALLOW, and pauses immediately before
   real append with expected version 1.
3. B uses a separate connection and different request identity to execute and
   commit a competing legal PAY.
4. A1 is released. Its real append observes store version 2 rather than 1,
   returns `STALE_WRITE`, and rolls back without an accepted A1 effect.
5. Only after rollback confirmation, fresh A2 invokes PAY with A1's original
   signature. The current aggregate implementation reloads PAID history and
   raises `ValueError("Order is already paid")` during fresh domain candidate
   construction. It does not reuse A1's candidate or validation artifact.

The events are causal barriers, not timing assumptions. Event waits are only
failure deadlines. There are no sleeps. A1 and B have distinct backend
connections, and A2 starts only after A1 has returned and its connection is
idle.

## Evidence and Falsification Boundary

The experiment succeeds only if the production types and stores show all of
the following:

- A1 reaches real candidate construction, real strict validation ALLOW, stream
  admission, and the real append boundary;
- A1 returns a real `PostgresWriteSideResult` with append `STALE_WRITE` and
  exact typed expected/observed version-mismatch evidence;
- A1's transaction is idle after explicit rollback and its candidate event is
  absent from accepted history;
- schedule A's B commits the exact request and A2 resolves through real REPLAY,
  leaving exactly one event and one idempotency row;
- schedule B's competing PAY is the only accepted PAY, A1 has no idempotency
  row, and A2 follows the current fresh-domain exception path before validation
  or append;
- per-invocation validation and gate observations show that no A1 candidate or
  validation object is carried into A2.

The hypothesis is falsified if real append does not produce the targeted typed
stale evidence, rollback leaves an A1 effect, A2 cannot observe the committed
authority, or the schedule requires synthetic stale injection. Source identity
is established from `AppendVersionMismatchEvidence`, not reason or exception
text.

## Result

Both deterministic PostgreSQL schedules passed.

### Schedule A — Same-request Winner

- A1 reached real candidate construction and strict validation `ALLOW`;
- B committed the exact same complete `RequestSignature`;
- A1's real PostgreSQL append produced the targeted version-mismatch
  `STALE_WRITE`;
- A1 rolled back with no accepted A1 effect;
- fresh A2 resolved through the real `REPLAY` path;
- exactly one accepted event and one idempotency record remained.

### Schedule B — Competing State Invalidates Old Work

- the seeded CREATE was authoritative;
- A1 PAY constructed and validated its candidate from CREATED history;
- B committed a competing legal PAY;
- A1's real append produced the targeted version-mismatch `STALE_WRITE`;
- A1 rolled back with no accepted A1 PAY;
- fresh A2 reloaded current PAID history;
- A2 followed the real domain rejection path:
  `ValueError("Order is already paid")`;
- A2 did not reuse A1 candidate or validation evidence;
- only legitimate accepted effects remained durable.

The established conclusion is narrow: fresh full re-invocation has
semantic/information value after the characterized append-time version-mismatch
`STALE_WRITE` schedules.

The generic `STALE_WRITE` verdict remains too broad for direct production
authorization because multiple physical stale sources still share that
technical outcome. PR4 preserves typed evidence only for the characterized
append version mismatch. Human reason text is neither source evidence nor
policy input.

## What Success Would Prove

Success would show that a fresh full invocation has semantic and information
value after these two concrete, committed-authority version-mismatch schedules:
it can resolve as real REPLAY or recompute domain legality from current PAID
history. It would also show that reusing A1's old candidate, validation, or
append attempt is unnecessary and, in schedule B, semantically unsafe.

## Explicit Non-claims

Even success would not prove that:

- generic `AdmissionVerdict.STALE_WRITE` is authorized for production
  re-invocation;
- append retry or resuming the old attempt is safe;
- candidate reuse or validation reuse is safe;
- typed append-version-mismatch evidence authorizes another invocation;
- retry count, timing, budget, backoff, or an A3 lifecycle is determined.

This experiment does not characterize PR2 retained-writer identity or exact
live writer-object custody.

The experiment adds no `ReinvocationAuthorization`, evaluator profile,
experiment-owned authorization type, retry manager, retry loop, or production
hook.

## Quotient-model Observation

The targeted append stale schedules differ from preparation `LOCK_TIMEOUT`.
Here, B has already committed accepted authority that invalidates A1's append;
at a preparation timeout boundary, the competing holder remains unresolved.
Both may give a later fresh invocation information value, but this observation
alone does not place them in the same semantic quotient class.
