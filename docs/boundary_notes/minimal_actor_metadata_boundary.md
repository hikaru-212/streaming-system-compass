# Minimal Actor Metadata Boundary

[← Back to Boundary Notes](README.md)

## Purpose

This note defines the minimum actor metadata boundary needed before Stage 4 runtime semantic governance.

Stage 3.5E introduces database role and permission hardening, but database permissions answer only one question:

```text
Which runtime role is allowed to mutate which durable artifact?
```

Stage 4 will need a different kind of evidence:

```text
Who or what produced this evidence?
Who or what triggered this decision?
Who or what applied this recovery action?
```

PR5 exists to separate these concepts before Stage 4 begins.

---

## Core Distinction

```text
database role
≠ actor metadata
≠ governance decision evidence
```

These three concepts are related, but they must not be collapsed.

---

## 1. Database Role

A database role is a PostgreSQL permission identity.

Examples:

```text
compass_app_writer
compass_projection_worker
compass_snapshot_worker
compass_readonly
```

It answers:

```text
Can this active database role execute this SQL operation?
```

For example:

```text
Can compass_snapshot_worker INSERT projection_snapshots?
```

This is the concern covered by Stage 3.5E PR2–PR4.

A database role is a permission boundary.

It is not, by itself, a durable explanation of why a semantic decision was made.

---

## 2. Actor Metadata

Actor metadata is durable producer or trigger information attached to a record.

Examples:

```text
created_by
triggered_by
actor_id
actor_role
runtime_component
```

It answers:

```text
Which component, role, or process produced this artifact?
```

For example:

```text
projection_snapshots.created_by = 'snapshot-worker'
```

This may identify the producer of the snapshot artifact.

It does not prove that the snapshot is trusted.

It does not prove that a policy decision approved the snapshot.

It does not prove that downstream usage is safe.

---

## 3. Governance Decision Evidence

Governance decision evidence belongs to Stage 4.

Examples:

```text
validated_by
decision_by
receipt_by
quarantined_by
repair_requested_by
policy_ref
runtime_decision_id
```

It answers:

```text
What semantic outcome was produced?
Which evidence was used?
Which policy or rule was referenced?
Which actor or runtime component made or triggered the decision?
Which recovery path was allowed?
```

This requires Stage 4 concepts such as:

```text
SemanticOutcome
DecisionReceipt
RuntimeDecisionPolicy
DiagnosticTrace
StrategySelector
RetryGovernance
```

Stage 3.5E should not implement these governance records prematurely.

---

## Accepted Boundary

Stage 3.5E accepts the following boundary:

```text
Stage 3.5E
= runtime role permission boundaries
+ minimal producer metadata where already present or clearly justified

Stage 4
= semantic outcome, durable decision evidence, actor attribution, policy-linked recovery, and runtime governance
```

Therefore:

```text
created_by
= baseline producer metadata

validated_by / decision_by / receipt_by
= Stage 4 governance evidence
```

---

## Current Stage 3.5E Position

The current durable schema already contains limited producer metadata in some places.

The clearest example is:

```text
projection_snapshots.created_by
```

This is useful as producer metadata.

It should be interpreted narrowly:

```text
created_by says who produced the artifact.
created_by does not say the artifact is trusted.
created_by does not say the artifact was selected by policy.
created_by does not say downstream usage is safe.
```

Snapshot trust still depends on accepted history, lineage checks, payload integrity, schema / reducer compatibility, tail replay, and validation receipts introduced later.

---

## Why This Boundary Matters

Without this boundary, Stage 4 could accidentally treat permission identity as semantic evidence.

For example:

```text
compass_snapshot_worker can INSERT projection_snapshots
```

means:

```text
the snapshot worker is allowed to produce snapshot artifacts
```

It does not mean:

```text
the snapshot is valid
```

It does not mean:

```text
the snapshot was selected by runtime policy
```

It does not mean:

```text
the snapshot can safely drive downstream actions
```

Permission allows a path.

Actor metadata identifies a producer.

Governance evidence explains a semantic decision.

---

## Stage 4 Handoff

Stage 4 may attach actor metadata to runtime evidence records.

Examples:

```text
DecisionReceipt.actor_id
DecisionReceipt.actor_role
DecisionReceipt.evidence_source
DecisionReceipt.boundary
DecisionReceipt.strategy_used
DecisionReceipt.elapsed_ms
```

Stage 4 may also introduce decision-specific actor fields when they have clear semantic meaning:

```text
validated_by
decision_by
receipt_by
triggered_by
quarantined_by
repair_requested_by
```

Those fields should be introduced only when there is a corresponding runtime governance concept.

Do not add actor fields before the system knows what decision, receipt, policy, or recovery action they describe.

---

## Non-goals

PR5 does not implement:

```text
actor registry
user table
role table
login/session auth
JWT
full RBAC
multi-tenant authorization
audit dashboard
DecisionReceipt persistence
RuntimeDecisionPolicy
SemanticOutcome
DiagnosticTrace
StrategySelector
RetryGovernance
production IAM
```

PR5 also does not require a schema migration unless a small alignment issue is found during implementation review.

The default direction is documentation-only.

---

## Reusable Rule

```text
Do not treat permission identity as semantic decision evidence.
```

A role may be allowed to perform an operation.

A record may identify who produced it.

A runtime decision must still preserve what happened, what it meant, what evidence was used, and why the selected action was allowed.

---

## Final Principle

```text
Database roles control mutation authority.
Actor metadata identifies producers and triggers.
Decision receipts preserve semantic governance evidence.
```
