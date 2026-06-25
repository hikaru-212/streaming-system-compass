# Research Note: From Generated Language to Source-Grounded Semantic Admission

[← Back to AI Governance Index](README.md)

**Recorded on:** 2026-06-23

---

## Purpose

This note records a conceptual extension of the project’s structured semantic outcome direction.

The original Stage 4 reasoning focused on moving from raw implementation failures such as:

```python
raise ValueError("invalid transition")
```

toward:

```text
structured semantic outcome
→ runtime decision policy
→ runtime decision
→ action safety gate
→ layered trust / governance
```

That transition was originally motivated by event validation, projection drift, and runtime control inside the Compass system.

This note extends the same reasoning to a different but related domain:

```text
LLM-generated natural language
```

The motivating question is:

```text
Can an AI-generated summary be checked against its source links,
and if the semantic error is too large,
can the system block or regenerate the summary before exposing it?
```

The answer is yes in principle.

But the important architectural lesson is not merely:

```text
use another LLM to check the first LLM
```

The deeper lesson is:

```text
generated natural language
→ structured semantic claims
→ source-grounded verification
→ semantic outcome
→ runtime decision
→ admission / block / retry / review
```

This is the natural-language version of the Compass admission problem.

---

## Background

The discussion was motivated by a failure pattern in AI-generated search summaries.

A search system may read source links that are mostly correct or harmless, then generate an AI Overview that incorrectly attributes a high-risk claim to a person, company, or publisher.

The dangerous part is not simply that the model generated imperfect text.

The dangerous part is that the system transformed source material into a new public-facing assertion.

For example:

```text
Source links: do not directly support that Company A committed fraud.
Generated summary: Company A was involved in fraud.
```

This creates a semantic gap between:

```text
source-grounded evidence
vs
generated public claim
```

Traditional search could present links and snippets.

An AI Overview generates a new statement.

Once the system generates a new statement, especially one involving reputation, crime, finance, medicine, or law, the output is no longer just retrieval.

It becomes a candidate semantic artifact.

That candidate should not automatically become public truth.

It should pass an admission boundary.

---

## Original Naive Loop Idea

A simple loop-based defense would be:

```text
LLM A reads links and generates Summary A.
LLM B reads the same links and generates Summary B.
LLM C compares Summary A and Summary B.
If the summaries differ too much, retry or block.
```

This is better than trusting a single model.

It creates some separation between generation and verification.

It may also reduce the risk that one model’s local attention error becomes the final output.

However, this approach is still too weak if it only compares two free-form summaries.

Two summaries can appear similar while hiding a serious semantic difference.

For example:

```text
Summary A: Company X committed fraud.
Summary B: Company X was mentioned in articles discussing fraud allegations.
```

These two summaries may be close in embedding space.

They may share many keywords.

But they do not carry the same legal or semantic meaning.

The first is a direct accusation.

The second is a statement about being mentioned in a context.

A pure summary-to-summary comparison is therefore too coarse.

The system needs a more explicit semantic representation.

---

## Corrected Architecture

The stronger architecture is not:

```text
summary vs summary
```

but:

```text
generated summary
→ high-risk claim extraction
→ source-grounded claim verification
→ structured semantic outcome
→ runtime decision
```

A better loop is:

```text
User query
    ↓
LLM A generates candidate summary
    ↓
Claim Extractor converts the candidate summary into structured claims
    ↓
Verifier reads source links or source snapshots
    ↓
Each claim is classified as supported, unsupported, neutral, or contradicted
    ↓
Runtime decision policy chooses ALLOW, WARN, RETRY, BLOCK, or HUMAN_REVIEW
```

This makes the output governable.

The goal is not to make natural language perfectly deterministic.

The goal is to prevent unsupported high-risk claims from crossing an irreversible or public-facing boundary.

---

## Structured Claim Extraction

The first key step is to convert generated text into atomic semantic claims.

For example, the generated sentence:

```text
Company X was involved in fraud and money laundering.
```

should not remain only as a sentence.

It should be decomposed into structured claims:

```json
{
  "claim_id": "c1",
  "subject": "Company X",
  "predicate": "involved_in",
  "object": "fraud",
  "risk_type": "criminal_accusation",
  "severity": "high",
  "modality": "asserted_as_fact",
  "source_support": "unknown",
  "evidence_required": true
}
```

And:

```json
{
  "claim_id": "c2",
  "subject": "Company X",
  "predicate": "involved_in",
  "object": "money_laundering",
  "risk_type": "criminal_accusation",
  "severity": "high",
  "modality": "asserted_as_fact",
  "source_support": "unknown",
  "evidence_required": true
}
```

This step matters because free-form text is difficult to govern.

Structured claims can be compared, logged, tested, routed, and converted into runtime decisions.

This mirrors the Compass direction:

```text
raw failure string
→ structured semantic outcome
```

In the natural-language setting, the transition becomes:

```text
raw generated sentence
→ structured semantic claim
```

---

## Source-Grounded Verification

