# PostgreSQL Read-Side Result to DecisionReceipt: End-to-End Flow

This guide follows the current Stage 3.5C projection and replay-validation code, Stage 3.5D snapshot paths, Stage 4A semantic adapters, and the unmerged Stage 4B PR5 receipt adapters. It is a reader guide, not a new source of authority.

Primary sources: `src/pipeline/projection/postgres_worker.py`, `src/pipeline/projection/replay_validator.py`, `src/pipeline/projection/projection_snapshot_replay_validator.py`, `src/pipeline/projection/projection_snapshot_assisted_state_resolver.py`, `src/compass/runtime/read_side_outcome_mapping.py`, and `src/compass/runtime/read_side_decision_receipt_mapping.py`.

## Reading guide

For mapping ownership after a typed result exists, read [Stage 4A to Stage 4B: Read-Side Mapping Flow](stage_4a_to_stage_4b_read_side_mapping_flow.md). For quick type, enum, and confusion-pair lookup, read the [Read-Side Mapping Type and Vocabulary Reference](read_side_mapping_type_and_vocabulary_reference.md). The Traditional Chinese version is [PostgreSQL Read-Side Result 到 DecisionReceipt：端到端流程](read_side_result_to_decision_receipt_end_to_end.zh.md).

## 1. Executive overview

There are four distinct paths. Path A produces worker-execution evidence and currently stops before Stage 4A/PR5. Paths B, C, and D produce the three typed result families mapped by PR5.

```text
Path A — projection execution
accepted event
→ PostgresProjectionWorker
→ projection_states + projection_order_progress
→ PostgresProjectionWorkerResult
↛ Stage 4A / PR5 mapping

Path B — durable projection consistency
accepted history ──canonical replay──┐
                                     ├→ DurableReplayValidator
projection_states ──────────────────┘
→ ReplayValidationResult
→ Stage 4A SemanticOutcome
→ PR5 DecisionReceipt

Path C — snapshot-path comparison
accepted history ──full replay──────────────┐
snapshot + contiguous same-order tail ─────┤
                                            └→ ProjectionSnapshotReplayValidator
→ ProjectionSnapshotReplayValidationResult
→ Stage 4A SemanticOutcome
→ PR5 DecisionReceipt

Path D — snapshot-assisted resolution
externally supplied trusted_snapshot_id
+ compatible snapshot
+ contiguous same-order tail
→ ProjectionSnapshotAssistedStateResolver
→ ProjectionSnapshotAssistedResolutionResult
→ Stage 4A SemanticOutcome
→ PR5 DecisionReceipt
```

The responsibility boundaries are:

```text
projection execution
≠ projection correctness validation
≠ snapshot trust validation
≠ snapshot-assisted resolution
≠ trust continuation
≠ runtime action
```

Accepted history remains business authority. Projection state, per-order progress, snapshots, `SemanticOutcome`, and `DecisionReceipt` are evidence with narrower meanings.

## 2. Stage 3.5C projection execution

### 2.1 Projection identity and eligible-event discovery

The current fixed production definition is `order_state_projection`, epoch `1`. `PostgresProjectionWorker` does not accept arbitrary projection identity because `projection_states` remains keyed only by `order_id`. Sources: `src/pipeline/projection/order_projection_definition.py::ORDER_STATE_PROJECTION_NAME`, `ORDER_STATE_PROJECTION_EPOCH`, and `require_current_order_state_projection`.

Durable progress is keyed by:

```text
(projection_name, projection_epoch, order_id)
```

`ProjectionOrderProgress` records `last_sequence`, `last_event_id`, and `last_global_position`. The accepted event is eligible only when its order-local sequence is exactly `COALESCE(last_sequence, 0) + 1`. A missing progress row means local sequence zero. `global_position` only sorts currently eligible work deterministically and preserves lineage; it is not an order-local correctness cursor or a complete committed-history frontier. Sources: `src/storage/projection_progress_store.py::ProjectionOrderProgress`, `src/storage/postgres_projection_eligible_event_source.py::PostgresProjectionEligibleEventSource.load_eligible`.

