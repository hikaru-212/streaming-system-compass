# Stage 4B.1 — DiagnosticTrace / ResolutionTrace

[← Back to Implementation Notes](../README.md)

## Current Status

```text
Stage 4B.1
= DiagnosticTrace / ResolutionTrace

first source-grounded slice
= ProjectionSnapshotAssistedResolutionTrace

current status
= documentation and contract planning only

implementation
= not yet present
```

Stage 4A and Stage 4B PR1–PR7 are complete. The separately delivered
`PostgresDecisionReceiptTransactionOwner` is implemented, tested, and merged,
but automatic receipt construction and materialization remain deferred.

Stage 4B.1 is the current formal development stage. This directory defines the
planning boundary for later implementation PRs; it does not claim that a trace
contract or traced resolver API exists.

## Purpose

Stage 4B.1 separates one execution path's bounded progress and terminal stage
from:

- the primary producer result;
- compact `DecisionReceipt` governance evidence;
- multiple attempts and retry relationships;
- policy, strategy, fallback, and runtime action.

The first source-grounded slice is the snapshot-assisted resolver because its
current source already distinguishes snapshot preparation, complete tail-source
validation, and tail replay.

## Current Planning Note

- [Projection Snapshot-Assisted Resolution Trace](projection_snapshot_assisted_resolution_trace.md)

The note is grounded in the current resolver, its focused unit tests, and the
existing read-side semantic-outcome and DecisionReceipt adapters. Provisional
names or fields in that note require explicit PR2 approval before they become a
production contract.

## Intended PR Sequence

```text
feat/stage4b1-diagnostic-resolution-trace
├── PR1 documentation and boundary
├── PR2 immutable trace contract
├── PR3 parallel traced resolver API
└── later PR only if source-grounded need appears
```

Every Stage 4B.1 PR branch targets:

```text
feat/stage4b1-diagnostic-resolution-trace
```

Only after Stage 4B.1 closeout does that integration branch merge into:

```text
feat/stage4-runtime-semantic-governance
```

## Boundary

The initial slice is producer-specific and in memory. Stage 4B.1 PR1 does not
implement production code, tests, persistence, serialization, migrations,
`DecisionReceipt` linkage, `AttemptLog`, retry, fallback, policy, strategy,
measurement, cost evidence, observability deployment, or runtime action.
