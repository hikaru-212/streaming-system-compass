# PostgreSQL Write-Side Result to DecisionReceipt: End-to-End Flow

This guide follows the current production code and directly related tests, connecting Stage 3.5B, Stage 4A, and Stage 4B PR4. It is a reading guide and does not replace the invariants defined by the types themselves.


Primary sources: `src/pipeline/transactional/postgres_write_side.py::PostgresTransactionalWriteSide`, `src/compass/transition/runtime.py::ValidationRuntime`, `src/compass/runtime/write_side_outcome_mapping.py::map_postgres_write_side_result_to_semantic_outcome`, `src/compass/runtime/write_side_decision_receipt_mapping.py::map_postgres_write_side_result_to_decision_receipt`, and `src/compass/runtime/write_side_rule_feedback.py::map_postgres_write_side_result_to_semantic_rule_feedback`.

## How to read this guide

For the complete request lifecycle, read the sections in order. For Stage 4A / Stage 4B ownership only, read [Stage 4A to Stage 4B: Write-Side Mapping Flow](stage_4a_to_stage_4b_write_side_mapping_flow.md). For a class, enum, or helper lookup, read the [Write-Side Mapping Type and Vocabulary Reference](write_side_mapping_type_and_vocabulary_reference.md).

## 1. Executive overview

```text
create_order(...) / pay_order(...)
        │
        ▼
PostgresTransactionalWriteSide
        │
        ├── idempotency
        ├── stream preparation
        ├── history loading / aggregate rehydration
        ├── candidate construction
        ├── Compass validation
        ├── append admission
        ├── idempotency recording
        └── commit / rollback
        │
        ▼
PostgresWriteSideResult
        │
        ▼
PR4 producer-specific write-side adapter
        ├── validate the original PostgresWriteSideResult
        ├── call Stage 4A mapper → SemanticOutcome
        ├── select typed identity / subject / fate / all-NE flags / summary
        └── call generic mapper(SemanticOutcome, supporting contracts)
                                │
                                ▼
                    DecisionReceipt.__post_init__
                                │
                                ▼
                        DecisionReceipt

PostgresWriteSideResult
        │
        ▼
explicit PR7 semantic-rule-feedback mapper
        ├── call Stage 4A mapper → SemanticOutcome
        └── expose exact rule refinement only for terminal VALIDATION_BLOCKED
                                │
                                ▼
             PostgresWriteSideSemanticRuleFeedback
```

`PostgresTransactionalWriteSide` executes a command, may read and write PostgreSQL, and uses `PostgresWriteSideResult` to represent a normally completed lifecycle outcome. Stage 4A interprets that result as a semantic tuple. Stage 4B PR4 selects only completed typed evidence and assembles an in-memory `DecisionReceipt`; it does not execute another write, commit, rollback, or retry. Serializer v1, PostgreSQL receipt persistence, and a dedicated receipt transaction owner now exist as separately invoked capabilities; no normal write command automatically materializes a receipt. Sources: `src/pipeline/transactional/postgres_write_side.py::PostgresTransactionalWriteSide._execute_command`, `src/compass/runtime/write_side_decision_receipt_mapping.py::map_postgres_write_side_result_to_decision_receipt`, `src/compass/runtime/decision_receipt_serialization.py::serialize_decision_receipt`, `src/storage/postgres_decision_receipt_transaction_owner.py::PostgresDecisionReceiptTransactionOwner`.

`StreamAdmissionResult` is the stream-preparation evidence produced by `ConcurrencyGate.prepare_stream(...)`. Its position relative to history loading, candidate construction, and validation depends on orchestration placement. `AdmissionResult` is the candidate-level append boundary. Neither is synonymous with transaction commit or accepted-history membership. The actual insert occurs when a gate calls `PostgresEventStore.append(...)`; transaction completion is controlled by `PostgresWriteSideUnitOfWork.__exit__`. Sources: `src/pipeline/transactional/admission.py::StreamAdmissionResult`, `src/pipeline/transactional/admission.py::AdmissionResult`, `src/pipeline/transactional/postgres_admission.py::_append_with_translation`, `src/pipeline/transactional/postgres_unit_of_work.py::PostgresWriteSideUnitOfWork.__exit__`.

## 2. Entry points

### `create_order(...)`

`PostgresTransactionalWriteSide.create_order(...)` accepts `request_id`, `order_id`, and `amount`, selects `CommandType.CREATE`, and supplies a `CandidateEventBuilder` that calls `aggregate.create(...)` on the current `OrderAggregate`. Source: `src/pipeline/transactional/postgres_write_side.py::PostgresTransactionalWriteSide.create_order`.

### `pay_order(...)`

