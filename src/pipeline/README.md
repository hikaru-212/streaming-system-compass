# Pipeline Layer

[← Back to src README](../README.md)

This module defines how events and state transitions move through the system.

If `src/core/` defines semantic meaning, and `src/storage/` preserves history, then `src/pipeline/` defines the execution flow built around them.

---

## Purpose

The purpose of this module is to coordinate how domain events are:

- admitted
- persisted
- replayed
- projected
- validated against replayed authority
- resolved through snapshot-assisted read-side paths
- analytically processed later

This is the layer where the system begins to behave like a runtime rather than only a domain model.

---

## Responsible For

This module is responsible for:

- transactional command flow
- event admission path
- replay / rehydration flow
- projection execution flow
- durable replay / rebuild validation flow
- projection snapshot-assisted replay validation
- projection snapshot-assisted state resolution
- analytical event-processing flow later

Current and planned submodules include:

- `transactional/`
- `projection/`
- `analytical/` (planned later)

---

## Not Responsible For

This module is **not** responsible for:

- defining domain event meaning
- defining aggregate legality rules
- acting as the persistence layer itself
- being the final owner of semantic policy
- injecting adversarial failure
- deciding database permissions
- treating snapshots as authority
- replacing accepted-history replay with unqualified snapshot trust

Those responsibilities belong to:

- [core/](../core/README.md)
- [storage/](../storage/README.md)
- [compass/](../compass/README.md)
- `chaos_engine/`
- future Stage 3.5E durable history / permission hardening

---

## Design Principle

This layer should be treated as the **execution topology** of the system.

It answers questions such as:

- In what order are components called?
- When does validation happen?
- When is an event persisted?
- When is state applied?
- When is projection updated?
- How does replay happen after restart?
- When is snapshot-assisted replay allowed to participate?
- When must authority replay remain the comparison path?

In short:

- core defines meaning
- pipeline defines movement
- storage preserves movement and progress
- Compass checks whether movement remains semantically correct

The pipeline should coordinate boundaries without owning all of them.

---

## Main Pipeline Boundaries

### [transactional/](transactional/)

Defines the write-side transactional flow.

Typical responsibilities:

- handle incoming commands
- coordinate idempotency checks
- call aggregate logic
- run event admission checks
- run Compass Layer 1 validation
- persist accepted events
- record idempotency results
- apply accepted events to in-memory aggregate state
- rebuild aggregate state through accepted-history replay
- preserve validation placement and append-time admission boundaries

This is the first pipeline segment that was implemented.

For the higher-level write-side design, see:

- [Transactional Core](../../docs/architecture/transactional_core.md)
- [ADR 0010 — Separate Transaction Atomicity from Concurrency Admission](../../docs/adr/0010_transaction_atomicity_vs_concurrency_admission.md)
- [ADR 0011 — Separate Validation Mode from Validation Placement Strategy](../../docs/adr/0011_validation_mode_vs_validation_placement.md)
- [ADR 0012 — Two-Phase Concurrency Admission for PostgreSQL Write-Side](../../docs/adr/0012_two_phase_concurrency_admission.md)

---

### [projection/](projection/)

Defines the read-side projection flow.

Typical responsibilities:

- consume events from accepted history
- incrementally build materialized state
- persist projection state
- track checkpoints / offsets
- recover through replay / rebuild
- validate durable projection state against accepted-history replay
- validate snapshot-assisted replay against authority replay
- resolve read-side state from qualified snapshot + tail replay
- enforce baseline sequencing assumptions

The projection runtime now has several baseline forms:

1. a deterministic in-memory Stage 3 baseline
2. a PostgreSQL-backed Stage 3.5C PR4 worker baseline
3. a Stage 3.5C PR5 durable replay / rebuild validation baseline
4. a Stage 3.5D PR4 projection snapshot-assisted replay validation baseline
5. a Stage 3.5D PR4.5 projection snapshot-assisted state resolver baseline

The current PostgreSQL-backed projection worker connects:

```text
order_events
→ PostgresProjectionEligibleEventSource
→ canonical reducer
→ PostgresProjectionStore
→ PostgresProjectionProgressStore
```

and persists:

```text
projection state
+
exact-next per-order progress
```

inside one read-side transaction boundary.

The repaired worker uses:

```text
(projection_name = order_state_projection, projection_epoch = 1, order_id)
→ last applied local sequence + accepted-event lineage
```

`global_position` remains accepted-event lineage and deterministic scheduling
metadata. It is not a restart cursor or complete committed-history frontier.
Legacy global checkpoint rows do not bootstrap repaired progress.

Durable replay validation compares:

