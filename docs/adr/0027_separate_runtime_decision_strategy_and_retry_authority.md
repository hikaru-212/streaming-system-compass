# ADR 0027: Separate Runtime Decision, Strategy, and Retry Authority

[← Back to ADR Index](README.md)

## Status

Accepted

## Implementation Status

This ADR establishes the docs-first authority boundary for the Stage 4C+
decision-governance phase.

No production `RuntimeDecision`, strategy selector, retry-governance component,
execution mechanism, persistence schema, or attempt record is implemented by
this decision.

---

## Decision Scope

This decision separates:

```text
Stage 4C
= current-observation Runtime Decision Authority

Stage 4D
= Strategy Selection Authority inside an already-permitted action

Stage 4E
= Retry / Attempt Authorization

execution
= a separate boundary after authorization and strategy selection
```

It also records the evidence posture for the first Stage 4C–4E delivery:
live, in-memory governance is the first design center, while restart-recovery
governance remains a distinct deferred consumer.

This ADR decides responsibility. It does not decide implementation shape.

## Context

The completed Stage 4 foundation preserves several deliberately separate
meanings:

```text
technical status
!= SemanticOutcome
!= exact rule refinement
!= diagnosis
!= RuntimeDecision
!= strategy
!= retry authorization
!= retry execution
```

Stage 4A introduced `SemanticOutcome`. Stage 4B introduced durable
`DecisionReceipt` governance evidence. Stages 4B.1 and 4B.2 added bounded
producer-specific execution and measurement evidence. Stage 4B.3 closed as not
currently justified under ADR 0026. Stage 4B.5 completed Order Correctness
Contract V0 with 18 stable rules; exactly six FullProof `TRANSITION_TRUTH` rules
currently have typed runtime producer coverage.

The older Stage 4 planning material assigned Stage 4C a generic runtime-action
role, but also proposed retry-specific actions and fields such as:

```text
RETRY_AFTER_RELOAD
RETRY_WITH_BACKOFF
retry_allowed
max_attempts
```

That shape collapses current-response authority and cross-attempt authority.
It conflicts with the later Stage 4E responsibility for retry classification,
attempt safety, reload requirements, attempt limits, intent consistency, and
cross-attempt lineage.

The roadmap also contained Stage 4D examples in which a strategy selector could
appear to authorize `REBUILD`, `QUARANTINE`, or `ESCALATE`. Those are generic
current-response decisions when they answer what the runtime may or must do now;
they are not independently created by strategy selection.

## Decision

### Stage 4C Owns Current-Observation Runtime Decision Authority

Stage 4C answers:

> Given the current semantic observation and eligible supporting evidence,
> what generic current response or action is permitted, required, or denied?

Stage 4C may authorize or require generic current responses such as allowing,
blocking, replaying a prior accepted result, falling back to authority,
rebuilding, quarantining, or escalating.

`REBUILD`, `QUARANTINE`, and `ESCALATE` are Stage 4C-level decisions when they
describe what is permitted or required for the current observation. Their exact
names and representation are not frozen by this ADR.

Stage 4C does not:

- execute an action;
- select an execution strategy;
- authorize another attempt;
- define retry count or budget;
- define backoff or retry timing;
- authorize retry after reload;
- own prior-attempt lineage or cross-attempt governance.

`RETRY_AFTER_RELOAD` and `RETRY_WITH_BACKOFF` are not Stage 4C runtime actions.
`retry_allowed` and `max_attempts` are not Stage 4C runtime-decision fields.

### Stage 4D Owns Strategy Selection Inside Prior Authorization

Stage 4D answers:

> Given an already-permitted action, which eligible execution path or strategy
> should implement it?

Eligible paths may include authority replay, qualified snapshot-assisted
resolution, `PRE_TRANSACTION` plus optimistic concurrency control,
`IN_TRANSACTION` plus pessimistic admission, or another semantically permitted
execution path.

Stage 4D may choose how an already-authorized response is performed. It must not
independently create authority for `REBUILD`, `QUARANTINE`, `ESCALATE`, or any
other generic action.

### Stage 4E Owns Retry and Attempt Authorization

Stage 4E answers:

> Is another attempt authorized, and if so, under which explicit constraints?

Stage 4E exclusively owns:

- retry and attempt classification;
- whether another attempt is allowed;
- retry safety;
- reload-before-retry and revalidation-before-retry requirements;
- backoff and timing constraints;
- total and per-class attempt limits and attempt budget;
- same-candidate versus regenerated-candidate constraints;
- intent consistency;
- prior-attempt lineage and cross-attempt governance.

Current-attempt failure does not authorize another attempt. Retry authorization
does not execute a retry, permit reuse of the same candidate, or grant unlimited
attempts.

### Execution Remains Separate

