# Stage 4A to Stage 4B: Write-Side Mapping Flow

This guide covers only the division of responsibility between Stage 4A and Stage 4B after a `PostgresWriteSideResult` has been completed. For the Stage 3.5B transaction details, first read [PostgreSQL Write-Side Result to DecisionReceipt: End-to-End Flow](write_side_result_to_decision_receipt_end_to_end.md).

## How to read this guide

For Stage 4A / Stage 4B ownership, start with the three-layer mapping model and the field-ownership table. For the complete request lifecycle, return to the [end-to-end flow](write_side_result_to_decision_receipt_end_to_end.md). For a class, enum, or helper lookup, use the [Type and Vocabulary Reference](write_side_mapping_type_and_vocabulary_reference.md).

## 1. The three-layer mapping model

```text
PostgresWriteSideResult
        │
        ▼
PR4 producer-specific write-side adapter
map_postgres_write_side_result_to_decision_receipt
        │
        ├── _validate_result_shape(original result)
        │
        ├── call Stage 4A mapper
        │       map_postgres_write_side_result_to_semantic_outcome
        │               └── SemanticOutcome
        │
        ├── independently select typed producer evidence
        │       identity / subject / correlation / provenance
        │       admission fate / default all-NE flags / evidence summary
        │
        └── call Stage 4B generic receipt mapper
                map_semantic_outcome_to_decision_receipt(
                    SemanticOutcome,
                    supporting contracts,
                )
                        │
                        ▼
                DecisionReceipt.__post_init__
                        │
                        ▼
                DecisionReceipt
```

The three responsibilities are:

1. Stage 4A `map_postgres_write_side_result_to_semantic_outcome(...)` validates the basic result shape, selects the technical status, and uses the technical mapping to determine the semantic tuple. Source: `src/compass/runtime/write_side_outcome_mapping.py::map_postgres_write_side_result_to_semantic_outcome`.
2. The generic Stage 4B `map_semantic_outcome_to_decision_receipt(...)` copies the semantic tuple one-to-one and assembles explicitly supplied supporting contracts. It has no knowledge of the PostgreSQL producer. Source: `src/compass/runtime/decision_receipt_mapping.py::map_semantic_outcome_to_decision_receipt`.
3. Stage 4B PR4 `map_postgres_write_side_result_to_decision_receipt(...)` is the public entry point. It accepts the typed write-side result directly, validates its shape, calls Stage 4A, independently selects subject, correlation, identity provenance, admission fate, default all-`NOT_EVALUATED` flags, and a compact summary from the original result, and passes both groups of inputs to the generic mapper. `SemanticOutcome` is not the PR4 adapter's sole input. Source: `src/compass/runtime/write_side_decision_receipt_mapping.py::map_postgres_write_side_result_to_decision_receipt`.

The PR4 public wrapper owns this composition internally:

```text
PostgresWriteSideResult
→ map_postgres_write_side_result_to_semantic_outcome
→ SemanticOutcome
→ map_semantic_outcome_to_decision_receipt
→ DecisionReceipt
```

PR4 implements the producer-specific mapping adapter. No production command
path currently invokes it. Strict DecisionReceipt serialization and PostgreSQL
persistence exist through separate explicit boundaries, but automatic
materialization from a normal write command remains outside PR4.

Stage 4B.5 adds a separate refinement composition without changing ownership
of the Stage 4A tuple or the DecisionReceipt path:

```text
PostgresWriteSideResult
→ explicit map_postgres_write_side_result_to_semantic_rule_feedback(...)
   ├── existing Stage 4A SemanticOutcome mapping
   └── exact Order rule refinement only for terminal VALIDATION_BLOCKED
→ PostgresWriteSideSemanticRuleFeedback
```

This object is not a `DecisionReceipt`, does not change the write-side
transaction, and is not automatically produced by every write command.
Preserved validation observation on a later terminal outcome remains available
on the source result but does not become that outcome's terminal rule
refinement.

