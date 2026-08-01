# Postmortem: From Architectural Warning to Executable Invariant

*Why a correctly predicted PostgreSQL visibility risk remained active until a deterministic transaction test forced the repository to confront it.*

[← Back to Postmortems Index](README.md)

**Recorded on:** 2026-07-31

## Summary

This note compares two related Stage 3.5D discoveries that followed very different engineering paths.

The first problem was concrete.

A snapshot schema test allowed two different orders to reuse the same
`source_global_position`.

That test described an impossible world.

`source_event_sequence` is order-local, but `source_global_position` is global.
The mismatch pointed directly to the wrong uniqueness boundary, and the schema
and tests were corrected.

The second problem was more subtle.

While reasoning about snapshot freshness and accepted-history lineage, the
project correctly distinguished:

- PostgreSQL sequence allocation order;
- transaction commit order;
- visible-row order;
- temporary visibility gaps;
- permanent rollback gaps;
- per-order causal sequence;
- cross-order global progress.

That reasoning predicted the exact failure class later reproduced in the
PostgreSQL projection worker.

However, the warning remained a document-level architectural concern.

It was not converted into:

- a repository-specific proof obligation;
- an executable worker invariant;
- a deterministic multi-connection PostgreSQL test;
- or a production contract preventing a higher visible position from excluding
  a lower position that could still commit later.

The result was an unusual gap:

```text
the failure had been described
but the implementation had not been proven safe against it
```

A later source-grounded audit and four-connection characterization test finally
demonstrated the active defect:

```text
T1 allocates P1 and remains uncommitted
T2 allocates P2 and commits first
the worker processes P2 and advances durable progress
T1 commits P1 later
the old global cursor permanently excludes P1
```

This postmortem is not about blaming AI review, human review, or the original
author.

It records a more reusable lesson:

> An architectural warning is not an enforced invariant.

Correct reasoning, review agreement, and passing ordinary tests can all coexist
with an active concurrency defect when the warning is not translated into an
adversarial executable schedule.

---

## 1. Two Problems That Looked Related

Both discoveries involved snapshot source-boundary fields:

```text
order_id
source_event_id
source_event_sequence
source_global_position
```

Both also involved the word `global`.

That superficial similarity can make the two problems look like one continuous
bug.

They were not.

The first problem concerned **identity and uniqueness scope**.

The second concerned **transaction visibility and progress completeness**.

```text
Problem A:
Can two snapshot rows claim the same global source coordinate?

Problem B:
Can a worker safely treat the largest visible source coordinate as a complete
committed-history frontier?
```

The first was found and repaired immediately.

The second was logically predicted but not experimentally tied back to the
current worker until later.

Understanding why requires separating the two discovery paths.

---

## 2. The Problem That Was Actually Found

During Stage 3.5D PR2, a schema test allowed:

```text
order-001, source_global_position = 1
order-002, source_global_position = 1
```

The test looked superficially similar to the valid case:

```text
order-001, source_event_sequence = 1
order-002, source_event_sequence = 1
```

But the two fields have different semantic scopes.

```text
source_event_sequence
= position inside one order stream
= unique together with order_id

source_global_position
= one coordinate in the global accepted-event table
= globally unique

source_event_id
= accepted-event identity
= globally unique
```

The phrase:

```text
allows same global position for different orders
```

was semantically uncomfortable.

If the position was truly global, two different accepted events could not share
it.

That discomfort produced a direct contradiction:

```text
global identity claim
vs
per-order uniqueness constraint
```

The responsible boundary was obvious:

```text
test expectation
→ database uniqueness rule
→ snapshot schema
```

The repair was correspondingly direct:

```text
UNIQUE(order_id, source_event_sequence)
UNIQUE(source_global_position)
UNIQUE(source_event_id)
```

The problem was found before the stage closed because the test described an
impossible event-log reality.

The important signal was not a failing test.

The signal was a passing test whose semantic world was wrong.

---

## 3. Why the First Problem Was Easier to Close

The schema problem had four properties that made it actionable.

### 3.1 It had a concrete artifact

The incorrect assumption existed in a named test and a named database
constraint.

There was no need to infer where the guarantee should live.

### 3.2 It had a short proof

The proof was almost definitional:

```text
global means one value cannot identify two different accepted events
```

### 3.3 It had a local owner

The migration and schema tests owned the rule.

The repair did not require coordinating writer timing, reader visibility,
durable cursor advancement, restart, and reconciliation.

### 3.4 It had an immediate falsification question

The review question was:

