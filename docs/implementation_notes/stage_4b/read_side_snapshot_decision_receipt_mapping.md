# Read-Side / Snapshot DecisionReceipt Mapping

## 1. Purpose

This note records the approved Stage 4B PR5 mapping boundary:

```text
ReplayValidationResult
ProjectionSnapshotReplayValidationResult
ProjectionSnapshotAssistedResolutionResult
→ DecisionReceipt
```

The PR5 adapter must remain a producer-specific preparation layer around the
stable PR3 generic constructor:

```text
typed producer result
→ existing Stage 4A SemanticOutcome adapter
→ producer-owned receipt inputs
→ map_semantic_outcome_to_decision_receipt
→ DecisionReceipt
```

The approved mapping preserves these distinctions:

```text
technical status
≠ semantic outcome
≠ evidence path
≠ observed boundary
≠ root cause
≠ identity provenance
≠ flag evaluation state
≠ runtime action
```

The three producer families are audited separately. A shared status name does
not create a shared evidence source, subject, identity source, flag conclusion,
or evidence-summary vocabulary.

## 2. Producer flows and approved PR5 composition

### 2.1 Durable read-side replay validation

```text
DurableReplayValidator.validate_order(order_id)
→ ReplayValidationResult
→ map_replay_validation_result_to_semantic_outcome
→ SemanticOutcome(boundary=LAYER_2_READ_SIDE)
→ PR5 read-side receipt preparation
→ map_semantic_outcome_to_decision_receipt
→ DecisionReceipt
```

`DurableReplayValidator` loads accepted history for one order, reconstructs
expected projection state through the canonical reducer, loads persisted
projection state, and compares the two. It does not mutate accepted history,
projection state, or checkpoint progress and does not execute recovery policy.

### 2.2 Projection snapshot trust validation

```text
ProjectionSnapshotReplayValidator.validate_order(order_id)
→ ProjectionSnapshotReplayValidationResult
→ map_projection_snapshot_replay_validation_result_to_semantic_outcome
→ SemanticOutcome(boundary=SNAPSHOT_TRUST)
→ PR5 snapshot-trust receipt preparation
→ map_semantic_outcome_to_decision_receipt
→ DecisionReceipt
```

The validator independently reconstructs `authority_state` from accepted
history, loads the latest projection snapshot, validates its boundary, replays
projection tail events using:

```text
same order_id
+ sequence > snapshot.source_event_sequence
+ ORDER BY sequence ASC
```

The validator requires every returned tail record to be the exact next
order-local sequence. The result may preserve snapshot lineage even when
validation fails, but it does not expose `source_event_sequence`. Snapshot
lineage is not accepted-history authority.

### 2.3 Snapshot-assisted projection resolution

```text
ProjectionSnapshotAssistedStateResolver.resolve_order(
    order_id,
    trusted_snapshot_id=...
)
→ ProjectionSnapshotAssistedResolutionResult
→ map_projection_snapshot_assisted_resolution_result_to_semantic_outcome
→ SemanticOutcome(boundary=SNAPSHOT_TRUST)
→ PR5 snapshot-assisted receipt preparation
→ map_semantic_outcome_to_decision_receipt
→ DecisionReceipt
```

The resolver consumes a caller-qualified snapshot identifier, loads that exact
snapshot, checks resolver compatibility, and replays a same-order tail after
the snapshot's `source_event_sequence` in ascending, contiguous order-local
sequence. The result does not expose that source sequence. The resolver does
not replay accepted history and does not expose `authority_state`.
Consequently, it cannot prove snapshot equivalence to accepted-history
authority. Its failures identify an observed snapshot-assisted boundary, not
necessarily a snapshot root cause.

### 2.4 PostgreSQL observation boundary

The PostgreSQL replay, snapshot-validation, and snapshot-assisted orchestration
boundaries may require:

```text
same connection
+ top-level transaction
+ REPEATABLE READ
+ READ ONLY
```

Those requirements make the related PostgreSQL reads one database observation.
The generic result dataclasses do not attest which orchestration produced a
constructable result. Each PR5 adapter must therefore map only the typed result
evidence and must not claim that every result was produced under the PostgreSQL
observation boundary.

### 2.5 Stable PR3 boundary

`map_semantic_outcome_to_decision_receipt` preserves the typed semantic tuple
and accepts explicit receipt inputs. It does not inspect or copy
`SemanticOutcome.context` or `SemanticOutcome.evidence`, infer evidence source,
infer identity provenance, derive flags, select runtime action, or persist a
receipt.

PR5 must not make the PR3 mapper read-side-aware. All producer interpretation
belongs in the three narrow PR5 wrappers.

## 3. Producer and status inventories

The current production enums define exactly the following statuses.

### 3.1 `ReplayValidationResult`

| Status | Concrete production evidence |
|---|---|
| `MATCH` | Accepted history is non-empty; `expected_state` and `persisted_state` are present and equal. |
| `MISSING_PROJECTION` | Accepted history is non-empty; `expected_state` is present and `persisted_state` is absent. |
| `DRIFT` | Accepted history is non-empty; both states are present and differ. |
| `NO_ACCEPTED_HISTORY` | No accepted history exists for the requested order; `expected_state` is absent. `persisted_state` may be present or absent because the validator still loads it. |

