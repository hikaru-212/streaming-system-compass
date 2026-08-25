# Same Terms, Different Physical Models

> **Status:** Public reasoning note.
> This note explains a reasoning boundary discovered while discussing `STALE_WRITE` and `LOCK_TIMEOUT`.
> It is **not** a production contract for PostgreSQL concurrency, retry authorization, or reconciliation policy.

*How the same technical vocabulary can hide different assumptions about actors, state, and time.*

**Context:** Concurrency semantics, observation boundaries, and retry reasoning

---

## Summary

Two engineers can use exactly the same words and still reason about different systems.

The discussion began with:

```text
STALE_WRITE
LOCK_TIMEOUT
```

The intended question assumed two concurrent contenders:

```text
A || B
```

and asked:

> If A observes `STALE_WRITE` or `LOCK_TIMEOUT`, what does that observation tell us about B?

A different interpretation answers another question:

> If A observes `STALE_WRITE` or `LOCK_TIMEOUT`, did A itself commit?

Both questions may be technically meaningful, but they solve for different variables.

```text
intended:
Obs(A) -> infer State(B)

different interpretation:
Obs(A) -> infer State(A)
```

The core lesson is simple:

```text
same technical term
!=
same physical model
```

Before reasoning about a concurrency failure, make the actors, observation point, and inference target explicit.

---

## 1. Name the Actors Before Reasoning

Assume:

```text
A = observer / losing contender
B = competing contender
```

Then define the observation:

```text
Obs(A) = STALE_WRITE
```

or:

```text
Obs(A) = LOCK_TIMEOUT
```

Only then ask:

```text
What does Obs(A) prove about State(B)?
```

This removes a surprisingly dangerous ambiguity.

The failure is observed by A, but the unknown state may belong to B.

```text
failure observed by A
!=
state being inferred about A
```

A technically correct statement about A can therefore be irrelevant to a question about B.

---

## 2. `STALE_WRITE`: A Scoped Concurrent-Winner Model

The following claim is intentionally conditional.

Assume:

1. A and B are concurrent contenders for the same accepted authority.
2. Both reason from the same prior accepted version.
3. B is specifically the contender that causes A's stale-write outcome.
4. The stale result is caused by B's competing change becoming authoritative.

A simplified schedule is:

```text
initial accepted authority = v3

A                               B
------------------------------------------------
load v3                         load v3
build from v3                   build from v3
                                write competing v4
                                COMMIT
attempt based on v3
-> STALE_WRITE
```

Under this model:

```text
A did not commit its candidate
```

and, because B is explicitly assumed to be the winner that caused the stale result:

```text
B's competing change has already become committed authority
```

The useful intuition is:

```text
STALE_WRITE
~=
"I discovered that the world I reasoned from has already changed."
```

This is stronger than simply saying that A failed. It describes what A's observation implies about the shared authority under the stated causal model.

### Important caveat

`STALE_WRITE` by itself is not a complete causal history.

A system may classify several conditions as stale:

```text
stream-version mismatch
candidate continuity mismatch
recognized append conflict
recognized uniqueness conflict
other stale-candidate conditions
```

Therefore:

```text
STALE_WRITE
!=
proof that a specific competitor B existed
```

unless the surrounding physical model already establishes that B was the concurrent winner.

```text
error category
!=
complete causal history
```

---

## 3. `LOCK_TIMEOUT`: A Different Temporal Meaning

Now assume a transaction-scoped lock conflict.

```text
B
-> begins transaction
-> acquires conflicting lock
-> remains in flight
```

Then:

```text
A
-> attempts the same lock
-> cannot acquire it
-> observes LOCK_TIMEOUT / lock-not-acquired
```

A simplified schedule:

```text
A                               B
------------------------------------------------
                                BEGIN
                                acquire lock
                                perform work...
try same lock
-> LOCK_TIMEOUT                 ?
```

At the moment A fails to acquire the lock, the useful inference is not:

```text
B has committed
```

Instead:

```text
B is still unresolved / in flight
```

