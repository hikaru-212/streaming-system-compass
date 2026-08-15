# Stage 4B — DecisionReceipt / Runtime Evidence Record

[← Back to Implementation Notes](../README.md)

## Purpose

This directory records the design, implementation, validation, and closeout history for:

```text
Stage 4B — DecisionReceipt / Runtime Evidence Record
```

Stage 4A completed the `SemanticOutcome` core.

Stage 4B completed the next step:

```text
technical runtime evidence
→ SemanticOutcome
→ DecisionReceipt
```

The purpose of Stage 4B is not to build an observability platform, diagnostic trace system, benchmark suite, runtime policy engine, strategy selector, or retry governance layer.

The purpose is to define how selected semantic outcomes become compact, reviewable, machine-readable runtime evidence records.

---

## Current Status

```text
PR1–PR6 — Complete
Interlude — Read-Side Canonical Context Protection — Complete
Interlude — DecisionReceipt Flag Evaluation State — Complete
PR7 — Complete
```

Stage 4B is complete. [Stage 4B.1 — DiagnosticTrace / ResolutionTrace](../stage_4b_1/README.md)
is also complete through PR7, including the immutable snapshot-assisted trace
contract and PostgreSQL write-side Result + Trace integration. Snapshot traced
resolver runtime integration remains intentionally deferred. See the
[Stage 4B closeout](stage_4b_closeout.md) for the final
source map, invariants, validation-evidence map, non-goals, and roadmap
transition, and the
[Stage 4B.1 closeout](../stage_4b_1/stage_4b_1_closeout.md) for the completed
trace-stage authority and Stage 4B.2 handoff.

A separate post-Stage 4B PostgreSQL follow-up first characterized one
transaction-local cleanup mechanism for live-but-idle DecisionReceipt owners and
then produced the implemented, tested, and merged
`PostgresDecisionReceiptTransactionOwner`. The component owns one separate
governance transaction for an already-complete receipt. Automatic callers,
production timeout calibration, connection-pool integration, and runtime policy
remain unimplemented. See
[DecisionReceipt Transaction-Owner Liveness Hardening](decision_receipt_owner_liveness_runtime_hardening.md).

This follow-up does not reopen Stage 4B or the completed Stage 4B.1 boundary.

Reported focused PR2 verification:

```text
test_semantic_outcome.py
→ 25 passed

test_decision_receipt.py
→ 102 passed
```

---

## Why This Stage Exists

Stage 4A made runtime correctness evidence semantically interpretable.

It answered:

```text
Given technical runtime evidence,
what does this mean for semantic correctness?
```

Stage 4B answers the next question:

```text
Given a SemanticOutcome,
what summary evidence should be preserved so future governance can review, query, and act on that semantic meaning?
```

Without Stage 4B, `SemanticOutcome` remains an in-memory interpretation boundary.

That may be enough for systems that only need immediate runtime classification.

However, it is not enough for systems that need:

```text
auditability
reviewability
policy-linked recovery
operator investigation
runtime decision evidence
strategy selection evidence
retry governance evidence
future agent workflow governance
```

Stage 4B introduces `DecisionReceipt` to preserve selected semantic outcomes as governance evidence.

---

## Core Principle

```text
SemanticOutcome
≠
DecisionReceipt

DecisionReceipt
≠
application log

DecisionReceipt
≠
DiagnosticTrace

DecisionReceipt
≠
AttemptLog

DecisionReceipt
≠
RuntimeDecisionPolicy
```

A `SemanticOutcome` describes what a technical result means semantically.

A `DecisionReceipt` preserves summary-level evidence of that semantic conclusion.

A `DiagnosticTrace` explains detailed failure paths, replay cursors, partial progress, and resolution internals.

An `AttemptLog` records retry / replay / attempt sequences.

A `RuntimeDecisionPolicy` decides what the runtime is allowed to do.

Stage 4B should only implement the receipt layer.

---

## Relationship to ADR 0016

Stage 4B PR1 introduces:

```text
ADR 0016 — DecisionReceipt Is Governance Evidence, Not Application Logging
```

ADR 0016 records why Stage 4B should not be treated as:

```text
put error logs in a database
```

or:

```text
replace ELK / Loki / CloudWatch / normal application logging
```

The decision is narrower:

```text
Persist selected SemanticOutcome-derived evidence as compact runtime governance records.
```

Application logs remain useful for debugging, monitoring, and operations.

