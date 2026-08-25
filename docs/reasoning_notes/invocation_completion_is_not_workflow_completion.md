# Invocation Completion Is Not Workflow Completion

[← Back to Reasoning Notes Index](README.md)

Recorded on: 2026-08-25

## Current Authority

This note is a non-authoritative reasoning record.

Current architecture ownership belongs to:

- [ADR 0029 — Stage 4C+ Exists at the Automation Boundary](../adr/0029_stage_4c_plus_exists_at_the_automation_boundary.md)
- [Stage 4E Closeout](../implementation_notes/stage_4e/stage_4e_closeout.md)
- [PostgreSQL Concurrency Admission Boundary](../boundary_notes/postgres_concurrency_admission_boundary.md)

Current source, tests, accepted ADRs, boundary notes, and stage closeouts remain authoritative if this note and the implementation ever diverge.

---

## Purpose

This note preserves the reasoning path from one concurrency question to a broader automation boundary:

```text
If one invocation finishes after the authoritative world changed,
what exactly has finished?
```

The derivation exposed several distinctions:

```text
Invocation Completed
!=
Workflow Responsibility Completed
```

```text
observation supersession
!=
the boundary that detects it
```

```text
fresh re-observation
!=
retry old work
```

```text
information value
!=
authority
```

and finally:

```text
evidence
!=
proposal
!=
authority
!=
execution
```

This note explains that derivation. It does not define a new runtime contract.

---

## 1. The Hidden Premise in a Request Boundary

A traditional request can end safely like this:

```text
request
→ contention / conflict / rejection
→ no accepted effect
→ result returned
```

The runtime can stop because responsibility moves to a caller, operator, scheduler, or another service.

The hidden premise is:

```text
someone else still owns what happens next
```

That is often enough for a human-operated backend.

---

## 2. Autonomous Workflows Remove That Premise

Now suppose one machine owns a larger workflow goal.

```text
A1 observes S1
        ↓
constructs candidate
        ↓
B commits S2
        ↓
A1 eventually stops safely
```

The database may still be correct:

```text
accepted history is valid
A1 left no accepted effect
```

But the workflow may still need to determine:

```text
What is true now?
Has the goal already been satisfied?
Is the original action now unnecessary?
Is it now invalid?
Does another governed action remain?
```

Therefore:

```text
Invocation Completed
!=
Workflow Responsibility Completed
```

and:

```text
database correctness
!=
workflow progress responsibility
```

This does not mean Compass guarantees eventual workflow completion.

It means invocation completion is not machine authority to infer what happens next.

---

## 3. "Stale" Is Not One Physical Model

Different physical events can look broadly similar.

Early pessimistic contention may look like:

```text
prepare_stream()
→ LOCK_TIMEOUT
```

At that point, the invocation may not yet have loaded history, built a candidate, validated it, or attempted append.

A different model is:

```text
A1 observes version 1
B commits version 2
A1 later reaches append
→ authoritative history has advanced
```

The key lesson is:

```text
same broad failure family
!=
same physical cause
```

That matters when consequences depend on the cause.

---

## 4. Observation Supersession Is Not a Verdict

Consider:

```text
A1 observes S1
        ↓
B commits S2
        ↓
A1 still reasons from S1
```

A1's observation has been superseded.

But:

```text
the world changed relative to A1
!=
A1 has already detected that change
```

Observation supersession is a physical relationship between an earlier observation and the current authoritative world.

It is not automatically a validation verdict or retry decision.

---

## 5. Validation Does Not Necessarily Detect It

Validation reasons about:

```text
candidate
vs
captured ValidationContext
```

It does not automatically mean:

```text
re-read authoritative storage
and prove the world is unchanged
```

So this schedule is possible:

```text
A1 captures S1
→ builds candidate from S1
→ B commits S2
→ validation still checks candidate against captured S1
→ validation may ALLOW
```

Therefore:

```text
authoritative state changed
!=
validation must fail
```

and:

```text
VALIDATION_BLOCKED
!=
proof of a concurrent accepted write
```

A validation block can exist without concurrency, and concurrency can exist without validation detecting it.

---

## 6. Supersession Is Not the Detection Boundary

A later authoritative boundary may reveal information unavailable to the earlier computation.

Examples include:

```text
authoritative idempotency observation
```

or:

```text
append-time authoritative version observation
```

So:

```text
observation supersession
= what physically happened

detection boundary
= where enough evidence later becomes visible
```

This distinction is more reusable than any one error name.

---

## 7. Topology Changes Which Evidence Is Likely

A pre-transaction optimistic path naturally leaves a wider interval between observation and append.

A cooperating in-transaction pessimistic path tries to serialize earlier, so contention is more likely to appear as:

```text
prepare_stream()
→ LOCK_TIMEOUT
```

But locks protect cooperating participants, not arbitrary writers outside the protocol.

Therefore:

```text
topology
→ influences which evidence is likely to arise
```

while:

```text
authority evaluation
→ should consume reviewed evidence
not a topology label
```

This prevents rules like:

```text
optimistic = retryable
```

or:

```text
pessimistic = globally race-free
```

from becoming false abstractions.

---

## 8. Fresh Re-Observation Is Not Retry of Old Work

When an earlier observation is no longer current, a useful next step may be:

```text
fresh invocation
→ fresh authoritative observation
→ fresh domain reconstruction
→ fresh reasoning
```

