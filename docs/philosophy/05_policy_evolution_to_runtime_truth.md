# Future Direction: From Policy Evolution to Runtime Truth

[← Back to Philosophy Index](README.md)

## 1. Why This Note Exists

A related future direction for **Streaming System + Compass** is the relationship between policy evolution and runtime semantic admission.

As AI-assisted systems become more capable, governance cannot remain only in natural language documents, chat history, pull request comments, or developer memory.

If an AI-assisted system needs to operate safely over time, the rules that define correct behavior must eventually become explicit artifacts that can be reviewed, versioned, compared, validated, replayed, and consumed by machines.

This note records a future architecture direction:

```text
human intent
→ machine-readable policy
→ agent or workflow execution
→ runtime semantic admission
→ structured semantic outcome
→ recovery / replay / evidence
→ policy evolution
```

This direction is not fully implemented yet.

It is a future-oriented philosophy for how Compass may evolve after the runtime semantic validation, structured outcome, runtime decision, and action-safety baselines become stable.

---

## 2. The Broader Architecture Trend

Recent policy-as-code and agent workflow projects suggest a broader architectural trend:

```text
human intent
→ machine-readable policy
→ compiled execution structure
→ validation evidence
→ reviewable workflow artifacts
```

The important idea is:

```text
rule evolution itself should become machine-readable
```

This means that rules should not only be written for humans.

They should also become artifacts that tools, agents, validators, reviewers, and replay systems can inspect.

A policy-contract layer may answer questions such as:

```text
What behavior is allowed?
What behavior is forbidden?
Which rules changed?
Which rule version is active?
Which validation evidence is required?
Which replay result supports this change?
Which recovery path is allowed after a failure?
```

This is related to Compass, but it is not the same boundary.

---

## 3. Policy Contract vs Compass Runtime Admission

A policy-contract layer defines what correctness means.

Compass verifies whether a concrete runtime action actually satisfies that correctness boundary at the moment it attempts to mutate system truth.

Compass answers a different question:

```text
Given the accepted history,
should this specific runtime candidate action be admitted into system truth?
```

These two boundaries should not be collapsed.

A policy can be correct while the runtime context is still wrong.

For example:

```text
A policy may allow CREATED → PAID.
```

But at runtime, the candidate action may still be based on:

```text
a stale snapshot
an outdated version
a corrupted projection
a duplicate request
an agent-generated assumption
a context that no longer matches accepted history
```

In that situation, the policy alone is not enough.

The system still needs a runtime admission boundary that asks:

```text
Is the candidate action truthful relative to the accepted history right now?
```

This is the role of Compass.

---

## 4. Why Compass Alone Is Not the Full Governance Loop

Compass can reject invalid runtime actions.

However, Compass alone is not enough for a complete agent-governance loop.

If Compass only returns structured rejection outcomes, an agent may understand why an action failed, but still not know which correction path is semantically allowed.

Without a policy-contract source, retry may degrade into trial-and-error against Compass:

```text
change something
try again
wait until admission succeeds
```

That is not governed recovery.

A more mature architecture should move toward policy-guided recovery:

```text
structured semantic outcome
→ violated policy or contract
→ allowed recovery strategy
→ retry, abort, replay, or escalate
```

For example:

```json
{
  "decision": "REJECT",
  "reason": "STALE_PROOF",
  "violated_policy": "order.payment.requires_fresh_version",
  "recovery": {
    "strategy": "REFRESH_ACCEPTED_HISTORY_AND_REBUILD_ONCE",
    "max_attempts": 1,
    "human_required": false
  }
}
```

This does not mean Compass should become a full policy-authoring system.

It means Compass outcomes should eventually be able to reference policy rules, recovery contracts, and replay evidence.

---

## 5. Future Integration Pattern

A future Semantic Infrastructure layer may contain three complementary boundaries.

### 5.1 Policy Contract Layer

The Policy Contract Layer represents intended correctness before execution.

It may:

```text
represent domain rules and rule evolution
define allowed and forbidden behavior
record validation and replay expectations
describe recovery semantics
provide machine-readable comparison sources for agents and tools
```

### 5.2 Compass Runtime Admission Layer

The Compass Runtime Admission Layer validates runtime truth before mutation.

It may:

```text
validate candidate actions against accepted history
prevent invalid mutations from entering system truth
detect stale proof, invalid transition, or derived-state drift
produce structured semantic outcomes
```

### 5.3 Semantic Evidence and Recovery Layer

The Semantic Evidence and Recovery Layer connects failure evidence back to governance.

It may:

```text
link rejection outcomes back to policy rules
distinguish retryable, replayable, abortable, and dangerous failures
create evidence for audit, replay, and future policy improvement
guide runtime decision policy and action safety gates
```

The long-term direction is therefore not:

```text
Policy Contract replaces Compass
```

or:

```text
Compass replaces Policy Contract
```

The direction is:

```text
Policy Contract defines machine-readable correctness.
Compass enforces runtime semantic truth.
Semantic Outcome connects failure evidence back to recovery and policy evolution.
```

---

## 6. Relation to Semantic Infrastructure

This future direction extends the earlier separation between Data Infrastructure and Semantic Infrastructure.

Data Infrastructure preserves physical facts:

```text
events persisted
transactions committed
checkpoints advanced
projection state stored
```

Semantic Infrastructure evaluates whether those facts still preserve meaning:

```text
candidate event truth
derived state truth
retry intent consistency
snapshot trust
action safety
runtime recovery meaning
```

Policy contracts add another dimension:

```text
intended correctness should also become machine-readable
```

This allows the system to connect:

```text
intended meaning
runtime truth
failure evidence
recovery strategy
policy evolution
```

At that point, Semantic Infrastructure becomes more than validation.

It becomes the layer that connects machine-readable intent, runtime truth, and governable recovery.

---

## 7. Current Stage Boundary

This note describes a future architecture direction.

It does not mean the project currently implements a full policy-contract system.

The near-term project path remains narrower:

```text
Stage 3.5C
→ durable read-side baseline

Stage 3.5D
→ snapshot trust / replay efficiency

Stage 3.5E
→ durable history and permission hardening

Stage 4
→ Layer 2 validation, SemanticOutcome, RuntimeDecisionPolicy

Stage 4B.5 / future extension
→ Order Domain Policy Contract v0

Stage 5
→ semantic correctness × operational freshness → action safety
```

The first realistic policy-contract step should be small and domain-specific:

```text
Order Domain Policy Contract v0
```

Its goal should not be to build a general policy-authoring framework.

Its goal should be to let `SemanticOutcome` reference:

```text
policy_ref
violated_rule_id
recovery_hint
replay_requirement
human_review_requirement
```

This keeps the implementation focused while preserving the future direction.

---

## 8. Design Principle

The guiding principle is:

```text
Policy Contract defines intended correctness.
Compass verifies runtime truth.
Semantic Outcome records evidence and recovery meaning.
```

Or more directly:

```text
A system is not governable only because it can block invalid actions.
A system becomes governable when each block can be traced back to a rule,
a recovery path,
and evidence that can improve future policy.
```

This is the future direction Compass may evolve toward.