A runtime decision authorizes or denies a response; it does not execute that
response. A retry decision authorizes or denies another attempt; it does not
perform that attempt.

For a later attempt, the conceptual handoff may be:

```text
current execution evidence
→ Stage 4C current-response decision
→ Stage 4E attempt authorization
→ Stage 4D strategy selection for the authorized attempt
→ execution
```

This does not make `C → D → E` a mandatory irreversible runtime pipeline.
Normal executions that do not consider another attempt do not need to pass
through Stage 4E.

## First-Delivery Evidence and Process-Lifecycle Boundary

The first Stage 4C–4E delivery is primarily live, in-memory runtime governance:

```text
process remains alive
→ live in-memory runtime governance

process is lost or restarted
→ restart-recovery governance
```

For the normal live hot path, the first design center is:

```text
SemanticOutcome
+ terminally applicable exact rule refinement when source-applicable
```

For the current PostgreSQL write-side producer,
`PostgresWriteSideSemanticRuleFeedback` is a useful source-specific composition
because it preserves one `SemanticOutcome` plus terminally applicable
`OrderRuleViolationEvidence`. This ADR does not make that producer-specific
carrier a universal Stage 4C abstraction.

`DecisionReceipt` remains durable governance evidence. It is not required as a
normal first-slice live Stage 4C or Stage 4E hot-path input, and the live path
does not require receipt persistence before making an in-process decision.
This decision does not limit receipts to restart recovery; other concrete
durable governance consumers may continue to use them without turning them
into authorization.

Restart-recovery governance is a distinct deferred consumer. A later restart or
recovery path may use durable receipts for reconstruction, delayed
reconciliation, operator investigation, governance continuation, or recovery of
semantic context after in-memory artifacts have been lost. This ADR does not
design that path.

Durable evidence is not permanent authorization. A future restart path must not
replay an old action merely because a `DecisionReceipt` exists.

## Consequences

### Positive

- Current-response authority cannot silently authorize another attempt.
- Retry limits, reload requirements, backoff, and lineage have one owner.
- Strategy selection remains constrained by semantic authorization.
- Authorization remains distinguishable from execution.
- The first live path can consume the semantic evidence already available in
  one process without requiring receipt persistence as a prerequisite.
- Durable evidence remains available for later recovery and governance
  consumers without being treated as permanent authorization.

### Negative / Deferred

- Stage 4C cannot by itself complete a retry loop.
- Stage 4E needs a source-grounded attempt model before implementation.
- The Stage 4D/4E handoff must be explicit whenever a new attempt needs a new
  strategy.
- Restart-recovery governance, durable runtime decisions, and cross-runtime
  continuation remain deferred until a concrete consumer exists.

## Alternatives Considered

### Keep retry-specific actions and fields in Stage 4C

Rejected because it would make current-observation action authority also own
cross-attempt safety, budgets, timing, and lineage.

### Let Stage 4D choose rebuild, quarantine, or escalation independently

Rejected because strategy selection would create action authority instead of
operating inside prior authorization.

### Require every execution to follow C → D → E

Rejected because Stage 4E is relevant only when another attempt is considered.
For an authorized later attempt, E may precede D's strategy choice.

### Require DecisionReceipt for every live decision or retry

Rejected for the first delivery because the live in-process semantic artifacts
already exist, while persistence and restart recovery are different lifecycle
problems. This rejection does not reduce the importance of durable receipt
evidence.

### Freeze a universal evidence envelope now

Rejected because the first source-grounded inputs are already known and no
concrete multi-producer policy consumer justifies a new wrapper.

## Non-Goals

This ADR does not freeze or introduce:

- Python class names;
- exact enum values beyond the ownership exclusions in this decision;
- a policy-engine implementation;
- a strategy or retry algorithm;
- a persistence schema;
- an `AttemptLog` schema;
- durable `RuntimeDecision` storage;
- a universal evidence envelope;
- retry execution;
- restart-recovery implementation;
- production code, tests, or migrations.

## Relationship to Existing Decisions

ADR 0016 remains authoritative that `DecisionReceipt` is durable governance
evidence rather than application logging or an attempt log.

ADR 0018 remains authoritative that producer receipt adapters preserve evidence
without evaluating governance flags and that `NOT_EVALUATED` is not `FALSE`.

ADR 0026 remains authoritative for the Stage 4B.3 closeout and re-entry
boundary. This decision does not imply that Projection Trust Continuation was
implemented.

## Current Decision Summary

```text
Stage 4C
= current-response authority

Stage 4D
= strategy inside prior authorization

Stage 4E
= another-attempt authorization and constraints

authorization
!= execution

live in-memory governance
!= restart-recovery governance

DecisionReceipt available
!= DecisionReceipt required for the first live hot path
```