`PostgresTransactionalWriteSide.pay_order(...)` accepts the same identity and amount fields, selects `CommandType.PAY`, and supplies a builder that calls `aggregate.pay(...)`. The builder creates an `OrderEvent` candidate that does not yet have accepted-history authority. Sources: `src/pipeline/transactional/postgres_write_side.py::PostgresTransactionalWriteSide.pay_order`, `src/core/order/aggregate.py::OrderAggregate.pay`.

### `_execute_command(...)`

Both public entry points enter `_execute_command(...)`. `PostgresWriteSideConfig.validation_placement` selects the path:

| placement | Execution function | Current default |
|---|---|---|
| `IN_TRANSACTION` | `_execute_in_transaction_command(...)` | no |
| `PRE_TRANSACTION` | `_execute_pre_transaction_command(...)` | yes |

The current `PostgresWriteSideConfig` defaults are `ValidationMode.STRICT` and `ValidationPlacement.PRE_TRANSACTION`. The separate default gate factory builds `PostgresOptimisticAdmissionGate`. Validation mode, validation placement, and concurrency-gate strategy are three independent axes: PRE does not automatically mean optimistic, and IN does not automatically mean pessimistic. Sources: `src/pipeline/transactional/postgres_write_side_config.py::PostgresWriteSideConfig`, `src/pipeline/transactional/postgres_write_side.py::_default_admission_gate_factory`, `tests/unit/pipeline/transactional/test_postgres_write_side_config.py::test_default_postgres_write_side_config_uses_strict_pre_transaction`.

Both paths first construct `RequestSignature(request_id, command_type, order_id, amount)` from the command arguments. `RequestSignature` defines the current request intent. The PostgreSQL store converts it to a semantic fingerprint to distinguish `MISS`, same-intent `REPLAY`, and different-intent `CONFLICT`. Sources: `src/storage/idempotency_store.py::RequestSignature`, `src/storage/postgres_idempotency_store.py::build_semantic_fingerprint`, `src/storage/postgres_idempotency_store.py::PostgresIdempotencyStore.check`.

For a conflict, the typed result can preserve the shared `request_id` lookup identity, the prior accepted `IdempotencyRecord`, the prior accepted event, and an optional current candidate identity when candidate construction already occurred. It does not simultaneously preserve another complete representation of the current conflicting request intent. The retained `IdempotencyRecord.signature` describes the prior accepted signature. A receipt must not reconstruct two complete signatures or invent the current conflicting `command_type`, `order_id`, or `amount` from unrelated evidence.

`REPLAY` / `CONFLICT` before candidate construction covers two distinct placements:

```text
IN_TRANSACTION
→ authoritative idempotency check
→ no candidate has been constructed

PRE_TRANSACTION
→ preliminary idempotency check
→ no candidate has been constructed
```

`REPLAY` / `CONFLICT` at the post-validation authoritative re-check belongs only to `PRE_TRANSACTION`:

```text
preliminary MISS
→ accepted-history load
→ candidate construction
→ validation ALLOW
→ enter write UOW
→ authoritative idempotency re-check
→ REPLAY or CONFLICT
```

Therefore, replay/conflict before candidate construction is not exclusive to `IN_TRANSACTION`, and not every `PRE_TRANSACTION` replay/conflict occurs after validation.

## 3. `IN_TRANSACTION` path

The following is the actual order in `_execute_in_transaction_command(...)`. The entire path is inside one `PostgresWriteSideUnitOfWork`; a normal accepted return commits when the context manager exits.

Exceptions raised from inside the `with` body cause `__exit__` to roll back and re-raise. A failure raised by `connection.commit()` from inside `__exit__` escapes that method. The current implementation does not guarantee a subsequent rollback after a commit failure. Sources: `src/pipeline/transactional/postgres_write_side.py::PostgresTransactionalWriteSide._execute_in_transaction_command`, `src/pipeline/transactional/postgres_unit_of_work.py::PostgresWriteSideUnitOfWork.__exit__`.

