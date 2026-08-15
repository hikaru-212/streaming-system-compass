# From Statement Success to Owner-Liveness

[← Back to Reasoning Notes Index](README.md)

> **Status:** This is a non-authoritative reasoning record. Current
> implementation guarantees are owned by the
> [DecisionReceipt PostgreSQL Transaction Safety and Liveness Boundary](../boundary_notes/decision_receipt_postgres_transaction_safety_and_liveness_boundary.md)
> and the [PR6 persistence implementation record](../implementation_notes/stage_4b/decision_receipt_persistence.md).

*How a narrow `INSERTED` question exposed a missing PostgreSQL progress guarantee, and how the reasoning became executable evidence.*

**Recorded on:** 2026-08-04

**Form:** Engineering reasoning case study

**Context:** Stage 4B PR6 — DecisionReceipt PostgreSQL persistence

## Summary

This note preserves the discovery path behind a PostgreSQL transaction-liveness question.

No owner or waiter timeout has been selected or configured in the current
repository scope. One possible future mechanism for a live-but-idle owner is:

```text
idle_in_transaction_session_timeout
```

As external PostgreSQL context, experienced operators may already know this
mechanism. It is not a current application guarantee.

The important part of the case was different.

The question was derived before the mechanism was known.

The reasoning began from a narrow discomfort:

> If `store.insert()` returns `INSERTED` before commit, what exactly has succeeded?

That led to:

```text
INSERTED
≠ COMMITTED
```

The next question was:

> If another transaction inserts the same unique identity, can it proceed while the first transaction remains unresolved?

That led to real PostgreSQL unique-index waiting.

A proposed protection then appeared:

```text
lock_timeout
```

If configured, that would only bound the waiting contender.

It did not answer:

> Who cleans up the owner transaction if its connection remains alive but it never commits or rolls back?

That missing responsibility exposed the difference between:

```text
waiter boundedness
and
owner cleanup
```

The repository audit then showed that the current tests established normal
commit and rollback paths, but not abandoned-owner boundedness.

A new connection-loss integration test converted one part of the reasoning into executable evidence.

This note exists because the reasoning path itself is the relevant capability:

> discovering the shape of a missing guarantee before knowing the name of the implementation mechanism.

---

## 1. Initial Question: What Does `INSERTED` Prove?

The first issue was not concurrency.

It was the meaning of the return status.

The store returned:

```text
INSERTED
ALREADY_PRESENT
```

But the store did not own commit.

That created an immediate distinction:

```text
the SQL statement inserted a row
≠
the caller transaction committed
```

The correct interpretation became:

```text
INSERTED
= statement-level fact inside the caller-owned transaction
```

It did not mean:

```text
durably persisted
externally visible
safe to authorize retry
```

This mattered because later Stage 4 policy may use the receipt as evidence for:

- retry;
- no-retry;
- fallback;
- rebuild;
- operator review.

If the receipt has not committed, an external action based on it can outlive the evidence that justified it.

---

## 2. The Next Boundary: Policy Evaluation vs Action Execution

A pure decision can be evaluated before commit. The names below are
illustrative and non-contractual; they do not define current runtime types:

```text
DecisionReceipt
→ evaluate policy
→ produce RetryDecision / ActionIntent
```

But an external action should not be authorized merely because:

```text
store.insert() returned INSERTED
```

The safer future shape is:

```text
outside transaction:
    build receipt
    evaluate policy

inside short transaction:
    insert receipt
    insert durable intent
    commit

outside transaction:
    dispatcher executes action
```

This separated:

```text
evidence calculation
durable intent
external effect
```

The transaction question was therefore not an isolated persistence detail.

It affected future retry correctness.

---

## 3. Concurrent Insert: Why the Contender Must Wait

The next question was whether Transaction B could insert the same identity while Transaction A remained uncommitted.

A normal MVCC read by B cannot see A's row.

That initially invites a misleading conclusion:

```text
B cannot see A
→ B can insert
```

But unique-index enforcement has a different responsibility.

B's outcome depends on A:

```text
A commits
→ B must not insert the same identity

A rolls back
→ B may become the successful inserter
```

Therefore PostgreSQL cannot safely return B's final statement result until A's transaction outcome is known.

B waits during the `INSERT` statement.

This exposed a useful distinction:

```text
read visibility
≠ write-conflict arbitration
```

---

## 4. A Logical Challenge Improved the Explanation

An incomplete argument claimed:

> If A and B could both insert before commit, uniqueness would be violated.

That argument was not sufficient.

A different database design could theoretically allow:

```text
A statement succeeds
B statement succeeds
A commits
B fails at commit
```

That design would still preserve final uniqueness.

The missing premise was the actual timing of PostgreSQL constraint arbitration.