The commit-inversion regression is covered by `tests/integration/pipeline/projection/test_postgres_projection_worker_commit_visibility.py::test_worker_processes_late_committing_lower_global_position_per_order`. A lower allocated position that commits later remains eligible for its own order. A rolled-back allocation creates no accepted row and no progress obligation.

### 2.2 Canonical reducer and transaction coupling

`reduce_order_event(current_state, event)` is a pure deterministic reducer. It requires the same `order_id` and `event.sequence == current_state.version + 1`, then returns a new frozen `OrderState`. `build_empty_projection_state(order_id)` starts at version zero. Sources: `src/pipeline/projection/reducer.py::build_empty_projection_state`, `reduce_order_event`; `src/core/order/state.py::OrderState`.

`PostgresProjectionWorker.process_next()` requires an idle connection, owns one top-level transaction, and requires the eligible source, state store, and progress store to share that exact connection. Within that transaction it loads one eligible event, loads/builds state, reduces the event, writes `projection_states`, and advances per-order progress. A returned `applied` result means those writes completed through the worker-owned transaction. The rollback coupling is tested by `tests/integration/pipeline/projection/test_postgres_projection_worker.py::test_projection_state_and_progress_rollback_together_on_progress_failure`.

### 2.3 Worker result branches

`PostgresProjectionWorkerResult` is a frozen, human-readable integration-test/debugging result with these fields:

```text
worker_name
action
global_position
order_id
event_sequence
projected_version
reason
```

| `action` | Present lineage | Exact current meaning | Does not prove |
|---|---|---|---|
| `applied` | position, order, event sequence, projected version | One currently visible exact-next accepted event was reduced and state plus per-order progress completed in the worker transaction. | Equality with full replay, global catch-up, reducer correctness against intended domain meaning, continuing trust, snapshot trust, or runtime authorization. |
| `no_event` | optional lineage fields are absent | No currently visible exact-next event was eligible during this invocation. | No later commit, complete accepted-history processing, projection validity, or global catch-up. |

PR5 deliberately does not map `PostgresProjectionWorkerResult`. Worker execution reports that one execution step completed; it is not the same evidence as a full replay comparison.

## 3. Durable replay validation

### 3.1 Observation flow

`DurableReplayValidator.validate_order(order_id)` uses one shared connection and requires it to be idle. It owns one top-level `REPEATABLE READ READ ONLY` transaction, loads accepted history, replays it through the current canonical reducer, loads persisted `projection_states`, and returns `ReplayValidationResult`. Sources: `src/pipeline/projection/replay_validator.py::DurableReplayValidator.validate_order`, `_validate_order`.

The result dataclass does not itself attest how it was constructed. The PostgreSQL orchestration proves the observation boundary only when that concrete validator method produced it.

### 3.2 Expected state versus persisted state

`expected_state` is the `OrderState` derived from accepted history through the current canonical reducer in this validation invocation. `persisted_state` is the independently loaded row from `projection_states`. Neither field is accepted history itself.

```text
accepted history → build empty state → canonical reducer → expected_state
projection_states row                              → persisted_state
```

`MISSING_PROJECTION` therefore requires `expected_state` present and `persisted_state` absent: accepted history was sufficient to reconstruct a projection, but the durable projection row was missing.

`NO_ACCEPTED_HISTORY` is coarser. The validator sets `expected_state=None`, then still loads persisted projection state. `persisted_state` may therefore be present or absent. When it is present, the current vocabulary records “no accepted history” but does not separately name “derived state without authority support.” That is a current vocabulary limitation and a deferred hardening concern, not a reason to invent a new status in this guide.

### 3.3 Legal shape matrix

| Status | `expected_state` | `persisted_state` | Additional relation |
|---|---:|---:|---|
| `MATCH` | present | present | states equal |
| `MISSING_PROJECTION` | present | absent | accepted history exists |
| `DRIFT` | present | present | states unequal |
| `NO_ACCEPTED_HISTORY` | absent | present or absent | no equality assertion |

PR5 `_validate_replay_result_shape` rejects contradictory synthetic combinations before Stage 4A mapping. Blank `order_id` rejection is receipt-admission validation; it does not claim the generic dataclass cannot be constructed with a blank value.

### 3.4 Common-mode limitation

