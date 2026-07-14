# Postmortem: Semantic Level Mismatch in an AI-Assisted Runtime Contract

[← Back to Postmortems Index](README.md)

**Recorded on:** 2026-07-15

---

## 1. Purpose

This note records a semantic-contract correction discovered during Stage 4B.

The issue was not that the generated code was syntactically invalid.

The issue was subtler:

```text
The implementation contract was type-safe,
defensive,
well-tested,
and locally coherent,

but one enum mixed multiple semantic levels.
```

This is especially important in AI-assisted engineering.

An AI assistant can often improve implementation hardening:

```text
stronger type checks
defensive immutability
JSON-safe evidence
depth guards
stable enum tests
runtime contract validation
```

However, implementation hardening does not automatically guarantee domain-semantic precision.

In short:

```text
code can be correct enough to run,
but vocabulary may not be correct enough to govern.
```

This mirrors the core Compass lesson:

```text
a generated artifact can be structured,
but not necessarily semantically admitted.
```

---

## 2. Context

Stage 4A introduced `SemanticOutcome`.

Its role is:

```text
technical runtime evidence
→ SemanticOutcome
```

Stage 4B introduces `DecisionReceipt`.

Its role is:

```text
SemanticOutcome
→ compact runtime governance evidence
```

The `DecisionReceipt` contract is intended to preserve selected semantic evidence in a form that can later support:

```text
reviewability
auditability
policy-linked recovery
runtime decisions
strategy selection
retry governance
future agent workflow governance
```

Stage 4B PR2 defines the in-code runtime contract.

It does not yet implement:

```text
SemanticOutcome → DecisionReceipt mapping
write-side receipt mapping
read-side / snapshot receipt mapping
SQL persistence
DiagnosticTrace
RuntimeDecisionPolicy
StrategySelector
RetryGovernance
```

Therefore, PR2 is the right moment to define the vocabulary precisely before later adapters depend on it.

---

## 3. Original Implementation

The initial `DecisionReceiptEvidenceSource` enum was:

```python
class DecisionReceiptEvidenceSource(str, Enum):
    """
    Runtime evidence path that produced the receipt.

    This vocabulary identifies where the receipt evidence came from. It does
    not execute recovery, select strategy, classify retry safety, or persist the
    receipt.
    """

    RUNTIME_TECHNICAL_STATUS = "RUNTIME_TECHNICAL_STATUS"
    READ_SIDE_REPLAY = "READ_SIDE_REPLAY"
    SNAPSHOT_REPLAY = "SNAPSHOT_REPLAY"
    SNAPSHOT_ASSISTED_RESOLUTION = "SNAPSHOT_ASSISTED_RESOLUTION"
    WRITE_SIDE_ADMISSION = "WRITE_SIDE_ADMISSION"
    UNKNOWN = "UNKNOWN"
```

At first glance, this looked reasonable.

It was:

```text
typed
explicit
stable
testable
not a runtime decision
not a retry policy
not a persistence state
```

The surrounding contract was also defensively implemented.

The code used:

```text
frozen dataclasses
explicit enum validation
non-empty string checks
UUID checks
JSON-safe evidence containers
immutable mapping conversion
depth-limited JSON normalization
```

This made the code locally strong.

But the enum still had a semantic-level problem.

---

## 4. What Was Confusing

The docstring said:

```text
Runtime evidence path that produced the receipt.
```

That means the enum should answer:

```text
Where did this receipt evidence come from?
```

However, the enum members did not all describe the same kind of thing.

They mixed:

```text
path-level names
operation-level names
status-level names
success-oriented names
fallback names
```

The mismatch was not obvious from the type system.

The code would still run.

The tests could still pass.

The enum values could still be stable.

But the vocabulary was not semantically level-consistent.

---

## 5. Original Vocabulary Problem

The original enum mixed these levels:

| Original enum | Semantic level | Problem |
|---|---|---|
| `WRITE_SIDE_ADMISSION` | Path | Correct level. This describes an evidence path. |
| `READ_SIDE_REPLAY` | Operation / validation mode | Too narrow. Read-side evidence is not always only replay. |
| `SNAPSHOT_REPLAY` | Operation / validation mode | Too narrow. Snapshot trust includes more than replay. |
| `SNAPSHOT_ASSISTED_RESOLUTION` | Success-oriented operation | Sounds like successful resolution only. |
| `RUNTIME_TECHNICAL_STATUS` | Status / condition | Confuses evidence path with technical status. |
| `UNKNOWN` | Transitional fallback | Reasonable as fallback. |

The main problem was:

```text
DecisionReceiptEvidenceSource was intended to model evidence paths,
but several names modeled operations, statuses, or successful outcomes.
```

---

## 6. The Question That Exposed the Flaw

The flaw became visible only after asking concrete routing questions:

```text
If a normal read-side result uses a snapshot-assisted mechanism,
does every normal read-side receipt become SNAPSHOT_ASSISTED_PATH?

If a projection is rebuilt from full replay,
does it belong to READ_SIDE_REPLAY?

If snapshot validation fails,
is that SNAPSHOT_REPLAY or SNAPSHOT_ASSISTED_PATH?

If LOCK_TIMEOUT happens during write-side admission,
is the source RUNTIME_TECHNICAL_STATUS or WRITE_SIDE_ADMISSION?
```

These questions exposed the hidden problem:

```text
technical_status
and
evidence_source

were being mentally allowed to overlap.
```

But they should be different axes.

The corrected model is:

```text
evidence_source = path / source of evidence
technical_status = observed condition inside that path
```

For example:

```text
write-side admission + LOCK_TIMEOUT
→ evidence_source = WRITE_SIDE_ADMISSION
→ evidence_summary.technical_status = LOCK_TIMEOUT
```

The technical status does not determine the evidence source.

The runtime path determines the evidence source.

---

## 7. Corrected Model

The corrected `DecisionReceiptEvidenceSource` should be path-level:

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

This is not only a rename.

It changes the vocabulary from:

```text
mixed path / operation / status / outcome terms
```

to:

```text
consistent path-level evidence source terms
```

---

## 8. Before / After Difference

| Before | After | Reason |
|---|---|---|
| `RUNTIME_TECHNICAL_STATUS` | `RUNTIME_OBSERVATION` | A technical status is evidence detail, not an evidence path. |
| `READ_SIDE_REPLAY` | `READ_SIDE_PATH` | Read-side evidence may include projection match, missing projection, drift, checkpoint issues, or replay validation. It is not only replay. |
| `SNAPSHOT_REPLAY` | `SNAPSHOT_TRUST_PATH` | Snapshot trust includes boundary, lineage, schema, reducer compatibility, payload evidence, and replay-related validation. |
| `SNAPSHOT_ASSISTED_RESOLUTION` | `SNAPSHOT_ASSISTED_PATH` | The assisted path may succeed, fail, be unavailable, drift, or require fallback. It is not necessarily a successful resolution. |
| `WRITE_SIDE_ADMISSION` | `WRITE_SIDE_ADMISSION` | Already path-level. |
| `UNKNOWN` | `UNKNOWN` | Still useful as transitional fallback. |

The corrected vocabulary keeps every enum member at the same abstraction level:

```text
path
path
path
path
generic observation path
fallback
```

Instead of:

```text
path
operation
operation
successful operation
status class
fallback
```

---

## 9. Corrected Definitions

| Enum | Definition |
|---|---|
| `WRITE_SIDE_ADMISSION` | Evidence produced by the write-side admission / orchestration path. |
| `READ_SIDE_PATH` | Evidence produced by read-side projection, query, replay validation, or derived-state validation paths. |
| `SNAPSHOT_TRUST_PATH` | Evidence produced by validating whether a snapshot artifact is trustworthy as derived state compression. |
| `SNAPSHOT_ASSISTED_PATH` | Evidence produced by attempting to use snapshot-assisted reconstruction, validation, or fast-path resolution. |
| `RUNTIME_OBSERVATION` | Generic runtime-level observation that cannot be attributed to a more specific evidence path. |
| `UNKNOWN` | Transitional fallback when an adapter has not provided enough path information. |

---

## 10. Mapping Examples

The corrected model produces clearer mapping rules:

| Scenario | Evidence source | Technical status |
|---|---|---|
| write-side admission accepted an event | `WRITE_SIDE_ADMISSION` | `WRITE_SIDE_ACCEPTED` |
| write-side admission blocked a candidate | `WRITE_SIDE_ADMISSION` | `COMPASS_VALIDATION_BLOCKED` |
| write-side admission hit a lock timeout | `WRITE_SIDE_ADMISSION` | `LOCK_TIMEOUT` |
| read-side projection matched authority | `READ_SIDE_PATH` | `MATCH` |
| read-side projection was missing | `READ_SIDE_PATH` | `MISSING_PROJECTION` |
| read-side projection drifted | `READ_SIDE_PATH` | `DRIFT` |
| snapshot boundary was invalid | `SNAPSHOT_TRUST_PATH` | `INVALID_SNAPSHOT_BOUNDARY` |
| snapshot compatibility was invalid | `SNAPSHOT_TRUST_PATH` | `INVALID_SNAPSHOT_COMPATIBILITY` |
| snapshot-assisted reconstruction succeeded | `SNAPSHOT_ASSISTED_PATH` | `RESOLVED_FROM_SNAPSHOT` |
| snapshot-assisted path had no usable snapshot | `SNAPSHOT_ASSISTED_PATH` | `MISSING_SNAPSHOT` |
| snapshot-assisted tail replay failed | `SNAPSHOT_ASSISTED_PATH` | `TAIL_REPLAY_FAILED` |
| snapshot-assisted reconstruction drifted | `SNAPSHOT_ASSISTED_PATH` | `SNAPSHOT_ASSISTED_DRIFT` |
| generic runtime health check observed a lock timeout | `RUNTIME_OBSERVATION` | `LOCK_TIMEOUT` |

