# Stage 4A to Stage 4B: Read-Side Mapping Flow

This guide starts after a typed read-side or snapshot producer result already exists. It explains which layer owns semantic interpretation, producer-specific receipt evidence, generic construction, and shared validation. It does not describe validator execution as receipt mapping.

Primary sources: `src/compass/runtime/read_side_outcome_mapping.py`, `src/compass/runtime/read_side_decision_receipt_mapping.py`, `src/compass/runtime/decision_receipt_mapping.py`, and `src/compass/runtime/decision_receipt.py`.

## Reading guide

For the complete producer lifecycle, read [PostgreSQL Read-Side Result to DecisionReceipt: End-to-End Flow](read_side_result_to_decision_receipt_end_to_end.md). For quick type and enum lookup, read the [Read-Side Mapping Type and Vocabulary Reference](read_side_mapping_type_and_vocabulary_reference.md). The Traditional Chinese version is [Stage 4A 到 Stage 4B：Read-Side Mapping Flow](stage_4a_to_stage_4b_read_side_mapping_flow.zh.md).

## 1. Scope and three-layer model

```text
producer-specific technical result
        │
        ▼
Stage 4A producer adapter
        │  owns semantic tuple and boundary
        ▼
SemanticOutcome
        │
        ▼
PR5 producer adapter
        │  validates shape; selects evidence/identity/summary
        ▼
generic DecisionReceipt mapper (PR3)
        │  copies semantic tuple and explicit supporting contracts
        ▼
DecisionReceipt
        │  shared type and JSON-safe validation
        ▼
frozen in-memory receipt
```

The ownership split is:

| Layer | Owns | Does not own |
|---|---|---|
| Producer | Technical status, result fields, state/lineage shape, reason | Semantic category, receipt identity, governance action |
| Stage 4A | `ok`, boundary, category, code, severity, risk, reversibility, reason | Receipt evidence source, subject, correlation, flag evaluation |
| PR5 | Producer-shape admission, evidence source, subject, correlation, identity source, compact summary, neutral flags | New semantic remapping, runtime policy, persistence |
| PR3 generic mapper | One-to-one semantic-tuple copy and explicit supporting contracts | Producer inference or inspection of outcome context/evidence |
| `DecisionReceipt` | Shared type, identity, enum, correlation, JSON-safety, and immutability validation | Producer execution, policy, serialization, persistence |

## 2. Why the generic mapper is deliberately insufficient

`map_semantic_outcome_to_decision_receipt(...)` receives an already-formed `SemanticOutcome`. It cannot truthfully infer the following from semantic category, code, or free-form `context`/`evidence`:

- whether evidence came from durable replay, snapshot comparison, or snapshot-assisted resolution;
- whether the primary subject is an order, projection, snapshot, or runtime failure boundary;
- whether a snapshot ID is a requested reference or loaded artifact lineage;
- whether `source_global_position` belongs to a loaded snapshot;
- which producer state objects were present;
- whether any governance proposition was actually evaluated.

The generic mapper therefore never inspects or copies `SemanticOutcome.context` or `.evidence`. PR5 receives the original typed producer result, reconstructs compact canonical evidence directly from it, and supplies all supporting contracts explicitly. Source: `src/compass/runtime/decision_receipt_mapping.py::map_semantic_outcome_to_decision_receipt`.

## 3. Producer-by-producer field ownership

### 3.1 `ReplayValidationResult`