Replay validation proves consistency with the current canonical reducer. Live projection and full replay call the same deterministic `reduce_order_event`. If that reducer implements the intended domain contract incorrectly in the same way on both paths, they may still `MATCH`. Consequently:

```text
ReplayValidationResult.MATCH
= current persisted projection equals current canonical replay
≠ independent proof that the reducer matches intended domain meaning
```

## 4. Snapshot replay validation

### 4.1 Two reconstruction paths

`ProjectionSnapshotReplayValidator.validate_order(order_id)` builds two paths in one invocation:

```text
authority path:
accepted history → empty state → canonical full replay → authority_state

snapshot-assisted path:
latest snapshot → boundary validation → hydrate state
→ same-order contiguous tail replay → snapshot_assisted_state
```

The final comparison is `snapshot_assisted_state` versus `authority_state`. It is not a comparison with persisted `projection_states`.

For PostgreSQL, `PostgresProjectionSnapshotReplayValidator` constructs snapshot, accepted-history, and tail readers on the same connection and runs the generic validator inside one top-level `REPEATABLE READ READ ONLY` transaction. The generic validator and `ProjectionSnapshotReplayValidationResult` do not themselves attest that orchestration. Source: `src/pipeline/projection/postgres_snapshot_observation.py::PostgresProjectionSnapshotReplayValidator`.

### 4.2 Snapshot boundary and tail correctness

The validator checks requested order identity, positive snapshot source coordinates, state/source-sequence alignment, supported state status, and that the snapshot sequence is not ahead of accepted history. It hydrates the snapshot, then loads tail records using:

```text
same order_id
+ event.sequence > snapshot.source_event_sequence
+ ORDER BY event.sequence ASC
```

Every returned record must be the exact next `source_event_sequence`. A different-order record or a non-contiguous local sequence produces `TAIL_EVENT_SOURCE_CONTRACT_VIOLATION`.

`source_global_position` is retained in the result only as loaded snapshot lineage. The result does not expose `source_event_id`, `source_event_sequence`, `projection_name`, or `projection_epoch`, and PR5 does not recover them from snapshot/state objects or storage.

### 4.3 Legal shape matrix

| Status | Loaded lineage (`snapshot_id` + position) | Snapshot-assisted state | Authority state | Additional relation |
|---|---:|---:|---:|---|
| `MATCH` | required | present | present | states equal |
| `MISSING_SNAPSHOT` | absent | absent | present | accepted history exists and was replayed |
| `INVALID_SNAPSHOT_BOUNDARY` | required | absent | present | boundary or hydration failed |
| `TAIL_EVENT_SOURCE_CONTRACT_VIOLATION` | required | present | present | equality is allowed |
| `SNAPSHOT_ASSISTED_DRIFT` | required | present | present | inequality is not required when reducer application failed before divergence |
| `NO_ACCEPTED_HISTORY_FOR_ORDER` | both present or both absent | absent | absent | snapshot may have been loaded before history absence was classified |

> **Why can `SNAPSHOT_ASSISTED_DRIFT` preserve equal states?**
>
> The current producer status is broader than a final unequal-state comparison. It may preserve both state objects when the snapshot-assisted reconstruction path fails before a conclusive final equality comparison. PR5 therefore validates the producer-supported shape rather than inferring inequality from the word `DRIFT`. This is a current vocabulary characteristic and may warrant later review; the reader guide does not redefine the production status.

`MISSING_SNAPSHOT` requires `authority_state` because the producer reaches that status only after non-empty accepted history has been replayed. If accepted history is absent, the producer returns `NO_ACCEPTED_HISTORY_FOR_ORDER`, whether or not a snapshot was loaded.

When accepted history is absent but loaded snapshot lineage is present, the snapshot may be an orphan or otherwise unsupported derived artifact without current authority backing. The current status records the no-history condition and preserves optional lineage, but it does not classify that integrity concern separately.

`MATCH` proves only equality for this producer observation. It does not prove permanent snapshot trust, payload-integrity qualification beyond implemented checks, complete future history, business authority, or runtime authorization.

## 5. Snapshot-assisted resolution

### 5.1 Resolution flow

