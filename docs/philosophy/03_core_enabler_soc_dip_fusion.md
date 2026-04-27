# Core/Enabler as Semantic Fusion of SoC and DIP

[← Back to Philosophy Index](README.md)

## Purpose

This note connects the **Core / Enabler** model to two classical software architecture principles:

- Separation of Concerns (SoC)
- Dependency Inversion Principle (DIP)

This note is a derived interpretation of the Core / Enabler model.

The original model came from debugging, ETL workflow analysis, and the Input–Bridge–Output framework. This document explains how that model also maps naturally onto established software architecture language.

---

## 1. Traditional View: SoC and DIP as Separate Principles

In traditional software architecture, SoC and DIP are usually treated as related but distinct principles.

| Principle | Focus | Typical Expression |
|---|---|---|
| Separation of Concerns | divide responsibilities | validation, storage, business logic, and presentation are separated |
| Dependency Inversion | reverse dependency direction | high-level logic depends on abstractions rather than concrete implementations |

SoC divides.
DIP redirects.

They often work together, but they are usually explained separately.

---

## 2. Core / Enabler View

The Core / Enabler model reframes the same problem semantically.

### Core

The Core owns intent, business meaning, and semantic contracts.

It answers:

- what does this system mean?
- what business transformation is being performed?
- what invariants must remain true?
- what is the irreducible work?

### Enabler

The Enabler provides tools, mechanisms, and runtime support.

It answers:

- how is the Core validated?
- how is it persisted?
- how is it scheduled?
- how is it observed?
- how is it protected under failure?

This distinction separates not only code responsibilities, but layers of intent.

---

## 3. How Core / Enabler Expresses SoC

Core and Enabler naturally express Separation of Concerns.

The Core should not own infrastructure concerns such as:

- scheduling
- monitoring
- retries
- storage implementation details
- schema tooling internals
- external orchestration mechanics

Enablers should not redefine business meaning.

For example:

- an aggregate owns domain legality
- an idempotency store owns retry identity memory
- a concurrency gate owns admission continuity
- Compass owns semantic validation
- a projection worker owns derived state construction

Each boundary exists to prevent meaning from leaking into the wrong layer.

This is SoC, but expressed through semantic ownership.

---

## 4. How Core / Enabler Expresses DIP

Core / Enabler also expresses Dependency Inversion.

The Core should define the semantic contract.
Enablers should conform to that contract.

For example:

```text
Core-defined need:
  validate this candidate event against transition truth

Possible enablers:
  strict validator
  shadow validator
  warning-only validator
  future validation backend
```

The Core should not depend on a specific tool.
The tool should depend on the Core's intent.

This means dependency inversion is not just a code import direction.
It is an intent direction:

> tools must serve meaning, not the other way around.

---

## 5. Semantic Fusion

The Core / Enabler model fuses SoC and DIP into one structure.

| Classical Principle | Core / Enabler Interpretation |
|---|---|
| SoC | separate semantic ownership from support mechanisms |
| DIP | make support mechanisms depend on Core-defined intent |
| Result | tools become replaceable without changing the meaning of the system |

This is why Core / Enabler is not only a naming preference.

It is a way to reason about architecture by asking:

```text
What owns meaning?
What protects meaning?
What should be replaceable?
What must remain stable?
```

---

## 6. Example in Streaming System + Compass

In this project:

| Core / Enabler | Project Example |
|---|---|
| Core | order domain rules, aggregate legality, event semantics |
| Enabler | idempotency, concurrency gate, Compass validation, projection, checkpointing |
| Stable semantic contract | `INIT -> CREATED -> PAID` domain rules in v1 |
| Replaceable mechanism | validation dispatch, admission strategy, persistence backend |

The project does not treat runtime tools as semantic truth.

Instead:

- the domain defines meaning
- the aggregate enforces command legality
- Compass validates transition truth
- the event store / admission gate protects accepted history
- idempotency protects request retry safety
- projection derives read-side state

This keeps the system modular not only structurally, but semantically.

---

## 7. Philosophical Implication

In this view:

- separation is not only about files or classes
- inversion is not only about interfaces
- architecture is not only about dependency arrows

The deeper goal is to preserve intent.

Core / Enabler turns two engineering rules into one semantic law:

> Tools exist to serve meaning, and meaning must not be enslaved by tools.

---

## 8. Summary

Core / Enabler can be seen as a semantic fusion of SoC and DIP.

It separates:

```text
meaning-producing logic
from
meaning-protecting mechanisms
```

It inverts:

```text
tooling dependency
back toward
Core-defined semantic intent
```

This is why the model is central to Streaming System + Compass.

The project is not only separating modules.
It is separating responsibility for meaning, execution, validation, and recovery.
