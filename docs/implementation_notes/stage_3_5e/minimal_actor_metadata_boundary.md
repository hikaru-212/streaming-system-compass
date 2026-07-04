# Minimal Actor Metadata Boundary

[← Back to Stage 3.5E](README.md)

## Purpose

This note defines the Stage 3.5E PR5 implementation boundary:

```text
Stage 3.5E PR5 — Minimal Actor Metadata Boundary
```

PR5 clarifies what actor metadata means before the project enters Stage 4 runtime semantic governance.

The goal is not to introduce a full actor model.

The goal is to prevent the project from confusing:

```text
database role permissions
producer metadata
governance decision evidence
```

---

## Why PR5 Exists

Stage 3.5E PR2–PR4 establish a PostgreSQL permission boundary.

They answer:

```text
Which runtime role can mutate which durable table?
```

However, Stage 4 will need to answer richer runtime governance questions:

```text
Who produced this evidence?
Who triggered this recovery?
Who created this receipt?
Who selected this strategy?
Who decided this action was allowed?
```

PR5 defines the minimum boundary between those questions.

---

## Accepted Model

Stage 3.5E accepts this model:

```text
database role
= permission identity
= controls what SQL operations a runtime component may perform

actor metadata
= producer / trigger metadata
= records who or what produced a durable artifact

governance evidence
= Stage 4 decision evidence
= records what happened, what it meant, who did it, what it cost, and what recovery path was allowed
```

These concepts should remain separate.

---

## Current Baseline

Stage 3.5E already has limited producer metadata in the durable schema.

The clearest current example is:

```text
projection_snapshots.created_by
```

This field should be interpreted as:

```text
producer metadata
```

not as:

```text
trust proof
policy approval
runtime decision evidence
downstream action safety proof
```

A snapshot row may say who created it.

That does not mean the snapshot is trusted.

Snapshot trust still requires validation against accepted history and later receipt-backed trust selection.

---

## PR5 Decision

PR5 is documentation-first and should normally remain documentation-only.

The default decision is:

```text
No schema migration in PR5.
Do not add a full actor registry.
Do not add audit tables.
Do not add DecisionReceipt tables.
Use existing created_by-style fields as baseline producer metadata.
Defer validated_by / decision_by / receipt_by / triggered_by to Stage 4 governance evidence.
```

Schema changes should be introduced only if an existing field is clearly misdocumented or misleading.

---

## Stage 4 Handoff

PR5 prepares Stage 4 by defining what Stage 4 may later attach to receipts and decisions.

Stage 4B may use fields such as:

```text
actor_id
actor_role
evidence_source
boundary
strategy_used
elapsed_ms
```

Stage 4 may also introduce governance-specific actor fields such as:

```text
validated_by
decision_by
receipt_by
triggered_by
repair_requested_by
quarantined_by
```

But those fields belong with Stage 4 concepts:

```text
SemanticOutcome
DecisionReceipt
RuntimeDecisionPolicy
DiagnosticTrace
StrategySelector
RetryGovernance
```

They should not be introduced as isolated columns before the corresponding governance meaning exists.

---

## Relationship to Stage 3.5E Roles

The Stage 3.5E runtime roles are still permission roles:

```text
compass_app_writer
compass_projection_worker
compass_snapshot_worker
compass_readonly
```

They express runtime responsibility boundaries.

They are not a full human identity system.

They are not product user roles.

They are not a complete audit model.

They answer:

```text
Which component may mutate which durable artifact?
```

They do not fully answer:

```text
Which actor made this semantic decision, under which policy, with which evidence?
```

That answer belongs to Stage 4.

---

## Non-goals

PR5 does not implement:

```text
new PostgreSQL roles
new SQL migrations
actor registry
user table
role table
login/session auth
JWT
full RBAC
multi-tenant auth
cloud IAM integration
audit dashboard
DecisionReceipt persistence
RuntimeDecisionPolicy
SemanticOutcome
DiagnosticTrace
StrategySelector
RetryGovernance
production identity wiring
```

PR5 also does not update global test/development documentation.

Those belong to Stage 3.5E PR6 closeout.

---

## Completion Criteria

PR5 is complete when:

```text
minimal actor metadata boundary is documented
existing created_by-style metadata is interpreted as producer metadata
permission identity is separated from governance evidence
Stage 4 actor evidence is explicitly deferred
README / PR breakdown notes are aligned
no full identity / audit / receipt system is introduced
```

---

## Summary

PR5 closes the conceptual gap between Stage 3.5E permission hardening and Stage 4 runtime governance.

It preserves the distinction:

```text
permission role
≠ producer metadata
≠ decision evidence
```

This allows Stage 4 to introduce SemanticOutcome, DecisionReceipt, RuntimeDecisionPolicy, and RetryGovernance without overloading database roles or `created_by` fields with meanings they do not yet carry.
