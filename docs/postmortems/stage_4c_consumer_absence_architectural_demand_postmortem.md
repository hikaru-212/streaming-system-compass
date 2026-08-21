# Postmortem: Conflating Current Consumer Absence with Architectural Demand in Stage 4C

[← Back to Postmortems Index](README.md)

**Recorded on:** 2026-08-22

---

## 1. Purpose

This note records a reasoning failure discovered immediately after the first
Stage 4C PR2 implementation.

The code itself was not the problem.

The first Stage 4C PR2 implementation had a coherent responsibility:

```text
PostgresWriteSideSemanticRuleFeedback
→ evaluate_postgres_write_side_runtime_decision
→ PostgresWriteSideRuntimeDecisionEvaluation
   ├─ RuntimeDecision
   └─ exact source feedback
```

The problem appeared after noticing that no production caller consumed the
result.

That observation triggered a reasonable architecture question:

```text
If RuntimeDecision represents authority,
but nobody consumes it,
is Stage 4C actually complete?

More fundamentally:

Should a real consumer exist?
```

The discussion then became circular because one source fact was repeatedly
treated as if it answered a different architecture question:

```text
no current production consumer
```

was allowed to drift into:

```text
no consumer is needed
```

or:

```text
consumer work is not architecturally justified
```

Those statements are not equivalent.

The corrected lesson is:

```text
current source absence
!=
evidence of architectural non-need
```

and:

```text
responsibility validity
!=
current implementation necessity
!=
current production wiring
!=
stage completion
```

This distinction later became one of the most important results of the
Stage 4C → 4D → 4E runtime-governance experiment.


---

## Core Engineering Principle Exposed by This Episode

> **If I cannot state why a mechanism needs to exist, I should not implement it.**
>
> **If a responsibility boundary still appears necessary, intuition is not enough:
> isolate it in the smallest reversible experiment and let executable evidence
> prove or falsify the claim.**

These two rules are intentionally paired.

The first prevents speculative architecture:

```text
unclear purpose
→ do not promote a mechanism into production
```

The second prevents current source absence from becoming a false architecture
verdict:

```text
responsibility still appears meaningful
+ current source cannot settle the question
→ build a bounded experiment
→ use observable behavior as evidence
```

This episode required both disciplines at once:

```text
do not build what cannot justify its existence

but

do not discard a responsibility merely because its consumer does not exist yet
```

---

## 2. Context

Stage 4C was introduced to own Runtime Decision Authority.

Its question is:

```text
Given the current semantic observation and eligible supporting evidence,
what generic current response is permitted, required, or refused?
```

PR2 implemented two separately owned pieces:

```text
generic RuntimeDecision contract
+
first Layer-1 PostgreSQL / Order evaluator
```

The first positive response vocabulary was:

```text
USE_CURRENT_RESULT
RETURN_PRIOR_ACCEPTED_RESULT
BLOCK_CURRENT_CONTINUATION
REQUIRE_ESCALATION
```

Unsupported observations, including the first-profile
`CONCURRENCY_UNCERTAIN` cases, were refused rather than mapped to an implicit
allow or block.

At that point, however, the repository had no production caller above
`PostgresTransactionalWriteSide` that consumed the resulting
`RuntimeDecision`.

Therefore the actual production shape was:

```text
PostgresWriteSideResult
→ PostgresWriteSideSemanticRuleFeedback
→ Stage 4C evaluator
→ RuntimeDecision

STOP
```

There was no production branch such as:

```text
RuntimeDecision
→ select current result
→ return prior accepted result
→ withhold continuation
→ surface escalation
```

That missing segment was real.

The mistake was not noticing it.

The mistake was reasoning incorrectly from it.

---

## 3. The Triggering Question

After PR2 was implemented, the question became:

```text
There is no consumer.

Should there be one?
```

This question contains several different subquestions:

```text
1. Does a production consumer exist now?

2. Does PR2 require a production consumer to be a valid contract/evaluator PR?

3. Does Stage 4C require a consumer before its responsibility is behaviorally
   demonstrated?

4. Should a production application layer be invented merely to create one?

5. Could an experiment-only consumer test whether the responsibility has real
   behavioral value?

6. Does the absence of a current consumer prove that the responsibility itself
   is unnecessary?
```

These questions were initially collapsed together.

That collapse created the reasoning loop.

---

## 4. What the Source Audit Actually Proved

The source audit could prove:

```text
no production code currently consumes RuntimeDecision
```

It could also prove:

```text
no production code currently catches Stage 4C refusal
and turns it into caller-visible behavior
```

It could further prove:

```text
removing PR2 would not currently alter the normal PostgreSQL writer path
```

Those are valid source-grounded facts.

But the audit could not prove:

```text
Stage 4C has no behavioral value
```

