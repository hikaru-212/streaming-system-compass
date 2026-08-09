# Causal Failure Modeling: From Failure Classification to Failure Genesis

[← Back to Semantic Admission](README.md)

## Purpose

This note records a public-facing design concept for Compass-style semantic admission systems.

The immediate example is an idempotency conflict:

```text
same request_id
+ different semantic payload
→ idempotency conflict
```

A normal failure model can classify and block this conflict.

A causal failure model asks a deeper question:

```text
How was the invalid candidate generated in the first place?
```

This distinction matters because semantic admission should not only detect bad candidates at the boundary.

It should also preserve the evidence shape needed to understand whether a candidate is a true replay, a regenerated action, a correction, a stale reconstruction, or a mutable-state artifact.

---

## Core Idea

Failure modeling can be separated into several levels.

```text
failure classification
→ failure handling
→ failure evidence
→ failure lineage
→ failure genesis
```

Each level answers a different question.

---

## Level 1 — Failure Classification

Failure classification asks:

```text
What can go wrong?
```

Examples:

```text
timeout
duplicate request
idempotency conflict
stale write
lock timeout
infrastructure error
validation failure
snapshot drift
missing accepted history
```

This level names the failure.

For example:

```text
same request_id + different payload
→ IDEMPOTENCY_CONFLICT
```

This is useful, but limited.

It tells the system what type of failure was observed, but not how the failure was generated.

---

## Level 2 — Failure Handling

Failure handling asks:

```text
What should the system do when the failure appears?
```

Examples:

```text
timeout → retry
lock timeout → retry with backoff
idempotency conflict → block
infrastructure error → escalate
semantic validation failure → reject candidate
snapshot missing → fallback to authority replay
```

This level connects failures to runtime reactions.

However, it should not be introduced too early in the semantic pipeline.

For Compass-style governance, semantic interpretation should remain separate from runtime action.

```text
technical evidence
≠
semantic outcome

semantic outcome
≠
runtime decision

runtime decision
≠
execution strategy

retry attempt
≠
intent preservation
```

A mapping layer may conclude that an idempotency conflict means semantic conflict was detected.

It should not also decide retry, fallback, escalation, or strategy execution.

---

## Level 3 — Failure Evidence

Failure evidence asks:

```text
What evidence proves that this failure occurred?
```

For an idempotency conflict, the evidence may include:

```text
same request_id
different semantic signature
prior idempotency record exists
new request payload does not match the prior signature
prior accepted event exists or is referenced when applicable
```

At this level, the concern is not only classification.

The concern is evidence integrity.

For example:

```text
accepted_event_id must only refer to accepted history
candidate_event_id identifies a candidate that may still be rejected
rejected candidates must not be exposed as accepted_event_id
technical_status evidence must not contradict the mapped status
order_id lineage must not contradict itself across evidence sources
request_id lineage must not contradict itself across evidence sources
```

This matters because later governance layers may preserve evidence in durable
receipts or expose it through non-durable diagnostic traces.

Bad evidence should not become accepted governance or diagnostic truth.

---

## Level 4 — Failure Lineage

Failure lineage asks:

```text
Where was the failure observed?
Where may it have originated?
How did it propagate?
What downstream layer could misinterpret it?
```

This separates observation boundary from root cause.

For example:

```text
NO_ACCEPTED_HISTORY_FOR_ORDER
```

may be observed by a read-side validator.

That does not prove the write-side failed.

It only proves that the read-side validator could not establish authority-backed evidence for that order.

Similarly:

```text
TAIL_EVENT_SOURCE_CONTRACT_VIOLATION
```

does not prove semantic drift.

It means the snapshot-assisted path could not safely complete tail replay.

If comparison did not complete, drift has not been proven.

At this level, failure is modeled as a chain:

```text
origin candidate
→ propagation path
→ observation boundary
→ semantic interpretation
→ possible downstream misinterpretation
```

This prevents the system from jumping from observation to unsupported root-cause claims.

---

## Level 5 — Failure Genesis

Failure genesis asks:

```text
How was the invalid candidate generated in the first place?
```

For idempotency conflict, the deeper question is not only:

```text
Can the system detect same request_id + different payload?
```

The deeper question is:

```text
Why did the system produce a different semantic payload while preserving the same request identity?
```

This is a generation problem, not only a classification problem.

The invalid state may be produced by several broad classes of upstream behavior:

```text
request identity and payload lifecycle become disconnected
retry reconstructs payload from mutable state
semantic payload is evaluated lazily
idempotency key scope is too broad
an automated workflow regenerates intent while preserving old identity
a correction flow reuses the original command identity
```

The exact scenario is less important than the invariant:

```text
request identity
semantic signature
payload snapshot
candidate action identity
```

must remain coherent if a retry is intended to be a replay of the same semantic intent.

