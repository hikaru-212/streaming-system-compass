# CQRS as a Lens for AI Governance

## Write-Side Admission and Claim-Side Correctness Around Authoritative Truth

[← Back to Semantic Admission Index](README.md)

## 1. Purpose

This note uses CQRS as an architectural lens for two related semantic
correctness problems.

The central idea is simple:

> A technically successful operation is not sufficient evidence of semantic
> correctness.

For state-changing paths, the question is:

> What may become true?

For AI-mediated interpretation, the emerging research question is:

> What may be claimed as true?

These are related governance boundaries, but they are asymmetric. They have
different authority domains, evidence requirements, failure modes, maturity,
and runtime responsibilities.

CQRS does not solve AI governance. The lens is useful because it keeps
state-changing admission separate from downstream consumption, while also
showing that AI-mediated interpretation introduces a correctness concern that
ordinary deterministic projection does not answer.

---

## 2. Status and Maturity

This is a conceptual architecture bridge inside the Semantic Admission
documentation. It is not an ADR, an implementation specification, a production
claim-governance contract, or a replacement for existing Compass boundaries.

The current maturity is:

```text
Write-side domain / transition validation and Accepted History admission
→ implemented Compass baseline, including durable PostgreSQL paths

Deterministic projection, replay / rebuild comparison,
and bounded read-side / snapshot SemanticOutcome mapping
→ implemented repository baselines;
  projections and snapshots remain derived

SemanticOutcome and DecisionReceipt
→ implemented bounded interpretation and governance-evidence foundations;
  neither is Runtime Decision Authority

Stage 4C Runtime Decision Authority
→ completed / closed bounded current-response authority;
  this note does not implement or replace it

Stage 4D Strategy Selection Authority
→ responsibility retained;
  implementation deferred under ADR 0028

Stage 4E Same-Request Re-Invocation Authority
→ completed / closed bounded authority for at most one fresh invocation
  under the reviewed evidence profiles;
  not generic retry governance

AI-mediated source reconstruction and claim admission
→ emerging conceptual and research direction;
  no production claim-admission runtime exists

Production claim-admission runtime
→ not implemented
```

Document-truth reconstruction is an experimental research direction and is not
part of the current `main` implementation baseline.

The completed Stage 4 responsibilities remain separate and non-linear:

```text
technical evidence
→ SemanticOutcome

SemanticOutcome
→ optional selected DecisionReceipt evidence

applicable live evidence
→ Stage 4C current-response authority

eligible completed-invocation evidence
→ Stage 4E same-request re-invocation authority

Stage 4D
→ HOW selection only when an already-authorized operation
  has multiple eligible strategies

authorization
!=
execution
```

[ADR 0029](../adr/0029_stage_4c_plus_exists_at_the_automation_boundary.md)
owns the broader automation-boundary decision. This bridge does not turn the
responsibilities into one mandatory runtime pipeline.

`SemanticOutcome` is a typed semantic interpretation of technical evidence. It
is not admission, authorization, policy, or an execution command.

`DecisionReceipt` preserves selected durable governance evidence. It is not
Runtime Decision Authority, authorization, or execution.


---

## 3. The Core Model

At the conceptual level, **Authoritative Truth** names the role played by
information that a system permits consumers to rely on. The concrete authority
domains remain distinct:

```text
Authoritative Truth
→ conceptual role / abstraction

Accepted History
→ Compass's durable event authority

Governed Source Corpus
→ claim-side evidence domain whose sources may differ in authority,
  freshness, supersession status, scope, or conflict
```

A document corpus is not automatically `Accepted History`. A retrieved document
is not automatically authoritative. Source status must be established for the
claim and scope under review.

Within the implemented event path, the existing vocabulary remains precise:

- `Candidate Artifact` is the broad category for a proposed output, action,
  event, claim, plan, or generated object.
- `Candidate Action` is a proposed action before formal acceptance.
- `Candidate Event` is the concrete event-shaped proposal presented to the
  current Compass validation and admission path.
- An `Accepted Fact` is a state change formally admitted and durably committed.
- `Accepted History` is the durable sequence the system treats as event
  authority.
- Read models and projections are derived from that authority; they are not a
  replacement authority.

The two high-level paths are:

```text
WRITE-SIDE GOVERNANCE

proposed action
      ↓
candidate event
      ↓
domain / transition validation
      ↓
concurrency / persistence admission
      ↓
Accepted History
```

```text
CLAIM-SIDE RESEARCH DIRECTION

Governed Source Corpus
      ↓
observation / retrieval
      ↓
source-status resolution
      ↓
interpretation / inference
      ↓
candidate claim
      ↓
claim review / admission
      ↓
trusted or accepted meaning
```

The common principle is:

> Technical success does not establish semantic correctness.

---

## 4. Write-Side Semantic Admission

The implemented Compass baseline primarily protects the event-shaped
state-changing path.

An agent, user, workflow, or service proposes an action or intended effect. The
implemented path then makes the candidate-event boundary explicit:

```text
proposed action
      ↓
candidate event
      ↓
domain decision and transition-truth validation
      ↓
concurrency / persistence admission
      ↓
Accepted History
```

This flow preserves two current responsibilities:

- Compass validation determines whether the candidate event is semantically
  trustworthy under its transition boundary.
- The concurrency / persistence admission boundary determines whether the
  candidate event can still become the next accepted fact.

Permission, evidence, idempotency, transaction ownership, and later semantic
interpretation remain separately scoped concerns. The flow does not collapse
validation into Runtime Decision Authority or execution.

The important distinction is that a technically executable operation is not
necessarily a semantically valid state transition.

For example:

```text
permission check passed
API call succeeded
transaction committed
```

does not necessarily imply:

```text
the resulting state transition was authorized and semantically correct
```

A write-side governance system therefore asks questions such as:

- Is this actor authorized to propose or cause this action?
- Does the proposed transition satisfy domain invariants?
- Is the relevant evidence sufficient and current?
- Does the workflow preserve the intended authority boundary?
- Is an indirect path producing an intended effect that the originating actor
  was not authorized to cause?
- Is this candidate event semantically trustworthy?
- Can this candidate event still become the next accepted fact?

The fundamental write-side question is:

> **What may become true?**

---

## 5. Claim-Side Semantic Governance Research

AI-mediated claim correctness is related to write-side admission, but it is not
its mirror image and it is not a currently implemented symmetric runtime.

An AI may leave accepted event history unchanged while reading a governed source
corpus and producing a report, summary, recommendation, decision-support
artifact, or natural-language conclusion.

A conceptual path is:

```text
Governed Source Corpus
        ↓
retrieval / observation
        ↓
source-status resolution
        ↓
interpretation
        ↓
inference
        ↓
candidate claim
        ↓
claim review / admission
        ↓
trusted or Accepted Public-Facing Meaning
```

`Structured Claim`, `Claim Boundary`, and `Accepted Public-Facing Meaning` are
existing Semantic Admission concepts that can anchor this research direction.
`Claim Admission`, `Read-Side Semantic Governance`, and `claim-side semantic
governance` remain working research vocabulary rather than established
production Compass terminology.

The technical pipeline may succeed while the semantic result is still wrong.

For example:

```text
retrieval succeeded
context was populated
the model returned an answer
citations were attached
```

does not necessarily imply:

```text
the resulting claim is justified by current, relevant, authority-qualified evidence
```

The fundamental claim-side question is:

> **What may be claimed as true?**

---

## 6. Why Ordinary RAG Evaluation Is Not the Whole Problem

RAG is one possible implementation technique. The same semantic risk appears
when an AI reads long-context prompts, repositories, databases, search tools,
knowledge graphs, document stores, or several of these sources together.

Retrieval success, populated context, fluent generation, and attached citations
do not establish that a claim is justified. A citation identifies a referenced
source; by itself it does not establish source authority, freshness, coverage,
conflict resolution, correct interpretation, or a valid inference.

The broader question is:

> How can a system determine whether an AI-generated claim is justified by the
> governed evidence domain it was expected to interpret?

This is a claim-correctness and evidence-governance problem, not merely a
retrieval-quality problem.

---

## 7. Concise Claim-Side Failure Model

The claim-side research direction is motivated by several recurring risks:

### Incomplete Evidence Coverage

```text
"I found no problem"
≠
"there is no problem"
```

Without coverage evidence, absence of an observed contradiction is not evidence
that no contradiction exists.

### Stale or Superseded Sources

```text
source exists
≠
source is relevant
≠
source is current
≠
source is authoritative for this claim
```