| Order | Function / input → output | Authority and early return |
|---:|---|---|
| 1 | `RequestSignature(...)` | fixes the caller command as idempotency intent; no candidate exists |
| 2 | `PostgresWriteSideUnitOfWork.__enter__` | starts the write-transaction scope shared by the event and idempotency stores |
| 3 | `uow.idempotency_store.check(signature)` → `IdempotencyDecision` | authoritative check; `REPLAY` or `CONFLICT` explicitly calls `rollback()` and returns; no candidate and no append |
| 4 | `admission_gate.prepare_stream(order_id)` → `StreamAdmissionResult` | stream preparation; the pessimistic gate attempts an advisory lock, while the optimistic gate returns `ADMITTED` without locking; rejection explicitly rolls back before candidate construction or append |
| 5 | `_rehydrate_aggregate(uow, order_id)` → `OrderAggregate, history` | loads accepted history and applies it to the aggregate; reading does not create membership |
| 6 | `_build_validation_context(...)` → `ValidationContext` | preserves the actual previous event/version/status for Compass |
| 7 | `build_candidate_event(aggregate)` → `OrderEvent` | creates the candidate; it is not accepted history |
| 8 | `_invoke_validation(candidate, context)` → `ValidationDecision` plus optional `ValidationDecisionWithRuleEvidence` | uses `decide_with_rule_evidence(...)` when exposed, otherwise calls legacy `decide(...)`; `BLOCK` explicitly rolls back and returns `VALIDATION_BLOCKED`; the candidate exists and append has not been invoked |
| 9 | `gate.append_if_admitted(candidate, expected_current_version)` → `AdmissionResult` | candidate-level append admission; an `ADMITTED` result means the gate called the event-store append; rejection explicitly rolls back and returns `ADMISSION_REJECTED` |
| 10 | `uow.idempotency_store.record(signature, candidate)` | writes accepted-event idempotency memory in the same transaction; a failure raised from the body makes `__exit__` roll back the inserted event |
| 11 | evaluate `return PostgresWriteSideResult(ACCEPTED, ...)` | Python builds the result object and evaluates the return expression inside the `with` block, then runs clean `__exit__` commit; the caller receives the result only after commit succeeds |

With `IN_TRANSACTION + PESSIMISTIC`, a successful `prepare_stream(...)` holds the stream lock until commit or rollback. History loading, candidate construction, Compass validation, and append all occur in the lock scope. The append-time version/continuity check still runs as the final accepted-history continuity guard. Sources: `src/pipeline/transactional/postgres_admission.py::PostgresPessimisticAdmissionGate.prepare_stream`, `src/pipeline/transactional/postgres_admission.py::PostgresPessimisticAdmissionGate.append_if_admitted`, `src/storage/postgres_event_store.py::PostgresEventStore.append`.

Every normal non-accepted early return explicitly calls `uow.rollback()`. An unexpected exception or idempotency-record failure raised inside the body is rolled back by `__exit__`. A commit failure escapes directly; the current implementation guarantees neither a subsequent rollback nor a typed ambiguous-commit reconciliation result. Sources: `tests/integration/pipeline/transactional/test_postgres_write_side.py::test_in_transaction_record_failure_rolls_back_appended_event`, `src/pipeline/transactional/postgres_unit_of_work.py::PostgresWriteSideUnitOfWork.__exit__`.

## 4. `PRE_TRANSACTION` path

`_execute_pre_transaction_command(...)` moves reading and Compass work outside the write UOW, then repeats authoritative idempotency checking and append admission before writing. Source: `src/pipeline/transactional/postgres_write_side.py::PostgresTransactionalWriteSide._execute_pre_transaction_command`.

| Order | Function / input → output | Authority and early return |
|---:|---|---|
| 1 | `RequestSignature(...)` | fixes caller intent |
| 2 | `read_idempotency_store.check(signature)` → preliminary `IdempotencyDecision` | preliminary check; `REPLAY`/`CONFLICT` can return early; `finally` always rolls back the implicit read transaction; no candidate |
| 3 | `read_event_store.load(order_id)` → accepted history | loads the accepted-history view visible to the current implicit read transaction outside the write UOW; this is not a Compass durable snapshot; rollback closes only the read transaction and does not delete durable history |
| 4 | `_rehydrate_aggregate_from_history(...)` → `OrderAggregate` | rebuilds state from the history just loaded |
| 5 | `_build_validation_context(...)` → `ValidationContext` | records the previous event/version/status as observed by the read |
| 6 | `build_candidate_event(aggregate)` → `OrderEvent` | the candidate exists before stream preparation |
| 7 | `_invoke_validation(...)` → `ValidationDecision` plus optional `ValidationDecisionWithRuleEvidence` | uses the evidence-aware capability when present and the legacy decide-only fallback otherwise; `BLOCK` returns `VALIDATION_BLOCKED`; no write UOW, append, or new accepted event |
| 8 | enter `PostgresWriteSideUnitOfWork` | starts the write transaction |
| 9 | `uow.idempotency_store.check(signature)` → authoritative `IdempotencyDecision` | race-window re-check; `REPLAY`/`CONFLICT` can now return with current candidate validation evidence; explicit rollback |
| 10 | `gate.prepare_stream(order_id)` → `StreamAdmissionResult` | the current default `PRE_TRANSACTION + PostgresOptimisticAdmissionGate` always returns `ADMITTED`; generic orchestration retains a defensive rejection branch for an explicitly injected non-default/custom gate, where candidate and allowing validation exist but `AdmissionResult` is absent |
| 11 | `gate.append_if_admitted(...)` → `AdmissionResult` | performs append-time OCC arbitration against the pre-read version; this is the stale/concurrency rejection boundary for the current default PRE + optimistic composition; rejection rolls back |
| 12 | `idempotency_store.record(...)`, then evaluate `return PostgresWriteSideResult(ACCEPTED, ...)` | event and record share one UOW; the result object is built inside the block, clean `__exit__` commits, then the caller receives it |

