# Stage 4B.1 — DiagnosticTrace / ResolutionTrace

[← Back to Implementation Notes](../README.md)

## Current Status

```text
Stage 4B.1
= DiagnosticTrace / ResolutionTrace

bounded reference slice
= ProjectionSnapshotAssistedResolutionTrace

current status
= PR6 complete / repository validation accepted

implemented
= PR2 immutable snapshot-assisted trace contract

write-side characterization
= complete / 10 focused PostgreSQL scenarios

write-side trace contract
= complete / immutable producer-specific canonical-prefix contract

write-side traced execution integration
= implemented / producer-specific in-memory result + trace envelope

snapshot traced resolver integration
= deferred before implementation

next formal step
= PR7 closeout / handoff
```

Stage 4A and Stage 4B PR1–PR7 are complete. The separately delivered
`PostgresDecisionReceiptTransactionOwner` is implemented, tested, and merged,
but automatic receipt construction and materialization remain deferred.

Stage 4B.1 is the current formal development stage. PR1 completed its boundary
documentation, and PR2 implemented the immutable producer-specific trace and
execution-envelope contract. No traced resolver API exists.

The original snapshot-assisted traced-resolver PR3 was revalidated and
superseded before implementation. No current operational snapshot consumer
requires that API, so the PR2 contract remains a bounded reference case rather
than a reason for further snapshot-specific runtime expansion.

Projection-worker `DiagnosticTrace` was also source-audited and is not planned
for current Stage 4B.1. Its normal exits already have result artifacts, while
failure-path partial progress would require a new trace-on-exception transport
that this stage does not authorize.

The write-side source audit and formal PR4 execution characterization are now
complete. PR4 established the current PRE_TRANSACTION + OCC and
IN_TRANSACTION + pessimistic topologies, their mixed-strategy correctness
handoffs, and the transaction-local boundary between append success and durable
commit. PR5 used that evidence to implement the immutable producer-specific
write-side DiagnosticTrace contract. PR6 now integrates that contract through
parallel traced APIs while preserving the legacy APIs and shared write
algorithms. The production integration, focused pure-unit evidence, and PostgreSQL
integration coverage are complete. Final repository-wide validation executed
the full `tests` tree successfully:

```text
pytest tests -q
1650 passed in 30.93s
```

PR6 is therefore accepted for the current repository state and may proceed to
PR7 closeout / handoff.

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

## Current Notes

- [Projection Snapshot-Assisted Resolution Trace](projection_snapshot_assisted_resolution_trace.md)
- [Write-Side Execution Characterization](write_side_execution_characterization.md)
- [Write-Side Execution Trace Contract](write_side_execution_trace_contract.md)
- [Write-Side Traced Execution](write_side_traced_execution.md)
- [Stage 4B.1 PR Breakdown](stage_4b_1_pr_breakdown.md)

The snapshot note is grounded in the current resolver, its focused unit tests,
and the existing read-side semantic-outcome and `DecisionReceipt` adapters. It
preserves the PR1 boundary and the final PR2 immutable contract while recording
the later runtime-integration deferral.

The write-side characterization note records the PR4 source-grounded execution
model and executable evidence without turning test-only checkpoints, database
wait states, or concurrency mechanics into public DiagnosticTrace vocabulary.

The write-side execution trace note records the final PR5 immutable contract,
its placement-specific canonical sequences, and the separation between retained
topology evidence and primary-result ownership of committed completion.

The write-side traced-execution note records the implemented PR6 envelope,
invocation-local collection, shared legacy/traced execution paths, synchronous
pre-commit composition boundary, validation evidence, and deferred PR7
implications.

## Intended PR Sequence

```text
feat/stage4b1-diagnostic-resolution-trace
├── PR1 documentation and boundary — complete
├── PR2 immutable snapshot-assisted trace contract — complete
├── original PR3 snapshot-assisted traced resolver API — superseded before implementation
├── PR3 snapshot necessity revalidation and reprioritization — complete / documentation only
├── PR4 write-side execution characterization — complete
├── PR5 write-side DiagnosticTrace contract — complete
├── PR6 write-side traced execution integration — complete / accepted
└── PR7 Stage 4B.1 closeout and handoff — next
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

The implemented Stage 4B.1 trace contracts are producer-specific and in memory.
Stage 4B.1 does not make snapshot runtime integration mandatory and does not add
trace
persistence, serialization, migrations, `DecisionReceipt` linkage, `AttemptLog`,
retry, fallback, policy, strategy, measurement, cost evidence, observability
deployment, or runtime action.
