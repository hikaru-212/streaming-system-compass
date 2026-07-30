# Write-Side Admission DecisionReceipt Mapping

## 1. Purpose

This note is the final implementation closeout for the Stage 4B PR4 mapping:

```text
PostgresWriteSideResult
→ existing Stage 4A write-side SemanticOutcome adapter
→ PR4 producer-specific receipt preparation
→ PR3 map_semantic_outcome_to_decision_receipt
→ DecisionReceipt
```

PR4 implements a narrow producer-specific wrapper around the stable PR3 generic
constructor. It is a result-shape validator and producer-specific typed
evidence mapper: it must preserve the Stage 4A semantic tuple, select receipt
inputs from typed write-side lifecycle evidence, and refuse contradictory or
malformed authority-bearing evidence. It is not a governance-flag evaluator.

PR4 must not make PR3 write-side-aware. It must not derive receipt authority
from arbitrary `SemanticOutcome.context` or `SemanticOutcome.evidence`.

The governing distinctions remain:

```text
technical status
≠ semantic outcome
≠ evidence path
≠ identity provenance
≠ admission fate
≠ flag evaluation state
≠ runtime action
```

## 2. Current production flow

`PostgresTransactionalWriteSide` currently supports two validation placements:

```text
IN_TRANSACTION
PRE_TRANSACTION
```

Both return the same typed `PostgresWriteSideResult`, but they can reach the
same final outcome with different lifecycle evidence.

The in-transaction order is:

```text
authoritative idempotency check
→ stream preparation
→ candidate creation
→ Compass validation
→ append-time admission
→ idempotency record
→ unit-of-work commit
```

The pre-transaction order is:

```text
preliminary idempotency check
→ accepted-history load
→ candidate creation
→ Compass validation
→ authoritative idempotency re-check
→ stream preparation
→ append-time admission
→ idempotency record
→ unit-of-work commit
```

This difference is material. A pre-transaction result may carry a
`ValidationDecision` and therefore a real `candidate_event_id` even when the
authoritative idempotency check or stream-preparation boundary prevented
append-time admission from being reached.

The Stage 4A adapter:

```text
map_postgres_write_side_result_to_semantic_outcome
```

validates part of the result shape, maps the result to one technical status,
pins the semantic boundary to `LAYER_1_WRITE_SIDE`, and constructs the existing
`SemanticOutcome`.

PR4 calls that adapter without caller-provided context or evidence
overrides. PR4 then prepares typed receipt inputs directly from
`PostgresWriteSideResult` and its owned nested contracts. The PR3 mapper
preserves the complete semantic tuple and constructs `DecisionReceipt`.

For every concrete result in this path:

```text
evidence_source = WRITE_SIDE_ADMISSION
```

This remains true for success, replay, semantic rejection, concurrency
conflict, lock timeout, and infrastructure failure.

## 3. Producer and outcome inventory

### `PostgresWriteSideOutcome`

The concrete result enum has five members:

| `PostgresWriteSideOutcome` | Required or normal nested evidence | Stage 4A technical status |
|---|---|---|
| `ACCEPTED` | `accepted_event`; production also carries admitted stream, validation, and append results | `WRITE_SIDE_ACCEPTED` |
| `REPLAY` | `IdempotencyDecision(REPLAY)` with an `IdempotencyRecord` and existing accepted event | `IDEMPOTENT_REPLAY` |
| `CONFLICT` | `IdempotencyDecision(CONFLICT)` with the prior `IdempotencyRecord` in production | `IDEMPOTENCY_CONFLICT` |
| `VALIDATION_BLOCKED` | `ValidationDecision` whose action blocks the candidate | `COMPASS_VALIDATION_BLOCKED` |
| `ADMISSION_REJECTED` | rejected `StreamAdmissionResult` or rejected `AdmissionResult` | depends on `AdmissionVerdict` |

### Write-side technical statuses

The current write-side status inventory is:

| Technical status | Current source | Stage 4A semantic outcome |
|---|---|---|
| `WRITE_SIDE_ACCEPTED` | concrete `ACCEPTED` result | `VALID` / `SEMANTICALLY_VALID` |
| `IDEMPOTENT_REPLAY` | concrete `REPLAY` result | `RETRY_CLASSIFIED` / `IDEMPOTENT_REPLAY_ALLOWED` |
| `IDEMPOTENCY_CONFLICT` | concrete `CONFLICT` result | `BLOCK_REQUIRED` / `SEMANTIC_CONFLICT_DETECTED` |
| `COMPASS_VALIDATION_BLOCKED` | concrete `VALIDATION_BLOCKED` result | `BLOCK_REQUIRED` / `SEMANTIC_CONFLICT_DETECTED` |
| `CONCURRENT_STATE_STALENESS` | `ADMISSION_REJECTED` plus `STALE_WRITE` | `CONCURRENCY_UNCERTAIN` / `CONCURRENCY_UNCERTAIN` |
| `LOCK_TIMEOUT` | `ADMISSION_REJECTED` plus `LOCK_TIMEOUT` | `CONCURRENCY_UNCERTAIN` / `CONCURRENCY_UNCERTAIN` |
| `WRITE_SIDE_INFRASTRUCTURE_ERROR` | `ADMISSION_REJECTED` plus `INFRASTRUCTURE_ERROR` | `ESCALATION_REQUIRED` / `REQUIRES_OPERATOR_REVIEW` |
| `OCC_CONFLICT_AFTER_VALIDATION` | present in the generic technical-status table, but not emitted by the current `PostgresWriteSideResult` adapter | `CONCURRENCY_UNCERTAIN` / `CONCURRENCY_UNCERTAIN` |

The current adapter maps append-time `STALE_WRITE` to
`CONCURRENT_STATE_STALENESS`, not `OCC_CONFLICT_AFTER_VALIDATION`. PR4 must not
invent an `OCC_CONFLICT_AFTER_VALIDATION` producer or remap the existing Stage
4A result.

`COMMIT_OUTCOME_UNRESOLVED` is an `EventAdmissionDisposition`, not a technical
status. No current production code produces a `PostgresWriteSideResult` for an
ambiguous commit, no reconciliation evidence is carried by the result, and the
only code references are the shared receipt contract and its contract tests.
PR4 must not map `WRITE_SIDE_INFRASTRUCTURE_ERROR` to
`COMMIT_OUTCOME_UNRESOLVED`.

### Lifecycle facts available on the result

| Typed source | Relevant fields and types | Authority boundary |
|---|---|---|
| `OrderEvent` | `event_id: str`, `request_id: str`, `order_id: str` | Accepted-history authority only when the event is the returned accepted event or comes from an accepted idempotency record |
| `RequestSignature` | `request_id: str`, `order_id: str` | Request/idempotency correlation; not candidate or accepted-event authority by itself |
| `ValidationResult` | `candidate_event_id: str`; arbitrary `metadata` | Candidate identity is typed; metadata is non-authoritative |
| `StreamAdmissionResult` | `order_id: str`, `verdict`, `reason` | Stream-preparation lifecycle evidence; it has no candidate event field |
| `AdmissionResult` | `candidate_event_id: str`, `accepted_event_id: str \| None`, `verdict`, `reason` | Append-time candidate and admission evidence |
| `PostgresWriteSideResult` | outcome and the nested values above | Producer-owned orchestration result |

`PostgresWriteSideResult` does not retain the current `RequestSignature` on a
miss. Consequently, fresh validation-blocked and admission-rejected results
usually cannot supply authoritative `request_id`. A pre-transaction
validation-blocked result also has no `StreamAdmissionResult`, so it cannot
supply typed `order_id`. Arbitrary `ValidationResult.metadata` must not fill
those gaps.

## 4. Complete mapping table

The table distinguishes lifecycle variants that share a technical status.
`CE` means `candidate_event_id`; `AE` means `accepted_event_id`.