Therefore:

```text
candidate exists
≠
append_if_admitted(...) was invoked
```

In the default PRE path, the authoritative idempotency re-check is the first proof of this invariant. A preliminary check can return `MISS`, allowing candidate construction and validation, while the authoritative write-UOW re-check later returns `REPLAY` or `CONFLICT` and ends the flow before `append_if_admitted(...)`.

For the current default `PRE_TRANSACTION + PostgresOptimisticAdmissionGate` composition, `prepare_stream(...)` always returns `ADMITTED`, so it does not normally produce a candidate-present stream rejection. The generic orchestration rejection branch and PR4 post-validation fixture cover only a defensive typed shape constructable with an explicitly injected non-default/custom gate.

If such a shape is constructed, PR4 maps it to `APPEND_ADMISSION_NOT_REACHED`: `AdmissionResult is None` proves that `append_if_admitted(...)` was not invoked, while candidate identity can already exist. This does not mean the default PRE runtime normally receives a rejected `prepare_stream(...)`. Sources: `src/pipeline/transactional/postgres_admission.py::PostgresOptimisticAdmissionGate.prepare_stream`, `src/compass/runtime/write_side_decision_receipt_mapping.py::_admission_disposition_for_result`, `tests/unit/compass/runtime/test_write_side_decision_receipt_mapping.py::test_non_default_post_validation_stream_rejections_map_to_append_admission_not_reached`.

Stream `STALE_WRITE` in the PR4 tests is also synthetic typed-domain verdict coverage. Current PostgreSQL stream-preparation gates do not produce it.

## 5. Write-side result construction

`PostgresWriteSideOutcome` describes only the normal orchestration outcome category. `PostgresWriteSideResult` preserves the outcome and supporting objects already produced by that lifecycle. It is not itself semantic classification or a receipt. Sources: `src/pipeline/transactional/postgres_write_side.py::PostgresWriteSideOutcome`, `src/pipeline/transactional/postgres_write_side.py::PostgresWriteSideResult`.

When the evidence-aware runtime capability is used, `validation_decision_evidence` preserves the carrier from that exact invocation and must own the identical `validation_decision` object. Its `observed_rule_violation` view may remain available on a later post-validation terminal result. That preserved observation is sibling evidence, not automatically the terminal semantic explanation. Legacy decide-only runtimes remain supported and produce no carrier.

| Result shape | Terminal / resolving lifecycle phase | Must exist | Must be absent / identity meaning | Transaction behavior |
|---|---|---|---|---|
| `ACCEPTED` | accepted-history write | `MISS`, admitted stream, ALLOW validation, admitted `AdmissionResult`, returned event | candidate, append accepted ID, and returned event ID must agree | append → idempotency record → build result in block → clean `__exit__` commit → caller receives result |
| `REPLAY` before candidate construction | IN authoritative or PRE preliminary idempotency check | `REPLAY` decision plus prior `IdempotencyRecord` | no current candidate; record event is the prior accepted event | PRE read-transaction rollback; IN UOW rollback |
| `REPLAY` at the post-validation authoritative re-check | PRE authoritative idempotency re-check after validation ALLOW | same plus ALLOW validation | current candidate can differ from prior accepted event; no stream/append evidence | explicit UOW rollback |
| `CONFLICT` before candidate construction | IN authoritative or PRE preliminary idempotency check | `CONFLICT` decision plus prior accepted record | no current candidate; record event is conflict evidence, not current acceptance | rollback |
| `CONFLICT` at the post-validation authoritative re-check | PRE authoritative idempotency re-check after validation ALLOW | same plus ALLOW validation | current candidate can exist and differ from the prior event; no stream/append evidence | explicit UOW rollback |
| `VALIDATION_BLOCKED` | Compass validation | `MISS` plus BLOCK validation | candidate exists; no accepted event or `AdmissionResult`; IN can carry admitted stream evidence, PRE does not | IN explicit rollback; PRE has not entered write UOW |
| pre-candidate stream rejection | stream preparation | `MISS` plus rejected `StreamAdmissionResult` | no validation, candidate, `AdmissionResult`, or accepted event; actual IN lifecycle shape | explicit UOW rollback |
| post-validation stream rejection | stream preparation | `MISS` plus rejected stream and ALLOW validation | current candidate; no `AdmissionResult` or accepted event; defensive typed shape only for non-default/custom composition | explicit UOW rollback |
| append `STALE_WRITE` | append admission | admitted stream, ALLOW validation, rejected `AdmissionResult` | current candidate; no accepted ID | explicit rollback |
| append `LOCK_TIMEOUT` | append admission | same with `LOCK_TIMEOUT` verdict | known typed technical rejection; no accepted event | explicit rollback |
| append `INFRASTRUCTURE_ERROR` | append admission | same with `INFRASTRUCTURE_ERROR` verdict | known typed technical rejection; no accepted event | explicit rollback |

