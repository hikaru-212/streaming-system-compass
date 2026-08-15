# Reasoning Note — Retry Amplification, Local Correctness, and Semantic Diagnosis

[← Back to Reasoning Notes](README.md)

**Recorded on:** 2026-08-15

## Status

Exploratory reasoning note.

This document starts from an observed client-side failure experience and uses
it to reason about retry amplification, evidence boundaries, and system-level
failure interpretation.

It is not:

```text
an OpenAI incident report

a reconstruction of OpenAI's internal architecture

proof that a specific retry implementation exists

a root-cause analysis of the observed service behavior

a Stage 4B.5 production-evidence record
```

The concrete service internals are unknown.

Where this note moves from observation to a possible failure model, that
transition is stated explicitly.

---

## Triggering Observation

During one ChatGPT web session, the browser experience degraded significantly.

The observable sequence included behavior such as:

```text
slow or incomplete page behavior

repeated loading / refresh attempts

eventual "Too many requests" style failure
```

At the same time, other access paths did not appear to fail in exactly the same
way.

That observation is sufficient to ask an engineering question.

It is not sufficient to identify the internal cause.

The useful question is therefore not:

```text
What exactly did OpenAI implement incorrectly?
```

The useful question is:

```text
What classes of distributed-system behavior could transform
a small number of human recovery actions
into a much larger machine request load?
```

---

## Observed Facts and Hypothesized Mechanism Must Stay Separate

The observed facts are bounded:

```text
the web experience became slow

manual recovery actions occurred

a rate-related terminal message appeared
```

A plausible but unproven failure model is:

```text
slow or ambiguous request
        ↓
client/library/application retry
        ↓
another attempt begins before prior outcome is fully known
        ↓
multiple internal requests exist for one human intention
        ↓
additional latency / contention / rate pressure
        ↓
more retry or refresh behavior
        ↓
amplification
```

This is a useful model because it describes a known class of distributed-system
risk.

It must not be presented as evidence of the actual OpenAI implementation.

---

## Human Action Rate Is Not Machine Request Rate

A user may believe:

```text
I clicked refresh twice.
```

That does not establish:

```text
exactly two backend requests occurred.
```

One visible action may trigger:

```text
page bootstrap requests

authentication calls

conversation fetches

asset requests

stream reconnection

client retries

library retries

service-to-service retries

fallback calls
```

The important quantity is therefore not only:

```text
human actions per minute
```

but potentially:

```text
machine attempts per user intent
```

A distributed system can amplify a small amount of visible activity into much
larger internal work.

---

## Retry Is Not Neutral

Retry is often described as a reliability mechanism:

```text
request failed
→ try again
```

That description is incomplete.

A retry creates additional work.

Whether it improves reliability depends on the failure class and on what is
already happening elsewhere in the system.

Consider:

```text
original request is merely slow

client assumes failure

client retries

original request is still executing

retry is also executing
```

The system has not recovered one request.

It has created two attempts for one intent.

If many clients do the same thing:

```text
latency
→ retry
→ more load
→ more latency
→ more retry
```

The recovery mechanism can participate in the failure.

This is retry amplification.

---

## A Final Technical Status Does Not Explain the Failure Chain

Suppose the final observable result is:

```text
429 Too Many Requests
```

That status may accurately describe the final boundary.

It does not necessarily answer:

```text
Why did request pressure become high?

Was the original request already executing?

Did the client retry?

Did an SDK retry?

Did an upstream service retry?

Were multiple requests derived from one user action?

Was the rate limit protecting an already overloaded dependency?
```

Therefore:

```text
final technical status
≠
root cause
```

The same distinction appears elsewhere in runtime governance:

```text
technical status
≠
semantic interpretation
≠
diagnosis
≠
authorized response
```

A rate-limit result may be correct locally while the overall retry system is
behaving poorly.

---

## Local Correctness Does Not Guarantee System Correctness

Each component in a retry chain can be locally reasonable.

For example:

```text
browser:
request looks stalled → retry

SDK:
transport timeout → retry

service A:
dependency timeout → retry service B

rate limiter:
too many requests → reject
```

Every component may satisfy its own local rule.

The combined system can still produce:

```text
duplicate work

retry storms

queue growth

increased tail latency

rate-limit pressure

resource exhaustion
```

This is a general distributed-systems lesson:

```text
locally valid actions
can compose into globally harmful behavior
```

The same shape appears in multi-agent authority systems.

A workflow may consist entirely of individually permitted operations while the
composed path produces an effect that no individual permission boundary was
intended to authorize.

---

## Ambiguous Outcomes Make Retry Harder

Retry becomes especially difficult when the caller does not know whether the
previous attempt took effect.

For example:

```text
request sent

server performs side effect

connection disappears before response arrives
```

The caller sees:

```text
no confirmed success
```

but reality may be:

```text
side effect already committed
```

A blind retry can therefore duplicate effects.

This is why retry design is connected to:

```text
idempotency

request identity

commit ambiguity

reconciliation

deduplication

attempt lineage
```

A timeout is not enough information to decide whether another attempt is safe.

---

## Evidence Needed to Diagnose Amplification

A useful diagnosis would need to correlate one human intent with the machine
attempts derived from it.

Possible evidence includes:

```text
user_action_id

request_id

parent_request_id

attempt_number

request_started_at

request_completed_at

latency

timeout boundary

retry_reason

retry_owner

backoff selected

rate-limit decision

final response

downstream request identities
```

With such evidence, one could ask:

```text
How many attempts came from one intent?

Which layer created each retry?

Was the previous attempt still active?

Did multiple attempts overlap?

Which retry reason dominated?

Did latency rise before retry volume?

Did retry volume rise before rate limiting?
```

Without correlation evidence, a final `429` tells very little about the path
that produced it.

---

## Retry Ownership Matters

A particularly dangerous system is one in which retry ownership is unclear.

For example:

```text
browser retries

HTTP library retries

SDK retries

service retries

queue consumer retries
```

If each layer independently assumes:

```text
I am responsible for recovery
```

the effective retry budget becomes the product of several local policies.

A simplified example:

```text
client: 3 attempts

service A: 3 attempts per client attempt

service B: 2 attempts per A attempt
```

One user intent may create as many as:

```text
3 × 3 × 2
= 18 downstream attempts
```

The problem is not that any single retry count is obviously extreme.

The problem is composition.

---

## Backoff Helps but Does Not Establish Authorization

Exponential backoff and jitter can reduce synchronization and immediate load.

They do not answer the more fundamental question:

```text
Should this operation be retried at all?
```

A retry system therefore needs at least two separate questions:

```text
1. Is another attempt authorized?

2. If authorized, when should it occur?
```

Backoff answers mainly the second.

It does not prove the first.

---

## Circuit Breakers and Backpressure Address a Different Boundary

When a dependency is unhealthy, continuing to send work can make recovery
slower.

Mechanisms such as:

```text
circuit breakers

concurrency limits

load shedding

queue limits

backpressure

retry budgets
```

attempt to limit that amplification.

Again, these are not interchangeable.

For example:

```text
retry policy
= whether another attempt is justified

backoff
= when another attempt should occur

circuit breaker
= whether calls to a failing dependency should temporarily be admitted

rate limiter
= how much request activity is permitted

idempotency
= whether repeated intent can safely converge on one effect
```

Treating all of these as "retry logic" hides important authority boundaries.

---

## Failure Observed Is Not Retry Authorization

The strongest architectural conclusion from this reasoning is:

```text
failure observed
≠
retry permitted
```

Even when retry is permitted:

```text
retry permitted
≠
retry immediately
```

and:

```text
retry permitted
≠
retry with the same candidate
```

For a semantic failure, the existing candidate may be known to violate a stable
correctness proposition.

Repeating it unchanged is not recovery.

It is reproduction of the same invalid state.

---

## Connection to Stage 4B.5

Stage 4B.5 provides a useful prerequisite for future Retry Governance.

Before Stage 4B.5, a later policy might receive:

```text
FAILED

BLOCK

reason = "candidate previous version does not match..."
```

After Stage 4B.5 it can receive:

```text
SemanticOutcome
+
OrderRuleViolationEvidence(
    rule_id =
        order.transition.proof-prev-version-matches-accepted
)
```

That evidence still does not authorize retry.

But it gives a future policy a stable input for deciding:

```text
Is another attempt meaningful?

Can a new candidate differ in a way that addresses this failure?

Does the authoritative state need to be re-read first?

Would retry reproduce the same invalid proposition?

Should the request stop instead?
```

This is why Stage 4B.5 rule evidence and future retry decision evidence should
remain separate.

---

## Possible Future Runtime Shape

A future workflow may look conceptually like:

```text
Candidate A
        ↓
runtime validation
        ↓
SemanticOutcome
+
RuleViolationEvidence
        ↓
Retry Governance
        ↓
RetryDecisionEvidence
        ↓
AUTHORIZED
/ DENIED
/ REQUIRES_REFRESH
/ REQUIRES_DIFFERENT_CANDIDATE
/ REQUIRES_OPERATOR
        ↓
optional Candidate B
```

The important part is not the exact vocabulary.

The important part is that:

```text
observed failure evidence
```

does not directly trigger:

```text
execution
```

An explicit governance boundary stands between them.

---

## What This Note Does Not Know

This reasoning does not establish:

```text
which ChatGPT web-client component retried

whether a browser retry occurred

whether an SDK retry occurred

whether an OpenAI service retried internally

whether requests overlapped

whether the observed rate limit was caused by retry amplification

which rate-limit algorithm was involved
```

Those questions require system telemetry that is not available here.

The value of the observation is not that it proves a particular internal
architecture.

Its value is that it exposes a useful failure model worth understanding and
simulating.

---

## A Useful Simulation

The failure shape can be studied without reproducing any real service.

A local lab could model:

```text
Client
        ↓
Service A
        ↓
Service B
```

Then introduce:

```text
increasing latency

ambiguous timeout

client retry

service retry

fixed retry budgets

jitter

circuit breaking

idempotency identity
```

Useful observations would include:

```text
logical user intents

machine attempts

concurrent in-flight attempts

successful effects

duplicate effects

queue depth

tail latency

retry amplification factor
```

The goal would not be to reproduce the observed ChatGPT incident.

It would be to understand how local recovery policies compose.

---

## Engineering Questions Worth Carrying Forward

The observation leaves a set of reusable review questions:

```text
Who owns retry?

What exact evidence authorizes another attempt?

Can more than one layer retry the same intent?

Is the previous attempt known to have failed?

Can an ambiguous previous attempt already have committed?

Does the retry reuse the same candidate?

What must change before another candidate is meaningful?

What is the retry budget across the full call graph?

What prevents retry from increasing the failure it is trying to recover from?

Can one user intent be traced across every machine attempt?
```

These questions apply to ordinary distributed systems and to agent-driven
workflows.

---

## Learning Direction

The useful follow-up areas are not tied to one vendor implementation.

They include:

```text
HTTP request and connection lifecycle

browser and SDK retry behavior

timeouts and ambiguous outcomes

idempotency and deduplication

retry budgets

exponential backoff and jitter

circuit breakers

load shedding and backpressure

rate limiting

request lineage and observability

distributed tracing

semantic retry governance
```

The goal is not to treat every transient failure as evidence of retry
amplification.

The goal is to know what evidence would distinguish:

```text
one slow request

from

one intent that became many attempts
```

---

## Final Takeaway

The key system-level lesson is:

```text
A retry can be locally correct
and still contribute to a globally incorrect recovery process.
```

Therefore a robust system should not reduce retry to:

```text
failure
→ try again
```

A stronger model is:

```text
failure observation
        ↓
evidence
        ↓
semantic diagnosis
        ↓
explicit retry authorization
        ↓
bounded retry strategy
        ↓
new attempt, if permitted
```

That separation is the part worth carrying forward.
