# Deterministic Autonomous-Governance Experiment

## Question

Can a deterministic planner propose one fresh same-request invocation while remaining unable to authorize or execute that proposal?

## Result

Yes.

This experiment demonstrates that proposal generation, re-invocation authority, and owner-local execution capability can remain separate even when they are composed into one deterministic recovery path.

The same planner proposal may lead to different executable consequences because proposal generation does not determine whether Stage 4E authority exists, and an issued authorization artifact does not itself constitute reusable execution capability.

```text
proposal
!=
authority
!=
execution
```

## Experiment topology

```text
complete RequestSignature
+
exact completed PostgresWriteSideResult
        ↓
DeterministicRecoveryPlanner
(plan_recovery)
        ↓
RecoveryProposal | None
```

The proposal is then composed with an independently evaluated Stage 4E result:

```text
                     ┌→ RecoveryProposal

A1 evidence ─────────┤

                     └→ Stage 4E assessment


RecoveryProposal
+
independent assessment
+
live owner custody
        ↓
ControlledExecutor
        ↓
PostgresWriteSideInvocationOwner
        ↓
one A2 or refusal
```

Stage 4E does not consume `RecoveryProposal`.

`ControlledExecutor` does not mint authority, does not evaluate Stage 4E, does not invoke the writer directly, and does not own the AVAILABLE/SPENT lifecycle.

The production invocation owner remains the one-shot capability boundary.

## Planner semantics

The deterministic planner is intentionally over-eager.

It proposes the same fresh-observation consequence for both:

```text
typed coherent append STALE_WRITE
```

and:

```text
generic evidence-less append STALE_WRITE
```

The planner therefore answers only a bounded proposal question:

> Does this completed append-conflict observation justify proposing one fresh same-request observation?

It does **not** establish:

- concurrency as the true cause;
- authoritative-state advancement;
- supersession of a stale premise;
- retryability;
- re-invocation authority; or
- executable capability.

Those distinctions remain outside the planner.

This is deliberate: the experiment needs the planner to be able to make the same proposal in cases where the authority layer later reaches different conclusions.

## Source custody

`RecoveryProposal` retains the exact supplied `RequestSignature` and `PostgresWriteSideResult`.

This source binding is experiment-local live custody.

It is **not**:

- durable provenance;
- restart-safe identity;
- hostile-code-safe source binding;
- distributed authority binding; or
- a transferable capability.

The experiment assumes trusted in-process composition supplies the exact A1 result returned by the bound invocation owner.

## Controlled execution

`ControlledExecutor` composes three already-existing facts:

```text
RecoveryProposal
+
independent Stage 4E assessment
+
live owner custody
```

It checks that the proposal, retained A1 result, request signature, and independently supplied authority assessment are compatible.

It does not reproduce the Stage 4E predicate.

It does not create authority.

It does not inspect or mutate the owner's private lifecycle state.

Its only execution path delegates to:

```text
PostgresWriteSideInvocationOwner.invoke_authorized_reinvocation()
```

A free-standing `ReinvocationAuthorization` is therefore not a transferable execution capability. The bound owner must still possess its own explicitly evaluated, positive, unspent authority.

## Positive PostgreSQL composition witness

The positive path is established against real PostgreSQL rather than a synthetic stale-write result.

```text
real PostgreSQL typed-forward append conflict
→ RecoveryProposal
→ independently evaluated Stage 4E authorization
→ ControlledExecutor
→ production invocation owner
→ one fresh A2
→ authoritative REPLAY
```

The deterministic schedule is:

```text
A1
→ enters the retained production writer
→ completes strict validation
→ pauses immediately before the real optimistic append

B
→ uses a separate PostgreSQL connection
→ submits the identical complete RequestSignature
→ commits first

A1 resumes
→ real PostgreSQL append observes version advancement
→ expected version = 0
→ observed version = 1
→ typed AppendVersionMismatchEvidence
→ STALE_WRITE
→ no accepted event
→ A1 rolls back
```

The completed A1 result is then used independently by two paths:

```text
A1 result
├─→ planner
│   → RecoveryProposal
│
└─→ Stage 4E
    → ReinvocationAuthorization
```

The executor delegates to the production invocation owner.

A2 re-enters the retained production writer as a **fresh invocation** and terminates at its fresh preliminary idempotency check with `REPLAY`.

The retained validation, gate-construction, and append-candidate observation counts remain unchanged across A2. Therefore A2 did not resume or reuse A1's:

- candidate;
- validation result;
- append attempt; or
- prior execution frame.

A second executor call propagates the owner's already-spent lifecycle failure.

The database remains at:

```text
order_events = 1
idempotency_records = 1
```

Only the legitimate accepted effect committed by B remains durable.

## Negative authority witness

The negative path deliberately preserves the planner's proposal while changing the authority outcome.

```text
generic evidence-less STALE_WRITE
→ same proposed action
→ NoReinvocationAuthority
→ ControlledExecutionRefused
→ no A2
```

This witness is deterministic unit composition using the production Stage 4E evaluator and invocation owner with a bounded writer double.

The planner still proposes one fresh same-request invocation.

Stage 4E does not authorize it.

The executor therefore refuses execution.

The important distinction is:

```text
same proposal
!=
same authority
!=
same executable consequence
```

A real PostgreSQL generic-stale negative schedule is intentionally outside the scope of this first experiment.

## One-shot capability witness

An issued authorization is not equivalent to unlimited retry authority.

The bound invocation owner retains the lifecycle:

```text
AVAILABLE
→ SPENT
```

The first valid execution may consume that authority and produce one A2.

A second execution attempt with the same proposal and authorization does not produce A3.

Therefore:

```text
authorization
!=
retry-until-success
```

and:

```text
authorization artifact
!=
reusable execution capability
```

## Established distinctions

This bounded experiment establishes the following distinctions:

- proposal is not authority;
- proposal generation is not recovery correctness;
- proposal generation is not execution;
- the same proposed action may receive different authority outcomes;
- an authority artifact is not owner-local available capability;
- authorization is not execution;
- one issued one-shot authority is not retry-until-success;
- a fresh same-request invocation is not resumption of old work; and
- owner-local capability state remains necessary even when proposal and authorization artifacts are externally available.

## Current experiment boundary

This experiment is intentionally narrow.

It does not implement or depend on:

- an LLM planner;
- `DecisionReceipt` as planner input;
- Stage 4C integration;
- Stage 4D strategy selection;
- generic retry;
- retry loops;
- retry budgets;
- backoff;
- a scheduler;
- A3;
- durable planner state;
- restart recovery;
- distributed planner state;
- distributed authority;
- capability tokens;
- cryptographic provenance;
- hostile-code-safe source binding;
- a production `ControlledExecutor`;
- a production planner API;
- a new authority profile;
- a new `STALE_WRITE` normalization; or
- Quotient Model v2.

The experiment establishes only the bounded composition needed to demonstrate that a deterministic machine-generated recovery proposal can remain separate from both authority and execution.
