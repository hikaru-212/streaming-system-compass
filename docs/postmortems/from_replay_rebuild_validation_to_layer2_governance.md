# From Replay / Rebuild Validation to Layer 2 Governance

[← Back to Postmortems](README.md)

## Context

Stage 3.5C PR5 introduces the durable replay / rebuild validation baseline.

The immediate engineering goal is intentionally narrow:

```text
accepted history
→ replay through canonical reducer
→ expected projection state
→ compare with persisted projection state
```

This raised an important design question:

> Is PR5 already Compass Layer 2?

The answer is:

```text
PR5 is the physical replay / rebuild correctness substrate.
Compass Layer 2 is the future semantic governance layer built on top of derived-state evidence.
```

This postmortem records that distinction so the project does not collapse replay validation, semantic classification, runtime decision policy, and recovery behavior into one implementation step.

---

## The Confusion

PR5 and Compass Layer 2 feel similar because both are concerned with derived-state correctness.

Both are related to this question:

```text
Does the current derived state still match what source-of-truth history implies?
```

That similarity is real.

However, they operate at different architectural levels.

PR5 asks:

```text
Can I recompute and compare the expected projection state from accepted history?
```

Compass Layer 2 asks:

```text
What does derived-state mismatch mean, and what should the system do about it?
```

This distinction matters because a replay validator should not silently become a runtime governance engine.

---

## PR5 Boundary

PR5 is about durable replay / rebuild correctness.

It answers the practical streaming-system question:

> If the read-side state is wrong, can the system use the accepted event log to verify or reconstruct the correct version?

In other words:

```text
event log is still trusted
derived state may be stale, missing, or corrupted
replay / rebuild must be possible
```

PR5 produces comparison evidence such as:

```text
MATCH
MISSING_PROJECTION
DRIFT
NO_ACCEPTED_HISTORY
```

It does not decide what to do with that evidence.

---

## Compass Layer 2 Boundary

Compass Layer 2 should eventually interpret derived-state evidence.

It should answer questions such as:

- Is this projection state trustworthy enough for runtime use?
- Is the mismatch severe?
- Should the system rebuild?
- Should the system quarantine the derived state?
- Should downstream reads be blocked?
- Should a structured `SemanticOutcome` be emitted?
- Should runtime decision policy continue, stop, retry, or escalate?

Layer 2 is therefore not only a comparison tool.

It is a semantic classification and runtime decision boundary.

---

## Why Full Replay Is Not the Layer 2 Runtime Path

PR5 uses full accepted-history replay because it creates the clearest correctness oracle:

```text
accepted history is truth
canonical reducer is the legal derivation path
replay-derived state is the expected derived state
```

However, Compass Layer 2 should not require full replay on every runtime check.

A future Layer 2 should likely have multiple levels:

```text
Fast path:
local derived-state invariant checks

Medium path:
checkpoint / lineage / reducer-version checks

Slow path:
full replay validation from PR5
```

PR5 establishes the slow but authoritative baseline.

Layer 2 can later decide when that baseline is needed.

---

## Possible Layer 2 Fast Path

A future Layer 2 fast path may validate local projection transition correctness:

```text
previous projection state
+
accepted event
→
next projection state
```

This is similar in shape to Compass Layer 1, but applied to derived state.

Layer 1 protects:

```text
candidate event entering accepted history
```

Layer 2 fast path may protect:

```text
accepted event being reflected into derived state
```

A local check is cheaper than replaying all accepted history.

But it only proves local consistency.

It does not fully prove that the entire persisted projection state is aligned with all accepted history.

That is why PR5 full replay remains necessary as the durable correctness baseline.

---

## Relationship Summary

The relationship is:

```text
PR5
= replay / rebuild correctness evidence

Compass Layer 2
= semantic interpretation + runtime decision + recovery policy
```

PR5 belongs to:

- verification
- replay
- rebuild substrate
- audit
- diagnosis
- durable correctness baseline

Compass Layer 2 belongs to:

- semantic classification
- structured outcomes
- runtime decision policy
- action safety
- recovery governance

---

## Design Lesson

The key lesson is:

> A correctness oracle is not yet a governance layer.

PR5 can prove that a projection is aligned or drifted.

It should not decide whether to rebuild, quarantine, alert, block, continue, or escalate.

Those decisions belong to later Compass Layer 2, `SemanticOutcome`, runtime decision policy, and action safety work.

---

## Preserved Boundary

PR5 should stay narrow:

```text
accepted history
→ replay / rebuild expected state
→ compare with persisted projection state
```

Compass Layer 2 should come later:

```text
derived-state evidence
→ semantic outcome
→ runtime decision
→ recovery / safety action
```

In short:

```text
PR5 proves that the system can recalculate the correct read-side state.

Compass Layer 2 decides what a read-side correctness failure means and what the system should do about it.
```
