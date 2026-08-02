# Deferred Backlog — Projection Without Accepted-History Authority

## Status

**Deferred — likely near-term Layer 2 vocabulary hardening**

Do not fold this into current PR5 or PR6. Revisit after both are merged and the Stage 4B integration branch is rebaselined.

## Problem

The current `ReplayValidationResult` vocabulary allows:

```text
status = NO_ACCEPTED_HISTORY
expected_state = None
persisted_state = present
```

This means:

```text
accepted history for the order = absent
persisted projection state for the order = present
```

The current status names only the missing authority side. It does not explicitly name the more serious fact that a derived state exists without current accepted-history support.

This is materially different from:

```text
accepted history absent
persisted projection absent
```

The current vocabulary therefore collapses two different conditions into one status.

## Why this matters

A projection should be derived from accepted history. If projection state exists without accepted history, possible causes include:

- direct or unauthorized writes to `projection_states`;
- deleted or lost accepted history;
- migration or repair errors;
- mismatched order identity;
- fixtures or scripts bypassing the normal worker path;
- derived state produced from a source that is no longer present.

The affected order projection cannot be treated as trusted.

A single occurrence does not prove the whole projection table is wrong, but it proves that the projection-integrity assumption has been violated at least once. That justifies broader blast-radius validation.

## Current and proposed status matrix

Current:

| Status | Expected | Persisted |
|---|---:|---:|
| `MATCH` | present | present and equal |
| `DRIFT` | present | present and unequal |
| `MISSING_PROJECTION` | present | absent |
| `NO_ACCEPTED_HISTORY` | absent | absent or present |

Possible future matrix:

| Status | Expected | Persisted |
|---|---:|---:|
| `MATCH` | present | present and equal |
| `DRIFT` | present | present and unequal |
| `MISSING_PROJECTION` | present | absent |
| `NO_ACCEPTED_HISTORY` | absent | absent |
| `PROJECTION_WITHOUT_ACCEPTED_HISTORY` | absent | present |

Candidate names:

```text
PROJECTION_WITHOUT_ACCEPTED_HISTORY
PROJECTION_WITHOUT_AUTHORITY
ORPHAN_PROJECTION
UNSUPPORTED_DERIVED_STATE
```

The final name should describe the technical fact without selecting a recovery action.

## Expected handling by layer

### Producer contract

Likely first change:

```text
ReplayValidationStatus
ReplayValidationResult
DurableReplayValidator
```

Introduce a distinct status for:

```text
expected_state absent
persisted_state present
```

This belongs in the producer vocabulary, not only in a mapper-side shape validator.

### Stage 4A

Map it to a distinct `LAYER_2_READ_SIDE` semantic outcome expressing:

```text
derived state exists without accepted-history authority
```

It should not be treated as ordinary drift.

### DecisionReceipt

Preserve bounded evidence such as:

```text
order_id
technical status
expected_state_present = false
persisted_state_present = true
```

Do not automatically set rebuild, fallback, review, or retry flags.

### Stage 4B.3

This condition should stop trust continuation for the affected order and become a strong revalidation/investigation trigger.

### Stage 4C / 4D

Later governance may choose:

```text
quarantine affected order
block use of affected projection
validate all orders for the projection definition / epoch
rebuild one order
rebuild the full projection
fallback to accepted-history replay
escalate for investigation
```

The technical status itself should not hardcode those actions.

## Expected operational response

Likely first response:

```text
detect projection without authority
→ stop qualifying the affected boundary
→ run a broader projection validation scan
→ determine blast radius
→ choose local or full remediation from evidence
```

A full-table rebuild should not be automatic from one orphan row. A full validation scan is the more disciplined first step.

## Proposed placement

Handle after PR5 and PR6 merge.

Suggested sequence:

```text
1. Merge PR5
2. Merge PR6
3. Rebaseline Stage 4B integration branch
4. Add a Layer 2 vocabulary-hardening note
5. Add explicit projection-without-authority status
6. Align Stage 4A semantic mapping
7. Align DecisionReceipt mapping and tests
8. Make Stage 4B.3 treat it as a trust-stop / revalidation trigger
9. Let Stage 4C / 4D decide scan, quarantine, fallback, or rebuild
```

Tentative label:

```text
Stage 4B Interlude — Layer 2 orphan-projection vocabulary hardening
```

If the work stays limited to semantic correction, keep it narrow. If it expands into scans, checkpoint invalidation, or remediation, move that broader work into Stage 4B.3 / 4C / 4D.

## Likely files

Revalidate exact paths after merge.

```text
src/pipeline/projection/replay_validator.py
src/compass/runtime/read_side_outcome_mapping.py
src/compass/runtime/read_side_decision_receipt_mapping.py

tests/integration/pipeline/projection/test_durable_replay_validation.py
tests/unit/compass/runtime/test_read_side_outcome_mapping.py
tests/unit/compass/runtime/test_read_side_decision_receipt_mapping.py

docs/implementation_notes/stage_4a/read_side_outcome_mapping.md
docs/implementation_notes/stage_4b/read_side_snapshot_decision_receipt_mapping.md
docs/roadmap/stage_4_runtime_semantic_governance_roadmap.md
```

## Non-goals

This backlog item does not itself implement:

- projection-wide scan orchestration;
- quarantine;
- rebuild;
- fallback;
- retry;
- operator workflow;
- trust-checkpoint storage;
- background scheduling;
- projection delivery infrastructure.

Its first responsibility is semantic precision:

> Distinguish “no accepted history and no projection” from “no accepted history but persisted projection exists.”

## Open questions

1. What should the exact technical status name be?
2. Should one occurrence also create a projection-definition integrity warning?
3. Which Stage 4A semantic code should represent derived state without authority?
4. Should one occurrence require a projection-wide validation scan?
5. How should Stage 4B.3 suspend or invalidate trust for the affected order?
6. Should broader scan results produce per-order receipts or an aggregate record?
7. When should remediation escalate from local cleanup to full rebuild?
8. How should accepted-history loss be distinguished from unauthorized projection insertion?
9. Which role may authorize removal of an orphan projection?
10. Should this also be treated as a security / permission-integrity event?

## Decision summary

```text
Do not change PR5 or PR6 now.

Record the vocabulary gap.

Plan a narrow post-merge Layer 2 semantic-hardening step.

Treat projection-without-authority as stronger than ordinary
NO_ACCEPTED_HISTORY.

Use it later as a trust-continuation stop and broader validation trigger.

Leave scan, quarantine, rebuild, fallback, and retry decisions to later
governance stages.
```
