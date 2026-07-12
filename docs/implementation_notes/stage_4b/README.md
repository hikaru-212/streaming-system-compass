# Stage 4B — DecisionReceipt / Runtime Evidence Record

[← Back to Implementation Notes](../README.md)

## Purpose

This directory records the implementation plan and boundary decisions for:

```text
Stage 4B — DecisionReceipt / Runtime Evidence Record
```

Stage 4A completed the `SemanticOutcome` core.

Stage 4B begins the next step:

```text
technical runtime evidence
→ SemanticOutcome
→ DecisionReceipt
```

The purpose of Stage 4B is not to build an observability platform, diagnostic trace system, benchmark suite, runtime policy engine, strategy selector, or retry governance layer.

The purpose is to define how selected semantic outcomes become compact, reviewable, machine-readable runtime evidence records.

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
DecisionReceipt runtime contract
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

## Relationship to Future Stage 4 Work

Stage 4B remains narrow.

Later stages may build on it:

```text
Stage 4B.1
= DiagnosticTrace / ResolutionTrace

Stage 4B.2
= Measurement Matrix / Cost Evidence Inventory

Stage 4B.5
= Order Domain Policy Contract v0

Stage 4C
= RuntimeDecisionPolicy

Stage 4C.5
= Layer 1 / Layer 2 Outcome Alignment

Stage 4D
= StrategySelector / Fast-Path Health Policy

Stage 4E
= Retry Governance / Attempt Classification
```

Stage 4B should not implement those layers early.

It should preserve clear extension points so those layers can consume receipt evidence later.

---

## Current PR Sequence

Stage 4B is expected to proceed through:

```text
PR1 — DecisionReceipt / Runtime Evidence Boundary
PR2 — DecisionReceipt Runtime Contract
PR3 — SemanticOutcome to DecisionReceipt Adapter
PR4 — Write-Side Admission DecisionReceipt Mapping
PR5 — Read-Side Snapshot DecisionReceipt Mapping
PR6 — DecisionReceipt Durable Persistence
PR7 — Stage 4B Closeout
```

A durable PostgreSQL receipt store should be introduced as Stage 4B PR6 after the receipt shape stabilizes.

Do not introduce a database schema before the receipt boundary and mapping shape are clear.

---

## Non-goals

Stage 4B PR1 does not implement:

```text
DecisionReceipt runtime contract
DecisionReceipt mapping code
DiagnosticTrace
Measurement Matrix
Order Domain Policy Contract
RuntimeDecisionPolicy
StrategySelector
RetryGovernance
ActionSafetyGate
SQL migrations before PR6
PostgresDecisionReceiptStore before PR6
durable receipt table before PR6
operator review execution
fallback execution
rebuild orchestration
quarantine mechanism
benchmark suite
observability platform
LLM token accounting
model routing policy
```

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

## Relationship to Future Stage 4 Work

Stage 4B remains narrow.

Later stages may build on it:

```text
Stage 4B.1
= DiagnosticTrace / ResolutionTrace

Stage 4B.2
= Measurement Matrix / Cost Evidence Inventory

Stage 4B.5
= Order Domain Policy Contract v0

Stage 4C
= RuntimeDecisionPolicy

Stage 4C.5
= Layer 1 / Layer 2 Outcome Alignment

Stage 4D
= StrategySelector / Fast-Path Health Policy

Stage 4E
= Retry Governance / Attempt Classification
```

Stage 4B should not implement those layers early.

It should preserve clear extension points so those layers can consume receipt evidence later.

## Current PR Sequence

Stage 4B is expected to proceed through:

```text
PR1 — DecisionReceipt / Runtime Evidence Boundary
PR2 — DecisionReceipt Runtime Contract
PR3 — SemanticOutcome to DecisionReceipt Adapter
PR4 — Write-Side Admission DecisionReceipt Mapping
PR5 — Read-Side Snapshot DecisionReceipt Mapping
PR6 — DecisionReceipt Durable Persistence
PR7 — Stage 4B Closeout
```

Detailed PR scope should be recorded in:

- [PR Breakdown](pr_breakdown.md)


## Detailed Notes

- [PR Breakdown](pr_breakdown.md)
- [DecisionReceipt Boundary](decision_receipt_boundary.md)
- DecisionReceipt Persistence — to be added in PR6 as `decision_receipt_persistence.md`


