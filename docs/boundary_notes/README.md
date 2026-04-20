# Boundary Notes

## Purpose

This folder contains boundary notes for the core modules of the project.

These notes are not meant to replace implementation or architecture documents.  
Their purpose is narrower and more practical:

- clarify what each module is responsible for
- clarify what each module is **not** responsible for
- reduce semantic confusion during implementation
- preserve design intent as the codebase grows

---

## Why This Folder Exists

As the project evolved, it became clear that many implementation questions were not caused by syntax alone.

They were often caused by **boundary confusion**, such as:

- which module owns a given value
- whether a function should decide something or only carry it
- whether a layer validates meaning, stores it, or derives it
- whether a component belongs to write-side truth, read-side derivation, or runtime governance

Because of that, these notes exist as a middle layer between:

- high-level architecture documents
- low-level code implementation

They help keep the project readable at the module-boundary level.

---

## What These Notes Are For

Boundary notes are especially useful when asking questions such as:

- Why does this parameter get passed in rather than computed here?
- Why is this module not allowed to decide that value?
- Why does this layer validate but not persist?
- Why does projection ignore some event metadata?
- Why is proof used in transition validation but not in projection logic?

These are not merely coding-style questions.  
They are boundary questions.

---

## What These Notes Are NOT

These notes are **not** intended to be:

- full architecture specifications
- user-facing documentation
- API references
- implementation details for every function

Those concerns belong elsewhere:

- architecture → `docs/architecture/`
- roadmap → `docs/roadmap/`
- code → `src/`
- tests → `tests/`

---

## Current Notes

This folder currently includes notes for the most important early-stage boundaries:

- `event_module.md`
- `proof_module.md`
- `aggregate_module.md`
- `event_store_module.md`
- `idempotency_module.md`
- `registry_module.md`
- `projection_module.md`
- `checkpoint_module.md`

These were prioritized because they directly affect the first implementation stages of the project.

---

## How to Use These Notes

A practical reading order is:

1. `event_module.md`
2. `proof_module.md`
3. `aggregate_module.md`
4. `event_store_module.md`
5. `idempotency_module.md`
6. `registry_module.md`
7. `projection_module.md`
8. `checkpoint_module.md`

This roughly follows the intended semantic development order of the project:

- define event meaning
- define proof meaning
- define aggregate decision logic
- define persistence boundaries
- define request safety boundaries
- define orchestration boundaries
- define state-derivation boundaries
- define runtime progress boundaries

---

## Relationship to the Rest of the Project

These notes should be read together with:

- `src/core/order/README.md`
- `src/storage/README.md`
- `src/pipeline/README.md`
- `src/compass/README.md`
- `docs/architecture/transactional_core.md`
- `docs/architecture/compass_layers.md`
- `docs/roadmap/implementation_roadmap.md`

A good rule of thumb is:

- if you are confused about **what the system is trying to become**, read the roadmap
- if you are confused about **how the major layers relate**, read the architecture docs
- if you are confused about **what one module should or should not do**, read the boundary notes

---

## Guiding Principle

The main purpose of this folder is to prevent this kind of failure:

> entering code-level detail before module-level responsibility is clear

In other words:

- first set the scale
- then identify the role
- then inspect the detail

This keeps implementation aligned with the system’s semantic design rather than letting local code decisions drift into architectural confusion.

---

## Summary

This folder is a practical design aid.

It exists to make module boundaries explicit before they become accidental.