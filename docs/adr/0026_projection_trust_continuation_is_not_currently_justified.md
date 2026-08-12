# ADR 0026: Projection Trust Continuation Is Not Currently Justified

[← Back to ADR Index](README.md)

## Status

Accepted

## Implementation Status

Accepted as the documentation-only Stage 4B.3 closeout decision.

No production source, test, migration, schema, persistence, serializer, trust
checkpoint, runtime policy, strategy, or retry behavior is introduced by this
decision.

---

## Context

Stage 4B.3 began with a bounded architecture question:

> Can a previously replay-qualified mutable projection boundary remain
> qualified across exact-next projection advances without repeatedly replaying
> accepted history?

PR1 documented the distinction between one point-in-time replay `MATCH`, one
caller-visible committed worker `applied` result, and a possible future trust-
continuation conclusion. It intentionally did not authorize implementation.

PR2 then converted the mechanics relevant to that question into executable
characterization, including:

- replay `MATCH` without repaired per-order progress;
- repeatable-read observation stability while projection state changes in a
  different transaction;
- state/progress disagreement failing through reducer sequence checks;
- progress failure rolling state and progress back together;
- commit-time failure preventing caller-visible `applied` and durable writes;
- replacement workers resuming from durable per-order progress.

See the historical/reference
[Stage 4B.3 responsibility boundary](../implementation_notes/stage_4b_3/projection_trust_continuation_boundary.md)
and
[trust-mechanics characterization](../implementation_notes/stage_4b_3/trust_mechanics_characterization.md).

PR1 and PR2 were deliberately performed before deciding whether additional
runtime machinery was necessary. Their evidence made it possible to compare a
candidate continuation layer with the correctness guarantees already present in
the supported projection runtime rather than preserving a planned stage by
roadmap inertia.

The resulting architecture-necessity audit found no current runtime consumer or
missing correctness property that requires incremental projection-trust
qualification.

## Current Projection Authority Model

The current durable boundaries are:

```text
order_events
= accepted business authority

projection_states
= mutable, disposable derived read model

projection_order_progress
= durable per-order processing lineage

projection_checkpoints
= legacy / general operational evidence
!= repaired PostgreSQL worker progress

projection_snapshots
= optional reference / reconstruction infrastructure under ADR 0021
```

Accepted-history membership is what grants an event business-authority status.
The event store provides replayable accepted history through `order_events`; see
[`PostgresEventStore`](../../src/storage/postgres_event_store.py).

Projection state remains subordinate to that history. It may be updated,
cleared, compared, or reconstructed without rewriting accepted business facts;
see [`PostgresProjectionStore`](../../src/storage/postgres_projection_store.py)
and the Stage 3.5E
[database-role privilege baseline](../implementation_notes/stage_3_5e/database_role_privilege_baseline.md).

The authority distinction is therefore:

```text
derived state
!= business authority
```

## Current Projection Runtime

The supported PostgreSQL order-state projection fixes one production identity:

```text
projection_name  = order_state_projection
projection_epoch = 1
```

Callers cannot select another name or epoch. `worker_name` is operational
identity only; it is not part of durable per-order progress identity. See
[`order_projection_definition.py`](../../src/pipeline/projection/order_projection_definition.py)
and its
[definition tests](../../tests/unit/pipeline/projection/test_postgres_projection_definition.py).

The current dataflow is:

```text
currently visible accepted exact-next event
→ load projection state or construct INIT / version-0 state
→ canonical reduce_order_event(...)
→ save projection state
→ advance projection_order_progress
→ successful top-level transaction commit
→ caller-visible action="applied"
```

This path is implemented by
[`PostgresProjectionWorker.process_next()`](../../src/pipeline/projection/postgres_worker.py).
Its event source, state store, and progress store must share the exact worker
connection.

The supported topology remains one active worker for the current projection
definition and epoch. This decision does not add leasing, competing-worker
orchestration, multi-epoch state, or a production rebuild runner.

## Reducer Correctness Boundary

The canonical production reducer directly enforces:

- `event.order_id == current_state.order_id`;
- `event.sequence == current_state.version + 1`;
- `CREATED` follows `INIT`;
- `PAID` follows `CREATED`;
- `PAID.amount` equals the current projected `total_amount` under the v1 model;
- unsupported event types are rejected;
- returned state preserves the order identity;
- returned state version equals the applied event sequence.

See [`reduce_order_event(...)`](../../src/pipeline/projection/reducer.py).

Targeted unit tests cover order mismatch, sequence gaps, supported transitions,
and PAID amount mismatch in
[`test_reducer.py`](../../tests/unit/pipeline/projection/test_reducer.py).
Adversarial history tests additionally exercise duplicate, out-of-order, and
broken-continuity replay.

A few narrow targeted negative tests remain absent, including direct exact-next
rejection cases for `CREATED` from non-`INIT`, `PAID` from a non-`CREATED`
state, and a forged or future unsupported event type. Those are test-coverage
gaps. They do not mean the corresponding production checks are absent.

The reducer validates one local transition. It does not prove that a projection
row was historically correct before the current call or remained unchanged
afterward. Full accepted-history replay owns that independent comparison.

## Accepted-Event and Progress Boundary

Eligible-event discovery reads only `order_events`, which is the accepted-
history table. An event is eligible only when its order-local sequence is:

```text
COALESCE(progress.last_sequence, 0) + 1
```

for the supplied projection name, projection epoch, and event order. See
[`PostgresProjectionEligibleEventSource`](../../src/storage/postgres_projection_eligible_event_source.py)
and its
[PostgreSQL integration tests](../../tests/integration/storage/test_postgres_projection_eligible_event_source.py).

Progress advancement independently rechecks that the cited accepted-event ID,
order ID, sequence, and global position exist together in `order_events`. It
admits initial sequence `1` or an update exactly one sequence beyond durable
progress; see
[`PostgresProjectionProgressStore`](../../src/storage/postgres_projection_progress_store.py).

The schema adds a composite accepted-event lineage foreign key and an exact-next
trigger in
[`006_create_projection_order_progress.sql`](../../db/migrations/006_create_projection_order_progress.sql).
Store and schema tests cover missing predecessor, regression, skip, rollback,
and mismatched lineage.

`global_position` remains:

```text
accepted-event lineage
+ deterministic scheduling metadata among eligible events
```

It is not transaction commit order and not a committed-history completeness
frontier. ADR 0020 remains the authority for that distinction.

## Worker Transaction Boundary

The current atomic unit is:

```text
projection_states
+ projection_order_progress
= one worker-owned top-level transaction
```

The worker rejects a non-idle connection before processing so an outer
transaction or nested savepoint cannot be confused with its durable commit.

Executable integration evidence establishes:

```text
progress failure
→ state and progress roll back

commit-time failure
→ no caller-visible applied result
→ neither state nor progress is durable

replacement worker / different worker_name
→ resume from durable per-order progress
```

See
[`test_postgres_projection_worker.py`](../../tests/integration/pipeline/projection/test_postgres_projection_worker.py)
and
[`test_postgres_projection_worker_commit_visibility.py`](../../tests/integration/pipeline/projection/test_postgres_projection_worker_commit_visibility.py).

This transaction boundary protects the supported normal materialization path.
It does not claim that privileged out-of-band writes are impossible.

## Database Mutation Authority

Stage 3.5E separates normal runtime responsibilities through PostgreSQL roles.
The current projection-state posture is:

```text
compass_app_writer
→ no projection_states access

compass_readonly
→ SELECT only

compass_snapshot_worker
→ SELECT only
→ no projection_states mutation authority

compass_projection_worker
→ SELECT / INSERT / UPDATE / DELETE projection_states
→ intended normal runtime projection-state writer
```

The projection worker may select, insert, and update repaired per-order
progress, but normal runtime deletion of that progress is denied. The complete
grants are implemented by
[`005_create_durable_state_permission_roles.sql`](../../db/migrations/005_create_durable_state_permission_roles.sql)
and migration 006, with named-role permission tests under
[`tests/integration/security/`](../../tests/integration/security/).

Privileged table owners, migration operators, database administrators, and
superusers remain outside the normal runtime mutation model. They may perform
controlled setup, reset, migration, or administrative work. The repository
does not claim to prevent a malicious database superuser.

