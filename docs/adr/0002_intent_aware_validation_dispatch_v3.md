# ADR 0002: Intent-Aware Validation Dispatch for Compass Runtime

## Status

Proposed

---

## Context

The current transactional core uses a strict, hard-wired Compass validation path:

1. candidate event is produced
2. Compass validation runs immediately
3. rejected event is blocked
4. accepted event is persisted

This design is suitable for the first proof-carrying transactional prototype because it makes semantic admission explicit and easy to demonstrate.

However, it also has clear limitations:

- validation is tightly coupled to the registry flow
- every event is treated as if it deserves the same validation cost
- there is no clean way to support optional, downgraded, or shadow validation
- validation cost is not measured in a structured way
- registry currently knows too much about validation behavior

As the system evolves, the project needs a more flexible runtime model that can support different validation depths depending on event criticality, operational intent, and runtime policy.

---

## Decision

Compass runtime validation will evolve from a hard-wired strict check into an **intent-aware validation dispatch architecture**.

The new design separates validation into four concerns:

1. **TransitionValidator**
   - owns semantic checking only
   - validates a candidate event against contextual truth
   - returns a structured `ValidationResult`

2. **ValidationDispatcher**
   - decides which validator or validation depth should be used
   - bases the decision on event type, risk, trust level, or runtime policy

3. **ValidationRunner**
   - executes the selected validator
   - records telemetry such as logic time and I/O time
   - produces a complete validation result

4. **ValidationPolicy**
   - translates validation outcome into an enforcement action
   - determines whether the event should be allowed, blocked, warned, or shadow-recorded

The registry must not directly own validation semantics.  
It should only consume the final enforcement action.

This design aims not only to preserve semantic correctness, but also to make the runtime cost of correctness observable and attributable.

---

## Design Goals

This decision is intended to support the following goals:

- keep the registry as an orchestration boundary, not a semantic ownership layer
- allow different validation depths for different event categories
- preserve strict full-proof validation for critical transactional paths
- support optional lower-cost validation for low-risk events
- make validation cost observable and explainable
- prepare the system for future shadow or warn-only modes without rewriting registry flow

---

## Non-Goals

This decision does **not** attempt to solve all future validation needs immediately.

It does not yet require:

- a distributed validation fabric
- asynchronous validator execution
- policy learning or ML-based routing
- fully dynamic runtime heuristics
- external telemetry infrastructure

The first implementation should remain rule-based and small.

---

## Proposed Runtime Structure

The intended flow is:

1. registry produces candidate event
2. dispatcher selects validator and validation profile
3. runner executes validation and captures telemetry
4. policy converts result into an enforcement action
5. registry uses enforcement action to continue or stop processing

Conceptually:

```text
request
→ registry
→ aggregate produces candidate event
→ validation dispatcher
→ validation runner
→ validation policy
→ enforcement action
→ registry decides persist / reject / warn / shadow
```

---

## Core Abstractions

### 1. `TransitionValidator`

A validator must implement a common contract.  
It receives:

- candidate event
- validation context

It returns:

- `ValidationResult`

A validator must not directly persist, block, or mutate registry flow.

### 2. `ValidationResult`

Validation must return more than a simple verdict.

The result object should include at least:

- verdict
- reason
- validator name
- validation depth
- logic validation time
- I/O time
- total time
- optional metadata

This is necessary because the project wants to measure not only correctness, but also the operational cost of correctness.

### 3. `ValidationDispatcher`

The dispatcher decides which validation path to use.

Examples:

- low-risk event → `NoOpValidator` or `SimpleSequenceValidator`
- standard event → `BasicTransitionValidator`
- critical transactional event → `FullProofValidator`

The dispatcher is rule-based in the initial version.

### 4. `ValidationRunner`

The runner is responsible for execution and telemetry.

It must distinguish between:

- logical validation cost
- I/O cost required to obtain truth context

This distinction is important because the project explicitly wants to understand whether Compass overhead comes from semantic checking itself or from surrounding storage access.

### 5. `ValidationPolicy`

The policy converts `ValidationResult` into an enforcement action.

Typical actions include:

- `ALLOW`
- `BLOCK`
- `ALLOW_WITH_WARNING`
- `SHADOW_ONLY`

This makes enforcement explicit and keeps policy separate from semantic checking.

---

## Design Rationale: Structural Typing for Runtime Enablers

In the current implementation direction of the Compass transactional path, runtime enablers such as:

- `TransitionValidator`
- `ConcurrencyGate`
- `IdempotencyProvider`

should prefer **structural contracts** (`Protocol`) over nominal inheritance (`ABC`) at the runtime boundary.

The reason is practical:

### 1. Orchestration should care about behavior, not bloodline

The registry is designed as an orchestration boundary.  
Its job is to coordinate:

- admission
- validation
- persistence
- enforcement

It should not need to know whether a validator or gate belongs to a particular inheritance tree.  
It only needs to know that the component provides the required behavior.

