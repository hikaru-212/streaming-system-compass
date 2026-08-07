# Stage 4B.1 PR Breakdown

[← Back to Stage 4B.1](README.md)

## Purpose

This note defines the implementation sequence for:

```text
Stage 4B.1 — DiagnosticTrace / ResolutionTrace
```

Stage 4B established `DecisionReceipt` as compact, durable semantic-governance
evidence.

Stage 4B.1 adds a separate responsibility:

```text
one execution path
→ bounded execution progress
→ terminal execution stage
→ safe structured diagnostic evidence
```

The goal is not to create a generic logging system.

The goal is to preserve execution-path evidence that is useful for diagnosis
but does not belong in the primary producer result, `SemanticOutcome`,
`DecisionReceipt`, runtime policy, execution strategy, or retry governance.

The first concrete read-side slice is:

```text
ProjectionSnapshotAssistedResolutionTrace
```

A write-side slice remains the implementation focus after the bounded
snapshot-assisted contract completed in PR2. Further snapshot-specific runtime
integration is deferred after the PR3 necessity revalidation.

The write-side slice is intentionally provisional until a source-grounded audit
confirms the exact current write-side execution stages and safe evidence.

---

## Stage Principle

Stage 4B.1 preserves the following separation:

```text
primary producer result
≠
DiagnosticTrace

DecisionReceipt
≠
DiagnosticTrace

DiagnosticTrace
≠
AttemptLog

one execution path
≠
multiple attempts

execution progress
≠
runtime decision

execution failure
≠
retry authorization
```

Responsibilities remain:

```text
SemanticOutcome
= shared semantic interpretation

DecisionReceipt
= compact durable governance evidence

DiagnosticTrace
= bounded detail for one execution path

AttemptLog
= multiple attempts, retry relationships, and intent consistency
```

Stage 4B.1 should prefer producer-specific traces over a premature
repository-wide generic trace schema.

A generic trace abstraction should be introduced only if multiple concrete
producers later demonstrate a stable shared contract.

---

## Why the First Read-Side Slice Uses Snapshot-Assisted Resolution

The snapshot-assisted resolver is the first read-side trace producer because it
already has a source-grounded multi-stage execution path with meaningful partial
progress:

```text
trusted snapshot boundary
→ snapshot compatibility / hydration
→ paginated tail loading and source validation
→ complete validated tail
→ tail replay
→ resolved result
```

It also has two distinct progress frontiers:

```text
tail validation progress
≠
tail replay progress
```

This makes it a useful first DiagnosticTrace case without requiring mutation,
retry governance, or runtime policy.

Projection-worker tracing was separately source-audited and is not planned for
current Stage 4B.1. Its normal `no_event` and `applied` exits already have result
artifacts. The non-duplicative evidence exists mainly on propagating exception
paths, where exposing partial progress would require a new exception wrapper,
sink, callback, or persistence transport that this stage does not authorize.

Do not add projection-worker `DiagnosticTrace` merely for symmetry.

---

## Why a Write-Side Slice Is Planned

Stage 4B.1 should not stop at snapshot tracing if the current write-side source
supports a bounded, useful single-execution trace.

The write side contains materially different execution paths, especially:

```text
PRE_TRANSACTION + OCC
```

and:

```text
IN_TRANSACTION + pessimistic locking
```

A write-side DiagnosticTrace may preserve execution-stage evidence such as:

```text
validation boundary
transaction boundary
concurrency boundary
authority re-read / admission boundary
append boundary
commit boundary
terminal stage
```

These names are conceptual only.

The final write-side vocabulary must be source-grounded and must not be frozen
until the dedicated write-side audit is reviewed.

The write-side trace is important because later Stage 4B.2 cost evidence is
primarily intended to compare write-side correctness-preserving strategies,
including where validation, transaction, lock, and conflict cost is paid.

However:

```text
DiagnosticTrace
≠
Measurement / Cost Evidence
```

Stage 4B.1 records what happened during one execution.

Stage 4B.2 may later record how expensive those execution choices were.

---

## Stage Branch / PR Branch Workflow

Stage 4B.1 uses its own integration branch:

```text
feat/stage4b1-diagnostic-resolution-trace
```

Individual PR branches are created from the current Stage 4B.1 integration
branch.

The intended workflow is:

```text
feat/stage4-runtime-semantic-governance
└── feat/stage4b1-diagnostic-resolution-trace
    ├── PR1 branch
    ├── PR2 branch
    ├── PR3 branch
    ├── later write-side PR branches
    └── closeout PR branch
```

Every Stage 4B.1 PR branch targets:

```text
feat/stage4b1-diagnostic-resolution-trace
```

No Stage 4B.1 PR targets:

```text
feat/stage4-runtime-semantic-governance
```

directly.

Only after Stage 4B.1 closeout does the Stage 4B.1 integration branch merge
back into the Stage 4 integration branch.

One PR may contain multiple commits.

The intended discipline remains:

```text
one PR
= one coherent semantic delivery unit

one commit
= one smaller boundary-preserving change
```

---

## Documentation-First Rule

When a new trace producer or semantic boundary is introduced, prefer:

```text
1. source-grounded audit / documentation
2. immutable contract
3. execution integration
4. focused equivalence and failure-path tests
5. closeout and deferral review
```

Do not invent a generalized trace model before concrete producer evidence
requires it.

---

## Current Stage 4B.1 PR Sequence

```text
PR1 — DiagnosticTrace / ResolutionTrace Boundary
PR2 — Snapshot-Assisted Resolution Trace Contract
PR3 — Snapshot Necessity Revalidation and Stage 4B.1 Reprioritization

Original PR3 — Snapshot-Assisted Traced Resolver API
Projection Worker DiagnosticTrace — source-audited decision

PR4+ — Write-Side DiagnosticTrace; exact decomposition remains source-grounded
Stage 4B.1 Closeout
```

Status:

```text
PR1
= COMPLETE

PR2
= COMPLETE

PR3
= COMPLETE / DOCUMENTATION ONLY

Original PR3
= SUPERSEDED BEFORE IMPLEMENTATION
= deferred until a concrete snapshot runtime consumer or workload justifies it

Projection Worker DiagnosticTrace
= AUDITED
= DO NOT ADD in current Stage 4B.1

PR4+
= PROVISIONAL; exact decomposition depends on the dedicated write-side source audit

Stage 4B.1 Closeout
= PLANNED
```

The PR4+ numbering is not implementation authority.

After the write-side audit, later work may be collapsed, split, or renamed if the
source proves that a smaller decomposition is safer.

The stable sequencing rule is:

```text
preserve the completed snapshot-assisted trace contract as a bounded reference
→ defer snapshot traced-resolver integration
→ retain the projection-worker DO NOT ADD decision
→ review the dedicated write-side audit
→ implement only justified bounded write-side trace scope
→ Stage 4B.1 closeout
```

---

# PR1 — DiagnosticTrace / ResolutionTrace Boundary

## Goal

Define the Stage 4B.1 responsibility before production trace code is added.

PR1 establishes:

```text
what DiagnosticTrace owns
what the primary result owns
what DecisionReceipt owns
what AttemptLog owns
which evidence is safe
which evidence is deferred
```

## Status

Complete.

## Branch

```text
docs/stage4b1-pr1-resolution-trace-boundary
```

## Completed Scope

PR1 added:

```text
docs/implementation_notes/stage_4b_1/README.md

docs/implementation_notes/stage_4b_1/
  projection_snapshot_assisted_resolution_trace.md
```

PR1 also aligned current-authority Stage 4B documentation with the merged
`PostgresDecisionReceiptTransactionOwner` baseline.

PR1 established that the first read-side slice is producer-specific and
in-memory.

It reconstructed the current snapshot-assisted resolver order:

```text
constructor validation
→ trusted snapshot precondition
→ exact snapshot lookup
→ snapshot compatibility
→ snapshot hydration
→ paginated tail loading with per-record source validation
→ complete validated tail accumulation
→ replay of the complete validated tail
→ successful result
```

It also established:

```text
resolved_state
= primary result only

source_global_position
= snapshot lineage only

currently propagating unexpected exception
→ continues to propagate
→ no guaranteed trace execution result
```

## Non-goals

PR1 does not implement:

```text
trace dataclasses
traced resolver API
trace persistence
DecisionReceipt linkage
AttemptLog
measurement
policy
strategy
retry
runtime action
```

---

# PR2 — Snapshot-Assisted Resolution Trace Contract

## Goal

Translate the PR1 snapshot-assisted trace boundary into a small immutable
production contract.

## Status

Complete and merged before PR3.

## Branch

```text
feat/stage4b1-pr2-resolution-trace-contract
```