Its future may still be:

```text
B -> COMMIT
```

or:

```text
B -> ROLLBACK
```

The useful intuition is:

```text
LOCK_TIMEOUT
~=
"Someone currently occupies the conflicting execution boundary,
but I do not yet know what accepted fact, if any, will result."
```

So the two observations carry different temporal information.

---

## 4. Same Failure Family, Different Knowledge

At a high level both conditions may be classified as concurrency failures.

That does not mean they say the same thing about the world.

| Observation at A | Scoped assumption | What A may infer about B | What remains unknown |
|---|---|---|---|
| `STALE_WRITE` | B is the concurrent winner that caused the stale result | B's competing accepted change has already become authoritative | Whether B represents the same request, and what A should do next |
| `LOCK_TIMEOUT` / lock not acquired | B currently owns the conflicting transaction-scoped lock | B is still in flight at the observation point | Whether B will later commit or roll back |
| Commit acknowledgement lost | The uncertainty concerns A's own commit attempt | No simple failure result proves durability | Whether A committed must be reconciled |

The third row matters because it prevents another scope collapse:

```text
competitor uncertainty
!=
own-commit uncertainty
```

They may both eventually require reconciliation, but they are different problems.

A compact interpretation is:

```text
STALE_WRITE
= "the world has already changed"

LOCK_TIMEOUT
= "someone is currently trying to change the world"
```

These are scoped reasoning models, not universal definitions for every implementation.

---

## 5. Errors Are Observations, Not Just Labels

A concurrency error is not merely a control-flow token.

It is an observation made:

```text
by some actor
at some time
through some mechanism
against some shared state
```

Its meaning depends on at least:

```text
who observed it
when it was observed
which mechanism produced it
which other actors exist
which state variable we are trying to infer
```

A useful reasoning shape is therefore:

```text
observation
-> provable state
-> remaining uncertainty
```

For example:

```text
Obs(A) = STALE_WRITE
-> what has become authoritative?
-> what assumption is obsolete?

Obs(A) = LOCK_TIMEOUT
-> what is currently occupied?
-> what remains unresolved?
```

The error-handling layer may flatten both into "failure."

The reasoning layer should not.

---

## 6. Why This Matters for Retry

A retry layer that sees only:

```text
technical failure
```

may be tempted to reduce everything to:

```text
failure
-> retry?
```

That is too early.

For the scoped stale-write case:

```text
authority has already changed
-> old reasoning context is obsolete
-> the next invocation must re-enter normal governance
```

For the scoped lock-conflict case:

```text
competitor may still be unresolved
-> another invocation may see the same lock conflict
-> or it may later observe replay, rejection, validation failure, or success
```

The important principle is not that retry must predict the next result.

It is:

```text
retry
-> re-enter the guarded request path
-> let fresh idempotency, authority, domain, validation, and admission checks
   determine how far the invocation proceeds
```

This is different from blindly repeating a stale mutation.

```text
governed re-invocation
!=
reuse old candidate / old state / old version and append again
```

In short:

> **Retry re-enters governance; it does not bypass governance.**

The precise retry contract belongs elsewhere. This note only explains why the physical model must be reconstructed before policy is derived.

---

## 7. A Better Way to Ask Concurrency Questions

Ambiguity drops sharply when the actors and target variable are named explicitly.

Instead of:

> When A gets `STALE_WRITE`, has it committed?

write:

> Assume A and B are concurrent contenders for the same authority. If A receives `STALE_WRITE`, what can A infer about whether B has committed?

Instead of:

> What does `LOCK_TIMEOUT` mean for commit?

write:

> Assume B currently owns the conflicting transaction-scoped lock. If A fails to acquire that lock, what can A infer about B's state at that moment, and what remains unknown about B's eventual commit or rollback?

A few extra words fix four hidden variables:

```text
actor
competitor
observation point
inference target
```

---

## 8. A Reusable Reasoning Procedure

When analyzing a concurrency failure:

1. **Name every actor.**

   ```text
   A = observer
   B = competitor
   ```

