# Retry Is Not Intent Preservation

[← Back to Semantic Admission](README.md)

## Purpose

This note explains why agent retry should not be treated as a single harmless category.

A retry may look like the system is simply trying the same task again.

But in an agentic system, this assumption is unsafe.

A later attempt may preserve the original meaning, or it may only preserve the outer task identity while changing the intended action path, target state, or semantic meaning.

The core claim is:

```text
retry attempt
≠
same intent
```

A retry is only safe when the system can prove what kind of retry it is.

---

## Core Claim

Agent output should be treated as a candidate, not as truth.

The same principle applies to retries:

```text
agent retry
=
candidate continuation
```

not:

```text
agent retry
=
proof of same intent
```

A retry only means that the system is attempting again.

It does not prove that the new attempt still carries the same meaning as the original request.

---

## Why This Matters

In traditional software, retry often means:

```text
same request
same parameters
same operation
temporary failure
try again
```

For example:

```text
database timeout
network timeout
lock timeout
temporary service failure
```

In these cases, retry is mostly an operational concern.

But agentic systems are different.

An agent may regenerate the action plan during retry.

That means the next attempt may change:

```text
which action is proposed
which path is taken
which object is modified
which constraint is treated as important
which semantic meaning is preserved
```

The system must not assume that a retry preserves intent merely because it appears inside the same loop.

---

## Example: Same Task, Different Meaning

Suppose the user asks:

```text
Modify TableA.amount from INT to DECIMAL.
```

A safe action path might be:

```text
ALTER_COLUMN TableA.amount → DECIMAL
```

A failed first attempt may retry.

But a later agent attempt might propose:

```text
DROP_TABLE TableA
CREATE_TABLE TableA(id INT, amount DECIMAL)
```

The final schema may look correct.

But the meaning changed.

The original task implied:

```text
preserve existing data
```

The retried action path violated that meaning.

Therefore, this is not merely a retry.

It is a semantic change inside a retry loop.

---

## Retry Classes Are Semantically Different

A system should distinguish at least these cases:

```text
same request identity + same semantic fingerprint
→ safe idempotent replay
```

```text
same request identity + different semantic fingerprint
→ same identity carrying different meaning
```

```text
different request identity + same semantic fingerprint
→ new request with same meaning
```

```text
different request identity + different semantic fingerprint
→ normal new command
```

```text
temporary infrastructure failure
→ operational retry
```

```text
derived state mismatch
→ rebuild or quarantine, not request retry
```

```text
same agent task identity + different intent fingerprint
→ possible agent intent drift / proxy-objective drift
```

These cases should not share one generic `retry` label.

They require different runtime decisions.

---

## Idempotency Is Not Enough

Idempotency answers a narrow question:

```text
Have we already accepted the same request identity with the same command meaning?
```

It should not become a general retry audit table.

A successful idempotency record remembers:

```text
request_id
semantic_fingerprint
accepted result
```

But retry reason is attempt-level evidence.

Retry classification belongs to a runtime outcome or attempt evidence layer, such as:

```text
request_attempts
semantic_outcomes
runtime_outcomes
```

This distinction matters because the system needs to know not only whether a request was replayed, but why a retry happened and whether the retry preserved meaning.

---

## Human Intent Drift vs Agent Proxy-Objective Drift

For humans, intent drift can happen when the original architectural goal is gradually diluted by local implementation work.

For agents, the outward pattern may look similar, but the mechanism is different.

An agent does not have intent in the human sense.

It follows:

```text
prompt
tool feedback
tests
evaluators
runtime signals
```

When these feedback signals capture only local correctness, the agent may continue optimizing a proxy objective while the global premise drifts.

A safer technical term is:

```text
proxy-objective drift
```

or:

```text
apparent intent drift
```

The practical lesson is the same:

```text
retry loops need semantic admission boundaries
```

A retry loop should not be allowed to mutate durable state merely because it eventually produced an executable action.

---

## Relationship to Semantic Admission

Semantic admission asks:

```text
Should this candidate action be allowed to become accepted truth?
```

For retries, the question becomes:

```text
Should this retried candidate still be considered the same semantic task?
```

If the answer is unknown, the system should not blindly continue.

It should classify the retry reason before allowing irreversible mutation.

A safe agentic system should distinguish:

```text
execution retry
semantic retry
idempotent replay
concurrency retry
infrastructure retry
derived-state rebuild
agent meaning drift
```

Without this distinction, the system may treat a changed action path as if it were merely a repeated attempt.

---

## Runtime Implication

A retry classifier should be able to produce evidence such as:

```text
retry_observed = true
retry_class = SEMANTIC_DRIFT
retry_safety = BLOCK_AND_ESCALATE
intent_consistency = AGENT_INTENT_DRIFT
```

or:

```text
retry_observed = true
retry_class = IDEMPOTENT_REPLAY
retry_safety = SAFE_TO_REPLAY
intent_consistency = SAME_INTENT
```

The runtime decision should depend on this classification.

Not every retry should be allowed.

Not every retry should be blocked.

The system must first understand what kind of retry it is.

---

## Summary

Retry is not a single category.

A retry may be:

```text
safe replay
stale-state competition
temporary infrastructure failure
semantic conflict
derived-state rebuild
agent proxy-objective drift
```

Therefore:

```text
retry
≠
same intent
```

and:

```text
successful retry
≠
semantic correctness
```

For agentic systems, retry must pass through semantic admission before it is allowed to change durable state.