This is not:

```text
retry old append
reuse old candidate
reuse old validation
```

A fresh invocation may discover that the same request already succeeded, or that another accepted change made the old action invalid.

The value comes from learning what is true now.

---

## 9. Information Value Still Does Not Grant Authority

This is where concurrency reasoning becomes governance reasoning.

It is tempting to say:

```text
another invocation could reveal useful information
→ invoke again
```

That is too strong.

The correct distinction is:

```text
fresh-invocation information value
!=
ReinvocationAuthorization
```

An experiment can prove that another observation would be useful.

It cannot create permission to perform one.

---

## 10. Evidence Must Match the Consequence

A coarse technical status may collapse several physical causes:

```text
physical cause A ─┐
physical cause B ─┼→ coarse technical status
physical cause C ─┘
```

If those causes are not consequence-equivalent, the coarse label cannot safely authorize all of them.

Therefore:

```text
technical outcome
!=
physical evidence
```

and:

```text
same technical status
!=
same consequence authority
```

The broader rule is:

> Evidence must be discriminative enough for the consequence that depends on it.

---

## 11. The Automation Boundary

A human-operated system can often stop at evidence because a person supplies the missing judgment:

```text
Should we wait?
Should we retry?
Should we investigate?
Should we stop?
```

An autonomous system cannot treat that human judgment as free.

The missing responsibilities must become explicit:

```text
evidence
        ↓
proposal
        ↓
authority evaluation
        ↓
controlled execution
        ↓
fresh observation
        ↓
governance again
```

The core separation is:

```text
evidence
!=
proposal
!=
authority
!=
execution
```

This is the reasoning path behind ADR 0029.

---

## 12. Why Stage 4B Can Be a Valid Endpoint

The conclusion is not:

```text
every backend needs Stage 4C+
```

For a human-operated backend:

```text
Stage 4B evidence
→ human judgment
→ operational action
```

may be enough.

Stage 4C+ becomes necessary when:

```text
downstream consequence authority
moves from humans
into autonomous machinery
```

That is why the boundary can be summarized as:

```text
Stage 4B and earlier
= evidence / understanding system

Stage 4C+
= automation authority boundary
```

---

## 13. Stage 4C+ Is Not More Diagnosis

The completed Stage 4 split makes this concrete:

```text
Stage 4C
→ what current response is authorized?

Stage 4D
→ how should an already-authorized operation be executed?
→ responsibility retained; implementation deferred

Stage 4E
→ may another complete invocation of the same request enter?
```

These are consequence questions, not simply new labels for what happened.

---

## 14. Planner Proposal Is Not Execution Authority

A future planner or AI agent may propose:

```text
REINVOKE_SAME_REQUEST
```

but:

```text
planner proposal
!=
another-invocation authority
```

and:

```text
another-invocation authority
!=
execution
```

A controlled executor must enforce the authority result.

A useful negative control is:

```text
planner proposes another invocation

but

authority evaluation returns NO AUTHORITY

therefore

executor must not enter another invocation
```

This is a future experiment implied by the reasoning, not a current production claim.

---

## Corrected Mental Model

The original intuition was:

```text
failure
→ maybe retry
```

The corrected model is:

```text
invocation
→ observation
→ candidate / validation / execution evidence
→ completed result

world may change
without that change being immediately observable

later authoritative boundary
→ may expose stronger evidence

fresh re-observation
→ may have information value

but:

information value
!= authority

therefore:

evidence
→ proposal
→ consequence-specific authority
→ controlled execution
→ fresh observation
→ governance again
```

This is why concurrency handling, workflow progress, and automation authority should not collapse into one generic retry mechanism.

---

## Reusable Lessons

```text
Invocation Completed
!=
Workflow Responsibility Completed
```

```text
database correctness
!=
workflow progress responsibility
```

```text
stale observation
!=
validation failure
```

```text
observation supersession
!=
detection boundary
```

```text
fresh re-observation
!=
retry old work
```

```text
information value
!=
authority
```

```text
technical outcome
!=
physical evidence
```

```text
evidence
!=
proposal
!=
authority
!=
execution
```

Together these distinctions form the reasoning bridge from local concurrency behavior to explicit automation authority.

---

## Current Owner / Remaining Question

The accepted architectural decision is owned by:

```text
ADR 0029
— Stage 4C+ Exists at the Automation Boundary
```

The completed Stage 4 implementation owns the current Stage 4C and Stage 4E authority contracts.

The remaining question is experimental:

```text
Can existing evidence
+ planner proposal
+ consequence-specific authority
+ controlled execution
+ fresh observation

compose into a useful autonomous recovery loop
without allowing the planner to manufacture its own authority?
```

That question should be answered with executable evidence before another production stage or runtime responsibility is introduced.

---

## Summary

The reasoning began with a concurrency question and ended at an authority boundary.

```text
one invocation can finish safely
while the larger workflow remains unresolved

        ↓

authoritative state may change
without validation detecting the change

        ↓

a later authoritative boundary may expose stronger evidence

        ↓

a fresh invocation may reveal new information

        ↓

information value still does not grant authority

        ↓

autonomous systems therefore need explicit separation between
evidence, proposal, authority, and execution
```

The resulting architectural conclusion is:

```text
Stage 4B
= evidence boundary

Stage 4C+
= automation authority boundary
```

That conclusion is owned by ADR 0029.