### 3.2 `ProjectionSnapshotReplayValidationResult`

| Status | Concrete production evidence |
|---|---|
| `MATCH` | A snapshot was loaded; snapshot-assisted replay and accepted-history replay completed; both states are present and equal. |
| `MISSING_SNAPSHOT` | Accepted history replay completed and `authority_state` is present; no snapshot was loaded. |
| `INVALID_SNAPSHOT_BOUNDARY` | A snapshot was loaded, its boundary or hydration contract failed, and `authority_state` is present. |
| `TAIL_EVENT_SOURCE_CONTRACT_VIOLATION` | A snapshot was loaded and hydrated, `authority_state` exists, and the tail source returned a different-order record or a non-contiguous order-local event sequence. |
| `SNAPSHOT_ASSISTED_DRIFT` | A loaded snapshot path either failed reducer application or completed with state different from `authority_state`; this does not isolate the snapshot as root cause. |
| `NO_ACCEPTED_HISTORY_FOR_ORDER` | Accepted history is absent for the requested order; neither comparison state exists. A previously loaded snapshot may or may not exist and, when present, its lineage is preserved. |

### 3.3 `ProjectionSnapshotAssistedResolutionResult`

| Status | Concrete production evidence |
|---|---|
| `RESOLVED_FROM_SNAPSHOT` | The requested snapshot was loaded and compatible; tail replay completed; `resolved_state` is present. |
| `MISSING_SNAPSHOT` | A specific requested snapshot identifier was not found; that identifier is an observed request reference, not loaded snapshot lineage. |
| `INVALID_SNAPSHOT_PRECONDITION` | No `trusted_snapshot_id` was supplied; no snapshot lookup or lineage observation completed. |
| `INVALID_SNAPSHOT_COMPATIBILITY` | A snapshot was loaded, but its order, boundary, schema, reducer, or state contract is incompatible with the resolver. |
| `TAIL_EVENT_SOURCE_CONTRACT_VIOLATION` | A compatible snapshot was loaded, but the tail source returned a different-order record or a non-contiguous order-local event sequence. |
| `TAIL_REPLAY_FAILED` | A compatible snapshot was loaded, but reducer application over the tail failed; the result deliberately exposes no partial `resolved_state`. |

No additional status exists in any of the three current production enums.

Snapshot validator `MATCH` proves only the producer's implemented comparison:
snapshot-assisted state equals the accepted-history replay state observed by
that producer invocation. It does not prove complete source-event lineage,
payload-integrity qualification, business authority, runtime authorization, or
completed negative governance-flag evaluations.

`RESOLVED_FROM_SNAPSHOT` proves only that the resolver produced state from the
selected snapshot and a contiguous order-local tail under its implemented
checks. It does not authorize irreversible use, fallback, snapshot promotion,
or retry.

### 3.4 Result-field boundary

The two snapshot result dataclasses expose, as applicable:

```text
order_id
snapshot_id
source_global_position
status
snapshot_assisted_state / authority_state / resolved_state
reason
```

PR5 uses the state-valued fields only to derive compact state-presence evidence.
It must not copy the state objects into the receipt.

The result dataclasses do not expose:

```text
source_event_id
source_event_sequence
projection_name
projection_epoch
```

PR5 must not recover those facts from snapshot objects, state objects,
`SemanticOutcome` mappings, context, metadata, caller mappings, or storage
lookups.

## 4. Three separate mapping tables

The semantic tuple notation used below is:

```text
ok / boundary / category / semantic_code / severity / risk / reversibility
```

Flag notation is:

```text
F = fallback_required
R = rebuild_required
O = operator_review_required
T = retry_candidate
NE = NOT_EVALUATED
```

All rows use `admission_evidence=None`, the default empty actor and cost
contracts, and producer metadata `{}`. No unavailable request or event identity
is populated; Section 7 enumerates the fields that must remain absent.

### 4.1 `ReplayValidationResult` mapping

Every row uses:

```text
evidence_source = READ_SIDE_PATH
correlation.identity_source = READ_SIDE_OBSERVATION
correlation.order_id = result.order_id
```