`ProjectionSnapshotAssistedStateResolver.resolve_order(order_id, trusted_snapshot_id=...)` consumes an identifier already qualified by the caller. The resolver does not establish that trust. It loads that exact snapshot, checks order/schema/reducer/state compatibility, hydrates it, loads the same-order exact-next tail, and applies the canonical reducer.

```text
trusted_snapshot_id
→ exact snapshot lookup
→ compatibility checks
→ snapshot hydration
→ contiguous same-order tail after source_event_sequence
→ resolved_state
```

The PostgreSQL wrapper uses the same connection and one top-level `REPEATABLE READ READ ONLY` transaction for snapshot and tail reads. The generic result dataclass does not attest that boundary. Source: `src/pipeline/projection/postgres_snapshot_observation.py::PostgresProjectionSnapshotAssistedStateResolver`.

### 5.2 Legal shape matrix

| Status | `snapshot_id` meaning | `source_global_position` | `resolved_state` |
|---|---|---:|---:|
| `RESOLVED_FROM_SNAPSHOT` | loaded snapshot | present | present |
| `MISSING_SNAPSHOT` | requested reference, not loaded lineage | absent | absent |
| `INVALID_SNAPSHOT_PRECONDITION` | absent; no trusted ID supplied | absent | absent |
| `INVALID_SNAPSHOT_COMPATIBILITY` | loaded snapshot | present | absent |
| `TAIL_EVENT_SOURCE_CONTRACT_VIOLATION` | loaded snapshot | present | absent |
| `TAIL_REPLAY_FAILED` | loaded snapshot | present | absent |

`RESOLVED_FROM_SNAPSHOT` proves successful reconstruction through the selected snapshot and contiguous local tail under implemented checks. It does not independently replay accepted history, expose `authority_state`, prove accepted-history equivalence, or authorize use, fallback, retry, rebuild, or policy.

## 6. Stage 4A mapping

Stage 4A turns each technical result into a typed semantic tuple. It does not build receipt identity, decide policy, or persist anything.

| Typed result | Stage 4A function | Boundary |
|---|---|---|
| `ReplayValidationResult` | `map_replay_validation_result_to_semantic_outcome` | `LAYER_2_READ_SIDE` |
| `ProjectionSnapshotReplayValidationResult` | `map_projection_snapshot_replay_validation_result_to_semantic_outcome` | `SNAPSHOT_TRUST` |
| `ProjectionSnapshotAssistedResolutionResult` | `map_projection_snapshot_assisted_resolution_result_to_semantic_outcome` | `SNAPSHOT_TRUST` |

The shared technical mapping selects:

```text
ok
category
semantic_code
severity
risk_level
reversibility
```

The producer adapter supplies the boundary and reason. Technical status is evidence; the semantic tuple classifies its meaning. Neither is runtime action.

## 7. Stage 4B PR5 mapping

Each PR5 wrapper follows the same composition while remaining producer-specific:

```text
typed producer result
→ validate producer shape
→ call its Stage 4A mapper
→ select producer evidence source, subject, correlation, identity source
→ build compact summary directly from typed result
→ use DecisionReceiptFlags()
→ map_semantic_outcome_to_decision_receipt
→ DecisionReceipt validation
```

| Producer result | Evidence source | Correlation | Summary keys |
|---|---|---|---|
| `ReplayValidationResult` | `READ_SIDE_PATH` | `order_id`, `READ_SIDE_OBSERVATION` | `technical_status`, `expected_state_present`, `persisted_state_present` |
| `ProjectionSnapshotReplayValidationResult` | `SNAPSHOT_TRUST_PATH` | order plus optional loaded snapshot lineage | `technical_status`, `snapshot_artifact_present`, `snapshot_assisted_state_present`, `authority_state_present` |
| `ProjectionSnapshotAssistedResolutionResult` | `SNAPSHOT_ASSISTED_PATH` | order plus requested reference or loaded lineage | `technical_status`, `snapshot_artifact_present`, `resolved_state_present` |

The generic mapper copies the complete Stage 4A semantic tuple one-to-one. It deliberately does not inspect `SemanticOutcome.context` or `.evidence`. PR5 reconstructs compact evidence from the typed result so caller-overridable Stage 4A mappings cannot become canonical receipt evidence.

