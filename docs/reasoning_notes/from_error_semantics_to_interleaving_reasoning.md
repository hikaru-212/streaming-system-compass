# From Error Semantics to Interleaving Reasoning

[← Back to Reasoning Notes Index](README.md)

**Recorded on:** 2026-08-08

## Summary

This note records a change in engineering reasoning that became visible across
Stage 3.5B, Stage 4A, Stage 4B, and Stage 4B.1.

The change did not come from one source.

It developed through two parallel tracks:

```text
Top-down semantic track
Stage 4A SemanticOutcome
→ Stage 4B DecisionReceipt / evidence ownership
→ Stage 4B.1 execution topology

Bottom-up database track
PostgreSQL transactions
→ Unit of Work / commit / rollback
→ MVCC visibility
→ isolation
→ advisory locks
→ uniqueness arbitration
→ statement success versus durable commit
```

The first track supplied a better vocabulary for asking:

> What should this failure mean, and which boundary owns that meaning?

The second supplied a physical model for asking:

> How can this failure actually happen inside PostgreSQL?

The important change was not simply learning to write more complicated tests.

It was becoming able to formulate new failure scenarios independently by
combining semantic expectations with database execution realities.

That combination eventually produced questions such as:

```text
If two valid write-side compositions can coexist,
what happens when one changes durable authority
after the other has already crossed an earlier guard?

If an event INSERT succeeds but has not committed,
what can another transaction observe?

If MVCC hides an uncommitted row,
can PostgreSQL uniqueness arbitration still block a competing INSERT?

If a competitor becomes durable before or after authoritative idempotency,
why should the loser become REPLAY in one case and STALE_WRITE in another?
```

This document preserves that learning path.

---

## 1. Starting Point — Transaction Mechanics Without Strong Intuition

Stage 3.5B introduced the durable PostgreSQL write side:

```text
Unit of Work
transaction scope
idempotency
accepted-history loading
validation placement
concurrency admission
event append
idempotency persistence
commit / rollback
```

At that point these mechanisms could be read and explained, but they were not
yet a strong mental model for independently generating failure cases.

Concepts such as:

```text
with PostgresWriteSideUnitOfWork(...)
connection.commit()
connection.rollback()
autocommit=False
```

were understandable at the API level.

The rough model was:

```text
UOW groups related writes
commit makes work durable
rollback removes unfinished work
optimistic admission detects stale writes
pessimistic admission protects a stream
```

But it was still difficult to look at a transaction path and immediately ask:

```text
What if another transaction commits exactly here?

Which earlier observation has now become stale?

Which data is visible to another connection?

Which operation already succeeded but is still reversible?

Which guard should reject the loser?

What semantic result should the caller receive?
```

Reading transactional code and being able to generate adversarial
interleavings against it are different abilities.

Stage 3.5B provided the mechanisms.

Later work gradually supplied the reasoning model.

---

## 2. Track One — Stage 4A Made Failure Meaning Explicit

Stage 4A introduced `SemanticOutcome` and forced a stronger distinction between
technical behavior and semantic meaning.

The project could no longer treat every unsuccessful write as one generic
failure.

Instead, distinctions such as these mattered:

```text
technical status
≠ semantic outcome

STALE_WRITE
≠ LOCK_TIMEOUT

REPLAY
≠ CONFLICT

VALIDATION_BLOCKED
≠ ADMISSION_REJECTED

append rejection
≠ transaction failure
```

This changed how write-side code was read.

Instead of asking only:

```text
Did the call succeed?
```

the analysis increasingly became:

```text
What exactly happened?

Which component knows that?

What semantic conclusion is justified?

What conclusion would be an overclaim?
```

That was an important shift because failure paths became part of the system
model rather than secondary branches around the happy path.

---

## 3. Stage 4B Added Evidence Ownership

Stage 4B added another constraint.

A `SemanticOutcome` is not automatically the same thing as durable governance
evidence.

`DecisionReceipt` work required explicit decisions about:

