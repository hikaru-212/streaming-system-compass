# CQRS for AI Governance

[← Back to Semantic Admission Index](README.md)

## 1. Purpose

Traditional CQRS separates responsibility for commands that may change state
from responsibility for queries that return representations.

In AI-enabled systems, that structural separation exposes two further
governance responsibilities: deciding what may enter authoritative state and
deciding what may be presented as a trustworthy claim.

These authorities require separate evidence and admission boundaries.

The distinction can be summarized as:

```text
STATE-CHANGE / EFFECT-SIDE GOVERNANCE
What may become true?

CLAIM-SIDE SEMANTIC GOVERNANCE
What may be claimed as true?
```

This is a conceptual interpretation of the separation exposed by CQRS. It does
not claim that CQRS itself defines semantic authority, claim admission, or AI
governance.

The shared principle is:

> **Technical success does not establish semantic correctness.**

For multi-agent systems, a second principle is equally important:

> **Agreement does not create semantic authority.**

---

## 2. CQRS Before AI

In conventional CQRS:

- a command expresses an intent that may change state;
- a query returns a representation without intentionally changing state; and
- the responsibilities, models, and scaling needs of those paths may differ.

This separation can make ownership and execution boundaries clearer. It does
not, by itself, prove that a command is valid, that a representation is
complete, or that a natural-language conclusion drawn from queried data is
true.

CQRS also does not require Event Sourcing. An architecture may separate command
and query responsibilities while using many different persistence and
integration designs.

AI makes the limits of the conventional separation more visible. An AI system
may participate in a command path by proposing an action. It may also consume
queried data or other sources and produce an interpretation that a person or
another agent treats as knowledge.

Those are different semantic risks.

---

## 3. AI Adds a Semantic-Authority Separation

### State-Change / Effect-Side Governance

The primary question is:

> **What may become true?**

A general state-changing path is:

```text
proposed action
      ↓
candidate action / intended effect
      ↓
semantic validation / authority check
      ↓
effect admission
      ↓
authoritative state change
```

The AI may propose an action, but proposal and tool access do not give the AI
authority to make the action part of trusted state.

### Claim-Side Semantic Governance

The primary question is:

> **What may be claimed as true?**

A general claim-producing path is:

```text
governed evidence sources
      ↓
AI observation / interpretation
      ↓
candidate claim
      ↓
claim review / admission
      ↓
trusted claim
```

Claim production may occur downstream of query or read paths, but it is not the
same operation as a conventional deterministic read model or projection. A
query can return data successfully while an AI still misinterprets the data,
misses relevant sources, or makes an inference the evidence does not justify.

```text
                 CQRS VIEW OF AI SEMANTIC GOVERNANCE

┌──────────────────────────────────────────────┬──────────────────────────────────────────────┐
│ COMMAND / EFFECT SIDE                        │ QUERY / CLAIM SIDE                           │
├──────────────────────────────────────────────┼──────────────────────────────────────────────┤
│ Core question                                │ Core question                                │
│ What may become true?                        │ What may be claimed as true?                 │
├──────────────────────────────────────────────┼──────────────────────────────────────────────┤
│ Governed object                              │ Governed object                              │
│ State-changing action or intended effect     │ Semantic claim or interpretation             │
├──────────────────────────────────────────────┼──────────────────────────────────────────────┤
│ Failure mode                                 │ Failure mode                                 │
│ Invalid state admission                      │ Unsupported or overstated claim              │
├──────────────────────────────────────────────┼──────────────────────────────────────────────┤
│ Evidence / decision basis                    │ Evidence / decision basis                    │
│ Current state, invariants, history, authority│ Grounding, source status, coverage, inference│
├──────────────────────────────────────────────┼──────────────────────────────────────────────┤
│ Defense goal                                 │ Defense goal                                 │
│ Protect authoritative durable state          │ Protect trustworthy downstream meaning       │
└──────────────────────────────────────────────┴──────────────────────────────────────────────┘
```

The symmetry is in the location of the semantic boundary, not in the
implementation of the boundary. Effect-side governance asks whether an action
may become authoritative state; claim-side governance asks whether a claim may
become trusted meaning. They are structurally parallel but asymmetric in their
candidates, evidence, authority models, failure modes, results, and mechanisms.

---