> Can two different accepted events legally have the same global position?

The answer was no.

The implementation could be corrected immediately.

---

## 4. The Risk That Was Only Derived

The second line of reasoning began from a different question:

> What makes one snapshot newer than another?

The first correction was:

```text
created_at
= when the derived row was written

source boundary
= how far accepted history had been represented
```

That led to a deeper question:

> What exactly does `global_position` represent?

The project then correctly distinguished:

```text
allocation-order position
= when PostgreSQL assigned the sequence value

committed-history order
= when transactions became durable and visible

visible-row order
= which committed rows one SELECT could observe

aggregate-local sequence
= causal order inside one order stream
```

From that distinction, the dangerous schedule followed naturally:

```text
T1 receives position 10 and stays uncommitted
T2 receives position 11 and commits first
a reader can see 11 without seeing 10
```

The earlier postmortem also distinguished:

```text
temporary visibility gap
≠
permanent rollback gap
≠
visible poison event
```

That reasoning was correct.

It described the exact class of failure later reproduced.

But it remained a general architectural warning.

It did not yet prove that the current repository had completed the whole
failure chain.

---

## 5. Knowing a Failure Class Is Not Proving a Repository Defect

Four levels must remain distinct:

```text
1. A failure is possible in systems of this kind.
2. This repository contains the ingredients for the failure.
3. The current production path actually composes those ingredients unsafely.
4. A deterministic test reproduces the durable bad outcome.
```

The earlier reasoning established level 1 and much of level 2.

The later audit and PostgreSQL test established levels 3 and 4.

To prove the active repository defect, the review had to connect all of these
facts:

1. `global_position` was allocated by `nextval()` during `INSERT`.
2. The accepted-event transaction could remain uncommitted afterward.
3. Another transaction could allocate a higher position and commit first.
4. The worker selected only visible rows satisfying:

   ```sql
   WHERE global_position > checkpoint
   ORDER BY global_position ASC
   LIMIT 1
   ```

5. The worker advanced durable progress to the visible higher position.
6. No durable hole or pending-position model prevented that advancement.
7. The lower event could commit after the checkpoint had already moved.
8. Restart resumed from the higher checkpoint.
9. Replay validation could detect drift for a known order but did not repair
   worker progress.
10. Snapshot-tail pagination reused the same unsafe global scalar premise.

The postmortem reasoning had not traced this complete executable chain through
the current source.

That was the missing step.

---

## 6. Why the Warning Did Not Become an Immediate Repair

The exact internal reason cannot be reconstructed with certainty.

It would be dishonest to invent one.

The repository evidence supports a narrower conclusion:

> The visibility concern was treated as a future cursor-hardening problem rather
> than as a hypothesis requiring immediate falsification against the current
> worker.

Several conditions made that interpretation easy.

### 6.1 The original task was about snapshots

The active work concerned:

- snapshot freshness;
- schema lineage;
- uniqueness scope;
- fast-path versus authority-path trust;
- future validation receipts.

The worker appeared as an upstream premise, not as the explicit audit target.

### 6.2 There was no observed incident

There was no exception, failing projection assertion, missing-order report, or
operator-visible checkpoint anomaly.

The bug was a silent omission.

### 6.3 The repository used single-worker language

A single projection worker sounds safer than a multi-worker system.

However, the reproduced race required:

```text
two accepted-event writers
+
one projection worker
```

The race was between writer commit visibility and reader progress, not between
two workers.

### 6.4 The warning sounded like future maturity work

Once temporary and permanent gaps were distinguished, the solution space
appeared to involve:

- hole registries;
- committed sequencers;
- CDC;
- operational incident handling;
- or globally ordered publication.

That could make the concern look larger and more future-facing than the current
aggregate-local projection actually required.

### 6.5 Every local component appeared coherent

The following statements were individually true:

- sequence values were unique;
- visible rows were ordered by `global_position`;
- projection state and progress usually shared one transaction;
- the reducer enforced exact-next order-local sequence;
- restart resumed from durable progress;
- one active worker was assumed.

The failure existed in their composition.

---

## 7. The Composition Error

The old design combined three mechanisms:

```text
non-transactional sequence allocation
+
MVCC committed-row visibility
+
exclusive scalar resume cursor
```

None of those mechanisms was individually defective.

Together they created the omission.

### Sequence allocation

PostgreSQL could assign P1 before P2.

### Transaction visibility

Another connection could see committed P2 while P1 remained invisible.

### Scalar resume

Once progress became P2, future queries excluded all positions at or below P2.

