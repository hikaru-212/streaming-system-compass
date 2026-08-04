# Read-side Documentation Index

[← Back to Topic_Indexes Index](README.md)

## How to Use This Index

This is an experimental, topic-based navigation layer for the reviewed Read-side documentation. The existing `docs/` structure remains the source for each document's type, status, and development context.

A document may appear under more than one topic when it makes a substantial contribution to each subject. Repetition here provides navigation; it does not grant the document additional authority.

This index does not transfer authority from accepted event history to projection state, progress rows, checkpoints, or delivery envelopes. Later completed boundaries govern current implementation interpretation when older planning documents describe a broader intended scope. Reasoning notes preserve derivations; postmortems reconstruct concrete episodes. Neither defines current architecture by itself.

## Read-side Reading Path

| Order | Document | Role | Why read here |
|---:|---|---|---|
| 1 | [Stage 3.5C — Durable Read-Side Baseline](../../implementation_notes/stage_3_5c/README.md) | Stage navigation/status | Start with the completed baseline's scope, authority model, and explicit later-stage exclusions. |
| 2 | [Projection Module](../../boundary_notes/projection_module.md) | Boundary note | Establish projection as state derivation from accepted history rather than event admission or truth ownership. |
| 3 | [ADR 0020 — Per-Order Projection Progress](../../adr/0020_per_order_projection_progress_and_order_local_snapshot_tails.md) | Accepted ADR | Establish exact-next per-order completeness and the narrower lineage/scheduling role of `global_position`. |
| 4 | [Read-Side Persistence Boundary](../../boundary_notes/read_side_persistence_boundary.md) | Boundary note | Separate accepted history, durable projection state, progress evidence, per-order sequence, and source coordinates. |
| 5 | [Projection Boundary](../../boundary_notes/projection_boundary.md) | Boundary note | Separate the pure reducer, runtime worker, projection store, and progress store. |
| 6 | [Global-Position Projection Worker Boundary](../../boundary_notes/global_position_projection_worker_boundary.md) | Historical Stage 3.5C boundary | Understand the earlier scalar-checkpoint design that ADR 0020 replaced for current completeness. |
| 7 | [Checkpoint Module](../../boundary_notes/checkpoint_module.md) | Historical/generic boundary | Learn why checkpoint state is operational metadata and why the legacy scalar checkpoint is not current completeness. |
| 8 | [Durable Read-Side Schema Baseline](../../architecture/read_side_schema_baseline.md) | Historical schema baseline | Examine the original state/checkpoint schemas before the ADR 0020 repair. |
| 9 | [Durable Replay / Rebuild Validation Boundary](../../boundary_notes/durable_replay_rebuild_validation_boundary.md) | Boundary note | Learn the completed validation-only PR5 comparison contract and its result vocabulary. |
| 10 | [ADR 0014 — Defer Projection Events as a Separate Delivery Layer](../../adr/0014_defer_projection_events_as_delivery_layer.md) | ADR | Confirm that direct accepted-history consumption does not introduce a second event-truth layer. |
| 11 | [Stage 3.5C PR Breakdown](../../implementation_notes/stage_3_5c/pr_breakdown.md), [Projection Pipeline](../../architecture/projection_pipeline.md), and the reviewed reasoning notes/postmortems | Implementation history and design evolution | Finish with implementation chronology, earlier maturity language, derivations, and historical lessons after current boundaries are understood. |

## Read-side Overview and Responsibility Map

Accepted event history is the authoritative source of admitted facts. Projection state is durable but derived and rebuildable. Current projection completeness is exact-next and per order through `projection_order_progress`. Legacy scalar checkpoint state is historical operational metadata. Neither projection state nor any progress artifact is accepted history.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Stage 3.5C — Durable Read-Side Baseline](../../implementation_notes/stage_3_5c/README.md) | Stage navigation/status | Start here | Summarizes accepted-history authority, derived projection state, operational checkpoints, and replay as the authority path. | Stage 3.5C is complete at the durable Read-side baseline level; distributed orchestration and Layer 2 remain later work. |
| [Projection Module](../../boundary_notes/projection_module.md) | Boundary note | Core | Defines the external projection responsibility and excludes write-side admission and event-truth ownership. | Essential responsibility boundary; no formal ADR status is claimed. |
| [Read-Side Persistence Boundary](../../boundary_notes/read_side_persistence_boundary.md) | Boundary note | Core | Defines the durable authority, derived-state, checkpoint, and cursor separations. | Originally PR1 planning; explicitly updated to reflect completed Stage 3.5C. |
| [High-Level Architecture](../../architecture/high_level_architecture.md) | Architecture | Deep dive | Places projection after accepted-history admission and before later state-level validation. | Foundation architecture; it does not make projection output authoritative history. |
| [Compass Layers](../../architecture/compass_layers.md) | Architecture | Deep dive | Distinguishes write-side transition validation from later projection/state validation. | Layer 2 direction does not imply that Stage 3.5C PR5 already implements Layer 2. |