| Concrete path | Semantic mapping already produced by Stage 4A | Subject | Correlation | Primary identity source | Admission disposition | Flags `(fallback, rebuild, operator review, retry candidate)` | Receipt-safe summary |
|---|---|---|---|---|---|---|---|
| `ACCEPTED` with admitted append evidence | `WRITE_SIDE_ACCEPTED` → `VALID` / `SEMANTICALLY_VALID` | `ACCEPTED_EVENT(AE)` | order, request, `CE`, `AE`; `CE == AE` | `ACCEPTED_HISTORY` | `ADMITTED_TO_ACCEPTED_HISTORY` | `(NE, NE, NE, NE)` | technical status, outcome, idempotency verdict, lifecycle phase, stream/validation/append verdicts |
| early `REPLAY`, before candidate creation | `IDEMPOTENT_REPLAY` → `RETRY_CLASSIFIED` / `IDEMPOTENT_REPLAY_ALLOWED` | `ACCEPTED_EVENT(AE)` | order and request from record/accepted event; `CE=None`; prior `AE` | `ACCEPTED_HISTORY` | `MATCHED_EXISTING_ACCEPTED_EVENT` | `(NE, NE, NE, NE)` | technical status, outcome, idempotency verdict, lifecycle phase |
| authoritative `REPLAY` after pre-transaction validation | same as above | `ACCEPTED_EVENT(AE)` | order and request from record/accepted event; candidate `CE`; prior `AE` | `ACCEPTED_HISTORY` | `MATCHED_EXISTING_ACCEPTED_EVENT` | `(NE, NE, NE, NE)` | technical status, outcome, idempotency verdict, lifecycle phase, validation verdict |
| early `CONFLICT`, before candidate creation | `IDEMPOTENCY_CONFLICT` → `BLOCK_REQUIRED` / `SEMANTIC_CONFLICT_DETECTED` | `REQUEST(request_id)` | request and prior-record order; `CE=None`; prior unrelated `AE` | `WRITE_SIDE_CORRELATION` | `IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY` | `(NE, NE, NE, NE)` | technical status, outcome, idempotency verdict, lifecycle phase |
| authoritative `CONFLICT` after pre-transaction validation | same as above | `REQUEST(request_id)` | request and prior-record order; candidate `CE`; prior unrelated `AE` | `WRITE_SIDE_CORRELATION` | `IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY` | `(NE, NE, NE, NE)` | technical status, outcome, idempotency verdict, lifecycle phase, validation verdict |
| `VALIDATION_BLOCKED` in transaction | `COMPASS_VALIDATION_BLOCKED` → `BLOCK_REQUIRED` / `SEMANTIC_CONFLICT_DETECTED` | `CANDIDATE_EVENT(CE)` | stream `order_id`; no authoritative request; `CE`; `AE=None` | `CANDIDATE_EVENT_IDENTITY` | `SEMANTIC_ADMISSION_REJECTED` | `(NE, NE, NE, NE)` | technical status, outcome, idempotency verdict, lifecycle phase, stream verdict, validation action/verdict/mode |
| `VALIDATION_BLOCKED` before transaction | same as above | `CANDIDATE_EVENT(CE)` | no typed order or request; `CE`; `AE=None` | `CANDIDATE_EVENT_IDENTITY` | `SEMANTIC_ADMISSION_REJECTED` | `(NE, NE, NE, NE)` | technical status, outcome, idempotency verdict, lifecycle phase, validation action/verdict/mode |
| stream-preparation `STALE_WRITE` before candidate creation | `CONCURRENT_STATE_STALENESS` → `CONCURRENCY_UNCERTAIN` | `ORDER(order_id)` | stream `order_id`; no request, `CE`, or `AE` | `WRITE_SIDE_CORRELATION` | `APPEND_ADMISSION_NOT_REACHED` | `(NE, NE, NE, NE)` | technical status, outcome, idempotency verdict, lifecycle phase, stream verdict |
| stream-preparation `STALE_WRITE` after pre-transaction validation | same as above | `CANDIDATE_EVENT(CE)` | stream `order_id`; `CE`; no request or `AE` | `CANDIDATE_EVENT_IDENTITY` | `APPEND_ADMISSION_NOT_REACHED` | `(NE, NE, NE, NE)` | technical status, outcome, idempotency verdict, lifecycle phase, stream and validation verdicts |
| append-time `STALE_WRITE` | `CONCURRENT_STATE_STALENESS` → `CONCURRENCY_UNCERTAIN` | `CANDIDATE_EVENT(CE)` | stream `order_id`; no authoritative request; `CE`; `AE=None` | `CANDIDATE_EVENT_IDENTITY` | `APPEND_CONCURRENCY_CONFLICT` | `(NE, NE, NE, NE)` | technical status, outcome, idempotency verdict, lifecycle phase, stream/validation/append verdicts |
| stream-preparation `LOCK_TIMEOUT` before candidate creation | `LOCK_TIMEOUT` → `CONCURRENCY_UNCERTAIN` | `ORDER(order_id)` | stream `order_id`; no request, `CE`, or `AE` | `WRITE_SIDE_CORRELATION` | `APPEND_ADMISSION_NOT_REACHED` | `(NE, NE, NE, NE)` | technical status, outcome, idempotency verdict, lifecycle phase, stream verdict |
| stream-preparation `LOCK_TIMEOUT` after pre-transaction validation | same as above | `CANDIDATE_EVENT(CE)` | stream `order_id`; `CE`; no request or `AE` | `CANDIDATE_EVENT_IDENTITY` | `APPEND_ADMISSION_NOT_REACHED` | `(NE, NE, NE, NE)` | technical status, outcome, idempotency verdict, lifecycle phase, stream and validation verdicts |
| append-time `LOCK_TIMEOUT` | same as above | `CANDIDATE_EVENT(CE)` | stream `order_id`; no authoritative request; `CE`; `AE=None` | `CANDIDATE_EVENT_IDENTITY` | `APPEND_TECHNICAL_FAILURE` | `(NE, NE, NE, NE)` | technical status, outcome, idempotency verdict, lifecycle phase, stream/validation/append verdicts |
| stream-preparation `INFRASTRUCTURE_ERROR` before candidate creation | `WRITE_SIDE_INFRASTRUCTURE_ERROR` → `ESCALATION_REQUIRED` / `REQUIRES_OPERATOR_REVIEW` | `ORDER(order_id)` | stream `order_id`; no request, `CE`, or `AE` | `WRITE_SIDE_CORRELATION` | `APPEND_ADMISSION_NOT_REACHED` | `(NE, NE, NE, NE)` | technical status, outcome, idempotency verdict, lifecycle phase, stream verdict |
| stream-preparation `INFRASTRUCTURE_ERROR` after pre-transaction validation | same as above | `CANDIDATE_EVENT(CE)` | stream `order_id`; `CE`; no request or `AE` | `CANDIDATE_EVENT_IDENTITY` | `APPEND_ADMISSION_NOT_REACHED` | `(NE, NE, NE, NE)` | technical status, outcome, idempotency verdict, lifecycle phase, stream and validation verdicts |
| append-time `INFRASTRUCTURE_ERROR` | same as above | `CANDIDATE_EVENT(CE)` | stream `order_id`; no authoritative request; `CE`; `AE=None` | `CANDIDATE_EVENT_IDENTITY` | `APPEND_TECHNICAL_FAILURE` | `(NE, NE, NE, NE)` | technical status, outcome, idempotency verdict, lifecycle phase, stream/validation/append verdicts |
| `OCC_CONFLICT_AFTER_VALIDATION` | generic mapping exists, but no current result path emits it | no mapping | no mapping | no mapping | no mapping | no mapping | no mapping |
| ambiguous commit | no current `PostgresWriteSideResult` producer | no mapping | no mapping | no mapping | do not invent `COMMIT_OUTCOME_UNRESOLVED` | no mapping | no mapping |