| `DecisionReceipt` field | Stage 4A owner | PR5 adapter owner | PR3/shared-contract behavior |
|---|---|---|---|
| `receipt_id` | no | caller supplies wrapper argument | PR3 copies; receipt validates UUID |
| `outcome_id` | `SemanticOutcome.outcome_id` | caller supplies wrapper argument to Stage 4A | PR3 copies from outcome |
| `ok` | technical-status mapping | preserve only | copied one-to-one |
| `boundary` | fixed `LAYER_2_READ_SIDE` | preserve only | copied one-to-one |
| `category` | technical-status mapping | preserve only | copied one-to-one |
| `semantic_code` | technical-status mapping | preserve only | copied one-to-one |
| `severity` | technical-status mapping | preserve only | copied one-to-one |
| `risk_level` | technical-status mapping | preserve only | copied one-to-one |
| `reversibility` | technical-status mapping | preserve only | copied one-to-one |
| `reason` | producer reason with Stage 4A blank fallback | preserve only | copied one-to-one |
| `evidence_source` | no | constant `READ_SIDE_PATH` | explicit required input |
| `subject` | no | `PROJECTION(order_id)`, except no history → `ORDER(order_id)` | shared subject validation |
| `correlation` | no | order only; `READ_SIDE_OBSERVATION` | request/event/snapshot fields absent |
| `actor` | no | no producer evidence | default `DecisionReceiptActor()` |
| `cost_summary` | no | no producer evidence | default `DecisionReceiptCostSummary()` |
| `flags` | no | `DecisionReceiptFlags()` | all fields `NOT_EVALUATED` |
| `admission_evidence` | no | read side owns none | `None` |
| `evidence_summary` | no | status plus expected/persisted presence | JSON-safe validation |
| `metadata` | no | no approved metadata | `{}` |

### 3.2 `ProjectionSnapshotReplayValidationResult`

| `DecisionReceipt` field | Stage 4A owner | PR5 adapter owner | PR3/shared-contract behavior |
|---|---|---|---|
| `receipt_id` | no | caller supplies wrapper argument | PR3 copies; receipt validates UUID |
| `outcome_id` | `SemanticOutcome.outcome_id` | caller supplies wrapper argument to Stage 4A | PR3 copies from outcome |
| `ok` | technical-status mapping | preserve only | copied one-to-one |
| `boundary` | fixed `SNAPSHOT_TRUST` | preserve only | copied one-to-one |
| `category` | technical-status mapping | preserve only | copied one-to-one |
| `semantic_code` | technical-status mapping | preserve only | copied one-to-one |
| `severity` | technical-status mapping | preserve only | copied one-to-one |
| `risk_level` | technical-status mapping | preserve only | copied one-to-one |
| `reversibility` | technical-status mapping | preserve only | copied one-to-one |
| `reason` | producer reason with Stage 4A blank fallback | preserve only | copied one-to-one |
| `evidence_source` | no | constant `SNAPSHOT_TRUST_PATH` | explicit required input |
| `subject` | no | status-specific `SNAPSHOT`, `RUNTIME`, `PROJECTION`, or `ORDER` | shared subject validation |
| `correlation` | no | order plus paired loaded `snapshot_id`/position when present | shared UUID/non-negative-position validation |
| `actor` | no | no producer evidence | default `DecisionReceiptActor()` |
| `cost_summary` | no | no producer evidence | default `DecisionReceiptCostSummary()` |
| `flags` | no | `DecisionReceiptFlags()` | all fields `NOT_EVALUATED` |
| `admission_evidence` | no | snapshot read side owns none | `None` |
| `evidence_summary` | no | status, artifact presence, assisted/authority presence | JSON-safe validation |
| `metadata` | no | no approved metadata | `{}` |

### 3.3 `ProjectionSnapshotAssistedResolutionResult`