| Status | Stage 4A semantic tuple | Subject | Other correlation | Flags `F/R/O/T` | Direct evidence summary |
|---|---|---|---|---|---|
| `MATCH` | `true / LAYER_2_READ_SIDE / VALID / SEMANTICALLY_VALID / INFO / LOW / REVERSIBLE` | `PROJECTION(result.order_id)` | Snapshot and event fields absent | `NE/NE/NE/NE` | `technical_status=MATCH`; `expected_state_present=true`; `persisted_state_present=true` |
| `MISSING_PROJECTION` | `false / LAYER_2_READ_SIDE / REBUILD_REQUIRED / REQUIRES_REBUILD / WARNING / MEDIUM / REBUILDABLE` | `PROJECTION(result.order_id)` | Snapshot and event fields absent | `NE/NE/NE/NE` | `technical_status=MISSING_PROJECTION`; `expected_state_present=true`; `persisted_state_present=false` |
| `DRIFT` | `false / LAYER_2_READ_SIDE / DRIFT / DRIFT_DETECTED / ERROR / HIGH / REBUILDABLE` | `PROJECTION(result.order_id)` | Snapshot and event fields absent | `NE/NE/NE/NE` | `technical_status=DRIFT`; `expected_state_present=true`; `persisted_state_present=true` |
| `NO_ACCEPTED_HISTORY` | `false / LAYER_2_READ_SIDE / UNRESOLVED / RUNTIME_UNRESOLVED / WARNING / UNKNOWN / UNKNOWN` | `ORDER(result.order_id)` | Snapshot and event fields absent | `NE/NE/NE/NE` | `technical_status=NO_ACCEPTED_HISTORY`; `expected_state_present=false`; `persisted_state_present=(result.persisted_state is not None)` |

`PROJECTION(result.order_id)` means the projection subject is keyed by the
order identifier; it does not claim that projection identity is accepted
business truth. `NO_ACCEPTED_HISTORY` uses an `ORDER` subject because the
completed observation is the absence of accepted history for that requested
order, not a completed projection comparison.

### 4.2 `ProjectionSnapshotReplayValidationResult` mapping

Every row uses:

```text
evidence_source = SNAPSHOT_TRUST_PATH
correlation.order_id = result.order_id
correlation.snapshot_id = result.snapshot_id
correlation.source_global_position = result.source_global_position
```

The correlation omits request and event identifiers.

| Status | Stage 4A semantic tuple | Subject | Primary identity source | Flags `F/R/O/T` | Direct evidence summary |
|---|---|---|---|---|---|
| `MATCH` | `true / SNAPSHOT_TRUST / VALID / SEMANTICALLY_VALID / INFO / LOW / REVERSIBLE` | `SNAPSHOT(str(result.snapshot_id))` | `SNAPSHOT_LINEAGE` | `NE/NE/NE/NE` | `technical_status=MATCH`; `snapshot_artifact_present=true`; `snapshot_assisted_state_present=true`; `authority_state_present=true` |
| `MISSING_SNAPSHOT` | `false / SNAPSHOT_TRUST / FALLBACK_REQUIRED / FAST_PATH_UNAVAILABLE / WARNING / MEDIUM / REVERSIBLE` | `SNAPSHOT(None)` | `READ_SIDE_OBSERVATION` | `NE/NE/NE/NE` | `technical_status=MISSING_SNAPSHOT`; `snapshot_artifact_present=false`; `snapshot_assisted_state_present=false`; `authority_state_present=true` |
| `INVALID_SNAPSHOT_BOUNDARY` | `false / SNAPSHOT_TRUST / UNTRUSTED / DERIVED_STATE_UNTRUSTED / ERROR / HIGH / REBUILDABLE` | `SNAPSHOT(str(result.snapshot_id))` | `SNAPSHOT_LINEAGE` | `NE/NE/NE/NE` | `technical_status=INVALID_SNAPSHOT_BOUNDARY`; `snapshot_artifact_present=true`; `snapshot_assisted_state_present=false`; `authority_state_present=true` |
| `TAIL_EVENT_SOURCE_CONTRACT_VIOLATION` | `false / SNAPSHOT_TRUST / UNRESOLVED / RUNTIME_UNRESOLVED / ERROR / HIGH / UNKNOWN` | `RUNTIME(None)` | `SNAPSHOT_LINEAGE` | `NE/NE/NE/NE` | `technical_status=TAIL_EVENT_SOURCE_CONTRACT_VIOLATION`; `snapshot_artifact_present=true`; `snapshot_assisted_state_present=true`; `authority_state_present=true` |
| `SNAPSHOT_ASSISTED_DRIFT` | `false / SNAPSHOT_TRUST / DRIFT / DRIFT_DETECTED / ERROR / HIGH / REBUILDABLE` | `PROJECTION(result.order_id)` | `SNAPSHOT_LINEAGE` | `NE/NE/NE/NE` | `technical_status=SNAPSHOT_ASSISTED_DRIFT`; `snapshot_artifact_present=true`; `snapshot_assisted_state_present=true`; `authority_state_present=true` |
| `NO_ACCEPTED_HISTORY_FOR_ORDER` | `false / SNAPSHOT_TRUST / UNRESOLVED / RUNTIME_UNRESOLVED / WARNING / UNKNOWN / UNKNOWN` | `ORDER(result.order_id)` | `SNAPSHOT_LINEAGE` when a loaded snapshot supplied both lineage fields; otherwise `READ_SIDE_OBSERVATION` | `NE/NE/NE/NE` | `technical_status=NO_ACCEPTED_HISTORY_FOR_ORDER`; `snapshot_artifact_present=(result.snapshot_id is not None)`; `snapshot_assisted_state_present=false`; `authority_state_present=false` |

The `RUNTIME` subject for a tail-source contract violation prevents the loaded
snapshot from being labeled as the cause when the source returns a
different-order record or a non-contiguous order-local sequence.
The `PROJECTION` subject for `SNAPSHOT_ASSISTED_DRIFT` records the observed
state disagreement without asserting whether the snapshot payload, tail
source, or another reconstruction input caused it.