```text
which evidence may be preserved
where that evidence came from
which identity it refers to
which lifecycle it represents
what the receipt is allowed to claim
```

This strengthened the distinction between:

```text
business authority
semantic classification
governance evidence
transaction lifecycle
operation completion
```

The later `PostgresDecisionReceiptTransactionOwner` work made one distinction
especially concrete:

```text
persistence operation returned
≠
transaction commit acknowledged
```

A statement can succeed inside a live transaction and still disappear if the
transaction rolls back.

A transaction can also enter an ambiguous or failed commit path where the
client cannot safely infer durable state from local control flow alone.

This lesson eventually became reusable outside receipt persistence.

---

## 4. Track Two — PostgreSQL Knowledge Gradually Filled In the Physical Model

Stage 4 semantic work was only one half of the change.

During the same period, repeated work with PostgreSQL gradually built a more
concrete model of what the database was physically doing.

This knowledge did not arrive in one dedicated database-learning phase.

It accumulated through actual project problems.

Important pieces included:

```text
Unit of Work ownership
connection lifecycle
autocommit behavior
commit / rollback semantics
statement success versus transaction durability
READ COMMITTED visibility
MVCC
transaction-local writes
advisory transaction locks
optimistic versus pessimistic concurrency
unique constraints and unique-index arbitration
blocking lock waits
connection-local transaction state
sequence allocation versus commit visibility
```

The value of these concepts was not merely knowing their definitions.

They began to explain why certain race windows physically exist.

For example:

```text
an uncommitted INSERT can succeed locally

while

another connection cannot read that row

but

the unique index can still prevent both transactions
from committing the same unique stream position
```

That is a much richer model than:

```text
"the database has a unique constraint"
```

Likewise:

```text
pg_try_advisory_xact_lock(...)
```

became more than an API call.

It represented a transaction-scoped cooperative locking protocol whose lifetime
depends on the surrounding transaction and whose protection only applies to
participants that honor the same protocol.

---

## 5. Why Neither Track Was Enough Alone

The two learning tracks solve different problems.

### Semantic governance without database knowledge

If only the Stage 4 semantic model existed, it would be possible to say:

```text
this should become STALE_WRITE
this should become REPLAY
this should become CONFLICT
```

but it would still be difficult to know exactly how to create the physical
interleaving that produces those outcomes.

The semantic map answers:

```text
What should the failure mean?
```

It does not by itself explain:

```text
How do I force PostgreSQL into the exact state where this boundary is tested?
```

### Database knowledge without semantic governance

The opposite limitation also exists.

Knowing:

```text
MVCC
READ COMMITTED
unique index waits
advisory locks
transaction rollback
```

does not automatically answer:

```text
Which failure should become a stable application result?

Which evidence is authoritative?

Which result is merely infrastructure failure?

Which failure belongs to idempotency versus stream admission?
```

Database mechanics explain the physical event.

They do not automatically provide the semantic contract.

### The useful combination

The stronger reasoning model became:

```text
semantic expectation
+
database physical behavior
=
falsifiable interleaving question
```

For example:

```text
Writer B already observed idempotency MISS.
Writer A commits in the window before B appends.

Question 1:
Which guard still has authority to reject B?

Question 2:
Should B now become REPLAY, STALE_WRITE, or an exception?

Question 3:
What durable state is allowed to remain?
```

That is where the two tracks began reinforcing one another.

---

## 6. Stage 4B.1 Made Execution Time Explicit

Stage 4B.1 moved the analysis from terminal outcome to execution topology.

The write side has two important compositions:

```text
PRE_TRANSACTION + optimistic admission

and

IN_TRANSACTION + pessimistic admission
```

The goal was not to decide which one is better.

The first task was to establish how they actually execute.

### PRE_TRANSACTION + optimistic

```text
preliminary idempotency
→ preliminary history
→ candidate construction
→ validation
→ business UOW
→ authoritative idempotency
→ optimistic preparation
→ append-time arbitration
→ idempotency persistence
→ commit
```

### IN_TRANSACTION + pessimistic