The composition created a false implication:

```text
largest processed visible position
=
complete committed-history frontier
```

That implication was never provided by PostgreSQL.

The worker was locally consistent with its own cursor.

The cursor meaning was globally wrong.

---

## 8. Why Ordinary Tests Passed

The old tests primarily exercised already-committed or serial history:

```text
append A
commit A
append B
commit B
run worker
```

Under that schedule:

```text
allocation order
=
commit order
=
visible-row order
```

The unsafe assumption behaved like a valid guarantee.

Unit tests could also prove:

- reducer sequence validation;
- checkpoint persistence;
- projection-state writes;
- rollback behavior;
- restart wiring;
- result shapes.

None of those tests forced the system into this world:

```text
P1 allocated but invisible
P2 committed and visible
worker progress advances to P2
P1 commits later
```

The tests were not meaningless.

They proved local behavior.

They did not prove global cursor completeness under commit inversion.

---

## 9. Why Review Agreement Was Not Enough

The implementation had been reviewed by the author and with assistance from
multiple AI systems.

That history should not be rewritten as:

```text
AI failed to find an obvious bug
```

The stronger explanation is:

```text
the review objective did not require converting the warning
into an adversarial repository-specific proof
```

AI-assisted review often follows the active boundary.

If the task is snapshot uniqueness, it inspects snapshot uniqueness.

If the task is snapshot trust, it inspects lineage, compatibility, and
authority.

Even when a model agrees that allocation order differs from commit order, that
agreement does not automatically produce:

```text
migration inspection
→ writer transaction trace
→ worker source trace
→ checkpoint durability trace
→ four-connection schedule
→ post-quiescence authority comparison
```

There was also a semantic naming effect.

Terms such as:

```text
global_position
accepted_history
durable checkpoint
```

suggest stronger guarantees than the source actually supplied.

When migrations, source, tests, and documents all share the same vocabulary,
review can validate a coherent but over-strong premise.

The failure was therefore not merely a missed line of code.

It was a missing verification obligation in the workflow.

---

## 10. The Test That Changed the Evidence Level

The later characterization test used independent PostgreSQL connections for:

```text
T1 lower-position writer
T2 higher-position writer
projection worker
independent observer
```

The schedule was deterministic.

```text
T1 inserts A and receives P1
T1 remains uncommitted

T2 inserts B and receives P2
P1 < P2
T2 commits

observer sees B
observer does not see A

worker processes B
worker records progress beyond P1

T1 commits A

observer confirms A is durable accepted history
worker runs again
A is not processed under the old cursor
```

This test did more than create concurrency.

It proved each required boundary:

- allocation order;
- commit inversion;
- first-observation visibility;
- worker processing;
- durable progress;
- later accepted-history durability;
- final projection omission.

The test converted:

```text
plausible architectural warning
```

into:

```text
experimentally reproduced active correctness defect
```

---

## 11. Would Earlier Chaos Testing Have Found It?

Possibly, but not automatically.

### Random chaos without a correctness oracle

A test that randomly:

- delays transactions;
- kills workers;
- increases concurrency;
- rolls back writers;
- or restarts processes;

might create the schedule.

But the system could still appear healthy:

```text
worker returned success
progress advanced
no exception occurred
later poll returned no event
```

Without an authority reconciliation oracle, the omission could remain silent.

### Invariant-driven chaos

A stronger chaos test could have found it if it required:

```text
after the system becomes quiescent,
every committed accepted event must be reflected in projection state
or explicit pending/terminal evidence
```

The test would need to enumerate orders from accepted history, replay authority,
and compare the final derived state.

### Deterministic schedule testing

For this defect, deterministic transaction scheduling was better than random
chaos.

It did not depend on probability, timing guesses, or sleeps.

The reusable distinction is:

```text
chaos creates unusual schedules

an invariant oracle determines whether those schedules are safe
```

Chaos alone is not proof.

---

## 12. The Repair Chosen by ADR 0020

The implemented projection did not require a total business order across
different orders.

Its state and reducer were already aggregate-local.

ADR 0020 therefore replaced one unsafe global completeness cursor with
per-order exact-next progress.

The repaired progress identity is:

```text
projection definition
+
projection epoch
+
order_id
```

An event is eligible when:

```text
event.sequence
=
last processed sequence for that order + 1
```

Now:

```text
processing order B
cannot advance order A's progress
```

If A commits late, it remains eligible for its own stream.

A rolled-back global sequence value creates no accepted event and therefore no
progress obligation for another order.