## Accepted History as Projection Source

Projection consumes admitted facts from accepted event history. If accepted history and any derived projection, checkpoint, or delivery artifact disagree, accepted history remains the recovery authority.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Projection Module](../../boundary_notes/projection_module.md) | Boundary note | Start here | Defines projection as transformation of accepted event history into read-side state. | Projection does not decide whether events were admissible. |
| [Read-Side Persistence Boundary](../../boundary_notes/read_side_persistence_boundary.md) | Boundary note | Core | Defines `order_events` as accepted-history authority and read-side tables as correctable derived artifacts. | Current durable boundary preserved through Stage 3.5C. |
| [Durable Read-Side Schema Baseline](../../architecture/read_side_schema_baseline.md) | Architecture | Core | Makes accepted history the rebuild source for durable `projection_states`. | Completed Stage 3.5C schema foundation. |
| [ADR 0014 — Defer Projection Events as a Separate Delivery Layer](../../adr/0014_defer_projection_events_as_delivery_layer.md) | ADR | Deep dive | Keeps `order_events` as the direct projection source and defers any separate durable delivery layer. | Accepted deferral decision; a future delivery layer would remain derived. |
| [From Projection Concerns to Event Truth](../../reasoning_notes/from_projection_concerns_to_event_truth.md) | Reasoning note | Historical/supporting | Explains the project's derivation from projection-first concerns to accepted-history entry as the earlier correctness boundary. | Non-authoritative reasoning record, not a current runtime contract. |

## Projection Worker and Reducer

The reducer owns pure, deterministic state derivation. It consumes current projected state and an exact-next accepted event and produces the next projected state. It remains unaware of storage, checkpoints, event acquisition, restart, and worker control flow.

The projection worker owns eligible accepted-event acquisition, deterministic scheduling, exact-next local apply/gap classification, reducer invocation, transaction orchestration, projection persistence, per-order progress advancement, commit/rollback, and restart flow. Projection state and its per-order progress commit atomically. The worker must not duplicate or redefine reducer logic.

The supported topology remains one active worker for the current projection definition and epoch. Multi-worker leases, coordination, capacity control, and a global committed watermark remain deferred.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Projection Boundary](../../boundary_notes/projection_boundary.md) | Boundary note | Start here | Defines the reducer as the local semantic core and the worker as the local runtime enabler. | Written before implementation; the responsibility split remains current. |
| [ADR 0020 — Per-Order Projection Progress](../../adr/0020_per_order_projection_progress_and_order_local_snapshot_tails.md) | Accepted ADR | Core | Defines the repaired PostgreSQL worker orchestration, exact-next eligibility, and atomic state/progress transaction. | Current completeness authority. |
| [Global-Position Projection Worker Boundary](../../boundary_notes/global_position_projection_worker_boundary.md) | Historical Stage 3.5C boundary | Historical/supporting | Records the earlier PostgreSQL worker and confirms that the canonical reducer remains storage-agnostic. | Its scalar-checkpoint completeness model is superseded by ADR 0020. |
| [Projection Pipeline](../../architecture/projection_pipeline.md) | Planning-era architecture/evolution note | Deep dive | Describes the Stage 3 reducer, worker, store, and shared replay path as an architecture progression. | Its Stage 3 in-memory/durability maturity language predates completed Stage 3.5C. |
| [Stage 3.5C PR Breakdown](../../implementation_notes/stage_3_5c/pr_breakdown.md) | Implementation history | Historical/supporting | Records the PR4 implementation sequence connecting source, reducer, stores, and transaction ownership. | Useful delivery history; does not override later completed boundaries. |

## Global Position and Event Consumption

