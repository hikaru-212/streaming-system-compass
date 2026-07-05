# Agent Pipelines as a Stochastic Process

[← Back to Semantic Admission Index](README.md)

## When Bad State Becomes Future Context

I have been thinking about agentic systems through a lens that comes from my background in applied mathematics and stochastic processes.

Most discussions about AI agent failures still treat a bad output as a single event. The agent answered incorrectly. The agent called the wrong tool. The agent generated an unsafe action. That framing is useful, but I think it misses a deeper risk.

In an agentic system, a bad action is not necessarily isolated. If the system admits it into durable state, that action may become part of the environment that future agents observe. It can be stored in a database, preserved in a log, indexed into memory, surfaced through retrieval, reflected in analytics, or used by downstream workflows.

Later, another agent may retrieve that polluted state and use it as evidence.

At that point, the failure is no longer only:

```text
The agent made a bad decision.
```

It becomes:

```text
The system taught future agents that the bad decision was part of reality.
```

This is the deeper risk I care about. A bad action is dangerous not only because it is wrong, but because it may become context.

---

## The Mathematical Intuition

In stochastic process theory, we often study how local behavior can create global behavior.

A single particle moves. A single node becomes infected. A single frog wakes up.

At first glance, these are small events. But the deeper question is not only what happens at the first site. The deeper question is whether the event creates a path for further propagation.

This is why epidemic models are useful. In a simple infection model, one infected node may infect neighboring nodes. The important question is not only whether one node was infected. The important question is whether the infection can spread through the network.

The frog model gives another useful picture.

In the frog model, some frogs are active and others are sleeping. Active frogs move through a graph. When an active frog visits a site containing sleeping frogs, those frogs wake up and begin moving as well. The process is no longer about the original frog. It is about whether activation keeps spreading through the system.

A conceptual view of the frog model: active frogs move through a graph, wake sleeping frogs, and create a propagation process. The panels illustrate stages of propagation, not exact consecutive time steps.

That structure feels surprisingly close to agent pipelines.

A wrong state is not just a wrong value. Once admitted, it can become an activated source. It can move through databases, logs, memory, dashboards, retrieval systems, analytics, and future agent decisions. It can wake up new downstream behaviors.

The original failure has not merely occurred.

It has entered the propagation process.

---

## From Frog Model to Agent Pipeline

The analogy is not exact, and it should not be treated as a formal proof. But it gives a useful mental model.

In the frog model, the active frogs are the carriers of propagation. In an agentic system, accepted state can play a similar role. Once something becomes durable, it can be read, copied, indexed, summarized, retrieved, analyzed, and reused.

A bad agent action becomes dangerous when it is admitted into durable state and later reused as trusted context.

The key point is that the bad state does not need to directly cause every future error. It only needs to become part of the context from which future decisions are generated.

That is enough to change the system.

In a classical random process, we might ask whether a particle returns to the origin, whether infection dies out, or whether activation continues indefinitely. In agent pipelines, the analogous question is different:

```text
Does bad state have a path to influence future decisions?
```

If the answer is yes, then the original mistake is not merely a local error. It is a seed for future semantic drift.

---

## Why Real Agent Pipelines Are Harder Than Clean Mathematical Models

Mathematical models are powerful because they isolate structure. To make analysis possible, we often assume that the environment is clean.

A model may assume independent movement, identical distributions, fixed transition rules, a stable graph, well-defined states, or no memory beyond the current position. These assumptions are not weaknesses. They are what make the model analyzable.

But enterprise agent pipelines are not that clean.

They are not memoryless. They are not independent. They do not operate on a fixed graph. Their transition rules are not always stable. Their state definitions may evolve with the business. Their future inputs may depend on their past outputs.

An agent may read from context, write to state, update memory, call tools, generate logs, modify a database, influence a dashboard, and change what another agent retrieves later. The system is not simply moving through an environment. It is modifying the environment that future steps will observe.

This is the key difference.

In a clean stochastic model, the graph is usually given. In a real agent pipeline, the graph itself may evolve. New data sources appear. New workflows are added. New retrieval indexes are built. New semantic definitions are introduced. Old definitions become stale. Teams change how they use metrics. Context is not static.

In a clean model, a transition may be drawn from a fixed distribution. In a real agent pipeline, the transition behavior may depend on memory, prompts, tool outputs, cached context, historical data, user feedback, and previous agent actions.

In a clean model, we may assume the state is well-defined. In a real enterprise system, even the meaning of a state may be contested.

```text
What does “active user” mean?
What does “revenue” mean?
What does “completed workflow” mean?
What does “accepted fact” mean?
```

These are not just database fields. They are business semantics. If the system learns the wrong meaning, or admits the wrong meaning into durable state, the error can propagate through future reasoning.

This makes agent pipelines more complex than many classical propagation models. They are not only stochastic processes on a graph. They are feedback systems where the graph, the state, and the context can all be modified by the process itself.

---

## The Difference Between a Bad Answer and Bad State

A bad answer is temporary.

It may confuse a user, waste time, or require correction. That is still a problem, but it is not the deepest failure mode.

Bad state is different.

Bad state can become durable. It can be stored, indexed, retrieved, analyzed, summarized, fine-tuned on, or used as context for another decision. It can become part of the system’s memory of the world.

That is the difference between:

```text
The agent said something wrong.
```