`NE` means `DecisionReceiptFlagState.NOT_EVALUATED`.

The current PostgreSQL gates do not produce stream-preparation `STALE_WRITE`;
that variant is constructable and accepted by the Stage 4A adapter because the
shared `AdmissionVerdict` is used at both phases. It remains in the audit so
the mapping is total over the current typed input domain. It must not be
described as a current concrete gate behavior.

## 5. Subject and correlation rules

Subject selection follows the object whose fate or authority the receipt
primarily records:

```text
newly admitted candidate
→ ACCEPTED_EVENT

idempotent replay matched to history
→ ACCEPTED_EVENT

idempotency conflict
→ REQUEST

semantic validation rejection
→ CANDIDATE_EVENT

stream failure before candidate creation
→ ORDER

stream or append failure after candidate creation
→ CANDIDATE_EVENT
```

`subject_id` remains a string. For event subjects it is the canonical string
form of the parsed UUID. The same parsed UUID is stored in the corresponding
typed correlation field.

Correlation fields must be selected from typed evidence:

- `order_id` comes from an accepted event, a `StreamAdmissionResult`, or an
  `IdempotencyRecord.signature`, with contradiction checks across all present
  typed sources.
- `request_id` comes from an accepted event or
  `IdempotencyRecord.signature`, with contradiction checks. A miss does not
  retain the current request signature, so PR4 must leave it absent.