DecisionReceipt exists for durable semantic governance evidence.

---

## Stage 4B Focus

Stage 4B introduces the DecisionReceipt boundary.

It may include:

```text
DecisionReceipt purpose and evidence boundary
SemanticOutcome → DecisionReceipt mapping
write-side DecisionReceipt mapping
read-side / snapshot DecisionReceipt mapping
DecisionReceipt durable persistence
Stage 4B closeout
```

It should preserve the Stage 4A separation:

```text
technical status
≠
semantic outcome

semantic outcome
≠
runtime decision

runtime decision
≠
execution strategy

retry attempt
≠
same intent
```

Stage 4B extends that with:

```text
semantic outcome
≠
durable governance receipt

durable governance receipt
≠
diagnostic trace

diagnostic trace
≠
retry attempt log

receipt evidence
≠
semantic authority
```

---

## Java / Rust Portability Boundary

Stage 4B introduces core runtime governance contracts that may later be ported to Java / JVM or Rust.

The current implementation remains Python.

However, Stage 4B code should avoid Python-only dynamic behavior in core runtime contracts.

Guiding rule:

```text
Python implementation
portable contracts
JSON-safe evidence
explicit topology
clear concurrency boundaries
future Java / Rust migration path preserved
```

For Stage 4B this means:

```text
stable receipt fields should be explicit and typed
flexible evidence should remain JSON-safe
core runtime logic should not depend on dynamic attribute lookup
receipt evidence should not contain Python runtime objects
identity should be represented by IDs, not object ownership graphs
mapping code should not execute recovery
```

Good direction:

```text
DecisionReceipt
= typed outer contract
+ JSON-safe evidence_summary
+ JSON-safe cost_summary
```

Avoid:

```text
DecisionReceipt
= arbitrary dict[str, Any]
```

or:

```text
evidence_summary
= Python objects, validator instances, database connections, callbacks, exception objects, or mutable runtime state
```

This portability rule should apply to new Stage 4B runtime contracts.

It should not trigger a large retroactive refactor of stable earlier code.

---

## Read-Side Canonical Context Protection

Before PR3, the read-side Stage 4A adapters were hardened so caller-provided
context can add supplementary values but cannot contradict canonical context
derived from typed runtime results.

The protected context remains producer-owned:

```text
ReplayValidationResult
→ order_id

ProjectionSnapshotReplayValidationResult
ProjectionSnapshotAssistedResolutionResult
→ order_id
→ snapshot_id
→ source_global_position
```

This Interlude does not make `SemanticOutcome.context` or
`SemanticOutcome.evidence` automatically receipt-safe.

PR4, PR5, or caller / orchestration must explicitly preselect receipt-safe
`evidence_summary` and `metadata`. PR3 only accepts and validates those inputs;
it does not inspect the open-ended outcome mappings.

---

## SemanticOutcome to DecisionReceipt Adapter

PR3 is complete.

The generic mapper establishes:

```text
SemanticOutcome
+ explicit receipt-specific inputs
→ DecisionReceipt
```

It preserves the complete typed semantic tuple and accepts explicit receipt
identity, evidence source, supporting contracts, preselected JSON-safe evidence,
and metadata.

It does not inspect or copy:

```text
SemanticOutcome.context
SemanticOutcome.evidence
```

It also does not infer producer ownership, subject, correlation, identity
provenance, admission disposition, governance flags, policy, strategy, retry
authorization, serialization, or persistence.

PR4 and PR5 must remain producer-specific wrappers around this stable generic
construction boundary.

---

## DecisionReceipt Flag Evaluation State

The implemented shared contract is:

```text
DecisionReceiptFlagState
= TRUE | FALSE | NOT_EVALUATED
```

Every flag defaults to:

```text
NOT_EVALUATED
```

`FALSE` is reserved for a completed evaluation that explicitly negates the
condition. `NOT_EVALUATED` means the receipt contains no completed evaluation
and must not be interpreted as `FALSE`.

No current producer, consumer, invariant, or test justifies
`NOT_APPLICABLE`.

PR3 remains pass-through only. PR4 and PR5 leave producer-created flags `NOT_EVALUATED`.
Only later explicitly authorized evaluators may produce `TRUE` or `FALSE`.
Stage 4E alone owns retry classification and authorization.

`DecisionReceiptFlagState` is publicly exported. All four
`DecisionReceiptFlags` fields use it and default to `NOT_EVALUATED`. Strict
validation rejects legacy booleans, raw strings, `None`, integers, and
unrelated enum values. The old boolean convenience properties were removed.

