# Read-Side Mapping Type and Vocabulary Reference

This is a quick source-grounded lookup for the Stage 3.5C projection and replay path, Stage 3.5D snapshot paths, Stage 4A semantic mapping, and Stage 4B PR5 receipt mapping. It records current meanings; it does not create new authority.

## Reading guide

For the full lifecycle, read [PostgreSQL Read-Side Result to DecisionReceipt: End-to-End Flow](read_side_result_to_decision_receipt_end_to_end.md). For mapper ownership, read [Stage 4A to Stage 4B: Read-Side Mapping Flow](stage_4a_to_stage_4b_read_side_mapping_flow.md). The Traditional Chinese version is [Read-Side Mapping Type 與 Vocabulary Reference](read_side_mapping_type_and_vocabulary_reference.zh.md).

## 1. Type dependency diagram

```text
OrderEvent ───────────────────────────────────────────────────────────┐
    │ accepted-history member only when stored in order_events       │
    ▼                                                                │
canonical reducer + OrderState                                       │
    │                                                                │
    ├→ PostgresProjectionWorker                                      │
    │    ├→ projection_states                                        │
    │    ├→ ProjectionOrderProgress                                  │
    │    └→ PostgresProjectionWorkerResult (execution only)          │
    │                                                                │
    ├→ DurableReplayValidator                                        │
    │    └→ ReplayValidationResult                                   │
    │                                                                │
ProjectionSnapshot + accepted history + order-local tail             │
    ├→ ProjectionSnapshotReplayValidator                             │
    │    └→ ProjectionSnapshotReplayValidationResult                 │
    └→ ProjectionSnapshotAssistedStateResolver                       │
         └→ ProjectionSnapshotAssistedResolutionResult               │
                                                                     │
three mapped result families ─→ Stage 4A SemanticOutcome             │
                              ─→ PR5 supporting receipt types         │
                              ─→ PR3 generic mapper                   │
                              ─→ DecisionReceipt                     │
```

## 2. Class and interface reference