Successful retrieval can still select historical, superseded, or incorrectly
scoped material.

### Conflicting Evidence

Evidence volume or majority agreement does not automatically resolve authority.
A later accepted source may govern current interpretation even when several
older sources disagree with it.

### Fact Versus Inference

```text
source-supported fact
≠
model inference
```

A claim may begin from a correctly retrieved fact and still overstate what the
source justifies.

### Provenance and Uncertainty

A trustworthy claim path may need to preserve which sources, spans, authority
statuses, coverage limits, conflict resolutions, and inference steps support a
claim, together with unresolved uncertainty. This is a research requirement,
not a claim that a production schema or validator already exists.

---

## 8. Relationship to Existing AI-Governance Research

This note defines the architectural bridge; it does not duplicate the detailed
claim-review mechanism.

Related research already covers:

- [From Generated Language to Source-Grounded Semantic Admission](../research/ai_governance/from_generated_language_to_source_grounded_semantic_admission.md)
  — candidate generated artifacts, source grounding, conflicting evidence, and
  fact-versus-inference review.
- [Admitted Overviews, Cache Freshness, and Event-Driven Invalidation](../research/ai_governance/admitted_overview_cache_and_event_driven_invalidation.md)
  — why admitted public-facing meaning may later become stale and require
  revalidation.
- [Multi-pass Suspicion Reasoning](../research/ai_governance/multi_pass_suspicion_reasoning.md)
  — an exploratory review pattern for candidate answers and explicit evidence
  scrutiny.

Those documents remain research notes rather than current Compass runtime
contracts. This bridge only explains why their claim-correctness questions are
adjacent to the existing Semantic Admission problem.

---

## 9. Effect Admission and Claim Admission Are Asymmetric

The two boundaries share a correctness principle without sharing an identical
implementation.

| Dimension | Write-Side Admission | Claim-Side Research Direction |
|---|---|---|
| Input | Proposed action represented by a candidate event | Governed source corpus with mixed source status |
| Core question | What may become true? | What may be claimed as true? |
| Current governance object | Candidate event | Candidate claim or Structured Claim |
| Authority anchor | Accepted History and current domain context | Authority-qualified sources for the claim and scope |
| Main failure | Invalid candidate enters Accepted History | Unsupported interpretation becomes trusted meaning |
| Evidence emphasis | Domain invariants, prior history, permission, concurrency, idempotency | Coverage, source authority, freshness, conflict, provenance, inference, uncertainty |
| Maturity | Implemented Compass baseline | Emerging conceptual and research direction |

The write-side path changes durable event authority. The claim-side path may
leave that authority unchanged while still producing consequential meaning for
humans or downstream agents.

The phrase **effect admission** may be useful as a broad conceptual shorthand,
but the implemented repository vocabulary remains more precise: proposed
action, candidate event, validation, admission, accepted fact, and `Accepted
History`.

---

## 10. Shared Principle, Separate Responsibilities

Both sides expose the same deeper systems principle:

> **Technical success does not establish semantic correctness.**

On the write side:

```text
successful execution
≠
valid state transition
```

On the read side:

```text
successful retrieval + generation
≠
evidence-justified claim
```

This is the common foundation.

The similar high-level pattern does not erase repository responsibilities:

```text
validation
≠ technical evidence
≠ SemanticOutcome
≠ DecisionReceipt
≠ Runtime Decision Authority
≠ strategy selection
≠ retry / cross-attempt authorization
≠ execution
```

`SemanticOutcome` gives typed semantic meaning to technical evidence.
`DecisionReceipt` may preserve selected governance evidence. Neither one
authorizes or executes an action.

Any future claim-side runtime must define its own evidence eligibility,
admission result, consumer, and authorization boundary rather than borrowing
authority from the availability of current Stage 4 types.

---

## 11. Three Distinct Consumption Modes

AI-mediated interpretation introduces an additional downstream
semantic-consumption path adjacent to conventional CQRS read models. It does not
redefine the conventional CQRS read side and it is not merely a new projector.

### 11.1 Aggregate Replay / Rehydration

```text
Accepted History
      ↓
deterministic replay / rehydration
      ↓
Current Aggregate State
```

This path supports future transactional decisions. It reconstructs aggregate
state by applying accepted events under domain semantics. It is not analytical
truth reconstruction and does not produce an AI claim.