### 4.3 `ProjectionSnapshotAssistedResolutionResult` mapping

Every row uses:

```text
evidence_source = SNAPSHOT_ASSISTED_PATH
correlation.order_id = result.order_id
correlation.snapshot_id = result.snapshot_id
correlation.source_global_position = result.source_global_position
```

The correlation omits request and event identifiers.

| Status | Stage 4A semantic tuple | Subject | Primary identity source | Flags `F/R/O/T` | Direct evidence summary |
|---|---|---|---|---|---|
| `RESOLVED_FROM_SNAPSHOT` | `true / SNAPSHOT_TRUST / VALID / SEMANTICALLY_VALID / INFO / LOW / REVERSIBLE` | `PROJECTION(result.order_id)` | `SNAPSHOT_LINEAGE` | `NE/NE/NE/NE` | `technical_status=RESOLVED_FROM_SNAPSHOT`; `snapshot_artifact_present=true`; `resolved_state_present=true` |
| `MISSING_SNAPSHOT` | `false / SNAPSHOT_TRUST / FALLBACK_REQUIRED / FAST_PATH_UNAVAILABLE / WARNING / MEDIUM / REVERSIBLE` | `SNAPSHOT(str(result.snapshot_id))` | `READ_SIDE_OBSERVATION` | `NE/NE/NE/NE` | `technical_status=MISSING_SNAPSHOT`; `snapshot_artifact_present=false`; `resolved_state_present=false` |
| `INVALID_SNAPSHOT_PRECONDITION` | `false / SNAPSHOT_TRUST / UNTRUSTED / DERIVED_STATE_UNTRUSTED / ERROR / HIGH / REBUILDABLE` | `RUNTIME(None)` | `READ_SIDE_OBSERVATION` | `NE/NE/NE/NE` | `technical_status=INVALID_SNAPSHOT_PRECONDITION`; `snapshot_artifact_present=false`; `resolved_state_present=false` |
| `INVALID_SNAPSHOT_COMPATIBILITY` | `false / SNAPSHOT_TRUST / UNTRUSTED / DERIVED_STATE_UNTRUSTED / ERROR / HIGH / REBUILDABLE` | `SNAPSHOT(str(result.snapshot_id))` | `SNAPSHOT_LINEAGE` | `NE/NE/NE/NE` | `technical_status=INVALID_SNAPSHOT_COMPATIBILITY`; `snapshot_artifact_present=true`; `resolved_state_present=false` |
| `TAIL_EVENT_SOURCE_CONTRACT_VIOLATION` | `false / SNAPSHOT_TRUST / UNRESOLVED / RUNTIME_UNRESOLVED / ERROR / HIGH / UNKNOWN` | `RUNTIME(None)` | `SNAPSHOT_LINEAGE` | `NE/NE/NE/NE` | `technical_status=TAIL_EVENT_SOURCE_CONTRACT_VIOLATION`; `snapshot_artifact_present=true`; `resolved_state_present=false` |
| `TAIL_REPLAY_FAILED` | `false / SNAPSHOT_TRUST / FALLBACK_REQUIRED / FAST_PATH_UNAVAILABLE / WARNING / MEDIUM / REVERSIBLE` | `RUNTIME(None)` | `SNAPSHOT_LINEAGE` | `NE/NE/NE/NE` | `technical_status=TAIL_REPLAY_FAILED`; `snapshot_artifact_present=true`; `resolved_state_present=false` |

For `MISSING_SNAPSHOT`, `result.snapshot_id` is the requested identifier that
failed lookup. It is not evidence that a snapshot artifact was loaded, so its
identity source is `READ_SIDE_OBSERVATION`, not `SNAPSHOT_LINEAGE`.

`TAIL_REPLAY_FAILED` uses a `RUNTIME` subject because the resolver proves only
that the assisted reconstruction attempt failed. It does not prove that the
snapshot, the accepted tail events, or the persisted projection is the root
cause.

## 5. Evidence-source rules

Evidence source is owned by the concrete producer:

| Producer | `DecisionReceiptEvidenceSource` |
|---|---|
| `ReplayValidationResult` | `READ_SIDE_PATH` |
| `ProjectionSnapshotReplayValidationResult` | `SNAPSHOT_TRUST_PATH` |
| `ProjectionSnapshotAssistedResolutionResult` | `SNAPSHOT_ASSISTED_PATH` |

The selection is constant for every status from a producer. It must not be
derived from:

```text
MATCH
MISSING_SNAPSHOT
SNAPSHOT_ASSISTED_DRIFT
TAIL_REPLAY_FAILED
ok
boundary
category
semantic_code
```

Both snapshot producers currently create `SemanticOutcome` with
`boundary=SNAPSHOT_TRUST`. That shared observed semantic boundary does not
collapse their different evidence paths.

## 6. Subject rules

Subject identifies the primary thing the receipt is about. It is selected from
the completed producer observation, not mechanically from
`SemanticOutcome.boundary`.