The repair also changed projection snapshot tails from:

```text
global_position > snapshot.source_global_position
```

to:

```text
same order_id
+
sequence > snapshot.source_event_sequence
+
contiguous order-local replay
```

`global_position` remains useful as:

- unique storage coordinate;
- accepted-event lineage;
- deterministic scheduling metadata.

It is no longer treated as a complete committed-history frontier.

---

## 13. What the Earlier Reasoning Got Right

The earlier committed-history postmortem should not be treated as a failed
analysis.

It correctly identified:

- allocation order versus commit order;
- visibility gaps;
- rollback gaps;
- the danger of blindly advancing over unexplained positions;
- the distinction between missing positions and poison events;
- the cost difference between per-entity ordering and global ordering;
- the need for guarantees to exist at the boundary where failure occurs.

The later repair did not invalidate that reasoning.

It specialized the solution to the actual implemented requirement.

Instead of adding a general global hole registry, the project recognized:

```text
the current projection is aggregate-local
```

and removed the unnecessary global completeness dependency.

The earlier warning was therefore technically valuable.

Its weakness was not correctness.

Its weakness was that it was not connected to an executable repository
obligation.

---

## 14. The Workflow Failure

The missing workflow transition was:

```text
architectural warning
→ tracked correctness obligation
→ current-source audit
→ adversarial test
→ accepted decision or explicit risk
```

The warning stopped after documentation.

A stronger process should require every statement shaped like:

```text
must not
cannot assume
unsafe unless
requires explicit handling
may permanently skip
```

to be classified as one of:

```text
A. enforced by current production code
B. proven by an executable test
C. accepted as a deliberate non-goal or risk
D. unresolved correctness obligation
```

A warning must not remain in an ambiguous fifth state:

```text
documented, agreed with, but not owned
```

---

## 15. New Review Rule

For every durable cursor or progress marker, ask:

1. At what moment is the coordinate allocated?
2. At what moment does its row become visible?
3. Can a higher coordinate become visible first?
4. What does progress permanently exclude?
5. What evidence proves excluded work cannot appear later?
6. What happens after rollback?
7. What happens after restart?
8. Is the cursor global while the business state is only partition-local?
9. Is completeness an actual requirement or an accidental implementation
   choice?
10. Which real database test demonstrates the answer?

For every architecture warning, also ask:

> Which current source path would fail if this warning is already active?

That question turns general understanding into repository verification.

---

## 16. Testing Rule Going Forward

Concurrency-sensitive database guarantees should be tested at three levels.

### Level 1 — Deterministic boundary test

Construct the exact transaction schedule with independent connections.

### Level 2 — Quiescent authority reconciliation

After concurrent work stops:

```text
accepted history
→ full replay
→ compare with derived state
```

The authority path must enumerate all accepted orders, including orders with no
projection row.

### Level 3 — Stress or chaos exploration

Randomly vary:

- writer duration;
- commit order;
- rollback;
- worker restart;
- lock delay;
- batch size.

Stress testing broadens schedule coverage.

The deterministic test preserves the exact known failure forever.

---

## 17. Relationship to Compass

Compass treats verification as a first-class system concern.

This incident exposes why that principle must apply not only to business-event
semantics but also to infrastructure claims.

The repository already distinguished:

```text
accepted history
derived projection state
checkpoint evidence
snapshot evidence
semantic outcome
runtime decision
```

But the old cursor contract made an infrastructure inference stronger than its
evidence:

```text
processed visible P2
→ assumed complete history through P2
```

The repair restores the evidence boundary.

Progress now proves only what the per-order contract can actually support.

This is also a concrete example of a broader Compass rule:

> Evidence must not authorize a stronger conclusion than the boundary that
> produced it can prove.

---

## 18. Final Lesson

The first bug was caught because a test described an impossible world.

The second survived because a document described a possible failure, but no
test forced the repository to enter that world.

```text
semantic discomfort
→ immediate contradiction
→ local repair

architectural warning
→ correct reasoning
→ no executable obligation
→ active defect survived
```

The reusable lesson is:

> Correct reasoning is necessary, but it is not enforcement.

And the stronger engineering rule is:

> When a document predicts a concurrency failure, convert the prediction into a
> deterministic transaction test before treating the boundary as closed.

A warning is not a guard.

A review agreement is not a proof.

A passing ordinary test suite is not evidence for a schedule it never
constructed.

The boundary becomes trustworthy only when the implementation, the invariant,
and the adversarial evidence agree.
