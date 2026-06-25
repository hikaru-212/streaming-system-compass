# Note: TTL and Event-Driven Invalidation for Source-Grounded AI Overviews

[← Back to AI Governance Index](README.md)

**Recorded on:** 2026-06-23

## Purpose

This note records a possible optimization strategy for source-grounded semantic admission of AI-generated summaries.

The earlier idea was:

```text
generated summary
→ structured claim extraction
→ source-grounded verification
→ semantic outcome
→ runtime decision
→ admit / retry / block / review
```

That architecture improves semantic safety, but it also increases cost and latency.

If every user query triggers a full generation and verification loop, the system may become too expensive for high-traffic search or overview-style products.

This note explores a practical optimization:

```text
verified AI overview
→ cache as temporary admitted output
→ serve repeatedly within TTL
→ regenerate only after expiration or meaningful source-change signal
```

The goal is to reduce repeated LLM generation while preserving a clear semantic admission boundary.

---

## Problem

LLM-generated summaries are not naturally stable.

The same query may produce different summaries at different times because of:

```text
sampling randomness
retrieval ranking changes
source-page changes
context assembly changes
model/runtime updates
cache differences
```

If the system regenerates an AI Overview every time a user opens the result, then the output may behave like a non-deterministic runtime artifact.

For example:

```text
10:00 query → Overview A
10:01 query → Overview B
10:02 query → Overview C
```

Even if the source links remain mostly the same, small changes in retrieval order or context construction can produce different language-level outputs.

This creates two problems:

1. **Cost explosion**
   Full semantic admission may require generation, source reading, claim extraction, evidence verification, and possibly retry.

2. **Semantic instability**
   A high-risk claim may appear in one generated version but not another.

The system therefore needs a way to reduce unnecessary regeneration.

---

## Core Idea

The core idea is to treat a verified overview as a temporary admitted artifact.

Once a generated overview passes source-grounded semantic admission, the system stores it with:

```text
query identity
source snapshot identity
structured claims
verification outcome
runtime decision
created_at
expires_at
TTL policy
invalidation policy
```

Then, for a defined period of time, the system serves the same admitted overview instead of regenerating a new one.

The basic flow becomes:

```text
User query
    ↓
Check admitted overview cache
    ↓
If cache hit and still valid:
    return cached admitted overview
    ↓
If cache miss, expired, or invalidated:
    run generation + semantic admission loop
    ↓
If admitted:
    store new overview with TTL
    return admitted overview
```

This does not eliminate uncertainty permanently.

It creates temporary determinism inside a bounded time window.

---

## Why TTL Helps

TTL helps because it turns repeated probabilistic generation into a controlled refresh cycle.

Without TTL:

```text
every query
→ regenerate
→ reverify
→ possible new semantic drift
→ high cost
```

With TTL:

```text
first query
→ generate
→ verify
→ admit
→ cache

later queries within TTL
→ reuse admitted output
```

This gives the system three benefits.

### 1. Cost Control

The expensive path is only triggered on cache miss, TTL expiration, or explicit invalidation.

For high-traffic queries, this can reduce cost dramatically.

For example:

```text
first query in window:
    full LLM generation + verification loop

next 100,000 queries in same window:
    serve cached admitted overview
```

The system pays the semantic admission cost once per TTL window instead of once per user request.

---

### 2. Output Stability

TTL reduces short-term randomness.

Users do not see a different overview every minute merely because the model sampled differently or the retrieval context shifted slightly.

Inside the TTL window, the overview behaves like a stable admitted artifact.

This matters especially for high-risk claims, where random wording changes can create legal, financial, or reputational risk.

---

### 3. Auditability

If the admitted overview is stored with its source snapshot and verification outcome, the system can later explain:

```text
what was generated
which sources were used
which claims were extracted
which evidence supported or contradicted those claims
which runtime decision admitted the output
when it was admitted
when it expired
why it was invalidated
```