## 2. Why the generic mapper is intentionally insufficient

The generic mapper accepts a `SemanticOutcome` plus explicit supporting values. It does not read or copy:

```text
SemanticOutcome.context
SemanticOutcome.evidence
```

Tests lock in this behavior. Sources: `tests/unit/compass/runtime/test_decision_receipt_mapping.py::test_mapper_does_not_copy_or_inspect_outcome_context`, `tests/unit/compass/runtime/test_decision_receipt_mapping.py::test_mapper_does_not_copy_or_inspect_outcome_evidence`.

The reason is that a free-form payload cannot independently prove these axes:

- `evidence_source`: which evidence path made the observation.
- `subject`: the primary entity the receipt concerns.
- `correlation`: the other typed identities and event relationships.
- `identity_source`: the provenance of the primary identity block.
- `admission_evidence`: the current attempt's candidate-level admission fate.
- `flags`: whether an authorized evaluator completed each tri-state
  proposition; PR4 completes none.

If the generic mapper inferred these fields from `category`, `semantic_code`, nullable IDs, or an arbitrary mapping, it would collapse semantic meaning, identity authority, and lifecycle evidence into one axis. Sources: `src/compass/runtime/decision_receipt_mapping.py::map_semantic_outcome_to_decision_receipt`, `tests/unit/compass/runtime/test_decision_receipt_mapping.py::test_mapper_does_not_infer_write_side_admission_contracts`.

## 3. Field ownership table

### `DecisionReceipt` fields

| Field | Owner | Write-side PR4 behavior |
|---|---|---|
| `receipt_id` | supplied by the producer-specific adapter; copied by the generic mapper | caller-owned native `UUID` |
| `outcome_id` | copied from `SemanticOutcome` | Stage 4A uses the caller's `outcome_id` |
| `ok` | copied from `SemanticOutcome` | preserved exactly |
| `boundary` | copied from `SemanticOutcome` | `LAYER_1_WRITE_SIDE` |
| `category` | copied from `SemanticOutcome` | preserved exactly |
| `semantic_code` | copied from `SemanticOutcome` | preserved exactly |
| `severity` | copied from `SemanticOutcome` | preserved exactly |
| `risk_level` | copied from `SemanticOutcome` | preserved exactly |
| `reversibility` | copied from `SemanticOutcome` | preserved exactly |
| `reason` | copied from `SemanticOutcome` | preserved exactly |
| `evidence_source` | producer-specific adapter | fixed to `WRITE_SIDE_ADMISSION` |
| `subject` | producer-specific adapter | selected from the concrete outcome and identity |
| `correlation` | producer-specific adapter | selected only from typed sources; event IDs become `UUID` values |
| `actor` | generic mapper default | `DecisionReceiptActor()`; PR4 leaves it empty |
| `cost_summary` | generic mapper default | `DecisionReceiptCostSummary()`; PR4 derives no timing |
| `flags` | producer-specific adapter | `DecisionReceiptFlags()` leaves all four fields `NOT_EVALUATED` |
| `admission_evidence` | producer-specific adapter | present for every concrete PR4 result |
| `evidence_summary` | producer-specific adapter | compact allow-list vocabulary |
| `metadata` | generic mapper default | `{}`; PR4 leaves it empty |

Assembly ownership is in `src/compass/runtime/decision_receipt_mapping.py::map_semantic_outcome_to_decision_receipt`; write-side selection is in `src/compass/runtime/write_side_decision_receipt_mapping.py::map_postgres_write_side_result_to_decision_receipt`; final type and cross-field validation is in `src/compass/runtime/decision_receipt.py::DecisionReceipt.__post_init__`.

### `SemanticOutcome` fields

| Field | Generic receipt mapper |
|---|---|
| `outcome_id`, `ok`, `boundary`, `category`, `semantic_code`, `severity`, `risk_level`, `reversibility`, `reason` | copied one-to-one |
| `context` | intentionally ignored |
| `evidence` | intentionally ignored |

