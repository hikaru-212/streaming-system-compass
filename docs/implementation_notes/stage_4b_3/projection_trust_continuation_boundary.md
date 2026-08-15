# Projection Trust Boundary and Continuation

[← Back to Stage 4B.3](README.md)

## Historical Status and Supersession

This document preserves the accepted PR1 problem framing and source analysis.
Its proposal that Stage 4B.3 proceed into runtime trust-continuation
implementation is superseded by
[ADR 0026](../../adr/0026_projection_trust_continuation_is_not_currently_justified.md),
which closes Stage 4B.3 as not currently justified. PR1 remains useful
historical/reference evidence; Stage 4B.3 PR3 and later implementation work do
not proceed.

## Status

This document is the Stage 4B.3 PR1 responsibility authority. It records the
current source-grounded boundary, the evidence that is missing, the decisions
that remain open, and the work that Stage 4B.3 must not absorb.

PR1 is documentation-only. This document does not authorize production code,
tests, migrations, schemas, persistence, or runtime behavior. Conceptual names
used here do not freeze future class, field, status, serialization, schema, or
table names. Later implementation requires separately reviewed contracts and
executable evidence.

## Decision

Accepted history remains business authority. Projection state remains derived,
mutable state. A projection can agree with accepted replay at one observation
and can successfully apply one later event without either result, by itself,
proving that projection trust may continue.

Stage 4B.3 therefore owns the qualification boundary between:

```text
point-in-time replay/state agreement
+
one exact-next committed projection advance
```

and a future, explicitly evidenced continuation conclusion.

It does not make current projection state authoritative, establish domain
correctness, or authorize a runtime action.

## Current Projection Identity

Current production source supports one projection definition:

```text
projection_name  = order_state_projection
projection_epoch = 1
order_id          = aggregate-local identity
```

The worker fixes the name and epoch; callers cannot select a generalized
projection. `worker_name` is operational identity only and is deliberately
absent from durable progress identity.

Epoch `1` identifies the repaired per-order progress lineage. It prevents
reinterpretation of legacy checkpoint evidence. It is not reducer version, a
schema version, a multi-version runtime, or authority for concurrent projection
epochs.

The durable progress key is:

```text
(projection_name, projection_epoch, order_id)
```

The mutable `projection_states` key is only `order_id`. Consequently, projection
name plus epoch qualifies current durable progress identity, not complete
mutable projection-state identity.

Sources:

* [`order_projection_definition.py`](../../../src/pipeline/projection/order_projection_definition.py)
* [`postgres_worker.py`](../../../src/pipeline/projection/postgres_worker.py)
* [`006_create_projection_order_progress.sql`](../../../db/migrations/006_create_projection_order_progress.sql)
* [`002_create_read_side_tables.sql`](../../../db/migrations/002_create_read_side_tables.sql)
* [ADR 0020](../../adr/0020_per_order_projection_progress_and_order_local_snapshot_tails.md)

## Exact Meaning of Worker `APPLIED`

For one caller-visible worker result with `action="applied"`, current source
establishes this path:

```text
currently visible accepted exact-next event selected
→ current projection state loaded (or empty state constructed)
→ canonical reducer applied
→ projection state upserted
→ per-order progress advanced exactly once
→ accepted-event ID/order/sequence/global-position lineage rechecked
→ projection state and progress transaction exits successfully
→ result reaches caller
```

The worker owns the top-level transaction. State and progress use the same
connection and therefore commit or roll back together. A progress conflict or
commit failure prevents a caller-visible `applied` result.

This supports the narrow statement:

```text
APPLIED
= one committed exact-next projection advance
```

It does not prove global catch-up, history completeness, full replay
equivalence, intended domain correctness, continuing trust, snapshot trust,
freshness, or runtime action authority.

The result object is intended for integration tests and debugging. Its fields
report `worker_name`, action, global position, order ID, event sequence,
projected version, and a reason. It does not carry projection name or epoch,
accepted event ID, prior sequence, pre- or post-state binding, durable progress
identity, live-logic identity, or an independent commit identity. Caller
visibility is commit-correlated behavior of `process_next`; the object is not a
standalone continuation proof.

Sources:

* [`postgres_worker.py`](../../../src/pipeline/projection/postgres_worker.py)
* [`postgres_projection_progress_store.py`](../../../src/storage/postgres_projection_progress_store.py)
* [`postgres_projection_store.py`](../../../src/storage/postgres_projection_store.py)
* [`test_postgres_projection_worker.py`](../../../tests/integration/pipeline/projection/test_postgres_projection_worker.py)
* [`test_postgres_projection_worker_commit_visibility.py`](../../../tests/integration/pipeline/projection/test_postgres_projection_worker_commit_visibility.py)