`global_position` is a globally unique accepted-event identity and lineage coordinate. The current worker uses it only as deterministic scheduling metadata among events already eligible through per-order exact-next progress. It is not a committed-history completeness frontier and does not own restart completeness.

It is not interchangeable with per-order `sequence`. The current baseline supports one active worker for the projection definition and epoch; distributed, sharded, multi-worker, and global-watermark models remain outside the implemented boundary.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [ADR 0020 — Per-Order Projection Progress](../../adr/0020_per_order_projection_progress_and_order_local_snapshot_tails.md) | Accepted ADR | Start here | Defines `global_position` as lineage and scheduling evidence while per-order progress owns completeness. | Current implemented decision. |
| [Global-Position Projection Worker Boundary](../../boundary_notes/global_position_projection_worker_boundary.md) | Historical Stage 3.5C boundary | Historical/supporting | Preserves the earlier `load_after` and scalar-checkpoint model. | Not the current completeness contract after ADR 0020. |
| [Durable Read-Side Schema Baseline](../../architecture/read_side_schema_baseline.md) | Historical schema baseline | Historical/supporting | Preserves the generic cursor schema and Stage 3.5C selection of global position. | Read through ADR 0020 for current progress semantics. |
| [Read-Side Persistence Boundary](../../boundary_notes/read_side_persistence_boundary.md) | Historical/supporting boundary | Historical/supporting | Explains the earlier aggregate-sequence versus worker-cursor distinction. | Read through ADR 0020; local sequence now owns per-order completeness. |
| [From Per-Order Global Position to Global Source Boundary](../../postmortems/from_per_order_global_position_to_global_source_boundary.md) | Postmortem | Historical/supporting | Reinforces that a global source boundary is globally scoped even when recorded beside order-local fields. | Stage 3.5D snapshot-schema correction; not part of the Stage 3.5C worker implementation. |

## Per-order Sequence and Projection Continuity

Per-order `sequence` is aggregate-local causal order. It is used for one-order replay, projection version/`last_sequence`, exact-next reducer continuity, and current per-order completeness through `projection_order_progress`. It is not a global coordinate or global watermark.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [ADR 0020 — Per-Order Projection Progress](../../adr/0020_per_order_projection_progress_and_order_local_snapshot_tails.md) | Accepted ADR | Start here | Defines `(projection_name, projection_epoch, order_id)` progress and exact-next `last_sequence` advancement. | Current implemented completeness contract. |
| [Durable Read-Side Schema Baseline](../../architecture/read_side_schema_baseline.md) | Historical schema baseline | Historical/supporting | Defines `projection_states.last_sequence` as local reflected progress. | Predates the dedicated `projection_order_progress` repair. |
| [Projection Boundary](../../boundary_notes/projection_boundary.md) | Boundary note | Core | Defines exact-next reduction and worker-level skip/apply/gap classification. | High-level duplicate/gap policy; advanced disorder handling remains deferred. |
| [Global-Position Projection Worker Boundary](../../boundary_notes/global_position_projection_worker_boundary.md) | Boundary note | Deep dive | Contrasts local causal sequence, global accepted-history order, and worker checkpoint cursor. | Stage 3.5C PR4 complete. |
| [Durable Replay / Rebuild Validation Boundary](../../boundary_notes/durable_replay_rebuild_validation_boundary.md) | Boundary note | Deep dive | Requires one-order validation replay to use `sequence ASC`, not global worker order as a substitute for local causality. | Stage 3.5C PR5 complete. |
| [From Per-Order Global Position to Global Source Boundary](../../postmortems/from_per_order_global_position_to_global_source_boundary.md) | Postmortem | Historical/supporting | Preserves the reusable distinction between local sequence scope and global source scope. | Historical Stage 3.5D correction. |

## Progress and Restart Semantics

Current restart completeness is recorded independently for each order in `projection_order_progress`. An accepted event is eligible only when its sequence is exactly the next local sequence. Projection-state mutation and the corresponding per-order progress update commit or roll back together.

The generic `projection_checkpoints` infrastructure remains, but the repaired order-state worker neither reads nor advances the legacy scalar checkpoint. Existing rows are historical evidence of the largest visible allocation position processed by the earlier worker, not proof of a complete committed-history prefix.