| Type / symbol | Definition | Producer | Consumer | Authority meaning | Do not confuse with |
|---|---|---|---|---|---|
| `OrderEvent` | `src/core/order/events.py::OrderEvent` | aggregate/write-side materialization; PostgreSQL hydration | reducer, history readers | Event-shaped data; accepted authority only when present in `order_events` | Candidate construction alone or projection state |
| `OrderState` | `src/core/order/state.py::OrderState` | reducer, snapshot hydration, state store | worker, validators, resolver | Immutable derived read-side value | Mutable aggregate or accepted history |
| `ProjectionOrderProgress` | `src/storage/projection_progress_store.py::ProjectionOrderProgress` | worker | eligible source, progress store | Last durably applied local event for projection/epoch/order | Global checkpoint, business authority, trust checkpoint |
| `PostgresProjectionWorkerResult` | `src/pipeline/projection/postgres_worker.py::PostgresProjectionWorkerResult` | `PostgresProjectionWorker.process_next` | tests/debugging | One invocation’s `applied` or `no_event` execution evidence | Replay equality, global catch-up, PR5 input |
| `ReplayValidationResult` | `src/pipeline/projection/replay_validator.py::ReplayValidationResult` | `DurableReplayValidator` | Stage 4A replay mapper; PR5 replay wrapper | Expected canonical replay versus persisted projection observation | Worker execution or intended-domain correctness proof |
| `ProjectionSnapshot` | `src/storage/postgres_projection_snapshot_store.py::ProjectionSnapshot` | snapshot writer/store | validator/resolver | Immutable derived compression artifact with event lineage and compatibility data | Accepted history or permanent trust |
| `ProjectionSnapshotStoreProtocol` | `src/pipeline/projection/projection_snapshot_replay_validator.py::ProjectionSnapshotStoreProtocol` | implementation supplies latest snapshot | generic validator | Storage-agnostic latest-snapshot lookup | PostgreSQL transaction attestation |
| `ProjectionSnapshotLookupProtocol` | `src/pipeline/projection/projection_snapshot_assisted_state_resolver.py::ProjectionSnapshotLookupProtocol` | implementation supplies exact snapshot | generic resolver | Lookup by caller-supplied snapshot ID | Trust qualification |
| `ProjectionTailEventSourceProtocol` | both snapshot producer modules | tail source | validator/resolver | Same-order records after a local sequence | Global-position completeness cursor |
| `ProjectionSnapshotReplayValidationResult` | `src/pipeline/projection/projection_snapshot_replay_validator.py` | snapshot replay validator | Stage 4A snapshot mapper; PR5 trust wrapper | Snapshot-assisted state versus independent accepted-history replay | Persisted `projection_states` validation or permanent trust |
| `ProjectionSnapshotAssistedResolutionResult` | `src/pipeline/projection/projection_snapshot_assisted_state_resolver.py` | assisted resolver | Stage 4A resolver mapper; PR5 assisted wrapper | Result of selected snapshot plus compatible contiguous local tail | Authority comparison or runtime authorization |
| `SemanticOutcome` | `src/compass/runtime/semantic_outcome.py::SemanticOutcome` | Stage 4A adapters | PR3 generic mapper and later consumers | Typed semantic classification for one boundary | Technical result, policy decision, receipt persistence |
| `DecisionReceiptSubject` | `src/compass/runtime/decision_receipt.py::DecisionReceiptSubject` | PR5 selection | `DecisionReceipt` | What the receipt is primarily about | Root cause or correlation provenance |
| `DecisionReceiptCorrelation` | `src/compass/runtime/decision_receipt.py::DecisionReceiptCorrelation` | PR5 selection | `DecisionReceipt` | Queryable order/snapshot lineage with one primary identity source | Accepted authority or field-level provenance |
| `DecisionReceiptFlags` | `src/compass/runtime/decision_receipt.py::DecisionReceiptFlags` | PR5 supplies defaults | later authorized evaluator/consumer | State of four governance propositions | Technical status or implicit booleans |
| `DecisionReceiptActor` | `src/compass/runtime/decision_receipt.py::DecisionReceiptActor` | default in PR5 | receipt consumers | Optional receipt-safe actor evidence | Database permissions |
| `DecisionReceiptCostSummary` | `src/compass/runtime/decision_receipt.py::DecisionReceiptCostSummary` | default in PR5 | receipt consumers | Optional compact non-negative cost evidence | Detailed trace or benchmark system |
| `DecisionReceipt` | `src/compass/runtime/decision_receipt.py::DecisionReceipt` | PR3 generic mapper | future consumers | Frozen semantic tuple plus explicit compact governance evidence | Runtime action, serialization, persistence, or trust lease |

The current tree has no separate generic `projection_snapshot_store.py` module; storage-agnostic snapshot protocols live in the validator/resolver modules, while the concrete dataclass/store live in `src/storage/postgres_projection_snapshot_store.py`.

## 3. Enum and vocabulary reference

### 3.1 Projection execution action representation

`PostgresProjectionWorkerResult.action` is currently a string, not an enum. Real worker branches return:

| Value | Meaning |
|---|---|
| `"applied"` | One currently visible exact-next same-order event was applied and state/progress completed in the worker transaction. |
| `"no_event"` | No currently visible exact-next event was eligible; not global catch-up. |

### 3.2 Producer status enums

| Enum | Current members |
|---|---|
| `ReplayValidationStatus` | `MATCH`, `MISSING_PROJECTION`, `DRIFT`, `NO_ACCEPTED_HISTORY` |
| `ProjectionSnapshotReplayValidationStatus` | `MATCH`, `MISSING_SNAPSHOT`, `NO_ACCEPTED_HISTORY_FOR_ORDER`, `INVALID_SNAPSHOT_BOUNDARY`, `TAIL_EVENT_SOURCE_CONTRACT_VIOLATION`, `SNAPSHOT_ASSISTED_DRIFT` |
| `ProjectionSnapshotAssistedResolutionStatus` | `RESOLVED_FROM_SNAPSHOT`, `MISSING_SNAPSHOT`, `INVALID_SNAPSHOT_PRECONDITION`, `INVALID_SNAPSHOT_COMPATIBILITY`, `TAIL_EVENT_SOURCE_CONTRACT_VIOLATION`, `TAIL_REPLAY_FAILED` |

