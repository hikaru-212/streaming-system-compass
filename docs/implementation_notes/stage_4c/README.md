# Stage 4C — Runtime Decision Authority

[← Back to Implementation Notes](../README.md)

## Status

```text
STAGE 4C COMPLETE / CLOSED
PR1 SOURCE-GROUNDED IMPLEMENTATION-ENTRY BOUNDARY
PR2 IMPLEMENTED
GENERIC RUNTIMEDECISION + FIRST LAYER-1 POSTGRESQL / ORDER PROFILE
STAGE 4C.5 COMPATIBILITY / DOCUMENTATION CLOSEOUT
STAGE 4E PR3 LIVE OWNER DELIVERY CAPABILITY IMPLEMENTED
```

This stage entry records the source-grounded Stage 4C PR1 boundary, the PR2
delivery of the generic immutable `RuntimeDecision` contract and first Layer-1
PostgreSQL / Order evaluator, and the Stage 4C.5 compatibility disposition. The
two PR2 responsibilities remain separately owned in separate modules. The
implemented evaluator is an explicit callable capability with no automatic
application caller wiring. Stage 4E PR3 now gives the live PostgreSQL
invocation owner an explicit production delivery capability over its current
normal result without changing Stage 4C profile semantics. No application or
bootstrap consumer currently enforces the returned delivery.

The accepted authority decision is
[ADR 0027 — Separate Runtime Decision, Strategy, and Retry Authority](../../adr/0027_separate_runtime_decision_strategy_and_retry_authority.md).

The implementation sequence is preserved separately in the
[Stage 4C PR Breakdown](pr_breakdown.md). This README owns the current
source-grounded implementation boundary; the breakdown preserves delivery
sequencing and downstream re-entry gates. The final completion authority is the
[Stage 4C closeout](stage_4c_closeout.md).

## Purpose

Stage 4C owns Runtime Decision Authority.

It answers:

> Given the current semantic observation and eligible supporting evidence,
> what generic current response or action is permitted, required, or denied?

It does not execute the response, choose an execution strategy, or authorize
another same-request public writer invocation.

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
!= same-request re-invocation authorization
!= re-invocation execution
```

Stage 4C owns a generic current-response decision. Stage 4D may later choose
`HOW` for an already-authorized operation when multiple eligible execution
paths exist. Stage 4E separately decides whether one later public writer
invocation using the same complete `RequestSignature` is allowed and under
which constraints. Actual action and request re-invocation execution remain
separate.

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

- same-request re-invocation classification or authorization;
- re-invocation count, budget, or timing;
- cross-invocation authority-refresh or validation-authority requirements;
- cross-invocation candidate-reuse constraints;
- prior-invocation lineage or intent consistency;
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

The generic output is implemented as an immutable `RuntimeDecision` carrying
only the selected `RuntimeDecisionResponse`, the exact consumed
`SemanticOutcome` object, and a non-empty human-readable explanation. It does
not duplicate outcome identity or tuple fields, add a separate reason code, or
depend on Order or PostgreSQL types. The generic output does not introduce a
universal rule-evidence abstraction, evidence bag, `Stage4CInput`, or generic
governance envelope.

The first concrete evaluation profile is narrower:

```text
Layer-1 PostgreSQL / Order write-side profile

input:
PostgresWriteSideSemanticRuleFeedback

