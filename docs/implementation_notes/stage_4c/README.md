# Stage 4C — Runtime Decision Authority

[← Back to Implementation Notes](../README.md)

## Status

```text
PR1 SOURCE-GROUNDED IMPLEMENTATION-ENTRY BOUNDARY
NO PRODUCTION IMPLEMENTATION CLAIMED
```

This stage entry records the source-grounded Stage 4C PR1 boundary. It freezes
the first implementation profile and downstream decision gates without
claiming that a production runtime-decision contract, policy, action type,
strategy selector, retry-governance component, or executor exists.

The accepted authority decision is
[ADR 0027 — Separate Runtime Decision, Strategy, and Retry Authority](../../adr/0027_separate_runtime_decision_strategy_and_retry_authority.md).

The proposed implementation sequence is maintained separately in the
[Stage 4C PR Breakdown](pr_breakdown.md). This README owns the current
source-grounded implementation-entry boundary; the breakdown owns planning and
may change after later source or human review.

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

Exact evidence may inform Stage 4C policy evaluation. It is not independently
self-authorizing:

```text
coarse SemanticOutcome
+ eligible exact refinement
→ more precise policy input

exact evidence
!= RuntimeDecision
!= self-authorizing policy
```

The first source-grounded profile does not use the supported exact FullProof
rule identities to leave the generic block-required response family. That is a
statement about this first profile, not a permanent rule prohibiting exact
evidence from influencing a future separately reviewed policy decision.

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

## Generic Responsibility and First Concrete Profile

The generic Stage 4C responsibility is producer- and domain-neutral:

```text
eligible current semantic observation
→ generic current-response RuntimeDecision
```

The generic output must not be defined around Order-specific evidence. PR1
does not introduce a universal rule-evidence abstraction, evidence bag,
`Stage4CInput`, or generic governance envelope.

The first concrete evaluation profile is narrower:

```text
Layer-1 PostgreSQL / Order write-side profile

required:
SemanticOutcome

when source-applicable:
terminally applicable OrderRuleViolationEvidence

output:
generic current-response RuntimeDecision meaning
```

`OrderRuleViolationEvidence` belongs to this concrete profile, not to the
generic Stage 4C contract. A future cross-domain consumer must demonstrate a
concrete need before Stage 4C introduces a more general evidence abstraction.

## First Invocation and Consumer Boundary

The first concrete observation flow is:

```text
PostgresWriteSideResult
→ PostgresWriteSideSemanticRuleFeedback
→ future Stage 4C evaluation
→ caller-owned use of RuntimeDecision
```

The first invocation owner is conceptually the caller after
`PostgresTransactionalWriteSide` has normally returned a terminal result. The
Stage 4C evaluator remains outside the write-side transaction and admission
execution. PR1 does not add a writer API, application layer, executor, or retry
loop merely to create a consumer.

A future RuntimeDecision over an accepted write-side result cannot
retroactively authorize the database write. It governs only the caller's use
of the already-completed current result.

## First-Slice Evidence Posture

The conservative first-slice evidence posture is:

```text
primary evidence
= SemanticOutcome

eligible refinement when source-applicable
= terminally applicable exact OrderRuleViolationEvidence
```

An exact rule refinement may narrow the current terminal semantic explanation
and may inform policy evaluation. It does not independently authorize an
action or retry.

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
| `OrderRuleViolationEvidence` | One exact stable Order-rule violation for one candidate when produced by an eligible source. | Complete violation coverage, diagnosis, repair, action authority, or retry safety. | Optional profile-specific refinement when terminally applicable. |
| `PostgresWriteSideSemanticRuleFeedback` | One source-controlled PostgreSQL composition of `SemanticOutcome` and terminally applicable exact rule refinement. | Universal producer contract, durable provenance, complete rule coverage, or retry authority. | Useful producer-specific carrier; not mandatory or universal. |
| `DecisionReceipt` | Durable-capable, reviewable governance evidence preserving selected semantic meaning, subject, correlation, admission fate, and evaluation states. | Current action authority, retry authorization, proof that one in-memory instance was persisted, or permanent authorization. | Supporting durable evidence; not required for the first live hot path. |
| Producer-specific trace | Bounded execution topology or diagnostic detail owned by its producer. | Terminal semantic cause, action permission, retry safety, or durability unless separately established. | Not a mandatory input; add only for a concrete policy consumer. |
| Measurement evidence | Bounded execution-cost observations. | Semantic truth, action authority, retry safety, or strategy authorization. | Not a mandatory Stage 4C input; principally relevant to later strategy consumers. |
| `FullProofValidationEvidence` | The producer-specific validation result and an optional exact violation from exactly six supported `TRANSITION_TRUTH` rules. | All 18 rules, terminal write-side meaning, action authority, or retry safety. | Not a Stage 4C input requirement; consume eligible preserved refinement instead. |