It could not prove:

```text
no caller should ever consume RuntimeDecision
```

It could not prove:

```text
Stage 4C can be closed without demonstrating consumption
```

It could not prove:

```text
a consumer responsibility is architecturally unnecessary
```

The audit established the current repository state.

It did not establish the final architecture.

---

## 5. The Reasoning Loop

The circular discussion repeatedly moved through a pattern like this:

```text
Observation:
There is no current production consumer.

        ↓

Conclusion:
Do not invent a production caller merely to consume RuntimeDecision.

        ↓

Question:
Then how do we know RuntimeDecision actually changes caller behavior?

        ↓

Response:
There is no current production consumer.

        ↓

Question:
That only describes the current source.
Does Stage 4C need consumption to prove its authority boundary?

        ↓

Response:
No current caller requires it.

        ↓

Question:
But absence of a caller is exactly the fact being questioned.
Why does that prove no demand exists?

        ↓

back to the beginning
```

The key failure was that:

```text
"there is no consumer"
```

was used both as:

```text
the observation
```

and:

```text
the justification for not investigating whether one is architecturally needed
```

That is circular.

---

## 6. The Hidden Invalid Inference

The invalid inference was:

```text
NoConsumerExistsNow
→
NoConsumerNeedExists
```

That implication does not follow.

A more precise logical decomposition is:

```text
NoConsumerExistsNow
```

means only:

```text
current implementation state
```

To conclude:

```text
NoConsumerShouldBeImplementedNow
```

additional evidence is required.

To conclude:

```text
NoConsumerResponsibilityExists
```

even stronger evidence is required.

The three claims occupy different levels:

```text
descriptive source fact

implementation-priority judgment

architectural-responsibility judgment
```

They must not be substituted for each other.

---

## 7. Why the Stage 4B.3 Comparison Mattered

The distinction became clearer by comparing this case with Stage 4B.3.

Stage 4B.3 was not stopped merely because:

```text
no current consumer exists
```

There was additional evidence.

The Order domain was shallow:

```text
INIT
→ CREATED
→ PAID
```

Full accepted-history replay was already sufficient.

The proposed trust-continuation machinery would have introduced additional:

```text
state
lifecycle
trust continuation
compatibility handling
recovery complexity
```

without demonstrated benefit for the current domain.

Therefore the conclusion was supported by a cost/correctness comparison:

```text
mechanism cost
>
demonstrated current value
```

That is materially different from:

```text
nobody calls this yet
→ therefore nobody needs it
```

The reusable rule is:

```text
absence of a consumer
can be evidence about current integration state

but it is not sufficient evidence
for architectural non-need
```

---

## 8. The Correct Separation of Questions

The discussion became tractable only after separating four questions.

### A. Does the responsibility make sense?

For Stage 4C:

```text
SemanticOutcome
!=
caller action authority
```

A semantic interpretation can describe what happened without deciding what a
caller may do with the completed result.

Therefore a distinct current-response authority responsibility is coherent.

### B. Is the contract/evaluator implementation justified?

Yes.

The first evaluator provides a fail-closed typed authority boundary:

```text
reviewed tuple
→ RuntimeDecision

unsupported tuple
→ typed refusal
```

This has value even before automatic production wiring.

### C. Is production caller wiring justified now?

Not automatically.

No existing production application boundary required inventing a new
application service, writer API, executor, or orchestration layer merely so the
new type would have a consumer.

### D. Is behavioral consumption still worth testing?

Yes.

This is the missing question that broke the loop.

The absence of a production caller does not prevent an experiment from asking:

```text
If a caller did consume RuntimeDecision,
would observable behavior actually differ?
```

That question can be answered without manufacturing production architecture.

---

## 9. The Corrected Experimental Move

Instead of forcing a production consumer into the formal PR2 branch, a separate
experiment branch introduced the smallest bounded runtime owner.

Its flow was:

```text
complete RequestSignature
→ real PostgreSQL public writer
→ exact PostgresWriteSideResult
→ exact PostgresWriteSideSemanticRuleFeedback
→ Stage 4C RuntimeDecision or typed refusal
→ caller-visible consequence
```

The caller consequences were deliberately producer-specific:

```text
USE_CURRENT_RESULT
→ CurrentResultSelected

RETURN_PRIOR_ACCEPTED_RESULT
→ PriorAcceptedResultSelected

BLOCK_CURRENT_CONTINUATION
→ CurrentContinuationBlocked

REQUIRE_ESCALATION
→ EscalationRequired

Stage 4C refusal
→ NoStage4CAuthority
```

This experiment answered the question that source inspection alone could not.

It demonstrated:

```text
RuntimeDecision
can constrain caller behavior
without changing writer safety,
transaction semantics,
or accepted-history authority.
```

That is the behavioral value of Stage 4C.

