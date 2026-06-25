# Semantic Admission for State-Changing AI Systems

[← Back to Semantic Admission Index](README.md)

## Why successful execution is not the same as accepted truth

AI agents are powerful because they can turn intent into action.

They can call tools, update records, trigger workflows, move data across systems, and coordinate multi-step operations. This makes them useful, but it also changes the risk model of enterprise software.

A traditional software system usually executes a bounded path written by engineers. An agentic system may generate the path itself.

That means the central question is no longer only:

> Did the system execute successfully?

It is also:

> Should this candidate action have been allowed to change the system?

## Execution Success Is Not Semantic Correctness

An agent can call a tool and receive `200 OK`.

A database write can commit.

A workflow can complete.

A final state can look correct.

But none of these facts automatically prove that the action preserved the intended business meaning.

The action may still be wrong.

It may target the wrong entity. It may violate domain constraints. It may drift from the original user intent. It may take a destructive path to reach a correct-looking final state. It may create state that future systems will treat as truth.

This is the core failure mode Compass is designed around:

> A system can technically succeed while producing the wrong business meaning.

## Candidate Actions Are Not Accepted Facts

A model output is not system truth.

A proposed tool call is not system truth.

A proposed event is not system truth.

A proposed context update is not system truth.

Each of these is only a candidate.

A candidate should become durable system truth only after it passes an explicit admission boundary.

This distinction matters most when agents can mutate enterprise state.

Without an admission boundary, a probabilistic output can become a database row, a workflow transition, a memory entry, a retrieval document, or an accepted event. Once that happens, the system may start treating the action as reality.

## Admission Before Mutation

Post-hoc observability is necessary.

Logs matter. Audits matter. Dashboards matter. Evaluations matter. Trace inspection matters.

But once a bad action has already mutated durable state, observation may only tell us that damage happened.

Enterprise agents need something stronger:

> admission before mutation.

Admission asks whether the candidate action is allowed to become part of system truth.

This includes questions such as:

- What actions are allowed?
- What actions are blocked?
- Which entities can be touched?
- Which state changes require escalation?
- Which action paths are semantically unsafe?
- Which proof must be provided before the mutation is accepted?

The goal is not to stop agents from acting.

The goal is to make agent-driven automation governable.

## Evaluation Improves the Agent. Admission Protects the System.

Evaluation asks whether the agent output looked correct or performed well against a task.

Admission asks whether a specific candidate action is allowed to change durable state.

Both are important, but they protect different things.

Evaluation helps the agent improve over time.

Admission protects the system at the moment where a candidate becomes accepted truth.

A system that relies only on evaluation may learn from failures after they occur. A system with admission can block invalid mutations before they become accepted history.

## Why Accepted History Matters

Bad state does not stay local.

Once a bad fact enters durable systems, it can flow into:

- analytics
- dashboards
- audit logs
- memory
- retrieval corpora
- fine-tuning datasets
- downstream workflows
- future agent decisions

At that point, the failure is no longer only a bad action.

The system may teach future agents that the bad action was part of reality.

This is why Compass distinguishes between candidate action and accepted fact, and between proposed event and accepted history.

Accepted history is not just a storage layer. It is the set of facts future systems are allowed to trust.

## The Compass Position

Compass is a semantic correctness boundary for failure-aware pipelines and state-changing agent systems.

It separates:

- technical execution from semantic correctness
- database commit from semantic truth
- candidate action from accepted fact
- candidate event from accepted history
- final-state appearance from admissible action path

The central question is:

> What is allowed to become system truth?

Compass does not assume agents are bad. It assumes agents are powerful enough that their actions need explicit admission boundaries.

For enterprise agents, reliability is not only about producing better outputs.

It is also about deciding which candidate actions are allowed to become accepted facts.