## First Supported Current-Response Profile

PR1 freezes four supported Layer-1 semantic profiles. The response labels below
state semantic meaning; they do not freeze Python module names, class names,
enum names, enum values, exceptions, function signatures, or policy classes.

| Boundary / category / semantic code | Generic current-response meaning | Qualification |
|---|---|---|
| `LAYER_1_WRITE_SIDE` / `VALID` / `SEMANTICALLY_VALID` | Allow use or return of the already-completed current result. | This does not retroactively authorize candidate append or transaction commit. |
| `LAYER_1_WRITE_SIDE` / `RETRY_CLASSIFIED` / `IDEMPOTENT_REPLAY_ALLOWED` | Permit replay or return of the prior accepted result. | This is not authorization for another attempt and creates no new candidate or accepted event. |
| `LAYER_1_WRITE_SIDE` / `BLOCK_REQUIRED` / `SEMANTIC_CONFLICT_DETECTED` | Block current downstream continuation. | Terminal exact Order-rule evidence may refine why the conflict was blocked. In this first profile it does not create repair or retry authority or change the generic block-required response family. |
| `LAYER_1_WRITE_SIDE` / `ESCALATION_REQUIRED` / `REQUIRES_OPERATOR_REVIEW` | Require escalation of the current condition. | Stage 4C does not implement or execute an operator workflow. |

Potential response concepts include allowing a completed current result,
replaying a prior accepted result, blocking current continuation, and
escalating the current condition. They remain semantic contract requirements,
not frozen production identifiers.

## Unsupported and Refused Observations

`CONCURRENCY_UNCERTAIN` is explicitly outside the first supported mapping.
Current source proves uncertainty but does not yet establish whether the
correct current response is block, escalation, reload, backoff, another
attempt, or another response. Reload, backoff, and another-attempt questions
also cross into Stage 4E authority.

```text
unsupported or unresolved Stage 4C observation
→ no authoritative RuntimeDecision
→ never implicit ALLOW
```

Required primary evidence that is absent, malformed, internally incoherent, or
outside the reviewed profile must be refused rather than normalized into an
allow decision. PR1 freezes this conceptual refusal boundary but does not
freeze an exception type, result type, or error API. Refusal is not a fabricated
positive `BLOCK` decision; it is the absence of authority to proceed as allowed.

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

The first profile applies the following absence semantics:

```text
terminal VALIDATION_BLOCKED
→ exact rule refinement may be exposed when the source produced it

validation passed
→ no violation refinement

validation never ran
→ no fabricated refinement

validation occurred but another result became terminal
→ earlier observation may remain in lower-level evidence
→ it does not automatically refine the later terminal SemanticOutcome

legacy or unsupported validator
→ coarse SemanticOutcome may exist without exact refinement
```

Absent refinement must be represented explicitly enough to distinguish it from
present exact evidence. Absence is not semantic success, policy permission, or
proof that no rule was violated. Stage 4C must not infer a rule identity from
reason strings, mutable metadata, or outcome vocabulary.

## ValidationDecision and RuntimeDecision

The existing `ValidationDecision` is validation-specific enforcement:

```text
ValidationResult
→ ValidationPolicy
→ ALLOW or BLOCK candidate validation
→ consumed inside write-side admission
```

