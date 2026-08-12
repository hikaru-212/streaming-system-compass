# Stage 4B.5 PR Breakdown

[← Back to Stage 4B.5](README.md)

## Purpose

This note defines the implementation sequence for:

```text
Stage 4B.5 — Order Correctness Contract v0
```

Stage 4B.5 exists so that current correctness enforcement can be described by
stable, machine-readable rule identities without turning the declarative
contract into executable authority.

The first concrete consumer motivation is live Agent feedback:

```text
coarse rejection
→ exact violated correctness rule
→ constrained next-candidate space
```

The stage does not decide how the Agent repairs its reasoning and does not
authorize retry.

---

## Stage Principle

```text
current executable correctness
→ declarative correctness contract
→ parity evidence
→ typed rule-level evaluation evidence where source-legitimate
→ live semantic + rule feedback
```

Preserve:

```text
rule identity
!= technical status

rule identity
!= SemanticOutcomeCode

rule evidence
!= RuntimeDecision

rule evidence
!= retry authorization

contract
!= executable authority
```

---

## Branch Workflow

Stage 4B.5 uses the integration branch:

```text
feat/stage4b5-order-correctness-contract
```

Each PR branch targets that integration branch.

The planned sequence is:

```text
feat/stage4b5-order-correctness-contract
├── docs/stage4b5-pr1-source-grounded-order-correctness-boundary
├── feat/stage4b5-pr2-order-correctness-contract-v0
├── test/stage4b5-pr3-python-authority-parity
├── feat/stage4b5-pr4-rule-evaluation-evidence
├── feat/stage4b5-pr5-live-agent-rule-feedback
└── docs/stage4b5-pr6-closeout
```

If the post-PR5 human decision requires a separately scoped aggregate/domain
command-rejection evidence PR, insert it before closeout and renumber the final
closeout PR at that time.

One PR may contain multiple commits, but:

```text
one PR
= one coherent semantic delivery unit

one commit
= one smaller boundary-preserving change
```

---

## Evidence-First Sequence

```text
documentation
→ immutable declarative contract
→ executable-authority parity
→ producer-owned rule-evaluation evidence
→ live composition
→ closeout
```

No runtime rule-evaluation integration should precede a stable contract and
parity evidence.

---

# PR1 — Source-Grounded Order Correctness Boundary

## Branch

```text
docs/stage4b5-pr1-source-grounded-order-correctness-boundary
```

## Responsibility

```text
documentation only
```

## Purpose

Freeze the source-grounded Stage 4B.5 responsibility, enforcement ownership,
rule-category boundary, rule-identity principles, live Agent-feedback
motivation, known contradictions, and subsequent PR sequence before production
contract implementation.

## Deliverables

PR1 should add or update:

```text
docs/implementation_notes/stage_4b_5/README.md
docs/implementation_notes/stage_4b_5/pr_breakdown.md
docs/implementation_notes/stage_4b_5/order_correctness_contract_source_grounded_boundary.md
```

It should preserve:

```text
docs/implementation_notes/stage_4b_5/order_correctness_contract_boundary.md
```

as historical pre-audit candidate input.

PR1 may also perform narrow current-authority navigation/status alignment when
explicitly authorized.

## Required Decisions

PR1 records these source-grounded human decisions:

```text
event_id
= identity may be preallocated on a candidate;
  accepted-event status comes from accepted-history membership

positive amount
= normalized monetary value must be > 0

full-payment equality
= guaranteed by the normal command/candidate/admission trust chain;
  trusted apply(event) does not independently revalidate it

Order Correctness Contract
= multiple explicitly separated correctness categories;
  not one flat DOMAIN_INVARIANT list
```

PR1 also records:

- aggregate/domain command rejection is not Compass `ValidationResult(FAILED)`
  followed by validation-policy `BLOCK`;
- aggregate failures currently do not have precise typed rule-level evidence;
- Compass Layer 1 owns exact failure branches internally but does not yet return
  a typed rule discriminator;
- stable rule identity is justified by the live Agent-feedback consumer;
- actual rule IDs remain PR2 responsibility.

## Dependencies