### 11.2 Deterministic Projection

```text
Accepted History
      ↓
canonical deterministic reducer / projector
      ↓
Read Model
```

Its correctness concerns include materialization, sequence and progress,
replay/rebuild equivalence, and drift from accepted-history authority.
Projection state remains derived, rebuildable, and subordinate to `Accepted
History`.

The project's existing phrase **one event stream, two semantic worlds** retains
its current meaning here: the same accepted event history supports
transactional and analytical / observational consumption under different
execution goals. This note does not redefine that phrase as write governance
versus claim governance.

### 11.3 AI-Mediated Semantic Interpretation

```text
Governed Source Corpus
      ↓
retrieval / observation
      ↓
source-status resolution
      ↓
interpretation / inference
      ↓
Candidate Claim
```

This path asks whether available evidence actually justifies the resulting
claim. Its sources may include accepted event history, derived read models,
documents, databases, or other authority-scoped material, but those inputs do
not become equivalent merely because one AI consumes them.

Preferred working descriptions include **AI-mediated semantic
interpretation**, **source-grounded claim reconstruction**, **document-source
truth-status reconstruction**, and **claim-side semantic governance**.
Unqualified **truth reconstruction** is avoided because repository documents
already use reconstruction for deterministic aggregate, projection, snapshot,
and receipt paths.

---

## 12. A Broader Semantic Admission Problem Space

The conceptual relationship can be summarized without claiming a symmetric
runtime:

```text
proposed action
      ↓
candidate-event validation and admission
      ↓
Accepted History
      ↓
deterministic transactional or projection consumption
```

Separately:

```text
Governed Source Corpus
      ↓
AI-mediated observation and interpretation
      ↓
Candidate Claim
      ↓
conceptual claim review / admission
      ↓
trusted or Accepted Public-Facing Meaning
```

Both paths belong to a broader Semantic Admission problem space because both
protect a boundary between a candidate and meaning that another consumer may
trust. They remain different paths with different sources and consequences.

The write-side boundary asks:

> Is this candidate event semantically trustworthy, and can it still become an
> accepted fact?

The claim-side research boundary asks:

> Is this candidate claim justified by authority-qualified evidence for its
> stated scope?

---

## 13. Working Authority Vocabulary

This framing also connects naturally to broader AI-governance questions.

The following terms are conceptual research vocabulary in this note. They are
not asserted as established production Compass architecture.

### Representational Authority

> Who is the AI authorized to represent?

### Epistemic Authority

> What is the AI justified in claiming to know?

### Operational Authority

> What is the AI authorized to cause or change?

The implemented Compass baseline directly protects candidate-event truth,
accepted-history admission, durable permission boundaries, and derived-state
correctness. Those responsibilities overlap operational and evidence-authority
questions without adopting this three-part vocabulary as a runtime contract.

Source-grounded claim research is most directly concerned with epistemic
authority: what the available governed evidence justifies an AI in claiming.

A complete AI-governance architecture may eventually need to make these
boundaries explicit rather than treating them as one undifferentiated
permission problem.

---

## 14. Why Read-Only AI Still Creates Semantic Risk

A common safety instinct is to make AI systems read-only.

That reduces operational risk, but it does not eliminate semantic risk.

A read-only AI can still:

- produce an incorrect compliance report,
- summarize an obsolete architecture,
- omit a critical constraint,
- invent a causal relationship,
- recommend an unsafe action,
- misstate what a repository currently supports,
- or influence a human or another agent to take an incorrect action.

Therefore:

> **Read-only does not mean consequence-free.**

If downstream humans or agents treat an AI-generated claim as trustworthy,
claim correctness becomes a governance concern even when the producing AI has
no direct mutation capability.

---

## 15. Working Claim-Side Vocabulary

The exact claim-side terminology is not fixed. These labels remain research
vocabulary rather than accepted production contracts.

### Write-Side Semantic Governance

Conceptually describes the protection around a proposed action becoming an
accepted fact. In the implemented event path, use the more precise repository
terms `candidate event`, transition-truth validation, concurrency / persistence
admission, and `Accepted History`.

### Read-Side Semantic Governance

Working research term for governing whether a reconstructed claim may be
accepted as a trustworthy representation of authority-qualified sources.

### Claim Admission

