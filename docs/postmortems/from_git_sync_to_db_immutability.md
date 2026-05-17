# Postmortem: From Git Local–Remote Drift to Database Immutability Boundaries

[← Back to Postmortems Index](README.md)

**Recorded on:** 2026-05-16

## Summary

This note records a small but important chain of understanding:

1. I started from a seemingly simple Git question:
   why did GitHub already merge my PR while my local terminal still showed the old state?
2. That question forced me to clearly distinguish **local state** from **remote state**.
3. From there, I realized that the same boundary problem appears again when moving from Python memory semantics into database persistence semantics.
4. In particular, Python-side guarantees such as `frozen=True` and append-only event handling do **not** automatically cross the process boundary into PostgreSQL.
5. Therefore, Stage 3.5B must not be treated as “just writing data into a database.”
   It is the stage where in-memory semantic rules must be **re-declared physically** at the database boundary.

This postmortem exists to preserve that shift in thinking before durable write-side implementation begins.

---

## 1. Trigger Question

The trigger was a Git question that initially looked trivial:

> Why did the remote repository show that the PR had already been merged, while my local terminal still showed the older state?

At first glance this felt like a tooling confusion problem.
But the deeper lesson was architectural:

- GitHub remote state is one service.
- Local Git state is another service.
- They do not “silently agree.”
- They only align when I perform an explicit synchronization operation such as `git pull`.

This means:

- remote merge does not magically mutate local state
- local history does not automatically reflect remote truth
- synchronization across boundaries must be explicit

That insight became the conceptual bridge to the database problem.

---

## 2. The Deeper Realization

The Git situation revealed a more general rule:

> Independent services do not inherit each other’s rules or state automatically.

This same pattern appears when moving from:

- Python process semantics
- to PostgreSQL persistence semantics

In memory, I may define a rule such as:

- `@dataclass(frozen=True)` → event objects cannot be mutated after creation

But PostgreSQL is not part of the Python process.
It is another independent runtime with its own storage engine, permissions, and mutation model.

So the question becomes:

> If Python objects are frozen in memory, what must I do in the database so that stored events are effectively frozen there too?

This is not a small implementation detail.
It is the core conceptual problem of Stage 3.5B.

---

## 3. Why the Git Analogy Is Not Forced

This analogy is not decorative.
It is structurally correct.

### Git case

- Remote merge happens on GitHub.
- Local branch remains unchanged until explicit synchronization.
- No implicit state propagation exists across the boundary.

### Database case

- `frozen=True` exists inside Python process semantics.
- PostgreSQL does not know or care about Python dataclass guarantees.
- No implicit rule propagation exists across the process boundary.

### Shared structure

In both cases:

- there are two independent systems
- each system has its own truth boundary
- crossing the boundary requires explicit alignment
- assuming “the other side should already know” is the mistake

That is why the Git question became a useful trigger rather than a random detour.

---

## 4. What Was Actually Happening In Memory Before Persistence

Before database migration, append-only behavior was enforced mainly by two in-memory mechanisms.

### 4.1 Object-level immutability

The event object was protected by Python semantics such as `frozen=True`.

Meaning:

- once an event instance was created, code could not legally mutate its fields in place
- immutability was enforced by the runtime object model

### 4.2 Container-level append-only behavior

The in-memory event history was effectively:

- a stream of accepted events
- appended in sequence
- never updated in place
- replayed as authoritative history

This means append-only was achieved by:

- disciplined code path design
- immutable event objects
- append-only list / store usage
- replay based on accepted history

This worked because everything still lived inside one application-controlled memory world.

---

## 5. Why That Is Not Enough For Stage 3.5B

Once events are moved into a database, the protection model changes completely.

In memory:

- the runtime itself can freeze the object

In PostgreSQL:

- rows are mutable by default
- if a user has `UPDATE` permission, then historical rows can be rewritten
- if a user has `DELETE` permission, then accepted history can be erased
- if uniqueness / ordering constraints are weak, stream structure can be corrupted

So if I want database persistence to preserve the same semantic intent as the in-memory model, I must translate the rule.

That translation is not automatic.

---

## 6. Core Lesson: Semantic Rules Must Be Re-declared At Each Boundary

The main lesson of this postmortem is:

> Semantic truth does not travel across service boundaries for free.

It must be re-expressed in the native enforcement mechanisms of each layer.

### In Python

- `frozen=True`
- controlled append-only logic
- explicit replay rules
- in-process guardrails

### In PostgreSQL

- permission model
- schema constraints
- key design
- append-only insertion discipline
- transaction structure
- optional triggers or policy locks

So the problem is not:
“how do I save my Python objects into Postgres?”

The real problem is:

> how do I preserve the semantic contract of those objects after they leave Python’s protection model?

---

## 7. Mapping Python-Side Rules to Database-Side Rules

This is the key translation table that emerged from the discussion.