## Current Implemented Scope

PR2 adds:

```text
src/pipeline/projection/
  projection_snapshot_assisted_resolution_trace.py

tests/unit/pipeline/projection/
  test_projection_snapshot_assisted_resolution_trace.py
```

PR2 narrowly updates:

```text
docs/implementation_notes/stage_4b_1/
  projection_snapshot_assisted_resolution_trace.md
```

PR2 introduces:

```text
ProjectionSnapshotAssistedResolutionTerminalStage

ProjectionSnapshotAssistedResolutionTrace

ProjectionSnapshotAssistedResolutionExecution
```

Final terminal stages:

```text
SNAPSHOT_PRECONDITION
SNAPSHOT_LOOKUP
SNAPSHOT_COMPATIBILITY
SNAPSHOT_HYDRATION
TAIL_SOURCE
TAIL_REPLAY
COMPLETED
```

Final trace fields:

```text
terminal_stage
snapshot_source_event_sequence
last_validated_tail_event_sequence
last_successfully_replayed_tail_event_sequence
source_expected_event_sequence
observed_event_sequence
observed_order_id
observed_event_id
```

PR2 deliberately omits:

```text
replay_expected_event_sequence
compatibility_failure_kind
source_global_position
snapshot_id
requested order_id
primary result status
primary result reason
resolved_state
partial state
trace_id
DecisionReceipt linkage
persistence
policy
retry
cost
```

## Contract Principle

PR2 defines only what a valid trace and execution envelope look like.

It does not collect evidence from the resolver.

It does not modify resolver execution.

## Non-goals

PR2 does not implement:

```text
resolve_order_with_trace(...)
resolver refactor
generic DiagnosticTrace base class
trace serializer
database persistence
write-side trace
AttemptLog
measurement
policy
strategy
retry
```

---

# PR3 — Snapshot Necessity Revalidation and Stage 4B.1 Reprioritization

## Goal

Record the complete snapshot-necessity revalidation, accept the current snapshot
stance, stop further snapshot-specific Stage 4B.1 runtime expansion after PR2,
and redirect remaining implementation review toward the write side.

## Status

Complete / documentation only.

## Branch

```text
docs/stage4b1-pr3-snapshot-necessity-revalidation
```

## Scope

PR3 records:

```text
Snapshot Trust Contract
= valid and reusable

projection snapshots for the current Order workload
= optional derived reconstruction / trust-reference infrastructure

snapshot-assisted trace contract
= complete in PR2 and retained as a bounded reference case

snapshot traced-resolver integration
= deferred before implementation

projection-worker DiagnosticTrace
= audited / DO NOT ADD in current Stage 4B.1

remaining Stage 4B.1 implementation focus
= write-side DiagnosticTrace, subject to dedicated source audit
```

This PR does not modify production code, resolver execution, tests, migrations,
dependencies, persistence, `DecisionReceipt`, or `AttemptLog`.

## Superseded Original PR3 Plan

The original development sequence assigned PR3 to:

```text
Snapshot-Assisted Traced Resolver API
→ resolve_order_with_trace(...)
→ ProjectionSnapshotAssistedResolutionExecution
```

That plan was revalidated and superseded before implementation. No current
operational snapshot consumer requires the API, and the current shallow Order
workload does not justify additional snapshot-specific runtime integration.

The plan is deferred rather than erased. A concrete future snapshot consumer,
materially deeper aggregate-local history, measured reconstruction cost, or
explicit recovery requirement may justify reopening it. Until then, PR2 is the
final bounded snapshot trace contract, and existing resolver behavior remains
unchanged.

---

# PR4 — Write-Side DiagnosticTrace Audit / Boundary

## Goal

Determine the smallest useful producer-specific write-side DiagnosticTrace
boundary from current source before adding write-side trace code.

## Status

Provisional.

A parallel read-only worktree audit may be used before this PR is frozen.

## Provisional Branch

```text
docs/stage4b1-pr4-write-side-trace-boundary
```

The final branch name should be chosen after the audit.

## Required Audit Scope

Reconstruct separately:

```text
PRE_TRANSACTION + OCC
```

and:

```text
IN_TRANSACTION + pessimistic locking
```

The audit must identify:

```text
actual execution stages
typed terminal outcomes
safe structured local evidence
evidence already owned by current results
evidence already owned by SemanticOutcome / DecisionReceipt
single-attempt boundary
currently propagating exceptions
transaction / commit ownership
```

