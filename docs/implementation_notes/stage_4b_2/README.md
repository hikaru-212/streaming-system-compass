# Stage 4B.2 — Measurement Evidence

[← Back to Implementation Notes](../README.md)

## Current Status

```text
Stage 4A
= COMPLETE

Stage 4B
= COMPLETE / CLOSED

Stage 4B.1
= COMPLETE / CLOSED

Stage 4B.2
= CURRENT FORMAL DEVELOPMENT STAGE

PR1
= COMPLETE / DOCUMENTATION ONLY

PR2
= COMPLETE / DETERMINISTIC CHARACTERIZATION ACCEPTED

PR3
= COMPLETE / MERGED

PR4
= CURRENT IMPLEMENTATION STAGE
+ PRODUCTION INSTRUMENTATION IMPLEMENTED
+ DETERMINISTIC UNIT VALIDATION IN PROGRESS
+ AWAITING HUMAN REVIEW

PR5
= NEXT / MEASUREMENT CORRECTNESS VALIDATION
```

At PR1 completion:

```text
measurement responsibility
= documented

runtime measurement contract
= not implemented

runtime instrumentation
= not implemented

empirical comparison
= not executed

concurrency characterization
= not executed
```

PR2 adds test-owned measurement-mechanics evidence only. PR3 adds the immutable
execution-local contract without production timing or measured producer APIs.
Neither changes the instrumentation or experiment status recorded at PR1
completion. PR4 now adds the explicit production measurement capability while
leaving empirical comparison and concurrency characterization unstarted.

## Purpose

Stage 4B.1 and Stage 4B.2 answer different questions:

```text
Stage 4B.1
= what happened during one supported producer execution?

Stage 4B.2
= what did that execution strategy cost?
```

Stage 4B.2 makes bounded PostgreSQL write-side cost observable and then uses
that evidence for controlled empirical comparison. It remains descriptive: it
does not select a strategy, authorize retry, define semantic acceptability,
implement rate limiting, or claim universal production capacity.

## Three Evidence Levels

| Level | Responsibility |
|---|---|
| Level A | Producer-specific measurement evidence for explicitly bounded work performed by one PostgreSQL write execution. |
| Level B | Controlled empirical comparison of the current PRE+OCC and IN+pessimistic compositions under matched PostgreSQL workloads. |
| Level C | Bounded concurrency and contention characterization for those compositions in one recorded environment. |

One execution's measurement remains separate from multi-execution experiment
samples and aggregates.

## Current Priority

Stage 4B.2 is write-side first. Its empirical priority is:

```text
PRE_TRANSACTION
+ optimistic append-time admission

vs

IN_TRANSACTION
+ concrete pessimistic admission
```

The purpose is to measure the current implementations rather than assume which
is faster, where their cost is paid, or how contention changes the comparison.

## Major Boundaries

```text
DiagnosticTrace
!= measurement evidence

one execution's measurement
!= aggregate experiment result

measurement evidence
!= strategy decision

bounded concurrency evidence
!= rate-limiting policy
```

Detailed measurement should initially remain producer-specific, in memory, and
separate from `PostgresWriteSideExecutionTrace`, `SemanticOutcome`,
`DecisionReceipt`, and accepted-event metadata.

## Stage Documents

| Document | Role |
|---|---|
| [Measurement Vocabulary and Ownership](measurement_vocabulary_and_ownership.md) | Current PR1 responsibility authority, source-grounded candidate boundaries, methodology constraints, persistence deferrals, non-goals, and stop conditions. |
| [Measurement Mechanics Characterization](measurement_mechanics_characterization.md) | PR2 deterministic fake-clock findings for timer boundaries, overlap, absence, current early-exit topology, finalization, exception preservation, and safe post-UOW delivery constraints. |
| [PostgreSQL Write Measurement Contract](postgres_write_measurement_contract.md) | PR3 producer-specific immutable contract, nanosecond representation, four-state phase semantics, result-first availability, completeness invariants, and opt-in capability boundary. |
| [PostgreSQL Write Measurement Instrumentation](postgres_write_measurement_instrumentation.md) | PR4 production instrumentation, explicit measured APIs, shared-algorithm seams, clock and failure behavior, canonical composition scope, frozen baseline, and PR5 handoff. |
| [Stage 4B.2 PR Breakdown](pr_breakdown.md) | PR1–PR8 branch sequence, responsibilities, dependencies, non-goals, and stop conditions. |

## Predecessor and Roadmap

- [Stage 4B.1 Closeout](../stage_4b_1/stage_4b_1_closeout.md)
- [Stage 4B.1 Write-Side Execution Characterization](../stage_4b_1/write_side_execution_characterization.md)
- [Stage 4B.1 Write-Side Execution Trace Contract](../stage_4b_1/write_side_execution_trace_contract.md)
- [Stage 4B.1 Write-Side Traced Execution](../stage_4b_1/write_side_traced_execution.md)
- [Implementation Roadmap](../../roadmap/implementation_roadmap.md)

## Boundary

PR1 establishes the responsibility boundary. PR2 adds deterministic test-owned
measurement-mechanics characterization. PR3 freezes the producer-specific
immutable contract and delivery decisions without adding production timers.
PR4 implements the explicit producer-specific measurement surface while
preserving the existing unmeasured APIs and shared PRE/IN algorithms. None of
these PRs performs performance or concurrency experiments, persistence,
telemetry, strategy policy, retry governance, or rate admission.
