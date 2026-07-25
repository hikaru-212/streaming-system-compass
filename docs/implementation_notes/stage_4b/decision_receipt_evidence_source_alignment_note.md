# Stage 4B DecisionReceipt Evidence Source Alignment Note

## Purpose

This note explains how Stage 4A runtime mapping statuses should align with Stage 4B `DecisionReceiptEvidenceSource`.

The important distinction is:

```text
Stage 4A technical_status
= raw status / adapter-facing result vocabulary

Stage 4B DecisionReceiptEvidenceSource
= path-level source of the evidence preserved in a DecisionReceipt
```

Therefore, `DecisionReceiptEvidenceSource` should not be selected from:

```text
success / failure
semantic outcome category
technical status name alone
validator operation name
retry classification
policy decision
```

It should be selected from the runtime path that produced the evidence.

In short:

```text
technical_status
= what condition was observed

DecisionReceiptEvidenceSource
= where the evidence came from
```

---

## Current Production Vocabulary

The current Stage 4B PR2 production vocabulary is:

```python
class DecisionReceiptEvidenceSource(str, Enum):
    """
    Runtime evidence path that produced the receipt.

    This vocabulary identifies where receipt evidence came from. It describes
    the evidence path, not the technical status, semantic outcome, runtime
    action, execution strategy, retry policy, persistence state, or validator
    operation.
    """

    WRITE_SIDE_ADMISSION = "WRITE_SIDE_ADMISSION"
    READ_SIDE_PATH = "READ_SIDE_PATH"
    SNAPSHOT_TRUST_PATH = "SNAPSHOT_TRUST_PATH"
    SNAPSHOT_ASSISTED_PATH = "SNAPSHOT_ASSISTED_PATH"
    RUNTIME_OBSERVATION = "RUNTIME_OBSERVATION"
    UNKNOWN = "UNKNOWN"
```

This is intentionally a **path-level vocabulary**.

It should not mix:

```text
path names
operation names
technical status names
success-oriented result names
```

---

## Previous Vocabulary and Correction

Earlier drafts used:

```python
class DecisionReceiptEvidenceSource(str, Enum):
    RUNTIME_TECHNICAL_STATUS = "RUNTIME_TECHNICAL_STATUS"
    READ_SIDE_REPLAY = "READ_SIDE_REPLAY"
    SNAPSHOT_REPLAY = "SNAPSHOT_REPLAY"
    SNAPSHOT_ASSISTED_RESOLUTION = "SNAPSHOT_ASSISTED_RESOLUTION"
    WRITE_SIDE_ADMISSION = "WRITE_SIDE_ADMISSION"
    UNKNOWN = "UNKNOWN"
```

This was locally understandable, but semantically mixed.

| Previous name | Problem | Corrected name |
|---|---|---|
| `RUNTIME_TECHNICAL_STATUS` | Describes a status nature, not an evidence path. | `RUNTIME_OBSERVATION` |
| `READ_SIDE_REPLAY` | Describes an operation / validation method, not the whole read-side path. | `READ_SIDE_PATH` |
| `SNAPSHOT_REPLAY` | Describes a replay operation, not the whole snapshot trust path. | `SNAPSHOT_TRUST_PATH` |
| `SNAPSHOT_ASSISTED_RESOLUTION` | Sounds like successful resolution, but the path also covers missing / failed / drift outcomes. | `SNAPSHOT_ASSISTED_PATH` |
| `WRITE_SIDE_ADMISSION` | Already path-level. | unchanged |
| `UNKNOWN` | Transitional fallback. | unchanged |

The corrected rule is:

```text
DecisionReceiptEvidenceSource names evidence paths.

It should not name:
- technical status classes
- validator operations
- success cases
- recovery decisions
```

---

## Core Rule

Concrete adapter ownership wins.

Status-only classification is advisory and must not override the runtime
component that produced the evidence.

Do not classify evidence source by `ok=True` or `ok=False`.

Do not classify evidence source by status name alone.

Classify it by this question:

```text
Which runtime path produced this evidence?
```