output:
PostgresWriteSideRuntimeDecisionEvaluation
= generic RuntimeDecision
+ exact source PostgresWriteSideSemanticRuleFeedback
```

`OrderRuleViolationEvidence` belongs to this concrete profile, not to the
generic Stage 4C contract. A future cross-domain consumer must demonstrate a
concrete need before Stage 4C introduces a more general evidence abstraction.

## First Invocation and Consumer Boundary

PR1 recorded the source-grounded conceptual flow:

```text
PostgresWriteSideResult
→ PostgresWriteSideSemanticRuleFeedback
→ evaluate_postgres_write_side_runtime_decision
→ PostgresWriteSideRuntimeDecisionEvaluation
→ caller-owned use of RuntimeDecision
```

PR2 implements the explicit evaluator capability in that flow, but does not
wire a production caller. Its invocation boundary is after
`PostgresTransactionalWriteSide` has normally returned a terminal result. A
future invocation owner would be the caller at that post-return boundary. The
Stage 4C evaluator remains outside the write-side transaction and admission
execution. PR2 does not add a writer API, application layer, executor, or retry
loop merely to create a consumer.

A `RuntimeDecision` over an accepted write-side result cannot
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
`PostgresWriteSideSemanticRuleFeedback` is the source-controlled
producer-specific evaluator input because it preserves:

```text
SemanticOutcome
+ terminally applicable OrderRuleViolationEvidence
```

The profile-specific evaluation delivery preserves the exact feedback object
beside the generic decision so reviewability does not force Order evidence into
the generic contract. Neither carrier is a universal Stage 4C abstraction.
This stage does not introduce a generic evidence bag or `Stage4CInput` wrapper.

## Evidence Eligibility

| Evidence | What it proves | What it does not prove | First-slice posture |
|---|---|---|---|
| `SemanticOutcome` | Coarse semantic meaning, observation boundary, severity, risk, reversibility, context, and supporting evidence. | Runtime action, execution strategy, retry authorization, or persistence. | Required primary live evidence. |
| `OrderRuleViolationEvidence` | One exact stable Order-rule violation for one candidate when produced by an eligible source. | Complete violation coverage, diagnosis, repair, action authority, or retry safety. | Optional profile-specific refinement when terminally applicable. |
| `PostgresWriteSideSemanticRuleFeedback` | One source-controlled PostgreSQL composition of `SemanticOutcome` and terminally applicable exact rule refinement. | Universal producer contract, durable provenance, complete rule coverage, or retry authority. | Required input for this first profile; not mandatory for Stage 4C universally. |
| `DecisionReceipt` | Durable-capable, reviewable governance evidence preserving selected semantic meaning, subject, correlation, admission fate, and evaluation states. | Current action authority, retry authorization, proof that one in-memory instance was persisted, or permanent authorization. | Supporting durable evidence; not required for the first live hot path. |
| Producer-specific trace | Bounded execution topology or diagnostic detail owned by its producer. | Terminal semantic cause, action permission, retry safety, or durability unless separately established. | Not a mandatory input; add only for a concrete policy consumer. |
| Measurement evidence | Bounded execution-cost observations. | Semantic truth, action authority, retry safety, or strategy authorization. | Not a mandatory Stage 4C input; principally relevant to later strategy consumers. |
| `FullProofValidationEvidence` | The producer-specific validation result and an optional exact violation from exactly six supported `TRANSITION_TRUTH` rules. | All 18 rules, terminal write-side meaning, action authority, or retry safety. | Not a Stage 4C input requirement; consume eligible preserved refinement instead. |

## First Supported Current-Response Profile

PR1 froze four supported Layer-1 semantic profiles. PR2 implements their
subject-explicit response identifiers as one closed generic vocabulary.

| Boundary / category / semantic code | Generic current-response meaning | Qualification |
|---|---|---|
| `LAYER_1_WRITE_SIDE` / `VALID` / `SEMANTICALLY_VALID` | `USE_CURRENT_RESULT` | The caller may use or return the already-completed current result. This does not retroactively authorize candidate append or transaction commit. |
| `LAYER_1_WRITE_SIDE` / `RETRY_CLASSIFIED` / `IDEMPOTENT_REPLAY_ALLOWED` | `RETURN_PRIOR_ACCEPTED_RESULT` | The caller may return the prior accepted result. This is not authorization for another request invocation and creates no new candidate or accepted event. |
| `LAYER_1_WRITE_SIDE` / `BLOCK_REQUIRED` / `SEMANTIC_CONFLICT_DETECTED` | `BLOCK_CURRENT_CONTINUATION` | Terminal exact Order-rule evidence may refine review text. It does not create repair or retry authority or leave the block-current-continuation family. |
| `LAYER_1_WRITE_SIDE` / `ESCALATION_REQUIRED` / `REQUIRES_OPERATOR_REVIEW` | `REQUIRE_ESCALATION` | Stage 4C expresses authority only and does not execute an operator workflow. |

## Unsupported and Refused Observations

`CONCURRENCY_UNCERTAIN` is explicitly outside the first supported mapping.
Current source proves uncertainty but does not yet establish whether the
correct current response is block, escalation, reload, backoff, another
same-request re-invocation, or another response. Reload, backoff, and
same-request re-invocation questions also cross into Stage 4E authority.

```text
unsupported or unresolved Stage 4C observation
→ no authoritative RuntimeDecision
→ never implicit ALLOW
```

Input outside the reviewed four tuples is refused through the evaluator-specific
`PostgresWriteSideRuntimeDecisionRefused` exception. Wrong Python input types
raise `TypeError`; source-feedback construction failures propagate rather than
being reconstructed or normalized. Refusal is neither a fifth response nor a
fabricated positive `BLOCK_CURRENT_CONTINUATION` decision, and it is never
implicit `USE_CURRENT_RESULT`.

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

That last conceptual case does not broaden the current first-profile input.
PR2 deliberately consumes `PostgresWriteSideSemanticRuleFeedback`, whose
source-controlled construction requires exact Order rule evidence when
`VALIDATION_BLOCKED` is the terminal write-side result. An evidence-less
terminal validation block therefore cannot enter this evaluator through the
current feedback carrier.

This does not make the coarse `SemanticOutcome` invalid, permit fabricated
rule evidence, or weaken the Stage 4B.5 carrier. It is a deliberate first-profile
scope boundary, not a permanent architectural prohibition. Supporting such a
producer later requires separate source-grounded review.

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

It may stop a candidate before accepted-history mutation. A `RuntimeDecision`
instead consumes a terminal/current `SemanticOutcome` and eligible supporting
evidence after the relevant producer result exists, then expresses generic
current-response authority.

```text
ValidationDecision
!= RuntimeDecision