| `DecisionReceipt` field | Stage 4A owner | PR5 adapter owner | PR3/shared-contract behavior |
|---|---|---|---|
| `receipt_id` | no | caller supplies wrapper argument | PR3 copies; receipt validates UUID |
| `outcome_id` | `SemanticOutcome.outcome_id` | caller supplies wrapper argument to Stage 4A | PR3 copies from outcome |
| `ok` | technical-status mapping | preserve only | copied one-to-one |
| `boundary` | fixed `SNAPSHOT_TRUST` | preserve only | copied one-to-one |
| `category` | technical-status mapping | preserve only | copied one-to-one |
| `semantic_code` | technical-status mapping | preserve only | copied one-to-one |
| `severity` | technical-status mapping | preserve only | copied one-to-one |
| `risk_level` | technical-status mapping | preserve only | copied one-to-one |
| `reversibility` | technical-status mapping | preserve only | copied one-to-one |
| `reason` | producer reason with Stage 4A blank fallback | preserve only | copied one-to-one |
| `evidence_source` | no | constant `SNAPSHOT_ASSISTED_PATH` | explicit required input |
| `subject` | no | status-specific `PROJECTION`, `SNAPSHOT`, or `RUNTIME` | shared subject validation |
| `correlation` | no | order plus requested reference or loaded lineage | shared UUID/non-negative-position validation |
| `actor` | no | no producer evidence | default `DecisionReceiptActor()` |
| `cost_summary` | no | no producer evidence | default `DecisionReceiptCostSummary()` |
| `flags` | no | `DecisionReceiptFlags()` | all fields `NOT_EVALUATED` |
| `admission_evidence` | no | resolver owns no write admission | `None` |
| `evidence_summary` | no | status, artifact presence, resolved-state presence | JSON-safe validation |
| `metadata` | no | no approved metadata | `{}` |

## 4. Shape validation

The result dataclasses are constructable containers and do not enforce every cross-field relation. PR5 fails closed before it selects receipt identity. These checks do not rerun producers, query storage, or prove that PostgreSQL orchestration occurred.

### 4.1 `_validate_replay_result_shape`

| Status | Legal shape |
|---|---|
| `MATCH` | expected and persisted present and equal |
| `MISSING_PROJECTION` | expected present, persisted absent |
| `DRIFT` | expected and persisted present and unequal |
| `NO_ACCEPTED_HISTORY` | expected absent; persisted optional |

The validator also requires the exact `ReplayValidationStatus` enum family and a non-blank order for receipt admission.

Across all three producer families, every present state must be an `OrderState`
whose `order_id` equals the result's `order_id`. This is receipt-admission
validation for directly constructable result containers, not proof of producer
execution or PostgreSQL orchestration.

### 4.2 `_validate_snapshot_replay_result_shape`

| Status | Legal shape |
|---|---|
| `MATCH` | paired loaded lineage; both states present/equal |
| `MISSING_SNAPSHOT` | lineage absent; assisted absent; authority present |
| `INVALID_SNAPSHOT_BOUNDARY` | loaded lineage; assisted absent; authority present |
| `TAIL_EVENT_SOURCE_CONTRACT_VIOLATION` | loaded lineage; both states present; equality allowed |
| `SNAPSHOT_ASSISTED_DRIFT` | loaded lineage; both states present; equality allowed |
| `NO_ACCEPTED_HISTORY_FOR_ORDER` | both comparison states absent; lineage paired but optional |

`SNAPSHOT_ASSISTED_DRIFT` is currently broader than a final unequal-state comparison. The producer can preserve both state objects when the assisted path fails before a conclusive final equality comparison. PR5 therefore must not infer inequality solely from the status name. This is a current vocabulary characteristic, not a new semantic rule introduced by the mapper.

When `NO_ACCEPTED_HISTORY_FOR_ORDER` retains loaded lineage, the result may be observing a snapshot artifact without current accepted-history authority. Current vocabulary preserves the no-history status and optional lineage but does not classify that integrity concern separately.

`_validate_paired_snapshot_lineage` requires `snapshot_id` and `source_global_position` to be both present or both absent. Loaded branches require the pair. The shared `DecisionReceiptCorrelation` accepts position zero, rejects negative integers, and rejects `bool`. PR5 adds only the producer-specific rule that position must be positive for snapshot-replay `MATCH`, `TAIL_EVENT_SOURCE_CONTRACT_VIOLATION`, and `SNAPSHOT_ASSISTED_DRIFT`, and for assisted `RESOLVED_FROM_SNAPSHOT`, `TAIL_EVENT_SOURCE_CONTRACT_VIOLATION`, and `TAIL_REPLAY_FAILED`. Zero remains admissible evidence for `INVALID_SNAPSHOT_BOUNDARY` and `INVALID_SNAPSHOT_COMPATIBILITY`.