Examples:

```text
WRITE_SIDE_ACCEPTED
→ WRITE_SIDE_ADMISSION

COMPASS_VALIDATION_BLOCKED
→ WRITE_SIDE_ADMISSION

RESOLVED_FROM_SNAPSHOT
→ SNAPSHOT_ASSISTED_PATH

SNAPSHOT_ASSISTED_DRIFT from snapshot replay validator
→ SNAPSHOT_TRUST_PATH

INVALID_SNAPSHOT_BOUNDARY
→ SNAPSHOT_TRUST_PATH

MISSING_PROJECTION
→ READ_SIDE_PATH

LOCK_TIMEOUT in write-side admission
→ WRITE_SIDE_ADMISSION

LOCK_TIMEOUT in generic runtime health observation
→ RUNTIME_OBSERVATION
```

---

## Why status alone is sometimes not enough

Some statuses are too generic.

For example:

```text
MATCH
```

`MATCH` only tells us the result is semantically valid.

It does not tell us which evidence path produced the match.

So the mapper should use:

```text
technical_status + boundary / adapter context
```

Examples:

```text
MATCH + SNAPSHOT_TRUST
→ SNAPSHOT_TRUST_PATH

MATCH + READ_SIDE_PROJECTION
→ READ_SIDE_PATH

MATCH + WRITE_SIDE_ADMISSION
→ WRITE_SIDE_ADMISSION

MATCH + generic runtime observation
→ RUNTIME_OBSERVATION
```

So `MATCH` should not automatically mean `RUNTIME_OBSERVATION`.

Likewise:

```text
LOCK_TIMEOUT
```

does not automatically mean `RUNTIME_OBSERVATION`.

If lock timeout happened while the write-side admission path was trying to acquire an admission lock, the evidence source should remain:

```text
WRITE_SIDE_ADMISSION
```

and the technical condition should be preserved as:

```text
evidence_summary.technical_status = LOCK_TIMEOUT
```

---

## Recommended Initial Mapping

This table is a starting point for adapter-specific receipt mapping.

It should not be read as a global status-only mapper. When adapter context is available, adapter context wins.

| Stage 4A technical_status | Recommended evidence_source | Reason |
|---|---|---|
| `WRITE_SIDE_ACCEPTED` | `WRITE_SIDE_ADMISSION` | Write-side admission accepted the candidate. |
| `COMPASS_VALIDATION_BLOCKED` | `WRITE_SIDE_ADMISSION` | Compass / admission blocked the candidate. |
| `CONCURRENT_STATE_STALENESS` | `WRITE_SIDE_ADMISSION` | Write-side admission observed stale state. |
| `OCC_CONFLICT_AFTER_VALIDATION` | `WRITE_SIDE_ADMISSION` | Conflict happened after validation in the write-side admission path. |
| `LOCK_TIMEOUT` | context-dependent | Usually `WRITE_SIDE_ADMISSION` if observed during admission locking; otherwise `RUNTIME_OBSERVATION`. |
| `WRITE_SIDE_INFRASTRUCTURE_ERROR` | context-dependent | Usually `WRITE_SIDE_ADMISSION` if observed inside write-side admission; otherwise `RUNTIME_OBSERVATION`. |
| `IDEMPOTENT_REPLAY` | `WRITE_SIDE_ADMISSION` | Idempotency was classified in the write-side admission path. |
| `IDEMPOTENCY_CONFLICT` | `WRITE_SIDE_ADMISSION` | Idempotency conflict belongs to write-side admission governance. |
| `MATCH` | context-dependent | Needs boundary or adapter context. |
| `RESOLVED_FROM_SNAPSHOT` | `SNAPSHOT_ASSISTED_PATH` | Runtime used snapshot-assisted path successfully. |
| `MISSING_SNAPSHOT` | context-dependent | `SNAPSHOT_TRUST_PATH` from the trust validator; `SNAPSHOT_ASSISTED_PATH` from the assisted resolver. |
| `TAIL_REPLAY_FAILED` | context-dependent | Usually `SNAPSHOT_ASSISTED_PATH` if tail replay failed during assisted resolution; otherwise `RUNTIME_OBSERVATION` if no specific path exists. |
| `SNAPSHOT_ASSISTED_DRIFT` | context-dependent | Use the producing component; the current snapshot replay validator owns `SNAPSHOT_TRUST_PATH`. |
| `INVALID_SNAPSHOT_BOUNDARY` | `SNAPSHOT_TRUST_PATH` | Snapshot trust boundary validation failed. |
| `INVALID_SNAPSHOT_PRECONDITION` | context-dependent | The current assisted resolver produces this status, so that path maps to `SNAPSHOT_ASSISTED_PATH`. |
| `INVALID_SNAPSHOT_COMPATIBILITY` | context-dependent | The current assisted resolver produces this status, so that path maps to `SNAPSHOT_ASSISTED_PATH`. |
| `TAIL_EVENT_SOURCE_CONTRACT_VIOLATION` | context-dependent | `SNAPSHOT_TRUST_PATH` from trust validation; `SNAPSHOT_ASSISTED_PATH` from assisted resolution; otherwise `RUNTIME_OBSERVATION`. |
| `MISSING_PROJECTION` | `READ_SIDE_PATH` | Read-side projection state is missing and may need rebuild. |
| `DRIFT` | `READ_SIDE_PATH` | Read-side projection / replay validation detected drift. |
| `NO_ACCEPTED_HISTORY` | context-dependent | Needs boundary or adapter context. |
| `NO_ACCEPTED_HISTORY_FOR_ORDER` | context-dependent | Needs boundary or adapter context. |

