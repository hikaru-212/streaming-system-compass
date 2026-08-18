# Stage 4C PR Breakdown

[← Back to Stage 4C](README.md)

## Purpose

This note records the planning hypothesis for implementing:

```text
Stage 4C — Runtime Decision Authority
```

It sequences separately reviewable work after the source-grounded PR1 boundary.
It does not make the proposed PR count, module topology, or Python API
mandatory.

The governing authority remains
[ADR 0027](../../adr/0027_separate_runtime_decision_strategy_and_retry_authority.md).
The [Stage 4C README](README.md) owns the current implementation-entry boundary
and first concrete profile. This note owns only downstream sequencing, decision
gates, and completion criteria.

## Current Status

```text
PR1
= documentation-only source-grounded boundary
= established in the current branch

production Runtime Decision Authority
= not implemented

PR2 and later
= planning hypothesis
= subject to source and human review
```

## Stage Principle

```text
accepted authority boundary
→ source-grounded first profile
→ minimal generic contract
→ concrete evaluation profile
→ caller-owned composition only when a real caller exists
→ separately justified producer-family expansion
→ closeout
```

Preserve:

```text
SemanticOutcome
!= RuntimeDecision

OrderRuleViolationEvidence
!= RuntimeDecision
!= self-authorizing policy

ValidationDecision
!= RuntimeDecision

RuntimeDecision
!= strategy selection
!= execution

current attempt failed
!= another attempt authorized

RetryAuthorization
!= RetryExecution
```

## Planning Topology Is Not Frozen

The current planning hypothesis is:

```text
PR1
→ source-grounded documentation boundary

likely PR2
→ minimal immutable producer/domain-neutral current-response contract

likely PR3
→ first source-grounded Layer-1 PostgreSQL / Order write-side profile

possible PR4
→ caller-owned composition when a real production caller is identified

later
→ separately justified Stage 4C producer-family expansion
→ Stage 4C closeout
```

This is a review aid, not a mandatory PR count.

Source audit may combine adjacent PRs when a standalone seam would expose a
dormant abstraction without a concrete consumer. Source audit may split a PR
when it would otherwise own more than one independently reviewable semantic
responsibility. The combined Stage 4B.5 PR5+PR6 delivery is process precedent
for changing topology after discovering the real production consumer; it is
not Stage 4C semantic or API precedent.

Any combination or split requires human review before implementation scope is
changed.

---

# PR1 — Source-Grounded Runtime Decision Boundary

## Responsibility

Freeze the first implementation-entry boundary before production contract
work:

```text
live
in-memory
caller-owned
Layer-1 PostgreSQL write-side first
```

The first concrete observation flow is:

```text
PostgresWriteSideResult
→ PostgresWriteSideSemanticRuleFeedback
→ future Stage 4C evaluation
→ caller-owned use of RuntimeDecision
```

The evaluator remains outside `PostgresTransactionalWriteSide` transaction and
admission execution.

## PR1 Human Decisions

PR1 records that:

1. generic Runtime Decision Authority remains producer- and domain-neutral;
2. `OrderRuleViolationEvidence` belongs only to the first concrete Order
   profile when source-applicable;
3. the first profile supports four Layer-1 semantic tuples and excludes
   `CONCURRENCY_UNCERTAIN`;
4. unsupported or incoherent input produces no authority and never implicit
   allow;
5. exact evidence may inform policy but is not self-authorizing;
6. the currently supported terminal FullProof refinements remain within the
   generic block-required family for this first profile;
7. that first-profile behavior is not a permanent prohibition on exact
   evidence influencing a future separately reviewed policy;
8. `ValidationDecision` and `RuntimeDecision` remain separate authorities;
9. the first live decision does not require `DecisionReceipt` persistence;
10. separate decision identity and policy identity/versioning are deferred for
    lack of a current consumer.

## PR1 Completion Criteria

PR1 is complete when:

- the Stage 4C README records the source-grounded first profile;
- this planning note records downstream hypotheses and decision gates;
- both Stage 4 roadmaps say PR1 documentation is established while production
  Runtime Decision Authority remains unimplemented;
- only the authorized documentation files changed;
- no production API, test, migration, dependency, persistence, strategy,
  retry, or execution behavior changed.

---

# Likely PR2 — Minimal Generic Current-Response Contract

## Planning Responsibility

Introduce the smallest immutable producer/domain-neutral contract necessary to
represent a generic current-response decision.

Potential semantic response concepts include:

```text
allow use or return of a completed current result
permit replay or return of a prior accepted result
block current downstream continuation
require escalation of the current condition
```

PR1 does not freeze the production module, class name, enum name, enum values,
exception type, function signatures, or policy class. PR2 must choose those
only after a fresh source and call-site audit.

## Entry Gate

Before implementation, human review must confirm:

- the contract represents current-response authority rather than execution;
- it contains no Order-specific field in its generic vocabulary;
- it contains no retry authorization, retry count, budget, backoff, reload,
  revalidation, candidate-regeneration, intent, or lineage field;
- its reviewability requirements can be met in memory without persistence;
- unsupported or incoherent observations cannot become implicit allow;
- no separate `decision_id`, `policy_id`, or `policy_version` has acquired a
  concrete source-grounded consumer.