## Exact Meaning of Replay `MATCH`

`DurableReplayValidator.validate_order()` owns one PostgreSQL transaction and
sets it to `REPEATABLE READ READ ONLY`. Within that observation it:

1. loads accepted history for one order;
2. replays all accepted events visible to that transaction through the
   canonical reducer;
3. loads the persisted projection state for the same order;
4. compares the replay-derived and persisted `OrderState` values.

One `MATCH` therefore means:

> For one order in one repeatable-read observation, canonical replay of the
> visible accepted history produced an `OrderState` equal to the visible
> persisted `OrderState`.

The compared state contains order ID, status, total amount, paid amount, and
version. `projection_states.last_sequence` is not loaded or independently
validated. The validator does not inspect per-order progress, capture terminal
accepted event ID or global position, capture projection name or epoch, identify
the reducer version, or claim global completeness. A match can therefore occur
without a durable progress row.

The required distinction is:

```text
MATCH
= point-in-time state-consistency observation
!= continuation-capable validated projection boundary
```

Sources:

* [`replay_validator.py`](../../../src/pipeline/projection/replay_validator.py)
* [`postgres_projection_store.py`](../../../src/storage/postgres_projection_store.py)
* [`reducer.py`](../../../src/pipeline/projection/reducer.py)
* [`test_durable_replay_validation.py`](../../../tests/integration/pipeline/projection/test_durable_replay_validation.py)

## Observation-to-Boundary Gap

Qualifying an order-local base at sequence `N` requires more than renaming a
`MATCH`. The current repository provides uneven pieces of the necessary
evidence:

| Evidence concern | Current classification | Reason |
| --- | --- | --- |
| Terminal accepted event ID | Derivable now; requires source enrichment to preserve | Accepted replay has the event, but `ReplayValidationResult` does not retain its identity |
| Terminal order-local sequence | Available/derivable now | Replay-derived `OrderState.version` represents the last applied local sequence |
| Projection name and epoch | Derivable now for the one fixed definition | Constants exist, but the replay result does not capture them |
| Durable progress lineage | Available now but requires a new qualification contract | The progress row carries event ID, sequence, and global position; replay validation does not inspect it |
| Projection-state content | Available in the observation but requires a new binding contract | Both expected and persisted states are returned; no continuation-safe binding is defined |
| Source observation identity | Currently unavailable; requires a new contract | Repeatable-read consistency exists, but no reusable observation identity is emitted |
| Live projection-logic identity | Currently unavailable | No authoritative live reducer identity or version is defined |
| Commit-correlated advance evidence | Behavioral correlation exists; requires contract enrichment | Caller-visible `applied` follows transaction exit, but the result lacks the evidence needed to join boundaries |
| Global-position lineage | Available in progress and worker results; requires enrichment where needed | It is event lineage and a scheduling tie-breaker, not a completeness frontier |

The future qualification contract must distinguish facts read directly in one
observation, facts derived from them without new semantics, and facts acquired
later. It must not present a later read as if it belonged to the original
observation.

## State-Content Binding

Sequence or version equality is insufficient projection-state binding.

`projection_states` is keyed only by order ID and is upserted independently by
the projection store. `projection_order_progress` is separately keyed by
projection name, epoch, and order ID. The progress row has accepted-event
lineage constraints, but there is no cross-table constraint requiring its
sequence to equal projection-state version or `last_sequence`. The store API
also permits projection state to be saved or cleared independently of progress.

The current worker avoids divergence on its successful path by writing state
and progress in one transaction. That operational invariant does not turn the
two schemas into one identity and does not protect a future continuation claim
from independent mutation outside that path.

A continuation-capable boundary must therefore bind the actual observed
projection-state content somehow. PR1 does not select a hash, fingerprint,
canonical serialization, full-state embedding, or other representation.
Snapshot `payload_hash` is snapshot-specific metadata and is not reused by
default.

Sources:

* [`002_create_read_side_tables.sql`](../../../db/migrations/002_create_read_side_tables.sql)
* [`006_create_projection_order_progress.sql`](../../../db/migrations/006_create_projection_order_progress.sql)
* [`postgres_projection_store.py`](../../../src/storage/postgres_projection_store.py)

## Live Projection-Logic Identity

The repository has one canonical live reducer function, but it has no
authoritative live reducer version or other durable logic identity that can
qualify mutable projection execution across time.

```text
projection_epoch
!= reducer_version

snapshot reducer-version metadata
!= automatically authoritative live projection-logic identity
```

