# Agent-Assisted Compass Layer Construction

[← Back to Semantic Admission Index](README.md)

**Recorded on:** 2026-07-02  

## 1. Problem Context

Enterprise AI systems are beginning to learn business semantics from existing organizational signals:

- tables
- schemas
- query history
- dashboards
- BI metrics
- transformation logic
- semantic views
- documentation
- user feedback
- lineage and usage patterns

This approach can help agents understand enterprise data more effectively. However, it also introduces a deeper governance problem.

Existing enterprise signals are not always correct.

A frequently used query pattern may reflect historical habit rather than correct business meaning. A dashboard metric may be outdated. A semantic definition may have changed after a product or pricing model evolved. Different teams may use the same term with different meanings.

If an agent learns from these signals directly, it may infer useful context, but that inferred context should not automatically become accepted semantic truth.

The core issue is:

```text
inferred semantic meaning ≠ accepted semantic contract
```

This is structurally similar to the original Compass principle:

```text
candidate event ≠ accepted fact
```

---

## 2. Core Idea

Compass can be extended from validating candidate events and actions into validating candidate semantic contracts.

In this extension, an agent is allowed to inspect enterprise signals and propose a candidate Compass layer, but it should not be allowed to approve its own semantic truth.

The agent can reduce human cognitive load by discovering patterns, surfacing conflicts, drafting rules, and producing evidence. However, the final accepted semantic boundary should still be reviewed, approved, or governed by someone who truly understands the company’s business semantics.

The principle is:

```text
agent proposes semantic contracts
Compass validates and records evidence
human or policy admits high-risk semantic truth
```

---

## 3. Why This Matters

A system like Cortex Sense or a semantic context layer can help an agent understand enterprise context. But if the semantic layer is generated from historical enterprise behavior, then the system must answer several questions:

- Which signals are authoritative?
- Which signals are merely inferred?
- Which signals are outdated?
- Which definitions conflict?
- Which definitions are team-specific?
- Which inferred meanings are safe enough to use?
- Which meanings require human confirmation?

Without an admission boundary, inferred context can silently become trusted context.

That creates a new failure mode:

```text
historical enterprise behavior
→ inferred semantic meaning
→ agent treats it as truth
→ future answers or actions depend on it
```

If the historical signals were wrong, stale, or scoped to the wrong team, the system may preserve and amplify incorrect business meaning.

Compass can address this by treating inferred semantics as candidates, not accepted truth.

---

## 4. Proposed Extension: Semantic Contract Evolution Boundary

This extension can be described as a Semantic Contract Evolution Boundary.

The system tracks semantic understanding as versioned contracts:

```text
semantic contract v1
    ↓
new enterprise signals appear
    ↓
agent proposes candidate semantic contract v2
    ↓
Compass-style validation
    ↓
accepted semantic contract v2
```

Each semantic version should carry evidence and lineage.

A candidate semantic contract should explain:

- where the definition came from
- which tables or dashboards support it
- which queries imply it
- which semantic views confirm it
- which documents mention it
- which teams use it
- which signals conflict with it
- when it was last supported
- which scope it applies to

This turns semantic evolution into a governed process instead of an invisible model update.

---

## 5. Role of the Agent

The agent should not be the final authority.

Its role is to reduce human burden by doing the expensive discovery work:

- discover candidate definitions
- summarize evidence
- detect conflicting meanings
- infer likely scope
- rank signals by authority and freshness
- draft candidate validation rules
- generate explanation receipts
- suggest whether human review is needed

The agent can produce a candidate Compass layer, but that candidate layer must still be admitted.

A safe workflow looks like this:

```text
enterprise signals
    ↓
agent proposes candidate semantic contract
    ↓
Compass validates evidence, lineage, freshness, and conflict
    ↓
result:
    ACCEPTED
    REJECTED
    UNCERTAIN
    CONFLICTING
    HUMAN_REVIEW_REQUIRED
```

The agent assists construction.

It does not self-authorize truth.

---

## 6. Human Role