- `candidate_event_id` comes from `AdmissionResult.candidate_event_id` when
  append-time evidence exists, otherwise from
  `ValidationResult.candidate_event_id`. If both exist, they must parse and
  compare equal.
- `accepted_event_id` comes only from an accepted event returned as accepted
  history or from the accepted event in an `IdempotencyRecord`.

For `IDEMPOTENCY_CONFLICT`, the record's `accepted_event_id` belongs to the
prior accepted request. It must never be described as the accepted identity of
the current conflicting attempt. The prior record's `order_id` may also differ
from the current conflicting request's order, which is not retained by
`PostgresWriteSideResult`.

PR4 must not derive admission fate from whether these fields are null. The
typed lifecycle outcome and nested verdict determine the fate.

## 6. Identity-source rules

The primary `DecisionReceiptIdentitySource` is:

| Receipt shape | Primary identity source |
|---|---|
| Newly accepted event | `ACCEPTED_HISTORY` |
| Early or late idempotent replay | `ACCEPTED_HISTORY` |
| Idempotency conflict centered on the request | `WRITE_SIDE_CORRELATION` |
| Validation-blocked candidate | `CANDIDATE_EVENT_IDENTITY` |
| Stream rejection before a candidate exists | `WRITE_SIDE_CORRELATION` |
| Stream or append rejection after a candidate exists | `CANDIDATE_EVENT_IDENTITY` |

This field is primary-block provenance, not field-level provenance. A replay
may have a candidate ID from candidate evidence and an accepted ID from
accepted history. An idempotency-conflict receipt may have request correlation,
a candidate ID, and a prior accepted ID from different sources.

ADR 0017 explicitly accepts this current limitation. PR4 must document the
mixed provenance in its tests and must not imply that one primary source grants
the same authority to every correlation field.

## 7. UUID conversion boundary

The actual producer types are:

```text
order_id: str
request_id: str
OrderEvent.event_id: str
ValidationResult.candidate_event_id: str
AdmissionResult.candidate_event_id: str
AdmissionResult.accepted_event_id: str | None
```

`DecisionReceiptCorrelation.order_id` and `.request_id` remain strings.

`DecisionReceiptCorrelation.candidate_event_id` and `.accepted_event_id`
require native `UUID` values.

PR4 owns the conversion:

```python
UUID(producer_event_id)
```

Parsing occurs only after the typed provenance source has been selected and
before constructing `DecisionReceiptSubject`,
`DecisionReceiptCorrelation`, or `DecisionReceiptAdmissionEvidence`.

The production event factory currently emits canonical UUIDv4 strings, and
PostgreSQL hydration converts stored UUID values back to strings. The public
dataclasses nevertheless accept arbitrary strings, and existing Stage 4A unit
fixtures use non-UUID placeholders. PR4 therefore must validate rather than
assume.

Malformed behavior is fail-closed:

