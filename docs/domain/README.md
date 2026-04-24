# Domain Specifications

This directory contains domain-level specifications for the project.

These documents define:

- business meaning of domain states and events
- aggregate-level legality rules
- domain invariants
- versioned scope boundaries of the domain model
- known limitations that are intentionally deferred to later versions
- future semantic evolution paths

These documents are intentionally different from other documentation areas:

- `docs/architecture/` describes system structure, module boundaries, and runtime scope
- `docs/adr/` records architectural decisions and their rationale
- `docs/roadmap/` describes implementation order and milestone sequencing
- `docs/postmortems/` captures lessons learned from design or implementation failures

## Current documents

### `order_domain_v1_rules.md`
Defines the current v1 business semantics for the order domain.

This includes:

- the meaning of `INIT`, `CREATED`, and `PAID`
- aggregate-level legality rules
- monetary constraints for the minimal write-side model
- idempotency ownership and retry behavior boundaries
- event/state alignment rules
- known out-of-scope limitations for v1

## Why versioned domain documents exist

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

## Reading guideline

When reading domain specifications, interpret them as:

- source-of-truth documents for business meaning
- constraints that the aggregate must enforce
- complements to, not replacements for, architecture and ADR documents

A good rule of thumb is:

- if the question is **what does this business state or event mean?**, read the domain specification
- if the question is **which module owns this responsibility?**, read the architecture notes
- if the question is **why was this technical direction chosen?**, read the ADRs