Per-order progress proves only durably coordinated local processing. It does not prove that the projection is semantically correct; replay-based validation may still detect drift.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [ADR 0020 — Per-Order Projection Progress](../../adr/0020_per_order_projection_progress_and_order_local_snapshot_tails.md) | Accepted ADR | Start here | Defines current per-order restart completeness and atomic state/progress advancement. | Current implemented authority. |
| [Checkpoint Module](../../boundary_notes/checkpoint_module.md) | Historical/generic boundary | Historical/supporting | Defines checkpoint state as operational metadata distinct from accepted and projected state. | Its scalar model is not current worker completeness. |
| [Global-Position Projection Worker Boundary](../../boundary_notes/global_position_projection_worker_boundary.md) | Historical Stage 3.5C boundary | Historical/supporting | Defines the earlier durable checkpoint cursor and state/checkpoint transaction. | Superseded for current completeness by ADR 0020. |
| [Projection Boundary](../../boundary_notes/projection_boundary.md) | Boundary note | Core | Establishes the invariant that checkpoint must not advance before successful state persistence. | Architectural rule later strengthened through PostgreSQL atomicity. |
| [Durable Read-Side Schema Baseline](../../architecture/read_side_schema_baseline.md) | Historical schema baseline | Historical/supporting | Defines the legacy checkpoint schema shape and operational timestamps. | `updated_at` is not a freshness or correctness guarantee. |
| [From In-Memory Correctness to Durable Consistency](../../reasoning_notes/from_in_memory_correctness_to_durable_consistency.md) | Reasoning note | Historical/supporting | Explains why state/progress coordination must become an explicit durable transaction. | Cross-cutting derivation, not the current implementation specification. |

## Durable Projection Persistence

Persistence makes derived state and progress survive restart. It does not transfer semantic authority from accepted history to those artifacts or move reducer logic into PostgreSQL.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Read-Side Persistence Boundary](../../boundary_notes/read_side_persistence_boundary.md) | Boundary note | Start here | Defines what Python/runtime logic owns and what PostgreSQL durably preserves. | Foundational PR1 boundary preserved by completed PR2–PR5. |
| [ADR 0020 — Per-Order Projection Progress](../../adr/0020_per_order_projection_progress_and_order_local_snapshot_tails.md) | Accepted ADR | Core | Defines `projection_order_progress`, exact-next advancement, and atomic state/progress persistence. | Current implemented progress boundary. |
| [Durable Read-Side Schema Baseline](../../architecture/read_side_schema_baseline.md) | Historical schema baseline | Historical/supporting | Defines `projection_states`, legacy `projection_checkpoints`, minimum row shape, exact money, and cursor vocabulary. | Read through ADR 0020 for current completeness. |
| [Global-Position Projection Worker Boundary](../../boundary_notes/global_position_projection_worker_boundary.md) | Historical Stage 3.5C boundary | Historical/supporting | Defines the earlier atomic persistence of projection state and scalar checkpoint progress. | Superseded for completeness by ADR 0020. |
| [Stage 3.5C — Durable Read-Side Baseline](../../implementation_notes/stage_3_5c/README.md) | Stage navigation/status | Deep dive | Qualifies the durable baseline's completion and later operational exclusions. | Complete baseline, not complete distributed production infrastructure. |
| [Stage 3.5C PR Breakdown](../../implementation_notes/stage_3_5c/pr_breakdown.md) | Implementation history | Historical/supporting | Records PR1 schema, PR2 projection store, PR3 checkpoint store, and PR4 worker implementation. | Historical delivery detail; stores do not own transaction or reducer semantics. |

## Replay and Rebuild

Replay starts from accepted history and uses the canonical reducer to derive expected projection state. Incremental processing and replay must not use different reduction rules.

