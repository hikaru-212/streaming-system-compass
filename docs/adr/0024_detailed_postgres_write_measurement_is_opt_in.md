# ADR 0024: Detailed PostgreSQL Write Measurement Is an Opt-In Capability

[← Back to ADR Index](README.md)

## Status

Accepted

## Implementation Status

Stage 4B.2 PR3 implements the producer-specific immutable contract without
changing existing producer APIs. The explicit production measurement-enabled
surface and its instrumentation remain assigned to PR4. The existing
unmeasured APIs remain unchanged.

---

## Decision Scope

This decision governs whether detailed Stage 4B.2 PostgreSQL write measurement
is mandatory for every current producer call.

It does not select a validation placement or concurrency-admission strategy and
does not define later sampling or observability policy.

## Context

Level-A measurement records multiple nested intervals around current write-side
operations. Even when collection is efficient, those clock reads, state
updates, and final contract construction are work that the existing unmeasured
APIs do not perform.

The current write side already has valid legacy and traced surfaces:

```text
create_order(...)
pay_order(...)

create_order_with_trace(...)
pay_order_with_trace(...)
```

Stage 4B.2 needs an equivalent measured surface for controlled comparison, but
it has no evidence or consumer requirement that makes detailed collection
mandatory for every production execution.

## Decision

Detailed Stage 4B.2 measurement is an explicit execution-level capability.

```text
existing unmeasured execution
→ remains valid and unchanged

explicit measurement-enabled execution
→ returns the complete producer-specific Level-A delivery contract
```

Caller or orchestration chooses the surface before one execution begins.

PR3 freezes the contract boundary but does not name or implement the future PR4
public methods. PR4 must add equivalent explicit measured surfaces for the
current PRE_TRANSACTION and IN_TRANSACTION compositions without changing the
existing write algorithms or unmeasured APIs.

The first boundary does not include:

- per-phase enable/disable configuration;
- sampling percentages;
- dynamic measurement policy;
- an always-present no-op collector;
- automatic strategy selection; or
- telemetry-backend integration.

## Rationale

Execution-level opt-in gives controlled experiments one equivalent measured
surface while retaining a legitimate zero-detailed-instrumentation path for
latency-sensitive or extreme-performance deployments.

It also makes caller intent explicit. Existing APIs do not silently acquire
new observer overhead, measurement failure modes, or delivery types.

Sampling and dynamic enablement can be layered above explicit measured and
unmeasured surfaces later if a concrete production observability consumer
requires them. Those policies do not belong in the Level-A evidence contract.

## Alternatives Considered

### Instrument every existing write automatically

Rejected. It would impose detailed measurement work on callers that did not
request it and would change the operating-cost boundary of existing APIs.

### Add runtime flags for every phase

Rejected. Per-phase policy would enlarge PR3, permit incomplete surfaces with
unclear comparability, and mix evidence semantics with operational policy.

### Install an always-present no-op collector

Rejected. It would make the unmeasured path depend on measurement machinery and
would not preserve a clean capability boundary.

### Implement percentage sampling in the producer

Rejected for this stage. Sampling ownership, selection bias, and production
telemetry consumers remain undefined.

## Consequences

### Positive

- Existing legacy and traced APIs retain their current cost and behavior.
- Detailed measurement overhead is paid only by callers choosing it.
- PRE and IN experiments can use the same explicit measured surface.
- Future orchestration can choose measured or unmeasured execution without
  redefining Level-A evidence.

### Negative

- Callers must select a separate capability when detailed evidence is needed.
- Unmeasured executions intentionally provide no detailed Stage 4B.2 artifact.
- Production-wide coverage would require later policy above this boundary.

### Neutral but Important

Opt-in measurement does not mean optional fields inside an available snapshot.
The immutable PR3 snapshot retains the complete explicit phase-state surface;
phase applicability and reach remain represented by typed states.

## Non-Goals

This ADR does not introduce:

- production instrumentation or measured methods;
- sampling, dynamic enablement, or monitoring policy;
- OpenTelemetry, metrics, logs, exporters, or dashboards;
- strategy selection or adaptive switching;
- retry, AttemptLog, rate limiting, or capacity policy;
- persistence or DecisionReceipt projection; or
- a generic cross-producer measurement abstraction.

## Relationship to Existing Decisions

- ADR 0022 already preserves separate untraced and traced APIs. This ADR uses
  the same explicit-capability principle without adopting trace failure
  semantics.
- ADR 0023 governs result-first delivery when the future explicit measured
  surface is selected. This ADR governs whether that surface is selected at
  all.

## Current Decision Summary

```text
detailed PostgreSQL write measurement
= explicit capability
!= mandatory execution tax

existing unmeasured APIs
= valid unchanged production surface

sampling and dynamic observability
= future policy above this boundary
```