```text
accepted-history replay
vs
persisted projection state
```

Snapshot-assisted replay validation compares:

```text
snapshot-assisted replay
vs
full accepted-history replay
```

Snapshot-assisted state resolution reconstructs read-side state through:

```text
qualified projection snapshot
→ hydrate snapshot state
→ load same-order tail events after snapshot.source_event_sequence
→ replay tail through canonical reducer
→ resolved projection state
```

Stage 4A and Stage 4B now map the current read-side validation evidence into
`SemanticOutcome` and `DecisionReceipt`. Those mappings remain point-in-time
governance evidence; they do not establish projection trust continuation or
runtime action authority.

For the higher-level projection design, see:

- [Projection Pipeline](../../docs/architecture/projection_pipeline.md)
- [Projection Boundary](../../docs/boundary_notes/projection_boundary.md)
- [Global-Position Projection Worker Boundary](../../docs/boundary_notes/global_position_projection_worker_boundary.md)
- [ADR 0013 — Snapshot Runtime Eligibility and Validation Receipt Boundary](../../docs/adr/0013_snapshot_runtime_eligibility_and_validation_receipt_boundary.md)
- [Projection README](projection/README.md)
- [Stage 4B.3 Projection Trust Boundary](../../docs/implementation_notes/stage_4b_3/projection_trust_continuation_boundary.md)

---

### `analytical/` (planned)

Defines the future analytical interpretation of the same event stream.

Typical responsibilities may later include:

- event-time processing
- aggregation
- windows
- lateness handling
- analytical metrics or statistical views

This layer is intentionally deferred until the transactional, projection, durable read-side, and semantic validation baselines are stronger.

---

## Current Implementation Scope

At the current stage, the implemented focus includes:

1. [transactional/](transactional/)
2. [projection/](projection/)

while:

1. `analytical/`

remains a later stage.

The reason is still the same:

- transactional flow establishes correctness of event admission and persistence
- projection flow establishes correctness of state derivation
- replay validation establishes whether persisted derived state matches accepted history
- snapshot-assisted replay establishes efficiency without replacing authority
- analytical flow is valuable, but should be built on top of a stable semantic foundation

---

## Transactional Flow as the First Milestone

The first important pipeline path is:

1. receive command
2. check idempotency
3. load or create aggregate
4. replay historical events if needed
5. produce candidate event
6. validate event admission / transition truth
7. run concurrency admission
8. persist accepted event
9. record idempotency result
10. apply event to aggregate state or return durable result

This write-side path exists as the current durable PostgreSQL-backed baseline after Stage 3.5B.

The durable write-side baseline includes:

- `PostgresWriteSideUnitOfWork`
- `PostgresTransactionalWriteSide`
- `PostgresOptimisticAdmissionGate`
- `PostgresPessimisticAdmissionGate`
- `prepare_stream(order_id)`
- `append_if_admitted(candidate_event, expected_current_version)`
- `IN_TRANSACTION` validation placement
- minimal `PRE_TRANSACTION` validation placement guarded by append-time admission

The key boundary is:

```text
Compass validation
≠ concurrency admission
≠ transaction atomicity
≠ idempotency replay / conflict classification
```

---

## Projection Flow as the Second Milestone

After the transactional path became stable, the projection path evolved from:

- a demo-level replay helper

into:

- a baseline projection runtime with worker / reducer separation

The Stage 3 in-memory projection baseline supports:

- incremental application
- replayability
- checkpoint-aware sequencing
- deterministic replay / rebuild through the same runtime path

Stage 3.5C PR4 introduced the first PostgreSQL-backed worker. ADR 0020 later
repaired its progress boundary after the scalar global-position checkpoint was
shown not to be a commit-safe completeness cursor.

It supports:

- currently visible exact-next accepted-event discovery through `PostgresProjectionEligibleEventSource`
- shared order-event hydration through `order_event_hydration.py`
- durable projection state through `PostgresProjectionStore`
- durable repaired progress through `PostgresProjectionProgressStore`
- progress identity `(projection_name, projection_epoch, order_id)`
- atomic projection-state and per-order-progress persistence through `PostgresProjectionWorker`
- fail-fast handling for projection-state / progress mismatch
- `global_position` as lineage and scheduling metadata rather than completeness proof

Stage 3.5C PR5 adds durable replay / rebuild validation.

It supports:

- full accepted-history replay for one order
- comparison against persisted projection state
- `MATCH`
- `MISSING_PROJECTION`
- `DRIFT`
- `NO_ACCEPTED_HISTORY`
- replay validation that does not mutate projection state
- replay validation that does not advance checkpoint progress