---

## Context-dependent examples

### Example 1: `MATCH`

```text
technical_status = MATCH
boundary = SNAPSHOT_TRUST
```

Recommended evidence source:

```text
SNAPSHOT_TRUST_PATH
```

Reason:

```text
The match came from snapshot trust validation.
```

---

```text
technical_status = MATCH
boundary = READ_SIDE_PROJECTION
```

Recommended evidence source:

```text
READ_SIDE_PATH
```

Reason:

```text
The match came from read-side projection validation.
```

---

```text
technical_status = MATCH
boundary = WRITE_SIDE_ADMISSION
```

Recommended evidence source:

```text
WRITE_SIDE_ADMISSION
```

Reason:

```text
The match came from the write-side admission path.
```

---

```text
technical_status = MATCH
boundary = generic runtime boundary
```

Recommended evidence source:

```text
RUNTIME_OBSERVATION
```

Reason:

```text
No more specific evidence path is available.
```

---

### Example 2: `NO_ACCEPTED_HISTORY_FOR_ORDER`

This status is also context-dependent.

```text
technical_status = NO_ACCEPTED_HISTORY_FOR_ORDER
boundary = WRITE_SIDE_ADMISSION
```

Recommended evidence source:

```text
WRITE_SIDE_ADMISSION
```

Reason:

```text
The write-side admission path tried to validate a candidate against accepted history, but no accepted history existed for that order.
```

---

```text
technical_status = NO_ACCEPTED_HISTORY_FOR_ORDER
boundary = SNAPSHOT_TRUST
```

Recommended evidence source:

```text
SNAPSHOT_TRUST_PATH
```

Reason:

```text
Snapshot trust validation tried to compare snapshot lineage against accepted history, but no accepted history existed for that order.
```

---

```text
technical_status = NO_ACCEPTED_HISTORY_FOR_ORDER
boundary = READ_SIDE_PROJECTION
```

Recommended evidence source:

```text
READ_SIDE_PATH
```

Reason:

```text
Read-side projection validation could not find accepted history for that order.
```

---

### Example 3: `LOCK_TIMEOUT`

```text
technical_status = LOCK_TIMEOUT
boundary = WRITE_SIDE_ADMISSION
```

Recommended evidence source:

```text
WRITE_SIDE_ADMISSION
```

Reason:

```text
The lock timeout happened while the write-side admission path was attempting to protect the admission boundary.
```

---