```text
business UOW
→ authoritative idempotency
→ pessimistic preparation
→ protected history
→ candidate construction
→ validation
→ append-time arbitration
→ idempotency persistence
→ commit
```

Once these paths were understood as timelines, the gaps between checkpoints
became first-class reasoning targets.

The question changed from:

```text
What does this function do?
```

to:

```text
What if competing authority changes between these two checkpoints?
```

---

## 7. The Mixed-Strategy Question

Thinking ahead to strategy cost and timing raised a more basic question first:

```text
If write-side behavior is configurable per instance,
is the entire system guaranteed to use only one strategy?
```

A source audit showed that the answer is no.

The current design permits separate writer instances such as:

```text
writer A
= PRE_TRANSACTION + optimistic admission

writer B
= IN_TRANSACTION + pessimistic admission
```

using separate PostgreSQL connections against the same database.

The current production bootstrap does not compose both, but the abstraction does
not make them mutually exclusive.

This matters because the pessimistic advisory lock is cooperative.

An optimistic writer does not acquire the same advisory lock.

Therefore:

```text
pessimistic stream lock held
≠
all possible writers are globally excluded
```

That observation produced two new mixed-strategy characterization questions.

---

## 8. Interleaving One — IN Crosses Idempotency, PRE Wins Before Append

Consider:

```text
IN+pessimistic
→ business UOW entered
→ authoritative idempotency = MISS
→ pessimistic preparation succeeds
→ history observed
→ candidate built
→ validation ALLOW
→ pause before append
```

Then a PRE writer commits competing durable state:

```text
PRE+optimistic
→ accepted event
→ idempotency record
→ COMMIT
```

The IN execution resumes.

At this point:

```text
idempotency has already been checked
history has already been observed
validation has already completed
```

The IN path does not:

```text
re-run idempotency
reload history
retry
start a second attempt
```

Therefore correctness must transfer to a later guard:

```text
append-time version / stream-position arbitration
```

The expected result becomes:

```text
IdempotencyVerdict.MISS remains

append
→ STALE_WRITE

write-side outcome
→ ADMISSION_REJECTED

UOW
→ rollback
```

The important lesson is the ownership handoff:

```text
earlier guard already passed
→ competing authority changes
→ later guard now owns correctness
```

---

## 9. Interleaving Two — PRE Is Before UOW, IN Wins First

The opposite timing produces a different semantic result.

```text
PRE+optimistic
→ preliminary idempotency = MISS
→ preliminary history
→ candidate
→ validation ALLOW
→ pause before business UOW
```

Then:

```text
IN+pessimistic
→ authoritative MISS
→ protected execution
→ append
→ idempotency record
→ COMMIT
```

When PRE resumes:

```text
business UOW
→ authoritative idempotency check
```

the durable request memory already exists.

For the same request semantics:

```text
authoritative idempotency
→ REPLAY

PRE
→ rollback
→ no optimistic preparation
→ no append
```

The same competing fact produces a different loser result because it became
durable on the other side of the authoritative-idempotency boundary.

So the interesting question is no longer only:

```text
Who won?
```

It becomes:

```text
When did the winner become durable,
and which guard still owned the loser at that time?
```

---

## 10. Reusing the TransactionOwner Lesson on the Business UOW

The receipt TransactionOwner work suggested another question.

Suppose:

```text
event append returned ADMITTED
```

but:

```text
business UOW has not committed
```

Has accepted authority changed?

No.

The event has been inserted inside the transaction, but the write is still
reversible.

This creates another concurrency window:

```text
transaction A
→ append succeeds
→ event INSERT exists transaction-locally
→ no COMMIT yet

transaction B
→ ordinary MVCC read
→ cannot see A's uncommitted event
→ still observes the old stream version
→ attempts the same next stream position
```

This exposes an important distinction:

```text
MVCC visibility
≠
physical uniqueness arbitration
```

The second transaction may not be able to read the row as committed history,
but PostgreSQL's unique index can still coordinate the competing physical
position.

---

## 11. Uncommitted Position — Commit Versus Rollback Decides Authority