Every PR5 adapter uses `DecisionReceiptFlags()`. Thus `fallback_required`, `rebuild_required`, `operator_review_required`, and `retry_candidate` all remain `NOT_EVALUATED`. `MATCH` does not complete them as `FALSE`; `MISSING_PROJECTION` and semantic `REQUIRES_REBUILD` do not complete `rebuild_required` as `TRUE`. Source: ADR 0018.

All rows use default actor/cost, `metadata={}`, and `admission_evidence=None`. PR5 leaves request, candidate-event, and accepted-event identities absent.

## 8. End-to-end status matrix

`NE×4` means all four flags are `NOT_EVALUATED`. Semantic notation is `ok / boundary / category / code / severity / risk / reversibility`.

| Result / status | Required state/lineage shape | Evidence source; subject; identity | Stage 4A semantic tuple | Compact summary meaning | Proves / does not prove |
|---|---|---|---|---|---|
| Replay `MATCH` | expected and persisted present/equal | `READ_SIDE_PATH`; `PROJECTION(order)`; `READ_SIDE_OBSERVATION`; `NE×4` | `T / LAYER_2_READ_SIDE / VALID / SEMANTICALLY_VALID / INFO / LOW / REVERSIBLE` | both state-presence flags true | Point-in-time canonical-replay equality; not reducer/domain correctness or continued trust. |
| Replay `MISSING_PROJECTION` | expected present; persisted absent | same projection ownership; `NE×4` | `F / LAYER_2_READ_SIDE / REBUILD_REQUIRED / REQUIRES_REBUILD / WARNING / MEDIUM / REBUILDABLE` | expected true; persisted false | Authority replay state exists and projection row is missing; not rebuild authorization. |
| Replay `DRIFT` | both present/unequal | same projection ownership; `NE×4` | `F / LAYER_2_READ_SIDE / DRIFT / DRIFT_DETECTED / ERROR / HIGH / REBUILDABLE` | both presence flags true | States differ in this observation; not root cause or remediation. |
| Replay `NO_ACCEPTED_HISTORY` | expected absent; persisted optional | `READ_SIDE_PATH`; `ORDER(order)`; `READ_SIDE_OBSERVATION`; `NE×4` | `F / LAYER_2_READ_SIDE / UNRESOLVED / RUNTIME_UNRESOLVED / WARNING / UNKNOWN / UNKNOWN` | expected false; persisted reflects result | No authority history was observed; does not separately classify unsupported persisted state. |
| Snapshot validation `MATCH` | loaded lineage; both states present/equal | `SNAPSHOT_TRUST_PATH`; `SNAPSHOT(id)`; `SNAPSHOT_LINEAGE`; `NE×4` | `T / SNAPSHOT_TRUST / VALID / SEMANTICALLY_VALID / INFO / LOW / REVERSIBLE` | artifact and both states present | Two implemented paths matched now; not permanent trust or runtime authorization. |
| Snapshot validation `MISSING_SNAPSHOT` | no lineage; assisted absent; authority present | `SNAPSHOT_TRUST_PATH`; `SNAPSHOT(None)`; `READ_SIDE_OBSERVATION`; `NE×4` | `F / SNAPSHOT_TRUST / FALLBACK_REQUIRED / FAST_PATH_UNAVAILABLE / WARNING / MEDIUM / REVERSIBLE` | artifact false; authority true | History could produce authority state but no snapshot loaded; not fallback execution. |
| Snapshot validation `INVALID_SNAPSHOT_BOUNDARY` | loaded lineage; assisted absent; authority present | `SNAPSHOT_TRUST_PATH`; `SNAPSHOT(id)`; `SNAPSHOT_LINEAGE`; `NE×4` | `F / SNAPSHOT_TRUST / UNTRUSTED / DERIVED_STATE_UNTRUSTED / ERROR / HIGH / REBUILDABLE` | artifact true; only authority state present | Implemented boundary/hydration failed; not rebuild authorization. |
| Snapshot validation `TAIL_EVENT_SOURCE_CONTRACT_VIOLATION` | lineage and both states present | `SNAPSHOT_TRUST_PATH`; `RUNTIME(None)`; `SNAPSHOT_LINEAGE`; `NE×4` | `F / SNAPSHOT_TRUST / UNRESOLVED / RUNTIME_UNRESOLVED / ERROR / HIGH / UNKNOWN` | artifact and both states present | Different-order or non-contiguous tail record; not snapshot root cause. |
| Snapshot validation `SNAPSHOT_ASSISTED_DRIFT` | lineage and both states present | `SNAPSHOT_TRUST_PATH`; `PROJECTION(order)`; `SNAPSHOT_LINEAGE`; `NE×4` | `F / SNAPSHOT_TRUST / DRIFT / DRIFT_DETECTED / ERROR / HIGH / REBUILDABLE` | artifact and both states present | Comparison/reducer path drift evidence; not isolated cause or action. |
| Snapshot validation `NO_ACCEPTED_HISTORY_FOR_ORDER` | no states; lineage paired optional | `SNAPSHOT_TRUST_PATH`; `ORDER(order)`; lineage if loaded, otherwise observation; `NE×4` | `F / SNAPSHOT_TRUST / UNRESOLVED / RUNTIME_UNRESOLVED / WARNING / UNKNOWN / UNKNOWN` | artifact reflects optional loaded snapshot; states false | No authority history observed; not `MISSING_SNAPSHOT`. |
| Resolution `RESOLVED_FROM_SNAPSHOT` | loaded lineage; resolved present | `SNAPSHOT_ASSISTED_PATH`; `PROJECTION(order)`; `SNAPSHOT_LINEAGE`; `NE×4` | `T / SNAPSHOT_TRUST / VALID / SEMANTICALLY_VALID / INFO / LOW / REVERSIBLE` | artifact/resolved true | Selected snapshot path produced state; not authority equality or use authorization. |
| Resolution `MISSING_SNAPSHOT` | requested ID; no position/state | `SNAPSHOT_ASSISTED_PATH`; `SNAPSHOT(requested id)`; `READ_SIDE_OBSERVATION`; `NE×4` | `F / SNAPSHOT_TRUST / FALLBACK_REQUIRED / FAST_PATH_UNAVAILABLE / WARNING / MEDIUM / REVERSIBLE` | artifact/resolved false | Requested lookup failed; requested ID is not loaded lineage. |
| Resolution `INVALID_SNAPSHOT_PRECONDITION` | no ID, lineage, or state | `SNAPSHOT_ASSISTED_PATH`; `RUNTIME(None)`; `READ_SIDE_OBSERVATION`; `NE×4` | `F / SNAPSHOT_TRUST / UNTRUSTED / DERIVED_STATE_UNTRUSTED / ERROR / HIGH / REBUILDABLE` | artifact/resolved false | Required trusted ID absent; not snapshot evidence. |
| Resolution `INVALID_SNAPSHOT_COMPATIBILITY` | loaded lineage; no resolved state | `SNAPSHOT_ASSISTED_PATH`; `SNAPSHOT(id)`; `SNAPSHOT_LINEAGE`; `NE×4` | `F / SNAPSHOT_TRUST / UNTRUSTED / DERIVED_STATE_UNTRUSTED / ERROR / HIGH / REBUILDABLE` | artifact true; resolved false | Loaded snapshot failed compatibility; not action authorization. |
| Resolution `TAIL_EVENT_SOURCE_CONTRACT_VIOLATION` | loaded lineage; no resolved state | `SNAPSHOT_ASSISTED_PATH`; `RUNTIME(None)`; `SNAPSHOT_LINEAGE`; `NE×4` | `F / SNAPSHOT_TRUST / UNRESOLVED / RUNTIME_UNRESOLVED / ERROR / HIGH / UNKNOWN` | artifact true; resolved false | Tail source broke order-local contract; not snapshot root cause. |
| Resolution `TAIL_REPLAY_FAILED` | loaded lineage; no resolved state | `SNAPSHOT_ASSISTED_PATH`; `RUNTIME(None)`; `SNAPSHOT_LINEAGE`; `NE×4` | `F / SNAPSHOT_TRUST / FALLBACK_REQUIRED / FAST_PATH_UNAVAILABLE / WARNING / MEDIUM / REVERSIBLE` | artifact true; resolved false | Reducer application failed; not fallback execution or retry authorization. |