```text
technical_status = LOCK_TIMEOUT
boundary = generic runtime boundary
```

Recommended evidence source:

```text
RUNTIME_OBSERVATION
```

Reason:

```text
The lock timeout was observed as a generic runtime condition and cannot be attributed to a more specific evidence path.
```

---

### Example 4: `TAIL_REPLAY_FAILED`

```text
technical_status = TAIL_REPLAY_FAILED
boundary = SNAPSHOT_TRUST / snapshot-assisted resolver context
```

Recommended evidence source:

```text
SNAPSHOT_ASSISTED_PATH
```

Reason:

```text
The tail replay failure happened while attempting snapshot-assisted reconstruction.
```

---

```text
technical_status = TAIL_REPLAY_FAILED
boundary = generic runtime boundary
```

Recommended evidence source:

```text
RUNTIME_OBSERVATION
```

Reason:

```text
The failure cannot be attributed to a more specific evidence path.
```

---

## Meaning of each DecisionReceiptEvidenceSource

### `WRITE_SIDE_ADMISSION`

Use this when the outcome was produced by the write-side admission path.

This includes both successful and unsuccessful outcomes.

Examples:

```text
WRITE_SIDE_ACCEPTED
COMPASS_VALIDATION_BLOCKED
CONCURRENT_STATE_STALENESS
OCC_CONFLICT_AFTER_VALIDATION
LOCK_TIMEOUT during admission locking
IDEMPOTENT_REPLAY
IDEMPOTENCY_CONFLICT
```

Important:

```text
WRITE_SIDE_ADMISSION does not mean failure.
It means the evidence came from the write-side admission path.
```

---

### `READ_SIDE_PATH`

Use this when the evidence came from the read-side projection / query / projection validation path.

Examples:

```text
MATCH + READ_SIDE_PROJECTION
MISSING_PROJECTION
DRIFT
NO_ACCEPTED_HISTORY_FOR_ORDER + READ_SIDE_PROJECTION
projection validation mismatch
projection rebuild evidence
```

Important:

```text
READ_SIDE_PATH is broader than read-side replay.
It may include replay validation, projection checks, projection missing evidence, or derived-state validation.
It is not accepted-history authority by itself.
```

---

### `SNAPSHOT_TRUST_PATH`

Use this when the outcome was produced by snapshot trust validation.

Examples:

```text
MATCH + SNAPSHOT_TRUST
INVALID_SNAPSHOT_BOUNDARY
INVALID_SNAPSHOT_PRECONDITION
INVALID_SNAPSHOT_COMPATIBILITY
NO_ACCEPTED_HISTORY_FOR_ORDER + SNAPSHOT_TRUST
```

Important:

```text
SNAPSHOT_TRUST_PATH is about validating whether the snapshot artifact is trustworthy.
It does not mean the runtime used the snapshot as a fast path.
```

---

### `SNAPSHOT_ASSISTED_PATH`

Use this when the runtime used, attempted to use, or failed to use a snapshot-assisted path.

Examples:

```text
RESOLVED_FROM_SNAPSHOT
MISSING_SNAPSHOT
TAIL_REPLAY_FAILED during snapshot-assisted reconstruction
SNAPSHOT_ASSISTED_DRIFT
```

Important:

```text
SNAPSHOT_ASSISTED_PATH does not mean successful resolution.
It means the evidence came from the snapshot-assisted mechanism.
```

Also important:

```text
Not every read-side result that was originally produced using a snapshot belongs here.

If the receipt is about the final read-side projection state, use READ_SIDE_PATH.
If the receipt is about the assisted reconstruction mechanism itself, use SNAPSHOT_ASSISTED_PATH.
```

---

### `RUNTIME_OBSERVATION`

Use this only when the outcome came from a generic runtime-level observation and there is no more specific evidence path.

Examples:

```text
LOCK_TIMEOUT + generic runtime observation
WRITE_SIDE_INFRASTRUCTURE_ERROR outside a specific adapter path
TAIL_EVENT_SOURCE_CONTRACT_VIOLATION outside a specific assisted path
MATCH + generic runtime observation
```