A projection rebuild, when later orchestrated, must remain derived from accepted history. Stage 3.5C PR5 does not automatically rebuild, replace, or repair durable projection state, and it does not define checkpoint treatment for an actual rebuild.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Durable Replay / Rebuild Validation Boundary](../../boundary_notes/durable_replay_rebuild_validation_boundary.md) | Boundary note | Start here | Defines accepted-history replay through the canonical reducer and clearly separates comparison from future rebuild mutation. | Stage 3.5C PR5 complete at validation-only baseline level. |
| [Projection Boundary](../../boundary_notes/projection_boundary.md) | Boundary note | Core | Requires replay and incremental processing to share reducer semantics. | Stage 3 architecture boundary retained by durable implementation. |
| [Durable Read-Side Schema Baseline](../../architecture/read_side_schema_baseline.md) | Architecture | Core | Defines projection state as discardable and rebuildable from accepted history. | Does not itself provide rebuild orchestration. |
| [Projection Pipeline](../../architecture/projection_pipeline.md) | Planning-era architecture/evolution note | Deep dive | Describes shared worker/reducer replay as part of the in-memory Stage 3 foundation. | Architecture remains useful; durability chronology predates Stage 3.5C. |
| [Stage 3.5C PR Breakdown](../../implementation_notes/stage_3_5c/pr_breakdown.md) | Implementation history | Historical/supporting | Preserves broader planned PR5 reset/rebuild wording. | Older implementation-planning scope does not override the completed validation-only PR5 boundary. |

## Replay-based Validation and Drift Evidence

The completed PR5 boundary is validation-only:

```text
accepted history
-> canonical replay
-> expected projection state
-> compare with persisted projection state
-> MATCH | MISSING_PROJECTION | DRIFT | NO_ACCEPTED_HISTORY
```

Stage 3.5C PR5 does not automatically rebuild or mutate projection state, advance progress state, produce `SemanticOutcome`, implement Compass Layer 2 governance, or select recovery policy. Stage 4A later completed the Read-side and snapshot `SemanticOutcome` adapters, and Stage 4B completed their producer-specific `DecisionReceipt` mappings. Those mappings still do not mutate projections or automatically persist receipts.

A replay mismatch is evidence of derived-state drift. It does not mean accepted history is corrupt, and it does not by itself determine severity, rebuild policy, quarantine, or runtime action.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Durable Replay / Rebuild Validation Boundary](../../boundary_notes/durable_replay_rebuild_validation_boundary.md) | Boundary note | Start here | Defines the implemented comparison flow, result statuses, excluded metadata, and non-mutating scope. | Completed PR5 boundary governs current implementation interpretation. |
| [Durable Read-Side Schema Baseline](../../architecture/read_side_schema_baseline.md) | Architecture | Core | Defines persisted projection state as the comparison target while preserving accepted-history authority. | Schema constraints protect shape, not replay equivalence. |
| [Compass Layers](../../architecture/compass_layers.md) | Architecture | Deep dive | Provides the future Layer 2 context for projection/state validation. | Does not make PR5 a Layer 2 implementation. |
| [From Replay / Rebuild Validation to Layer 2 Governance](../../reasoning_notes/from_replay_rebuild_validation_to_layer2_governance.md) | Reasoning note | Historical/supporting | Explains that a correctness oracle supplies evidence while Layer 2 interprets severity and action. | Non-authoritative derivation; not a runtime-governance implementation. |
| [Stage 3.5C PR Breakdown](../../implementation_notes/stage_3_5c/pr_breakdown.md) | Implementation history | Historical/supporting | Shows the planned PR5 scope and Layer 2 non-goal in stage chronology. | Broader reset/rebuild language is historical planning and does not override the completed boundary. |

## Stage 4A / Stage 4B Read-side Mapping

Stage 4A maps bounded replay-validation, snapshot-trust, and snapshot-assisted evidence into typed `SemanticOutcome`. Stage 4B maps those producer results into `DecisionReceipt`, preserves tri-state flags as `NOT_EVALUATED`, and supports strict serialization and explicit caller-owned persistence. A mapping result is not automatic materialization, persistence, policy, fallback, rebuild, or action.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Read-side Outcome Mapping](../../implementation_notes/stage_4a/read_side_outcome_mapping.md) | Implementation boundary | Start here | Defines completed replay, snapshot-trust, and snapshot-assisted `SemanticOutcome` adapters. | Stage 4A complete. |
| [Read-side / Snapshot DecisionReceipt Mapping](../../implementation_notes/stage_4b/read_side_snapshot_decision_receipt_mapping.md) | Implementation boundary | Core | Defines completed producer-specific `DecisionReceipt` mapping and evidence checks. | Stage 4B complete; mapping performs no persistence. |
| [Stage 4B Closeout](../../implementation_notes/stage_4b/stage_4b_closeout.md) | Stage closeout | Core | Confirms completed mapping, serialization, persistence boundaries, and deferred runtime layers. | `DiagnosticTrace` / `ResolutionTrace` remain Stage 4B.1. |