In a conflict result, `accepted_event_id` belongs to the prior accepted record. It proves why the shared request identity conflicts with accepted history and does not mean that the current attempt was accepted. `subject = REQUEST` expresses the request-level conflict. The retained `IdempotencyRecord.signature` also describes only the prior accepted signature. Because the typed result does not preserve a complete current conflicting signature alongside it, the receipt cannot reconstruct two complete request intents.

`PostgresEventStore.append(...)` performs version/sequence checks and the `order_events` insert. `PostgresIdempotencyStore.record(...)` then writes the record. Both must be successfully committed by the same UOW to form durable success. Sources: `src/storage/postgres_event_store.py::PostgresEventStore.append`, `src/storage/postgres_idempotency_store.py::PostgresIdempotencyStore.record`, `tests/integration/pipeline/transactional/test_postgres_unit_of_work.py::test_successful_transaction_commits_event_and_idempotency_record`.

## 6. Stage 4A mapping

```text
PostgresWriteSideResult
    │
    ▼
map_postgres_write_side_result_to_semantic_outcome(...)
    │
    ├── validate basic result shape
    ├── select technical status
    ├── build reason / context / evidence
    └── map_runtime_technical_status(...)
    ▼
SemanticOutcome(boundary=LAYER_1_WRITE_SIDE, ...)
```

Stage 4A owns semantic interpretation. It first selects a technical status from the concrete outcome/verdict, then `map_runtime_technical_status(...)` determines `ok/category/semantic_code/severity/risk_level/reversibility`. For example, append `STALE_WRITE` selects `CONCURRENT_STATE_STALENESS`; that value is not `SemanticOutcome.category`, `SemanticOutcome.semantic_code`, or admission disposition. Sources: `src/compass/runtime/write_side_outcome_mapping.py::_technical_status_for_postgres_write_side_result`, `src/compass/runtime/technical_status_mapping.py::map_runtime_technical_status`.

`ValidationResult.verdict` preserves validation truth/evidence, while `ValidationDecision.action` preserves the enforcement response. They are not universally identical axes. `ValidationMode.OFF` can produce `ValidationVerdict.SKIPPED` with `EnforcementAction.ALLOW`. Source: `src/compass/transition/runtime.py::ValidationPolicy.decide`.

`SemanticOutcome.context` and `.evidence` are richer Stage 4A runtime payloads. The generic Stage 4B mapper intentionally does not inspect or copy them. PR4 preserves the Stage 4A semantic tuple and independently selects receipt evidence from the original typed result. Source: `tests/unit/compass/runtime/test_decision_receipt_mapping.py::test_mapper_does_not_copy_or_inspect_outcome_evidence`.

### Stage 4B.5 exact rule-evidence refinement

For the evidence-aware FullProof path, the current source chain is:

```text
candidate + ValidationContext
→ FullProofValidator.validate_with_rule_evidence(...)
→ FullProofValidationEvidence
   { ValidationResult, optional exact OrderRuleViolationEvidence }
→ ValidationRuntime.decide_with_rule_evidence(...)
→ ValidationDecisionWithRuleEvidence
→ PostgresWriteSideResult.validation_decision_evidence
```

Validation and policy evaluation each occur once. The producer emits exact rule identity at the executable predicate branch; no reason parsing, second pass, fallback re-validation, or evidence fabrication is used. Current FullProof production covers exactly six `TRANSITION_TRUTH` rules, not all 18 rules in the canonical Order correctness contract.

The separate, explicit PR7 path is:

```text
PostgresWriteSideResult
→ map_postgres_write_side_result_to_semantic_rule_feedback(...)
   ├── Stage 4A SemanticOutcome
   └── terminal exact rule refinement
→ PostgresWriteSideSemanticRuleFeedback
   { semantic_outcome, rule_refinement }
```

`VALIDATION_BLOCKED` requires exact `OrderRuleViolationEvidence` at this refined boundary. Every other terminal outcome returns `rule_refinement=None`, even when an earlier validation observation was preserved. This keeps validation observation separate from terminal explanation. PR7 does not change the write-side transaction and is not automatically invoked by write commands.

## 7. Stage 4B PR4 adapter

The public wrapper is:

```python
map_postgres_write_side_result_to_decision_receipt(
    *,
    receipt_id: UUID,
    outcome_id: UUID,
    result: PostgresWriteSideResult,
) -> DecisionReceipt
```

All three parameters are keyword-only. The adapter does not accept an arbitrary prebuilt `SemanticOutcome` and exposes no metadata/context/evidence/policy/retry/persistence parameters. Source: `tests/unit/compass/runtime/test_write_side_decision_receipt_mapping.py::test_public_wrapper_signature_is_exact_and_keyword_only`.