## Combination Gate

If the generic contract would otherwise be a dormant production seam with no
concrete evaluator, combine this responsibility with the first profile after
human approval. Do not add speculative public abstraction merely to preserve
the proposed PR number.

---

# Likely PR3 — First Layer-1 Write-Side Evaluation Profile

## Planning Responsibility

Evaluate the reviewed Layer-1 PostgreSQL write-side profile using:

```text
required SemanticOutcome
+ terminally applicable OrderRuleViolationEvidence when source-applicable
→ generic current-response RuntimeDecision
```

The generic contract remains domain-neutral. Order-specific evidence is
consumed only by this concrete evaluation profile.

The supported semantic inputs are limited to the four tuples established in
the README. `CONCURRENCY_UNCERTAIN`, read-side outcomes, and snapshot outcomes
remain outside this profile.

## Evidence Gate

Implementation must preserve:

- terminal validation block may expose exact refinement;
- validation success has no violation refinement;
- validation never run produces no fabricated refinement;
- earlier validation observation does not automatically refine a later
  replay, conflict, admission, or accepted terminal outcome;
- legacy or unsupported validators may provide coarse `SemanticOutcome`
  without exact refinement;
- absence of exact refinement is explicit and is neither success nor policy
  permission;
- exact rule identity is not parsed from reason strings or mutable metadata.

For current supported terminal FullProof violations, exact refinement may make
the decision reason and evidence reference more precise while remaining in the
generic block-required response family. Any future proposal to use exact
evidence to select a different generic response requires a new source-grounded
policy review; it is not prohibited by architecture merely because this first
profile does not need it.

## Validation Gate

Focused validation should prove:

- exact supported tuple matching;
- refusal of unsupported boundary/category/code combinations;
- `CONCURRENCY_UNCERTAIN` refusal;
- no implicit allow on malformed or incoherent input;
- no retroactive write authorization;
- idempotent prior-result replay is not another-attempt authorization;
- exact refinement cannot create repair or retry authority;
- no producer coverage is inferred for the other 12 Order rules.

---

# Possible PR4 — Caller-Owned Composition

## Planning Responsibility

Add explicit caller-owned composition only if a real production caller is
identified by source audit.

The intended ownership is:

```text
caller receives normal terminal PostgresWriteSideResult
→ caller explicitly requests semantic feedback and Stage 4C evaluation
→ caller receives RuntimeDecision
```

The evaluator must remain outside the write-side transaction and admission
execution. Do not add a new application layer, writer API variant, executor, or
retry loop merely to manufacture a caller.

## Stop Gate

If no concrete production caller exists, stop before automatic wiring. An
explicit callable evaluation capability may remain separately invoked, as the
current evidence mappers do; absence of automatic invocation must be reported
truthfully rather than hidden behind speculative orchestration.

---

# Later Producer-Family Expansion

Read-side and snapshot families require separate consumer audits before they
enter Stage 4C policy. The first slice does not decide responses for:

```text
REQUIRES_REBUILD
FAST_PATH_UNAVAILABLE
DERIVED_STATE_UNTRUSTED
DRIFT_DETECTED
```

It also does not decide snapshot fallback, rebuild, quarantine, or trust
selection. Expansion must not reopen Projection Trust Continuation without the
ADR 0026 re-entry conditions.

Each future family must independently establish:

- a concrete caller and current-response need;
- eligible producer evidence and observation boundary;
- supported typed semantic tuples;
- response meanings and refusal behavior;
- the Stage 4C authorization stop before Stage 4D strategy and execution;
- any Stage 4E handoff when another attempt is considered.

---

# Stage 4C Closeout Gate

Stage 4C closeout should not be scheduled solely because the first contract or
profile exists. Human review must determine whether the accepted Stage 4C scope
is complete or whether another concrete current-response consumer is required.

Closeout evidence should include:

- implemented generic current-response contract boundaries;
- implemented producer-family profiles and exact supported tuples;
- actual invocation ownership and any intentionally explicit-only capability;
- refusal and reviewability behavior;
- confirmation that strategy, another-attempt authorization, and execution
  remain separately owned;
- explicit durable/restart deferrals;
- source-grounded test and validation results.

## Downstream Non-Goals

This planning note does not approve:

- Stage 4D strategy selection;
- authority replay versus snapshot selection;
- PRE/OCC versus pessimistic strategy selection;
- Stage 4E retry classification or authorization;
- reload, revalidation, backoff, limits, budgets, candidate regeneration,
  intent consistency, or cross-attempt lineage;
- retry or action execution;
- a policy engine, DSL, registry, hot reload, or configuration store;
- a generic plugin framework or universal evidence envelope;
- automatic `DecisionReceipt` materialization;
- RuntimeDecision or attempt persistence;
- restart recovery or new migrations;
- Agent orchestration or candidate repair;
- new rule-evidence producers;
- projection trust continuation;
- production deployment or open-source preparation.

## Final Planning Rule

```text
PR number
!= architecture boundary

source and human review
→ may combine or split delivery units

responsibility ownership
→ must remain explicit
```