This makes the output governable instead of ephemeral.

---

## TTL Is Not Enough

TTL alone creates a new risk:

```text
staleness
```

If the world changes during the TTL window, the cached overview may become outdated.

For low-change topics, this may be acceptable.

For fast-moving topics, it can become dangerous.

Example:

```text
10:00 admitted overview:
    Company X has no confirmed fraud involvement.

10:15 breaking news:
    Company X is officially charged with fraud.

TTL = 6 hours

10:30 user query:
    system still serves the old cached overview
```

In this case, the system avoided hallucination but created freshness risk.

So TTL must not be the only invalidation mechanism.

---

## Event-Driven Invalidation

A better design combines TTL with event-driven invalidation.

The overview remains cached until one of two things happens:

```text
TTL expires
OR
a meaningful source-change event invalidates the cache
```

This creates a hybrid policy:

```text
time-based refresh
+
event-based refresh
```

Possible invalidation signals include:

```text
new high-authority source appears
source page content changes materially
search ranking changes significantly
breaking-news signal appears
high-risk keywords appear in new sources
legal / financial / medical status changes
trusted feed emits update
manual reviewer invalidates output
model or policy version changes
```

For example:

```text
cached overview TTL = 6 hours

but if a new trusted article appears with:
    "charged"
    "lawsuit"
    "fraud"
    "money laundering"
    "recall"
    "death"
    "security breach"

then invalidate cache immediately
and force a new generation + admission loop
```

This avoids treating time as the only source of truth.

---

## Suggested Cache Validity Model

A cached admitted overview should not only be marked as present or absent.

It should carry a trust state.

Possible states:

```text
VALID
EXPIRED
INVALIDATED_BY_SOURCE_CHANGE
INVALIDATED_BY_POLICY_CHANGE
INVALIDATED_BY_MODEL_CHANGE
INVALIDATED_BY_MANUAL_REVIEW
PENDING_REVALIDATION
BLOCKED
```

Example:

```json
{
  "overview_id": "overview_123",
  "query_key": "publisher X fraud",
  "status": "VALID",
  "created_at": "2026-06-23T10:00:00Z",
  "expires_at": "2026-06-23T16:00:00Z",
  "source_snapshot_id": "snapshot_456",
  "semantic_decision": "ALLOW",
  "risk_level": "HIGH",
  "invalidation_policy": {
    "ttl_hours": 6,
    "event_driven": true,
    "watch_terms": ["fraud", "lawsuit", "charged", "money laundering"],
    "trusted_sources_required": true
  }
}
```

---

## Risk-Based TTL Policy

Different topics should use different TTLs.

A single global TTL is too crude.

A better approach is risk-based and freshness-based.

Example policy:

```text
Low-risk / slow-changing:
    TTL = 24 hours to 7 days

Medium-risk:
    TTL = 6 to 24 hours

High-risk reputation / legal / financial:
    TTL = 1 to 6 hours
    event-driven invalidation required

Breaking news / market / public safety:
    TTL = minutes
    event-driven invalidation required
    may require warning or no summary

Critical domains:
    no cached overview without strong source snapshot
    possible human review
```

This means TTL is not merely a performance optimization.

It is part of the runtime trust policy.

---

## Relationship to Source-Grounded Admission

TTL should only apply after admission.

The system should not cache raw generated text merely because it was generated.

The correct sequence is:

```text
generate candidate overview
→ extract structured claims
→ verify claims against source snapshot
→ produce semantic outcome
→ runtime decision allows output
→ cache admitted overview with TTL
```

Caching before admission would only preserve unverified output.

The correct artifact to cache is:

```text
admitted overview
```

not:

```text
candidate overview
```

This distinction matters.

A cached hallucination is worse than a temporary hallucination because it can be repeatedly served at scale.

---

## Relationship to Accepted History

The cached admitted overview is not permanent truth.

It is closer to a temporary projection derived from source evidence.