---

## Example: Same Request Identity, Different Semantic Payload

Surface-level failure:

```text
request_id = req-001
payload = PAY 100
```

Later:

```text
request_id = req-001
payload = PAY 200
```

The system observes:

```text
same request_id
different semantic payload
```

and classifies:

```text
IDEMPOTENCY_CONFLICT
```

The failure genesis question is:

```text
Why was PAY 200 generated under req-001?
```

The important observation is:

```text
operational identity stayed stable
semantic intent changed
```

Operationally, the two candidates look related.

Semantically, they are different candidate actions.

A semantic admission system must prevent operational identity from collapsing semantic identity.

---

## Implications for Testing

A normal unit test may assert:

```text
same request_id + different payload
→ IDEMPOTENCY_CONFLICT
```

That is useful.

But it only tests the boundary after the invalid state already exists.

A deeper scenario test asks:

```text
What upstream sequence generated this invalid candidate?
```

Future failure-genesis tests may model broad patterns such as:

```text
mutable input state changes after request identity is assigned
retry reconstructs payload instead of replaying the original payload snapshot
workflow regeneration preserves old request identity
idempotency key scope allows different semantic commands to collide
correction command reuses original command identity
candidate identity leaks into accepted-event context
validation evidence becomes stale before append
```

These tests are not ordinary mapper tests.

They model how bad evidence is born before it reaches the semantic admission boundary.

---

## Relationship to Compass

Compass is based on the principle:

```text
candidate action
≠
accepted fact
```

Failure genesis modeling goes one step earlier.

It asks:

```text
How did this candidate action get generated?
Was it a true replay?
Was it a regenerated action?
Was it a correction?
Was it a stale reconstruction?
Was it a mutable-state artifact?
```

This matters because two candidate actions can look operationally related while being semantically different.

For example:

```text
same request_id
+ different payload
```

may look like one operational request.

But semantically, it may represent two different candidate actions.

Compass must prevent operational identity from collapsing semantic identity.

---

## Core Invariant

A retry must replay the original semantic intent.

It must not reuse the same request identity while regenerating a new semantic intent.

Therefore, a safe retry system should preserve:

```text
request_id
semantic signature
payload snapshot
candidate action identity
```

as one coherent unit.

If request identity is stable but payload is mutable, the system can generate semantic idempotency conflicts.

---

## Current Classification

This note is a non-authoritative public conceptual follow-up.

Its original source classification was:

```text
Future Stage 4B.1 / Stage 4E design note
```

That classification is now historical because Stage 4B.1 is complete. The
current classification is:

```text
Stage 4B.1-informed
post-Stage-4B.1 causal-governance design note
```

Its likely primary revisit is around:

```text
Stage 4E
Retry Governance
AttemptLog
intent consistency
```

Earlier concrete consumers may expose a narrower need, but this note does not
create an implementation commitment or reopen the completed Stage 4B.1 stage.

### Relationship to the Completed Stage 4B.1 Boundary

Stage 4B.1 `DiagnosticTrace` / `ResolutionTrace` supplies bounded evidence
about what happened during one execution. It preserves meaningful
execution-local failure evidence and bounded execution topology.

The current write-side `DiagnosticTrace` remains in-memory diagnostic evidence;
it is not durable governance evidence. Durable `DecisionReceipt` evidence
remains a separate responsibility.

Causal failure modeling asks a different question:

```text
How was an invalid candidate or semantic conflict generated upstream?
```

The current system can often identify where a failure was observed. It does
not generally preserve complete:

```text
candidate-generation lineage
cross-attempt causal lineage
mutable-input provenance
retry-regeneration provenance
```

Full causal failure genesis is therefore not implemented. This distinction
does not make Stage 4B.1 incomplete; it identifies a later causal-governance
problem outside that completed stage.

Potential future investigation areas remain:

```text
Retry Governance / AttemptLog / intent consistency
failure scenario generators
evidence-shape tests
semantic boundary tests
```

These are candidate consumers and research directions, not runtime contracts.

### Future Provenance Remains Deferred

Causal reasoning reinforces why provenance design should remain deferred until a
concrete consumer establishes its needs. The future problem may be broader than
binding a Result and Trace from one execution. It may need to serve:

```text
execution provenance
attempt provenance
candidate genesis
semantic-intent preservation
```

This note does not introduce or choose `execution_id`, `attempt_id`, opaque
provenance tokens, persistent provenance records, or cryptographic binding.
Identity and persistence design remain open for later architectural review.

---

## Takeaway

A failure model should not stop at:

```text
This failure can happen.
```

For semantic admission systems, the deeper question is:

```text
What sequence of state changes, identity mistakes, mutable inputs, retries, or regeneration steps produced this invalid candidate?
```

That is the purpose of causal failure modeling.
