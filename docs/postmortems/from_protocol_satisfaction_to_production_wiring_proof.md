# Postmortem: From Protocol Satisfaction to Production Wiring Proof

[← Back to Postmortems Index](README.md)

**Recorded on:** 2026-06-23

---

## Purpose

This note records a collaboration and implementation blind spot discovered during **Stage 3.5D PR4 — Projection Snapshot-Assisted Replay Validator**.

The issue was not that the validator logic was fundamentally wrong.

The issue was that the validator appeared complete at the unit-test level because its dependencies were expressed as `Protocol`s and satisfied by fake test implementations.

However, one production dependency was still missing:

```text
PostgresAcceptedHistoryEventSource
```

Without that adapter, the validator could be tested as a component, but not yet proven as a production-wired replay validator.

This postmortem records the corrected lesson:

```text
Protocol satisfaction is not production wiring proof.
```

A component can be logically correct and still be incomplete as a production feature if one of its real adapters has not been implemented or integration-tested.

---

## Context

Stage 3.5D introduces snapshot-assisted replay without allowing snapshots to become source of truth.

The governing rule is:

```text
accepted history = authority
snapshot = derived state compression
snapshot-assisted replay = fast path candidate
authority replay = correctness baseline
```

PR4 adds a validator that compares two paths:

```text
authority path:
accepted history → full replay → authority_state

snapshot-assisted path:
projection snapshot → hydrate state → replay tail events → snapshot_assisted_state
```

Then it checks:

```text
snapshot_assisted_state == authority_state
```

At the validator logic level, this required three dependency shapes:

```python
class ProjectionSnapshotStoreProtocol(Protocol):
    def load_latest_snapshot(self, order_id: str) -> ProjectionSnapshot | None:
        ...

class AcceptedHistoryStoreProtocol(Protocol):
    def load(self, order_id: str) -> list[OrderEvent]:
        ...

class ProjectionTailEventSourceProtocol(Protocol):
    def load_after(
        self,
        global_position: int,
        *,
        limit: int,
    ) -> list[ProjectionEventRecord]:
        ...
```

This made the validator cleanly testable with fake stores.

That part was correct.

The blind spot was assuming that clean unit tests over fake protocol implementations were enough to close the PR4 implementation boundary.

They were not.

---

## What Initially Looked Complete

The validator unit tests covered important behavior:

* `MATCH`
* `MISSING_SNAPSHOT`
* `NO_ACCEPTED_HISTORY_FOR_ORDER`
* `INVALID_SNAPSHOT_BOUNDARY`
* `SNAPSHOT_ASSISTED_DRIFT`
* snapshot hydration
* authority replay
* tail replay
* tail pagination
* non-advancing pagination protection
* invalid snapshot boundary checks
* drift preservation of both states
* no accepted history returning no authority state and no snapshot-assisted state

At the component level, this looked strong.

The validator could be instantiated with:

```text
FakeSnapshotStore
FakeAcceptedHistoryStore
FakeTailEventSource
```

and the full status contract could be exercised.

This proved:

```text
validator logic is correct against its declared protocols
```

But it did not prove:

```text
the production system has real adapters for every declared protocol
```

Nor did it prove:

```text
the validator can run against real PostgreSQL-backed storage boundaries
```

---

## The Missing Piece

The missing production dependency was:

```text
PostgresAcceptedHistoryEventSource
```

The validator needs a read-only accepted-history source that can load accepted events for a requested order:

```text
order_id
→ accepted OrderEvent list
→ ordered by sequence ASC
```

The project already had related pieces:

```text
PostgresProjectionSnapshotStore
PostgresProjectionEventSource
PostgresEventStore
row_to_order_event hydration helper
```

But PR4 still needed a clean read-only adapter for validator authority replay.

The intended responsibility of this adapter is narrow:

```text
read order_events
filter by order_id
ORDER BY sequence ASC
hydrate rows into OrderEvent
return list[OrderEvent]
do not append
do not mutate
do not own transactions
```

Without this adapter, the validator was not yet production-wired.

---

## Why This Was Easy to Miss

The blind spot came from a useful abstraction being mistaken for a complete implementation.