The source snapshot and verification outcome are the evidence boundary.

The cached overview is a derived artifact.

Therefore, the system should treat it as:

```text
derived
time-bounded
source-linked
revalidatable
discardable
```

This is similar in spirit to projection snapshots in Compass.

A snapshot is useful for efficiency, but it is not the authority.

Likewise:

```text
source evidence = authority
verified overview = derived admitted artifact
cache = efficiency mechanism
```

The cache improves performance.

It should not replace source-grounded verification as the trust boundary.

---

## Failure Modes

This optimization introduces several failure modes.

### 1. Stale Truth

The cached overview was correct when admitted, but the world changed.

Mitigation:

```text
event-driven invalidation
shorter TTL for high-risk topics
source freshness checks
trusted update feeds
```

---

### 2. Cached Hallucination

The verifier mistakenly admitted a bad overview, and the cache repeatedly serves it.

Mitigation:

```text
stricter admission for high-risk claims
claim-level evidence requirement
manual review for severe claims
post-admission monitoring
rapid invalidation path
```

---

### 3. Over-Invalidation

The system invalidates too often and loses the cost benefits of caching.

Mitigation:

```text
risk-tiered invalidation
source authority scoring
material-change detection
deduplication of update events
```

---

### 4. Under-Invalidation

The system misses a meaningful source change.

Mitigation:

```text
watch high-risk entities
monitor trusted sources
compare source snapshots
track important claim predicates
```

---

### 5. Policy Drift

The overview was admitted under an older policy that would no longer allow it.

Mitigation:

```text
store policy_version
invalidate on policy change
revalidate high-risk cached outputs
```

---

## Minimal Version

A minimal implementation does not need to solve everything.

The first version could be:

```text
1. Generate overview.
2. Extract high-risk claims.
3. Verify claims against sources.
4. If admitted, cache overview for a fixed TTL.
5. Serve cached overview until TTL expires.
6. On expiration, regenerate and reverify.
```

This already reduces cost and short-term randomness.

A later version can add:

```text
event-driven invalidation
risk-based TTL
source snapshot diffing
policy-version invalidation
manual review for severe claims
```

---

## Stronger Version

A stronger version would use:

```text
query_key
entity_key
risk_type
source_snapshot_hash
overview_hash
claim_hashes
verdicts
decision
policy_version
model_version
created_at
expires_at
invalidated_at
invalidation_reason
```

This allows the system to answer:

```text
Why did users see this overview?
Which source evidence supported it?
Was it still valid at that time?
Was it later invalidated?
Which policy admitted it?
```

This is important for governance and auditability.

---

## Reusable Principle

The reusable principle is:

```text
Do not regenerate probabilistic summaries more often than necessary.
```

But the deeper principle is:

```text
Only admitted semantic artifacts should be cached.
```

The architecture should be:

```text
candidate generation
→ semantic admission
→ admitted output cache
→ TTL / event-driven invalidation
→ regeneration only when needed
```

This turns randomness into a controlled refresh problem.

It also turns expensive verification into an amortized cost.

The system no longer asks:

```text
Should the model generate a new answer every time?
```

It asks:

```text
Is the currently admitted answer still valid enough to serve?
```

That is a better systems question.

---

## Summary

TTL and caching can make source-grounded semantic admission more practical.

The architecture is:

```text
generate once
verify once
admit once
serve many times
invalidate when time or events require it
```

TTL reduces cost and short-term output randomness.

Event-driven invalidation reduces staleness risk.

Together, they create a practical control layer around LLM-generated overviews:

```text
LLM generation is probabilistic.
Admitted output should be governed.
Cache should preserve only admitted output.
TTL controls regeneration frequency.
Events control freshness failure.
```

This is not a replacement for semantic admission.

It is an optimization layer above it.

The final boundary is:

```text
source evidence remains the authority
generated overview remains a candidate
admitted overview is a temporary derived artifact
cache is only an efficiency mechanism
```