## 4. Agreement Does Not Create Semantic Authority

Multi-agent systems may use voting, ranking, debate, aggregation, or quorum-like
selection to choose among proposals. These mechanisms can be useful, but they
answer a selection question:

```text
Which candidate did the group choose?
```

They do not necessarily answer the semantic question:

```text
Should the selected candidate be trusted or admitted?
```

Therefore:

```text
selection ≠ admission
agreement ≠ authority
consensus ≠ semantic truth
```

Classical distributed consensus primarily establishes agreement about a value,
history, or order under a protocol. It is not ordinarily a proof that the
chosen business transition or natural-language claim is semantically correct.

AI-agent voting is not automatically equivalent to distributed consensus. It
simply makes the separation vivid: several agents may reason differently, rely
on the same flawed evidence, or agree on the same invalid result.

---

## 5. Effect-Side Example: A Majority Selects an Invalid Transition

Suppose the current business state is:

```text
Current state: PAID

Allowed:
PAID → SHIPPED
PAID → REFUNDED

Invalid:
PAID → DELIVERED
```

Five agents propose the next action:

```text
Agent A → DELIVERED
Agent B → DELIVERED
Agent C → DELIVERED
Agent D → SHIPPED
Agent E → SHIPPED
```

A `3 / 5` majority selects `DELIVERED`.

The vote succeeded, but the selected transition is still invalid. The system
must not convert vote count into business authority.

```text
multi-agent selection / quorum
        ↓
candidate action
        ↓
effect-side semantic admission
        ↓
ADMIT or REJECT
```

The admission boundary checks the current state, applicable authority, and
business invariants. It rejects `PAID → DELIVERED` even though most agents
selected it.

> Consensus or voting may select a candidate. It does not grant that candidate
> semantic authority.

---

## 6. Claim-Side Example: A Majority Repeats an Unsupported Claim

Now suppose five agents assess whether a system is compliant:

```text
Agent A → "The system is compliant."
Agent B → "The system is compliant."
Agent C → "The system is compliant."
Agent D → "The system is not compliant."
Agent E → "The system is not compliant."
```

The three agreeing agents may all rely on the same stale policy, incomplete
retrieval, non-authoritative document, or unsupported inference. Repetition
does not repair the evidence gap.

```text
majority agreement on a claim
≠
evidence-justified truth
```

The safer path is:

```text
multi-agent aggregation
        ↓
candidate claim
        ↓
claim-side semantic review / admission
        ↓
trusted claim or rejection
```

Review asks whether the available evidence supports the claim for its stated
scope and time. It may consider source authority, coverage, freshness,
conflict, provenance, inference, and uncertainty rather than vote count alone.

> Agreement can be evidence, but it is not authority by itself.

---

## 7. Effect Authority and Claim Authority

This thesis uses two conceptual labels. They are not proposed as universal
runtime or repository vocabulary.

### Effect Authority

**Effect Authority** is authority to cause or admit a state-changing
consequence.

It may depend on the actor, current state, business rules, independent evidence,
scope, reversibility, and the boundary responsible for admission.

### Claim Authority

**Claim Authority** is authority under which a claim may be published,
preserved, or relied upon as trustworthy meaning.

It may depend on source authority, evidence coverage, freshness, provenance,
scope, conflict resolution, inference quality, uncertainty, and the consumer
that will rely on the claim.

The basic distinctions are:

```text
tool access ≠ effect authority
source access ≠ claim authority
majority agreement ≠ either authority
```

The two sides are related but asymmetric.

| Dimension | Effect-Side Governance | Claim-Side Governance |
|---|---|---|
| Candidate | Proposed action or intended effect | Proposed assertion or interpretation |
| Evidence | Current state, invariants, actor authority, independent operational evidence | Source authority, coverage, freshness, conflict, provenance, inference |
| Main failure | Invalid change becomes authoritative state | Unsupported claim becomes trusted meaning |
| Consequence | Durable or external state change | Human or agent reliance, communication, or later action |
| Mechanism | State- and authority-aware admission | Evidence- and scope-aware claim review |

One generic validator cannot be assumed to govern both. Each boundary needs an
evidence model and authority model appropriate to its candidate and
consequences.

---

## 8. Why Technical Success Is Insufficient

On the effect side:

```text
agents reached a majority
tool call succeeded
transaction committed
workflow completed
```

does not establish:

```text
the state change was semantically valid and authorized
```

On the claim side:

```text
retrieval succeeded
several agents agreed
generation completed
citations were attached
```

does not establish:

```text
the claim is justified by current, relevant, authority-qualified evidence
```

Execution mechanisms report what happened operationally. Semantic admission
decides whether the result is eligible to become trusted state or trusted
meaning.

---

## 9. The Governance Loop

Effect governance and claim governance remain separate boundaries, but they may
participate in one AI governance loop:

```text
governed evidence sources
        ↓
AI observation / interpretation
        ↓
candidate claim
        ↓
claim-side review / admission
        ↓
trusted claim
        ↓
human or agent reasoning
        ↓
proposed action
        ↓
effect-side admission
        ↓
authoritative state change
        ↓
source updates / invalidation signals
```

The arrows do not transfer authority automatically:

- A trusted claim is evidence for reasoning, not automatic action
  authorization.
- Effect-side admission must independently revalidate current state and
  authority.
- An admitted state change is not automatically authoritative for every later
  claim or scope.
- Agent-generated claims must not become circular evidence for their own
  proposed effects.

The loop is therefore not one continuous trust channel. It is a sequence of
candidate-producing steps separated by distinct governance boundaries.

---

## 10. Related Semantic Admission Work

Concrete effect-side examples include:

- [Candidate Actions Are Not Accepted Facts](candidate_actions_are_not_accepted_facts.md)
  — the foundational candidate-versus-accepted distinction.
- [Admission Before Mutation](admission_before_mutation.md)
  — why the state-changing boundary must precede durable mutation.
- [Shared Workflow Is Not Shared Authority](shared_workflow_is_not_shared_authority.md)
  — how indirect agent-controlled paths can launder authority.
- [Model Autonomy Is Not Business Authority](model_autonomy_vs_business_authority.public.md)
  — why action generation, tool capability, and institutional authority remain
  separate.

Related claim-side research includes:

- [From Generated Language to Source-Grounded Semantic Admission](../research/ai_governance/from_generated_language_to_source_grounded_semantic_admission.md)
  — source grounding, evidence conflict, and fact-versus-inference review.
- [Admitted Overviews, Cache Freshness, and Event-Driven Invalidation](../research/ai_governance/admitted_overview_cache_and_event_driven_invalidation.md)
  — why previously accepted meaning may require freshness-aware revalidation.
- [Agent-Assisted Compass Layer Construction](agent_assisted_compass_layer_construction.md)
  — treating inferred semantic contracts as candidates rather than
  self-authorized truth.

[Multi-pass Suspicion Reasoning](../research/ai_governance/multi_pass_suspicion_reasoning.md)
is secondary exploratory reading about explicit candidate-answer review. Agent
self-review can surface useful evidence, but it is not sufficient claim
authority by itself.

For how this general distinction maps onto project-specific concepts such as
Accepted History, Governed Source Corpus, projection, `SemanticOutcome`,
`DecisionReceipt`, and implementation maturity, see
[CQRS as a Lens for AI Governance](cqrs_ai_governance_write_read_side.md).

---

## 11. Non-Goals

This article does not claim that:

- CQRS itself solves AI governance;
- conventional query models perform claim admission;
- AI-mediated claim interpretation is a deterministic CQRS projection;
- multi-agent voting is equivalent to distributed consensus;
- distributed consensus guarantees business correctness;
- majority agreement establishes truth or authority;
- claim authority and effect authority are identical;
- Event Sourcing is required;
- Compass is required to apply this conceptual distinction;
- all AI outputs need deterministic validation;
- all claims can be formally proven; or
- one admission mechanism can automatically govern both sides.

The article defines a conceptual separation, not a production architecture or
implementation contract.

---

## 12. Final Principle

Traditional CQRS separates command and query responsibilities.

When AI participates in both state-changing and knowledge-producing paths, the
separation exposes two semantic-authority questions:

> **What may become true?**

> **What may be claimed as true?**

Technical success answers neither question by itself.

Multi-agent agreement answers neither question by itself.

Trustworthy AI systems therefore need distinct admission boundaries for
authoritative state changes and for claims that people or downstream agents may
rely upon.