It may stop a candidate before accepted-history mutation. A future
`RuntimeDecision` instead consumes a terminal/current `SemanticOutcome` and
eligible supporting evidence after the relevant producer result exists, then
expresses generic current-response authority.

```text
ValidationDecision
!= RuntimeDecision

ValidationDecision BLOCK
!= RuntimeDecision BLOCK
```

Similar human words do not merge their responsibility or authority boundaries.
For the first profile, RuntimeDecision `ALLOW` means that the caller may use or
return an already-completed result. It does not authorize candidate append.

## In-Memory Reviewability

Without freezing exact Python fields, a first-slice RuntimeDecision must expose
enough information to review:

- the selected generic current response;
- a stable machine-readable and human-readable decision reason;
- the consumed outcome reference, including `outcome_id`, boundary, category,
  and semantic code;
- when applicable, the exact refinement reference, including contract
  identity, contract version, rule identity, and candidate identity;
- explicit absence of exact refinement when no eligible refinement is present.

This is an in-memory reviewability requirement. It does not require
RuntimeDecision persistence, receipt persistence, or automatic receipt
materialization.

## Deferred Identity and Policy Versioning

PR1 does not justify a separate `decision_id`. The first slice is one live
same-process evaluation with no durable RuntimeDecision collection or
cross-process reconstruction requirement. The consumed `outcome_id` is
sufficient as the evidence reference for this boundary. RuntimeDecision
identity must be revisited only when a concrete consumer needs independent
decision correlation or persistence.

PR1 also defers `policy_id`, `policy_version`, a policy registry, hot reload,
and a policy configuration store. Possible future justifications include
multiple selectable policies, configuration rollout, durable decision
reconstruction, cross-process evaluation, policy comparison, or hot reload.
No current consumer requires them.

## Live In-Memory and Restart-Recovery Boundary

The first decision-governance delivery is primarily live and in memory:

```text
process remains alive
→ live in-memory runtime governance

process is lost or restarted
→ restart-recovery governance
```

For a normal short-lived in-process current-response decision,
`SemanticOutcome` plus eligible live refinement is the first design center.

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

It also does not introduce a generic plugin framework, Agent orchestration or
candidate repair, new rule-evidence producers, read-side or snapshot policy,
projection trust continuation, open-source preparation, or changes to
production code, tests, migrations, dependencies, or `.venv`.

## Read-Side and Snapshot Deferral

The first profile does not map `REQUIRES_REBUILD`, `FAST_PATH_UNAVAILABLE`,
`DERIVED_STATE_UNTRUSTED`, or `DRIFT_DETECTED`. It does not decide snapshot
fallback, quarantine, rebuild, or snapshot trust selection.

Those are possible future Stage 4C producer-family profiles only after a
separate source-grounded consumer audit. This deferral does not reopen Stage
4B.3; ADR 0026 continues to own Projection Trust Continuation re-entry.

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
- absent or malformed required primary evidence and unsupported or incoherent
  observations are refused rather than treated as allowed;
- optional exact-refinement absence is explicit and never fabricated;
- the first slice remains live/in-memory unless a concrete durability consumer
  independently justifies expansion;
- production changes, tests, and validation are separately authorized.

PR1 satisfies the documentation prerequisites by identifying the caller-owned
post-return boundary, the four supported Layer-1 profiles, terminal refinement
eligibility, refusal semantics, minimum in-memory reviewability, and explicit
identity/versioning deferrals. Exact production topology remains subject to the
source and human decision gates in the PR breakdown.

## Current Position

Stage 4C PR1 establishes the documentation-only, source-grounded
implementation-entry boundary. Production Runtime Decision Authority remains
unimplemented.

The first profile is live, in memory, caller-owned, and Layer-1 PostgreSQL
write-side first. The generic Stage 4C responsibility remains producer- and
domain-neutral; optional Order-rule refinement belongs only to the first
concrete profile. The next production proposal must follow the separately
reviewed planning gates rather than infer an API shape from this document.
