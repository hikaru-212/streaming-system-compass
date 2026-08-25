# Probabilistic Agency Inside Deterministic Business Workflows

## Where Should AI Be Allowed to Influence Business Truth?

[← Back to AI Governance Index](README.md)

**Recorded on:** 2026-08-26

## Research Status

Public research / problem-boundary note.

This document frames governance questions for probabilistic agency inside
deterministic business workflows.

It is not accepted architecture, a production runtime contract, a universal
AI-governance protocol, or an implementation commitment.

---

## 1. Purpose

AI systems are increasingly inserted into workflows that were originally built
around deterministic business rules.

The deepest question is not simply:

> Can an AI make the wrong decision?

It appears earlier:

> **Where should probabilistic AI be allowed to enter a workflow whose
> authoritative semantics are otherwise deterministic?**

Many business systems already resolve important facts through:

- authoritative records;
- explicit contracts;
- state machines;
- deterministic policies;
- transaction rules;
- domain invariants.

When those mechanisms already determine the answer, adding probabilistic
judgment may not add intelligence.

It may replace known authority with interpretation.

This note develops a compact model for separating:

```text
Delegation
!=
Influence
!=
Semantic Admission
```

and for preserving the broader distinction:

```text
probabilistic participation
!=
business authority
```

---

## 2. Authority-Resolved vs Judgment-Required

Consider two different questions.

### Authority-Resolved

```text
Who is the contracted vendor?
```

Suppose the authoritative contract system says:

```text
vendor = Bob
```

Then the correct path is:

```text
authoritative source
        ↓
deterministic lookup
        ↓
Bob
```

Asking several agents to vote on another answer would create an unnecessary
probability boundary.

The failure would occur before the vote:

> **An already-authoritative fact was delegated to probabilistic judgment.**

### Judgment-Required

Now consider:

```text
How risky is this loan applicant?
```

The system may know deterministic facts:

```text
income
credit score
debt ratio
payment history
employment history
```

but the overall assessment may still require:

- interpretation;
- prediction;
- incomplete-evidence handling;
- qualitative judgment;
- scenario analysis.

AI involvement may be reasonable here.

The useful distinction is not:

```text
simple
vs
complex
```

It is:

```text
authority already resolves the answer
vs
judgment remains unresolved
```

---

## 3. Do Not Probabilize What the System Already Knows

A useful principle is:

> **Do not probabilize what the authoritative system already knows how to
> decide deterministically.**

If the system already has:

```text
contracted_vendor = Bob
```

then:

```text
Which vendor should receive payment?
```

should not become a model-ranking problem.

Likewise, if the system already has:

```text
payment_authorized = true
inventory_reserved = true
order_accepted = true
```

and the business rule is:

```text
payment_authorized
AND inventory_reserved
AND order_accepted
→ SHIP
```

then shipping does not require an AI opinion.

AI should participate where uncertainty genuinely remains.

It should not re-litigate authority that already exists.

---

## 4. Local Determinism Is Not End-to-End Determinism

A deterministic business rule may be written as:

```text
y = f(x)
```

with:

```text
same x
→ same y
```

If `x` is also produced deterministically, the end-to-end behavior may remain
deterministic.

But suppose:

```text
x = g_AI(context)
```

where `g_AI` is probabilistic.

Then:

```text
y = f(g_AI(context))
```

Even if:

```text
f = deterministic
```

the composition:

```text
f ∘ g_AI
```

need not be.

Therefore:

> **Local deterministic business logic does not guarantee end-to-end
> deterministic business semantics when probabilistic components control its
> inputs, premises, or execution path.**

This is the central composition problem.

A state machine can be perfectly deterministic while the world presented to
that state machine was shaped probabilistically.

---

## 5. AI Does Not Need Direct Mutation Authority to Matter

A common safety question is:

> Can the agent directly mutate protected state?

That question is necessary, but incomplete.

