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

A write-side slice became the implementation focus after the bounded
snapshot-assisted contract completed in PR2. PR4 characterization, the PR5
immutable contract, and PR6 production integration are complete. Repository-wide
validation has now executed the full `tests` tree successfully:

```text
pytest tests -q
1650 passed in 30.93s
```

PR6 is accepted for the current repository state. PR7 closes Stage 4B.1 through
documentation, [ADR 0022](../../adr/0022_traced_write_side_execution_fails_closed_before_business_commit.md),
and explicit later-stage handoffs. Further snapshot-specific runtime integration
remains deferred after the PR3 necessity revalidation.

The dedicated write-side source audit and formal PR4 execution characterization
are complete. They established a bounded, source-grounded execution model for
PRE_TRANSACTION + OCC and IN_TRANSACTION + pessimistic locking, including
mixed-strategy handoffs and uncommitted stream-position arbitration. PR5 used
that evidence to freeze the smallest immutable trace vocabulary justified by
the current producer topology.

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

## Why Stage 4B.1 Includes a Write-Side Slice

Stage 4B.1 does not stop at snapshot tracing because the current write-side
source supports a bounded, useful single-execution trace.

The write side contains materially different execution paths, especially:

```text
PRE_TRANSACTION + OCC
```

and:

```text
IN_TRANSACTION + pessimistic locking
```

Before PR4 characterization and the PR5 freeze, candidate execution-stage
evidence included:

```text
validation boundary
transaction boundary
concurrency boundary
authority re-read / admission boundary
append boundary
commit boundary
terminal stage
```

These names were conceptual inputs rather than the final PR5 vocabulary.

The final write-side vocabulary is source-grounded in the completed PR4 audit
and characterization and is frozen by the accepted PR5 contract.

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
= COMPLETE
= immutable write-side DiagnosticTrace contract

PR6
= COMPLETE / ACCEPTED
= write-side traced execution integration
= repository-wide validation: 1650 passed in 30.93s

PR7
= COMPLETE / DOCUMENTATION CLOSEOUT
= closeout authority, ADR 0022, deferred handoffs, and global alignment
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
→ preserve the completed PR5 immutable write-side trace contract
→ preserve the implemented PR6 traced execution integration
→ preserve accepted repository-wide validation
→ complete the PR7 Stage 4B.1 closeout
→ hand measurement and cost evidence to Stage 4B.2
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

## PR5 Handoff and Accepted Decision

PR4 justified proceeding to a bounded write-side trace contract.

PR5 independently selected the stable producer-topology checkpoints. It did not
freeze every test-only checkpoint, SQL wait state, or database-internal detail.

The PR5 re-review concluded:

```text
CLEAN_COMMIT_RETURNED
= intentionally omitted
```

Clean committed producer completion is already owned by normal successful
primary-result delivery. DiagnosticTrace owns the bounded topology traversed
before that delivery and does not duplicate commit evidence.

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

Define the smallest immutable producer-specific contract for one write-side
execution.

## Status

Complete.

PR5 implements and tests the immutable producer-specific write-side
DiagnosticTrace contract justified by the accepted PR4 evidence.

## Branch

```text
feat/stage4b1-pr5-write-side-trace-contract
```

## Completed Scope

PR5 adds:

```text
src/pipeline/transactional/
  postgres_write_side_execution_trace.py

tests/unit/pipeline/transactional/
  test_postgres_write_side_execution_trace.py

docs/implementation_notes/stage_4b_1/
  write_side_execution_trace_contract.md
```

The production contract is:

```text
PostgresWriteSideExecutionCheckpoint

PostgresWriteSideExecutionTrace
= immutable
= producer-specific
= in memory only
```

`PostgresWriteSideExecutionTrace` stores exactly:

```text
validation_placement
checkpoints
```

and derives:

```text
terminal_checkpoint = checkpoints[-1]
```

The exact checkpoint vocabulary is:

```text
PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED
ACCEPTED_HISTORY_OBSERVED
VALIDATION_RETURNED
BUSINESS_UOW_REACHED
AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED
CONCURRENCY_PREPARATION_RETURNED
APPEND_ADMISSION_RETURNED
IDEMPOTENCY_PERSISTENCE_RETURNED
```

Every valid trace contains a non-empty exact prefix of the canonical sequence
for its actual `ValidationPlacement`.

### PRE_TRANSACTION Canonical Sequence

```text
PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED
→ ACCEPTED_HISTORY_OBSERVED
→ VALIDATION_RETURNED
→ BUSINESS_UOW_REACHED
→ AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED
→ CONCURRENCY_PREPARATION_RETURNED
→ APPEND_ADMISSION_RETURNED
→ IDEMPOTENCY_PERSISTENCE_RETURNED
```

### IN_TRANSACTION Canonical Sequence

