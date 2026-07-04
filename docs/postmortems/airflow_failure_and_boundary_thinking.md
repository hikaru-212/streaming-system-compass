# Airflow Failure and Boundary Thinking

[← Back to Postmortems](README.md)

**Recorded on:** 2026-07-04

## Summary

This postmortem records an early engineering failure that shaped how this project approaches system design.

Around August 2025, while building my first local ETL project, I reached the Airflow stage and lost the clear reasoning discipline that had guided the earlier MVP work. I had been asking why each tool was needed, what problem it solved, and whether it belonged to the core logic or the supporting system. But under pressure, my behavior changed.

I stopped reasoning clearly.

I started copy-pasting.

The Airflow pipeline did not fail in a simple way. It looked as if the ETL flow executed only the extract and transform parts, but not the load part. The pipeline would not complete, and I did not understand which boundary was responsible.

At that point, I was not debugging with a model of the system.

I was doing this:

```text
error
  ↓
copy to AI
  ↓
paste command back
  ↓
new error
  ↓
repeat
```

AI was involved, but understanding was not.

The setup eventually worked only after I almost rebuilt the Docker / Airflow configuration from scratch. The pipeline finally ran, but the experience left a lasting impression.

It also produced a deeper engineering lesson:

```text
The first problem is not always the bug.
The first problem is not knowing which boundary the bug belongs to.
```

---

## Trigger

The immediate trigger was an Airflow configuration and execution problem in a local ETL project.

The intended pipeline was simple at the conceptual level:

```text
extract
→ transform
→ load
```

But the runtime behavior did not match the conceptual model. The pipeline seemed to execute only part of the flow, and the load step did not complete as expected.

The actual confusion was not only:

```text
Why did Airflow fail?
```

It was:

```text
Which layer owns this failure?
```

Possible boundaries included:

- Python transformation logic
- Airflow DAG definition
- Airflow task dependency configuration
- Docker environment setup
- connection configuration
- file path / volume mapping
- task execution state
- scheduler / worker behavior
- database load behavior

Without a boundary model, every error became a black box.

---

## Initial Assumption

The implicit assumption was:

```text
If I give the error to AI and apply the suggested fix, the system should eventually work.
```

This was not completely unreasonable.

For small syntax errors or local configuration mistakes, copy-paste debugging can sometimes work. The problem was that Airflow was not a single local function. It was an orchestration environment composed of several moving parts.

The failure could live in code, configuration, scheduling, dependency ordering, runtime environment, mounted paths, or task state.

A single error message was not enough to identify the responsible boundary.

---

## Why the Assumption Looked Reasonable

The assumption looked reasonable because earlier project work had been incremental.

The project started from an MVP. Tools were added one by one. Each tool appeared to solve a concrete problem:

- scheduling
- dependency management
- retry
- observability
- environment isolation
- reproducibility

At that stage, adding Airflow seemed like a natural next step.

But Airflow changed the operational surface area of the project. The core transformation logic was still Python, but the execution environment became larger.

That distinction was not yet clear enough.

---

## Failure Mode

The failure mode was not only a broken Airflow setup.

The deeper failure mode was:

```text
operating a system without first identifying its responsibility boundaries
```

That produced several bad debugging behaviors:

- treating every error as equally local
- accepting AI suggestions without mapping them to a system layer
- changing configuration without knowing which invariant the change was supposed to restore
- solving symptoms without knowing whether the core transformation or the runtime enabler was failing
- reaching a working setup without understanding why it worked

Even when the pipeline finally succeeded, the success did not feel trustworthy.

The system worked, but I did not yet own the model.

---

## Corrected Understanding

The corrected model was:

```text
Before debugging an error, identify the boundary that could own the error.
```

A pipeline is not just code.

It is a composition of boundaries:

```text
business transformation logic
+ orchestration
+ environment
+ scheduling
+ state
+ retries
+ persistence
+ observability
```

Those parts should not be debugged as if they are the same layer.

The Airflow struggle taught me to ask:

- What is the core?
- What is only an enabler?
- Where does the state change?
- Where is the source of truth?
- What can be retried safely?
- What should be admitted into durable history?
- What should be rejected before mutation?

These questions later became central to Streaming System + Compass.

---

## Reusable Rule

```text
Do not enter code-level or tool-level debugging before identifying the boundary of responsibility.
```

More specifically:

```text
A tool failure should first be mapped to a system boundary.
Only then should the implementation detail be changed.
```

---

## Relationship to Compass

This postmortem predates Streaming System + Compass, but it explains one of the roots of the project’s working style.

Compass later formalizes a stronger version of the same habit:

```text
candidate output
→ boundary review
→ accepted fact
```

The Airflow failure was an early personal version of that lesson.

I had many candidate fixes.

But I did not yet have a clear admission boundary for deciding which fix actually matched the system’s failure mode.

---

## Non-Goals

This postmortem does not claim that Airflow was the wrong tool.

It also does not attempt to document the exact final Airflow fix.

The important lesson is not about one Airflow configuration.

The important lesson is about the engineering habit that emerged from the failure:

```text
boundary first, implementation second
```

---

## Final Lesson

```text
Without a boundary model, every error becomes a black box.
Every fix becomes a guess.
Even when the system works, the engineer may not know why it works.
```