Suppose:

```text
DirectPermission(SearchAgent, InventoryMutation) = DENIED
```

while the workflow still permits:

```text
SearchAgent
→ request replenishment
→ privileged inventory workflow
→ inventory mutation
```

The agent never directly performs the protected mutation.

It only selects or activates a workflow.

Yet the authoritative world changes.

Therefore:

```text
direct mutation authority
!=
reachable business influence
```

The important question becomes broader:

> **What parts of the decision environment may probabilistic agency influence,
> including authority-bearing paths it can activate indirectly?**

This is why direct permission alone is not a complete model of agent influence.

For the broader workflow-authority problem, see
[Shared Workflow Is Not Shared Authority](../../semantic_admission/shared_workflow_is_not_shared_authority.md).

---

## 6. Three Governance Boundaries

The problem becomes clearer when split into three questions.

### Boundary 1 — Delegation

> **Should AI be deciding this at all?**

A question is **authority-resolved** when the answer already follows from:

- authoritative data;
- contractual facts;
- deterministic rules;
- explicit state-machine semantics;
- hard domain invariants.

A question is **judgment-required** when meaningful ambiguity remains and the
answer genuinely requires:

- interpretation;
- prediction;
- uncertain evidence;
- qualitative evaluation;
- ambiguity resolution.

The Delegation Boundary decides whether probabilistic judgment belongs in the
problem at all.

### Boundary 2 — Influence

Even when AI may participate:

> **What may it influence?**

Possible influence surfaces include:

```text
inputs
sources
evidence
workflow selection
tool selection
routing
preconditions
privileged services
candidate construction
```

This boundary is more subtle than direct permission.

For example:

```text
AI cannot authorize shipment
```

does not imply:

```text
AI cannot influence whether shipment preconditions become true
```

The Influence Boundary therefore constrains what the agent may select, alter,
construct, route, or activate while producing a candidate.

### Boundary 3 — Semantic Admission

After a candidate exists:

> **May this candidate cross the semantic boundary?**

For a state-changing candidate:

```text
Candidate Action / Event
        ↓
semantic validation
        ↓
authority / evidence / current state
        ↓
ADMIT or REJECT
        ↓
Accepted Fact / Accepted History
```

For a claim:

```text
Candidate Claim
        ↓
evidence-grounded review
        ↓
ADMIT or REJECT
        ↓
Trusted / Accepted Meaning
```

The origin of the candidate does not determine its authority.

---

## 7. The Three-Boundary Model

```text
                    BUSINESS PROBLEM
                           │
                           ▼
                ┌─────────────────────┐
                │ Delegation Boundary │
                │                     │
                │ Should AI decide    │
                │ this at all?        │
                └──────────┬──────────┘
                           │
                           ▼
                  Probabilistic Agent
                           │
                           ▼
                ┌─────────────────────┐
                │ Influence Boundary  │
                │                     │
                │ What premises,      │
                │ evidence, tools,    │
                │ or paths may AI     │
                │ affect?             │
                └──────────┬──────────┘
                           │
                           ▼
             allowed sources / evidence
             tools / paths / preconditions
                candidate construction
                           │
                           ▼
                       Candidate
                           │
                           ▼
                ┌─────────────────────┐
                │ Semantic Admission  │
                │                     │
                │ May this candidate  │
                │ become trusted?     │
                └──────────┬──────────┘
                           │
                           ▼
                 Trusted / Accepted Result
```

These boundaries answer different questions.

They should not be collapsed into one generic "AI safety" layer or one
universal evaluator.

```text
Delegation
!=
Influence
!=
Semantic Admission
```

Coherent composition does not require one shared decision surface.

---

## 8. Facts About AI Are Not Automatically Facts About the Business World

Probabilistic output can be represented precisely without turning it directly
into business truth.

For example:

```text
AI risk assessment = 0.73
```

may legitimately produce:

```text
LoanRiskAssessmentProduced(
    applicant_id = 123,
    score = 0.73,
    model = X
)
```

This records a deterministic fact about the workflow:

> A particular model produced this assessment.

It does not mean:

```text
LoanApproved
```

A governed path may instead be:

```text
AI assessment
        ↓
RiskAssessmentProduced
        ↓
policy / evidence / approval rules
        ↓
LoanApproved
```

Similarly:

```text
AgentSuggestedVendor(Alice)
!=
VendorSelected(Alice)
```

and:

```text
3 agents agreed on Alice
!=
PaymentAuthorized(Alice)
```

A fact about what the AI produced is not automatically a fact about the
business world.

---

## 9. Relationship to Collective Selection

If a problem legitimately requires judgment, multiple agents may still be
useful.

They may independently observe a system and collectively select one candidate:

```text
distributed observations
        ↓
agent proposals
        ↓
voting / aggregation / debate
        ↓
selected candidate
```

That answers:

> Which candidate did the group select?

It does not answer:

> May this candidate become trusted business truth?

Therefore:

```text
selection
!=
admission
```

The selected result remains a candidate.

For the stronger operational example, see
[Consensus Is Not Semantic Authority](../../semantic_admission/consensus_is_not_semantic_authority_rate_limiter.md).

---

## 10. Relationship to Other Compass Boundaries

This problem is upstream of several other Compass concerns.

### Semantic Concurrency

Semantic Concurrency asks whether a candidate that was valid against `S1`
remains valid after authoritative state changes to `S2`.

That is different from asking why probabilistic agency was allowed to shape the
candidate or workflow in the first place.

The two can compose:

```text
AI produces candidate at S1
        ↓
authoritative state changes to S2
        ↓
candidate becomes stale
        ↓
revalidation required
```

But the causal questions remain distinct.

See
[Semantic Concurrency](../../semantic_admission/semantic_concurrency.md).

### Authority Composition

A limited actor may indirectly reach a protected effect through privileged
workflow components.

The Influence Boundary asks the upstream question:

> Why may the probabilistic actor choose or activate that authority-bearing
> path?

This is one way broad probabilistic influence can become reachable business
authority.

### Effect Side vs Claim Side

CQRS for AI Governance separates:

```text
Effect Side
What may become true?
```

from:

```text
Claim Side
What may be claimed as true?
```

Delegation and Influence appear earlier:

```text
Business Problem
        ↓
Delegation
        ↓
Influence
        ↓
Candidate
        ↓
Effect-side or Claim-side governance
```

See
[CQRS for AI Governance](../../semantic_admission/cqrs_ai_governance_write_read_side.md).

---

## 11. Relationship to ADR 0029

This note asks:

```text
Should probabilistic judgment enter?
What may it influence?
May the resulting candidate become trusted?
```

[ADR 0029 — Stage 4C+ Exists at the Automation Boundary](../../adr/0029_stage_4c_plus_exists_at_the_automation_boundary.md)
answers a different, later automation question:

> When downstream consequences move from human judgment into autonomous
> machinery, what consequence-specific authority must become explicit before
> controlled execution?

ADR 0029 does not replace Delegation, Influence, or Semantic Admission.

Likewise, those three boundaries do not imply a mandatory Stage 4C or Stage 4E
path for every AI-produced candidate.

Preserve:

```text
delegation
!=
influence
!=
semantic admission
```

and:

```text
evidence
!=
proposal
!=
authority
!=
execution
```

---

## 12. A Safer Architecture

The unsafe pattern is:

```text
authoritative fact already exists
        ↓
AI reinterprets it
        ↓
AI-generated answer becomes business input
        ↓
deterministic system acts on that answer
```

or:

```text
AI goal
        ↓
AI chooses tools and paths
        ↓
AI changes business preconditions
        ↓
deterministic rule now passes
```

The final deterministic transition may look locally correct while the path that
created its premises was not sufficiently governed.