Stage 4A `context` and `evidence` remain available to Stage 4A contract tests and other direct consumers, but they are not PR4 receipt authority. PR4 does not accept caller override inputs. Sources: `src/compass/runtime/write_side_outcome_mapping.py::map_postgres_write_side_result_to_semantic_outcome`, `tests/unit/compass/runtime/test_write_side_decision_receipt_mapping.py::test_semantic_context_and_evidence_are_not_copied`.

## 4. Technical-status alignment

One `PostgresWriteSideResult` has two status-selection paths:

```text
PostgresWriteSideResult
    → Stage 4A _technical_status_for_postgres_write_side_result(...)
    → SemanticOutcome.evidence["technical_status"]

PostgresWriteSideResult
    → PR4 _technical_status_for_result(...)
    → DecisionReceipt.evidence_summary["technical_status"]
```

The Stage 4A helper is private, so PR4 does not call it across modules. Each layer currently owns a private technical-status selector. PR4 independently reconstructs the compact value from the typed outcome and verdict; it does not read or copy `SemanticOutcome.evidence["technical_status"]`. Sources: `src/compass/runtime/write_side_outcome_mapping.py::_technical_status_for_postgres_write_side_result`, `src/compass/runtime/write_side_decision_receipt_mapping.py::_technical_status_for_result`.

### Cross-layer parity coverage

`tests/unit/compass/runtime/test_write_side_decision_receipt_mapping.py::test_write_side_receipt_preserves_stage_4a_technical_status` compares the Stage 4A and PR4 outputs for the same supported typed result. It proves that both layers select the same technical status for the currently supported stream and append verdict vocabulary. It covers:

- `ACCEPTED`, `REPLAY`, `CONFLICT`, and `VALIDATION_BLOCKED`.
- Stream `STALE_WRITE`, `LOCK_TIMEOUT`, and `INFRASTRUCTURE_ERROR`.
- Append `STALE_WRITE`, `LOCK_TIMEOUT`, and `INFRASTRUCTURE_ERROR`.

This parity test is responsible for status-selection consistency. It does not independently prove every validation placement, subject shape, or candidate-presence variant.

### Lifecycle-shape coverage

Two separate tests lock in distinct lifecycle facts:

- `tests/unit/compass/runtime/test_write_side_decision_receipt_mapping.py::test_stream_rejection_before_candidate_uses_order_subject`: pre-candidate stream rejection with no current candidate.
- `tests/unit/compass/runtime/test_write_side_decision_receipt_mapping.py::test_non_default_post_validation_stream_rejections_map_to_append_admission_not_reached`: post-validation stream rejection in a non-default/custom composition, where a current candidate exists but append admission was not reached.

The second test does not claim that the default `PRE_TRANSACTION + PostgresOptimisticAdmissionGate` flow normally produces a rejected `prepare_stream(...)`. Optimistic preparation always returns `ADMITTED`; pessimistic preparation can return admitted, lock timeout, or infrastructure error. Stream `STALE_WRITE` is synthetic typed-domain coverage. Sources: `src/pipeline/transactional/postgres_admission.py::PostgresOptimisticAdmissionGate.prepare_stream`, `src/pipeline/transactional/postgres_admission.py::PostgresPessimisticAdmissionGate.prepare_stream`.

> **Future maintenance consideration:** If the write-side technical-status vocabulary expands materially, reconsider a shared typed selector instead of continuing to grow duplicated private mappings. This is not current PR4 work.

## 5. Identity-selection pipeline

```text
typed producer sources
        │
        ├── collect order_id / request_id strings
        ├── collect candidate / accepted event-id strings
        ▼
_select_consistent_string / _select_consistent_uuid
        │
        ├── reject blank
        ├── UUID(value)
        └── reject contradiction
        ▼
_SelectedIdentity
        │
        ▼
DecisionReceiptCorrelation
```