### 6.1 Read-side replay

```text
completed projection comparison or missing projection
→ PROJECTION keyed by order_id

no accepted history for the requested order
→ ORDER keyed by order_id
```

### 6.2 Snapshot trust

```text
snapshot match, absence, or invalid boundary
→ SNAPSHOT

tail event source contract failure
→ RUNTIME

state disagreement without isolated cause
→ PROJECTION keyed by order_id

no accepted history for the requested order
→ ORDER keyed by order_id
```

A missing snapshot has `subject_type=SNAPSHOT` and `subject_id=None`; absence is
the observation and no artifact identity may be invented.

### 6.3 Snapshot-assisted resolution

```text
resolved projection state
→ PROJECTION keyed by order_id

requested snapshot missing or loaded snapshot incompatible
→ SNAPSHOT

missing resolver precondition, tail-source contract failure,
or tail replay failure without isolated cause
→ RUNTIME
```

The requested identifier on resolver `MISSING_SNAPSHOT` may be the snapshot
subject ID, but `snapshot_artifact_present=false` and
`identity_source=READ_SIDE_OBSERVATION` must remain explicit.

## 7. Correlation and lineage rules

### 7.1 Fields that may be populated

PR5 may populate only fields carried by the typed result:

```text
order_id
snapshot_id
source_global_position
```

PR5 must leave these fields absent:

```text
request_id
candidate_event_id
accepted_event_id
```

The producer results also do not expose `source_event_id`,
`source_event_sequence`, `projection_name`, or `projection_epoch`. PR5 must not
reconstruct any absent identity or progress fact from state payloads, snapshot
metadata, accepted events that are not present on the result,
`SemanticOutcome.context`, `SemanticOutcome.evidence`, caller evidence, or
storage lookups.

### 7.2 Snapshot lineage

For the snapshot trust validator, a non-null `snapshot_id` and
`source_global_position` are copied from a loaded `ProjectionSnapshot`.

For the assisted resolver:

```text
MISSING_SNAPSHOT snapshot_id
= requested lookup reference
≠ loaded snapshot lineage

INVALID_SNAPSHOT_COMPATIBILITY and later branches
snapshot_id + source_global_position
= loaded snapshot lineage
```

`source_global_position` is a globally unique accepted-event
allocation/storage coordinate preserved as loaded snapshot lineage. It is not:

```text
commit order
complete committed-history frontier
snapshot-tail correctness cursor
global catch-up evidence
snapshot trust proof
accepted-history qualification
cross-order causal order
```

The repaired validator and resolver use the snapshot's unexposed
`source_event_sequence`, not `source_global_position`, to select and validate a
contiguous order-local tail.

### 7.3 Subject identity versus correlation identity

The two may come from different evidence:

| Case | Subject identity | Correlation identity |
|---|---|---|
| Read-side projection comparison | Projection key from `result.order_id` | Same read-side order observation |
| Snapshot match or invalid boundary | Loaded `snapshot_id` | Requested order plus snapshot lineage |
| Snapshot-assisted resolved projection | Projection key from `result.order_id` | Snapshot lineage used by the resolution |
| Tail-source or tail-replay failure | No runtime subject ID | Requested order plus snapshot lineage |
| Resolver missing snapshot | Requested snapshot reference | Requested order plus the same unfulfilled reference |

For a loaded snapshot whose `order_id` is incompatible with the requested
order, the result exposes the requested `order_id` plus loaded snapshot
lineage. The current correlation contract records one primary identity source,
not field-level provenance. Selecting `SNAPSHOT_LINEAGE` as the primary source
does not claim that the requested order identifier came from the snapshot or
that either value has accepted-history authority.

### 7.4 Shape and receipt-admission validation

The result dataclasses are directly constructable and do not enforce all
status/field relationships. Each PR5 wrapper rejects a result that cannot
support the selected subject or lineage honestly. At minimum:

```text
Replay MATCH
→ expected_state and persisted_state both present and equal

Replay MISSING_PROJECTION
→ expected_state present; persisted_state absent

Replay DRIFT
→ both states present and different

Replay NO_ACCEPTED_HISTORY
→ expected_state absent

Snapshot-trust MATCH / INVALID / TAIL / DRIFT
→ loaded snapshot_id and source_global_position present

Snapshot-trust MISSING_SNAPSHOT
→ snapshot_id and source_global_position absent

Snapshot-trust NO_ACCEPTED_HISTORY_FOR_ORDER
→ snapshot_id and source_global_position both present or both absent

Assisted INVALID_SNAPSHOT_PRECONDITION
→ snapshot_id and source_global_position absent

Assisted MISSING_SNAPSHOT
→ requested snapshot_id present; source_global_position absent

Assisted loaded-snapshot branches
→ snapshot_id and source_global_position present

Assisted RESOLVED_FROM_SNAPSHOT
→ resolved_state present

Assisted non-resolved branches
→ resolved_state absent
```

`SNAPSHOT_ASSISTED_DRIFT` requires both exposed states to be present but does
not require them to be unequal. The producer also returns this status when
tail reducer application raises, and the still-exposed snapshot-assisted state
may equal `authority_state` at that point.