2. **Name the shared object.**

   ```text
   stream
   row
   lock
   request identity
   accepted authority
   ```

3. **Name the observation point.**

   ```text
   A receives STALE_WRITE
   A fails to acquire a lock
   A loses commit acknowledgement
   ```

4. **Name the state variable being queried.**

   ```text
   Committed(A)?
   Committed(B)?
   InFlight(B)?
   AuthorityChanged?
   DurabilityKnown?
   ```

5. **Separate the observation from the causal premise.**

   ```text
   STALE_WRITE category
   !=
   proof that a particular B existed
   ```

6. **State stronger assumptions explicitly when needed.**

   ```text
   assume B is the concurrent winner that caused A's stale result
   ```

7. **Ask what is known now.**

8. **Ask what remains unresolved.**

9. **Only then derive policy.**

   ```text
   retry?
   replay?
   reload?
   stop?
   escalate?
   ```

This prevents policy from being built on an underspecified physical model.

---

## 9. The Broader Engineering Lesson

Shared vocabulary creates an illusion of alignment.

Two people may both know:

```text
STALE_WRITE
LOCK_TIMEOUT
commit
rollback
MVCC
```

while drawing different internal diagrams.

One model may be:

```text
A
|
+-- operation
+-- failure
+-- did A commit?
```

The other may be:

```text
A -------------------+
                     |
                     +-- shared authority
                     |
B -------------------+

A observes failure
-> infer B's state
```

The words are identical.

The state models are not.

```text
shared terminology
!=
shared referent
!=
shared physical model
```

This matters far beyond database concurrency. The same failure mode appears in:

```text
timeouts
conflicts
stale reads
stale writes
lock failures
commit acknowledgement loss
idempotency conflicts
distributed workflows
AI-assisted engineering discussions
```

A polished answer can contain correct facts and still answer the wrong problem if it silently binds the wrong actor or state variable.

---

## 10. Review Questions

Before accepting an explanation of a concurrency failure, ask:

1. Who observed the signal?
2. Which actor's state is being inferred?
3. What shared authority or resource are the actors competing over?
4. At what exact point was the observation made?
5. Does the error category identify a causal competitor, or only classify the local failure?
6. What does the observation actually prove?
7. What remains unknown?
8. Is the uncertainty about another actor, or about the observer's own commit?
9. Which assumptions are facts from the mechanism, and which are added premises?
10. Is a retry policy being asked to solve a state-reconstruction problem that should be understood first?

---

## 11. What This Note Does and Does Not Claim

This note demonstrates:

- how shared terminology can hide different physical models;
- how an omitted referent can redirect an entire reasoning chain;
- how to distinguish observer state from competitor state;
- how scoped assumptions change what can be inferred from `STALE_WRITE`;
- how lock conflict and stale-write observations carry different temporal information;
- how concurrency errors can be treated as evidence about a larger state machine.

It does **not** claim:

- that every `STALE_WRITE` implies a committed concurrent winner;
- that every implementation detects stale writes in the same way;
- that every `LOCK_TIMEOUT` uses identical waiting or locking semantics;
- to specify PostgreSQL MVCC completely;
- to define a production retry policy;
- to define a final Stage 4E contract.

The claim is narrower:

> The same error term can support different reasoning depending on which physical model, actor, and state variable the discussion assumes.

---

## Final Lesson

The reasoning failure can be summarized as:

```text
two concurrent actors were assumed
-> A observed STALE_WRITE / LOCK_TIMEOUT
-> the intended question concerned B
-> the answer reasoned about A
-> the facts could still be locally correct
-> but the queried variable was wrong
-> explicit actors removed the ambiguity
-> the two observations exposed different temporal knowledge
```

The central principle is:

> **Shared vocabulary does not guarantee a shared physical model.**

A second formulation is:

> **Before asking whether an answer is correct, verify that both sides are solving for the same state variable.**

Practical version:

```text
name the actors
name the observation
name the referent
name the inference target
then reason
```
