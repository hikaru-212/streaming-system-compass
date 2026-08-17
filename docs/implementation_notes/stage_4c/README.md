# Stage 4C — Runtime Decision Authority

[← Back to Implementation Notes](../README.md)

## Status

```text
DOCS-FIRST ENTRY BOUNDARY
NO PRODUCTION IMPLEMENTATION CLAIMED
```

This index establishes the source-grounded entry boundary for Stage 4C. It does
not claim that a production runtime-decision policy, action type, strategy
selector, retry-governance component, or executor exists.

The accepted authority decision is
[ADR 0027 — Separate Runtime Decision, Strategy, and Retry Authority](../../adr/0027_separate_runtime_decision_strategy_and_retry_authority.md).

## Purpose

Stage 4C introduces Runtime Decision Authority.

It answers:

> Given the current semantic observation and eligible supporting evidence,
> what generic current response or action is permitted, required, or denied?

It does not execute the response, choose an execution strategy, or authorize
another attempt.

## Current Stage 4 Foundation

The accepted entry baseline is:

```text
Stage 4A
= COMPLETE / CLOSED
= SemanticOutcome

Stage 4B
= COMPLETE / CLOSED
= DecisionReceipt durable governance evidence

Stage 4B.1
= COMPLETE / CLOSED
= bounded producer-specific execution evidence

Stage 4B.2
= COMPLETE / CLOSED
= bounded measurement / cost evidence

Stage 4B.3
= COMPLETE / CLOSED AS NOT CURRENTLY JUSTIFIED
= PR1 / PR2 retained as investigation and reference evidence
= PR3+ intentionally do not proceed
= ADR 0026 owns re-entry

Stage 4B.5
= COMPLETE / CLOSED
= Order Correctness Contract V0
= 18 stable correctness rules
= exactly six FullProof TRANSITION_TRUTH rules with typed runtime producer coverage
```

The 18-rule contract is broader than current typed runtime evidence production.
Stage 4C must not infer producer coverage for the other 12 rules.

## Authority Boundary

The governing hierarchy is:

```text
technical status
!= SemanticOutcome
!= exact rule refinement
!= diagnosis
!= RuntimeDecision
!= strategy
!= retry authorization
!= retry execution
```

Stage 4C owns a generic current-response decision. Stage 4D may later choose an
eligible execution path inside that authorization. Stage 4E alone decides
whether another attempt is allowed and under which constraints. Actual action
and retry execution remain separate.

Stage 4C does not own:

- retry classification or authorization;
- retry count, budget, or timing;
- reload-before-retry or revalidation-before-retry requirements;
- same-candidate versus regenerated-candidate constraints;
- prior-attempt lineage or intent consistency;
- strategy selection;
- execution.

`RETRY_AFTER_RELOAD` and `RETRY_WITH_BACKOFF` are not Stage 4C runtime actions.
`retry_allowed` and `max_attempts` are not Stage 4C runtime-decision fields.

## First-Slice Evidence Posture

The conservative first-slice evidence posture is:

```text
primary evidence
= SemanticOutcome

eligible refinement when source-applicable
= terminally applicable exact OrderRuleViolationEvidence
```

An exact rule refinement narrows the current terminal semantic explanation. It
does not independently authorize an action or retry.

For the current PostgreSQL write-side path,
`PostgresWriteSideSemanticRuleFeedback` may be a useful source-controlled
producer-specific carrier because it preserves:

```text
SemanticOutcome
+ terminally applicable OrderRuleViolationEvidence
```

It is not a universal Stage 4C abstraction. This stage does not introduce a
generic evidence bag or freeze a `Stage4CInput` wrapper merely for convenience.

## Evidence Eligibility

| Evidence | What it proves | What it does not prove | First-slice posture |
|---|---|---|---|
| `SemanticOutcome` | Coarse semantic meaning, observation boundary, severity, risk, reversibility, context, and supporting evidence. | Runtime action, execution strategy, retry authorization, or persistence. | Required primary live evidence. |
| `OrderRuleViolationEvidence` | One exact stable Order-rule violation for one candidate when produced by an eligible source. | Complete violation coverage, diagnosis, repair, action authority, or retry safety. | Optional direct refinement when terminally applicable. |
| `PostgresWriteSideSemanticRuleFeedback` | One source-controlled PostgreSQL composition of `SemanticOutcome` and terminally applicable exact rule refinement. | Universal producer contract, durable provenance, complete rule coverage, or retry authority. | Useful producer-specific carrier; not mandatory or universal. |
| `DecisionReceipt` | Durable-capable, reviewable governance evidence preserving selected semantic meaning, subject, correlation, admission fate, and evaluation states. | Current action authority, retry authorization, proof that one in-memory instance was persisted, or permanent authorization. | Supporting durable evidence; not required for the first live hot path. |
| Producer-specific trace | Bounded execution topology or diagnostic detail owned by its producer. | Terminal semantic cause, action permission, retry safety, or durability unless separately established. | Not a mandatory input; add only for a concrete policy consumer. |
| Measurement evidence | Bounded execution-cost observations. | Semantic truth, action authority, retry safety, or strategy authorization. | Not a mandatory Stage 4C input; principally relevant to later strategy consumers. |
| `FullProofValidationEvidence` | The producer-specific validation result and an optional exact violation from exactly six supported `TRANSITION_TRUTH` rules. | All 18 rules, terminal write-side meaning, action authority, or retry safety. | Not a Stage 4C input requirement; consume eligible preserved refinement instead. |