A `Protocol` defines dependency shape.

It answers:

```text
What methods does this component require?
```

It does not answer:

```text
Which production class implements this dependency?
```

It also does not answer:

```text
Has that production class been tested against the real database?
```

Fake unit tests can satisfy a protocol perfectly.

That creates a risk:

```text
The component appears complete because tests pass,
while the production assembly chain is still incomplete.
```

In this case:

```text
AcceptedHistoryStoreProtocol
```

was satisfied in unit tests by:

```text
FakeAcceptedHistoryStore
```

but the production adapter:

```text
PostgresAcceptedHistoryEventSource
```

did not yet exist.

---

## The Core Mistake

The mistake was not using `Protocol`.

The mistake was stopping at protocol-level verification.

The incorrect mental shortcut was:

```text
validator unit tests pass
→ validator PR is complete
```

The corrected interpretation is:

```text
validator unit tests pass
→ validator logic is correct

production adapter tests pass
→ real dependency boundary is correct

PostgreSQL integration tests pass
→ production wiring is correct
```

These are different claims.

They should not be collapsed.

---

## Component Correctness vs Assembly Correctness

This incident reinforces a core project principle:

```text
component correctness
≠
system correctness
```

A component may be correct in isolation.

A protocol may be well-designed.

A fake test may exercise all logical branches.

But the production feature is incomplete until all required adapters exist and the real assembly path is tested.

For PR4, the full proof chain should be:

```text
validator unit tests
→ validator logic is correct

PostgresAcceptedHistoryEventSource tests
→ accepted-history read adapter is correct

validator PostgreSQL integration tests
→ real snapshot store + real accepted-history source + real tail event source work together
```

Only then can PR4 claim to be production-wired.

---

## Why Direct Integration Testing Was Not Enough

One tempting shortcut would be to skip the accepted-history adapter test and go directly into validator integration tests.

That would be weaker.

If the validator integration test failed, the failure could come from:

* validator logic
* snapshot store
* accepted-history SQL
* event hydration
* tail event source
* global-position boundary
* test data setup

This would blur the source of failure.

The better sequence is:

```text
1. test the adapter alone
2. test the validator with real adapters
```

That preserves boundary clarity.

The accepted-history source deserves its own test because it owns its own contract:

```text
load accepted events for one order
ordered by sequence ASC
hydrate into OrderEvent correctly
return [] for missing order
```

The validator integration test should then prove assembly, not rediscover adapter behavior for the first time.

---

## Corrected Commit Sequence

The corrected PR4 commit sequence is:

```text
Commit 1
docs: define projection snapshot replay validator boundary

Commit 2
validation: define projection snapshot replay result contract

Commit 3
validation: implement projection snapshot replay validator

Commit 4
storage: add accepted history event source

Commit 5
tests: cover projection snapshot replay validator with PostgreSQL stores

Commit 6
docs: align projection snapshot replay validator closeout
```

This sequence separates:

```text
design boundary
result contract
validator logic
storage adapter
production wiring proof
documentation closeout
```

This avoids treating a unit-tested protocol consumer as a complete production feature.

---

## The Collaboration Blind Spot

This issue is also a collaboration blind spot between a human engineer and an AI assistant.

The AI correctly focused on validator semantics:

* result status vocabulary
* authority vs snapshot-assisted state
* `NO_ACCEPTED_HISTORY_FOR_ORDER` meaning
* invalid boundary handling
* tail replay behavior
* pagination safety

But it initially underweighted production assembly:

```text
Which real class implements each Protocol?
```

The human reviewer noticed the missing dependency by asking:

```text
I wrote several protocols,
but where is the real accepted-history implementation?
```

That question exposed the missing adapter and integration path.

The reusable lesson is:

```text
AI-generated component logic may be locally coherent,
but production completeness still requires explicit assembly-chain review.
```

---

## Why This Matters for Coding Agents

This blind spot is not limited to human-AI chat collaboration.

A coding agent can also fall into the same pattern:

```text
1. infer a clean interface
2. implement the core component
3. generate fake-based unit tests
4. pass all local tests
5. miss the missing production adapter
```

The system then looks correct because:

```text
the component is well-tested
```