After claims are extracted, each claim should be checked against source evidence.

The verifier should not only ask:

```text
Does the summary look reasonable?
```

It should ask:

```text
Which source span supports this claim?
Does the source directly support the subject, predicate, and object?
Does the source contradict the generated claim?
Is the claim merely mentioned, alleged, denied, or proven?
```

A possible verification result is:

```json
{
  "claim_id": "c1",
  "verdict": "unsupported",
  "reason": "The source links do not directly state that Company X committed fraud.",
  "evidence_spans": [],
  "decision_hint": "BLOCK"
}
```

Or:

```json
{
  "claim_id": "c1",
  "verdict": "contradicted",
  "reason": "The source says Company X denied involvement and no finding was established.",
  "evidence_spans": [
    {
      "source_id": "url_2",
      "span": "Company X denied involvement and no evidence was found..."
    }
  ],
  "decision_hint": "BLOCK"
}
```

The verifier can be implemented with an LLM, a smaller classifier, an NLI model, retrieval-based evidence matching, rules, or a hybrid system.

The important architectural rule is that verification should be source-grounded.

The source is the authority.

The generated summary is only a candidate.

---

## Risk Ontology

A keyword list is useful but insufficient.

The system may begin with human-defined high-risk terms such as:

```text
fraud
scam
money laundering
illegal fundraising
criminal investigation
medical harm
investment guarantee
terrorism
sexual misconduct
corruption
```

But the system should not rely only on exact keywords.

The safer design is a risk ontology.

For example:

```json
{
  "risk_type": "criminal_or_fraud_accusation",
  "examples": [
    "fraud",
    "scam",
    "money laundering",
    "illegal fundraising",
    "Ponzi scheme"
  ],
  "required_evidence_level": "direct_source_support",
  "default_failure_action": "BLOCK"
}
```

This allows the system to distinguish between:

```text
Company X committed fraud.
```

and:

```text
Company X denied fraud allegations.
```

and:

```text
Company X was mentioned in an article about fraud trends.
```

All three may contain the same high-risk word.

But they do not carry the same semantic responsibility.

The system must therefore track more than keywords.

It must track:

```text
subject
predicate
object
modality
source support
risk category
decision policy
```

---

## Runtime Decision Policy

A structured claim verdict is not yet the final control boundary.

The system still needs a policy that decides what to do.

For example:

```text
low-risk unsupported claim
→ WARN or RETRY

high-risk unsupported claim
→ BLOCK

high-risk contradicted claim
→ BLOCK and escalate

high-risk claim with weak support
→ HUMAN_REVIEW

high-risk claim with direct support
→ ALLOW with citation
```

A possible decision object:

```json
{
  "output_id": "summary_123",
  "decision": "BLOCK",
  "reason": "High-risk criminal accusation is unsupported by source evidence.",
  "blocked_claims": ["c1", "c2"],
  "recommended_action": "regenerate_without_unsupported_claims"
}
```

This is the same separation already needed in Compass:

```text
SemanticOutcome describes what happened.
RuntimeDecisionPolicy decides what to do.
ActionSafetyGate enforces the decision.
```

In the AI Overview setting, the action safety gate protects the public-facing generated output.

---

## Relationship to Compass

This idea is not separate from Compass.

It is a generalization of the same boundary principle.

In the current Compass project:

```text
candidate event
→ semantic validation
→ accepted history admission
```

For natural-language generation:

```text
candidate summary
→ claim extraction
→ source-grounded verification
→ public output admission
```

The analogy is:

```text
candidate event
≈ candidate generated claim

accepted history
≈ publicly admitted answer

semantic validator
≈ source-grounded claim verifier

structured semantic outcome
≈ claim verification outcome

runtime decision
≈ allow / retry / block / review

action safety gate
≈ output admission boundary
```

The shared principle is:

```text
A candidate artifact is not an accepted fact.
```

This applies both to event streams and to generated language.

A model-generated sentence should not become externally visible truth merely because the generation workflow completed successfully.

---

## Why This Is Not Just Prompt Engineering

Most LLM reliability work starts by trying to make the generator better:

```text
better prompt
better instruction
better model
better context window
```

Those are useful, but they do not create a control boundary.

A better prompt still produces a candidate.

A better model still produces a probabilistic output.

A larger context window still allows attention contamination, source mixing, and unsupported synthesis.

This postmortem records a different framing:

```text
LLM output is not truth.
LLM output is a candidate semantic artifact.
Candidate semantic artifacts require admission.
```

That framing turns the problem from prompt optimization into semantic governance.

The core question becomes:

```text
What must be true before this generated claim is allowed to cross the boundary?
```

That is an engineering question, not only a prompt-writing question.

---

## Why This Resembles Loop Engineering

The architecture still uses a loop.

For example:

```text
generate
→ extract claims
→ verify claims
→ block or retry
→ regenerate with error context
```

But the loop is not blind repetition.

It is not:

```text
try again until the model sounds better
```

It is:

```text
retry only when a structured semantic outcome explains why the candidate failed
```

This distinction matters.

A blind retry loop can become expensive and unstable.

A structured admission loop can produce specific correction context:

```text
The previous summary asserted that Company X committed fraud.
The sources do not support that claim.
Regenerate the summary without unsupported criminal accusations.
```

The retry becomes evidence-guided.

The system is no longer simply asking the model to improve.

It is forcing the next candidate to satisfy an explicit semantic boundary.

---

## Cost and Latency Tradeoff

This architecture is expensive.

It adds:

```text
source fetching
source snapshotting
claim extraction
evidence retrieval
claim verification
runtime decision
possible retry
audit logging
```

The cost may be unacceptable for every low-risk consumer search query.

A full verification loop for every AI-generated answer would increase latency and token usage.

Therefore, the realistic design should be risk-tiered.

For example:

```text
low-risk query
→ normal generation

medium-risk query
→ lightweight claim extraction

high-risk query
→ source-grounded verification

critical-risk query
→ block or human review unless strong evidence exists
```

High-risk categories include:

```text
criminal accusations
financial claims
medical advice
legal conclusions
reputation-damaging claims
public safety claims
political claims
personal identity claims
company misconduct claims
```

This means semantic admission does not need to be equally expensive everywhere.

It should be applied most strictly where the cost of false output is high.

The cost is not a flaw in the model.

It is the price of moving from probabilistic generation to governed output.

---

## Source Snapshot Requirement

A further issue is time.

A generated summary at 19:00 and another generated summary at 23:00 may differ because:

```text
the model sampled differently
the retrieval ranking changed
source pages changed
cached content changed
context assembly changed
```

Therefore, source-grounded verification should preserve a source snapshot or evidence record.

The system should know:

```text
Which source content was used?
At what time?
Which spans supported which claims?
Which verifier produced the outcome?
Which decision policy was applied?
```

Without this, the system cannot reliably audit why a generated claim was admitted or blocked.

This resembles accepted history in Compass.

The source snapshot is not the same as accepted history, but it plays a similar audit role for generated language.

It preserves the evidence boundary behind a decision.

---

## Reusable Lesson

The reusable lesson is:

```text
generated language is not automatically governable.
```

To govern generated language, the system must convert it into structured semantic artifacts.

The transition is:

```text
free-form summary
→ structured claims
→ source-grounded verification
→ semantic outcome
→ runtime decision
→ output admission
```

This is the natural-language counterpart of:

```text
exception
→ structured semantic outcome
→ runtime decision policy
→ action safety gate
```

The deeper principle is:

```text
candidate output is not accepted truth.
```

This applies to:

```text
candidate events
candidate projections
candidate summaries
candidate tool calls
candidate reports
candidate agent actions
```

The system should not ask only:

```text
Did the workflow run?
```

It must also ask:

```text
Did the candidate artifact preserve the right meaning?
Is there evidence?
Is it safe to admit?
Is it safe to act?
```

---

## Future Role in the Repository

This note belongs in `docs/research/ai_governance/` because it records an exploratory architecture idea inspired by AI governance failure patterns.

It does not define the final API.

It does not claim that Compass already implements natural-language claim verification.

It does not expand the current implementation roadmap.

It records why the Stage 4 structured outcome direction may later generalize beyond event-stream validation.

A future ADR could define a more concrete boundary such as:

```text
ADR — Source-Grounded Semantic Admission for Generated Claims
```

That ADR would need to decide:

* claim schema
* risk ontology
* verification verdict enum
* runtime decision enum
* source snapshot requirements
* retry policy
* human review policy
* audit record shape

Possible verification verdicts:

```text
SUPPORTED
UNSUPPORTED
NEUTRAL
CONTRADICTED
INSUFFICIENT_EVIDENCE
```

Possible runtime decisions:

```text
ALLOW
ALLOW_WITH_WARNING
RETRY
BLOCK
HUMAN_REVIEW
ESCALATE
```

This research note only records why that boundary may be meaningful.

---

## Summary

This note records one architectural realization:

```text
LLM-generated text should be treated as a candidate semantic artifact,
not as accepted truth.
```

A safer system should evolve from:

```text
generate summary
→ show summary
```

to:

```text
generate summary
→ extract structured claims
→ verify claims against sources
→ produce semantic outcomes
→ apply runtime decision policy
→ admit, retry, block, or escalate
```

The purpose is not to eliminate all uncertainty.

The purpose is to prevent unsupported high-risk claims from crossing public or irreversible boundaries.

This makes the AI Overview problem a form of semantic admission failure.

The generated summary may look fluent.

The workflow may complete.

The links may exist.

But the public-facing claim may still be semantically wrong.

That is why final generated text is not enough.

A correct-looking answer does not prove that the system preserved the right meaning.

A successful generation workflow does not prove that the output is safe to admit.

The system needs a boundary between:

```text
candidate generated language
```

and:

```text
accepted public-facing meaning
```

That boundary is source-grounded semantic admission.