```text
blank event ID
non-UUID event ID
contradictory parsed candidate IDs
contradictory accepted IDs
admitted candidate and accepted IDs that differ
→ raise ValueError
→ do not construct a normal DecisionReceipt
```

PR4 must not silently drop a malformed identifier, move it into metadata,
replace it with a generated UUID, or downgrade its provenance to `UNKNOWN`.

`receipt_id` and `outcome_id` are already native UUID inputs owned by the
caller. The wrapper must not generate them internally.

## 8. Admission-disposition mapping

Admission disposition comes from concrete lifecycle evidence:

```text
ACCEPTED + admitted append result + matching event identity
→ ADMITTED_TO_ACCEPTED_HISTORY

REPLAY + accepted idempotency record
→ MATCHED_EXISTING_ACCEPTED_EVENT

CONFLICT + accepted idempotency record
→ IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY

VALIDATION_BLOCKED + blocking validation decision
→ SEMANTIC_ADMISSION_REJECTED

append-time STALE_WRITE
→ APPEND_CONCURRENCY_CONFLICT

append-time LOCK_TIMEOUT or INFRASTRUCTURE_ERROR
→ APPEND_TECHNICAL_FAILURE

stream rejection, before or after candidate construction
→ APPEND_ADMISSION_NOT_REACHED
```

The following mappings are forbidden:

```text
accepted_event_id present
→ infer admitted

candidate_event_id absent
→ infer append admission not reached

CONCURRENCY_UNCERTAIN semantic code
→ infer append conflict

WRITE_SIDE_INFRASTRUCTURE_ERROR
→ COMMIT_OUTCOME_UNRESOLVED
```

The implemented admission-fate refinement represents all three formerly
blocked shapes without `UNKNOWN` or omitted evidence:

- `APPEND_ADMISSION_NOT_REACHED` means `append_if_admitted(...)` was not
  invoked. It permits an optional candidate while continuing to forbid an
  accepted event.
- `IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY` requires the prior accepted
  event and permits an optional current candidate.
- `APPEND_TECHNICAL_FAILURE` requires a candidate and forbids an accepted
  event.

`COMMIT_OUTCOME_UNRESOLVED` remains reserved for a future producer that reports
a genuinely ambiguous commit and carries reconciliation evidence. No such
producer exists in the current write-side path.

## 9. Flag-state mapping

[ADR 0018](../../adr/0018_producer_receipt_adapters_preserve_evidence_but_do_not_evaluate_governance_flags.md)
establishes that producer-specific receipt adapters preserve evidence but do
not evaluate governance flags. Therefore every PR4 result supplies:

```text
fallback_required
rebuild_required
operator_review_required
retry_candidate
→ NOT_EVALUATED
```

Typed verdicts such as `STALE_WRITE`, `LOCK_TIMEOUT`, and
`INFRASTRUCTURE_ERROR` remain available as producer evidence. They do not by
themselves complete a governance proposition. `TRUE` and `FALSE` require an
authorized later evaluator, and `FALSE` must not be used as a default.

`ACCEPTED` is not special-cased to `FALSE`: PR4 runs no flag evaluator.
Leaving all four fields `NOT_EVALUATED` preserves the distinction between an
unevaluated proposition and a completed negative conclusion.

## 10. Evidence-summary vocabulary

PR4 defines one compact producer-owned vocabulary:

| Key | Value shape | Source |
|---|---|---|
| `technical_status` | exact Stage 4A status string | reconstructed from the typed result using the exact current Stage 4A status mapping |
| `write_side_outcome` | exact `PostgresWriteSideOutcome.value` | `result.outcome` |
| `idempotency_verdict` | exact `IdempotencyVerdict.value` | `result.idempotency_decision.verdict` |
| `lifecycle_phase` | `IDEMPOTENCY_CHECK`, `VALIDATION`, `STREAM_PREPARATION`, `APPEND_ADMISSION`, or `ACCEPTED_HISTORY` | selected from which typed result completed the path |
| `stream_admission_verdict` | exact `AdmissionVerdict.value` when present | `result.stream_admission_result.verdict` |
| `validation_action` | exact `EnforcementAction.value` when present | `result.validation_decision.action` |
| `validation_verdict` | exact `ValidationVerdict.value` when present | `result.validation_decision.validation_result.verdict` |
| `validation_mode` | exact `ValidationMode.value` when present | `result.validation_decision.validation_result.validation_mode` |
| `append_admission_verdict` | exact `AdmissionVerdict.value` when present | `result.admission_result.verdict` |

