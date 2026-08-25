# Semantic Admission

[← Back to Docs Home](../README.md)

This folder is the condensed AI governance entry point for the Streaming System + Compass project.

The full Compass project contains many distributed-systems implementation details: durable write-side storage, projections, checkpoints, replay validation, snapshot trust contracts, transaction boundaries, idempotency, concurrency, and failure recovery.

This section focuses on the higher-level problem framing:

> When an AI agent proposes a state-changing action, what makes that action eligible to become system truth?

That question remains the historical and implemented write-side core of
Semantic Admission. The broader corpus now also asks two related but asymmetric
questions:

```text
STATE-CHANGE / EFFECT-SIDE GOVERNANCE
What may become true?

CLAIM-SIDE SEMANTIC GOVERNANCE
What may be claimed as true?
```

Compass treats agent output as a candidate, not as truth.

A successful tool call, database write, or workflow completion may prove execution success, but it does not automatically prove semantic correctness.

The effect-side path is substantially grounded in implemented Compass behavior.
The claim-side path remains primarily conceptual and research-oriented; this
broader framing does not claim that production claim admission already exists.

Not every candidate comes from AI, and Semantic Admission does not govern every
AI decision. When probabilistic agency does participate, two earlier governance
questions may apply before a candidate reaches admission:

```text
delegation
→ should AI participate in this decision?

influence
→ what may AI affect, select, construct, route, or activate?

candidate
→ proposed action, event, claim, or other artifact

semantic admission
→ may the candidate receive trusted status appropriate to its type?
```

Delegation and Influence are adjacent upstream problem boundaries, not new
names for Semantic Admission and not one implemented universal evaluator. See
[Probabilistic Agency Inside Deterministic Business Workflows](../research/ai_governance/probabilistic_agency_inside_deterministic_business_workflows.md)
for the research framing.

---

## Disclosure Scope

This section is intended as a public conceptual entry point.

It defines the problem, vocabulary, and case-study framing for Semantic Admission.

It does not expose complete implementation internals, final contract schemas, validator algorithms, authority matrices, runtime policy tables, or production enforcement designs.

The goal is to make the architectural boundary understandable while preserving implementation flexibility and design ownership.

---

## Core Claim

A state-changing agent system needs a boundary between:

- **candidate action**: what the agent proposes
- **accepted fact**: what the system formally allows to become durable truth

This boundary is called **semantic admission**.

At the broader conceptual level, Semantic Admission can apply to a candidate
artifact before it becomes either trusted state or trusted meaning:

```text
candidate artifact
        ↓
governed semantic boundary
        ↓
accepted fact or trusted / accepted meaning
```

The two specializations remain distinct:

```text
Candidate Action
→ Accepted Fact

Candidate Claim
→ Trusted or Accepted Meaning
```

---

## Why This Matters for Agents

Traditional software systems usually execute paths written ahead of time by engineers.

Agentic systems may generate the action path dynamically.

That changes the risk model.

The system must not ask only:

> Did the action execute?

It must also ask:

> Should this candidate action have been allowed to change durable state?

This is especially important when multiple agents, workflows, or requests propose state changes at the same time.

Technical concurrency control can protect write ordering, but it does not fully decide whether competing candidate actions are semantically compatible.

---

## Why This Also Matters for Multi-Agent Workflows

A multi-agent system may share context, tools, sessions, and orchestration.

That is necessary, but not sufficient.

Shared context tells agents what was observed.

It does not automatically define what agents are allowed to claim, execute, or commit.

For commercial workflows, agents also need shared semantic contracts.

Example:

```text
Product A had stock at search time.
```

This does not automatically mean:

```text
Product A is purchasable at commit time.
```

A search result is not a purchase guarantee.

A recommendation is not a reservation.

A candidate checkout is not an accepted order.

---

## Why Bad State Can Become Future Context

In agentic systems, a bad action is not necessarily isolated.

If the system admits it into durable state, that action may become part of the environment future agents observe.

It can be stored, indexed, retrieved, summarized, reflected in analytics, or used by downstream workflows.

This creates a propagation risk:

```text
bad agent action
→ admitted durable state
→ future agent context
→ downstream decision
→ new state mutation
```

The goal of semantic admission is not to make agents perfect.

The goal is to prevent unvalidated outputs from becoming future context.

---

## Why Inferred Semantics Need Admission

Enterprise agents may infer business meaning from tables, dashboards, BI metrics, queries, semantic views, documentation, and usage patterns.

That can reduce human search burden.

But inferred meaning is not automatically accepted semantic truth.

```text
inferred semantic meaning ≠ accepted semantic contract
```

An agent may help propose a Compass layer, semantic contract, or business definition.

It should not authorize its own semantic truth.

A governed system should distinguish:

```text
semantic discovery
→ candidate semantic contract
→ evidence / lineage / conflict review
→ accepted semantic contract version
```

---

## Why Mutable State Is a Weak Boundary

Many early systems begin with CRUD because it is fast, familiar, and compatible with existing tools.

That is understandable.

However, agentic commerce introduces a stronger risk model.

When agents can dynamically call tools and mutate business state, the system must distinguish between:

```text
current mutable row
```

and:

```text
authoritative, auditable business fact
```

The current row may show what the state is now.

It may not explain who changed it, why it changed, what evidence supported the change, or whether the actor had business authority.

This section therefore treats mutable CRUD state as an important case study for Semantic Admission.

The public principle is:

```text
Current row state is not history.
Mutable state is not independent evidence.
Tool permission is not business authority.
Task completion is not truth preservation.
```

---

## Semantic Admission Taxonomy

This taxonomy answers:

> What class of semantic-governance problem is this?

The numbered reading order that follows answers a different question:

> What should I read next?

The taxonomy is navigational and conceptual. Where its labels are also described
in the glossary, they remain conceptual or taxonomy vocabulary and do not imply
equal implementation maturity or runtime contracts.

```text
SEMANTIC ADMISSION
│
├── Foundations
│
├── CQRS for AI Governance
│   ├── Effect-Side Governance
│   ├── Claim-Side Semantic Governance
│   └── Cross-Cutting Governance
│
└── Compass-Specific Mapping
```

### Foundations

Foundations establish shared candidate, truth, authority, evidence, and
admission vocabulary:

- [Semantic Admission for State-Changing AI Systems](./manifesto.md)
- [Semantic Admission Glossary](./glossary.md)
- [Candidate Actions Are Not Accepted Facts](./candidate_actions_are_not_accepted_facts.md)
- [CQRS for AI Governance](./cqrs_for_ai_governance.md) — the general
  semantic-authority split between effects and claims

### Effect-Side Governance

Primary question:

> **What may become true?**

This side is substantially grounded in the implemented Compass write-side
baseline and production-inspired repository paths.

#### Candidate / Admission Boundary

- [Admission Before Mutation](./admission_before_mutation.md)
- [An Agent Action Is a Hypothesis Until Admitted](./agent_action_as_hypothesis.md)

Failure: a generated or executable candidate is treated as accepted truth
without an independent semantic boundary.

#### Action Path / Authority

- [Action Path Admission](./action_path_admission.md)
- [Shared Workflow Is Not Shared Authority](./shared_workflow_is_not_shared_authority.md)
- [Model Autonomy Is Not Business Authority](./model_autonomy_vs_business_authority.public.md)
- [Input Guardrails Are Not Admission Boundaries](./input_guardrail_vs_admission_boundary_origin.public.md)

Failure: a technically reachable, executable, or apparently correct path is
mistaken for authorized business truth.

#### State-Evolution / Temporal Correctness

[Semantic Concurrency](./semantic_concurrency.md) asks whether a candidate that
was valid at state `S1` remains valid after an authoritative change produces
state `S2`.

```text
technically serialized
but semantically wrong
```

#### Retry / Intent Preservation

- [Retry Is Not Intent Preservation](./retry_is_not_intent_preservation.md)
- [Causal Failure Modeling](./causal_failure_modeling.md)

Failure: operational repetition or regenerated work no longer represents the
original semantic intent.

### Claim-Side Semantic Governance

Primary question:

> **What may be claimed as true?**

This side is currently more research-oriented. Its concerns include source
authority, evidence coverage, freshness and supersession, conflict resolution,
fact versus inference, provenance, uncertainty, and claim lifecycle or
invalidation.

Representative work includes:

- [Agent-Assisted Compass Layer Construction](./agent_assisted_compass_layer_construction.md)
- [From Generated Language to Source-Grounded Semantic Admission](../research/ai_governance/from_generated_language_to_source_grounded_semantic_admission.md)
- [Admitted Overviews, Cache Freshness, and Event-Driven Invalidation](../research/ai_governance/admitted_overview_cache_and_event_driven_invalidation.md)

[Multi-pass Suspicion Reasoning](../research/ai_governance/multi_pass_suspicion_reasoning.md)
is exploratory secondary work about candidate-answer review. These documents do
not establish production claim-admission mechanisms.

### Cross-Cutting Governance

Some failures cross the effect and claim boundaries rather than belonging
exclusively to one side:

```text
bad effect
→ future context
→ bad claim
```

```text
bad or stale claim
→ reasoning
→ proposed action
→ bad effect
```

Representative documents include:

- [Consensus Is Not Semantic Authority](./consensus_is_not_semantic_authority_rate_limiter.md)
  — uses a distributed rate-limiter remediation to show why legitimate
  collective selection still produces only a candidate for admission