## Terminal Applicability Boundary

Observed validation evidence is not automatically the terminal semantic cause.

```text
observed validation evidence
!= terminal semantic cause
```

Rule evidence preserved earlier in one execution must not automatically refine
a later unrelated terminal result. The current PostgreSQL rule-feedback mapper
therefore exposes exact refinement only when validation block is the terminal
write-side outcome. Preserved validation observation on another terminal path
remains evidence of what was observed earlier, not the explanation for why the
execution ultimately terminated.

Stage 4C must preserve this distinction rather than promoting every available
rule observation into a current decision cause.

## Live In-Memory and Restart-Recovery Boundary

The first decision-governance delivery is primarily live and in memory:

```text
process remains alive
→ live in-memory runtime governance

process is lost or restarted
→ restart-recovery governance
```

For normal short-lived in-process decision, regeneration, and transactional
re-attempt governance, `SemanticOutcome` plus eligible live refinement is the
first design center.

`DecisionReceipt` remains important durable governance evidence. Its
availability does not make it a mandatory first-slice Stage 4C or Stage 4E live
input, and the live path does not require receipt persistence before making an
in-process decision. It is not limited to restart recovery; other concrete
durable governance consumers may use it without turning evidence into
authorization.

Restart recovery is a different problem, not an unimportant one. Durable
receipt evidence may later support process or service restart, delayed
reconciliation, operator investigation, governance continuation, or
reconstruction of earlier semantic context after the original in-memory
artifacts no longer exist.

That later consumer is deferred. This stage does not design a restart-recovery
algorithm, and an old receipt must not be treated as permanent authority to
replay an old action.

## Stage 4C / 4D / 4E Handoffs

For a current response that needs no new attempt:

```text
eligible current evidence
→ Stage 4C current-response decision
→ Stage 4D strategy selection when multiple eligible paths exist
→ execution
```

When another attempt is being considered:

```text
current execution evidence
→ Stage 4C current-response decision
→ Stage 4E attempt authorization and constraints
→ Stage 4D strategy selection for the authorized attempt
→ execution
```

Not every normal execution passes through Stage 4E. Retry authorization does
not execute retry, permit same-candidate reuse, or grant unlimited attempts.

## Explicit Non-Goals

This docs-first entry does not introduce or freeze:

- production code or tests;
- Python class names or exact enum representation;
- a universal evidence envelope or `Stage4CInput` wrapper;
- a policy engine or configuration language;
- a strategy algorithm;
- a retry algorithm or executor;
- an `AttemptLog` or persistence schema;
- durable `RuntimeDecision` storage;
- automatic `DecisionReceipt` materialization;
- restart-recovery implementation;
- Stage 4D or Stage 4E production behavior;
- runtime producer coverage for all 18 correctness rules.

## Questions Requiring Source-Grounded Resolution

Before the first production PR, the stage must resolve:

1. Which current `SemanticOutcome` boundaries and codes enter the first narrow
   policy slice?
2. Which generic current responses are necessary for that concrete consumer,
   without introducing retry-specific actions?
3. Which exact rule refinements are eligible for each terminal source path?
4. How does the decision fail closed when required primary evidence is absent,
   malformed, or not source-applicable?
5. What minimum reason and evidence references make one in-memory decision
   reviewable without requiring durable decision storage?
6. Which caller owns the decision invocation, and where does authorization stop
   before strategy selection and execution?
7. Which first consumer demonstrates that Stage 4C is necessary rather than a
   speculative generic policy surface?

No answer should be inferred from exception strings, mutable metadata, stale
durable evidence, or a source-specific wrapper's mere availability.

## Readiness Criteria for the First Production PR

The first production PR is ready for proposal only when:

- ADR 0027 is the accepted responsibility authority;
- one concrete runtime consumer and invocation boundary are identified;
- the eligible `SemanticOutcome` subset is source-grounded;
- terminal rule-refinement applicability is explicit;
- the minimal generic current-response vocabulary is reviewed;
- Stage 4C actions contain no retry authorization, count, budget, backoff, or
  reload-before-retry ownership;
- Stage 4D and Stage 4E handoffs are explicit;
- missing or inapplicable evidence has fail-closed semantics;
- the first slice remains live/in-memory unless a concrete durability consumer
  independently justifies expansion;
- production changes, tests, and validation are separately authorized.

## Current Position

Stage 4C is docs-first and not implemented. The accepted foundation is
sufficient to define a narrow current-response authority boundary, but the
first concrete consumer, action vocabulary, invocation owner, and fail-closed
decision contract remain subject to source-grounded review before production
work begins.