For the current `INSERT ... ON CONFLICT DO NOTHING` path, PostgreSQL resolves the competing unique insertion before B's statement returns.

This correction mattered because it changed the explanation from:

```text
the final database state must be unique
```

to:

```text
the current store can rely on statement-time arbitration
because PostgreSQL does not defer this ON CONFLICT result until commit
```

The lesson was:

> A correct conclusion is not enough; the proof must use the mechanism that actually establishes it.

---

## 5. Blocking Was Not Deadlock

The PostgreSQL behavior in this section is external context used to refine the
question. The repository does not currently implement a general deadlock
handling policy.

The initial schedule was:

```text
A owns pending identity
B waits for A
```

This is blocking.

There is no cycle.

A genuine deadlock would require:

```text
A waits for something held by B
B waits for something held by A
```

This distinction prevented the wrong solution from being applied.

PostgreSQL deadlock detection can resolve circular waits.

It does not treat every long one-directional wait as a deadlock.

Therefore:

```text
deadlock detector
≠ general abandoned-owner cleanup
```

---

## 6. The Key Question: What If A Never Completes?

The normal explanation assumed:

```text
A eventually commits or rolls back
```

The reasoning removed that assumption.

Possible owner states became:

```text
A commits
A rolls back
A connection disappears
A remains alive but idle
A runs a statement indefinitely
A enters a circular deadlock
```

These states require different mechanisms.

The key question was not:

> What PostgreSQL parameter should be used?

It was:

> Which completion state currently has no owner?

At this point the gap became visible:

```text
B has a waiter-side protection candidate
A still lacks an owner-side cleanup guarantee
```

---

## 7. Why `lock_timeout` Was Only Half an Answer

As external PostgreSQL context, a future configured `lock_timeout` could bound
B's lock wait:

```text
B waits too long
→ B's statement fails
```

But A still exists.

Its transaction may still hold:

- row locks;
- unique-index ownership;
- old MVCC snapshots;
- resources that delay vacuum;
- application-level capacity.

Therefore:

```text
B stopped waiting
≠
A was cleaned up
```

This was the decisive reasoning step.

One candidate mechanism for the live-but-idle owner case became:

```text
idle_in_transaction_session_timeout
```

But the requirement had already been derived:

```text
some mechanism must bound an open owner transaction
that remains alive but performs no further work
```

The future mechanism could instead be:

- application rollback discipline;
- transaction context manager;
- connection termination;
- server idle timeout;
- total transaction deadline;
- pool reset;
- operational watchdog.

The tool name came after the responsibility gap.

---

## 8. The General Inference Pattern

The reasoning followed a repeatable sequence.

### Step 1 — Identify the actors

```text
A = owner
B = waiter
```

### Step 2 — Identify the current guarantee

```text
unique constraint prevents duplicate durable state
```

### Step 3 — Ask what the guarantee does not prove

```text
does it guarantee bounded completion?
```

### Step 4 — Remove the normal-completion assumption

```text
what if A never commits or rolls back?
```

### Step 5 — Separate responsibilities

```text
waiter timeout
owner cleanup
transaction rollback
connection reuse
```

### Step 6 — Separate safety from liveness

```text
no duplicate row
≠
contender eventually progresses
```

### Step 7 — Audit executable evidence

```text
which schedules do current tests actually construct?
```

### Step 8 — Convert one missing path into a deterministic test

```text
A inserts
B reaches real PostgreSQL Lock wait
A connection closes
B resumes
B commits
C verifies committed visibility
```

### Step 9 — Defer policies that belong elsewhere

```text
idle timeout values
lock timeout values
pool cleanup
deadlock retry
later action orchestration
```

This process can be reused outside PostgreSQL.

---

## 9. Repository Audit and Test Obligations

The audit separated existing transaction evidence from the exact obligations
created by this reasoning. Current implementation facts and guarantees belong
in the [specialized boundary](../boundary_notes/decision_receipt_postgres_transaction_safety_and_liveness_boundary.md)
and the [PR6 implementation record](../implementation_notes/stage_4b/decision_receipt_persistence.md).

The reasoning produced narrower test obligations:

- establish that a conflicting insert reaches a real PostgreSQL lock wait;
- exercise owner commit, rollback, and connection-close resolution paths;
- verify the contender's classification or committed visibility after owner
  resolution;
- verify that the first materialization remains preserved after conflict;
- distinguish finite test-harness waits from runtime timeout policy; and
- preserve native stronger-isolation failure and caller-rollback ownership.

Those obligations support the distinction between implemented safety, tested
conditional progress, and absent bounded abnormal-path liveness. This note
preserves how that distinction was derived; it does not own the current
contract.

---

## 10. Converting the Discovery into Executable Evidence