The adapter is implemented, but no production command path currently invokes
it. Its composition is covered by mapper unit tests. Durable receipt
serialization and PostgreSQL persistence are implemented through separate
explicit boundaries; automatic mapper-to-store materialization remains outside
this command path.

Actual call order and the question answered by each step:

| Order | Helper | Question |
|---:|---|---|
| 1 | `_validate_result_shape` | Do the outcome and nested typed evidence form a supported lifecycle? |
| 2 | Stage 4A mapper | What is the concrete result's semantic tuple? |
| 3 | `_select_identity` | Which typed sources provide order/request/candidate/accepted IDs, do they agree, and are UUIDs valid? |
| 4 | `_subject_for_result` | Which entity is this receipt primarily about? |
| 5 | `DecisionReceiptCorrelation(...)` | Which additional identities must be retained? |
| 6 | `_identity_source_for_result` | What is the provenance of the primary identity block? |
| 7 | `DecisionReceiptFlags()` | Leave all four governance propositions `NOT_EVALUATED` for later authorized evaluators. |
| 8 | `_admission_disposition_for_result` | What is the current attempt's candidate-level append-lifecycle fate? |
| 9 | `_evidence_summary_for_result` | Which compact typed facts are safe for the summary? |
| 10 | `map_semantic_outcome_to_decision_receipt` | How is the semantic tuple copied exactly and assembled with supporting contracts? |
| 11 | `DecisionReceipt.__post_init__` | Do type, JSON-safety, and cross-field admission invariants hold? |

## 8. End-to-end outcome matrix

`NE` means `NOT_EVALUATED`, not `FALSE`. Every row uses
`WRITE_SIDE_ADMISSION` as its evidence source. The displayed operator-review
and retry columns are `NE` in every row; `fallback_required` and
`rebuild_required` are also `NE` for every PR4 result.