Current typed locations:

| Identity | Sources |
|---|---|
| `order_id` | returned accepted event; idempotency-record accepted event; `IdempotencyRecord.signature`; `StreamAdmissionResult` |
| `request_id` | returned accepted event; idempotency-record accepted event; `IdempotencyRecord.signature` |
| `candidate_event_id` | `ValidationResult`; `AdmissionResult` |
| `accepted_event_id` | returned accepted event; idempotency-record accepted event |

Source: `src/compass/runtime/write_side_decision_receipt_mapping.py::_select_identity`.

Producer event IDs are strings; receipt event correlation uses native `UUID` values. `_parse_uuid(...)` raises `ValueError` for blank or malformed values. When several typed sources provide the same identity, they must agree. `ACCEPTED` additionally requires the candidate, returned accepted event, and append accepted ID to be identical. Sources: `src/compass/runtime/write_side_decision_receipt_mapping.py::_parse_uuid`, `src/compass/runtime/write_side_decision_receipt_mapping.py::_validate_accepted_identity`.

`ValidationResult.metadata`, `SemanticOutcome.context`, and other arbitrary mappings do not participate in identity recovery.

A `CONFLICT` result can preserve the shared `request_id` lookup identity, the prior accepted `IdempotencyRecord`, its prior accepted event, and an optional current candidate identity when candidate construction already occurred. Its `accepted_event_id` belongs to the prior accepted record and proves why the shared request identity conflicts with accepted history; it does not mean that the current attempt was accepted. `subject = REQUEST` represents the request-level conflict. The retained `IdempotencyRecord.signature` describes the prior accepted signature. The typed result does not also preserve a complete representation of the current conflicting request intent, so the receipt must not reconstruct two complete request signatures or invent the current conflicting `command_type`, `order_id`, or `amount` from unrelated evidence. Sources: `src/storage/idempotency_store.py::IdempotencyRecord`, `src/pipeline/transactional/postgres_write_side.py::PostgresWriteSideResult`, `tests/unit/compass/runtime/test_write_side_decision_receipt_mapping.py::test_conflict_preserves_prior_history_as_conflict_evidence`.

Lifecycle position remains a separate fact. `REPLAY` / `CONFLICT` before candidate construction can come from the authoritative idempotency check in `IN_TRANSACTION` or the preliminary idempotency check in `PRE_TRANSACTION`; both shapes have no candidate or validation decision. `REPLAY` / `CONFLICT` at the post-validation authoritative re-check belongs only to `PRE_TRANSACTION`: a preliminary `MISS` is followed by accepted-history loading, candidate construction, validation `ALLOW`, entry into the write UOW, and then the authoritative re-check. That later shape can retain both current candidate identity and prior accepted-history identity, while stream preparation and candidate-level append admission have not occurred.

## 6. Subject-selection pipeline

`subject` is the primary entity the receipt is about. `correlation` retains other provable identities. The rules are:

```text
ACCEPTED / REPLAY
    → ACCEPTED_EVENT

CONFLICT
    → REQUEST

VALIDATION_BLOCKED
    → CANDIDATE_EVENT

ADMISSION_REJECTED with candidate
    → CANDIDATE_EVENT

ADMISSION_REJECTED without candidate
    → ORDER
```

Source: `src/compass/runtime/write_side_decision_receipt_mapping.py::_subject_for_result`.

Three easy mistakes:

- An earlier `IdempotencyVerdict.MISS` does not automatically make `REQUEST` the subject. When a later validation or append boundary owns the final outcome, the receipt is primarily about the candidate.
- In a conflict, the prior accepted event is conflict evidence, not proof that the current attempt was accepted. The subject is the retained record's `REQUEST`, not `ACCEPTED_EVENT`.
- Candidate existence does not prove that `append_if_admitted(...)` was invoked. The PRE path can end after validation at the authoritative idempotency re-check or at stream preparation.