PR6 strengthened producer-conflict preservation evidence and added a
connection-loss resolution schedule. The reasoning-specific shape was:

```text
owner inserts and remains uncommitted
contender reaches an observed PostgreSQL Lock wait
owner connection closes without commit
contender resumes and inserts
contender commits
a fresh connection observes the committed row
```

This converted one missing owner-resolution path into executable evidence:

```text
connection loss
→ owner transaction rollback
→ waiter release
→ committed contender visibility
```

It does not establish the live-but-idle case or any runtime timeout.

That remains intentionally separate.

---

## 11. Why the Reasoning Path Is Worth Preserving

Any future PostgreSQL setting is ordinary operational knowledge. No timeout
parameter is selected or configured by the current repository scope.

The value of the case is not ownership of a parameter name.

The value lies in deriving:

```text
the current explanation protects only the waiter
```

before knowing:

```text
which PostgreSQL mechanism protects the owner side
```

This is a form of requirement discovery.

The same pattern appears throughout Compass:

```text
candidate
≠ accepted

technical result
≠ semantic outcome

semantic outcome
≠ decision receipt

receipt inserted
≠ receipt committed

retry candidate
≠ authorized retry action

safety
≠ liveness
```

The recurring method is:

> Refuse to merge adjacent states merely because ordinary execution usually moves through them quickly.

Once the states remain separate, missing owners and missing failure exits become visible.

---

## 12. What This Case Does and Does Not Demonstrate

It demonstrates:

- ability to challenge an incomplete technical explanation;
- ability to find a missing premise in a proof;
- ability to distinguish database visibility from uniqueness arbitration;
- ability to separate blocking from deadlock;
- ability to separate waiter protection from owner cleanup;
- ability to distinguish safety from liveness;
- ability to turn a derived failure path into a deterministic integration test;
- ability to defer operational policy rather than expand a foundational PR without limit.

It does not demonstrate:

- complete PostgreSQL operational expertise;
- production experience with large connection pools;
- correct timeout values under real workload;
- full deadlock handling;
- complete retry orchestration;
- Staff-level implementation maturity across all engineering dimensions.

The claim is deliberately narrower:

> Domain vocabulary was incomplete, but the reasoning process could still identify the class of missing guarantee.

---

## 13. AI-Era Evidence

AI can generate:

- code;
- tests;
- ADRs;
- SQL;
- architectural explanations;
- and polished technical articles.

Therefore a polished final artifact alone is weak evidence of independent judgment.

A more useful evidence trail shows:

1. the initial question;
2. the competing explanations;
3. the rejected assumption;
4. the missing proof premise;
5. the repository audit;
6. the changed test obligation;
7. the final scope boundary.

The point is not to prove that AI was absent.

The point is to prove:

> AI did not own the final acceptance criteria.

In this case, the relevant ownership was visible through repeated challenges:

```text
What exactly does INSERTED prove?
Why can B not commit later and fail then?
Does lock_timeout protect B or clean up A?
What happens if A never completes?
Which current tests actually prove this?
Which missing case belongs in PR6?
Which cases belong to later operational hardening?
```

The resulting evidence is stronger than a claim that the code was handwritten.

---

## 14. Reusable Review Questions

When a mechanism claims to solve a concurrency problem, ask:

1. Which actor does it protect?
2. Which actor still owns unresolved state?
3. Does it preserve safety, liveness, or both?
4. Does it handle normal completion only?
5. What if the owner disappears?
6. What if the owner remains alive but idle?
7. What if the statement remains active?
8. What if the wait becomes circular?
9. Which timeout or cleanup owner handles each case?
10. Which deterministic test demonstrates the claim?
11. Which failure leaves the connection unusable until rollback?
12. Which policy belongs to a later orchestration layer?

---

## 15. Final Lesson

The discovery path can be summarized as:

```text
statement success is not transaction commit
→ transaction completion belongs to the caller
→ invisible uncommitted state can block a uniqueness-conflicting contender
→ contender progress depends on an owner-resolution premise
→ a future waiter timeout could bound the waiter without cleaning up the owner
→ a live idle owner requires a separate cleanup responsibility
→ repository tests must distinguish safety from bounded abnormal-path liveness
→ connection-loss cleanup can be made executable now
→ idle-owner timeout policy belongs to later operational hardening
```

The central lesson is:

> Knowing the answer is useful. Deriving the missing question before knowing the answer is a different capability.

The implementation mechanism may be ordinary.

The inference pattern remains reusable. Current implementation interpretation
belongs to the
[DecisionReceipt PostgreSQL Transaction Safety and Liveness Boundary](../boundary_notes/decision_receipt_postgres_transaction_safety_and_liveness_boundary.md).