Focused DecisionReceipt tests and the runtime unit suite passed.

The full repository suite was attempted, but PostgreSQL integration tests could
not start because `TEST_DATABASE_URL` was unavailable. The exact reviewed
results are recorded in
`decision_receipt_flag_evaluation_state.md`.

The PR4 and PR5 producer-specific mappers and focused unit tests are
implemented. Under ADR 0018, every PR4 and PR5 governance flag remains
`NOT_EVALUATED`; typed producer results remain evidence for later authorized
evaluators.

PR5 preserves read-side replay, snapshot-trust, and snapshot-assisted evidence
without turning point-in-time validation into continuing trust. Runtime
invocation remains outside PR4 and PR5.

## DecisionReceipt Persistence

PR6 adds the explicit serializer v1, persistence-envelope contracts, migration
007, and caller-transaction-owned PostgreSQL insert/load boundary described in
[DecisionReceipt Durable Persistence](decision_receipt_persistence.md).

This is the serialization and durable-storage foundation. It does not
automatically invoke PR4/PR5 producers, persist mapper outputs, schedule
materialization, scan accepted history, or reconcile missing receipts.

The completed closeout transition is:

```text
PR7 — Stage 4B Closeout — Complete
Stage 4B.1 PR1–PR7 — Complete
Stage 4B.2 PR1–PR8 — Complete / Closed
Stage 4B.5 — Order Correctness Contract v0 — Complete / Closed
Stage 4B.3 — Projection Trust Boundary and Continuation — Separately Owned / Not Started
```

---

## Post-Stage 4B Transaction-Owner Liveness Follow-up

The repository has now characterized a transaction-local PostgreSQL mechanism
for the unresolved live-but-idle DecisionReceipt owner case.

Focused integration evidence establishes:

```text
uncommitted receipt owner
→ conflicting contender reaches a real Lock wait
→ transaction-local idle timeout terminates the owner
→ PostgreSQL rolls back the owner transaction
→ contender resumes and can commit
→ terminated owner connection is broken and must be discarded
```

This evidence later grounded the implemented
`PostgresDecisionReceiptTransactionOwner`, which applies its required timeout
transaction-locally, owns commit or rollback, and closes or discards its
dedicated connection.

The component is not an automatic production caller. No production timeout
duration or configuration owner, connection-pool integration, automatic
semantic mapping or materialization, retry authorization, migration, or schema
change is introduced by the owner.

The implementation guide is:

[DecisionReceipt Transaction-Owner Liveness Hardening](decision_receipt_owner_liveness_runtime_hardening.md)

This is a post-Stage 4B PostgreSQL hardening follow-up. It does not reopen the
completed Stage 4B contract or the completed Stage 4B.1 boundary.

---

## Relationship to Future Stage 4 Work

Stage 4B remains narrow.

Later stages may build on it:

```text
Stage 4B.1
= DiagnosticTrace / ResolutionTrace

Stage 4B.2
= Measurement Matrix / Cost Evidence Inventory

Stage 4B.5
= Order Correctness Contract v0 — complete / closed

Stage 4C
= RuntimeDecisionPolicy

Stage 4C.5
= Layer 1 / Layer 2 Outcome Alignment

Stage 4D
= StrategySelector / Fast-Path Health Policy

Stage 4E
= Retry Governance / Attempt Classification
```

Stage 4B.5 now provides exact machine-readable correctness evidence without
implementing Retry Governance. The other later layers remain separately owned.

It should preserve clear extension points so those layers can consume receipt evidence later.

---

## Current PR Sequence

Stage 4B proceeded through:

```text
PR1 — DecisionReceipt / Runtime Evidence Boundary
PR2 — DecisionReceipt Runtime Contract
Interlude — Read-Side Canonical Context Protection
PR3 — SemanticOutcome to DecisionReceipt Adapter
Interlude — DecisionReceipt Flag Evaluation State
PR4 — Write-Side Admission DecisionReceipt Mapping
PR5 — Read-Side Snapshot DecisionReceipt Mapping
PR6 — DecisionReceipt Durable Persistence
PR7 — Stage 4B Closeout
```

The durable PostgreSQL receipt store was introduced in Stage 4B PR6 after the
receipt boundary and mapping shape stabilized.

---

## Non-goals

Stage 4B does not implement the later governance layers that consume
DecisionReceipt evidence:

```text
DiagnosticTrace
Measurement Matrix
Order Domain Policy Contract
RuntimeDecisionPolicy
StrategySelector
RetryGovernance
ActionSafetyGate
automatic receipt materialization
accepted-history reconciliation
transactional outbox
operator review execution
fallback execution
rebuild orchestration
quarantine mechanism
benchmark suite
observability platform
LLM token accounting
model routing policy
```

PR6 provides persistence infrastructure only. Runtime materialization and
reconciliation remain deferred.

---

## Relationship to Earlier Stages

### Stage 4A

Stage 4A introduced the stable `SemanticOutcome` core.

It answered:

```text
technical runtime evidence
→ semantic interpretation
```

Stage 4B consumes that layer and answers:

```text
semantic interpretation
→ durable governance evidence
```

Stage 4B should not reopen Stage 4A mapping scope unless receipt requirements expose a missing evidence contract.

### Stage 3.5D

Stage 3.5D introduced snapshot trust and replay-efficiency support.

It clarified:

```text
snapshot = derived state compression
snapshot-assisted validation = evidence producer
snapshot-assisted resolver = trust consumer
```

Stage 4B may preserve snapshot trust evidence in `DecisionReceipt`.

It should not turn snapshots into authority.

### Stage 3.5E

Stage 3.5E introduced durable history and permission hardening.

It clarified:

```text
database role
≠
actor metadata
≠
governance evidence
```

Stage 4B may record actor or runtime-role evidence when receipt-safe.

It should not treat database permissions alone as governance receipts.

## Write-Side Mapping Reading Guide

- [End-to-end reader guide](write_side_result_to_decision_receipt_end_to_end.md)
- [Stage 4A → Stage 4B mapping flow](stage_4a_to_stage_4b_write_side_mapping_flow.md)
- [Type and vocabulary reference](write_side_mapping_type_and_vocabulary_reference.md)
- Design/audit source notes:
  [Write-Side Admission Fate Completion](write_side_admission_fate_completion.md) |
  [Write-Side DecisionReceipt Mapping](write_side_decision_receipt_mapping.md)

The reader guides explain current behavior and code navigation. The
design/audit notes preserve rationale, inventory, implementation history, and
closeout evidence; they remain separate documents.

## Read-Side / Snapshot Mapping Reading Guide

- [End-to-end reader guide](read_side_result_to_decision_receipt_end_to_end.md)
- [Stage 4A → Stage 4B mapping flow](stage_4a_to_stage_4b_read_side_mapping_flow.md)
- [Type and vocabulary reference](read_side_mapping_type_and_vocabulary_reference.md)
- Design/audit source note:
  [Read-Side / Snapshot DecisionReceipt Mapping](read_side_snapshot_decision_receipt_mapping.md)

The read-side guides distinguish projection execution, durable replay
validation, snapshot replay validation, and snapshot-assisted resolution. They
also record the point-in-time evidence boundary, common-mode reducer
limitation, order-local tail contract, completed fail-closed hardening, and
deferred semantic-precision issues.

## Detailed Notes

- [Stage 4B Closeout](stage_4b_closeout.md)
- [PR Breakdown](pr_breakdown.md)
- [Canonical DecisionReceipt Boundary](../../boundary_notes/decision_receipt_boundary.md)
- [PR1 DecisionReceipt Boundary Design Record](pr1_decision_receipt_boundary_design.md)
- [DecisionReceipt Runtime Contract](decision_receipt_contract.md)
- [DecisionReceipt Evidence Source Alignment Note](decision_receipt_evidence_source_alignment_note.md)
- [SemanticOutcome to DecisionReceipt Adapter](semantic_outcome_to_decision_receipt.md)
- [DecisionReceipt Flag Evaluation State](decision_receipt_flag_evaluation_state.md)
- [Write-Side DecisionReceipt Mapping](write_side_decision_receipt_mapping.md)
- [Read-Side / Snapshot DecisionReceipt Mapping](read_side_snapshot_decision_receipt_mapping.md)
- [PR6 DecisionReceipt Persistence Design](pr6_decision_receipt_persistence_design.md)
- [DecisionReceipt Durable Persistence](decision_receipt_persistence.md)
- [DecisionReceipt Transaction-Owner Liveness Hardening](decision_receipt_owner_liveness_runtime_hardening.md)
- [Deferred Hardening — Projection Without Accepted-History Authority](deferred_backlog_projection_without_accepted_history.md)