`DecisionReceiptCorrelation` supplies the shared validation for
`snapshot_id` and `source_global_position`: snapshot identity must be `UUID`,
and a present source position must be an integer other than `bool` and must be
non-negative. PR5 passes those typed producer fields through unchanged. The
current durable snapshot schema requires stored source positions to be
positive; the producer can nevertheless expose zero on an invalid-boundary or
invalid-compatibility result, and the receipt contract truthfully preserves
that non-negative invalid value.

Rejecting an internally contradictory typed result is producer-input
validation. It does not require or justify a shared receipt-contract change.

Blank `order_id` rejection is a separate receipt-contract admission check.
`DecisionReceiptCorrelation` requires a non-empty order identity; the rejection
does not prove that a generic producer result dataclass can never contain a
blank requested order ID.

## 8. Identity-source rules

Use `READ_SIDE_OBSERVATION` when identity is supported only by the producer's
requested or observed read-side scope:

```text
ReplayValidationResult
snapshot-trust MISSING_SNAPSHOT
snapshot-trust NO_ACCEPTED_HISTORY_FOR_ORDER without a loaded snapshot
assisted INVALID_SNAPSHOT_PRECONDITION
assisted MISSING_SNAPSHOT
```

Use `SNAPSHOT_LINEAGE` when the result preserves identity from an actually
loaded snapshot:

```text
snapshot-trust MATCH
snapshot-trust INVALID_SNAPSHOT_BOUNDARY
snapshot-trust TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
snapshot-trust SNAPSHOT_ASSISTED_DRIFT
snapshot-trust NO_ACCEPTED_HISTORY_FOR_ORDER with a loaded snapshot
assisted RESOLVED_FROM_SNAPSHOT
assisted INVALID_SNAPSHOT_COMPATIBILITY
assisted TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
assisted TAIL_REPLAY_FAILED
```

PR5 must not use:

```text
ACCEPTED_HISTORY
CANDIDATE_EVENT_IDENTITY
WRITE_SIDE_CORRELATION
CALLER_CONTEXT
```

Accepted-history replay may support a semantic comparison, but these result
objects do not expose accepted event identity or a correlation block derived
wholly from accepted-history identity. Likewise, snapshot identity and
`source_global_position` are lineage, not accepted-history membership proof.

No approved row needs `DecisionReceiptIdentitySource.UNKNOWN`. The typed
result always provides at least a read-side order observation. Semantic
`risk_level=UNKNOWN` and `reversibility=UNKNOWN` must nevertheless remain
unchanged for the Stage 4A rows that already carry them.

## 9. Flag-state discipline

ADR 0018 is authoritative for all three PR5 producer adapters:

```text
producer-specific receipt adapter
→ preserve typed evidence
≠ evaluate governance flags
```

Every supported replay, snapshot-trust, and snapshot-assisted status therefore
uses `DecisionReceiptFlags()`. All four fields remain `NOT_EVALUATED`:

```text
fallback_required
rebuild_required
operator_review_required
retry_candidate
```

Replay `MATCH` equality and `MISSING_PROJECTION` state absence remain typed
producer evidence. They do not authorize a completed negative or positive
`rebuild_required` evaluation. The same separation applies to every technical
status and Stage 4A semantic tuple.

In particular:

```text
MATCH
≠ completed rebuild_required evaluation

MISSING_PROJECTION or REQUIRES_REBUILD
≠ completed rebuild_required evaluation

MISSING_SNAPSHOT or TAIL_REPLAY_FAILED
→ FAST_PATH_UNAVAILABLE
≠ completed fallback_required evaluation

INVALID_SNAPSHOT_* or SNAPSHOT_ASSISTED_DRIFT
→ untrusted, drift, or rebuildable semantic evidence
≠ completed rebuild_required evaluation

failure, unresolved state, or tail concurrency
≠ retry_candidate
```

No row derives a completed flag from `ok`, category, semantic code, severity,
risk, reversibility, state presence, state equality, or technical status.
Later authorized evaluators may consume those facts under a separate complete
evaluator contract. PR5 must not own operator-review or retry evaluation;
Stage 4E continues to own retry classification and authorization.

## 10. Evidence-summary vocabularies

PR5 must build `evidence_summary` directly from the typed result. It must not
copy or select from the Stage 4A outcome mappings after construction.

### 10.1 Read-side replay vocabulary

```text
technical_status
expected_state_present
persisted_state_present
```

### 10.2 Snapshot-trust vocabulary

```text
technical_status
snapshot_artifact_present
snapshot_assisted_state_present
authority_state_present
```

### 10.3 Snapshot-assisted vocabulary

```text
technical_status
snapshot_artifact_present
resolved_state_present
```

Every key is producer-owned and JSON-safe. No domain state, event, snapshot
object, reason duplication, arbitrary mapping, exception, partial replay
position, or accepted-history payload enters the summary.

`result_type` is omitted. Each approved producer-specific public function fixes
the producer type, and a Python class name is implementation metadata rather
than receipt authority.

### 10.4 Stage 4A evidence merge checkpoint

