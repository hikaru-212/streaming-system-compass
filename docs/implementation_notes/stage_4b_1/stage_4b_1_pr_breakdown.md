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

The dedicated write-side source audit and formal PR4 execution characterization
are complete. They established a bounded, source-grounded execution model for
PRE_TRANSACTION + OCC and IN_TRANSACTION + pessimistic locking, including
mixed-strategy handoffs and uncommitted stream-position arbitration. PR5 may now
freeze only the smallest immutable trace vocabulary justified by that evidence.

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

PR4 — Write-Side Execution Characterization
PR5 — Write-Side DiagnosticTrace Contract
PR6 — Write-Side Traced Execution Integration
PR7 — Stage 4B.1 Closeout
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

PR4
= COMPLETE
= write-side execution characterization

PR5
= NEXT
= immutable write-side DiagnosticTrace contract

PR6
= PROVISIONAL; depends on PR5

PR7
= PLANNED
```

The earlier PR4 audit / boundary plan was refined after the parallel read-only
write-side source audit completed. The formal PR4 therefore became executable
write-side execution characterization rather than another audit-only document.

The stable sequencing rule is:

```text
preserve the completed snapshot-assisted trace contract as a bounded reference
→ defer snapshot traced-resolver integration
→ retain the projection-worker DO NOT ADD decision
→ preserve PR4 write-side execution characterization as the evidence baseline
→ freeze the smallest justified write-side trace contract in PR5
→ integrate traced execution only after PR5
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

# PR4 — Write-Side Execution Characterization

## Goal

Establish executable evidence for the current PostgreSQL write-side execution
topology before freezing a public write-side DiagnosticTrace contract.

PR4 does not add production trace code. It turns the completed source audit into
a bounded, falsifiable execution model that PR5 can safely use.

## Status

Complete.

## Branch

```text
feat/stage4b1-pr4-write-side-execution-characterization
```

## Completed Scope

PR4 adds:

```text
docs/implementation_notes/stage_4b_1/
  write_side_execution_characterization.md

tests/integration/pipeline/transactional/
  test_postgres_write_side_execution_characterization.py
```

The formal characterization contains 10 focused PostgreSQL scenarios.

### Strategy-local topology

```text
1. PRE validation BLOCK before business UOW / admission
2. PRE authoritative REPLAY after preliminary MISS
3. PRE append-time OCC conflict without reload or retry
4. IN+pessimistic ACCEPTED path in bounded order
5. IN+pessimistic lock non-acquisition
6. IN+pessimistic validation BLOCK before append
```

### Mixed-strategy handoffs

```text
7. IN+pessimistic crosses authoritative idempotency/history/validation,
   PRE+optimistic commits before IN append,
   IN remains MISS and terminates as STALE_WRITE / ADMISSION_REJECTED

8. PRE+optimistic completes preliminary work before business UOW,
   IN+pessimistic commits the same request,
   PRE authoritative idempotency returns REPLAY before optimistic preparation
```

These scenarios prove that valid writer compositions can coexist per instance
and that the pessimistic advisory lock is cooperative rather than global.
Correctness can hand off from idempotency to append-time stream arbitration
depending on when competing authority becomes durable.

### Uncommitted stream-position arbitration

```text
9. owner append succeeds but remains uncommitted,
   contender cannot see the row through ordinary READ_COMMITTED history,
   contender reaches the same-position INSERT and waits,
   owner COMMIT makes contender resume as STALE_WRITE / ADMISSION_REJECTED

10. same uncommitted-position arrangement,
    owner ROLLBACK releases the physical position,
    contender proceeds and becomes the only durable accepted writer
```

These scenarios establish:

```text
append statement success
≠ durable accepted authority

MVCC invisibility
≠ absence of physical uniqueness arbitration

commit / rollback
= determines which transaction may become durable authority
```

The blocking cases use separate PostgreSQL connections, explicit
`READ_COMMITTED`, deterministic thread / event synchronization, and observed
PostgreSQL lock-wait state. Elapsed time is used only as a bounded test-runner
safety limit, not as proof of the race.

## Source-Grounded Findings

PR4 confirms the following current topology.

### PRE_TRANSACTION + OCC

```text
preliminary idempotency
→ preliminary history
→ candidate / validation
→ business UOW
→ authoritative idempotency
→ optimistic preparation
→ append-time OCC / continuity arbitration
→ idempotency persistence
→ clean commit
```

### IN_TRANSACTION + pessimistic locking