---

## 10. What the Experiment Proved About Stage 4C

The experiment established that Stage 4C is not merely a renaming layer over
producer outcomes.

Without Stage 4C, callers regain freedom to interpret completed results
independently.

For example, callers could diverge on whether to:

```text
use an accepted result

return the exact prior accepted replay result

continue normally after conflict

continue normally after validation block

surface infrastructure escalation

treat concurrency uncertainty as block

treat concurrency uncertainty as retry permission
```

With Stage 4C, the reviewed first profile constrains those interpretations.

Therefore:

```text
SemanticOutcome
describes semantic meaning

RuntimeDecision
governs current-result handling
```

Those are different responsibilities.

The consumer experiment made that distinction executable.

---

## 11. What the Experiment Did Not Prove

The experiment did not prove that the experimental runtime owner itself should
be promoted to production.

It also did not prove that Stage 4C PR2 must include automatic production
wiring.

Those are separate decisions.

The final result was:

```text
Stage 4C responsibility
= validated

Stage 4C PR2 contract/evaluator
= worth formalizing

experimental caller consequence model
= useful proof mechanism

production caller/orchestration shape
= still separate future work
```

This is exactly why:

```text
behavioral validation
!=
mechanism promotion
```

---

## 12. Why "Do Not Invent a Consumer" Was Only Half Correct

One statement made during the discussion was correct:

```text
Do not invent a production caller merely to make RuntimeDecision look used.
```

That protects the codebase from speculative orchestration.

The mistake was extending that statement into:

```text
therefore do not investigate consumer behavior
```

The corrected pair is:

```text
Do not invent production demand.

Do create a bounded experiment when architectural demand is uncertain
and executable evidence can resolve the uncertainty.
```

Those principles are compatible.

They are not opposites.

---

## 13. Capability Completeness vs Stage Completeness

Another distinction exposed by the discussion is:

```text
PR completeness
!=
stage completeness
```

PR2 can be complete as:

```text
an explicit callable RuntimeDecision capability
```

while Stage 4C remains incomplete as:

```text
a behaviorally validated runtime-governance stage
```

before an actual consumer boundary has been tested.

The useful model is:

```text
PR2 capability completeness:

SemanticOutcome
→ reviewed evaluator
→ RuntimeDecision
```

versus:

```text
Stage 4C behavioral completeness:

completed producer result
→ semantic evidence
→ RuntimeDecision or refusal
→ caller-visible consequence
```

The experiment supplied evidence for the second model without forcing that
consumer into PR2.

---

## 14. Responsibility Validity vs Implementation Priority

This episode also established a broader rule later used for Stage 4D.

A responsibility can be conceptually valid while its implementation is not
currently justified.

Stage 4D eventually reached exactly that conclusion:

```text
HOW-selection responsibility
= valid

dynamic selector implementation
= not currently justified
```

The reason is not:

```text
no selector exists
```

The reason is:

```text
current operations have statically selected writer compositions

no operation currently has multiple simultaneously eligible strategies

no reviewed typed evidence chooses among them

adding a selector would not change observable behavior
```

This is the stronger form of reasoning that was missing during the original
Stage 4C consumer discussion.

---

## 15. Source State, Demand, and Proof Must Stay Separate

A reusable three-axis model is:

| Question | Evidence type | Example |
|---|---|---|
| What exists now? | source audit | no production RuntimeDecision consumer |
| What is needed now? | concrete behavior/cost/correctness requirement | no need to invent production orchestration for PR2 |
| Is the responsibility real? | counterfactual / executable architecture evidence | removing Stage 4C returns uncontrolled caller interpretation |

Confusing these axes creates premature conclusions.

The corrected chain is:

```text
source audit
→ describes current state

architecture reasoning
→ identifies missing responsibility questions

bounded experiment
→ tests uncertain behavioral claims

formalization decision
→ chooses what deserves mainline implementation
```

---

## 16. A Better Review Procedure

When a new contract has no current consumer, do not immediately conclude either:

```text
it must be wired
```

or:

```text
it is unnecessary
```

Ask in order:

```text
1. What exact responsibility does the contract claim to own?

2. Is that responsibility already owned somewhere else?

3. What observable freedom exists if nobody consumes the contract?

4. Does the absence of a consumer make the contract merely dormant,
   or semantically meaningless?

5. Is there a real current production caller?

6. If not, would creating one require speculative application architecture?

7. Can a bounded experiment demonstrate the behavioral consequence
   without promoting speculative production machinery?

8. If the experiment removes the layer, what concrete freedom or
   correctness property returns?

9. If nothing changes, has the layer actually earned inclusion?

10. If behavior changes, which semantic responsibility should be preserved,
    and which experimental mechanisms should remain temporary?
```