- [Shared Context Is Not Shared Contract](./shared_context_is_not_shared_contract.md)
- [When Bad State Becomes Future Context](./bad_state_as_future_context.md)
- [Agent Pipelines as a Stochastic Process](./agent_pipelines_as_stochastic_process.md)

Their maturity varies by article. This category groups shared failure models;
it does not claim one implemented cross-cutting runtime.

The distinction between concurrency and agreement is especially important:

- **Semantic Concurrency:** state changed, so candidate meaning may have
  changed. It asks, “Is the candidate still valid?” Its failure shape is
  `technically serialized, but semantically wrong`.
- **Consensus / collective selection:** many agents agreed and selected a
  candidate that may still be invalid. It asks, “Did agreement establish
  semantic authority?” Its failure shape is `technically agreed, but
  semantically wrong`.

The two problems share Semantic Admission as a downstream correctness boundary,
but they are not the same failure mode.

### Shared Lower-Level Principle

The existing principle remains:

> **Technical success does not establish semantic correctness.**

A deeper architectural interpretation is:

> **Technical correctness at one layer does not grant semantic authority at the
> next boundary.**

Examples include:

```text
concurrency control
→ candidate
→ semantic revalidation
→ accepted fact
```

```text
multi-agent selection
→ selected candidate
→ semantic admission
→ accepted result
```

```text
retrieval / generation
→ candidate claim
→ evidence-grounded review
→ trusted meaning
```

These are related responsibility patterns, not a claim that one current Compass
runtime implements every path.

### Compass-Specific Mapping

[CQRS as a Lens for AI Governance](./cqrs_ai_governance_write_read_side.md)
maps the general thesis onto `Accepted History`, `Governed Source Corpus`,
projection and consumption modes, `SemanticOutcome`, `DecisionReceipt`, and
current implementation-maturity boundaries.

---

## Reading Order

Start with:

1. [manifesto.md](./manifesto.md)
2. [glossary.md](./glossary.md)
3. [candidate_actions_are_not_accepted_facts.md](./candidate_actions_are_not_accepted_facts.md)
4. [action_path_admission.md](./action_path_admission.md)
5. [admission_before_mutation.md](./admission_before_mutation.md)
6. [CQRS for AI Governance](./cqrs_for_ai_governance.md)
   — the general thesis that state-changing effects and trustworthy claims need
   separate semantic-authority and admission boundaries.
7. [CQRS as a Lens for AI Governance](./cqrs_ai_governance_write_read_side.md)
   — the Compass-specific mapping of that thesis across `Accepted History`,
   `Governed Source Corpus`, consumption modes, and current implementation
   maturity.
8. [semantic_concurrency.md](./semantic_concurrency.md)
   — state-evolution and temporal correctness after authoritative state changes.
9. [Consensus Is Not Semantic Authority](./consensus_is_not_semantic_authority_rate_limiter.md)
   — shows why collective selection can produce a candidate without granting
   it effect or claim authority.
10. [bad_state_as_future_context.md](./bad_state_as_future_context.md)
11. [Agent Pipelines as a Stochastic Process](./agent_pipelines_as_stochastic_process.md)
12. [agent_action_as_hypothesis.md](./agent_action_as_hypothesis.md)
13. [retry_is_not_intent_preservation.md](./retry_is_not_intent_preservation.md)
14. [Causal Failure Modeling: From Failure Classification to Failure Genesis](./causal_failure_modeling.md)
15. [shared_context_is_not_shared_contract.md](./shared_context_is_not_shared_contract.md)
16. [crud_is_not_a_safe_boundary_for_agentic_commerce.md](./crud_is_not_a_safe_boundary_for_agentic_commerce.md)
17. [Agent-Assisted Compass Layer Construction](./agent_assisted_compass_layer_construction.md)
18. [input_guardrail_vs_admission_boundary_origin.public](./input_guardrail_vs_admission_boundary_origin.public.md)

---

## Public Case Studies

These documents use illustrative scenarios to explain Semantic Admission
principles. They are conceptual case studies, not implementation contracts,
authority matrices, policy engines, schemas, or runtime commitments.

- [Shared Workflow Is Not Shared Authority](shared_workflow_is_not_shared_authority.md)
  — shows why agent coordination cannot transfer authority to create accepted
  facts and why search-time evidence is not commit-time truth.
- [Model Autonomy Is Not Business Authority](model_autonomy_vs_business_authority.public.md)
  — separates model-generated proposals, tool capability, institutional
  authority, progressive autonomy, and admitted business action.
- [Consensus Is Not Semantic Authority](consensus_is_not_semantic_authority_rate_limiter.md)
  — shows why distributed agents may make a reasonable collective operational
  selection that still violates an authoritative business contract.

---

## Glossary Structure