### 4.3 `_validate_snapshot_assisted_result_shape`

The actual current helper name is `_validate_snapshot_assisted_result_shape`.

| Status | Legal shape |
|---|---|
| `RESOLVED_FROM_SNAPSHOT` | loaded snapshot ID and position; resolved state present |
| `MISSING_SNAPSHOT` | requested snapshot ID present; position and state absent |
| `INVALID_SNAPSHOT_PRECONDITION` | snapshot reference, lineage, and state absent |
| `INVALID_SNAPSHOT_COMPATIBILITY` | loaded ID/position; state absent |
| `TAIL_EVENT_SOURCE_CONTRACT_VIOLATION` | loaded ID/position; state absent |
| `TAIL_REPLAY_FAILED` | loaded ID/position; state absent |

The requested ID on `MISSING_SNAPSHOT` is not loaded lineage. The loaded branches must have both identity fields. Non-success branches deliberately expose no partial `resolved_state`.

### 4.4 What shape validation does not prove

Passing PR5 shape validation proves only that the supplied typed fields can support the selected receipt vocabulary without contradiction. It does not prove:

- that `DurableReplayValidator` or a PostgreSQL wrapper constructed the result;
- same-connection, top-level, repeatable-read orchestration;
- accepted-history completeness beyond the producer observation;
- snapshot trust continuation;
- root cause, policy, action, retry, or persistence.

## 5. Technical-status parity

Stage 4A owns the semantic tuple. PR5 preserves it without remapping and repeats only `result.status.value` as `evidence_summary.technical_status`.

| Producer status | `ok` | Boundary | Category / code | Severity / risk / reversibility |
|---|---:|---|---|---|
| Replay `MATCH` | true | `LAYER_2_READ_SIDE` | `VALID / SEMANTICALLY_VALID` | `INFO / LOW / REVERSIBLE` |
| Replay `MISSING_PROJECTION` | false | `LAYER_2_READ_SIDE` | `REBUILD_REQUIRED / REQUIRES_REBUILD` | `WARNING / MEDIUM / REBUILDABLE` |
| Replay `DRIFT` | false | `LAYER_2_READ_SIDE` | `DRIFT / DRIFT_DETECTED` | `ERROR / HIGH / REBUILDABLE` |
| Replay `NO_ACCEPTED_HISTORY` | false | `LAYER_2_READ_SIDE` | `UNRESOLVED / RUNTIME_UNRESOLVED` | `WARNING / UNKNOWN / UNKNOWN` |
| Snapshot validation `MATCH` | true | `SNAPSHOT_TRUST` | `VALID / SEMANTICALLY_VALID` | `INFO / LOW / REVERSIBLE` |
| Snapshot validation `MISSING_SNAPSHOT` | false | `SNAPSHOT_TRUST` | `FALLBACK_REQUIRED / FAST_PATH_UNAVAILABLE` | `WARNING / MEDIUM / REVERSIBLE` |
| Snapshot validation `INVALID_SNAPSHOT_BOUNDARY` | false | `SNAPSHOT_TRUST` | `UNTRUSTED / DERIVED_STATE_UNTRUSTED` | `ERROR / HIGH / REBUILDABLE` |
| Snapshot validation `TAIL_EVENT_SOURCE_CONTRACT_VIOLATION` | false | `SNAPSHOT_TRUST` | `UNRESOLVED / RUNTIME_UNRESOLVED` | `ERROR / HIGH / UNKNOWN` |
| Snapshot validation `SNAPSHOT_ASSISTED_DRIFT` | false | `SNAPSHOT_TRUST` | `DRIFT / DRIFT_DETECTED` | `ERROR / HIGH / REBUILDABLE` |
| Snapshot validation `NO_ACCEPTED_HISTORY_FOR_ORDER` | false | `SNAPSHOT_TRUST` | `UNRESOLVED / RUNTIME_UNRESOLVED` | `WARNING / UNKNOWN / UNKNOWN` |
| Resolution `RESOLVED_FROM_SNAPSHOT` | true | `SNAPSHOT_TRUST` | `VALID / SEMANTICALLY_VALID` | `INFO / LOW / REVERSIBLE` |
| Resolution `MISSING_SNAPSHOT` | false | `SNAPSHOT_TRUST` | `FALLBACK_REQUIRED / FAST_PATH_UNAVAILABLE` | `WARNING / MEDIUM / REVERSIBLE` |
| Resolution `INVALID_SNAPSHOT_PRECONDITION` | false | `SNAPSHOT_TRUST` | `UNTRUSTED / DERIVED_STATE_UNTRUSTED` | `ERROR / HIGH / REBUILDABLE` |
| Resolution `INVALID_SNAPSHOT_COMPATIBILITY` | false | `SNAPSHOT_TRUST` | `UNTRUSTED / DERIVED_STATE_UNTRUSTED` | `ERROR / HIGH / REBUILDABLE` |
| Resolution `TAIL_EVENT_SOURCE_CONTRACT_VIOLATION` | false | `SNAPSHOT_TRUST` | `UNRESOLVED / RUNTIME_UNRESOLVED` | `ERROR / HIGH / UNKNOWN` |
| Resolution `TAIL_REPLAY_FAILED` | false | `SNAPSHOT_TRUST` | `FALLBACK_REQUIRED / FAST_PATH_UNAVAILABLE` | `WARNING / MEDIUM / REVERSIBLE` |

