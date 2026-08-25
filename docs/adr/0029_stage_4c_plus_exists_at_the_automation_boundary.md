# ADR 0029 — Stage 4C+ Exists at the Automation Boundary

[← Back to ADR Index](README.md)

## Status

Accepted

## Implementation Status

The architecture boundary is established on the completed Stage 4 baseline.

```text
Stage 4A–4B.5
= completed semantic / evidence foundation

Stage 4C
= current-response authority
= implemented / closed

Stage 4D
= dynamic HOW-selection responsibility retained
= implementation deferred under ADR 0028

Stage 4E
= bounded same-request re-invocation authority
= implemented / closed
```

The end-to-end autonomous recovery composition described below is not yet implemented.
It remains an evidence-gated follow-up experiment.

---

## Context

By the end of Stage 4B, Compass can already support a traditional human-operated correctness workflow.

The system can preserve and expose:

- technical producer results;
- semantic interpretation;
- structured evidence;
- execution traces;
- measurements;
- correctness-rule evidence;
- durable governance receipts where applicable.

Conceptually:

```text
request
    ↓
technical result
    ↓
semantic interpretation
    ↓
evidence / trace / receipt
```

For a conventional backend, this may be a sufficient operational boundary.

A human operator or caller can inspect the evidence and decide whether to:

```text
return failure
wait
investigate
escalate
repair
or initiate another recovery procedure
```

In that model, downstream consequence authority may remain outside Compass.

This changes when the downstream actor is an autonomous runtime, workflow engine, recovery controller, or AI agent.

Stage 4B evidence can answer:

> What happened?

and:

> What evidence supports that interpretation?

It cannot by itself answer:

> What consequence is this machine authorized to cause next?

The missing distinction is:

```text
evidence
!=
proposal
!=
authority
!=
execution
```

The derivation from invocation-local concurrency behavior to this automation boundary is preserved separately in
[Invocation Completion Is Not Workflow Completion](../reasoning_notes/invocation_completion_is_not_workflow_completion.md).

---

## Decision

Compass treats the boundary after Stage 4B as the point where an evidence system may become an autonomous-governance system.

### Stage 4B and Earlier

The primary responsibility is epistemic:

```text
What happened?
What does it mean?
What evidence supports it?
```

A system may intentionally stop here when downstream operational decisions remain human-controlled.

### Stage 4C and Later

These responsibilities exist when machine-controlled consequences require explicit governance.

Their purpose is to make authority that would otherwise remain implicit in a human caller:

```text
explicit
typed
reviewable
enforceable
```

The current Stage 4 responsibilities are:

```text
Stage 4C
→ What current response is authorized?

Stage 4D
→ How should an already-authorized operation be executed?
→ responsibility retained; implementation deferred

Stage 4E
→ May one additional invocation of the same complete request enter?
```

These are distinct responsibilities.

They do not form one mandatory linear pipeline.

The architectural boundary is therefore:

```text
Stage 4B and earlier
= evidence / understanding system

Stage 4C+
= explicit machine consequence-authority boundary
```

This does not mean every backend needs Stage 4C+.

It means Stage 4C+ becomes necessary when downstream consequences move from human judgment into autonomous machinery.

---

## Invocation Completion Is Not Workflow Completion

Autonomous workflows expose a second distinction:

```text
Invocation Completed
!=
Workflow Responsibility Completed
```

A local request may terminate correctly while a larger workflow still needs to determine:

```text
What is the current authoritative world?
Has the workflow goal already been satisfied?
Is the original action now unnecessary?
Is the original action now illegal?
Does another governed action remain?
```

Therefore:

```text
database correctness
!=
workflow progress responsibility
```

Compass does not guarantee eventual workflow completion.

The narrower rule is:

> Invocation completion alone must not be treated as machine authority to stop, continue, or retry a larger autonomous workflow.

---

## Fresh Re-Observation Is Not Retry of Old Work

When authoritative state changes after an invocation reasoned from an older observation, the useful next operation may be a fresh invocation rather than reuse of stale work.

Preserve:

```text
fresh re-observation
!=
retry old append

fresh re-observation
!=
reuse old candidate

fresh re-observation
!=
reuse old validation
```

A fresh invocation may discover that:

```text
the same complete request already succeeded
```

or:

```text
another accepted change made the old action invalid
```

The completed Stage 4E PostgreSQL characterizations demonstrate both forms of information gain.

However:

```text
fresh-invocation information value
!=
ReinvocationAuthorization
```

Information value motivates an authority question.
It does not answer it.

---

## Evidence Must Be Strong Enough for the Consequence

Compass must not infer another-invocation authority from a coarse technical label alone.

For example:

```text
STALE_WRITE
```

can represent multiple physical causes.

Therefore:

```text
technical outcome
!=
physical evidence

same technical outcome
!=
same consequence authority
```

The completed Stage 4E implementation preserves this separation.

PR4 introduced typed append-version evidence:

```text
AppendVersionMismatchEvidence(
    expected_current_version,
    observed_current_version,
)
```

PR5 consumes only the narrower reviewed version-advance case:

```text
observed_current_version
>
expected_current_version
```

together with the required completed-result coherence.

Thus:

```text
physical fact
→ typed evidence
→ consequence-specific authority evaluation
```

remains intentionally different from:

```text
error type
→ retry
```

Generic `STALE_WRITE` is not a re-invocation policy.

---

## Stage 4E Specifically

Stage 4E does not decide:

```text
Should retry eventually succeed?
What recovery strategy is best?
How many attempts should exist?
When should another attempt run?
Has the entire workflow goal completed?
```

Its implemented responsibility is:

> Given reviewed evidence from a completed prior invocation, is exactly one additional invocation of the same complete `RequestSignature` authorized?

The current production-positive profiles are deliberately bounded:

```text
1. preparation-time LOCK_TIMEOUT profile

2. coherent append version-advance profile
```

The one-shot owner lifecycle preserves:

```text
AVAILABLE
→
SPENT
before A2 entry
```

and does not create:

```text
automatic A3
retry budget
retry-until-success
```

---

## Autonomous Recovery Composition

A future autonomous recovery experiment should test:

```text
Stage 4B / producer evidence
        ↓
Recovery Planner / AI Agent
        ↓
Recovery Proposal
        ↓
Consequence-Specific Authority Evaluation
        ↓
AUTHORIZED / REFUSED / NO AUTHORITY
        ↓
Controlled Executor
        ↓
Fresh Observation
        ↓
Governance again
```

The planner may eventually be deterministic or model-driven.

Its proposal is never itself authority:

```text
PlannerProposal(x, action)
!=
Authorized(x, action)
```

and:

```text
Authorized(x, action)
!=
Executed(x, action)
```

A fresh observation must return to governance rather than inherit permanent authority from the previous decision.

---

## Alternatives Considered

### Stop permanently at Stage 4B

Rejected as a universal rule.

Stage 4B is sufficient when humans retain downstream authority, but not when autonomous machinery must make and enforce consequence-bearing decisions.

### Let the planner execute its own remediation

Rejected.

This collapses:

```text
proposal
=
authority
=
execution
```

and removes the independent governance boundary.

### Treat technical failure classes as retry policy

Rejected.

Coarse statuses such as `LOCK_TIMEOUT`, `STALE_WRITE`, or validation failure do not prove one shared physical cause or consequence.

### Implement one mandatory `Stage 4C → Stage 4D → Stage 4E` pipeline

Rejected.

The responsibilities are consequence-specific and may be evaluated independently.

Stage 4D is currently deferred because no dynamic HOW-selection problem is justified.

---

## Consequences

### Positive

- Human-operated systems may stop at the evidence boundary without unnecessary autonomous-governance machinery.
- Autonomous systems gain an explicit place to separate proposals from authority.
- Evidence can support multiple consequence-specific evaluations without becoming self-authorizing.
- Current-response authority and another-invocation authority remain independent.
- Future planner or AI behavior can change without weakening the authority boundary.

### Trade-offs

- Autonomous workflows require more explicit machinery than human-operated backends.
- Evidence sufficient for diagnosis may still be insufficient for action authority.
- New protected effects may require additional consequence-specific authority types.
- Workflow-level completion remains separate from request completion.

---

## Current Repository Implication

The completed Stage 4 baseline already contains:

- structured `SemanticOutcome` interpretation;
- durable and execution-local evidence;
- correctness-rule evidence;
- Stage 4C current-response decision/refusal;
- Stage 4E another-invocation authorization/no-authority;
- one-shot re-invocation authority consumption;
- current-result custody across A1 and A2;
- executable PostgreSQL evidence that a fresh invocation can reveal new authoritative information.

The repository does not yet contain a complete autonomous recovery workflow.

There is no general:

- autonomous workflow owner;
- goal-completion contract;
- recovery planner in production;
- automatic Stage 4C / Stage 4E governance loop;
- recovery scheduler;
- durable A3 lifecycle;
- retry-until-success mechanism.

The next step is an experiment, not automatic production expansion.

---

## Follow-Up Evidence Gate

Before creating another production stage or runtime responsibility, require executable evidence that:

1. a planner can consume existing evidence and propose a meaningful next step;
2. authority evaluation can independently allow or refuse that proposal;
3. a controlled executor can enforce the authority result;
4. an unauthorized proposal cannot cause the protected consequence;
5. an authorized execution produces a fresh authoritative observation;
6. the fresh observation can re-enter governance;
7. workflow-level logic can distinguish invocation completion from workflow completion without bypassing consequence-specific authority;
8. the composition provides observable value beyond a human-operated Stage 4B workflow.

The first experiment should use a deterministic recovery planner.

A later experiment may replace that planner with an LLM while retaining the same authority boundary.

---

## Non-Goals

This ADR does not establish:

- that every backend needs Stage 4C+;
- that AI must be used inside Compass;
- that Stage 4C is a recovery planner;
- that Stage 4E is a workflow scheduler;
- that Stage 4E guarantees workflow progress;
- that every completed invocation deserves another invocation;
- that every stale or conflict result deserves re-invocation;
- that every validation failure proves authoritative state changed;
- that generic `STALE_WRITE` is a re-invocation policy;
- that fresh-invocation information value is itself authority;
- that a planner may bypass consequence-specific authority;
- that automatic A3, retry budgets, backoff, or schedulers are justified;
- that workflow completion and request completion require one universal state machine;
- that a new production stage is currently justified.

---

## References

- [ADR 0027 — Separate Runtime Decision, Strategy, and Retry Authority](0027_separate_runtime_decision_strategy_and_retry_authority.md)
- [ADR 0028 — Defer Dynamic Strategy Selection Until Multiple Eligible Execution Paths Exist](0028_defer_dynamic_strategy_selection_until_multiple_eligible_execution_paths_exist.md)
- [Stage 4E Closeout](../implementation_notes/stage_4e/stage_4e_closeout.md)
- [Stage 4E Implementation Notes](../implementation_notes/stage_4e/README.md)
- [Reasoning Note — Invocation Completion Is Not Workflow Completion](../reasoning_notes/invocation_completion_is_not_workflow_completion.md)