Sources: `src/pipeline/transactional/postgres_write_side.py::PostgresTransactionalWriteSide._execute_pre_transaction_command`, `tests/unit/compass/runtime/test_write_side_decision_receipt_mapping.py::test_conflict_preserves_prior_history_as_conflict_evidence`.

## 7. Admission-disposition pipeline

| Concrete `PostgresWriteSideResult` shape | Current `EventAdmissionDisposition` | Boundary meaning |
|---|---|---|
| `ACCEPTED` | `ADMITTED_TO_ACCEPTED_HISTORY` | admitted candidate and returned accepted event have the same identity |
| `REPLAY` | `MATCHED_EXISTING_ACCEPTED_EVENT` | prior accepted event matches the same intent |
| `CONFLICT` | `IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY` | prior accepted record proves a different-intent conflict |
| `VALIDATION_BLOCKED` | `SEMANTIC_ADMISSION_REJECTED` | Compass rejected the candidate |
| stream-owned `ADMISSION_REJECTED`; `AdmissionResult is None` | `APPEND_ADMISSION_NOT_REACHED` | candidate-level append was not invoked |
| append `STALE_WRITE` | `APPEND_CONCURRENCY_CONFLICT` | append performed continuity/OCC arbitration and rejected |
| append `LOCK_TIMEOUT` | `APPEND_TECHNICAL_FAILURE` | append returned a typed technical failure |
| append `INFRASTRUCTURE_ERROR` | `APPEND_TECHNICAL_FAILURE` | append returned a typed technical failure |

Sources: `src/compass/runtime/write_side_decision_receipt_mapping.py::_admission_disposition_for_result`, `src/compass/runtime/decision_receipt.py::_validate_admission_evidence`.

`LOCK_TIMEOUT` does not mean `APPEND_CONCURRENCY_CONFLICT`. A timeout only says the technical operation did not complete; it does not prove that a competing version or continuity check determined staleness. `STALE_WRITE`, by contrast, carries append-time version or constraint evidence of a concurrency rejection. Source: `src/pipeline/transactional/postgres_admission.py::_append_with_translation`.

A stream rejection remains `APPEND_ADMISSION_NOT_REACHED` even if a candidate exists. The authority for this fate is the absence of `AdmissionResult` and the fact that `append_if_admitted(...)` was not invoked, not candidate nullability. Sources: `src/pipeline/transactional/postgres_write_side.py::PostgresTransactionalWriteSide._execute_pre_transaction_command`, `tests/unit/compass/runtime/test_write_side_decision_receipt_mapping.py::test_non_default_post_validation_stream_rejections_map_to_append_admission_not_reached`.

## 8. Flag-state boundary

`DecisionReceiptFlagState` has:

```text
TRUE
FALSE
NOT_EVALUATED
```

`NOT_EVALUATED` means that no authorized evaluator completed that proposition.
It must not be read as `FALSE`. Under ADR 0018, PR4 supplies:

```text
fallback_required
rebuild_required
operator_review_required
retry_candidate
→ NOT_EVALUATED
```

Typed `STALE_WRITE`, `LOCK_TIMEOUT`, and `INFRASTRUCTURE_ERROR` verdicts remain
preserved through technical status, the semantic tuple, lifecycle phase,
admission disposition, and the compact evidence summary. They do not grant PR4
governance-evaluator authority. Later dedicated evaluators may produce `TRUE`
or `FALSE` under their own complete contracts. Sources:
`docs/adr/0018_producer_receipt_adapters_preserve_evidence_but_do_not_evaluate_governance_flags.md`,
`src/compass/runtime/write_side_decision_receipt_mapping.py::map_postgres_write_side_result_to_decision_receipt`,
`tests/unit/compass/runtime/test_write_side_decision_receipt_mapping.py::test_every_supported_result_shape_leaves_flags_not_evaluated`.

## 9. Evidence-summary pipeline

