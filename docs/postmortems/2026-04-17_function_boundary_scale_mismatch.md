# Postmortem: Scale Mismatch in Reading Function Boundaries

[← Back to Postmortems Index](README.md)

## 1. Context

While reading and refining the event-sourcing code in this project, I repeatedly got stuck on seemingly small questions such as:

- Why does `OrderEvent.create()` need `sequence` as an input?
- Why is `expected_current_version` computed outside `EventStore.append()`?
- Why do some functions appear to receive values decided elsewhere instead of deciding them internally?

At first glance, these looked like local code-reading issues.  
However, the repeated confusion suggested that the real problem was not syntax itself, but how I was choosing the scale at which I read the code.

---

## 2. Problem

The direct problem was that I kept questioning individual parameters and function signatures in isolation, without first identifying the architectural role of each component.

As a result, I treated a medium-scale component-boundary problem as if it were only a line-by-line function reading problem.

This caused multiple misunderstandings:

- expecting a data carrier to make business decisions
- expecting a storage layer to infer semantic meaning
- expecting a function to explain values whose origin actually belonged to another layer

---

## 3. Root Cause

The root cause was **scale mismatch**.

I entered the code from a micro-level reading mode too early.  
Instead of first asking:

- What role does this module play in the system?
- Is this component a decision-maker, data carrier, validator, or coordinator?
- Which layer owns this value?

I immediately asked:

- Why does this parameter exist here?
- Why doesn’t this function decide the value by itself?

Because the architectural boundary was not established first, local details appeared arbitrary or semantically broken.

---

## 4. What I Realized

This was not merely a function-level issue.  
It was a **medium-level architectural boundary issue**.

For example:

- `OrderEvent` is a data contract / event format
- `OrderAggregate` is the domain decision-maker
- `EventStore` is the persistence and version-validation layer
- `OrderRegistry` is the orchestration layer

Once these roles are clear, many local questions disappear naturally.

For instance, `sequence` should not be decided by `OrderEvent`, because `OrderEvent` is not the owner of version progression.  
That responsibility belongs to `OrderAggregate`.

---

## 5. Resolution

The effective solution was to return to my own IBO / fractal thinking model.

### Step 1: Re-establish the system scale
First identify:

- Input
- Bridge
- Output

### Step 2: Split the Bridge into Core and Enablers
Clarify:

- Core: components that create domain meaning
- Enablers: components that protect correctness, consistency, retry safety, and orchestration

### Step 3: Only then inspect individual functions
At that point, function parameters can be evaluated in the right context:

- Who owns this value?
- Who decides it?
- Who consumes it?
- Is this function doing decision, packaging, validation, or coordination?

---

## 6. Key Takeaway

What looked like a local code confusion was actually a failure to align reading scale with architectural scale.

The correction was not simply “read more carefully,” but:

- define the boundary first
- identify the role first
- inspect the parameter later

In short:

- First set the scale
- Then identify the role
- Then inspect the detail

---

## 7. Reusable Lesson

For future system reading and design work, I should avoid entering detailed function-level analysis too early when the problem is actually about component interaction.

A more reliable sequence is:

1. identify module role
2. identify boundary and ownership
3. identify data flow
4. only then inspect function signatures and local logic

This applies not only to code reading, but also to system design, debugging, and architectural documentation.

---

## 8. Follow-up Action

To prevent similar confusion in the future, I should add short boundary notes for core modules such as:

- `event.py`
- `aggregate.py`
- `event_store.py`
- `registry.py`
- `projection.py`

Each note should briefly state:

- what the module does
- what it does not do
- who provides its inputs
- who consumes its outputs
- what invariants it must preserve