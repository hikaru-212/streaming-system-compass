# Runtime SemanticOutcome Boundary

[← Back to Boundary Notes](README.md)

## Purpose

This boundary note defines the first Stage 4 runtime semantic governance boundary:

```text
technical runtime evidence
→ SemanticOutcome
```

It explains why a successful technical path should not be treated as complete semantic correctness.

---

## Boundary Statement

```text
A technical status is not a semantic outcome.
```

A technical status tells the system what happened inside a component.

A semantic outcome tells the system what that event means for correctness, trust, risk, and downstream usage.

For example:

```text
MATCH
```

may mean a validator matched authority replay under a specific boundary.

But the system still needs to know whether that match means:

```text
SEMANTICALLY_VALID
```

or whether the result is valid only under a narrower condition.

Similarly:

```text
TAIL_REPLAY_FAILED
```

does not automatically mean the snapshot is corrupt.

It may mean:

```text
RUNTIME_UNRESOLVED
REQUIRES_AUTHORITY_FALLBACK
FAST_PATH_UNAVAILABLE
```

depending on the failure stage and trust boundary.

---

## Why This Boundary Exists

Streaming System + Compass is built around one core idea:

```text
technical success
≠
semantic correctness
```

Earlier stages applied that idea to accepted history, projection state, snapshot trust, and durable permissions.

Stage 4 applies it to runtime governance.

A green runtime path does not prove that the resulting state should be trusted.

A replay result does not prove that downstream usage is safe.

A successful retry does not prove that the original intent was preserved.

A shared context does not prove that the system has a shared contract.

Stage 4A introduces SemanticOutcome so that these meanings are represented explicitly.

---

## Protected Distinctions

This boundary protects four distinctions:

```text
technical status
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
same intent
```

If these distinctions collapse, the system may start making governance decisions from raw implementation details.

That would recreate the same class of failure Compass is designed to prevent:

```text
something ran successfully
therefore it must be correct
```

---

## Accepted History Remains Authority

SemanticOutcome does not change the authority model.

The authority model remains:

```text
accepted history = authority
projection state = derived runtime view
snapshot = derived state compression
checkpoint = operational progress metadata
```

SemanticOutcome interprets evidence about these artifacts.

It does not promote derived state to authority.

It does not make snapshots trusted by declaration.

It does not make projections accepted facts.

---

## Example Boundary Cases

### Projection drift

```text
technical evidence:
projection replay validator detects mismatch

semantic outcome:
DRIFT_DETECTED
or
DERIVED_STATE_UNTRUSTED
```

The semantic outcome describes what the mismatch means.

It does not directly execute rebuild or quarantine.

---

### Snapshot trust failure

```text
technical evidence:
snapshot boundary is invalid

semantic outcome:
FAST_PATH_UNAVAILABLE
or
DERIVED_STATE_UNTRUSTED
```

The semantic outcome may imply that authority fallback is required.

It does not choose the fallback strategy.

---

### Tail replay failure

```text
technical evidence:
tail replay fails during snapshot-assisted resolution

semantic outcome:
RUNTIME_UNRESOLVED
or
REQUIRES_AUTHORITY_FALLBACK
```

This should not automatically mean:

```text
snapshot is corrupt
```

A tail path failure and snapshot trust failure are different semantic cases.

---

### Idempotent replay

```text
technical evidence:
request_id maps to a prior accepted event with the same request effect

semantic outcome:
IDEMPOTENT_REPLAY_ALLOWED
```

This does not mean every retry is safe.

A retry may preserve request identity while changing semantic meaning.

Retry governance belongs later.

---

### Idempotency conflict

```text
technical evidence:
same request identity appears with different semantic meaning

semantic outcome:
SEMANTIC_CONFLICT_DETECTED
or
INTENT_DRIFT_DETECTED
```

The system should not treat this as a normal replay.

A later RuntimeDecisionPolicy may block or escalate.

---

## What Belongs Here

SemanticOutcome may include:

```text
semantic code
semantic category
boundary / layer
severity
risk level
reversibility
reason
context summary
evidence summary
```

It may include enough context to explain what the outcome means.

It should remain focused on semantic interpretation.

---

## What Does Not Belong Here

SemanticOutcome should not become:

```text
a durable receipt table
a full diagnostic trace
a benchmark record
a retry lifecycle table
a policy engine
a strategy optimizer
a projection delivery queue
a Stage 5 action safety gate
```

Those concepts belong to later stages.

The boundary should remain small.

---

## Relationship to Future Receipts

A future DecisionReceipt may record:

```text
SemanticOutcome
boundary
evidence source
actor metadata
strategy used
timing / cost summary
fallback required
operator review required
```

That does not mean Stage 4A should persist receipts immediately.

Stage 4A defines the meaning that receipts will later preserve.

---

## Relationship to Future Runtime Decisions

A future RuntimeDecisionPolicy may consume SemanticOutcome and produce decisions such as:

```text
ALLOW
BLOCK
REPLAY_PRIOR_RESULT
FALLBACK_TO_AUTHORITY
REBUILD
QUARANTINE
ESCALATE
```

Stage 4A should not make those decisions directly.

It only prepares structured semantic input for that policy layer.

---

## Relationship to Future Strategy Selection

A future StrategySelector may choose among execution paths such as:

```text
full accepted-history replay
snapshot fast path
receipt-backed resolver
fresh validation then resolver
projection rebuild
fast-path downgrade
```

Stage 4A should not choose among those paths.

It may only express that a path is semantically unavailable, unresolved, or requires fallback.

---

## Final Rule

```text
SemanticOutcome gives meaning.
RuntimeDecision decides action.
StrategySelector chooses path.
RetryGovernance controls attempts.
```

Stage 4A should implement the first boundary only.