Normal runtime correctness and privileged operational/security corruption are
therefore different threat boundaries.

## Write-Side Independence

Write-side command admission rehydrates `OrderAggregate` from durable accepted
history by loading `order_events` and applying that history in sequence. It
builds Compass Layer 1 validation context from the rehydrated aggregate and its
last accepted event; see
[`postgres_write_side.py`](../../src/pipeline/transactional/postgres_write_side.py).

The write-side unit of work owns only event and idempotency stores; it does not
load or save projection state. The `compass_app_writer` role also lacks
projection-state access.

Consequently, projection drift can make a read model wrong or stale, but it
cannot rewrite accepted business facts or become command-admission authority
through the supported write-side path.

## Replay and Rebuild Boundary

Accepted history plus the canonical reducer contains sufficient architectural
information to reconstruct the current order projection:

```text
accepted order_events ordered by local sequence
+ version-zero OrderState
+ canonical reducer
→ reconstructed projection state
```

[`DurableReplayValidator`](../../src/pipeline/projection/replay_validator.py)
performs an independent comparison in one repeatable-read, read-only PostgreSQL
observation. It replays accepted history through the reducer and compares the
result with persisted projection state. Its statuses distinguish match, missing
projection, drift, and no accepted history.

The durable replay integration tests cover matching state, missing state,
behind/ahead drift, observation stability, local-sequence replay order, and the
fact that validation does not mutate history or progress; see
[`test_durable_replay_validation.py`](../../tests/integration/pipeline/projection/test_durable_replay_validation.py).

A fully automated production rebuild command is not currently implemented. ADR
0020 instead records a human-controlled reset and replay boundary. This is an
operational tooling gap, not a reason to elevate projection state into business
authority.

## Failure-Class Ownership

### Normal runtime correctness

Examples include:

- wrong order;
- skipped or duplicate event;
- invalid transition;
- PAID amount mismatch;
- partial state/progress write.

These are owned by exact-next eligible discovery, the canonical reducer,
accepted-event progress lineage and schema constraints, the worker transaction,
and the normal runtime permission boundary.

Stage 4B.3 does not add a currently required correctness property to this path.

### Reducer / deployment correctness

Examples include:

- a reducer implementation bug;
- an incompatible reducer deployment;
- a common-mode bug shared by live reduction and replay validation.

These belong to reducer and domain correctness, deployment/versioning, rebuild,
and other separately scoped work. Stage 4B.5 is in progress in an independent
development stream; this ADR neither assigns those concerns to, defines, nor
sequences that work. The current projection epoch prevents legacy progress
reinterpretation, but it is not a general live reducer-version identity.

Structural projection qualification that uses the same reducer cannot
independently detect a common-mode reducer bug and does not by itself define a
safe deployment or rebuild protocol.

### Privileged operational corruption

Examples include:

- a table owner directly updating `projection_states`;
- a manual partial reset;
- a database superuser mutation.

These belong to permissions, operational procedures, audit, replay validation,
rebuild, backup/recovery, and security hardening. Incremental qualification does
not prevent a privileged actor from changing projection state after a boundary
was observed.

## Why Incremental Qualification Is Not Required

The proposed Stage 4B.3 continuation shape was:

```text
full accepted-history replay validates S_N
→ establish qualified boundary N

successful exact-next worker advance N → N+1
→ extend qualification to boundary N+1
```

However, the advance itself is already protected by:

```text
accepted-event source
+ exact-next order-local progress
+ same-order and exact-next reducer invariants
+ current transition and amount checks
+ accepted-event lineage recheck
+ atomic state/progress commit
```

Qualification therefore does not strengthen the supported normal
materialization path. It would add governance or attestation vocabulary that
repackages:

```text
previous replay consistency
+ an already-correct committed projection advance
→ a continuing-qualification conclusion
```

No current production consumer requires that conclusion, and no current runtime
action depends on it.

Repeated replay may have a cost when an independent comparison is requested.
For the current shallow Order workload, no evidence demonstrates that this cost
requires another trust state, continuation evaluator, or durable checkpoint.

## The Direct-Mutation Limitation

Consider a projection that was replay-validated as:

```text
version = N
amount  = 1000
```

A privileged actor later directly changes `projection_states` to:

```text
version = N
amount  = 100
```

The earlier replay `MATCH` or any qualification derived from it describes the
earlier observation. It cannot prove that the mutable row was not changed
later. Sequence equality also cannot detect same-version content replacement.

Only a new authoritative comparison, such as accepted-history replay, detects
that content drift unless a separately justified independent integrity or audit
mechanism observes the later mutation.

Therefore:

```text
qualification
!= corruption prevention
!= continuous integrity monitoring
!= durable authority
```

Stage 4B.3 must not be presented as a defense against direct privileged
mutation.

## Secondary-Authority Risk

A qualified projection boundary is safe only as derived evidence consistent
with accepted authority.

If a future consumer uses qualification to avoid accepted history indefinitely,
admit commands, repair accepted history, or authorize business actions as
though qualification itself were truth, qualification risks becoming a de
facto secondary authority.

The current repository has no consumer that requires this delegation. Normal
reads may use projection state as a derived read model, while command admission,
independent validation, and recovery remain grounded in accepted history.

## Decision

Stage 4B.3 incremental projection-trust continuation is:

```text
CLOSED AS NOT CURRENTLY JUSTIFIED
```

It is not a current runtime correctness requirement.

The delivery disposition is:

```text
PR1
= responsibility / problem boundary
= complete historical/reference work

PR2
= executable current-mechanics characterization
= complete historical/reference work

PR3–PR7
= not proceeding
```

No immutable projection-trust evidence contracts, base qualifier, committed-
advance evidence integration, continuation evaluator, trust checkpoint,
persistence, or serializer will be added under the closed stage.

The current correctness model remains:

```text
accepted history
→ deterministic exact-next projection worker
→ mutable projection state + durable per-order progress

accepted history replay
→ independent comparison / recovery path
```

## Consequences

### Positive

- The authority model remains small and explicit.
- Accepted history remains the sole business authority.
- Existing worker guarantees are not made to appear weaker merely because an
  additional qualification vocabulary could be invented.
- The repository avoids duplicate in-memory trust state with no restart
  semantics.
- The repository avoids another durable derived checkpoint with its own
  provenance, mutation, crash-gap, and reconciliation assumptions.
- Replay and rebuild remain the independent validation and recovery paths.

### Negative / deferred

- There is no typed incremental qualification artifact.
- There is no trust-continuation evaluator.
- There is no low-cost cross-event trust attestation.
- Full replay may be required when an independent projection comparison is
  actually requested.
- A deeper future workload or concrete governance consumer may justify
  revisiting the decision.

## Re-entry Conditions

Projection trust continuation may be reopened only when a concrete consumer can
identify:

1. who consumes qualification;
2. what action depends on it;
3. which missing correctness property the existing reducer, progress, lineage,
   permission, and transaction guarantees cannot provide;
4. why replay/rebuild is insufficient or too expensive for that consumer;
5. the restart and durability requirements;
6. how accepted history remains sole business authority;
7. how qualification avoids becoming a secondary business authority.

Any future proposal must also state whether evidence is transient or durable,
who may mutate it, how reducer/deployment compatibility is represented, and how
stale or corrupted evidence fails closed.

## Relationship to Existing ADRs

### ADR 0020 — Per-Order Projection Progress and Order-Local Snapshot Tails

ADR 0020 remains valid. It supplies the exact-next per-order progress and
worker-transaction mechanics that make the current normal projection path
correct without a global completeness cursor.

### ADR 0021 — Projection Snapshots Are Optional for the Current Order Workload

ADR 0021 remains valid. Projection snapshots remain optional reference and
reconstruction infrastructure. Snapshot trust correctness does not prove
snapshot necessity, just as theoretical continuation utility does not prove a
need for another projection runtime layer.

This ADR applies the same evidence-gated complexity principle: existing
machinery or theoretical usefulness does not itself justify additional runtime
state or governance.

## Reusable Principle

> A deterministic derived-state pipeline does not require a separate trust-
> continuation layer merely because its materialized state is mutable. Add
> qualification machinery only for a concrete consumer that needs evidence
> beyond accepted-history authority, producer invariants, durable processing
> lineage, atomic persistence, and replay-based recovery.