and:

```text
The system accepted something wrong as truth.
```

This boundary matters.

Once a wrong output becomes accepted state, the system may begin to reason from it. The failure is no longer only about the agent’s original response. It has become part of the process that shapes future responses.

In that sense, bad state is not just an error.

It is a potential carrier.

---

## Durable State as a Propagation Boundary

This is why durable state is such a dangerous boundary.

Before mutation, an agent output is still only a candidate. It may be wrong, but the system has not yet accepted it as part of its world. After mutation, the situation changes. The output may now live in a database, event log, memory store, retrieval corpus, dashboard, or downstream workflow.

Once that happens, the system may treat it as evidence.

Post-hoc observability can tell us that something happened. Logs, traces, audits, and dashboards are useful. But if the wrong thing has already entered durable state, observability may only tell us that the infection has already crossed the boundary.

The better question is not only:

```text
Can we observe what happened?
```

The better question is:

```text
Should this candidate action have been admitted in the first place?
```

That is the role of admission before mutation.

---

## The Admission Boundary: Stopping Propagation at the Source

If bad state can propagate, then the most important control point is the moment before it enters the environment.

Before mutation, an agent output is still only a candidate. It may be wrong, incomplete, ambiguous, or unsafe, but the system has not yet accepted it as part of its durable reality. After mutation, the situation changes. The output may now be stored, indexed, retrieved, analyzed, and reused as context for future decisions.

This is the principle behind the Compass idea I have been building.

A model output should not automatically become system truth. An agent action should not automatically become accepted history. A generated event should not automatically become a committed fact.

In short:

```text
candidate action ≠ accepted fact
```

There needs to be an admission boundary between what an agent proposes and what the system allows to become durable truth.

This boundary does not exist to prevent agents from acting. It exists to prevent unvalidated outputs from becoming propagation sources.

A Compass-style admission layer asks questions such as:

- Is this candidate action valid?
- Is it allowed under the current business state?
- Does it preserve domain invariants?
- Is it idempotent?
- Does it conflict with accepted history?
- Can the resulting state be explained later?

If the answer is no, the action should not enter accepted history.

If the answer is uncertain, the system should escalate or refuse.

If the answer is yes, the action can become part of system truth.

This does not make agents perfect.

It changes where the failure is stopped.

Instead of discovering the damage only after it spreads, the system checks the candidate before it becomes durable.

The point is not to eliminate every bad output.

The point is to prevent bad outputs from becoming future context.

---

## Accepted History and Derived Views

In event-driven systems, accepted history matters because it defines what the system believes has happened.

If accepted history is clean, derived views can be rebuilt. If a projection drifts, it can be checked against the authority. If a snapshot becomes suspicious, the system can fall back to replay.

But if accepted history itself becomes dirty, the problem is deeper.

The source of truth has been polluted.

Everything derived from it may now be correctly generated from the wrong foundation. A dashboard may be technically consistent. A projection may replay correctly. A retrieval corpus may faithfully index the data. An analytics layer may compute accurately.

But all of them may be accurately reflecting a polluted truth.

That is the most dangerous failure mode:

```text
technically consistent, but semantically wrong
```

This is why admission matters before the wrong state becomes durable.

---

## Why This Matters for Enterprise AI

Enterprise AI systems are increasingly connected to tools, databases, workflows, and business processes. This changes the risk model.

When AI only answers questions, mistakes are bad.

When AI changes state, mistakes can become infrastructure.

A wrong definition can become a metric. A wrong metric can become a dashboard. A wrong dashboard can become a decision. A wrong decision can become a workflow. A wrong workflow can generate more data. That data can become future context.

This is how semantic errors propagate.

The enterprise problem is not only whether an agent can reason. It is whether the system can govern what the agent is allowed to change, preserve, and teach to future agents.

More context is not enough.

Better retrieval is not enough.

Post-hoc observability is not enough.

The system needs a boundary that decides what can become accepted truth.

---

## A Mathematical Reframing

From a stochastic process perspective, the question is not only whether a bad event occurs.

The question is whether the system gives that event a path to propagate.

In classical models, we may study whether activation dies out or survives. In agentic systems, we can ask a similar question:

```text
Does bad state remain isolated, or does it become part of the future context distribution?
```

If a bad state is rejected, the process may stop at the boundary.

If a bad state is accepted, it may enter the environment.

If it enters the environment, future agents may sample from it.

If future agents sample from it, their decisions may reinforce it.

At that point, the system is not merely storing history. It is shaping the probability space of future behavior.

This is why I see agent pipelines as a real-world, messier, memory-bearing version of propagation models.

They are not as clean as the models we study in mathematics.

But that is exactly why the analogy is useful.

The mathematical model shows the structure.

The real system shows the danger.

---

## Final Thought

A one-time failure can become future context.

That is the core idea.

In agentic systems, durable state is not just storage. It is part of the environment that future agents reason from. Memory is part of that environment. Retrieval is part of that environment. Analytics and dashboards are part of that environment. Downstream workflows are part of that environment.

If bad state enters that environment, the system may not simply remember the mistake.

It may learn from it.

That is why admission before mutation matters.

The goal is not to make agents perfect.

The goal is to prevent unvalidated agent output from becoming durable system truth.

Because once bad state becomes future context, the system may not only reproduce the error.

It may propagate it.