The reusable rule is:

```text
technical_status belongs in evidence_summary.
evidence_source belongs to the runtime path.
```

---

## 11. Why the Previous Tests Were Not Enough

The existing tests could confirm:

```text
DecisionReceipt is frozen
raw strings are rejected for enum fields
JSON evidence is immutable
non-JSON-safe values are rejected
enum member sets are stable
runtime action / strategy / retry fields are absent
```

Those tests were useful.

They hardened the contract.

However, tests that preserve an enum member set can also preserve the wrong vocabulary if the vocabulary itself is semantically mixed.

This is the important lesson:

```text
tests can protect a boundary,
but only after the boundary vocabulary is correct.
```

In this case, the tests were not wrong.

They were incomplete for semantic-level consistency.

---

## 12. Why AI Assistance Did Not Catch It

This issue is a useful AI-assisted engineering lesson.

AI assistance is often strong at local implementation hardening:

```text
add runtime validation
freeze mutable evidence
reject invalid values
guard recursive JSON normalization
cover enum stability
protect against accidental mutation
```

Those are implementation-level correctness patterns.

But this issue required a different question:

```text
Are all enum members describing the same kind of thing?
```

That is not a local syntax or safety question.

It depends on the system's domain model:

```text
What is a path?
What is an operation?
What is a technical status?
What is an evidence detail?
What belongs in the receipt source?
What belongs in evidence_summary?
```

AI can generate plausible names.

It may not automatically challenge whether all names occupy the same semantic level.

The issue was caught only after human review asked how normal read-side cases, snapshot-assisted cases, full replay cases, and technical failure cases would be routed.

---

## 13. Why This Is Not an AI Failure

This is not a failure of AI code generation.

It is a boundary lesson.

The AI-assisted implementation improved several important details:

```text
stronger runtime contract validation
JSON-safe evidence handling
immutability
depth guards
negative tests
contract non-goals
```

Those improvements are valuable.

The failure mode was narrower:

```text
the code was locally well-formed,
but the enum vocabulary did not fully preserve the intended semantic level.
```

The correct conclusion is not:

```text
do not use AI
```

The correct conclusion is:

```text
AI-generated contracts need semantic admission review.
```

For implementation details, the admission boundary can include:

```text
unit tests
type checks
frozen dataclasses
negative cases
JSON-safety checks
```

For domain contracts, the admission boundary must also include:

```text
semantic level consistency
authority boundary review
path vs operation separation
status vs source separation
outcome vs action separation
```

---

## 14. Reusable Review Heuristic

When reviewing AI-assisted enums or contracts, ask:

```text
1. Are all enum members describing the same kind of thing?

2. Are some members paths while others are operations?

3. Are some members sources while others are statuses?

4. Are some members causes while others are outcomes?

5. Are some members successful cases while others are neutral paths?

6. Does the name describe where evidence came from,
   or what condition was observed inside that evidence path?

7. Would a normal success case and a failure case from the same path
   use the same evidence_source?

8. If the same technical_status appears in different runtime paths,
   can the model represent that cleanly?
```

If the answer is unclear, the contract may be mixing semantic levels.

---

## 15. Corrected Stage 4B PR2 Direction

The corrected PR2 direction is:

```text
Keep:
- DecisionReceipt as frozen runtime governance evidence contract
- JSON-safe evidence_summary / metadata
- explicit subject / correlation / actor / cost / flags subcontracts
- no runtime action / policy / retry / persistence fields

Correct:
- DecisionReceiptEvidenceSource vocabulary

Do not change:
- Stage 4A SemanticOutcome
- Stage 4A technical_status mapper
- existing technical status names
```

The Stage 4A mapper remains:

```text
technical_status / raw runtime status name
→ SemanticOutcome
```

Stage 4B evidence source becomes:

```text
runtime evidence path
→ DecisionReceipt.evidence_source
```

These are separate axes.

---

## 16. Final Decision

Current decision:

```text
RUNTIME_TECHNICAL_STATUS
→ RUNTIME_OBSERVATION

READ_SIDE_REPLAY
→ READ_SIDE_PATH

SNAPSHOT_REPLAY
→ SNAPSHOT_TRUST_PATH

SNAPSHOT_ASSISTED_RESOLUTION
→ SNAPSHOT_ASSISTED_PATH

WRITE_SIDE_ADMISSION
→ unchanged

UNKNOWN
→ unchanged
```

This aligns `DecisionReceiptEvidenceSource` with its intended role:

```text
path-level receipt evidence source
```

The final lesson is:

```text
A typed enum is not automatically a correct semantic model.
```

Or, in the language of this project:

```text
generated code can be structured,
but semantic vocabulary still needs admission.
```

A shorter version:

```text
The code was correct enough to run.
The vocabulary was not yet correct enough to govern.
```