### 3.3 Stage 4A semantic enums

| Enum | Current members |
|---|---|
| `SemanticBoundary` | `LAYER_1_WRITE_SIDE`, `LAYER_2_READ_SIDE`, `SNAPSHOT_TRUST`, `IDEMPOTENCY`, `CONCURRENCY_ADMISSION`, `RUNTIME_GOVERNANCE` |
| `SemanticOutcomeCategory` | `VALID`, `UNRESOLVED`, `UNTRUSTED`, `DRIFT`, `FALLBACK_REQUIRED`, `REBUILD_REQUIRED`, `BLOCK_REQUIRED`, `ESCALATION_REQUIRED`, `CONCURRENCY_UNCERTAIN`, `RETRY_CLASSIFIED`, `INTENT_INCONSISTENT` |
| `SemanticOutcomeCode` | `SEMANTICALLY_VALID`, `RUNTIME_UNRESOLVED`, `DERIVED_STATE_UNTRUSTED`, `DRIFT_DETECTED`, `FAST_PATH_UNAVAILABLE`, `REQUIRES_AUTHORITY_FALLBACK`, `REQUIRES_REBUILD`, `REQUIRES_OPERATOR_REVIEW`, `REJECT_DOWNSTREAM_USAGE`, `CONCURRENCY_UNCERTAIN`, `IDEMPOTENT_REPLAY_ALLOWED`, `SEMANTIC_CONFLICT_DETECTED`, `INTENT_DRIFT_DETECTED` |
| `SemanticSeverity` | `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `SemanticRiskLevel` | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`, `UNKNOWN` |
| `SemanticReversibility` | `REVERSIBLE`, `REBUILDABLE`, `COMPENSABLE`, `IRREVERSIBLE`, `UNKNOWN` |

Only `LAYER_2_READ_SIDE` and `SNAPSHOT_TRUST` are used by the three current read-side Stage 4A adapters. The other members remain shared vocabulary.

### 3.4 DecisionReceipt enums

| Enum | Current members |
|---|---|
| `DecisionReceiptEvidenceSource` | `WRITE_SIDE_ADMISSION`, `READ_SIDE_PATH`, `SNAPSHOT_TRUST_PATH`, `SNAPSHOT_ASSISTED_PATH`, `RUNTIME_OBSERVATION`, `UNKNOWN` |
| `DecisionReceiptSubjectType` | `ORDER`, `REQUEST`, `CANDIDATE_EVENT`, `ACCEPTED_EVENT`, `SNAPSHOT`, `PROJECTION`, `RUNTIME`, `UNKNOWN` |
| `DecisionReceiptIdentitySource` | `ACCEPTED_HISTORY`, `CANDIDATE_EVENT_IDENTITY`, `WRITE_SIDE_CORRELATION`, `READ_SIDE_OBSERVATION`, `SNAPSHOT_LINEAGE`, `CALLER_CONTEXT`, `UNKNOWN` |
| `DecisionReceiptFlagState` | `TRUE`, `FALSE`, `NOT_EVALUATED` |

PR5 uses only `READ_SIDE_PATH`, `SNAPSHOT_TRUST_PATH`, and `SNAPSHOT_ASSISTED_PATH`; subjects `ORDER`, `PROJECTION`, `SNAPSHOT`, and `RUNTIME`; and identity sources `READ_SIDE_OBSERVATION` and `SNAPSHOT_LINEAGE`. Every flag is `NOT_EVALUATED`.

## 4. Function call index

Recommended source-reading order:

| Order | Function | Input → output | Why inspect it |
|---:|---|---|---|
| 1 | `PostgresProjectionEligibleEventSource.load_eligible` | definition/epoch/limit → eligible records | Exact-next per-order discovery and global-position scheduling boundary |
| 2 | `PostgresProjectionWorker.process_next` | one invocation → worker result | State/progress transaction and `applied`/`no_event` meaning |
| 3 | `reduce_order_event` | state + accepted event → next state | Shared canonical reducer and local-sequence invariant |
| 4 | `DurableReplayValidator.validate_order` | order → replay result | Expected versus persisted comparison and PostgreSQL observation |
| 5 | `ProjectionSnapshotReplayValidator.validate_order` | order → snapshot validation result | Authority and assisted paths in one generic invocation |
| 6 | `PostgresProjectionSnapshotReplayValidator.validate_order` | order → same result | Same-connection top-level repeatable-read/read-only wrapper |
| 7 | `ProjectionSnapshotAssistedStateResolver.resolve_order` | order + trusted snapshot ID → resolution result | Compatibility and tail replay without authority comparison |
| 8 | `PostgresProjectionSnapshotAssistedStateResolver.resolve_order` | same → same result | PostgreSQL observation wrapper |
| 9 | three functions in `read_side_outcome_mapping.py` | typed result → `SemanticOutcome` | Stage 4A boundary and semantic tuple |
| 10 | three functions in `read_side_decision_receipt_mapping.py` | typed result + IDs → `DecisionReceipt` | PR5 shape/subject/correlation/evidence ownership |
| 11 | `map_semantic_outcome_to_decision_receipt` | outcome + explicit supporting contracts → receipt | Generic one-to-one semantic preservation |
| 12 | `DecisionReceipt.__post_init__` | constructed fields → validated frozen receipt | Shared enum/type/JSON-safety boundary |

## 5. Which object should I inspect?

| Question | Inspect | Why |
|---|---|---|
| Did one worker application succeed? | `PostgresProjectionWorkerResult` | It reports `applied` versus `no_event` for one invocation. |
| Is persisted projection state equal to current accepted-history replay? | `ReplayValidationResult` | It exposes expected and persisted axes. |
| Is projection missing despite authority history? | `ReplayValidationResult.MISSING_PROJECTION` | Expected state is present while persisted state is absent. |
| Does derived state exist without observed authority history? | `ReplayValidationResult.NO_ACCEPTED_HISTORY` plus `persisted_state is not None` | Current status is coarse; inspect the presence axis. |
| Was a snapshot loaded during snapshot validation? | `snapshot_id` and `source_global_position` pair | Paired values represent loaded lineage. |
| Was snapshot-assisted reconstruction compared with authority replay? | `ProjectionSnapshotReplayValidationResult` | It carries both comparison-state axes where available. |
| Was state only resolved from a supplied snapshot? | `ProjectionSnapshotAssistedResolutionResult` | It has `resolved_state` but no authority state. |
| Was a tail record different-order or non-contiguous? | `TAIL_EVENT_SOURCE_CONTRACT_VIOLATION` | This is the producer’s order-local source-contract status. |
| Which semantic boundary owns the meaning? | `SemanticOutcome.boundary` or receipt `boundary` | Stage 4A fixes it. |
| Which evidence path produced the receipt? | `DecisionReceipt.evidence_source` | PR5 selects it from producer identity. |
| Was any governance flag evaluated? | All four `DecisionReceipt.flags` fields | `NOT_EVALUATED` means no completed proposition. |

## 6. Confusion pairs

