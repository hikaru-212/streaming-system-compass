# ADR 0028: Defer Dynamic Strategy Selection Until Multiple Eligible Execution Paths Exist

[← Back to ADR Index](README.md)

## Status

Accepted

## Implementation Status

Stage 4D Strategy Selection Authority remains a valid architectural
responsibility. Its production implementation is deferred.

No `StrategySelector`, runtime strategy policy, strategy identity, registry, or
new execution composition is introduced by this decision.

---

## Context

[ADR 0027](0027_separate_runtime_decision_strategy_and_retry_authority.md)
separates four responsibilities:

```text
Stage 4C
= current-response authority

Stage 4D
= HOW selection inside prior authorization

Stage 4E
= another-invocation authority

execution
= separate responsibility
```

Current production write-side composition is static. A
`PostgresTransactionalWriteSide` is constructed with one validation runtime,
one admission-gate factory, and one `PostgresWriteSideConfig`. The config fixes
validation placement for that writer, while the factory fixes how a concrete
admission gate is created for each command invocation.

The established compositions are construction choices:

```text
PRE_TRANSACTION + optimistic concurrency control

IN_TRANSACTION + pessimistic admission
```

No currently authorized operation exposes both paths as dynamically eligible
runtime alternatives. No reviewed runtime evidence or policy chooses between
them.

The completed Stage 4C-to-4E executable experiment confirmed that the first
Stage 4E profile can be modeled without a dynamic Stage 4D selector. It also
exposed a separate invariant: authority derived from invocation A1 must not be
consumed through a silently substituted execution composition for A2. Stage 4E
must preserve the applicable composition; it must not become an implicit
strategy selector.

The experiment used exact Python writer-instance retention to demonstrate that
invariant. That is an experimental proof mechanism, not a durable writer
identity contract or a reason to introduce a strategy registry.

## Decision

Retain Stage 4D Strategy Selection Authority as the owner of dynamic `HOW`
selection inside prior authorization.

Do not implement a production Stage 4D selector now.

For the first formal Stage 4E slice, preserve the execution composition already
owned for A1. Stage 4E authorization must not grant authority to replace that
composition for A2. A private in-process owner may retain the already-configured
writer transitively when that is sufficient; doing so does not create a public
or durable writer identity.

## Evidence

The deferral is grounded in current source and executable behavior:

- existing write-side strategy composition is static;
- `ValidationPlacement` is selected through immutable writer configuration;
- the admission strategy is supplied through writer construction;
- no currently authorized operation has multiple simultaneously eligible
  runtime strategies;
- no reviewed runtime `HOW`-selection rule exists;
- adding a selector now would not change observable behavior;
- the first Stage 4E profile requires composition preservation, not dynamic
  composition selection.

The absence of a current selector consumer is a repository fact. It is not an
architecture verdict that Stage 4D responsibility is invalid.

## Re-entry Condition

Stage 4D implementation should be reconsidered when all of the following exist:

```text
one already-authorized operation
+ multiple dynamically eligible execution strategies
+ reviewed evidence capable of choosing among them
+ observable behavioral value from runtime selection
```

The proposal must identify the existing authority, the eligible strategies,
the evidence that can choose among them, the observable behavior changed by the
selection, and the refusal behavior when no reviewed selection is available.

## Explicit Boundary

```text
strategy exists
!= dynamic strategy selection required

static composition
!= Stage 4D runtime selector

Stage 4E re-invocation authorization
!= permission to change HOW

same writer instance as private in-process ownership
!= durable semantic writer identity

consumer absence
!= evidence that Stage 4D responsibility is invalid
```

Stage 4D selects only among paths already eligible under prior authority. It
does not create current-response authority, another-invocation authority, or
execution authority.

## Consequences

### Positive

- Stage 4D remains available when a real dynamic selection problem appears.
- Stage 4E cannot silently acquire strategy-selection authority.
- The first Stage 4E profile can use the smallest source-grounded in-process
  composition ownership without introducing public semantic identity.
- Production avoids a selector that currently has no observable choice to make.

### Deferred

- Dynamic selection between validation/admission compositions is not available.
- Runtime health or cost evidence does not yet select a write-side strategy.
- Any future selector API remains unfrozen until the re-entry condition is met.

## Non-Goals

This ADR does not:

- implement `StrategySelector`;
- freeze a selector API;
- select `PRE_TRANSACTION`/optimistic versus
  `IN_TRANSACTION`/pessimistic at runtime;
- define snapshot fast-path policy;
- create writer, strategy, execution-plan, or topology identities;
- create strategy or policy registries;
- implement Stage 4E authorization or execution;
- authorize automatic A2 or A3 invocation;
- add production code, tests, migrations, dependencies, or persistence.

## Relationship to Stage 4E

The first formal Stage 4E boundary is documented in
[Stage 4E — Same-Request Re-Invocation Authority](../implementation_notes/stage_4e/README.md).
That boundary may require a small in-process owner to retain the complete
request, A1 evidence, and existing writer composition. Such retention preserves
the current `HOW`; it is not a Stage 4D selector.