| `PostgresWriteSideOutcome` / variant | Terminal / resolving lifecycle phase | `IdempotencyVerdict` | Current candidate identity | Accepted-history identity | `DecisionReceiptSubjectType` | `DecisionReceiptIdentitySource` | `EventAdmissionDisposition` | `technical_status` | `lifecycle_phase` | `operator_review_required` | `retry_candidate` |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `ACCEPTED` | accepted-history write / clean-exit commit | `miss` | current candidate | current accepted event | `ACCEPTED_EVENT` | `ACCEPTED_HISTORY` | `ADMITTED_TO_ACCEPTED_HISTORY` | `WRITE_SIDE_ACCEPTED` | `ACCEPTED_HISTORY` | NE | NE |
| pre-candidate `REPLAY` | IN authoritative or PRE preliminary idempotency check | `replay` | none | prior accepted record | `ACCEPTED_EVENT` | `ACCEPTED_HISTORY` | `MATCHED_EXISTING_ACCEPTED_EVENT` | `IDEMPOTENT_REPLAY` | `IDEMPOTENCY_CHECK` | NE | NE |
| post-validation authoritative `REPLAY` | PRE authoritative idempotency re-check | `replay` | current candidate | prior accepted record | `ACCEPTED_EVENT` | `ACCEPTED_HISTORY` | same as above | `IDEMPOTENT_REPLAY` | `IDEMPOTENCY_CHECK` | NE | NE |
| pre-candidate `CONFLICT` | IN authoritative or PRE preliminary idempotency check | `conflict` | none | prior accepted record | `REQUEST` | `WRITE_SIDE_CORRELATION` | `IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY` | `IDEMPOTENCY_CONFLICT` | `IDEMPOTENCY_CHECK` | NE | NE |
| post-validation authoritative `CONFLICT` | PRE authoritative idempotency re-check | `conflict` | current candidate | prior accepted record | `REQUEST` | `WRITE_SIDE_CORRELATION` | same as above | `IDEMPOTENCY_CONFLICT` | `IDEMPOTENCY_CHECK` | NE | NE |
| PRE `VALIDATION_BLOCKED` | Compass validation before write UOW | `miss` | current candidate | none | `CANDIDATE_EVENT` | `CANDIDATE_EVENT_IDENTITY` | `SEMANTIC_ADMISSION_REJECTED` | `COMPASS_VALIDATION_BLOCKED` | `VALIDATION` | NE | NE |
| IN `VALIDATION_BLOCKED` | Compass validation after admitted stream preparation | `miss` | current candidate | none | `CANDIDATE_EVENT` | `CANDIDATE_EVENT_IDENTITY` | same as above | `COMPASS_VALIDATION_BLOCKED` | `VALIDATION` | NE | NE |
| pre-candidate stream `STALE_WRITE` (synthetic) | stream preparation | `miss` | none | none | `ORDER` | `WRITE_SIDE_CORRELATION` | `APPEND_ADMISSION_NOT_REACHED` | `CONCURRENT_STATE_STALENESS` | `STREAM_PREPARATION` | NE | NE |
| post-validation stream `STALE_WRITE` (synthetic non-default/custom) | stream preparation | `miss` | current candidate | none | `CANDIDATE_EVENT` | `CANDIDATE_EVENT_IDENTITY` | `APPEND_ADMISSION_NOT_REACHED` | `CONCURRENT_STATE_STALENESS` | `STREAM_PREPARATION` | NE | NE |
| pre-candidate stream `LOCK_TIMEOUT` | stream preparation | `miss` | none | none | `ORDER` | `WRITE_SIDE_CORRELATION` | `APPEND_ADMISSION_NOT_REACHED` | `LOCK_TIMEOUT` | `STREAM_PREPARATION` | NE | NE |
| post-validation stream `LOCK_TIMEOUT` (non-default/custom) | stream preparation | `miss` | current candidate | none | `CANDIDATE_EVENT` | `CANDIDATE_EVENT_IDENTITY` | `APPEND_ADMISSION_NOT_REACHED` | `LOCK_TIMEOUT` | `STREAM_PREPARATION` | NE | NE |
| pre-candidate stream `INFRASTRUCTURE_ERROR` | stream preparation | `miss` | none | none | `ORDER` | `WRITE_SIDE_CORRELATION` | `APPEND_ADMISSION_NOT_REACHED` | `WRITE_SIDE_INFRASTRUCTURE_ERROR` | `STREAM_PREPARATION` | NE | NE |
| post-validation stream `INFRASTRUCTURE_ERROR` (non-default/custom) | stream preparation | `miss` | current candidate | none | `CANDIDATE_EVENT` | `CANDIDATE_EVENT_IDENTITY` | `APPEND_ADMISSION_NOT_REACHED` | `WRITE_SIDE_INFRASTRUCTURE_ERROR` | `STREAM_PREPARATION` | NE | NE |
| append `STALE_WRITE` | append admission | `miss` | current candidate | none | `CANDIDATE_EVENT` | `CANDIDATE_EVENT_IDENTITY` | `APPEND_CONCURRENCY_CONFLICT` | `CONCURRENT_STATE_STALENESS` | `APPEND_ADMISSION` | NE | NE |
| append `LOCK_TIMEOUT` | append admission | `miss` | current candidate | none | `CANDIDATE_EVENT` | `CANDIDATE_EVENT_IDENTITY` | `APPEND_TECHNICAL_FAILURE` | `LOCK_TIMEOUT` | `APPEND_ADMISSION` | NE | NE |
| append `INFRASTRUCTURE_ERROR` | append admission | `miss` | current candidate | none | `CANDIDATE_EVENT` | `CANDIDATE_EVENT_IDENTITY` | `APPEND_TECHNICAL_FAILURE` | `WRITE_SIDE_INFRASTRUCTURE_ERROR` | `APPEND_ADMISSION` | NE | NE |

Across the `APPEND_ADMISSION_NOT_REACHED` contract, current candidate identity is optional: the pre-candidate shape has none, while the non-default/custom post-validation shape has a current candidate. This is valid only where the typed lifecycle composition permits it. The default PRE + optimistic flow does not normally produce rejected stream preparation.

## 9. Three fully traced examples

### Example A: `ACCEPTED`

1. The entry point constructs `RequestSignature` and `CandidateEventBuilder`.
2. The authoritative check returns `IdempotencyDecision(MISS, record=None)`.
3. `prepare_stream(...)` returns an admitted `StreamAdmissionResult`.
4. History produces `OrderAggregate` and `ValidationContext`.
5. The builder produces an `OrderEvent` candidate.
6. The write side uses evidence-aware validation when available, producing an ALLOW `ValidationDecision` and its optional same-invocation carrier; a legacy decide-only runtime still produces the decision without that carrier.
7. `append_if_admitted(...)` calls event-store append and returns admitted `AdmissionResult`; candidate and accepted IDs match.
8. After the idempotency record is written, the `return PostgresWriteSideResult(ACCEPTED)` expression builds the result object inside the `with` block.
9. Clean `PostgresWriteSideUnitOfWork.__exit__` commits; the caller receives the result only after success.
10. Stage 4A produces the semantic tuple corresponding to `WRITE_SIDE_ACCEPTED`; an explicit PR7 mapping would expose `rule_refinement=None` because acceptance is the terminal explanation.
11. PR4 builds typed identity, an `ACCEPTED_EVENT` subject, accepted-history correlation, `ADMITTED_TO_ACCEPTED_HISTORY`, all-NE flags, and a compact summary.
12. The generic mapper and `DecisionReceipt` validation complete the in-memory receipt.