The glossary is grouped into five areas:

1. **System Truth & Admission Core**  
   Defines candidate artifacts, accepted facts, semantic admission, admission boundaries, durable state, and core correctness language.

2. **Technical & Semantic Concurrency Control**  
   Separates write-ordering problems from meaning-level conflicts between candidate actions.

3. **Storage, Authority & Evidence Boundaries**  
   Defines why mutable state, CRUD requests, truth sources, business authority, and audit evidence matter for agentic systems.

4. **Multi-Agent Semantic Contracts & Governance**  
   Defines shared context, shared semantic contracts, semantic escalation, commit-time truth, intent drift, and workflow-level correctness.

5. **CQRS for AI Governance & Cross-Cutting Principles**
   Defines conceptual vocabulary supporting effect-side versus claim-side
   governance, Delegation and Influence boundaries, collective selection, and
   cross-boundary principles without creating runtime contracts.

---

## Relationship to the Main Project

The main project grounds part of this framing in implemented and
production-inspired behavior. That grounding is primarily the effect-side
state-change boundary, together with bounded evidence, projection, snapshot,
and replay-validation foundations.

In the full Compass system:

- candidate events are validated before entering `Accepted History`
- `Accepted History` is treated as the durable event authority
- idempotency and concurrency are treated as separate boundaries
- projections are checked against `Accepted History`
- snapshots are derived, discardable, traceable, and subordinate
- replay validation is used to detect read-side semantic drift
- retry-like situations are classified by semantic meaning, not collapsed into one generic retry category

The implemented write-side specialization can be summarized as:

```text
candidate output / action
→ candidate event
→ validation / admission
→ accepted fact
→ Accepted History
```

This path is a concrete specialization within the broader Semantic Admission
taxonomy, not the whole taxonomy.

The completed Stage 4 architecture adds separately owned current-response and
bounded same-request re-invocation authority without turning Semantic Admission
into one mandatory Stage 4 pipeline. For autonomous downstream consequences,
[ADR 0029 — Stage 4C+ Exists at the Automation Boundary](../adr/0029_stage_4c_plus_exists_at_the_automation_boundary.md)
explains when later consequence-specific authority must become explicit.
Semantic Admission may itself govern a state-changing candidate's transition
into authoritative state; admission remains distinct from execution, and later
consequence-specific authority applies only where the consequence requires it.

The current maturity boundary is:

```text
Implemented / production-inspired Compass baseline
→ primarily effect-side state-change correctness
→ plus bounded evidence / projection foundations

Claim-side semantic governance
→ conceptual and research-oriented
→ no production claim-admission runtime is asserted

Cross-cutting taxonomy
→ conceptual grouping of failure modes
→ not one implemented cross-cutting runtime
```

This folder does not replace the implementation notes or ADRs. The
Compass-specific CQRS bridge records the more detailed mapping between this
taxonomy and current project terminology and maturity.

---

## Relationship to Research Notes

Some related ideas are exploratory and are not part of the current implementation roadmap.

See:

- [`../research/ai_governance/`](../research/ai_governance/)

The research notes include adjacent ideas such as
[probabilistic agency inside deterministic workflows](../research/ai_governance/probabilistic_agency_inside_deterministic_business_workflows.md),
source-grounded generation, overview cache admission, and multi-pass answer
review.

Those notes are related to semantic admission, but they are intentionally separated from this public conceptual entry point.

---

## Summary

Semantic Admission governs the boundary between a candidate artifact and the
trusted semantic status granted to it.

The two primary specializations are:

```text
Candidate Action
→ Accepted Fact

Candidate Claim
→ Trusted / Accepted Meaning
```

Their maturity is asymmetric. Effect-side governance is the historical and
implemented core of Compass. Claim-side governance is the broader conceptual
and research-oriented extension. Cross-cutting governance describes failure
modes that can affect both boundaries; it does not identify one implemented
runtime.

The CQRS framing makes the top-level distinction concise:

```text
STATE-CHANGE / EFFECT SIDE
What may become true?

CLAIM SIDE
What may be claimed as true?
```

The original Semantic Admission principles remain:

```text
A candidate action is not an accepted fact.

Bad state can become future context.

Shared context is not shared contract.

Current row state is not history.

Task completion is not truth preservation.

Tool permission is not business authority.

Inferred semantic meaning is not an accepted semantic contract.
```

A cross-cutting principle now adds:

> **Agreement does not create semantic authority.**

Collective selection may choose a candidate, but:

```text
collective selection
≠
semantic admission
```

The deeper shared architectural principle is:

> **Technical correctness at one layer does not grant semantic authority at the
> next boundary.**

Together, these principles explain why AI systems need explicit, separately
owned boundaries for what may become accepted fact and what may become trusted
or accepted meaning.