A safer architecture is:

```text
authoritative facts / deterministic rules
        │
        ├────────────── deterministic resolution
        │
        └── unresolved ambiguity / judgment
                    ↓
              Delegation allows AI
                    ↓
              Influence Boundary
                    ↓
               Candidate Result
                    ↓
              Semantic Admission
                    ↓
            Trusted / Accepted Result
```

AI participates where uncertainty genuinely remains.

It does not replace authority that already exists.

---

## 13. AI Should Resolve Ambiguity, Not Re-Litigate Authority

> **AI should resolve ambiguity, not re-litigate deterministic authority.**

AI may be useful for:

- language interpretation;
- incomplete evidence;
- prediction;
- qualitative judgment;
- exploratory analysis;
- candidate generation.

But when the authoritative system already knows:

```text
who
what
whether
when
under which rule
```

the AI should not invent a competing answer.

This does not make deterministic business logic sufficient by itself.

The stronger end-to-end rule remains:

> **A deterministic state machine is not enough if probabilistic agency controls
> the premises or workflow paths that reach it.**

---

## 14. Non-Goals

This framing does not claim that:

- AI should never participate in business workflows;
- all business decisions are deterministic;
- human judgment is deterministic;
- probabilistic models cannot provide useful evidence;
- every AI output needs deterministic proof;
- multi-agent systems are inherently unsafe;
- deterministic state machines alone guarantee business correctness;
- Semantic Admission replaces workflow design;
- Delegation, Influence, and Admission form one universal runtime protocol;
- Compass should control every application-layer decision.

The narrower claim is:

> **Probabilistic agency should not silently inherit control over business
> premises and paths merely because it participates in the workflow.**

---

## 15. Open Research Questions

### Delegation

- How can a system determine that a question is already authority-resolved?
- When should deterministic policy take precedence over model judgment?
- How should mixed deterministic/judgment workflows be partitioned?

### Influence

- Which tools may an agent invoke?
- Which authoritative sources may it modify?
- Which workflow branches may it activate?
- May an agent alter a precondition used to validate its own candidate?
- How should reachable business influence be computed across workflow composition?

### Evidence and Admission

- Which AI-produced artifacts are observations, claims, or business facts?
- When may AI-generated evidence influence deterministic admission?
- How should provenance distinguish authoritative facts from model interpretation?
- Which decisions require revalidation against current state?

### End-to-End Correctness

- How can a system show that deterministic business semantics survived
  probabilistic orchestration?
- How can Delegation, Influence, and Admission compose coherently while
  preserving distinct owners and evaluators?
- How should changes to agent capabilities alter the reachable business-effect
  surface?

---

## 16. Compact Decision Rule

```text
Business question
        ↓
Is the answer already determined by authoritative facts
or deterministic rules?
        │
        ├── YES
        │     ↓
        │ deterministic resolution
        │
        └── NO
              ↓
       Does the problem genuinely require
       interpretation / prediction / judgment?
              │
              ├── NO
              │     ↓
              │ keep AI out of the decision
              │
              └── YES
                    ↓
               AI may participate
                    ↓
              Influence Boundary
                    ↓
               candidate result
                    ↓
              governed admission
```

This is a problem boundary, not a complete implementation design.

---

## 17. Final Principle

The deepest question is not:

> Can AI perform this task?

It is:

> **Should probabilistic agency be allowed to influence the authority path that
> decides this business fact?**

The strongest current principles are:

> **Do not probabilize what the authoritative system already knows how to decide
> deterministically.**

> **AI should resolve ambiguity, not re-litigate deterministic authority.**

> **A deterministic state machine is not enough if probabilistic agency controls
> the premises or workflow paths that reach it.**

The broader research question is:

> **Where may probabilistic agency influence the premises and control paths of
> deterministic business workflows without turning deterministic business
> semantics into probabilistically governed outcomes?**