ValidationDecision BLOCK
!= RuntimeDecision BLOCK_CURRENT_CONTINUATION
```

Similar human words do not merge their responsibility or authority boundaries.
For the first profile, `USE_CURRENT_RESULT` means that the caller may use or
return an already-completed result. It does not authorize candidate append.

## In-Memory Reviewability

The generic `RuntimeDecision` exposes the selected current response, exact
consumed `SemanticOutcome`, and non-empty human-readable explanation. The
consumed outcome remains the single semantic observation authority: its
`semantic_code` is the current typed machine-readable rationale, while its
identity and tuple fields are not copied into the decision. The explanation is
reviewable but non-authoritative and must not be parsed for policy.

The first profile's `PostgresWriteSideRuntimeDecisionEvaluation` retains the
exact source `PostgresWriteSideSemanticRuleFeedback` beside the decision. Exact
terminal Order-rule refinement, or its source-controlled absence, therefore
remains reviewable without adding an Order field or generic evidence bag to
`RuntimeDecision`.

This is an in-memory reviewability requirement. It does not require
RuntimeDecision persistence, receipt persistence, or automatic receipt
materialization.

## Deferred Identity and Policy Versioning

PR2 does not justify a separate `decision_id`. The first slice is one live
same-process evaluation with no durable RuntimeDecision collection or
cross-process reconstruction requirement. The consumed `outcome_id` is
sufficient as the evidence reference for this boundary. RuntimeDecision
identity must be revisited only when a concrete consumer needs independent
decision correlation or persistence.

PR2 also defers `policy_id`, `policy_version`, a policy registry, hot reload,
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

## Stage 4C / 4D / 4E Relationship

For a completed current result:

```text
eligible current evidence
→ Stage 4C current-response decision or refusal
→ caller handling of that completed result
```

When another same-request invocation is considered, Stage 4E evaluates that
separate authority question from eligible prior-invocation evidence:

```text
eligible prior-invocation evidence
→ Stage 4E same-request re-invocation authorization or refusal