```text
BUSINESS_UOW_REACHED
→ AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED
→ CONCURRENCY_PREPARATION_RETURNED
→ ACCEPTED_HISTORY_OBSERVED
→ VALIDATION_RETURNED
→ APPEND_ADMISSION_RETURNED
→ IDEMPOTENCY_PERSISTENCE_RETURNED
```

## Commit Evidence Ownership

`CLEAN_COMMIT_RETURNED` is intentionally omitted. DiagnosticTrace owns bounded
execution topology, while successful primary-result delivery owns clean
committed producer completion.

`IDEMPOTENCY_PERSISTENCE_RETURNED` means only that
`PostgresIdempotencyStore.record(...)` returned normally inside the current
business transaction. It does not establish transaction commit, durable
idempotency authority, cross-transaction visibility, or successful
primary-result delivery.

For accepted execution, clean commit finality is established by successful
primary-result delivery. The trace establishes only the bounded execution
topology that preceded that delivery; commit finality does not follow from
`IDEMPOTENCY_PERSISTENCE_RETURNED` itself.

## Validation

Focused pure unit validation:

```text
./.venv/bin/python -m pytest -q \
  tests/unit/pipeline/transactional/test_postgres_write_side_execution_trace.py

40 passed
```

PR5 unit validation requires no PostgreSQL, Docker, or `TEST_DATABASE_URL`.

## Non-goals

PR5 does not add:

```text
traced write-side API
production checkpoint instrumentation
result + trace envelope
result / trace coherence
retry
AttemptLog
strategy selection
measurement
trace persistence
DecisionReceipt changes
exception-carried trace
commit-ambiguity redesign
```

---

# PR6 — Write-Side Traced Execution Integration

## Goal

Connect the current write-side execution path to the accepted PR5 trace contract
without changing authoritative write semantics.

## Status

Production integration, focused pure-unit validation, and PostgreSQL
integration coverage are complete. Final repository-wide validation executed
the full `tests` tree successfully:

```text
pytest tests -q
1650 passed in 30.93s
```

PR6 is accepted for the current repository state.

## Branch

```text
feat/stage4b1-pr6-write-side-traced-execution
```

## Completed Scope

PR6 adds:

```text
src/pipeline/transactional/
  postgres_write_side.py

tests/unit/pipeline/transactional/
  test_postgres_write_side_traced_execution_unit.py

tests/integration/pipeline/transactional/
  test_postgres_write_side_traced_execution_integration.py

docs/implementation_notes/stage_4b_1/
  write_side_traced_execution.md
```

The immutable producer-specific envelope is:

```text
PostgresWriteSideExecution
├── result: PostgresWriteSideResult
└── trace: PostgresWriteSideExecutionTrace
```

Its constructor validates only:

```text
trace.validation_placement
+ result.outcome
+ trace.terminal_checkpoint
```

It does not become a second validator for nested idempotency, validation,
stream-admission, append-admission, or accepted-event result semantics.

PR6 adds parallel APIs:

```text
create_order_with_trace(...) -> PostgresWriteSideExecution
pay_order_with_trace(...) -> PostgresWriteSideExecution
```

The legacy APIs remain unchanged:

```text
create_order(...) -> PostgresWriteSideResult
pay_order(...) -> PostgresWriteSideResult
```

Legacy and traced entry points share the same PRE and IN execution algorithms.
Only traced entry points create one private invocation-local collector. That
collector immediately validates each new immutable prefix through the accepted
PR5 constructor and is never stored on the writer or shared across calls.

The emitted checkpoint sequences remain the exact PR5 canonical sequences.

### PRE_TRANSACTION

```text
PRELIMINARY_IDEMPOTENCY_CHECK_RETURNED
→ ACCEPTED_HISTORY_OBSERVED
→ VALIDATION_RETURNED
→ BUSINESS_UOW_REACHED
→ AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED
→ CONCURRENCY_PREPARATION_RETURNED
→ APPEND_ADMISSION_RETURNED
→ IDEMPOTENCY_PERSISTENCE_RETURNED
```

### IN_TRANSACTION

```text
BUSINESS_UOW_REACHED
→ AUTHORITATIVE_IDEMPOTENCY_CHECK_RETURNED
→ CONCURRENCY_PREPARATION_RETURNED
→ ACCEPTED_HISTORY_OBSERVED
→ VALIDATION_RETURNED
→ APPEND_ADMISSION_RETURNED
→ IDEMPOTENCY_PERSISTENCE_RETURNED
```

`ACCEPTED_HISTORY_OBSERVED` is recorded immediately after accepted-history
loading returns and before aggregate reconstruction. Normal source-grounded
`REPLAY`, `CONFLICT`, `VALIDATION_BLOCKED`, `LOCK_TIMEOUT`, `STALE_WRITE`, other
admission rejection, and `ACCEPTED` returns compose the primary result with the
appropriate valid trace prefix.

## Pre-Commit Construction Boundary