```text
business UOW
→ authoritative idempotency
→ pessimistic stream preparation
→ protected history
→ candidate / validation
→ append-time continuity arbitration
→ idempotency persistence
→ clean commit
```

The two compositions may be constructed simultaneously on separate connections.
The current production bootstrap does not compose them together, but no global
strategy registry or singleton makes them mutually exclusive.

## Evidence Ownership

PR4 confirms that current primary artifacts already own terminal meaning:

```text
PostgresWriteSideResult
SemanticOutcome
DecisionReceipt
```

The remaining DiagnosticTrace value is execution topology and bounded progress,
not result duplication.

PR4 also preserves:

```text
one create_order(...) / pay_order(...) call
= one Stage 4B.1 execution

later invocation / retry relationship
= Stage 4E AttemptLog
```

## Commit / Durability Boundary

A successful append means the event INSERT succeeded inside the current
transaction. It does not mean the event is durable.

Normal `ACCEPTED` delivery reaches the caller only after clean UOW commit
returns. An event inserted before commit can still disappear on rollback.

PR4 therefore does not introduce a public `COMMITTED`, `NOT_COMMITTED`, or
`UNKNOWN` trace state. Commit ambiguity remains outside this characterization.

## Deferred Hardening — Concurrent Idempotency MISS→Record Arbitration

PR4 also records, but does not absorb, a separate source-supported request
identity race:

```text
same request_id
+ different order streams

writer A authoritative idempotency = MISS
writer B authoritative idempotency = MISS

A event append succeeds transaction-locally
B event append succeeds transaction-locally

both later attempt:
INSERT idempotency_records(request_id=...)
```

There is currently no request-level lock between idempotency `check()` and
`record()`. The `idempotency_records.request_id` primary key is therefore the
final physical arbiter once both writers have already observed `MISS`.

The losing `record()` may surface a raw PostgreSQL `UniqueViolation`; current
write-side code does not reclassify that path into typed `REPLAY` or `CONFLICT`.
Exceptional UOW rollback removes the loser's already-inserted event, so durable
state can remain consistent even though failure delivery is not yet a stable
idempotency semantic.

This is intentionally deferred because resolving it may require a semantic
contract decision rather than additional PR4 topology evidence.

```text
concurrent idempotency check→record TOCTOU
= source-supported
= exact two-connection characterization absent
= separate hardening gap
= not part of current PR4 acceptance
```

## Stage 4B.2 Relationship

PR4 identifies meaningful later measurement boundaries such as:

```text
validation duration
business-transaction duration
pessimistic lock-acquisition call duration
append / OCC arbitration duration
idempotency-persistence duration
wasted validation before OCC conflict
```

It does not implement measurement and does not rank PRE versus IN performance.

## PR5 Handoff

PR4 justifies proceeding to a bounded write-side trace contract.

PR5 must still independently decide which characterized checkpoints deserve
stable public vocabulary. It must not freeze every test-only checkpoint, SQL
wait state, or database-internal detail.

The first explicit PR5 re-review remains whether:

```text
CLEAN_COMMIT_RETURNED
```

adds non-duplicative trace evidence beyond normal successful primary-result
delivery.

## Non-goals

PR4 does not implement:

```text
production DiagnosticTrace dataclasses
traced write-side APIs
trace persistence
DecisionReceipt persistence changes
retry / AttemptLog
policy / strategy selection
measurement / benchmarking
commit-ambiguity reconciliation
generic cross-producer DiagnosticTrace
concurrent idempotency semantic redesign
```

---

# PR5 — Write-Side DiagnosticTrace Contract

## Goal

If PR4 confirms a useful bounded write-side trace, define the smallest immutable
producer-specific contract for one write-side execution.

## Status

Next.

PR4 has completed the source-grounded execution characterization. PR5 may now
freeze the smallest immutable producer-specific trace contract justified by
that evidence.

## Branch

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

PR4 characterization results are the evidence baseline for the final vocabulary.

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
the write-side execution characterization is complete and recorded
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
4. preserve PR4 write-side execution characterization as the evidence baseline
5. implement PR5 immutable write-side DiagnosticTrace contract
6. re-review CLEAN_COMMIT_RETURNED before freezing the PR5 checkpoint vocabulary
7. adapt PR6 traced execution integration only after PR5 is accepted
8. run Stage 4B.1 closeout
```

The concurrent idempotency `check → record` TOCTOU remains a separate hardening
gap and must not be pulled into PR5 merely because PR4 exposed it.

Do not start Stage 4B.2 implementation until the PR5/PR6 write-side trace scope
and Stage 4B.1 closeout are complete.