## 9. Complete examples

### 9.1 Replay `MATCH`

Accepted history replays to state version 2; `projection_states` also loads the same state. `ReplayValidationResult(MATCH, expected=state, persisted=state)` passes shape validation. Stage 4A produces `VALID / SEMANTICALLY_VALID` at `LAYER_2_READ_SIDE`. PR5 selects `READ_SIDE_PATH`, `PROJECTION(order_id)`, order-only `READ_SIDE_OBSERVATION`, three presence-summary keys, and all-neutral flags. The receipt proves only this comparison boundary.

### 9.2 Replay `MISSING_PROJECTION`

Accepted history replays successfully, but the store returns no projection row. Stage 4A classifies `REBUILD_REQUIRED / REQUIRES_REBUILD`; PR5 still leaves `rebuild_required=NOT_EVALUATED`. Semantic classification describes the condition. A completed governance proposition would require a separately authorized evaluator.

### 9.3 `NO_ACCEPTED_HISTORY` with persisted state

The validator finds no accepted events and still loads a persisted state. The legal result is `expected_state=None`, `persisted_state=state`. PR5 uses an `ORDER` subject and records only the two presence booleans. The condition may represent projection state without authority support, but current production vocabulary does not distinguish it from the case where both are absent.

### 9.4 Snapshot validation `MISSING_SNAPSHOT`