Important:

```text
RUNTIME_OBSERVATION does not mean all technical errors.
It does not mean all successful outcomes.
It does not mean all unknown outcomes.

It means the receipt evidence came from a generic runtime observation that cannot be attributed to a more specific path.
```

---

### `UNKNOWN`

Use this only when the adapter does not yet provide enough information.

Examples:

```text
Temporary PR2 fallback
Incomplete adapter mapping
Legacy status without boundary / context
```

Important:

```text
UNKNOWN should decrease as adapter-specific receipt mapping becomes more complete.
```

---

## Suggested mapper shape

The mapper should not rely only on `technical_status`.

Prefer:

```python
def evidence_source_for_runtime_status(
    *,
    technical_status: str,
    boundary: SemanticBoundary,
    adapter_context: Mapping[str, object] | None = None,
) -> DecisionReceiptEvidenceSource:
    ...
```

Reason:

```text
Some statuses, such as MATCH, LOCK_TIMEOUT, TAIL_REPLAY_FAILED,
and NO_ACCEPTED_HISTORY_FOR_ORDER, need boundary or adapter context to be
classified correctly.
```

However, later adapter-specific mappers should avoid a generic status-only
source mapper when the producer is already known.

For example:

```text
write-side receipt mapper
→ chooses WRITE_SIDE_ADMISSION

read-side receipt mapper
→ chooses READ_SIDE_PATH

snapshot trust receipt mapper
→ chooses SNAPSHOT_TRUST_PATH

snapshot-assisted receipt mapper
→ chooses SNAPSHOT_ASSISTED_PATH
```

This is often cleaner than asking a generic mapper to infer path ownership from status names.

---

## Current Producer Ownership

```text
ReplayValidationResult
→ READ_SIDE_PATH

ProjectionSnapshotReplayValidationResult
→ SNAPSHOT_TRUST_PATH

ProjectionSnapshotAssistedResolutionResult
→ SNAPSHOT_ASSISTED_PATH

PostgresWriteSideResult
→ WRITE_SIDE_ADMISSION
```

This means a status such as `MISSING_SNAPSHOT` or
`TAIL_EVENT_SOURCE_CONTRACT_VIOLATION` may map differently depending on which
concrete producer returned it.

---

## Final rule

```text
DecisionReceiptEvidenceSource is evidence-path classification.

It is not:
- success/failure classification
- raw technical status
- semantic category
- validator operation
- retry decision
- policy decision
- persistence status
```

The right question is always:

```text
Where did this evidence come from?
```

The wrong question is:

```text
What status name does this look like?
```

---

## Practical rule for Stage 4B PR3+

When implementing `SemanticOutcome → DecisionReceipt` adapters:

```text
1. First identify the adapter path.
2. Then assign DecisionReceiptEvidenceSource from that path.
3. Preserve technical_status inside evidence_summary when useful.
4. Do not derive evidence_source from ok/category alone.
5. Do not let generic runtime statuses override a more specific adapter path.
```

Example:

```text
write-side admission + LOCK_TIMEOUT
→ evidence_source = WRITE_SIDE_ADMISSION
→ evidence_summary.technical_status = LOCK_TIMEOUT
```

```text
snapshot-assisted path + TAIL_REPLAY_FAILED
→ evidence_source = SNAPSHOT_ASSISTED_PATH
→ evidence_summary.technical_status = TAIL_REPLAY_FAILED
```

```text
snapshot trust validation + INVALID_SNAPSHOT_BOUNDARY
→ evidence_source = SNAPSHOT_TRUST_PATH
→ evidence_summary.technical_status = INVALID_SNAPSHOT_BOUNDARY
```

```text
read-side projection validation + DRIFT
→ evidence_source = READ_SIDE_PATH
→ evidence_summary.technical_status = DRIFT
```

```text
generic runtime health observation + LOCK_TIMEOUT
→ evidence_source = RUNTIME_OBSERVATION
→ evidence_summary.technical_status = LOCK_TIMEOUT
```