Stage 3.5D adds snapshot-assisted replay / resolution.

It supports:

- projection snapshot schema and store
- projection snapshot-assisted replay validator
- projection snapshot-assisted state resolver
- explicit result states for match, missing snapshot, invalid boundary, tail contract violation, drift, unresolved resolver paths, and compatibility failures
- aggregate snapshot trust deferral because write-side aggregate snapshots can affect command validation and accepted-history admission

The projection path still does **not yet** include:

- projection trust continuation or durable projection-trust checkpoints
- runtime decision policy
- action safety gate
- out-of-order buffering
- DLQ handling
- watermark semantics
- worker leasing
- checkpoint row locking
- multi-worker coordination
- a production projection runner

Stage 4A and Stage 4B already provide structured semantic and receipt mappings
for current validation results. The remaining concerns stay separately owned by
Stage 4B.3, later runtime-governance stages, or production hardening.

---

## Snapshot-Assisted Read-Side Flow

Stage 3.5D introduces snapshot-assisted read-side flow without changing source-of-truth authority.

The core model is:

```text
accepted history = authority
snapshot = derived state compression
fast path = qualified snapshot + tail replay
validator = expensive authority comparison
resolver = safe read-side resolution primitive
```

The validator path answers:

```text
Does snapshot-assisted reconstruction match full accepted-history replay?
```

The resolver path answers:

```text
Can a caller reconstruct read-side state from an explicitly qualified snapshot and tail events?
```

The resolver does not decide whether the caller should fall back to full replay.

The resolver does not prove semantic equivalence by itself.

The broader runtime must continue to treat accepted history as the authority path.

---

## Near-Term Integration Points

This module directly connects:

### `src/core/order/`

For event production and aggregate rehydration.

### `src/storage/`

For event persistence, idempotency storage, projection state, event-source loading, checkpointing, and projection snapshot persistence.

### `src/compass/transition/`

For validating whether candidate events are admissible before accepted-history mutation.

### `src/pipeline/projection/`

For durable projection worker orchestration, replay validation, snapshot-assisted replay validation, and snapshot-assisted state resolution.

---

## Long-Term Integration Points

Later, this module will also connect heavily with:

### persistence-backed storage evolution

To strengthen write-side and read-side restart semantics beyond the current durable baseline.

### Stage 4B.3 projection trust continuation

To define whether a previously qualified per-order projection boundary remains
qualified after one exact-next committed advance. The current `MATCH` and
`APPLIED` results are inputs to that design, not continuation evidence by
themselves.

### Stage 4 runtime governance

The current foundation already converts selected validation results into:

```text
SemanticOutcome
→ DecisionReceipt
```

Later stages own runtime decisions, strategy selection, retry governance, and
action safety.

### `chaos_engine/`

To test how pipeline behavior survives:

- out-of-order delivery
- duplicate events
- poison messages
- partial commits
- network delays
- recovery interruptions
- snapshot corruption
- stale checkpoint / projection mismatch

---

## Key Invariants

At the current stage, the main pipeline-related invariants include:

- transactional event admission must preserve domain legality
- replay must rebuild aggregate state deterministically
- Compass Layer 1 validation must block invalid candidate events before accepted-history mutation
- admission must reject stale or unprepared writers
- projection must produce state consistent with processed accepted history
- repaired projection progress must advance by exact-next order-local sequence and accepted-event lineage
- PostgreSQL-backed projection must persist projection state and per-order progress atomically
- replay / rebuild must follow the same baseline projection semantics as incremental processing
- snapshot-assisted replay must not treat snapshot rows as authority
- snapshot-assisted state resolution must replay tail events through the canonical reducer
- aggregate snapshot trust remains deferred until write-side command-validation risk justifies it

Later analytical invariants may include:

- window boundaries are respected
- lateness handling remains semantically consistent

---

## Practical Reading Order

If reading this module from scratch, the recommended order is:

1. `transactional/`
2. `projection/`
3. `analytical/` later

Within `projection/`, the useful conceptual order is:

```text
reducer
→ worker
→ durable worker
→ replay validator
→ snapshot-assisted replay validator
→ snapshot-assisted state resolver
```

This reflects the current implementation order of the system.

---

## Summary

This module is where semantic rules turn into runtime flow.

If the core defines what the system means, the pipeline defines how that meaning moves through time.

The pipeline layer includes durable write-side orchestration, durable read-side
projection orchestration, replay validation, snapshot-assisted read-side
resolution, and Stage 4A/4B mapping into structured governance evidence. It
remains intentionally short of projection trust continuation, runtime decision
policy, strategy selection, retry governance, and action safety.
