# Stage 4C PR Breakdown

[← Back to Stage 4C](README.md)

## Purpose

This note records the final accepted delivery topology for:

```text
Stage 4C — Runtime Decision Authority
```

It records the source-audit decision to combine the generic contract and first
evaluation profile in PR2 while preserving their separate ownership, followed
by the bounded Stage 4C.5 compatibility and documentation closeout. Additional
work requires downstream re-entry through a concrete source-grounded demand.

The governing authority remains
[ADR 0027](../../adr/0027_separate_runtime_decision_strategy_and_retry_authority.md).
The [Stage 4C README](README.md) owns the implementation boundary and first
concrete profile. The [Stage 4C closeout](stage_4c_closeout.md) owns the final
completion decision. This note preserves delivery sequencing and downstream
re-entry gates.

## Current Status

```text
PR1
= documentation-only source-grounded boundary
= complete

PR2
= generic immutable RuntimeDecision contract
+ first Layer-1 PostgreSQL / Order evaluation profile
= implemented
= explicit callable capability only
= no automatic caller wiring

Stage 4C.5
= bounded compatibility / documentation closeout
= complete

Stage 4C
= COMPLETE / CLOSED
= no additional production code currently justified
```

## Stage Principle

```text
accepted authority boundary
→ source-grounded first profile
→ minimal generic contract
→ concrete evaluation profile
→ bounded consumer experiment as behavioral evidence only
→ Layer-1 / Layer-2 compatibility audit
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

current request invocation failed
!= same-request re-invocation authorized

same-request re-invocation authorization
!= re-invocation execution
```

## Accepted PR2 Topology

The source-grounded PR2 delivery topology is:

```text
PR1
→ source-grounded documentation boundary

PR2
→ minimal immutable producer/domain-neutral current-response contract
+ first source-grounded Layer-1 PostgreSQL / Order write-side profile
→ separate module and dependency ownership in one delivery

Stage 4C.5
→ compatibility and repository reconciliation
→ no new production profile
→ Stage 4C closeout

downstream re-entry
→ caller-owned composition or producer-family expansion only when a concrete
  current-response demand satisfies the closeout gates
```

PR2 delivers the generic contract and first evaluator together because the
current source has no standalone call site that requires `RuntimeDecision`
before the first evaluation profile exists. Keeping them in one delivery avoids
a contract-only increment while separate modules and one-way dependencies
preserve independent responsibility ownership. This delivery choice does not
make future PR numbers architectural boundaries.

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

PR1 recorded this conceptual end-to-end flow:

```text
PostgresWriteSideResult
→ PostgresWriteSideSemanticRuleFeedback
→ Stage 4C evaluation
→ caller-owned use of RuntimeDecision
```

PR2 implements only the explicit Stage 4C capability segment:

```text
PostgresWriteSideSemanticRuleFeedback
→ evaluate_postgres_write_side_runtime_decision
→ PostgresWriteSideRuntimeDecisionEvaluation
```

The existing upstream feedback mapper remains separately callable.
Caller-owned invocation and use remain explicit and unwired because no
production caller currently exists above `PostgresTransactionalWriteSide`.

The evaluator remains outside `PostgresTransactionalWriteSide` transaction and
admission execution.

## PR1 Boundary Decisions

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

## Historical PR1 Completion Criteria

The following criteria describe the documentation-only PR1 delivery at the
time it completed. They are preserved as chronology and do not describe the
repository's post-PR2 status:

PR1 is complete when:

- the Stage 4C README records the source-grounded first profile;
- this planning note records downstream hypotheses and decision gates;
- both Stage 4 roadmaps say PR1 documentation is established while production
  Runtime Decision Authority remains unimplemented;
- only the authorized documentation files changed;
- no production API, test, migration, dependency, persistence, strategy,
  retry, or execution behavior changed.

---

# PR2 — Generic Contract + First Write-Side Evaluation Profile

## Generic Contract Responsibility

Introduce the smallest immutable producer/domain-neutral contract necessary to
represent a generic current-response decision:

```text
RuntimeDecision
= RuntimeDecisionResponse
+ exact consumed SemanticOutcome
+ non-empty human-readable explanation
```

The closed response vocabulary is:

```text
USE_CURRENT_RESULT
RETURN_PRIOR_ACCEPTED_RESULT
BLOCK_CURRENT_CONTINUATION
REQUIRE_ESCALATION
```

The generic contract has no Order/PostgreSQL fields, copied outcome tuple,
separate reason taxonomy, decision identity, policy identity/versioning,
request re-invocation authorization or state, strategy, execution instruction,
persistence field, metadata bag, or evidence bag.

## First Profile Responsibility

Evaluate the reviewed Layer-1 PostgreSQL / Order write-side profile using:

```text
PostgresWriteSideSemanticRuleFeedback
→ evaluate_postgres_write_side_runtime_decision
→ PostgresWriteSideRuntimeDecisionEvaluation
   = generic RuntimeDecision
   + exact source PostgresWriteSideSemanticRuleFeedback
```

The generic contract remains domain-neutral. The profile-specific delivery
preserves exact source context, including terminally applicable
`OrderRuleViolationEvidence`, without creating a universal evidence envelope.

The supported mappings are exactly:

```text
LAYER_1_WRITE_SIDE / VALID / SEMANTICALLY_VALID
→ USE_CURRENT_RESULT

LAYER_1_WRITE_SIDE / RETRY_CLASSIFIED / IDEMPOTENT_REPLAY_ALLOWED
→ RETURN_PRIOR_ACCEPTED_RESULT

LAYER_1_WRITE_SIDE / BLOCK_REQUIRED / SEMANTIC_CONFLICT_DETECTED
→ BLOCK_CURRENT_CONTINUATION

LAYER_1_WRITE_SIDE / ESCALATION_REQUIRED / REQUIRES_OPERATOR_REVIEW
→ REQUIRE_ESCALATION
```

`CONCURRENCY_UNCERTAIN`, unsupported boundaries, unsupported category/code
combinations, and otherwise coherent tuples outside this first profile raise
the evaluator-specific typed refusal exception. Refusal is neither a positive
block decision nor implicit use authority.

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

The legacy/unsupported-validator allowance above does not mean that PR2 accepts
a raw coarse outcome. The first evaluator deliberately consumes
`PostgresWriteSideSemanticRuleFeedback`, whose source-controlled construction
requires exact Order rule evidence for a terminal `VALIDATION_BLOCKED` result.
An evidence-less validation block therefore cannot enter this first evaluation
path through the current carrier. That boundary neither invalidates the coarse
`SemanticOutcome`, permits fabricated evidence, nor weakens Stage 4B.5. Future
support requires separate source-grounded review and is not permanently
prohibited by this first profile.

## Validation Gate

Focused validation should prove:

- exact supported tuple matching;
- refusal of unsupported boundary/category/code combinations;
- `CONCURRENCY_UNCERTAIN` refusal;
- no implicit allow on malformed or incoherent input;
- no retroactive write authorization;
- idempotent prior-result replay is not authorization for another request
  invocation;
- exact refinement cannot create repair or retry authority;
- no producer coverage is inferred for the other 12 Order rules.

---

# Downstream Re-Entry — Caller-Owned Composition

## Planning Responsibility

Add explicit caller-owned composition only if a real production caller and
guarded current-response action are identified by a future source audit. No
such caller exists above
`PostgresTransactionalWriteSide` in current production source.

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

# Downstream Re-Entry — Producer-Family Expansion

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
- the Stage 4C authority boundary before any strategy selection or execution
  that depends on the current-response decision;
- an independent Stage 4E authority boundary when another same-request
  invocation is considered.

---

# Stage 4C Closeout Decision

Stage 4C closes because the accepted scope is complete and the Stage 4C.5 audit
found no remaining concrete current-response demand that justifies additional
production code. Existing Layer-1 and Layer-2 producer families already share
the producer-neutral `SemanticOutcome` structural contract. Compatibility does
not require identical producer evidence, `RuntimeDecision` policy, or caller
behavior.

The closeout evidence includes:

- implemented generic current-response contract boundaries;
- implemented producer-family profiles and exact supported tuples;
- actual invocation ownership and any intentionally explicit-only capability;
- refusal and reviewability behavior;
- confirmation that strategy, same-request re-invocation authorization, and
  execution remain separately owned;
- explicit durable/restart deferrals;
- source-grounded test and validation results.

The final evidence and transition record is the
[Stage 4C closeout](stage_4c_closeout.md).

## Downstream Non-Goals

This planning note does not approve:

- Stage 4D strategy selection;
- authority replay versus snapshot selection;
- PRE/OCC versus pessimistic strategy selection;
- Stage 4E same-request re-invocation classification or authorization;
- reload, revalidation, backoff, limits, budgets, candidate regeneration,
  intent consistency, or cross-invocation lineage;
- request re-invocation or action execution;
- a policy engine, DSL, registry, hot reload, or configuration store;
- a generic plugin framework or universal evidence envelope;
- automatic `DecisionReceipt` materialization;
- RuntimeDecision or request-invocation lineage persistence;
- restart recovery or new migrations;
- Agent orchestration or candidate repair;
- new rule-evidence producers;
- projection trust continuation;
- production deployment or open-source preparation.

## Final Planning Rule

```text
PR number
!= architecture boundary

source-grounded delivery dependencies
→ may combine or split implementation units

responsibility ownership
→ must remain explicit

Stage 4C closure
→ does not automatically schedule Stage 4D
→ does not implement Stage 4E
```