Source: `tests/unit/compass/runtime/test_write_side_decision_receipt_mapping.py::test_accepted_preserves_semantic_tuple_and_admission_identity`.

### Example B: `VALIDATION_BLOCKED`

The shared sequence is `RequestSignature` → `IdempotencyDecision(MISS)` → history/aggregate → candidate → evidence-aware FullProof validation → BLOCK `ValidationDecision` plus exact same-invocation rule evidence → `PostgresWriteSideResult(VALIDATION_BLOCKED)`. `AdmissionResult`, accepted event, and `IdempotencyRecord` are absent. A legacy decide-only runtime remains valid for the coarse write-side/Stage 4A path, but it cannot complete the stricter PR7 refined mapping without exact rule evidence.

Placement differs: the IN path already has an admitted `StreamAdmissionResult` and explicitly rolls back before returning; the PRE path has not created a write UOW, so `StreamAdmissionResult` is absent. Stage 4A produces the `COMPASS_VALIDATION_BLOCKED` semantic tuple. PR4 gets the candidate UUID from `ValidationResult.candidate_event_id` and builds a `CANDIDATE_EVENT` subject, `CANDIDATE_EVENT_IDENTITY` correlation, `SEMANTIC_ADMISSION_REJECTED`, and four NE flags. Source: `tests/unit/compass/runtime/test_write_side_decision_receipt_mapping.py::test_validation_blocked_uses_candidate_without_inventing_correlation`.

### Example C: append `ADMISSION_REJECTED / STALE_WRITE`

The sequence is `RequestSignature` → `MISS` → admitted `StreamAdmissionResult` → history/aggregate → candidate → ALLOW `ValidationDecision` → rejected `AdmissionResult(STALE_WRITE, candidate ID, accepted ID=None)`. The gate invoked `append_if_admitted(...)`, but version/continuity arbitration rejected the candidate. The write side explicitly rolls back and returns `PostgresWriteSideResult(ADMISSION_REJECTED)` with no accepted event or idempotency record.

Stage 4A uses `CONCURRENT_STATE_STALENESS` to build a concurrency-uncertain semantic tuple. PR4 builds candidate identity, a `CANDIDATE_EVENT` subject, `CANDIDATE_EVENT_IDENTITY` correlation, `APPEND_CONCURRENCY_CONFLICT`, `retry_candidate=NOT_EVALUATED`, and summary phase `APPEND_ADMISSION` with `append_admission_verdict=STALE_WRITE`. The typed verdict remains available for a later authorized evaluator; PR4 does not evaluate or authorize retry. Source: `tests/unit/compass/runtime/test_write_side_decision_receipt_mapping.py::test_append_rejection_maps_fate_and_leaves_flags_not_evaluated`.

## 10. Boundaries and non-goals

The current write-command and mapping flow:

- Does not automatically serialize or persist `DecisionReceipt`. The mapper returns a frozen in-memory contract. Strict serializer v1, the PostgreSQL store, and `PostgresDecisionReceiptTransactionOwner` exist, but a caller must explicitly construct and invoke those separate boundaries; normal write commands do not materialize receipts. Sources: `src/compass/runtime/decision_receipt_serialization.py::serialize_decision_receipt`, `src/storage/postgres_decision_receipt_store.py::PostgresDecisionReceiptStore`, `src/storage/postgres_decision_receipt_transaction_owner.py::PostgresDecisionReceiptTransactionOwner`.
- Does not automatically invoke PR7 semantic rule feedback. Callers explicitly compose it from one `PostgresWriteSideResult`. Preserved validation observation is exposed as terminal refinement only for `VALIDATION_BLOCKED`; other terminal outcomes use `rule_refinement=None`.
- Does not evaluate, execute, or authorize retry. `retry_candidate` remains `NOT_EVALUATED`; typed retry-relevant verdicts remain in the evidence summary for later authorized evaluators. Sources: `docs/adr/0018_producer_receipt_adapters_preserve_evidence_but_do_not_evaluate_governance_flags.md`, `tests/unit/compass/runtime/test_write_side_decision_receipt_mapping.py::test_every_supported_result_shape_leaves_flags_not_evaluated`.
- Does not provide ambiguous-commit reconciliation. `COMMIT_OUTCOME_UNRESOLVED` exists in the contract, but the current write-side adapter does not produce it. The current implementation also does not guarantee a subsequent rollback after commit failure. Source: `tests/unit/compass/runtime/test_write_side_decision_receipt_mapping.py::test_supported_write_side_results_do_not_map_to_commit_outcome_unresolved`.
- Does not include distributed routing, rate limiting, or hot-partition governance; the public wrapper has no corresponding input or side effect.
- Does not provide field-level identity provenance; `identity_source` describes the source of the primary correlation block.

The focused PR4 tests are mapper-composition unit tests. They are not real
PostgreSQL command-path integration tests and are not receipt-persistence
tests.