Every PR4 receipt contains:

```text
technical_status
write_side_outcome
idempotency_verdict
lifecycle_phase
```

Keys are added only when the typed evidence exists:

| Source | Optional keys |
|---|---|
| `StreamAdmissionResult` | `stream_admission_verdict` |
| `ValidationDecision` / `ValidationResult` | `validation_action`, `validation_verdict`, `validation_mode` |
| `AdmissionResult` | `append_admission_verdict` |

All enum-backed values use `.value`. The phase is `ACCEPTED_HISTORY`, `IDEMPOTENCY_CHECK`, `VALIDATION`, `STREAM_PREPARATION`, or `APPEND_ADMISSION`. Sources: `src/compass/runtime/write_side_decision_receipt_mapping.py::_lifecycle_phase_for_result`, `src/compass/runtime/write_side_decision_receipt_mapping.py::_evidence_summary_for_result`.

`validation_verdict` preserves validation truth/evidence; `validation_action` preserves the enforcement response. They are separate axes. The repository must not require a universal `ALLOW == PASSED` or `BLOCK == FAILED` identity. For example, `ValidationMode.OFF` can truthfully produce `ValidationVerdict.SKIPPED` with `EnforcementAction.ALLOW`. Sources: `src/compass/transition/types.py::ValidationVerdict`, `src/compass/transition/runtime.py::ValidationPolicy.decide`.

PR4 does not copy rich validation metadata, duplicate reasons, event bodies, `OrderEvent` objects, Python class names, exceptions, SQL, or `SemanticOutcome.context/evidence`. `metadata` stays `{}`; `actor` and `cost_summary` stay at the generic defaults. The PR4 receipt payload contains no policy, strategy, retry authorization, serializer result, or persistence result. Sources: `tests/unit/compass/runtime/test_write_side_decision_receipt_mapping.py::test_evidence_summary_is_compact_typed_vocabulary_and_cost_is_not_derived`, `tests/unit/compass/runtime/test_write_side_decision_receipt_mapping.py::test_evidence_summary_has_exact_keys_for_lifecycle_shape`.

## 10. Stage 4A / Stage 4B invariant summary

1. The Stage 4A semantic tuple is preserved exactly; PR4 does not reclassify it. Source: `tests/unit/compass/runtime/test_write_side_decision_receipt_mapping.py::test_representative_write_side_results_preserve_exact_stage_4a_semantic_tuple`.
2. Producer-specific evidence is selected only from the typed `PostgresWriteSideResult` and its nested objects.
3. Free-form `SemanticOutcome` payloads are not promoted to receipt authority.
4. Blank, malformed, or contradictory identity fails closed. Source: `tests/unit/compass/runtime/test_write_side_decision_receipt_mapping.py::test_malformed_authority_bearing_event_ids_fail_closed`.
5. Candidate identity is not accepted-history authority; a conflict's prior accepted event is not current acceptance.
6. Candidate existence does not mean append admission was reached; `AdmissionResult` is the candidate-level append-boundary evidence.
7. `DecisionReceipt` is a frozen in-memory contract intended to represent durable governance evidence. Serializer v1 and PostgreSQL persistence are implemented separately, but receipt construction does not mean that a row was automatically materialized. The PR4 mapper records completed facts and executes no action, policy, retry, serialization, or persistence. Sources: `src/compass/runtime/decision_receipt.py::DecisionReceipt`, `src/compass/runtime/decision_receipt_serialization.py::serialize_decision_receipt`, `src/storage/postgres_decision_receipt_store.py::PostgresDecisionReceiptStore`, `tests/unit/compass/runtime/test_write_side_decision_receipt_mapping.py::test_wrapper_has_no_side_effect_or_expanded_public_surface`.
8. Stage 4B.5 exact rule evidence is a separate domain-specific refinement path. It does not add per-rule `SemanticOutcome` codes or alter ownership of the Stage 4A semantic tuple.