| Python / In-Memory Rule | Database-Side Interpretation |
|---|---|
| `frozen=True` | Do not allow event rows to be updated after insertion |
| append-only event history | Allow `INSERT`, but prevent `UPDATE` and `DELETE` on accepted event rows |
| stream order by sequence | Enforce uniqueness and ordering assumptions via `(order_id, sequence)` identity |
| replay from accepted history | Read rows ordered by sequence and rebuild state deterministically |
| exact money values via `Decimal` | Store money in exact form (`NUMERIC` or exact serialized representation) |
| event truth guarded before admission | Only admitted events are written into durable event history |

This makes the next stage much clearer.

---

## 8. What Must Be True in the Database To Approximate `frozen=True`

If the in-memory meaning is:

> once an event becomes accepted history, it must not be rewritten

Then database-side design must make that true physically.

At minimum, that implies:

### 8.1 No event-row updates

For accepted event history, runtime application roles should not have:

- `UPDATE`
- `DELETE`

They should mainly have:

- `SELECT`
- `INSERT`

This is the closest database analogue to object immutability.

### 8.2 Strong stream identity

The event stream must prevent duplicate sequence occupancy.

For example, a composite identity such as:

- `(order_id, sequence)`

must not be reusable or overwritten.

This physically protects the append-only stream shape.

### 8.3 Explicit replay ordering

History must be read through:

- `ORDER BY sequence`

not by accidental physical row order.

### 8.4 Exact numeric preservation

Now that Stage 3.5A completed Decimal migration, durable storage must preserve exact money semantics rather than floating-point approximation.

---

## 9. Append-Only in Database Terms

Append-only does not merely mean “I usually only insert.”

It means:

> the system is physically designed so that historical truth is extended, not rewritten.

For the event table, append-only should mean:

- new admitted events are inserted
- prior accepted events are not updated
- prior accepted events are not deleted
- stream identity prevents overwriting an existing sequence slot
- replay semantics remain deterministic

This is the database-side continuation of the earlier in-memory event log model.

---

## 10. Why This Matters For Stage 3.5B

Stage 3.5B is not simply about introducing PostgreSQL.

It is about upgrading the write-side from:

- in-memory semantic safety

to:

- durable semantic safety

That includes:

- event-store persistence
- idempotency persistence
- transaction boundaries
- append-only enforcement
- exact money preservation
- replay-safe history reconstruction
- permission and constraint design

If these are not handled explicitly, then persistence will weaken the semantic model rather than strengthen it.

---

## 11. New Mental Model

The most important mindset shift from this discussion is:

### Old instinct

“I already enforced the rule in Python, so the system should still be safe.”

### Corrected model

“Python enforced the rule only inside its own process boundary.
Once data crosses into another service, the rule must be re-established in that service’s own enforcement language.”

This is the same reason:

- remote Git state must be pulled explicitly
- database immutability must be declared explicitly

The systems are adjacent, not magically unified.

---

## 12. Reusable Rule for Future Design

This discussion produced a reusable engineering rule:

> Whenever a guarantee seems “natural” in one layer, ask whether it still exists after crossing into another service boundary.

Examples:

- local Git state vs remote Git state
- Python immutability vs database row mutability
- application validation vs storage-level constraints
- in-memory ordering assumptions vs durable replay ordering

This rule should be applied deliberately in Stage 3.5B schema and migration design.

---

## 13. What This Means Before Writing SQL

Before writing actual database code, I should now ask:

1. What exact in-memory guarantee am I trying to preserve?
2. Which process currently enforces it?
3. Does that guarantee survive after crossing into Postgres?
4. If not, what is the database-native mechanism that must restate it?

For this project, the immediate examples are:

- `frozen=True` → no rewrite of accepted event rows
- append-only log → insert-only accepted history with protected stream identity
- `Decimal` semantics → exact durable money storage
- replayable history → stable ordering and stream reconstruction

---

## 14. Practical Next Step

The next implementation step should therefore not begin with random database code.

It should begin with an explicit translation exercise:

### “How do the current Python-side guarantees map into database-side physical constraints?”

That likely means the next work should focus on:

- write-side schema draft
- event-table identity and append-only protection
- idempotency-table role and transactional coupling
- runtime DB permissions
- exact money storage representation
- transaction boundaries for durable append + idempotency write

Only after that should full Stage 3.5B implementation proceed.

---

## 15. Final Postmortem Lesson

A small Git synchronization confusion turned into a much more important architecture lesson:

> local truth and remote truth are separate until synchronized
> in-memory truth and durable truth are separate until re-declared

That is the real lesson I want to preserve.

The Git issue was not embarrassing noise.
It was the trigger that exposed the deeper distributed-systems principle needed for the next stage.

And that principle is now clear:

> Boundaries do not preserve semantics automatically.
> They require explicit alignment.

---

## Suggested Follow-Up

Use this postmortem as the conceptual preface for Stage 3.5B work:

- define database-side append-only enforcement
- define database-side immutability analogue to `frozen=True`
- define exact money durability rules
- define how durable event history and idempotency are committed together