but the feature is incomplete because:

```text
the production dependency graph has a hole
```

This is especially likely when the code uses:

* `Protocol`
* dependency injection
* fake stores
* in-memory test doubles
* isolated unit tests
* adapter-based architecture

These are good engineering tools.

But they also make missing production wiring less obvious unless the PR checklist explicitly asks for it.

---

## Protocols Are Still Correct

This postmortem should not be read as an argument against protocols.

The protocol boundary was useful.

It kept the validator independent from PostgreSQL.

It made unit tests focused.

It prevented the validator from owning storage behavior.

That was the right design.

The corrected lesson is narrower:

```text
Protocol defines dependency shape.
Adapter implements dependency reality.
Integration test proves dependency assembly.
```

All three are needed.

---

## Correct Review Questions

When a new component introduces a `Protocol`, reviewers should ask:

```text
What production class implements this Protocol?
```

```text
Where is that production class tested?
```

```text
Where is the integration test proving the component works with the real implementation?
```

```text
Is the fake test proving logic, or accidentally standing in for missing production wiring?
```

```text
Does this PR stop at component correctness, or does it prove assembly correctness too?
```

For this project, a stronger PR review checklist is:

```text
1. Does every new Protocol have a planned production adapter?
2. Does every new storage adapter have its own database-backed test?
3. Does every cross-boundary validator have at least one real integration test?
4. Are fake tests used only for logic isolation, not as substitutes for production wiring?
5. Does the closeout documentation distinguish unit proof from integration proof?
```

---

## Relationship to Snapshot Trust Contract

This postmortem fits Stage 3.5D directly.

The Snapshot Trust Contract is based on the distinction between:

```text
authority path
fast path
derived state
trust evidence
```

A validator that compares snapshot-assisted replay against authority replay must not exist only as an abstract unit-tested component.

It must be able to connect to the actual durable evidence sources:

```text
accepted history
projection snapshots
tail event source
canonical reducer
```

Otherwise, the validator would prove only a conceptual contract, not the real durable replay path.

This matters because the project’s core principle is:

```text
accepted history = authority
```

If the accepted-history source is only fake-tested, then PR4 has not yet proven its authority path at the PostgreSQL boundary.

---

## Relationship to Future PR4.5 Resolver

This postmortem also clarifies why PR4.5 should be separate.

PR4 is about validation evidence:

```text
Does snapshot-assisted replay match authority replay?
```

PR4.5 should be about replay efficiency:

```text
Given a trusted snapshot, can the system reconstruct projection state through snapshot + tail replay without full authority replay?
```

The same review rule will apply to PR4.5:

```text
Do not stop at a resolver unit test with fake stores.
Prove the resolver against real snapshot and tail sources.
```

Otherwise, the project could repeat the same mistake in a different layer.

---

## Reusable Lesson

The reusable lesson is:

```text
passing fake-based unit tests proves component logic,
not production completeness.
```

A stronger formulation:

```text
Protocol satisfaction
≠
adapter existence
≠
production wiring proof
```

For architecture work, all three must be accounted for:

```text
Protocol satisfaction
→ component can be tested in isolation

Adapter existence
→ production has a real implementation

Production wiring proof
→ the real system can assemble and execute the intended path
```

This is especially important in systems that rely on:

* event sourcing
* replay
* snapshots
* durable storage adapters
* read-side / write-side separation
* validation layers
* agent-assisted coding
* generated code

---

## Summary

This postmortem records one key implementation lesson:

```text
a well-tested Protocol consumer can still be a half-finished production feature
if the real adapter and integration proof are missing.
```

During Stage 3.5D PR4, the validator logic was close to complete, but the production wiring was not yet complete because:

```text
PostgresAcceptedHistoryEventSource
```

had not been implemented or tested.

The corrected PR4 sequence is therefore:

```text
validator logic
→ accepted-history source adapter
→ validator PostgreSQL integration test
→ docs closeout
```

The broader lesson is:

```text
component correctness is not enough.
production assembly must be proven explicitly.
```

For future human-AI or coding-agent collaboration, every generated protocol should trigger the same review question:

```text
Where is the real adapter, and where is the integration proof?
```