The audit must determine whether both strategies can share one bounded
write-side trace vocabulary.

## Candidate Questions

The audit should answer:

```text
When does validation happen?

When does the business transaction begin?

When is authority re-read?

When is OCC checked?

When is a pessimistic lock acquired?

When is admission reached?

When is append reached?

When is idempotency persisted?

When is commit attempted / acknowledged?

Which progress is currently lost from the primary result?
```

These are audit questions, not frozen public stages.

## AttemptLog Boundary

A write-side DiagnosticTrace owns one execution only.

It must not include:

```text
previous_attempt_id
retry number
retry authorization
max attempts
backoff
next strategy
cross-attempt intent consistency
```

Those belong to Stage 4E.

## Stage 4B.2 Relationship

The PR4 audit should identify which execution boundaries later make cost
measurement meaningful.

It may identify candidate measurement points such as:

```text
validation duration
transaction duration
lock wait
append duration
wasted validation before OCC conflict
```

but it must not implement measurement.

## Stop Condition

Do not proceed to a write-side trace contract if the audit finds that a useful
trace would merely duplicate:

```text
PostgresWriteSideResult
SemanticOutcome
DecisionReceipt
existing transaction lifecycle evidence
```

or would require mixing in retry, policy, persistence, or unsafe exception
detail.

---

# PR5 — Write-Side DiagnosticTrace Contract

## Goal

If PR4 confirms a useful bounded write-side trace, define the smallest immutable
producer-specific contract for one write-side execution.

## Status

Provisional; depends on PR4.

## Provisional Branch

```text
feat/stage4b1-pr5-write-side-trace-contract
```

## Intended Direction

Prefer one contract that can represent both:

```text
PRE_TRANSACTION + OCC

IN_TRANSACTION + pessimistic locking
```

only if the shared vocabulary remains semantically clean.

Do not create a large union of mostly meaningless optional fields merely to
force both strategies into one dataclass.

If current source proves that the two paths require separate contracts, stop
for human review before implementation.

## Candidate Responsibility

A future contract may preserve bounded evidence such as:

```text
terminal execution stage
validation reached / completed
business transaction reached
concurrency boundary reached
lock reached / acquired when applicable
authority revalidation reached
admission reached
append reached / completed
commit reached / acknowledged
safe bounded identities already present in current execution
```

This list is conceptual only.

PR4 audit results must determine the final vocabulary.

## Required Boundary

The write-side trace must not become:

```text
business transaction result replacement
DecisionReceipt duplicate
transaction log
SQL log
retry log
AttemptLog
policy output
strategy output
measurement object
```

---

# PR6 — Write-Side Traced Execution Integration

## Goal

If PR5 is approved, connect the current write-side execution path to the
write-side trace contract without changing authoritative write semantics.

## Status

Provisional; depends on PR4 and PR5.

## Provisional Branch

```text
feat/stage4b1-pr6-write-side-traced-execution
```

## Intended Scope

Add the narrowest parallel or composition API needed to obtain:

```text
existing write-side primary result
+
one bounded write-side DiagnosticTrace
```

The exact API shape is not frozen by this breakdown.

## Required Preservation

PR6 must preserve:

```text
accepted history authority
idempotency semantics
validation placement
OCC behavior
pessimistic locking behavior
transaction boundaries
commit / rollback semantics
current result status semantics
current exception propagation
```

PR6 must not automatically retry or switch strategies.

A conflict or lock timeout may terminate the current trace, but any subsequent
attempt belongs to Stage 4E.

## Non-goals

PR6 does not implement:

```text
automatic retry
retry count
attempt chaining
strategy selection
cost timing
benchmarking
DecisionReceipt materialization
trace persistence
generic logging
```

---

# PR7 — Stage 4B.1 Closeout

## Goal

Close Stage 4B.1 after the implemented concrete trace slices have been reviewed
as a coherent DiagnosticTrace responsibility.

## Status

Planned.

## Recommended Branch

```text
docs/stage4b1-pr7-closeout
```

The final numbering may move if the provisional write-side sequence is changed.

## Closeout Questions

Closeout should explicitly answer:

```text
Did snapshot-assisted resolution retain a safe bounded immutable trace contract?

Was snapshot traced-resolver integration explicitly deferred with its workload
and consumer rationale?

Did the existing primary resolver API remain behaviorally unchanged?

Was a useful write-side trace implemented to the scope justified by source audit,
or explicitly deferred if the audit did not justify one?

Was projection-worker trace left unimplemented under its recorded DO NOT ADD
decision?

Can PRE_TRANSACTION + OCC and IN_TRANSACTION + pessimistic execution be
explained without mixing in retry or policy?

Did DiagnosticTrace remain separate from DecisionReceipt?

Did DiagnosticTrace remain separate from AttemptLog?

Did any trace persistence accidentally become required?

Is a repository-wide generic DiagnosticTrace abstraction actually justified?
```

## Completion Criteria

Stage 4B.1 may close when:

```text
the snapshot-assisted trace contract is implemented
the snapshot-assisted trace contract is tested
snapshot traced resolver integration is explicitly deferred with rationale
existing resolver behavior remains unchanged
projection-worker trace has an audited, recorded DO NOT ADD decision
the write-side trace audit has a recorded decision
write-side trace is implemented only to the source-justified scope, or explicitly deferred
single-execution vs AttemptLog boundaries are explicit
unsafe exception / SQL / payload evidence remains excluded
DecisionReceipt remains compact and separate
documentation and branch status are aligned
```

If the write-side audit concludes that no additional trace is justified, the
closeout must record that decision rather than forcing an unnecessary
implementation.

## Closeout Non-goals

Stage 4B.1 closeout does not require:

```text
trace persistence
trace serializer
database tables
retention policy
normal projection-worker trace
full observability platform
Stage 4B.2 measurements
RuntimeDecisionPolicy
StrategySelector
RetryGovernance
AttemptLog
```

---

## Stage 4B.1 and Stage 4B.2 Boundary

Stage 4B.1 answers:

```text
What happened during this one execution?
```

Stage 4B.2 answers:

```text
What did this execution strategy cost?
```

The primary Stage 4B.2 motivation is write-side strategy cost, especially:

```text
PRE_TRANSACTION + OCC
vs
IN_TRANSACTION + pessimistic locking
```

Potential later cost evidence includes:

```text
validation_elapsed_ms
transaction_elapsed_ms
db_append_elapsed_ms
lock_wait_ms
total_attempt_elapsed_ms
wasted validation before OCC conflict
```

Read-side cost evidence is secondary and should be implemented only when a
concrete policy, strategy, or optimization consumer requires it.

Stage 4B.2 should not become a snapshot benchmark project merely because the
first Stage 4B.1 trace producer is snapshot-assisted resolution.

---

## Projection-Worker DiagnosticTrace Decision

Projection-worker `DiagnosticTrace` was source-audited and is not planned for
current Stage 4B.1.

Reason:

```text
no_event
= no currently visible exact-next eligible event

applied
= one event successfully completed through transaction exit
```

Those normal exits already have result artifacts. The genuinely non-duplicative
trace value exists mainly when execution selected an event and made partial
progress before an exception propagated without returning an artifact.

Guaranteeing trace delivery on those paths would require a new transport such as:

```text
exception wrapper
sink or callback
persistence mechanism
```

Stage 4B.1 does not authorize that transport merely to guarantee a trace.
Therefore:

```text
Projection Worker DiagnosticTrace
= AUDITED
= DO NOT ADD in current Stage 4B.1
```

Do not add it merely for symmetry. `global_position` remains lineage and
deterministic scheduling evidence, not projection completeness.

---

## Stage 4B.1 Final Boundary

Stage 4B.1 should leave the repository with this conceptual separation:

```text
producer execution
→ primary result
   +
   bounded DiagnosticTrace when supported

primary result
→ SemanticOutcome
→ DecisionReceipt

multiple later executions / retries
→ Stage 4E AttemptLog
```

A trace explains one path.

A receipt preserves compact governance evidence.

An attempt log relates multiple executions.

None of these replaces the others.

---

## Current Next Step

Current remaining development sequence:

```text
1. preserve PR2 as the final bounded snapshot trace contract
2. keep snapshot traced-resolver integration deferred
3. retain the projection-worker DO NOT ADD decision
4. review the dedicated write-side source audit
5. finalize PR4+ decomposition from source evidence
6. implement only the approved bounded write-side trace scope
7. run Stage 4B.1 closeout
```

Do not start Stage 4B.2 implementation until the write-side trace audit and
Stage 4B.1 write-side scope decision have been reviewed.