Absent optional evidence means the key is omitted rather than converted into a
false assertion.

The receipt `reason` already preserves the Stage 4A reason. Producer reason
strings need not be duplicated in `evidence_summary`.

The vocabulary intentionally excludes:

```text
result_type
Python class names
full SemanticOutcome.context
full SemanticOutcome.evidence
ValidationResult.metadata
raw OrderEvent
RequestSignature payload and amount
exception objects or stack traces
database details
```

Typed identity belongs in `subject` and `correlation`, not duplicated in
flexible evidence.

## 11. Metadata boundary

PR4 produces:

```text
metadata = {}
```

Protected identity-like metadata keys do not override or supplement typed
fields. Arbitrary `SemanticOutcome.context`, `SemanticOutcome.evidence`,
`ValidationResult.metadata`, `result_type`, validator class names, and caller
labels are not automatically copied.

The current result carries no actor or cost measurement contract. PR4
therefore uses the existing default `DecisionReceiptActor` and
`DecisionReceiptCostSummary` rather than fabricate actor or timing evidence.

## 12. Mapping algorithm

The implemented wrapper algorithm is:

1. Require native UUID `receipt_id` and `outcome_id`.
2. Validate that `result.outcome` agrees with its typed idempotency,
   validation, stream-admission, append-admission, and accepted-event evidence.
3. Reject contradictory order, request, candidate-event, or accepted-event
   identities across all present typed sources.
4. Call `map_postgres_write_side_result_to_semantic_outcome` with
   `outcome_id` and `result` only. Do not expose its caller context/evidence
   override parameters through the PR4 wrapper.
5. Preserve the Stage 4A semantic tuple without remapping it.
6. Select `WRITE_SIDE_ADMISSION`.
7. Select subject and correlation from the typed result using Sections 5 and
   6.
8. Parse every selected candidate or accepted event string with `UUID(...)`;
   fail closed on malformed input.
9. Select admission disposition from the concrete lifecycle evidence, not
   nullable identifiers or semantic wording.
10. Supply default `DecisionReceiptFlags` so every flag remains
    `NOT_EVALUATED`.
11. Build only the evidence-summary keys in Section 10.
12. Pass the semantic outcome and explicitly prepared supporting contracts to
    `map_semantic_outcome_to_decision_receipt`.
13. Let the existing `DecisionReceipt` contract enforce typed cross-field and
    JSON-safety invariants.

PR4 does not accept an arbitrary prebuilt `SemanticOutcome`. The concrete
`PostgresWriteSideResult` is required so the wrapper retains producer
ownership of identity, lifecycle, disposition, and evidence selection.

## 13. Implemented production file and public function

The narrow production file is:

```text
src/compass/runtime/write_side_decision_receipt_mapping.py
```

The public function is:

```python
def map_postgres_write_side_result_to_decision_receipt(
    *,
    receipt_id: UUID,
    outcome_id: UUID,
    result: PostgresWriteSideResult,
) -> DecisionReceipt:
    ...
```

The function:

```text
construct the Stage 4A SemanticOutcome through the existing adapter
prepare producer-specific receipt evidence from the typed result
call map_semantic_outcome_to_decision_receipt
```

No generic selector framework, registry, callback extractor, policy engine,
retry engine, serializer, persistence adapter, or PR3 modification was needed.

The implemented public surface remains the module-level `__all__`; PR4 did not
modify `src/compass/runtime/__init__.py`.

## 14. Implemented unit-test coverage

The unit suite uses canonical UUID strings for all event IDs.

