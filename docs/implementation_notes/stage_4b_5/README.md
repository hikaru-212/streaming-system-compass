# Stage 4B.5 — Order Correctness Contract v0

> Runtime-overhead supplement: the completed, evidence-grounded findings are in
> the [Runtime Governance Overhead Characterization Report](runtime_governance_overhead_report.md),
> with the fixed design and limitations in the
> [Runtime Governance Overhead Characterization Method](runtime_governance_overhead_method.md).

> Closeout rationale: [Why Stage 4B.5 Exists](why_stage_4b_5_exists.md).
> Exploratory retry transition: [Retry Amplification, Local Correctness, and
> Semantic Diagnosis](../../reasoning_notes/retry_amplification_local_correctness_and_semantic_diagnosis.md).

## Status

```text
Stage 4B.5
= COMPLETE / CLOSED

current PR
= PR8 — documentation closeout

canonical correctness contract
= implemented with 18 stable rules

current typed runtime producer coverage
= exactly six FullProof TRANSITION_TRUTH rules

runtime / PostgreSQL evidence propagation and terminal refinement
= implemented
```

Stage 4B.5 defines a machine-readable representation of intended Order correctness without replacing the current Python executable authority.

The first concrete consumer motivation is live Agent feedback:

```text
candidate or command
→ current correctness enforcement
→ rejection
→ stable rule-level evidence
→ live Agent feedback
→ Agent independently regenerates a candidate
→ correctness enforcement runs again
```

The contract identifies which correctness constraint was violated.

It does not tell the Agent how to repair its reasoning, authorize retry, choose a recovery action, or bypass the existing correctness and admission boundaries.

---

## Core Boundary

```text
Python domain / Compass implementation
= current executable authority

Order Correctness Contract
= declarative machine-readable correctness representation

Parity tests
= evidence that the declarative representation remains aligned
```

The contract must not become:

- a second executable business-rule engine;
- a policy engine;
- runtime action selection;
- strategy selection;
- retry governance;
- admission execution;
- idempotency execution;
- Agent workflow orchestration.

---

## Current Source-Grounded Qualification

The current repository has more than one correctness-enforcement owner.

Important distinctions include:

```text
aggregate/domain command rejection
!=
Compass Layer 1 ValidationResult(FAILED)
→ validation-policy BLOCK

candidate construction
!=
accepted-event admission

trusted apply(event)
!=
complete command validation
```

Current aggregate command failures such as illegal command state, invalid amount,
or full-payment mismatch happen before candidate creation and do not currently
produce `ValidationResult`, `PostgresWriteSideResult`, or `SemanticOutcome`.

Current Compass Layer 1 rejection occurs after a candidate exists and validates
candidate claims against accepted-history-derived context.

That distinction is part of the Stage 4B.5 responsibility boundary.

---

## Stage Documents

- [PR Breakdown](pr_breakdown.md)
- [Source-Grounded Order Correctness Boundary](order_correctness_contract_source_grounded_boundary.md)
- [Why Stage 4B.5 Exists](why_stage_4b_5_exists.md)
- [Runtime Governance Overhead Characterization Method](runtime_governance_overhead_method.md)
- [Runtime Governance Overhead Characterization Report](runtime_governance_overhead_report.md)
- [Exploratory Retry-Amplification Reasoning Note](../../reasoning_notes/retry_amplification_local_correctness_and_semantic_diagnosis.md)
- [Deterministic YAML Readability Projection](order_correctness_contract_v0.yaml)
- `order_correctness_contract_boundary.md`
  - historical pre-audit planning input;
  - retained for provenance;
  - not current architecture authority.

---

## Delivered Stage 4B.5 Sequence

```text
PR1
→ source-grounded documentation boundary

PR2
→ immutable typed Order Correctness Contract v0
→ stable rule identities

PR3
→ executable-authority parity

PR4
→ typed FullProof rule-evaluation evidence

combined PR5 + PR6
→ ValidationRuntime preservation
→ PostgreSQL write-side propagation

PR7
→ explicit terminal SemanticOutcome + exact rule-refinement composition

supplements
→ deterministic Python-to-YAML readability projection
→ bounded runtime-governance overhead characterization

PR8
→ Stage 4B.5 documentation closeout
```

The accepted closeout scope keeps aggregate/domain command-rejection producers
deferred. Current typed production coverage remains the six FullProof
`TRANSITION_TRUTH` rules.

---

## First-Slice Categories

Stage 4B.5 must not flatten all correctness into one undifferentiated
`DOMAIN_INVARIANT` list.

The source-grounded first contract should preserve distinct categories such as:

- domain / command legality;
- candidate construction semantics;
- trusted-application preconditions and effects;
- Compass Layer 1 transition-truth constraints.

Admission, accepted-history durability, and idempotency semantics remain separate
later sub-slices unless explicitly promoted by a later human decision.

---

## Rule Identity

Stable rule identity is now justified by a concrete consumer:

```text
live Agent constraint feedback
```

PR2 froze the actual rule IDs with the immutable contract after PR1 established
the naming principles.

Rule identity must remain distinct from:

```text
technical status
SemanticOutcomeCode
admission disposition
RuntimeAction
recovery strategy
retry classification
```

---

## Live vs Durable Evidence

The first consumer is live same-process feedback.

Conceptually:

```text
SemanticOutcome
+
RuleEvaluationEvidence
→ live Agent feedback
```

The current same-invocation carrier is
`ValidationDecisionWithRuleEvidence`. The explicit terminal composition is
`PostgresWriteSideSemanticRuleFeedback`; neither changes `DecisionReceipt`
ownership or automatically persists feedback.

`DecisionReceipt` remains the durable compact governance artifact. Durable
rule-level correlation may later support cross-process recovery, historical
violation analysis, or Agent/workflow quality analysis, but that is not a v0
requirement and must not be implemented by stuffing `rule_id` into receipt
metadata.

---

## Explicit Non-Goals

Stage 4B.5 does not:

- change `OrderAggregate`;
- change Money semantics;
- change Compass Layer 1 allow/block semantics;
- change `SemanticOutcome`;
- change `DecisionReceipt`;
- change `DiagnosticTrace`;
- modify admission or idempotency behavior;
- add migrations or dependencies;
- automatically materialize `DecisionReceipt`;
- automatically invoke PR7 from every write command;
- authorize retry;
- define retry count, backoff, reload, fallback, rebuild, or human-review policy;
- automatically modify Agent candidates;
- implement Stage 4B.3 projection trust continuation.

---

## Historical Development Workflow

Stage 4B.5 used:

```text
feat/stage4b5-order-correctness-contract
```

as its integration branch.

Each PR branch is created from the current Stage 4B.5 integration branch and
merged back into it.

One PR may contain multiple commits, but each PR owns one coherent semantic
delivery unit.