Parity is covered by `tests/unit/compass/runtime/test_read_side_outcome_mapping.py` (one named test per status) and the PR5 matrices `REPLAY_CASES`, `SNAPSHOT_REPLAY_CASES`, and `SNAPSHOT_ASSISTED_CASES` in `tests/unit/compass/runtime/test_read_side_decision_receipt_mapping.py`.

## 6. Subject and identity selection

Subject means what the receipt is primarily about, not proven root cause.

| Producer/status | Subject |
|---|---|
| Replay `MATCH`, `MISSING_PROJECTION`, `DRIFT` | `PROJECTION(order_id)` |
| Replay `NO_ACCEPTED_HISTORY` | `ORDER(order_id)` |
| Snapshot validation `MATCH`, `INVALID_SNAPSHOT_BOUNDARY` | `SNAPSHOT(snapshot_id)` |
| Snapshot validation `MISSING_SNAPSHOT` | `SNAPSHOT(None)` |
| Snapshot validation tail contract violation | `RUNTIME(None)` |
| Snapshot validation drift | `PROJECTION(order_id)` |
| Snapshot validation no history | `ORDER(order_id)` |
| Resolution success | `PROJECTION(order_id)` |
| Resolution missing/incompatible snapshot | `SNAPSHOT(requested or loaded snapshot_id)` |
| Resolution precondition/tail-source/tail-replay failure | `RUNTIME(None)` |

Identity source is the primary provenance for the correlation block, not field-level provenance:

| Situation | Identity source |
|---|---|
| Replay; missing snapshot; missing trusted-ID precondition | `READ_SIDE_OBSERVATION` |
| Snapshot validation no-history without loaded snapshot | `READ_SIDE_OBSERVATION` |
| Resolver `MISSING_SNAPSHOT` requested reference | `READ_SIDE_OBSERVATION` |
| Any branch proving an actual snapshot was loaded | `SNAPSHOT_LINEAGE` |