Working research term for reviewing whether a candidate claim may become
trusted or Accepted Public-Facing Meaning.

Alternative terms for the read side may include:

- claim-side semantic governance,
- source-grounded claim governance,
- AI-mediated semantic interpretation,
- evidence-grounded claim admission,
- document-source truth-status reconstruction.

The important point is not the label.

The important point is that AI-mediated claim correctness is a first-class
research problem, not merely a retrieval implementation detail and not a
redefinition of deterministic CQRS projection.

---

## 16. Current Compass and Research Mapping

The two concerns have different maturity and evidence bases.

### Implemented Compass Baselines

The repository implements bounded foundations for:

- domain decisions and candidate-event construction;
- transition-truth validation;
- concurrency / persistence admission into `Accepted History`;
- deterministic aggregate rehydration;
- deterministic projection and replay/rebuild comparison;
- bounded read-side and snapshot `SemanticOutcome` mapping; and
- selected `DecisionReceipt` mapping, serialization, and persistence
  foundations.

These foundations do not collapse into Runtime Decision Authority, strategy
selection, retry authorization, or execution.

### Emerging Claim-Side Research

Source-grounded generation, evidence freshness, candidate-answer review, and
document-truth reconstruction explore how AI-generated claims might remain
accountable to a governed source corpus.

Document-truth reconstruction is an experimental research direction and is not
part of the current `main` implementation baseline. No production
claim-admission runtime is claimed.

The shared architectural concern is:

> A result should not be trusted merely because the system successfully
> produced it.

---

## 17. Open Research Questions

This framing opens several questions worth exploring.

### Write Side

- How should indirect authority composition be represented?
- How should reachable authority differ from direct permission?
- What evidence must exist before a proposed action can become an accepted fact?
- Where should semantic admission occur relative to transactions?
- How should retry and cross-attempt authority be governed?

### Claim Side

- How should required evidence coverage be defined?
- How can the system prove what was and was not observed?
- How should stale or superseded sources be detected?
- How should conflicting sources be arbitrated?
- How should facts be separated from model-generated inference?
- What constitutes sufficient evidence for a claim?
- How should uncertainty be represented?
- Can a claim be reproducibly reviewed from its preserved evidence trail?
- How should downstream agents consume claims whose evidence is incomplete?

### Across Both Sides

- Can write-side admission and claim admission share any useful governance
  abstraction without erasing their asymmetry?
- Can authority, provenance, scope, freshness, and evidence be represented
  consistently across both paths?
- Should an AI-generated claim become an explicit governed artifact rather
  than unstructured text?
- Can the same audit model reconstruct both:
  - why an effect was allowed, and
  - why a claim was believed?

---

## 18. Non-Goals

This framing does not claim that:

- CQRS itself solves AI governance,
- read-side governance is equivalent to traditional CQRS projection,
- AI-mediated interpretation changes the meaning of the conventional CQRS read side,
- claim-side analysis is a projector,
- a document corpus is `Accepted History`,
- every retrieved source is authoritative,
- `SemanticOutcome` or `DecisionReceipt` performs claim admission,
- this note implements Runtime Decision Authority, strategy selection, retry
  authorization, or execution,
- claim admission is already an accepted production Compass responsibility,
- Representational, Epistemic, or Operational Authority is frozen repository
  vocabulary,
- RAG correctness can be reduced to citations,
- all AI outputs must be deterministic,
- every natural-language claim can be formally proven,
- or write-side admission and claim-side governance should share identical
  implementations.

CQRS is used here as a useful architectural lens.

The important insight is that two different candidate-to-trust boundaries can
belong to one broader Semantic Admission problem space without becoming one
mechanism.

---

## 19. Final Principle

The write side asks:

> **What may become true?**

The claim-side research direction asks:

> **What may be claimed as true?**

Between these questions sits the broader conceptual role of authoritative
truth. In the implemented Compass path, `Accepted History` remains the durable
event authority. On the claim side, a `Governed Source Corpus` may contain
sources with different authority, freshness, supersession, scope, and conflict
status.

For AI systems, both paths require evidence, provenance, scope, and explicit
semantic boundaries, but their validation and admission responsibilities are
not interchangeable.

A system is not trustworthy merely because it can successfully write.

A system is not trustworthy merely because it can successfully read.

The deeper goal is to preserve semantic correctness in both directions.