Stage 4B.3 cannot honestly claim reducer-version-qualified continuation until a
separately accepted design establishes that identity. A narrower initial design
may decline to make such a claim, but PR1 does not choose between those paths or
select a representation.

Sources:

* [`order_projection_definition.py`](../../../src/pipeline/projection/order_projection_definition.py)
* [`reducer.py`](../../../src/pipeline/projection/reducer.py)

## Current and Future Atomicity

Current repository authority establishes one worker-owned atomic unit:

```text
projection state
+
per-order progress
→ same top-level transaction
```

No trust checkpoint participates today. Future trust-checkpoint ownership is an
unresolved decision:

### Model A — same transaction

```text
state + progress + trust checkpoint
→ commit or roll back together
```

This couples checkpoint availability and failure to the projection write path,
but avoids a post-commit crash gap for that advance. It would change the current
worker transaction and availability boundary.

### Model B — separate materialization

```text
state + progress commit
→ trust checkpoint materialized later
```

This preserves projection-write independence, but introduces crash gaps, stale
checkpoint windows, races with later advances, possible loss of an intermediate
state, and reconciliation requirements. A safe design must prevent false
positive trust when materialization no longer corresponds to the committed
state it claims to qualify.

PR1 selects neither model.

## Base Observation / Materialization Boundary

Replay validation is read-only. The transaction that establishes `MATCH` cannot
also write a durable checkpoint. A later write transaction therefore creates a
time-of-check/time-of-materialization boundary:

```text
transaction R observes accepted history and projection state at N
→ R ends
→ projection and/or accepted history may advance or state may be replaced
→ transaction W attempts to materialize evidence about R
```

Unless the future design preserves and requalifies the relevant observation,
lineage, and state binding, `W` can record a claim that no longer corresponds to
the state it purports to qualify. No later repository work currently solves
this gap. PR1 records it without choosing a materialization mechanism.

## Candidate Continuation Responsibility

Stage 4B.3 may eventually evaluate a narrow order-local transition of this
shape:

```text
qualified boundary at N
+
qualified exact-next committed advance N → N+1
→ continuation result for N+1
```

Such an evaluation must join compatible projection/progress identity,
order-local sequence, accepted-event lineage, pre-state and post-state binding,
source observation, applicable logic qualification, and commit-correlated
completion. Missing evidence must remain missing or unresolved; it must not be
filled by inference from `MATCH`, `APPLIED`, DiagnosticTrace, measurement
evidence, or adjacent Stage 4 contracts.

This is an order-local continuation boundary. It is not a global validated
frontier or a freshness guarantee.

## Relationship to Adjacent Work

Stage 4B.3 does not require ownership from:

* Stage 4B.1 DiagnosticTrace, which records resolution provenance;
* Stage 4B.2 measurement evidence, which records measurement provenance;
* Stage 4B.5 Order Correctness Contract, which owns domain correctness;
* Stage 4C RuntimeDecisionPolicy, which owns runtime action selection;
* Stage 4D StrategySelector, which owns execution strategy;
* Stage 4E retry and AttemptLog governance.

Projection trust continuation also differs from snapshot trust. Snapshots are
immutable historical compression artifacts; projection state is mutable and
continuously advanced. Snapshot evidence must not be copied into the live
projection boundary without independent justification.

## Decisions Required Before Implementation

The following remain explicit architecture decisions:

1. the minimum qualification evidence for an order-local base;
2. the representation used to bind state content;
3. whether and how live projection logic is identified;
4. how the original replay observation is preserved or requalified;
5. the minimum evidence for one continuation step;
6. the vocabulary for missing, mismatched, or unresolved evidence;
7. whether durable trust checkpoints are required;
8. if required, Model A versus Model B and all persistence consequences.

## Non-Goals

PR1 and this responsibility boundary do not select or authorize:

* a state hash or fingerprint representation;
* reducer-version representation;
* trust-checkpoint schema, table, migration, or persistence API;
* runtime actions, strategies, retry, AttemptLog, fallback, or remediation;
* DiagnosticTrace or measurement-evidence redesign;
* snapshot trust redesign;
* global catch-up, a global validated frontier, or history-completeness proof;
* trust TTL, leases, revalidation cadence, sampling, or scheduling;
* a production runner, automatic rebuild, or quarantine;
* accepted-history mutation or a generic trust framework.

## Reusable Principle

> A trustworthy continuation claim must bind the observed state, the accepted
> lineage that produced it, the exact transition that advanced it, and the
> applicable projection logic. Sequence coincidence and successful execution
> are necessary evidence in the current design, but neither is sufficient
> authority.