### Owner commits

```text
A INSERT sequence=N
→ succeeds
→ remains uncommitted

B ordinary SELECT
→ cannot see A
→ still sees version N-1

B INSERT sequence=N
→ reaches unique-index arbitration
→ waits for A

A COMMIT

B resumes
→ UniqueViolation on stream position
→ STALE_WRITE
→ ADMISSION_REJECTED
→ rollback
```

### Owner rolls back

```text
A INSERT sequence=N
→ succeeds
→ remains uncommitted

B attempts sequence=N
→ waits

A ROLLBACK

A's index occupant disappears

B
→ INSERT may proceed
→ idempotency persistence
→ COMMIT
```

The durable winner is B.

This proves a distinction first made concrete during receipt persistence:

```text
operation returned
≠
durable authority
```

The important part of the learning is the transfer.

A concept learned in one subsystem became a question generator in another.

---

## 12. A Separate Idempotency Race Also Became Visible

The same reasoning style exposes another TOCTOU window.

Two writers can use:

```text
same request_id
different order_id
```

and both independently observe:

```text
authoritative idempotency = MISS
```

Because they target different order streams, both event INSERTs may succeed
transaction-locally.

Only later do both attempt:

```text
INSERT idempotency_records(request_id=...)
```

There is currently no request-level lock between:

```text
check()
```

and:

```text
record()
```

The `idempotency_records.request_id` primary key can therefore become the final
physical request-identity arbiter.

The loser may receive a raw PostgreSQL `UniqueViolation`, and its UOW rollback
removes the event it had already inserted.

So the final durable state can remain internally consistent while the loser
still lacks a stable typed:

```text
REPLAY
or
CONFLICT
```

This concern is intentionally deferred from the current PR4 characterization.

The open issue is no longer only execution topology.

It is also a semantic contract question:

```text
Should the concurrent request loser remain an untyped persistence error?

or

Should it be reclassified into stable idempotency semantics?
```

That requires a separate decision.

---

## 13. The Dual-Track Development Model

The progression can now be described more accurately as two interacting tracks.

### Track A — Top-down semantic governance

```text
Stage 4A
SemanticOutcome
→ precise failure vocabulary

Stage 4B
DecisionReceipt
→ evidence ownership

TransactionOwner
→ statement / persistence completion
  separated from transaction durability

Stage 4B.1
execution topology
→ explicit checkpoint ownership
```

This track improved the ability to ask:

```text
What should this failure mean?
Who is allowed to say so?
```

### Track B — Bottom-up PostgreSQL knowledge

```text
Stage 3.5B onward

UOW
→ transaction lifecycle
→ autocommit
→ rollback
→ MVCC
→ READ COMMITTED
→ advisory xact locks
→ unique-index arbitration
→ lock waits
→ commit visibility
```

This track improved the ability to ask:

```text
How does this failure physically emerge?
What can another transaction actually see?
Where will PostgreSQL block or arbitrate?
```

### Intersection

The combination created a new reasoning pattern:

```text
semantic boundary
+
physical database boundary
+
controlled timing
=
interleaving characterization
```

That intersection is the main learning this document records.

---

## 14. What Actually Changed in Problem Formulation

Earlier, a test question was more likely to begin from an existing behavior:

```text
Does REPLAY return the previous event?

Does rollback remove the appended row?

Does validation BLOCK prevent append?
```

Those tests remain necessary.

But later questions began to be generated from gaps between boundaries:

```text
If the competitor commits after authoritative idempotency but before append,
why should the loser be STALE_WRITE instead of REPLAY?

If a pessimistic writer holds its cooperative lock,
can an optimistic writer still change durable history?

If append succeeds but commit has not happened,
can another connection observe the row?

If it cannot observe the row,
why can a unique constraint still block its INSERT?

If the owner rolls back instead of committing,
which writer becomes durable?
```

The important growth is not the length of the test code.

It is the ability to formulate these questions before the test implementation
exists.

---

## 15. The Role of AI

AI remains deeply involved in the project.

It has contributed:

```text
implementation
test scaffolding
documentation drafts
source audits
code review
test harness construction
```

This retrospective should not rewrite that history.

The development change is not:

```text
AI wrote the system before
→ now AI is unnecessary
```

The more accurate distinction is:

```text
earlier
AI often supplied both the implementation
and many of the important questions

later
AI can still implement the solution,
but missing failure questions can increasingly be formulated independently
before implementation
```

For example, the mixed-strategy and uncommitted-append questions emerged from
the system owner's own reasoning about:

```text
pluggable strategy composition
idempotency timing
UOW boundaries
commit versus append
MVCC
PostgreSQL uniqueness
```

AI remained useful for verifying source assumptions and implementing the final
controlled tests.

Problem formulation and implementation assistance are different contributions.

---

## 16. Controlled Interleavings Instead of Timing Guesswork

Concurrency bugs are often nondeterministic.

A weak test might try:

```text
start two writers
sleep(...)
hope the race occurs
```

That does not provide strong characterization evidence.

The newer tests instead identify semantic or physical synchronization points:

```text
pause after validation
pause before append
pause after a real INSERT but before commit
observe a real PostgreSQL Lock wait
then release commit or rollback
```

The goal is to force one selected schedule rather than rely on scheduler luck.

This does not prove every possible interleaving.

It provides reproducible evidence for interleavings that correspond to known
architecture boundaries.

That distinction should remain explicit.

---

## 17. What This Retrospective Does Not Claim

This note does not claim that:

- every concurrency schedule has been tested;
- the write side is formally verified;
- PRE_TRANSACTION is better than IN_TRANSACTION;
- IN_TRANSACTION is better than PRE_TRANSACTION;
- the current system is a distributed transaction protocol;
- advisory locking provides global exclusion;
- one benchmark result can determine strategy performance;
- mixed strategies should necessarily be deployed together;
- every current failure is already translated into the ideal semantic result;
- PostgreSQL knowledge is complete;
- AI-generated implementation has become unnecessary.

The write-side transaction remains a local PostgreSQL transaction.

The value of the newer characterization is narrower:

```text
specific physical interleavings
are now connected to
specific semantic and durability boundaries
```

---

## 18. Reusable Reasoning Pattern

The most reusable reasoning pattern from this progression is:

```text
1. Identify the current authority or evidence.

2. Identify the next authoritative or irreversible boundary.

3. Ask what another actor can change between those points.

4. Determine what the database physically allows in that interval.

5. Force that interleaving deterministically.

6. Identify which guard still owns correctness.

7. Require the loser to expose the semantics owned by that guard.

8. Verify durable database state independently of the returned result.

9. Keep these concepts separate:

   statement success
   transaction commit
   semantic outcome
   durable business authority
   governance evidence
```

This pattern is portable beyond the current Order workload.

It is also portable beyond Python.

---

## 19. Updated Mental Model

A simplified earlier model was:

```text
transaction
→ do work
→ commit or rollback
```

The newer model is more temporal:

```text
execution begins

→ evidence is observed

→ candidate meaning is formed

→ validation happens

→ another transaction may change authority

→ a statement may succeed locally

→ another transaction may still not see it

→ a database constraint may still coordinate it

→ commit or rollback determines durability

→ only then can some results legitimately claim accepted authority
```

The system is no longer read only as a sequence of functions.

It is read as a sequence of changing evidence, visibility, and authority.

---

## 20. Final Lesson

The main change was produced by two reinforcing learning paths.

Stage 4 semantic governance taught:

> How should failures be named, separated, and owned?

Repeated PostgreSQL work taught:

> How do those failures physically emerge through transactions, MVCC, locks,
> constraints, and commit timing?

Neither path alone would have produced the same reasoning ability.

Together they changed the central question from:

```text
"What does this UOW code do?"
```

to:

```text
"If authority changes at this exact point,
what is still visible,
what is still reversible,
what has become stale,
which guard owns the rejection,
and what may the system legitimately claim?"
```

That is the development path this reasoning note preserves.
