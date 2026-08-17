# Compass: Runtime Semantic Admission for Agentic State Mutation

[← Back to Overview Index](README.md)

> **Status:** This is a public, non-authoritative overview. Current source,
> accepted ADRs, boundary notes, and stage closeouts govern exact
> implementation truth.

## Current Implementation Orientation

- Stage 4A is complete: bounded technical runtime evidence maps to typed
  `SemanticOutcome`.
- Stage 4B is complete: `DecisionReceipt` contracts and mappings, tri-state
  flags, strict serializer v1, storage-neutral persistence contracts, and
  explicit caller-owned PostgreSQL persistence exist.
- Automatic receipt materialization and automatic mapper-to-store wiring are
  not implemented.
- Stage 4B.1 is complete: producer-specific `DiagnosticTrace` /
  `ResolutionTrace` contracts exist, and the PostgreSQL write-side traced APIs
  return Result + Trace; snapshot traced-resolver runtime integration remains
  intentionally deferred.
- Stage 4B.2 measurement / cost evidence is complete and closed.
- Stage 4B.5 Order Correctness Contract v0 is complete and closed: the contract
  has 18 stable rules, while current typed FullProof production covers exactly
  six transition-truth rules and does not authorize retry.
- Stage 4B.3 is complete and closed as not currently justified. PR1/PR2 remain
  investigation/reference evidence, ADR 0026 owns re-entry, and no Projection
  Trust Continuation mechanism was implemented.
- Stage 4C is now at a docs-first boundary: current-response Runtime Decision
  Authority is separate from Stage 4D strategy selection, Stage 4E retry/attempt
  authorization, and external execution. No production implementation is
  claimed.
- The first decision-governance direction is live/in-memory first.
  `SemanticOutcome` plus terminally applicable exact rule refinement is the
  primary live decision evidence; `DecisionReceipt` remains durable governance evidence
  but is not required for the first live hot path.

See the [Stage 4B closeout](../implementation_notes/stage_4b/stage_4b_closeout.md)
for the completed receipt baseline and the
[Stage 4B.1 closeout](../implementation_notes/stage_4b_1/stage_4b_1_closeout.md)
for the completed trace boundary. See
[ADR 0027](../adr/0027_separate_runtime_decision_strategy_and_retry_authority.md)
and the [Stage 4C docs-first entry](../implementation_notes/stage_4c/) for the
accepted next-phase responsibility boundary.

## The Problem

AI agents are increasingly able to turn intent into action.

They can call tools, update records, create orders, trigger workflows, move data, retry failed operations, coordinate with other agents, and modify durable enterprise state.

Traditional infrastructure can often prove that:

- an API call was authorized;
- a database transaction committed;
- a workflow completed;
- a tool invocation returned success;
- a retry technically succeeded.

But none of these facts proves:

> **This action should have been allowed to become reality.**

That is the gap Compass is designed to address.

## Agent Output Is a Candidate, Not Authority

A model response is not system truth.

A proposed tool call is not system truth.

A generated event is not system truth.

A multi-agent consensus is not system truth.

Each is only a **candidate action**: a proposal that may or may not deserve authority over durable state.

Compass therefore places an explicit admission boundary between agent reasoning and real-world mutation:

```text
Agent proposal
→ evidence gathering
→ semantic validation
→ concurrency admission
→ append and commit to accepted history
→ accepted durable fact
```

This flow describes the Compass authority transition into accepted history.
It does not claim that every external business effect is identical to an
accepted-history append.

The purpose is not to prevent agents from acting. The purpose is to prevent probabilistic proposals from becoming authoritative facts merely because they were executable.

## Accepted Authority Must Be Earned

Compass separates two roles that ordinary agent systems often collapse:

- **Candidate** — a proposed action, event, or state transition.
- **Accepted** — a candidate that has passed the required semantic and concurrency boundaries and has been admitted into accepted history.

An identifier may exist before admission. A tool may have permission. A write may be technically valid. None of these establishes accepted authority.

Accepted authority comes from successful admission into the system’s authoritative history.

This leads to a central distinction:

> **Permission answers whether an operation can be executed. Compass asks whether the operation should be allowed to become reality.**

That difference matters most in irreversible or high-impact domains such as finance, commerce, healthcare, identity, infrastructure, procurement, and public-sector systems.

## One Authoritative History, Multiple Evidence Roles

Compass treats accepted history as the durable record of admitted facts.

Other runtime artifacts remain useful, but they do not inherit that authority:

- **Projection state** is derived read state.
- **Checkpoint state** records operational progress.
- **Snapshot state** is derived fast-path evidence.
- **Idempotency records** preserve request-to-accepted-result relationships.
- **SemanticOutcome** interprets bounded technical evidence.
- **DecisionReceipt** preserves selected governance evidence when callers
  explicitly construct and persist a receipt through the implemented
  boundaries.
- **DiagnosticTrace** preserves bounded producer-specific one-execution
  topology where a concrete contract exists; it is not a primary result,
  receipt, measurement record, retry authorization, or generic cross-producer
  abstraction.

These artifacts must not impersonate one another.

A projection can be fresh but wrong.

A snapshot can exist but be untrusted.

A retry can succeed while no longer preserving the original intent.

A database role can be authorized while the business action remains inadmissible.

An outcome can be semantically valid without becoming executable authorization.

## Technical Success Is Not Semantic Correctness

Agentic systems often collapse everything into success or failure.

Compass instead recognizes that the same technical result may mean very different things:

- semantically valid;
- semantically blocked;
- concurrency-uncertain;
- derived state drifted;
- snapshot fast path unavailable;
- evidence unresolved;
- idempotent replay available;
- request identity conflicted;
- operator review required.

The target architecture separates live decision evidence from downstream
responsibilities. The model below is not the current end-to-end implementation:

```text
live SemanticOutcome
+ source-applicable terminal exact rule evidence
→ Runtime Decision Authority

authorized current response
→ Strategy Selection Authority
→ execution

another attempt considered
→ Retry / Attempt Authorization
→ Strategy Selection Authority for the authorized attempt
→ execution
```

The normal current-response path does not require Retry / Attempt
Authorization. Durable `DecisionReceipt` evidence may support later consumers,
but receipt persistence is not a prerequisite for live Runtime Decision
Authority.

`SemanticOutcome` describes what the evidence means.

It does not decide:

- whether to retry;
- whether to rebuild;
- whether to fall back;
- whether to quarantine;
- whether to notify an operator;
- whether to execute an irreversible mutation.

Those belong to separately owned decision, strategy-selection, attempt-
authorization, and execution responsibilities.

This separation prevents an apparently convenient status such as `ok = true`,
a retry-like result, or `FAST_PATH_UNAVAILABLE` from silently becoming
permission to act.

## Why Concurrency Is Also a Semantic Problem

An agent action can be valid when proposed and invalid when committed.

Two agents may independently produce reasonable actions from the same state. Once one action becomes accepted, the other may no longer preserve business meaning.

Compass therefore separates:

- semantic validation;
- transaction atomicity;
- concurrency admission.

A transaction can commit atomically while still admitting the wrong next fact.

A lock can serialize execution without proving that the serialized action remains semantically valid.

Final admission must therefore be grounded in the current accepted history, not merely in an earlier snapshot of state.

## Why Post-Hoc Observation Is Not Enough

Logs, traces, audits, dashboards, and evaluations are necessary.

But after a bad action has mutated durable state, observation may only explain how the damage occurred.

Worse, bad state rarely stays local. It can flow into:

- analytics;
- dashboards;
- retrieval systems;
- agent memory;
- audit trails;
- downstream workflows;
- training or fine-tuning data;
- future automated decisions.

A bad mutation can become future context.

Compass therefore emphasizes:

> **Admission before mutation, not only explanation after mutation.**

Evaluation improves the agent over time.

Admission protects the system at the moment where a candidate is about to become accepted truth.

## Multi-Agent Consensus Is Not Truth

Multiple agents can agree and still be wrong.

Agreement may only mean that several probabilistic systems shared the same flawed assumptions, contaminated context, or authority mistake.

A workflow can also launder authority: one agent without direct mutation permission may persuade another authorized agent to perform the action.

Compass does not treat consensus, orchestration, or delegation as proof of truth.

Every state-changing action must still cross the relevant admission boundary.

## The Compass Position

Compass is a runtime semantic admission protocol for agentic state mutation.

It preserves agent autonomy in proposing, reasoning, planning, and coordinating, while keeping authority over durable reality behind explicit, reviewable, and enforceable boundaries.

It separates:

- proposal from accepted fact;
- permission from authority;
- execution from meaning;
- evidence from decision;
- decision from strategy;
- strategy from action;
- derived state from accepted history;
- replay from retry permission;
- consensus from truth.

Compass does not assume agents are malicious.

It assumes they are powerful enough that their actions must be admitted, not merely executed.

## In One Sentence

> **Compass lets agents propose freely, but requires evidence, semantic validation, and concurrency admission before their proposals are allowed to become durable reality.**