The current Stage 4A adapters merge evidence as:

```text
canonical presence keys
then caller evidence override
then protected technical_status insertion/check
```

Consequently, caller evidence can currently override:

```text
expected_state_present
persisted_state_present
snapshot_assisted_state_present
authority_state_present
resolved_state_present
result_type
```

Only a contradictory `technical_status` is rejected.

PR5 therefore must not trust those open-ended `SemanticOutcome.evidence`
values for receipt preparation. Each adapter must:

```text
1. Call the existing Stage 4A adapter to construct semantic meaning.
2. Derive the receipt summary again from the typed result object.
3. Pass that summary explicitly to PR3.
```

PR5 must not modify Stage 4A merge behavior.

## 11. Metadata boundary

Producer-derived metadata must remain `{}` for every current status.

Typed identity belongs in `subject` and `correlation`. Stable producer facts
belong in `evidence_summary`. The wrappers must not copy:

```text
SemanticOutcome.context
SemanticOutcome.evidence
ProjectionSnapshot.metadata
state payloads
caller mappings
reason into a second flexible field
```

If a future caller needs actor, cost, or non-authoritative metadata evidence,
that should be added through explicit typed or JSON-safe parameters after a
separate concrete need is established. Such metadata must never affect
evidence source, subject, correlation, identity source, flags, or evidence
summary.

## 12. Mapping algorithms

Each approved wrapper must follow the same short sequence without a generic
selector framework.

### 12.1 Read-side replay

```text
1. Validate the status/field production shape.
2. Call map_replay_validation_result_to_semantic_outcome.
3. Select READ_SIDE_PATH.
4. Select subject from the status table.
5. Build order-only READ_SIDE_OBSERVATION correlation.
6. Use all-NOT_EVALUATED flags.
7. Build replay evidence_summary directly from result.
8. Call map_semantic_outcome_to_decision_receipt.
```

### 12.2 Snapshot trust

```text
1. Validate the status/field production shape and paired lineage fields.
2. Call map_projection_snapshot_replay_validation_result_to_semantic_outcome.
3. Select SNAPSHOT_TRUST_PATH.
4. Select subject from the status table without making a root-cause claim.
5. Select READ_SIDE_OBSERVATION or SNAPSHOT_LINEAGE from loaded-artifact facts.
6. Use all-NOT_EVALUATED flags.
7. Build snapshot-trust evidence_summary directly from result.
8. Call map_semantic_outcome_to_decision_receipt.
```

### 12.3 Snapshot-assisted resolution

```text
1. Validate the status/field production shape.
2. Call map_projection_snapshot_assisted_resolution_result_to_semantic_outcome.
3. Select SNAPSHOT_ASSISTED_PATH.
4. Select subject from the status table without attributing unproved cause.
5. Distinguish an unfulfilled requested snapshot ID from loaded lineage.
6. Use all-NOT_EVALUATED flags.
7. Build snapshot-assisted evidence_summary directly from result.
8. Call map_semantic_outcome_to_decision_receipt.
```

The wrappers must not accept Stage 4A `context` or `evidence` override
parameters. Those open-ended inputs are unnecessary for receipt construction
and would create a second path for non-authoritative data.

## 13. Approved files and public functions

The PR5 adapter change set must remain limited to:

```text
src/compass/runtime/read_side_decision_receipt_mapping.py
tests/unit/compass/runtime/test_read_side_decision_receipt_mapping.py
```

The production module must expose exactly:

```python
def map_replay_validation_result_to_decision_receipt(
    *,
    receipt_id: UUID,
    outcome_id: UUID,
    result: ReplayValidationResult,
) -> DecisionReceipt:
    ...


def map_projection_snapshot_replay_validation_result_to_decision_receipt(
    *,
    receipt_id: UUID,
    outcome_id: UUID,
    result: ProjectionSnapshotReplayValidationResult,
) -> DecisionReceipt:
    ...


def map_projection_snapshot_assisted_resolution_result_to_decision_receipt(
    *,
    receipt_id: UUID,
    outcome_id: UUID,
    result: ProjectionSnapshotAssistedResolutionResult,
) -> DecisionReceipt:
    ...
```

The module should use only small private per-producer helpers for shape
validation, subject selection, and loaded-artifact classification. It must not
add:

```text
generic selector framework
registry
callback extractor
status-to-evidence-source global mapper
policy object
strategy object
retry object
serializer
store
PostgresProjectionWorkerResult mapping
no_event mapping
source-event extraction
projection-definition extraction
runtime wiring
```

No change to `src/compass/runtime/__init__.py` is required for this design.
Callers and tests should import the public functions from their defining
module.

## 14. Unit-test contract

### 14.1 Per-status rows

The focused suite should retain one explicit mapping row for each current
status:

```text
ReplayValidationResult: 4
ProjectionSnapshotReplayValidationResult: 6
ProjectionSnapshotAssistedResolutionResult: 6
total status rows: 16
```

Each row must assert:

```text
exact Stage 4A semantic tuple preservation
producer-owned evidence_source
subject type and subject ID
all correlation fields
identity_source
all four flag states
exact evidence_summary key set and values
metadata == {}
admission_evidence is None
actor and cost defaults
```