- completed Stage 4A semantic boundary;
- completed Stage 4B DecisionReceipt foundation;
- completed Stage 4B.1 DiagnosticTrace work;
- completed Stage 4B.2 measurement work;
- current Order / Money / Proof / Event source;
- current Compass Layer 1 validator source;
- current accepted documentation and human direction.

## Non-Goals

- no production contract;
- no tests;
- no rule IDs frozen as API;
- no RuleEvaluationEvidence implementation;
- no SemanticOutcome or DecisionReceipt change;
- no Agent retry or correction behavior;
- no admission or idempotency implementation;
- no B4.3 work.

## Stop Condition

Stop if PR1 would need to:

- silently choose between contradictory normative and executable meaning;
- change runtime behavior;
- freeze rule IDs without a source-grounded semantic subject;
- infer rule identity from free-text reasons or exception strings.

---

# PR2 — Immutable Order Correctness Contract v0

## Branch

```text
feat/stage4b5-pr2-order-correctness-contract-v0
```

## Responsibility

Introduce the canonical immutable, data-only typed Python correctness contract.

## Expected Scope

PR2 may define:

- contract identity;
- contract version;
- closed vocabularies;
- explicit rule categories;
- stable rule identities;
- rule evaluation subjects;
- declarative transition relationships;
- normalized-money constraints;
- candidate-construction semantics;
- trusted-application preconditions/effects;
- Compass Layer 1 transition-truth rules approved by PR1.

## Representation Direction

Preferred first implementation:

```text
immutable
data-only
typed Python
```

Use frozen structures and existing stable domain enums where appropriate.

Do not introduce callbacks, predicates, evaluator functions, mutation methods,
policy methods, dependency injection, or a second hand-maintained JSON/YAML
authority.

## Dependencies

- accepted PR1;
- human disposition or explicit qualification of PR1 contradictions;
- approved rule-identity naming principles.

## Non-Goals

- no runtime evaluator;
- no RuleEvaluationEvidence;
- no Agent integration;
- no policy / retry / recovery;
- no admission or idempotency behavior changes;
- no serialization or persistence requirement.

## Stop Condition

Stop if any proposed rule:

- lacks a source-grounded proposition;
- requires changing current executable semantics;
- cannot define its subject clearly;
- would make the contract executable authority;
- requires a new dependency.

---

# PR3 — Python Executable-Authority Parity

## Branch

```text
test/stage4b5-pr3-python-authority-parity
```

## Responsibility

Provide executable evidence that the accepted declarative contract still
describes the current Python authority.

## Parity Surface

Parity should cover the approved PR2 scope across:

- `OrderAggregate`;
- shared Money behavior;
- candidate event and Proof construction;
- trusted `apply(event)` preconditions/effects;
- included Compass Layer 1 transition-truth checks.

## Important Boundary

```text
parity
= evidence that representations agree

parity
!= independent proof that both are semantically correct
```

Parity must compare behavior and structure, not exception-message wording.

## Dependencies

- accepted PR2.

## Non-Goals

- no production behavior changes;
- no weakening of mismatched expectations;
- no runtime rule-evaluation producer;
- no policy / retry / recovery;
- no database requirement.

## Stop Condition

Stop if the declarative contract and executable authority genuinely disagree.
Report the contradiction for human semantic review instead of normalizing it
through test changes.

---

# PR4 — Typed RuleEvaluationEvidence

## Branch

```text
feat/stage4b5-pr4-rule-evaluation-evidence
```

## Responsibility

Introduce the smallest typed rule-level evidence boundary and source-legitimate
producer support.

The initial producer should be limited to a source that already knows the exact
failed rule branch without text parsing.

Current first candidate:

```text
FullProofValidator
```

## Candidate Evidence Shape

Conceptually:

```text
contract identity
contract version
rule identity
evaluation result
subject / correlation identity when required
```

The exact production shape is not frozen by PR1.

## Dependencies

- accepted PR3 parity;
- approved rule IDs;
- proven producer ownership.

## Non-Goals

- no exception-string parsing;
- no free-text reason parsing;
- no metadata-key inference;
- no Aggregate behavior change;
- no admission/idempotency expansion;
- no policy, action, retry, or repair instruction.

## Stop Condition

