# ADR 0002 Evolution Note

This note records how ADR 0002 evolved before being committed as the current version.

Its purpose is not to preserve every intermediate wording choice, but to preserve the key design shifts that shaped the final document.

---

## Why This Note Exists

ADR 0002 did not emerge in a single pass.

It evolved through multiple refinements as the project clarified:

- how Compass validation should be separated from registry orchestration
- how validation depth should become runtime-configurable
- how runtime enablers should remain structurally replaceable
- how validation cost should become observable rather than implicit

This note preserves that decision trace.

---

## v1 — From Hard-Wired Strict Validation to Runtime Structure

The earliest version focused on one primary transition:

- moving Compass away from a strict validation step hard-coded directly inside the registry
- introducing the idea of:
  - `TransitionValidator`
  - `ValidationDispatcher`
  - `ValidationRunner`
  - `ValidationPolicy`

The main architectural shift in v1 was:

> validation should become a runtime subsystem rather than a single inline conditional branch

At this stage, the emphasis was on:
- separation of concerns
- modular validation flow
- future support for strict/off/warn/shadow-like modes

---

## v2 — Structural Typing for Runtime Enablers

The next refinement addressed a more subtle architectural question:

- why should runtime enablers such as validators and concurrency gates prefer `Protocol` over nominal inheritance?

This version clarified that:

- the registry is an orchestration boundary
- orchestration should depend on behavior, not on bloodline
- runtime enablers are mechanisms, not semantic truth objects
- structural typing improves replaceability and reduces friction at runtime boundaries

The main architectural shift in v2 was:

> runtime flexibility should be preserved through structural contracts, while semantic rigidity may still be introduced later where it truly belongs

This version made the ADR more than a validation-design note.  
It turned it into a statement about runtime boundary philosophy.

---

## v3 — Telemetry and Semantic Intent Safeguards

The final refinement clarified two additional concerns.

### 1. Validation cost must be measurable

ADR 0002 was strengthened to make explicit that the project is not only interested in semantic correctness itself, but also in the runtime cost of achieving that correctness.

This is why the ADR now emphasizes:

- logic validation time
- I/O time
- total validation cost
- observability of correctness overhead

The key shift here was:

> correctness is not enough; the cost of correctness must also be attributable

### 2. Structural flexibility requires compensating safeguards

Because structural contracts can make semantic intent more implicit, the final version also made room for compensating controls such as:

- strong contract tests
- stable validation-result shape expectations

The key shift here was:

> flexibility at the runtime boundary must be balanced by stronger testing discipline

---

## What Changed Across Versions

In simplified form:

- **v1** established the runtime validation structure
- **v2** clarified why runtime enablers should remain structurally typed
- **v3** clarified why validation telemetry matters and why structural freedom needs explicit safeguards

---

## What Stayed Constant

Despite refinement, several core ideas remained stable across all versions:

- registry should remain an orchestration boundary
- validation semantics should not be owned directly by the registry
- Compass should evolve from hard-wired strict checking toward a more intentional runtime model
- the project should preserve semantic rigor while remaining operationally evolvable

---

## Final Interpretation

The final version of ADR 0002 should therefore be read as the result of three converging concerns:

1. **semantic explicitness**
2. **runtime flexibility**
3. **cost observability**

This evolution is part of the broader direction of the project:
to turn Compass from a simple validation step into a more principled semantic runtime layer.

---

## Summary

ADR 0002 evolved from:

- a validation refactor note

into:

- a runtime architecture decision record that explains
  - how validation is dispatched
  - why runtime enablers are structurally typed
  - how correctness cost should be measured
  - and how flexibility should be balanced with semantic discipline