This keeps the registry aligned with dependency inversion and prevents unnecessary nominal coupling.

### 2. Runtime enablers should remain fluid and replaceable

Runtime enablers are mechanisms, not semantic truth objects.

They should be easy to swap:

- in-memory implementation → database-backed implementation
- no-op validator → full proof validator
- optimistic concurrency gate → different admission strategy

Structural typing is appropriate here because it reduces friction and avoids making runtime infrastructure depend on a shared class lineage.

### 3. This avoids over-hardening the wrong layer too early

Nominal inheritance can be useful when the system wants to strongly constrain semantic identity.

However, at the runtime-enabler layer, the current priority is:

- strategy fluidity
- plugin-like replaceability
- low coupling at orchestration boundaries

For that reason, `Protocol` is preferred here.

### 4. This does not reject stronger nominal contracts in the semantic core

This decision should not be interpreted as a general rejection of nominal identity.

A later semantic-core layer may still benefit from stronger nominal contracts when the purpose is to constrain semantic equivalence classes and reduce implementation ambiguity.

But that concern belongs more naturally to:

- semantic core modeling
- proof semantics
- validation-result shape guarantees

rather than to runtime orchestration enablers.

In short:

- semantic core may later justify stronger nominal boundaries
- runtime enablers currently prioritize structural replaceability

---

## Why This Decision Was Chosen

The previous strict inline approach is still valid for the first prototype, but it is too rigid as a long-term runtime model.

The new design was chosen because it preserves the important invariant:

> semantic validation remains explicit

while also allowing:

- validation depth control
- policy decoupling
- runtime observability
- future extensibility

It also aligns with the project’s broader architecture principle:

> core meaning should remain stable, while enablers should remain replaceable.

In this design:

- validator logic is core semantic enforcement
- dispatcher, runner, and policy are enablers around admission behavior

---

## Alternatives Considered

### Alternative A: Keep strict validation hard-coded in registry

**Pros**

- simplest first implementation
- easy to read in a prototype
- strong admission guarantee

**Cons**

- no clean extension path
- no structured telemetry separation
- registry becomes too aware of validation details
- hard to support mixed-cost validation paths

This approach is still acceptable for the earliest baseline version, but not ideal as the long-term runtime structure.

### Alternative B: Global mode switch only (`strict`, `off`, `warn-only`)

**Pros**

- easy to implement
- easy to reason about operationally

**Cons**

- too coarse
- all events in a mode pay the same treatment
- does not support intent-aware routing
- does not reflect domain criticality differences

This was rejected as too rigid.

### Alternative C: Fully dynamic heuristic or ML-based validation routing

**Pros**

- potentially adaptive
- can optimize runtime cost automatically

**Cons**

- too early
- difficult to explain
- weak as a first architecture baseline
- introduces additional uncertainty into a system whose main purpose is semantic clarity

This was rejected for the current stage.

---

## Consequences

### Positive Consequences

- validation becomes modular and measurable
- registry remains cleaner
- critical paths can keep strong proof validation
- lower-risk paths can use cheaper checks
- future shadow mode becomes much easier
- validation can be documented as a first-class runtime subsystem
- runtime enablers remain easier to swap and test

### Negative Consequences

- more abstraction than the first prototype
- more components to explain
- requires careful discipline to avoid overengineering
- may slow early implementation if too many validators are introduced at once
- if structural contracts are used carelessly, semantic intent may become too implicit

Because structural contracts can make semantic intent more implicit, runtime enablers should be supported by strong contract tests and stable validation-result shape expectations.

---

## Implementation Guidance

The first implementation of this design should stay intentionally small.

Recommended initial scope:

- `ValidationResult`
- `TransitionValidator` protocol
- `NoOpValidator`
- `FullProofValidator`
- simple rule-based `ValidationDispatcher`
- simple `ValidationPolicy` with only:
  - `ALLOW`
  - `BLOCK`

Optional later additions:

- `BasicTransitionValidator`
- `SimpleSequenceValidator`
- `ALLOW_WITH_WARNING`
- `SHADOW_ONLY`
- richer telemetry export
- runtime risk scoring

---

## Relationship to Existing Project Structure

This ADR does not replace the current transactional core.  
It refines how semantic admission should evolve inside it.

It is especially relevant to:

- `src/compass/`
- `src/pipeline/transactional/`
- `src/core/order/`
- `docs/architecture/transactional_core.md`

The transactional core still comes first.  
This ADR only describes how the validation boundary inside that core should be designed as the project matures.

---

## Summary

The project will move from a hard-wired strict Compass check toward an intent-aware validation dispatch architecture.

The key principle is:

- validators decide semantic truth
- policies decide enforcement
- registry only orchestrates

And at the runtime boundary:

- structural contracts are preferred for replaceable enablers
- stronger nominal constraints may be justified later in semantic-core contexts

This preserves semantic rigor while making validation depth, operational cost, and runtime behavior more explicit and more evolvable.
