# Domain Specifications

[← Back to Docs Home](../README.md)

This directory contains domain-level specifications and domain decision notes for **Streaming System + Compass**.

These documents define:

- business meaning of domain states and events
- aggregate-level legality rules
- domain invariants
- versioned scope boundaries of the domain model
- known limitations intentionally deferred to later versions
- future semantic evolution paths
- domain-level reasoning behind staged design decisions

---

## Domain Specs vs Other Docs

Domain documents are intentionally different from other documentation areas:

- [Architecture Notes](../architecture/README.md) describe system structure, module boundaries, and runtime scope.
- [Architecture Decision Records](../adr/README.md) record architectural decisions and their rationale.
- [Boundary Notes](../boundary_notes/README.md) clarify module-level ownership and responsibility boundaries.
- [Roadmaps](../roadmap/README.md) describe implementation order and milestone sequencing.
- [Postmortems](../postmortems/README.md) capture lessons learned from design or implementation failures.

---

## Current Documents

| Document | Type | Purpose |
|---|---|---|
| [Order Domain v1 Rules](order_domain_v1_rules.md) | Domain specification | Defines the current v1 business semantics for the order domain. |
| [Why Transition Correctness Came Before Full Domain Invariants](decision_note_transition_first_then_domain_invariants.md) | Domain decision note | Explains why transition correctness was stabilized before tightening full domain business invariants. |

---

## What `Order Domain v1 Rules` Covers

[Order Domain v1 Rules](order_domain_v1_rules.md) defines the current v1 order-domain model, including:

- the meaning of `INIT`, `CREATED`, and `PAID`
- aggregate-level legality rules
- monetary constraints for the minimal write-side model
- idempotency ownership and retry behavior boundaries
- event/state alignment rules
- known out-of-scope limitations for v1

---

## What the Transition-First Decision Note Covers

[Why Transition Correctness Came Before Full Domain Invariants](decision_note_transition_first_then_domain_invariants.md) explains why the project initially emphasized:

- state-machine legality
- predecessor proof structure
- sequence progression
- transition truth against prior history
- Compass Layer 1 correctness

before fully tightening:

- amount reasonableness
- business payload legality
- event type / numeric payload alignment
- request-boundary semantics
- stricter domain invariants

The key point is:

> transition correctness is necessary, but not sufficient.

The current write-side model must combine both:

- transition-system correctness
- domain-payload correctness

---

## Why Versioned Domain Documents Exist

The project is expected to evolve in semantic scope over time.

For example:

- v1 may support only `INIT -> CREATED -> PAID`
- later versions may introduce `PAYING`, partial payment, refund, or reconciliation logic

Those changes are not only implementation changes.  
They are changes in the domain model itself.

Because of that, versioned domain specifications are useful for:

- preserving a stable semantic baseline
- making scope boundaries explicit
- showing what is intentionally out of scope in a given version
- documenting future evolution without rewriting history

---

## Reading Guideline

When reading domain specifications, interpret them as:

- source-of-truth documents for business meaning
- constraints that the aggregate must enforce
- complements to, not replacements for, architecture and ADR documents

A good rule of thumb is:

- if the question is **what does this business state or event mean?**, read [Order Domain v1 Rules](order_domain_v1_rules.md)
- if the question is **why domain invariants were tightened after transition correctness**, read [Why Transition Correctness Came Before Full Domain Invariants](decision_note_transition_first_then_domain_invariants.md)
- if the question is **which module owns this responsibility?**, read the [Architecture Notes](../architecture/README.md) or [Boundary Notes](../boundary_notes/README.md)
- if the question is **why was this technical direction chosen?**, read the [ADRs](../adr/README.md)