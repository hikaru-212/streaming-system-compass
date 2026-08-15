# Stage 4B.5 — Order Correctness Contract v0

> Runtime-overhead supplement: the completed, evidence-grounded findings are in
> the [Runtime Governance Overhead Characterization Report](runtime_governance_overhead_report.md),
> with the fixed design and limitations in the
> [Runtime Governance Overhead Characterization Method](runtime_governance_overhead_method.md).

## Status

```text
Stage 4B.5
= ACTIVE PLANNING

current PR
= PR1 — source-grounded correctness boundary

PR1 responsibility
= documentation only

production contract
= not implemented

runtime rule-evaluation evidence
= not implemented
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

## PR1 Documents

- [PR Breakdown](pr_breakdown.md)
- [Source-Grounded Order Correctness Boundary](order_correctness_contract_source_grounded_boundary.md)
- [Runtime Governance Overhead Characterization Method](runtime_governance_overhead_method.md)
- [Runtime Governance Overhead Characterization Report](runtime_governance_overhead_report.md)
- `order_correctness_contract_boundary.md`
  - historical pre-audit planning input;
  - retained for provenance;
  - not current architecture authority.

---

## Planned Stage 4B.5 Sequence

```text
PR1
→ source-grounded documentation boundary

PR2
→ immutable typed Order Correctness Contract v0
→ stable rule identities

PR3
→ executable-authority parity

PR4
→ typed RuleEvaluationEvidence
→ producer-owned rule evidence, Compass-first

PR5
→ live SemanticOutcome + sibling rule evidence composition

post-PR5 decision gate
→ decide whether aggregate/domain command rejection needs a separately scoped
  typed rule-evidence producer before closeout

final PR
→ Stage 4B.5 closeout
```

PR4 and PR5 remain gated by the source-grounded evidence established in PR1–PR3.

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

PR1 freezes naming principles only.

Actual rule IDs are frozen only with the immutable contract in PR2.

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

No convenience envelope is required in PR1.

`DecisionReceipt` remains the durable compact governance artifact. Durable
rule-level correlation may later support cross-process recovery, historical
violation analysis, or Agent/workflow quality analysis, but that is not a v0
requirement and must not be implemented by stuffing `rule_id` into receipt
metadata.

---

## Explicit Non-Goals

Stage 4B.5 PR1 does not:

- add production code;
- add production tests;
- change `OrderAggregate`;
- change Money semantics;
- change Compass Layer 1 allow/block semantics;
- change `SemanticOutcome`;
- change `DecisionReceipt`;
- change `DiagnosticTrace`;
- modify admission or idempotency behavior;
- add migrations or dependencies;
- authorize retry;
- define retry count, backoff, reload, fallback, rebuild, or human-review policy;
- automatically modify Agent candidates;
- implement Stage 4B.3 projection trust continuation.

---

## Development Workflow

Stage 4B.5 uses:

```text
feat/stage4b5-order-correctness-contract
```

as its integration branch.

Each PR branch is created from the current Stage 4B.5 integration branch and
merged back into it.

One PR may contain multiple commits, but each PR owns one coherent semantic
delivery unit.