### 14.2 Lineage edge cases

Cover:

```text
snapshot-trust NO_ACCEPTED_HISTORY_FOR_ORDER with loaded snapshot lineage
snapshot-trust NO_ACCEPTED_HISTORY_FOR_ORDER without snapshot lineage
assisted MISSING_SNAPSHOT requested ID is READ_SIDE_OBSERVATION
assisted loaded-snapshot branches use SNAPSHOT_LINEAGE
source_global_position is preserved only when the typed result carries it
request and event correlation fields remain absent
```

### 14.3 Observed-boundary/root-cause cases

Assert:

```text
snapshot-trust tail-source violation subject is RUNTIME, not SNAPSHOT
snapshot-trust drift subject is PROJECTION, not a snapshot-cause assertion
assisted tail-source and tail-replay failures use RUNTIME subjects
```

### 14.4 Flag discipline

Assert:

```text
every supported producer status uses DecisionReceiptFlags()
all four fields are NOT_EVALUATED
MATCH does not infer rebuild_required
MISSING_PROJECTION / REQUIRES_REBUILD does not infer rebuild_required
FAST_PATH_UNAVAILABLE does not infer fallback_required
no technical or semantic field completes any governance proposition
```

### 14.5 Evidence boundary

Assert exact summary vocabularies and prove that:

```text
state objects are not copied
snapshot objects are not copied
SemanticOutcome.context is not copied
SemanticOutcome.evidence is not copied
caller-overridable Stage 4A presence keys cannot change receipt summary
result_type is not stored
metadata remains empty
```

Because the wrappers do not accept Stage 4A `context` or `evidence`,
the caller-override test may construct the Stage 4A outcome separately to
demonstrate the existing risk, then confirm the PR5 wrapper reconstructs its
own summary from the typed result.

### 14.6 Invalid producer shapes

Focused rejection tests should cover the status/state/lineage invariants and
receipt-admission boundary in section 7.4. They should verify deterministic
`ValueError` behavior and must not invent `UNKNOWN` subject or identity values
to hide contradictory input.

### 14.7 Scope tests

Assert that the new module introduces no:

```text
runtime action
policy
strategy
retry authorization
serialization
persistence
admission disposition
```

## 15. Shared-contract checkpoint

PR5 can be represented by the current shared contracts without modifying:

```text
src/compass/runtime/decision_receipt.py
src/compass/runtime/decision_receipt_mapping.py
src/compass/runtime/json_types.py
src/compass/runtime/semantic_outcome.py
```

The current contracts already provide:

```text
all three required evidence-source values
ORDER / PROJECTION / SNAPSHOT / RUNTIME subjects
typed order, snapshot, and source-global-position correlation
READ_SIDE_OBSERVATION and SNAPSHOT_LINEAGE
three-state flags
explicit JSON-safe evidence_summary and metadata
generic semantic-tuple-preserving receipt construction
```

The primary-correlation `identity_source` is sufficient for PR5 because the
mapping does not ask an automated consumer to make field-level authority
decisions and explicitly documents mixed order observation plus snapshot
lineage. This is a known precision limit, not a blocker for honest receipt
construction.

The caller-overridable Stage 4A evidence keys are also not a shared-contract
blocker. Reconstructing the compact summary from the typed result is the normal
PR5 producer-specific responsibility and preserves the PR3 rule that outcome
mappings are not inspected.

The source-grounded review found no shared-contract blocker for the approved
PR5 mapping.

## 16. Approved implementation decisions

ADR 0018 resolves flag ownership: producer adapters leave every flag
`NOT_EVALUATED`, including replay `MATCH` and `MISSING_PROJECTION`.

Producer-source review supports fail-closed `ValueError` checks for impossible
status/state/lineage shapes. Receipt construction also requires a non-empty
order identity even though a generic producer result dataclass can be directly
constructed with a blank requested value. The approved mapping must accept
equal exposed states for `SNAPSHOT_ASSISTED_DRIFT` because reducer failure can
occur before the snapshot-assisted state diverges.

The conservative `RUNTIME` subjects remain for tail-source and assisted
tail-replay failures. They preserve the observed boundary without assigning
unproved root cause to a snapshot or projection. No shared-contract change is
required.

## 17. Explicit non-goals

PR5 must not design or implement:

```text
PR4 write-side admission mapping
PR6 serialization or persistence
shared PR3 mapper changes
Stage 4A evidence merge changes
accepted-history mutation
projection rebuild execution
snapshot selection
snapshot trust qualification
fallback execution
quarantine
operator-review execution
policy
strategy
retry classification
retry authorization
retry execution
DiagnosticTrace
ResolutionTrace
AttemptLog
generic adapter frameworks
registries
callback extractors
metadata flattening
field-level identity provenance
PostgresProjectionWorkerResult mapping
no_event mapping
source-event extraction
projection-definition extraction
runtime wiring
```

The PR5 wrappers must prepare honest, compact, producer-specific receipt inputs
and delegate final construction to the existing generic PR3 mapper.