if another invocation is authorized:
→ Stage 4D strategy selection only when multiple eligible execution paths exist
→ execution
→ fresh producer result
→ Stage 4C current-response handling when applicable
```

Stage 4C current-response authority is not a prerequisite for Stage 4E
re-invocation authority. Stage 4C refusal is neither Stage 4E authorization nor
Stage 4E refusal.

Stage 4D owns `HOW` only when an already-authorized operation has multiple
eligible execution paths. The Stage 4C / 4D / 4E responsibilities therefore do
not form a mandatory linear pipeline. Same-request re-invocation authorization
does not execute the re-invocation, authorize an append or accepted effect,
permit old-candidate reuse, or grant unlimited request invocations.

## Stage 4C.5 Compatibility Disposition

Existing Layer-1 and Layer-2 producer families already share the
producer-neutral `SemanticOutcome` structural contract:

```text
compatible semantic contract
!= identical producer evidence
!= identical RuntimeDecision policy
!= identical caller behavior
```

Only the Layer-1 PostgreSQL / Order write-side family currently has a reviewed
`RuntimeDecision` profile. Layer-2, read-side, and snapshot families have no
concrete production current-response caller, guarded action requiring Stage 4C
authority, reviewed response rules, or demonstrated need for a generic
cross-layer evaluator.

Stage 4C.5 therefore closes as compatibility and documentation reconciliation.
It adds no Layer-2 or snapshot policy, rebuild/fallback/quarantine policy,
universal evaluator, generic evidence envelope, automatic caller wiring, or
production consumer created for symmetry.

## Explicit Non-Goals

This PR2 implementation does not introduce:

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
projection trust continuation, open-source preparation, automatic caller
wiring, writer changes, migrations, dependency changes, or `.venv` changes.

## Read-Side and Snapshot Deferral

The first profile does not map `REQUIRES_REBUILD`, `FAST_PATH_UNAVAILABLE`,
`DERIVED_STATE_UNTRUSTED`, or `DRIFT_DETECTED`. It does not decide snapshot
fallback, quarantine, rebuild, or snapshot trust selection.

Any future proposal for those producer families must satisfy the Stage 4C
re-entry conditions through a separate source-grounded consumer audit. This
deferral does not reopen Stage 4B.3; ADR 0026 continues to own Projection Trust
Continuation re-entry.

## PR2 Delivery and Closeout Boundary

The combined first production delivery preserves:

- ADR 0027 is the accepted responsibility authority;
- one concrete source-grounded evaluation profile exists;
- one explicit post-return invocation boundary is identified;
- the evaluator is an explicit callable production capability with no wired
  production caller;
- the eligible `SemanticOutcome` subset is source-grounded;
- terminal rule-refinement applicability is explicit;
- the minimal generic current-response vocabulary is reviewed;
- Stage 4C actions contain no same-request re-invocation authorization, count,
  budget, backoff, or cross-invocation authority-refresh ownership;
- Stage 4D and Stage 4E handoffs are explicit;
- absent or malformed required primary evidence and unsupported or incoherent
  observations are refused rather than treated as allowed;
- optional exact-refinement absence is explicit and never fabricated;
- the first slice remains live/in-memory unless a concrete durability consumer
  independently justifies expansion;
- profile-specific delivery retains exact source feedback without becoming a
  universal evidence envelope;
- production tests cover the contract, exact tuple mapping, refusal,
  reviewability, and terminal refinement boundary;
- no automatic caller is invented above the transactional writer.

PR1 supplied the source-grounded prerequisites. PR2 therefore delivers the
generic contract and first evaluator together while preserving their separate
module and dependency ownership. No standalone contract-only delivery is
required by the current source. Stage 4C.5 finds the existing producer-neutral
`SemanticOutcome` structure compatible across Layer-1 and Layer-2 families and
does not justify another production profile.

## Current Position

Stage 4C is complete and closed. PR2 implements the explicit callable
Layer-1 PostgreSQL write-side profile. Stage 4E PR3 consumes that unchanged
profile inside `PostgresWriteSideInvocationOwner`: the owner explicitly maps
only its currently published normal result and returns one cached decided or
refused current-response delivery with a stable owner-held `outcome_id`.
The generic `RuntimeDecision` remains producer- and domain-neutral; terminal
Order-rule refinement remains owned by the concrete feedback and evaluation
delivery.

This is the first production caller at the live producer-result boundary, not
an application/bootstrap consumer. It does not enforce continuation, execute
block or escalation effects, make evaluation automatic, or retain attempt
history. Stage 4C refusal remains only the absence of an authoritative
current-response decision and does not gate independent Stage 4E authority.
Stage 4D retains a valid `HOW`-selection responsibility but its implementation
is deferred. See the [Stage 4C closeout](stage_4c_closeout.md) for the historical
delivery map, compatibility verdict, downstream boundaries, and transition
record.