Stop if exact rule identity requires:

- changing Aggregate or Compass semantics;
- parsing text;
- creating a duplicate evaluator;
- inferring ownership from incidental metadata.

Current aggregate/domain command-failure coverage is explicitly not assumed.

---

# PR5 — Live Agent Rule Feedback

## Branch

```text
feat/stage4b5-pr5-live-agent-rule-feedback
```

## Responsibility

Provide same-process trusted correlation and delivery of live semantic evidence
and sibling rule-level evidence for the supported producer path.

Conceptually:

```text
SemanticOutcome
+
RuleEvaluationEvidence
→ live consumer / Agent
```

No new convenience envelope is required by default.

## Purpose

Move the supported live failure path from:

```text
coarse semantic rejection
```

to:

```text
coarse semantic rejection
+
exact violated correctness rule
```

so a consumer can constrain the next candidate space without Stage 4B.5
prescribing repair.

## Dependencies

- accepted PR4;
- source-grounded provenance / correlation guarantee.

## Non-Goals

- no SemanticOutcome field change;
- no DecisionReceipt change;
- no DiagnosticTrace change;
- no Agent automatic correction;
- no retry authorization;
- no retry count/backoff;
- no persistence requirement.

## Stop Condition

Stop if same-process correlation cannot be guaranteed without:

- free-text inference;
- global mutable state;
- protected contract changes;
- invented execution identity.

---

# Post-PR5 Human Decision Gate

After PR5, explicitly decide whether Stage 4B.5 completion requires live typed
rule evidence for aggregate/domain command failures such as:

- illegal command state before candidate construction;
- invalid normalized amount;
- full-payment mismatch.

Current source does not provide a precise typed domain-rejection producer for
these failures.

If live aggregate-domain rule feedback is required before closeout:

```text
insert a separately scoped PR before closeout
```

That PR must receive its own architecture review because it changes the current
producer surface.

If it is not required:

```text
close Stage 4B.5 with this producer-coverage limitation explicitly documented
```

---

# PR6 — Stage 4B.5 Closeout

## Branch

```text
docs/stage4b5-pr6-closeout
```

## Responsibility

Record the final delivered Stage 4B.5 boundary.

## Required Closeout Record

- accepted correctness contract and identity/version;
- stable rule-ID surface;
- parity scope and limitations;
- supported rule-evaluation producers;
- supported live semantic + rule feedback path;
- unsupported aggregate/domain rejection coverage, if still deferred;
- admission and idempotency deferrals;
- DecisionReceipt durability deferral;
- relationship to Stage 4C / 4D / 4E;
- explicit statement that rule feedback constrains candidate space but does not
  authorize retry or prescribe Agent reasoning.

## Non-Goals

- no new implementation;
- no durable rule analytics unless separately implemented;
- no automatic Agent correction;
- no policy / strategy / retry implementation.

## Stop Condition

Stop if closeout wording overstates:

- rule coverage;
- live producer coverage;
- durable evidence;
- retry capability;
- admission/idempotency scope.

---

## Stage-Wide Non-Goals

Stage 4B.5 does not absorb:

- Stage 4B.3 projection trust continuation;
- RuntimeDecisionPolicy;
- StrategySelector;
- RetryGovernance / AttemptLog;
- rate limiting or capacity policy;
- generic policy authoring;
- Agent planner/orchestrator;
- automatic contract evolution;
- cross-domain governance;
- DecisionReceipt redesign;
- DiagnosticTrace redesign;
- database schema/migration work unless separately authorized later.

---

## Stage Completion Boundary

Stage 4B.5 is complete when:

1. the source-grounded correctness boundary is documented and accepted;
2. a canonical immutable contract with stable identity/version exists;
3. stable rule identities exist for the approved scope;
4. parity evidence covers the approved executable owners;
5. at least the approved Compass-first rule-evaluation producer path is either
   implemented or explicitly deferred after human review;
6. the supported live feedback path is documented truthfully;
7. unsupported aggregate/domain typed rule feedback is not implied;
8. admission, idempotency, action policy, strategy, and retry remain separately
   owned.

A green parity suite is accepted evidence for the defined scope. It is not proof
that no future semantic bug exists.