This procedure avoids both overbuilding and premature deletion.

---

## 17. Counterfactual Review as the Missing Tool

The decisive technique was counterfactual removal.

For Stage 4C, ask:

```text
Remove RuntimeDecision and its consumer.

What becomes uncontrolled?
```

The answer was concrete:

```text
caller interpretation of completed results
```

For Stage 4D, ask:

```text
Remove dynamic strategy selection.

What changes today?
```

The answer was:

```text
nothing observable
```

because strategy is already statically selected.

For Stage 4E, ask:

```text
Remove another-invocation authorization.

What becomes uncontrolled?
```

The answer was:

```text
whether another invocation occurs
which complete request is used
how many additional invocations occur
whether execution composition changes
```

This produced the final C/D/E verdict:

```text
Stage 4C
→ KEEP

Stage 4D
→ KEEP RESPONSIBILITY + DEFER IMPLEMENTATION

Stage 4E
→ SIMPLIFY
```

The original consumer discussion lacked this counterfactual method.

Once introduced, the reasoning stopped being circular.

---

## 18. The AI-Assisted Reasoning Failure

This postmortem is also an AI-assisted architecture lesson.

The problematic reasoning pattern was not hallucinating a class or inventing a
field.

It was subtler:

```text
a true local fact
was repeatedly used as evidence for a stronger conclusion
that the fact did not support
```

The true fact was:

```text
no current production consumer exists
```

The unsupported stronger conclusion was allowed to drift toward:

```text
consumer behavior is not needed
```

This is dangerous because the reasoning sounds source-grounded.

Every sentence may mention real repository facts.

But the inference can still be invalid.

The lesson is:

```text
source-grounded premise
!=
source-grounded conclusion
```

The logical bridge must also be justified.

---

## 19. Reusable AI Review Heuristic

When an AI assistant says:

```text
there is no current X
```

and then recommends:

```text
therefore do not implement X
```

ask:

```text
Is absence itself the reason?

Or is there independent evidence that the responsibility, behavior,
or mechanism has no demonstrated value?
```

Useful follow-up questions are:

```text
What does removing this layer make possible again?

What behavior changes if the layer is consumed?

What concrete caller freedom is currently uncontrolled?

Is this an implementation-priority claim
or an architecture-responsibility claim?

What evidence would falsify the conclusion?

Can an experiment test the missing claim
without changing production architecture?
```

A good architecture recommendation should survive those questions.

---

## 20. Corrected Decision

The corrected Stage 4C conclusion is:

```text
No current production consumer exists.
```

This means:

```text
do not invent automatic production wiring merely to make PR2 look used
```

It does not mean:

```text
Stage 4C consumption is unnecessary
```

The bounded experiment demonstrated that current-response consumption has real
behavioral value.

Therefore:

```text
Stage 4C responsibility
→ KEEP

formal PR2
→ generic RuntimeDecision contract
+ first PostgreSQL write-side evaluator

automatic production caller wiring
→ not part of PR2

experimental consumer
→ evidence that the authority boundary is behaviorally meaningful

Stage 4C closeout
→ must consider the real caller/consumption boundary separately
```

---

## 21. What Should Be Preserved in the Repository

Preserve the semantic lesson:

```text
current absence
!= architectural non-need
```

Preserve the Stage 4C invariant:

```text
SemanticOutcome
!= RuntimeDecision
```

Preserve the behavioral distinction:

```text
authority representation
!= authority consumption
```

Preserve the implementation discipline:

```text
do not invent production consumers to satisfy architecture diagrams
```

Preserve the experimental discipline:

```text
when responsibility demand is uncertain,
build the smallest reversible experiment that can falsify the hypothesis
```

Do not promote merely because the experiment exists:

```text
experimental runtime owner class

producer-specific consequence dataclasses

experiment-local provenance machinery

test-only orchestration
```

The proof is valuable.

The proof mechanism is not automatically production architecture.

---

## 22. Final Takeaway

The original discussion became circular because it tried to answer:

```text
Should Stage 4C have a consumer?
```

with the observation:

```text
There is no consumer.
```

That cannot answer the question.

The corrected reasoning is:

```text
no current consumer
        ↓
source fact only
        ↓
identify the untested behavioral claim
        ↓
do not invent production wiring
        ↓
build bounded experiment
        ↓
observe counterfactual behavior
        ↓
decide responsibility and implementation separately
```

The shortest reusable rule is:

```text
"No current consumer"
is a repository fact,
not an architecture verdict.
```

A second version is:

```text
absence can justify investigation;
it cannot, by itself, justify non-need.
```

And the project-specific conclusion is:

```text
Stage 4C did not earn its place because a consumer already existed.

It earned its place because,
once consumption was made executable,
removing Stage 4C restored uncontrolled caller interpretation.
```