For accepted traced execution, the implementation orders finalization as:

```text
idempotency persistence returns
→ IDEMPOTENCY_PERSISTENCE_RETURNED is validated
→ PostgresWriteSideResult(ACCEPTED) is constructed
→ PostgresWriteSideExecution is constructed
→ return expression is ready
→ UOW __exit__ runs
→ connection.commit() runs
→ caller receives the already-built execution
```

Trace or envelope construction failure therefore occurs before commit and
drives exceptional UOW rollback. A commit exception prevents caller-visible
execution delivery. PR6 does not classify commit ambiguity or reinterpret that
exception as a known business result.

This is synchronous composition, not atomic persistence of diagnostic
artifacts. `PostgresWriteSideResult`, `PostgresWriteSideExecutionTrace`, and
`PostgresWriteSideExecution` remain Python in-memory objects. Only business
state such as the accepted event and idempotency record participates in the
PostgreSQL transaction.

`CLEAN_COMMIT_RETURNED` remains intentionally absent. The trace does not prove
commit finality, and `IDEMPOTENCY_PERSISTENCE_RETURNED` means only that the
bounded persistence call returned normally inside the transaction.

## Preservation Evidence

PR6 preserves:

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

The shared execution implementation and focused tests preserve those
boundaries. Currently propagating exceptions still propagate without a
guaranteed `PostgresWriteSideExecution`.

## Validation

Focused PR5-contract and PR6 pure-unit validation completed during the PR6
implementation review:

```text
./.venv/bin/python -m pytest -q \
  tests/unit/pipeline/transactional/test_postgres_write_side_execution_trace.py \
  tests/unit/pipeline/transactional/test_postgres_write_side_traced_execution_unit.py

82 passed in 0.11s
```

The committed focused PostgreSQL traced-execution suite contains 15
legacy/traced integration cases.

Final repository-wide validation then executed the complete `tests` tree,
including the focused PostgreSQL traced-execution coverage, PR4 characterization,
and existing regression tests:

```text
pytest tests -q

1650 passed in 30.93s
```

No test failure or skip is reported in the final run. PR6 acceptance is therefore
grounded in the current full-suite result rather than the earlier
environment-limited audit state.

## Deferred PR7 Implications

The producer path correctly pairs Result + Trace from one invocation, while
manual `PostgresWriteSideExecution` construction proves only structural
compatibility, not historical same-execution provenance. PR6 adds no
`execution_id`, `attempt_id`, or producer-certification mechanism.

The traced APIs are strict and fail closed: a trace invariant or instrumentation
failure can roll back an otherwise valid traced execution. Legacy APIs create
no tracing artifacts and retain their existing availability boundary. PR7 may
record that trade-off, but any best-effort model requires separate future
justification.

Later consumer-driven `SemanticOutcome` + Trace composition may be reassessed,
likely at Stage 4C entry. PR6 adds no such envelope, caller-independent pairing,
additional coherence validator, or `DecisionReceipt` orchestration.

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
generic DiagnosticTrace inheritance
SemanticOutcome + Trace composition
same-execution provenance identity
transaction durability classification
exception-carried trace
```

A conflict or lock timeout may terminate the current trace, but any subsequent
attempt belongs to Stage 4E.

---

# PR7 — Stage 4B.1 Closeout

## Goal

Close Stage 4B.1 after the implemented concrete trace slices have been reviewed
as a coherent DiagnosticTrace responsibility.

## Status

Complete / documentation only.

## Branch

```text
docs/stage4b1-pr7-closeout
```

## Completed Scope

PR7 adds no runtime behavior. It records:

- the stable [Stage 4B.1 closeout](stage_4b_1_closeout.md);
- [ADR 0022](../../adr/0022_traced_write_side_execution_fails_closed_before_business_commit.md)
  for strict, fail-closed PostgreSQL traced-write composition;
- the completed snapshot, projection-worker, and write-side dispositions;
- deferred same-execution provenance and `SemanticOutcome + Trace` consumer
  questions for Stage 4C entry;
- the missing production `Execution → SemanticOutcome → DecisionReceipt →
  TransactionOwner` orchestration without implementing it; and
- current repository status/navigation alignment with Stage 4B.2 next.

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

Stage 4B.1 leaves the repository with this conceptual separation:

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

The completed transition is:

```text
PR5 accepted and complete
→ PR6 production integration complete
→ focused and repository-wide validation accepted
→ PR6 accepted
→ Stage 4B.1 PR7 closeout complete
→ Stage 4B.2 Measurement Matrix / Cost Evidence Inventory next
```

The concurrent idempotency `check → record` TOCTOU remains a separate hardening
gap and is not pulled into PR7 merely because PR4 exposed it.

Stage 4B.2 may now proceed from the accepted PR4 topology, PR5 checkpoint
vocabulary, and PR6 instrumentation sites. This breakdown does not design its
measurement contract.