## Delivery Envelope and Projection-event Deferral

**ProjectionEventRecord — Read-side delivery envelope** is a runtime/read-source representation derived from an accepted event. It carries accepted-event meaning and source-position metadata into the worker without becoming independently authoritative.

It is not a separate durable projection-event log, an independently authoritative event, or a second event-truth layer. ADR 0014 governs the current deferral of a durable `projection_events` layer.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [ADR 0014 — Defer Projection Events as a Separate Delivery Layer](../../adr/0014_defer_projection_events_as_delivery_layer.md) | ADR | Start here | Defines direct replay from `order_events` and requires any future delivery layer to remain derived and recoverable. | Accepted deferral decision; implemented through omission and boundary preservation. |
| [Global-Position Projection Worker Boundary](../../boundary_notes/global_position_projection_worker_boundary.md) | Boundary note | Core | Defines the accepted-event source and global-position worker input. | Stage 3.5C PR4 complete. |
| [Stage 3.5C PR Breakdown](../../implementation_notes/stage_3_5c/pr_breakdown.md) | Implementation history | Historical/supporting | Records introduction of `ProjectionEventRecord` as the envelope between storage metadata and domain event meaning. | The envelope is not the deferred durable delivery layer. |
| [Projection Module](../../boundary_notes/projection_module.md) | Boundary note | Deep dive | Reinforces minimum dependency on accepted-event semantics needed for derivation. | Projection should avoid admission-only proof internals. |

## Implementation History and Design Evolution

These documents explain how the Read-side evolved from replay helpers to an in-memory runtime and then to the durable Stage 3.5C baseline. They preserve chronology and rationale; they do not override later completed boundaries.

| Document | Document role | Reading level | Contribution to this topic | Status or chronology note |
|---|---|---|---|---|
| [Stage 3.5C — Durable Read-Side Baseline](../../implementation_notes/stage_3_5c/README.md) | Stage navigation/status | Start here | Gives the current completion boundary and points to detailed implementation history. | Complete at durable Read-side baseline level. |
| [Stage 3.5C PR Breakdown](../../implementation_notes/stage_3_5c/pr_breakdown.md) | Implementation history | Historical/supporting | Preserves PR0–PR6 scope, sequence, tests, and non-goals. | Planning-era PR5 breadth does not override the completed validation-only boundary. |
| [Projection Pipeline](../../architecture/projection_pipeline.md) | Planning-era architecture/evolution note | Historical/supporting | Preserves the Stage 3 transition from replay helper to in-memory reducer/worker runtime. | Its persistent-runtime maturity language predates Stage 3.5C completion. |
| [From Projection Concerns to Event Truth](../../reasoning_notes/from_projection_concerns_to_event_truth.md) | Reasoning note | Historical/supporting | Records why accepted-history correctness became architecturally prior to projection correctness. | Non-authoritative derivation history. |
| [From In-Memory Correctness to Durable Consistency](../../reasoning_notes/from_in_memory_correctness_to_durable_consistency.md) | Reasoning note | Historical/supporting | Records why persistence requires explicit cross-time atomicity and recovery semantics. | Cross-cutting derivation history. |
| [From Per-Order Global Position to Global Source Boundary](../../postmortems/from_per_order_global_position_to_global_source_boundary.md) | Postmortem | Historical/supporting | Records a later snapshot-lineage correction that reinforces global versus local scope. | Stage 3.5D history, not the current worker specification. |
| [From Replay / Rebuild Validation to Layer 2 Governance](../../reasoning_notes/from_replay_rebuild_validation_to_layer2_governance.md) | Reasoning note | Historical/supporting | Preserves the distinction between PR5 comparison evidence and future semantic governance. | Does not establish Layer 2 implementation status. |

## Open Questions and Important Reading Notes

- Actual durable projection-rebuild orchestration and progress treatment are not yet defined by the Stage 3.5C PR5 boundary.
- Multi-worker coordination, a global committed watermark, and capacity control remain deferred.
- Older Stage 3 and PR-planning documents retain historical maturity and scope language.
- Replay-validation evidence is intentionally separate from later policy, strategy, retry, and action governance. Stage 4A/4B mappings preserve evidence without executing those layers.