Non-empty accepted history produces `authority_state`; latest snapshot lookup returns none. The result has no snapshot lineage and no assisted state. Stage 4A maps fast-path unavailability. PR5 uses `SNAPSHOT(None)`, `READ_SIDE_OBSERVATION`, and `snapshot_artifact_present=false`; it does not execute fallback.

### 9.5 Snapshot validation `MATCH`

The validator independently reconstructs authority state and snapshot-assisted state in one invocation and observes equality. PR5 preserves loaded `snapshot_id` and `source_global_position` as `SNAPSHOT_LINEAGE`, with subject `SNAPSHOT(id)`. The receipt does not turn point-in-time equality into permanent trust or authorization.

### 9.6 Resolution `RESOLVED_FROM_SNAPSHOT`

A caller supplies `trusted_snapshot_id`; the resolver loads a compatible snapshot, applies a contiguous same-order tail, and returns `resolved_state`. PR5 uses `SNAPSHOT_ASSISTED_PATH`, `PROJECTION(order_id)`, and loaded lineage. No accepted-history replay occurred in this path, so success does not prove authority equivalence.

### 9.7 Tail-source or tail-replay failure

A different-order/non-contiguous tail record produces `TAIL_EVENT_SOURCE_CONTRACT_VIOLATION`; a reducer exception in the assisted resolver produces `TAIL_REPLAY_FAILED`. PR5 uses conservative `RUNTIME` subjects while retaining loaded lineage in correlation. It does not label the snapshot as proven root cause or select fallback/retry.

## 10. Boundaries and deferred work

Current source provides composable worker, validator, resolver, semantic-mapper, and receipt-mapper primitives. It does not provide:

- a production projection runner or validation scheduler;
- automatic validator invocation or post-worker validation hook;
- `PostgresProjectionWorkerResult` Stage 4A/PR5 mapping;
- continuous projection or snapshot trust;
- a trust lease, automatic expiry, invalidation, or revalidation;
- Stage 4B.3 trust continuation (the roadmap section is provisional only);
- runtime action, policy, strategy, fallback, rebuild, quarantine, or retry;
- diagnostic-trace persistence;
- PR5 receipt serialization or persistence.

`MATCH` is point-in-time evidence for one observation. A later event does not make that historical observation false, but the earlier receipt alone does not prove the newest projection state.

Future vocabulary hardening may distinguish `NO_ACCEPTED_HISTORY` with persisted projection state from the case where both history and projection are absent. The snapshot path has a parallel concern: `NO_ACCEPTED_HISTORY_FOR_ORDER` may retain loaded snapshot lineage, which can represent a snapshot artifact without current authority support. This guide records both concerns without defining new production statuses.

The existing `src/pipeline/projection/README.md` contains stale lines claiming durable replay validation and structured Layer 2 `SemanticOutcome` do not exist. Current source takes precedence; this guide does not modify that README.

