# Stage 4B.1 — DiagnosticTrace / ResolutionTrace Closeout

[← Back to Stage 4B.1](README.md)

## 1. Purpose

Stage 4B.1 existed to preserve safe structured evidence for this question:

```text
What happened during one supported producer execution?
```

Stage 4A already mapped bounded technical evidence into `SemanticOutcome`.
Stage 4B already preserved selected semantic conclusions as compact durable
`DecisionReceipt` governance evidence. Stage 4B.1 adds a different
responsibility: producer-specific bounded execution progress and terminal
topology that does not belong in either artifact.

This closeout is the stable Stage 4B.1 completion authority. PR-specific notes
remain the detailed design, implementation, validation, and chronology records.

## 2. Final Responsibility Boundary

Stage 4B.1 preserves:

```text
primary producer Result
≠ DiagnosticTrace

SemanticOutcome
≠ DiagnosticTrace

DecisionReceipt
≠ DiagnosticTrace

DiagnosticTrace
≠ AttemptLog

one execution
≠ multiple attempts

execution topology
≠ measurement / cost

execution evidence
≠ retry authorization
```

The primary producer result owns how its execution ended and retains its typed
business or resolution evidence. `SemanticOutcome` owns shared semantic
interpretation. `DecisionReceipt` owns compact durable governance evidence. A
producer-specific `DiagnosticTrace` owns bounded progress or topology for one
execution. A later `AttemptLog` may relate multiple executions and retry
intent. Later policy decides whether another action or attempt is authorized.

Stage 4B.1 introduces no repository-wide generic `DiagnosticTrace`
abstraction. The implemented contracts remain producer-specific and in memory.

## 3. Completed PR Sequence

| Delivery | Completed responsibility |
|---|---|
| PR1 | Defined the `DiagnosticTrace` / `ResolutionTrace` responsibility boundary. |
| PR2 | Implemented the immutable snapshot-assisted resolution trace and execution-envelope contract. |
| PR3 | Revalidated snapshot necessity, superseded the original traced-resolver runtime plan before implementation, and reprioritized the stage. |
| PR4 | Established ten executable PostgreSQL write-side topology-characterization scenarios. |
| PR5 | Implemented the immutable producer-specific canonical-prefix write-side trace contract. |
| PR6 | Integrated write-side Result + Trace delivery through shared legacy/traced execution algorithms. |
| PR7 | Records this closeout, [ADR 0022](../../adr/0022_traced_write_side_execution_fails_closed_before_business_commit.md), deferred consumer/provenance handoffs, and global status alignment. |

The superseded original PR3 is not missing Stage 4B.1 work. It was replaced by
the accepted documentation-only necessity revalidation before runtime
implementation began.

## 4. Snapshot-Assisted Resolution Result

PR2 implemented:

```text
ProjectionSnapshotAssistedResolutionTrace

ProjectionSnapshotAssistedResolutionExecution
= ProjectionSnapshotAssistedResolutionResult
+ ProjectionSnapshotAssistedResolutionTrace
```

The immutable contract remains a valid producer-specific reference case. It
keeps the validated snapshot base, tail-source validation progress, and
successfully replayed tail progress distinct.

The parallel traced-resolver runtime API was intentionally deferred before
implementation. The current Order lifecycle has shallow aggregate-local
history, and no current operational consumer justifies additional
snapshot-specific runtime complexity.

The contract may be reopened for runtime integration if a future concrete
consumer, materially deeper history, measured reconstruction cost, or recovery
requirement makes the additional path worthwhile. Stage 4B.1 does not require
that future justification to close.

## 5. Projection-Worker Result

```text
Projection Worker DiagnosticTrace
= AUDITED
= DO NOT ADD in current Stage 4B.1
```

The projection worker's normal `no_event` and `applied` exits already return
meaningful artifacts. Its strongest non-duplicative trace value would occur on
propagating exception paths after partial progress.

Guaranteeing evidence on those paths would require a new transport such as an
exception wrapper, callback, sink, or persistence mechanism. No current
consumer justifies that transport, and Stage 4B.1 does not add it merely for
symmetry.