| Pair | Correct distinction |
|---|---|
| Worker execution vs replay validation | Worker result records one exact-next execution step; replay result compares full current canonical replay with persisted state. |
| Expected state vs persisted state | Expected is reconstructed from accepted history; persisted is loaded from `projection_states`. |
| Authority state vs snapshot-assisted state | Authority is full accepted-history replay; assisted is hydrated snapshot plus contiguous local tail. |
| `MISSING_PROJECTION` vs `NO_ACCEPTED_HISTORY` | First has authority replay state but no projection row; second has no accepted history and may still have a projection row. |
| `NO_ACCEPTED_HISTORY` with vs without persisted state | Both share current status; presence boolean distinguishes the coarse edge case. |
| `MISSING_SNAPSHOT` vs `NO_ACCEPTED_HISTORY_FOR_ORDER` | Validation missing-snapshot requires authority history/state; no-history has no authority state and may preserve optional loaded lineage. |
| No history without vs with loaded snapshot lineage | Both currently use `NO_ACCEPTED_HISTORY_FOR_ORDER`; loaded lineage may indicate a snapshot artifact without current authority support. |
| `SNAPSHOT_ASSISTED_DRIFT` vs guaranteed unequal states | The current producer status can preserve both states after an assisted-path failure before a conclusive final comparison; PR5 does not infer inequality from the name alone. |
| Snapshot validation vs snapshot resolution | Validation compares assisted reconstruction with authority; resolution consumes supplied trust and produces state without full replay. |
| `MATCH` vs permanent trust | Match is one observation; it has no lease, expiry, continuation, or future-state proof. |
| `source_global_position` vs `source_event_sequence` | Global position is lineage/scheduling coordinate; local event sequence drives tail correctness and is not exposed by mapped result dataclasses. |
| Subject vs correlation | Subject is what the receipt is about; correlation carries queryable identity/lineage and primary provenance. |
| Semantic outcome vs `DecisionReceipt` | Outcome is semantic classification; receipt adds compact evidence ownership/identity but still no action. |
| `NOT_EVALUATED` vs `FALSE` | The former records no completed evaluation; the latter is a completed negative proposition. |
| Technical failure vs runtime action | Status and semantic classification preserve evidence; later authorized layers choose action. |
| Point-in-time validation vs trust continuation | Current validators observe one boundary; provisional Stage 4B.3 would govern qualified advancement and is not implemented. |
| Canonical replay consistency vs intended correctness | Shared reducer equality can match despite a common-mode reducer defect; intended domain correctness needs a separate contract. |

## 7. Current gaps and reserved/deferred vocabulary

- `PostgresProjectionWorkerResult` has no Stage 4A or PR5 mapping.
- No production runner, validator scheduler, post-worker hook, or automatic mapper composition exists.
- PR5 returns an in-memory `DecisionReceipt`; it does not serialize or persist it.
- `NO_ACCEPTED_HISTORY` with persisted state has no separate production status; vocabulary hardening is deferred.
- `NO_ACCEPTED_HISTORY_FOR_ORDER` with loaded snapshot lineage has no separate orphan/unsupported-snapshot status; the parallel integrity vocabulary is deferred.
- `SNAPSHOT_ASSISTED_DRIFT` does not currently require unequal states; later vocabulary review may decide whether the name or producer classification should become narrower.
- Continuous projection trust, trust leases, invalidation, revalidation, and Stage 4B.3 trust continuation are deferred.
- Diagnostic traces, runtime policy, action, fallback, rebuild, quarantine, and retry governance are future responsibilities.
- `src/pipeline/projection/README.md` contains stale wording that says durable replay validation and structured Layer 2 `SemanticOutcome` do not exist; current source supersedes that claim, but this guide does not edit the README.
- The shared enums reserve members unused by PR5; their existence does not authorize PR5 to select them.

## 8. Source and test anchors

- Repaired progress decision: `docs/adr/0020_per_order_projection_progress_and_order_local_snapshot_tails.md`.
- Worker/progress tests: `tests/integration/pipeline/projection/test_postgres_projection_worker.py`, `tests/integration/pipeline/projection/test_postgres_projection_worker_commit_visibility.py`, `tests/integration/storage/test_postgres_projection_progress_store.py`, and `tests/integration/storage/test_postgres_projection_eligible_event_source.py`.
- Durable replay tests: `tests/integration/pipeline/projection/test_durable_replay_validation.py`.
- Snapshot producer tests: `tests/unit/pipeline/projection/test_projection_snapshot_replay_validator.py`, `tests/unit/pipeline/projection/test_projection_snapshot_assisted_state_resolver.py`, `tests/integration/pipeline/projection/test_projection_snapshot_replay_validator_postgres.py`, and `tests/integration/pipeline/projection/test_projection_snapshot_assisted_state_resolver_postgres.py`.
- Stage 4A parity tests: `tests/unit/compass/runtime/test_read_side_outcome_mapping.py`.
- PR5 matrices/ownership/invalid-shape tests: `tests/unit/compass/runtime/test_read_side_decision_receipt_mapping.py`.
- Flag ownership: `docs/adr/0018_producer_receipt_adapters_preserve_evidence_but_do_not_evaluate_governance_flags.md`.