A person who understands the company’s business semantics remains necessary, especially for high-risk definitions.

Examples include:

- MRR
- ARR
- churn rate
- active user
- revenue recognition
- customer status
- billing state
- pricing plan performance
- compliance metrics

These definitions are not just technical labels. They affect business decisions, reporting, finance, operations, and downstream automation.

For these cases, the agent should surface evidence and ambiguity, but the accepted semantic contract should be confirmed by a responsible owner.

This keeps the human role focused on judgment rather than search.

Instead of asking humans to inspect thousands of tables and dashboards manually, the agent narrows the problem:

```text
Here are the candidate definitions.
Here is the evidence.
Here are the conflicts.
Here is the likely scope.
Here is what needs approval.
```

---

## 7. Relationship to Original Compass

Original Compass:

```text
candidate event/action
    ↓
admission boundary
    ↓
accepted history
```

Extended Compass:

```text
candidate semantic definition
    ↓
semantic contract admission boundary
    ↓
accepted semantic contract version
```

The original system protects accepted history from invalid events.

The extended system protects accepted context from invalid inferred semantics.

Both follow the same deeper rule:

```text
candidate output must not become system truth by default
```

---

## 8. Relationship to Enterprise Semantic Systems

A system like Cortex Sense focuses on helping agents understand enterprise context.

Compass can complement this by asking:

```text
When does inferred context become accepted context?
```

This creates a natural separation:

```text
Semantic discovery layer:
    What does the enterprise data seem to mean?

Compass semantic admission layer:
    Which inferred meanings are allowed to become accepted semantic truth?
```

This distinction matters because enterprise semantics are not flat. A governed semantic view, a dashboard convention, a query pattern, a stale document, and an inferred model suggestion should not carry the same authority.

---

## 9. Example

Suppose the system discovers several definitions of `total_users`.

Evidence A:

```text
Marketing dashboard:
total_users = all registered users
```

Evidence B:

```text
Product analytics queries:
total_users = users active at least once in the period
```

Evidence C:

```text
Finance semantic view:
total_users = paying customers only
```

A naive agent might choose the most common one.

A Compass-style semantic boundary would instead produce:

```text
status = CONFLICTING_SEMANTIC_CANDIDATES

reason:
Multiple high-authority definitions exist for the same business term.

candidate_definitions:
1. all registered users
2. active users in period
3. paying customers only

required_action:
Human review required, or split the term by business scope.

suggested_scope:
marketing.total_users
product.active_users
finance.paying_customers
```

The system does not hide ambiguity.

It turns ambiguity into a governed decision.

---

## 10. Key Principle

The agent can help build the Compass layer, but it should not replace the Compass layer.

A useful formulation is:

```text
Agent-generated semantic contracts are candidates.
Accepted semantic contracts require evidence, lineage, validation, and governance.
```

Or shorter:

```text
The agent may draft the boundary.
The system must still govern admission.
```

---

## 11. Why This Reduces Cognitive Load

The goal is not to remove humans from semantic governance.

The goal is to move humans away from raw discovery and toward final judgment.

Without agent assistance, humans must manually inspect:

- tables
- dashboards
- queries
- docs
- lineage
- BI models
- historical definitions
- conflicting usage patterns

With agent-assisted Compass construction, the agent performs the discovery work and presents structured candidates.

Humans then decide:

- accept
- reject
- scope
- rename
- split
- escalate

This reduces cognitive load while preserving semantic accountability.

---

## 12. Summary

This concept extends Compass from event admission to semantic contract evolution.

The core idea is:

```text
If an agent can infer enterprise semantics from historical signals,
those inferred semantics should themselves pass through an admission boundary
before becoming accepted context.
```

This creates a stronger enterprise AI governance model:

```text
semantic discovery
    ↓
candidate semantic contract
    ↓
Compass-style validation
    ↓
accepted semantic contract version
    ↓
agent grounding / query planning / action validation
```

The agent helps propose the Compass layer.

But the accepted Compass layer should still be governed by evidence, lineage, validation rules, and human judgment where needed.