## 6. Write-Side Result

The completed write-side sequence is:

```text
PR4
→ executable PostgreSQL topology characterization

PR5
→ immutable producer-specific canonical-prefix trace

PR6
→ production Result + Trace integration
```

PR4 characterized PRE_TRANSACTION + OCC and IN_TRANSACTION + pessimistic
execution, mixed-strategy handoffs, and uncommitted stream-position
arbitration. PR5 retained only the smallest stable checkpoint vocabulary
supported by that evidence. PR6 instrumented the shared execution paths and
added parallel traced APIs without duplicating the PRE or IN algorithms.

The final producer-specific envelope is:

```text
PostgresWriteSideExecution
= PostgresWriteSideResult
+ PostgresWriteSideExecutionTrace
```

The primary result owns terminal producer meaning and typed nested evidence.
The trace owns actual validation placement and ordered bounded topology. The
envelope validates only the source-grounded placement, outcome, and terminal
checkpoint relationship.

## 7. Durability and Synchronous Composition Boundary

For accepted traced execution:

```text
valid PostgresWriteSideResult
+ valid final PostgresWriteSideExecutionTrace
+ valid PostgresWriteSideExecution
= synchronously composed before clean business-UOW exit
```

These objects remain in-memory Python artifacts:

```text
Result
Trace
Execution
= not transaction-durable
```

Only business state such as:

```text
accepted event
+ idempotency record
```

participates in the PostgreSQL business transaction.

Result + Trace is not atomically committed, and
`IDEMPOTENCY_PERSISTENCE_RETURNED` is not commit evidence. Successful caller
delivery follows clean UOW exit and acknowledged commit under the current
producer contract.

[ADR 0022](../../adr/0022_traced_write_side_execution_fails_closed_before_business_commit.md)
records the current strict, fail-closed traced-write decision. A trace or
execution-envelope invariant failure on the accepted traced path occurs before
clean UOW exit, propagates, and causes rollback. The untraced APIs construct no
trace artifacts and retain their existing availability boundary.

## 8. Validation Evidence

The accepted Stage 4B.1 evidence includes:

```text
PR4
= 10 focused PostgreSQL execution-characterization scenarios

PR5
= 40 focused write-side trace-contract unit tests

PR5 + PR6 focused pure-unit evidence
= 82 passed in 0.11s

final repository validation
= pytest tests -q
= 1650 passed in 30.93s
```

The final repository run included the PR4 characterization, PR5 contract,
PR6 traced-execution unit/integration coverage, and the existing regression
suite. PR7 adds documentation only and does not replace that accepted runtime
evidence with a new database run.

## 9. Same-Execution Provenance Handoff

The current producer path uses one invocation-local construction flow, so its
returned Result + Trace comes from the same trusted invocation by construction.

The public envelope constructor establishes only:

```text
compatibility
= could these artifacts belong together?
```

It does not independently authenticate:

```text
provenance
= did these artifacts actually come from the same execution?
```

A caller can manually pair a result from one execution with a structurally
compatible trace from another. PR7 does not add `execution_id`, `attempt_id`,
an opaque token, or another provenance contract merely to prevent that manual
construction.

The first handoff is Stage 4C entry or another concrete consumer review. If a
later consumer must reassociate artifacts after delay, persistence, or a
cross-process boundary, stronger execution provenance may become necessary.
If the problem expands into relationships among multiple attempts, Stage 4E
must retain ownership of attempt identity and intent consistency.

## 10. SemanticOutcome + Trace Handoff

For a trusted producer-returned execution `E`:

```text
R = E.result
T = E.trace
S = map exact R to SemanticOutcome

later live governance evidence
= exact S + exact T carried through one trusted dataflow
```

This appears feasible for a future live governance consumer. Independently
supplied `SemanticOutcome + Trace` remains unsafe because structural
compatibility does not establish historical provenance.

PR7 does not introduce:

- `SemanticOutcomeWithTrace`;
- a generic governance envelope;
- an additional Result/SemanticOutcome/Trace coherence validator; or
- caller-independent pairing.

The likely reassessment point is Stage 4C entry, when a concrete consumer can
define whether live trace evidence is actually required.

## 11. DecisionReceipt and TransactionOwner Handoff

The repository currently contains separately implemented components:

```text
PostgresWriteSideResult
→ callable SemanticOutcome mapper

PostgresWriteSideResult
→ callable producer-specific DecisionReceipt mapper

DecisionReceipt
→ implemented store

DecisionReceipt
→ implemented PostgresDecisionReceiptTransactionOwner persistence
```

The transaction owner accepts an already-complete receipt and owns a separate
governance transaction. It does not construct receipts or call the business
write path.

The repository does not currently provide one production orchestration root
for:

```text
PostgresWriteSideExecution
→ SemanticOutcome
→ DecisionReceipt
→ PostgresDecisionReceiptTransactionOwner
```

Existing executable composition is test-owned and does not establish an
automatic production caller. PR7 records the gap but does not solve automatic
materialization, accepted-history reconstruction, identity allocation, or
governance orchestration.

## 12. Failure Vocabulary Handoff

Later governance work must not collapse these boundaries into one generic
failure:

| Boundary | Current meaning |
|---|---|
| Typed non-accepted normal Result | The producer completed a supported normal-return path such as replay, conflict, validation block, or admission rejection. A traced API may return Result + Trace. |
| Pre-commit exception | No current typed producer result is returned; exceptional UOW exit rolls back when applicable, and no traced execution is guaranteed. |
| Business commit acknowledgement ambiguity | The current business path cannot truthfully classify final durability after an unacknowledged commit; the exception propagates and no execution is delivered. |
| Post-commit semantic mapping failure | A later consumer may fail after a producer result was already delivered; no such production orchestration currently exists, and a mapping failure cannot retroactively change business authority. |
| `DecisionReceipt` construction failure | Compact governance evidence could not be built; this remains separate from the original business outcome and trace. |
| Receipt transaction `NOT_COMMITTED` | The separate governance transaction has known non-commit evidence; this says nothing about business durability or retry authorization. |
| Receipt transaction `UNKNOWN` | Receipt-transaction commit acknowledgement is ambiguous; this says nothing about business durability or retry authorization. |

Detailed recovery, reconciliation, and retry meaning belongs to later stages.

## 13. Deferred Hardening

Stage 4B.1 closes without absorbing:

- concurrent idempotency check-to-record TOCTOU hardening;
- business-UOW bounded liveness;
- business commit ambiguity and reconciliation;
- crash-durable non-accepted occurrence evidence;
- external governance logging;
- automatic `DecisionReceipt` materialization;
- accepted-history receipt reconstruction;
- trace persistence, serialization, retention, or publication; or
- a generic cross-producer `DiagnosticTrace` abstraction.

These concerns require separate consumers, policy, semantics, persistence, or
recovery decisions. Their existence does not turn PR7 into production work.

## 14. Stage 4B.2 Handoff

The final stage boundary is:

```text
Stage 4B.1
= what happened during one execution?

Stage 4B.2
= what did that execution strategy cost?
```

Stage 4B.2 may now proceed. Its safe evidence baseline is:

- PR4's executable write-side topology;
- PR5's accepted validation-placement and checkpoint vocabulary; and
- PR6's instrumentation sites and shared execution paths.

Those sources identify meaningful measurement boundaries. They do not yet
define timing vocabulary, measurement ownership, a benchmark suite, cost-aware
policy, or strategy selection. Stage 4B.2 must make those decisions separately.

## 15. Completion Statement

Stage 4B.1 is complete through PR7.

It leaves the repository with bounded producer-specific trace contracts, one
implemented write-side traced execution, explicit snapshot and
projection-worker non-integrations, a strict synchronous traced-write decision,
and visible consumer/provenance handoffs. No additional production runtime work
is required before Stage 4B.2 begins.
