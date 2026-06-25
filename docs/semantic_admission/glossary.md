# Semantic Admission Glossary

[← Back to Semantic Admission Index](README.md)

This glossary defines the core vocabulary used in the Semantic Admission section of the Compass project.

## Candidate Action

A candidate action is an action proposed by an agent, workflow, API request, or automation process before the system has formally accepted it as valid.

A candidate action may be executable, but executability is not the same as admissibility.

Example:

- `ALTER_COLUMN TableA.amount TO DECIMAL`
- `DROP_TABLE TableA`
- `UPDATE customer_id=123 status='approved'`

A candidate action is not system truth.

## Accepted Fact

An accepted fact is a state change that the system has formally admitted and committed as durable truth.

The key point is not merely that the write succeeded. The key point is that the system allowed the action to become trusted state.

## Candidate Event

A candidate event is a proposed event that has not yet entered accepted history.

In Compass, a candidate event must pass validation before it becomes part of durable accepted history.

## Accepted History

Accepted history is the durable sequence of events or facts the system treats as the source of truth.

Read models, projections, snapshots, analytics, downstream workflows, and future agent decisions may depend on accepted history.

Because of this, accepted history must be protected from semantically invalid candidate events.

## Semantic Admission

Semantic admission is the process of deciding whether a candidate action or candidate event is allowed to become accepted system truth.

It asks:

> Should this candidate be allowed to mutate durable state?

Semantic admission is not the same as output evaluation. It is a boundary decision before or during state mutation.

## Admission Boundary

An admission boundary is the system boundary where candidate actions are accepted, rejected, escalated, or transformed before they can mutate durable state.

For state-changing agents, this boundary is critical because the agent may generate action paths dynamically.

## System Truth

System truth is the set of durable facts the system allows other components to rely on.

A tool call result, model output, or workflow step is not system truth by default.

## Semantic Correctness

Semantic correctness means that a system state or transformation preserves the intended business meaning, not merely that the code executed successfully.

A pipeline can finish, a schema can match, and a workflow can complete while still producing the wrong business meaning.

## Technical Success

Technical success means the system executed according to some operational signal:

- the tool returned success
- the database committed
- the job completed
- the workflow reached the end
- the final schema matched the expected shape

Technical success does not imply semantic correctness.

## Action Path

An action path is the sequence of operations used to reach a result.

The final state may look correct even when the action path was unsafe.

Example:

- Safe path: `ALTER_COLUMN`
- Unsafe path: `DROP_TABLE` followed by `CREATE_TABLE`

Both may lead to a table with the desired column type, but they do not preserve the same truth.

## Final-State Validation

Final-state validation checks whether the end result looks correct.

It is useful but incomplete.

A correct-looking final state does not prove that the action path was admissible.

## Compass Guard

A Compass Guard is a conceptual admission guard that evaluates candidate actions before they mutate state.

It may check:

- allowed actions
- blocked actions
- target entities
- required proofs
- escalation rules
- unsafe action paths

## Admission Before Mutation

Admission before mutation means the system validates whether an action is allowed before it changes durable state.

This is different from observing the damage after the mutation has already happened.

## Durable State

Durable state is state that persists and may be trusted by future systems.

Examples include:

- database rows
- event logs
- workflow state
- agent memory
- retrieval corpora
- audit records
- snapshots

Durable state requires stronger protection than temporary output.

## Bad State as Future Context

Bad state becomes future context when an invalid fact is admitted into durable systems and later used as evidence by agents, analytics, retrieval, or downstream workflows.

This turns a single bad action into a continuing source of semantic contamination.

## Architectural Over-Trust

Architectural over-trust is the mistake of allowing probabilistic outputs or successful executions to mutate durable state without an explicit admission boundary.

It treats generated actions as if they were already validated facts.

## Technical Concurrency

Technical concurrency refers to conflicts over write ordering, version continuity, locks, transaction boundaries, or stale state.

Traditional concurrency control usually asks questions such as:

* Did the version change?
* Did another transaction commit first?
* Can this write acquire the lock?
* Is this update based on a stale read?

Technical concurrency control is necessary, but it does not fully determine whether a candidate action is semantically admissible.

## Semantic Concurrency

Semantic concurrency refers to conflicts between multiple candidate actions that may be technically valid but semantically incompatible.

It asks:

> Even if these actions can be ordered, should they all be allowed to become accepted facts?

For example, multiple agents may observe the same state but propose different target meanings.

A traditional optimistic lock may decide which write wins first.

A pessimistic lock may serialize access.

But neither mechanism fully explains whether the delayed or losing actions should be retried, rejected, revalidated, escalated, transformed into new candidates, or blocked as semantically incompatible.

Semantic concurrency is the admission problem that remains after technical concurrency has controlled write ordering.

## Semantic Conflict

A semantic conflict occurs when two or more candidate actions cannot all become accepted facts without violating business meaning, user intent, domain rules, or accepted-history consistency.

A semantic conflict may exist even when:

* all actions are individually executable
* all requests passed basic validation
* all actors read the same initial state
* the database can serialize the writes
* a lock can determine who writes first

The conflict is not only about timing.

It is about meaning.

## Same-State Different-Intent Collision

A same-state different-intent collision occurs when multiple agents, workflows, or requests observe the same state but propose different target meanings.

Example:

```text
Observed state:
status = CREATED
version = 1
amount = 100.00

Candidate actions:
A: PAY order
B: CANCEL order
C: CHANGE amount
```

From a technical perspective, these actions may all be based on the same version.

From a semantic perspective, they represent incompatible futures.

The admission boundary must decide how to handle the delayed or losing candidates after one action becomes accepted history.

Possible outcomes include:

* reject
* retry after revalidation
* escalate for review
* transform into a new candidate
* block because the intent no longer matches the accepted state

## Concurrency Admission

Concurrency admission is the boundary where the system decides whether a candidate action can still become the next accepted fact under the current accepted history.

It is related to technical concurrency control, but not identical to it.

Technical concurrency control protects write ordering.

Semantic admission protects meaning.

Concurrency admission sits between them:

```text
candidate action
→ semantic validation
→ concurrency admission
→ accepted fact
```

In Compass, this distinction matters because a candidate may be semantically valid against an earlier state but no longer admissible after another fact has been accepted.