`CALLER_CONTEXT` and `UNKNOWN` exist in the shared enum but no approved PR5 row uses them. `ACCEPTED_HISTORY`, `CANDIDATE_EVENT_IDENTITY`, and `WRITE_SIDE_CORRELATION` are also inappropriate because these result dataclasses do not expose accepted/candidate event identity as correlation authority.

## 7. Evidence-summary ownership

Exact producer vocabularies are:

```text
ReplayValidationResult
technical_status
expected_state_present
persisted_state_present

ProjectionSnapshotReplayValidationResult
technical_status
snapshot_artifact_present
snapshot_assisted_state_present
authority_state_present

ProjectionSnapshotAssistedResolutionResult
technical_status
snapshot_artifact_present
resolved_state_present
```

PR5 intentionally omits state objects, snapshot objects, event payloads, `result_type`, duplicated reason, `SemanticOutcome.context`, `SemanticOutcome.evidence`, arbitrary metadata, raw exceptions, `source_event_id`, `source_event_sequence`, `projection_name`, and `projection_epoch`.

The ownership guard `test_mapped_producer_result_field_ownership_is_explicit` fails if producer result fields change, forcing a new mapping decision. `test_receipt_summary_is_reconstructed_without_outcome_payload_copying` proves that monkeypatched Stage 4A context/evidence cannot replace PR5 canonical summary values.

## 8. Governance flags

ADR 0018 establishes:

```text
producer-specific receipt adapters
→ preserve typed evidence
≠ evaluate governance flags
```

Every PR5 wrapper supplies `DecisionReceiptFlags()`, leaving:

```text
fallback_required = NOT_EVALUATED
rebuild_required = NOT_EVALUATED
operator_review_required = NOT_EVALUATED
retry_candidate = NOT_EVALUATED
```

`NOT_EVALUATED` is not `FALSE`. `MATCH` is positive technical/semantic evidence but does not prove that every governance proposition was completed negatively. A failure category or code may describe `FALLBACK_REQUIRED` or `REQUIRES_REBUILD` without completing the corresponding receipt flag as `TRUE`.

## 9. Current limitations

- Replay and snapshot `MATCH` are point-in-time evidence, not continuing trust.
- Full replay and live projection share the current canonical reducer; common-mode reducer defects may still match.
- `NO_ACCEPTED_HISTORY` permits persisted state, leaving projection-without-authority as coarse unresolved vocabulary.
- `NO_ACCEPTED_HISTORY_FOR_ORDER` may retain loaded snapshot lineage, leaving snapshot-without-authority as a parallel coarse integrity concern.
- `SNAPSHOT_ASSISTED_DRIFT` currently does not require unequal states because the producer status can represent an assisted-path failure before a conclusive final comparison.
- Snapshot validation and resolution result dataclasses do not attest PostgreSQL orchestration.
- `source_global_position` is snapshot lineage only; order-local tail correctness uses unexposed `source_event_sequence`.
- PR5 does not map `PostgresProjectionWorkerResult`.
- PR5 provides no production invocation, scheduler, continuous validation, trust continuation, runtime action, policy, retry, serialization, or persistence.
- Stage 4B.3 trust continuation remains a provisional roadmap plan, not production.

## 10. Source and test anchors

- Stage 4A functions: `src/compass/runtime/read_side_outcome_mapping.py`.
- PR5 public wrappers and private validators: `src/compass/runtime/read_side_decision_receipt_mapping.py`.
- Generic PR3 mapper: `src/compass/runtime/decision_receipt_mapping.py::map_semantic_outcome_to_decision_receipt`.
- Shared receipt contract: `src/compass/runtime/decision_receipt.py::DecisionReceipt`.
- Semantic parity: `tests/unit/compass/runtime/test_read_side_outcome_mapping.py`.
- Receipt matrices and edge cases: `tests/unit/compass/runtime/test_read_side_decision_receipt_mapping.py`.
- All-neutral flag ownership: `docs/adr/0018_producer_receipt_adapters_preserve_evidence_but_do_not_evaluate_governance_flags.md`.
