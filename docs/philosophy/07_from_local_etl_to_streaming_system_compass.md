# From Local ETL to Streaming System + Compass

[← Back to Design Philosophy](README.md)

## Purpose

This note records the origin path of **Streaming System + Compass**.

The project did not begin with streaming systems, event sourcing, distributed runtime design, or governance-oriented architecture.

It began with a smaller and more personal problem:

```text
local ETL friction
→ Airflow debugging pain
→ Core vs Enablers
→ semantic correctness
→ Compass as an abstract semantic protocol
→ streaming / event sourcing as the runtime body for Compass
```

The goal of this note is not to make the journey look cleaner than it was.

The goal is to preserve the reasoning path that explains why this project became a streaming system instead of remaining a local ETL, DAG, or architecture essay.

---

## 1. The Debugging Aha Moment

Before Compass existed, I was trying to understand programming and data engineering at a more fundamental level.

After spending hours debugging a stubborn issue, I had a simple realization:

```text
Programming is building a bridge between input and desired output.
```

Instead of staring only at implementation details, I started asking:

- What exactly is my input?
- What exactly do I want as output?
- What is the simplest transformation between them?

This became my first system-thinking model:

```text
Input
  ↓
Bridge / Transformation
  ↓
Output
```

Mathematically, this looked like:

```text
f: X → Y
```

Where:

- `X` is the input space
- `Y` is the desired output space
- `f` is the transformation that maps input into output

At first, this was only a debugging model.

Later, it became the way I understood ETL pipelines.

---

## 2. The Airflow Reality Check

When I later struggled with Airflow configuration, environment setup, parameters, and repeated errors, I almost gave up.

After finally getting it to work, I had another realization:

```text
Wait — this is just my local ETL with extra steps.
```

Airflow changed the execution environment, but it did not change the core transformation logic.

The real transformation still lived in Python code.

Airflow added:

- scheduling
- monitoring
- dependency management
- retries
- operational visibility
- runtime orchestration

That led to an important distinction:

```text
Core
= the part that changes business meaning

Enablers
= the parts that protect, schedule, validate, observe, retry, or stabilize the work
```

Examples:

| Component | Role |
|---|---|
| Data transformation logic | Core |
| Airflow | Enabler |
| Pandera schema validation | Enabler |
| Unit tests | Enabler |
| Logging / metrics | Enabler |
| Idempotent writes / retries | Enabler |

This distinction helped me avoid confusing tooling complexity with computational essence.

---

## 3. Core vs Enablers

The Core vs Enablers model became a way to reason about systems.

The Core asks:

```text
What actually changes the business meaning?
```

The Enablers ask:

```text
What makes the core work safer, more observable, more repeatable, or more reliable?
```

A simple checklist emerged:

1. Does this step change the business meaning?
   - If yes, it is probably Core.
2. If this step is removed, would the output values change?
   - If yes, it is probably Core.
3. Is this step mainly for validation, scheduling, observability, security, retry, or resilience?
   - If yes, it is probably an Enabler.

This was not only a tooling distinction.

It became the foundation for thinking about semantic correctness.

---

## 4. From ETL Correctness to Semantic Correctness

Local ETL and DAG systems exposed a deeper problem.

A pipeline can run successfully.

Every node can finish.

The schema can match.

The row count can look reasonable.

But that still does not prove the output means what it is supposed to mean.

This became the original Compass question:

```text
How do I know each transformation still preserves the intended business meaning?
```

At this stage, Compass was not a streaming system.

It was closer to a semantic governance idea for ETL DAGs.

The early intuition was:

```text
Each DAG node should not only produce output.
It should prove that the output still means what it is supposed to mean.
```

This was the first form of Compass:

```text
A semantic protocol between transformation boundaries.
```

---

## 5. The Abstract Compass Protocol Problem

The first version of Compass was too abstract.

In theory, it could be applied to many systems:

- local ETL
- Airflow DAGs
- dbt models
- Prefect flows
- agent workflows
- analytical pipelines

But the more abstract it became, the harder it was to evaluate.

A realistic reviewer could ask:

- Where does this protocol actually run?
- What state does it protect?
- What happens under retry?
- What happens under partial failure?
- Can it handle production-like flow?
- Is this a real system or only an architecture essay?

That was the turning point.

The problem was not that Compass was wrong.

The problem was that Compass needed a body.

---

## 6. Why Streaming / Event Sourcing Became the Runtime Body

Streaming and event sourcing were not the origin of Compass.

They became the runtime body for Compass because they exposed the right boundaries:

- candidate events
- accepted history
- state mutation
- idempotency
- concurrency
- replay
- projection correctness
- failure recovery
- snapshots
- trust boundaries

In ETL, Compass mostly checks meaning after transformation.

In event sourcing, Compass can check meaning before mutation enters accepted history.

That changed the role of Compass:

```text
semantic validation after data transformation
```

became:

```text
semantic admission before accepted history
```

This made the project more concrete.

Compass was no longer only an abstract semantic protocol. It became a correctness boundary inside a runtime where wrong events, stale projections, retry behavior, and replay mismatches could actually be tested.

---

## 7. The Real Transition

The real transition was not:

```text
ETL → Streaming
```

The real transition was:

```text
abstract semantic protocol
→ concrete runtime evidence
```

More precisely:

```text
Local ETL / DAG
  ↓
Core vs Enablers
  ↓
Pipeline success does not imply semantic correctness
  ↓
Compass as an abstract semantic governance protocol
  ↓
The abstraction becomes hard to evaluate
  ↓
Streaming / event sourcing becomes the runtime body
  ↓
Compass becomes a boundary for protecting accepted history
```

This is why the project eventually became **Streaming System + Compass**.

Not because streaming was the starting point, but because streaming gave Compass a concrete failure model.

---

## 8. Relationship to the Current Project

This origin path explains several design choices in the current repository:

| Origin Insight | Project Expression |
|---|---|
| Input → Bridge → Output | Command → Pipeline → Accepted Event / Derived State |
| Core vs Enablers | Domain semantics separated from reliability mechanisms |
| Airflow debugging pain | Boundary-first implementation discipline |
| Pipeline success is not semantic correctness | Compass validation and replay / drift checks |
| Abstract Compass was hard to evaluate | Streaming / event sourcing as concrete runtime body |
| Need for accepted evidence | accepted history as authority |
| Need for safe mutation | candidate events must pass admission before durable truth |

The project’s later stages extend this same path:

```text
accepted history
→ derived runtime state
→ semantic outcome
→ decision receipt
→ runtime policy
→ strategy selection
→ retry governance
```

---

## 9. Final Reflection

Compass started from a simple ETL question:

```text
Did this transformation still mean what I intended?
```

It then became a broader semantic correctness problem:

```text
Can a system technically succeed while producing the wrong business meaning?
```

Finally, through streaming and event sourcing, it became a runtime boundary:

```text
Which candidate events should be allowed to become accepted history?
```

The core idea stayed the same:

```text
Technical success does not guarantee semantic correctness.
```

But the evidence form changed.

At first, Compass was an idea about ETL DAG correctness.

Later, it became an abstract semantic protocol.

Eventually, it became a concrete event-driven runtime designed to test and protect business meaning under failure.

Streaming was not the origin of Compass.

```text
Streaming was the body that made Compass testable.
```