| Test group | Covered cases |
|---|---|
| Semantic preservation | all concrete statuses preserve the exact Stage 4A tuple and reason |
| Evidence source | every concrete result uses `WRITE_SIDE_ADMISSION`, including lock and infrastructure failures |
| Accepted path | subject accepted event; parsed equal candidate/accepted UUIDs; admitted disposition |
| Replay | early replay without candidate; replay after pre-transaction validation with distinct candidate and accepted IDs |
| Idempotency conflict | early and post-validation shapes; prior accepted ID kept distinct from current candidate; conflict disposition enforced |
| Validation blocked | in-transaction order correlation; pre-transaction absence of typed order/request; semantic-rejection disposition |
| Stale write | pre-candidate stream form; post-validation stream form; append form; only append form maps to append conflict |
| Lock timeout | pre-candidate stream form; post-validation stream form; append form; typed verdict remains in evidence |
| Infrastructure | stream and append forms; typed verdict remains in evidence; never commit-outcome unresolved |
| Flags | every supported write-side result leaves all four flags `NOT_EVALUATED` |
| UUID boundary | malformed accepted event, idempotency record event, validation candidate, and append candidate all fail closed |
| Contradictions | accepted event versus admission IDs; validation versus append candidate; record signature versus accepted event order/request; rejected append carrying accepted ID |
| Evidence summary | exact compact vocabulary; absent optional keys omitted; no reasons duplicated |
| Metadata | no context/evidence/validation metadata wholesale copy; metadata remains empty |
| Generic status without producer | `OCC_CONFLICT_AFTER_VALIDATION` is not fabricated from a result |
| Ambiguous commit | no current result maps to `COMMIT_OUTCOME_UNRESOLVED` |
| Non-goals | no runtime action, strategy, retry authorization, serialization, persistence, or side effect |

Tests also prove that the wrapper does not mutate write-side state and does not
generate `receipt_id` or `outcome_id`.

## 15. Shared-contract checkpoint

The implementation confirms that PR4 is represented without changing:

```text
src/compass/runtime/decision_receipt.py
src/compass/runtime/decision_receipt_mapping.py
src/compass/runtime/json_types.py
src/compass/runtime/semantic_outcome.py
```

The PR3 mapper, JSON-safe boundary, semantic tuple, subject types, UUID
correlation fields, evidence source, flag states, and admitted/replay/semantic
rejection/append-concurrency invariants were sufficient; PR4 required no
further shared-contract changes.

The implemented admission-fate contracts resolve the representation gaps.
`APPEND_ADMISSION_NOT_REACHED` permits an optional candidate, and the shared
enum supplies
`IDEMPOTENCY_CONFLICT_WITH_ACCEPTED_HISTORY` and
`APPEND_TECHNICAL_FAILURE` with the cross-field invariants described in
Section 8.

PR4 is represented without further changes to any shared contract listed
above.

The single primary `identity_source` also cannot encode field-level provenance
for replay and idempotency conflict. ADR 0017 records this as an accepted
limitation rather than a PR4 blocker, provided no consumer treats the primary
source as authority for every field.

## 16. Closeout state

PR4 producer evaluator ownership is resolved by ADR 0018. PR4 does not evaluate
governance flags. Admission-fate and metadata-shape decisions remain as
recorded in this note, and no remaining PR4 mapping decision blocks closeout.
This boundary does not authorize policy, strategy, retry-governance,
serialization, persistence, runtime invocation, or PR5 work.

## 17. Explicit non-goals

PR4 does not design or implement:

```text
changes to the PR3 generic mapper
changes to shared DecisionReceipt contracts in this task
generic evidence selectors
producer registries
callback extractors
read-side or snapshot receipt mapping
PR5
serialization
schema versioning
persistence
SQL migrations
PR6
DiagnosticTrace or ResolutionTrace
Measurement Matrix
RuntimeDecisionPolicy
StrategySelector
RetryGovernance
retry safety or authorization
automatic retry
fallback execution
rebuild execution
operator-review execution
accepted-history mutation
idempotency mutation
write-side orchestration changes
```

The implemented wrapper is evidence preparation only. `DecisionReceipt` remains
governance evidence, not a runtime action.
