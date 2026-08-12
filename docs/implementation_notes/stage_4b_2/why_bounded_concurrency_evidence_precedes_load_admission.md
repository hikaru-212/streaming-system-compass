# Why Bounded Concurrency Evidence Precedes Load Admission

[← Back to Stage 4B.2](README.md)

## Status

```text
Stage 4B.2 engineering rationale
= PUBLIC DECISION NOTE

Primary evidence
= PR7 canonical Level-C characterization

Future load-admission policy
= DEFERRED / SEPARATELY OWNED
```

This note explains why single-execution cost evidence is not enough to derive
production capacity or load-admission policy.

It does not define a rate limiter, production worker count, connection-pool
size, SLO, or automatic strategy policy.

## Context

Level A and Level B evidence can describe one execution and compare complete
strategies under controlled workloads.

They do not establish how those strategies behave as multiple requests overlap.

Therefore:

```text
single-execution cost
!= concurrency behavior
```

and:

```text
concurrency behavior
!= production capacity
```

## Why Level-C Evidence Was Required

A future admission decision should not begin from a latency inversion or an
arbitrary worker count.

Before policy is considered, the project needs bounded evidence about:

- how accepted latency changes as in-flight concurrency rises;
- whether completion gains remain proportional;
- how same-order contention differs from independent-stream concurrency;
- where competing requests terminate; and
- whether the experiment harness materially distorts the observation.

PR7 supplied that bounded evidence for the current PostgreSQL compositions.

## Why Workload Families Remain Separate

PR7 keeps:

```text
DIFFERENT_ORDER_GENERAL_CONCURRENCY
!= SAME_ORDER_HOT_STREAM
```

Different-order work describes concurrent accepted work across independent
streams.

Same-order hot-stream work describes contention around one logical stream.

Pooling them would erase the distinction between general database concurrency
and hot-key contention.

That distinction is relevant to future capacity engineering even though PR7
does not define a production policy.

## What PR7 Established

Within the tested worker levels, the canonical evidence showed:

- accepted latency increased as bounded concurrency increased;
- synchronized-burst completion also increased, but with diminishing gains;
- no unambiguous completion-rate plateau or decline appeared by the highest
  tested level;
- PRE stale-write and IN pessimistic lock-timeout cohorts terminated at
  different points in the current execution topology; and
- release-skew review found no concrete harness-dominated cell that blocked
  interpretation.

These are environment-qualified observations.

They are not production capacity certification.

## Why Rejection Placement Matters

A rejected request is not one generic cost class.

In the current recorded compositions, same-order PRE stale writes reached later
work than IN pessimistic lock-timeout contenders.

Therefore:

```text
rejection count
!= resource cost
```

Future admission work may need to care about where work is rejected, not only
whether it is rejected.

PR7 records that distinction without selecting a preferred strategy.

## Why Burst Completion Is Not Production Throughput

The Level-C protocol uses bounded synchronized bursts.

It does not model sustained or open-loop production arrivals.

Therefore its completion-rate observations are useful for local comparison but
must not be promoted into:

```text
production requests per second

safe concurrency

or

rate limit
```

The protocol establishes a bounded empirical shape, not a production arrival
model.

## Evidence Before Policy

PR7 gives future capacity work a measured starting point:

- bounded in-flight worker levels;
- accepted latency behavior;
- synchronized-burst completion behavior;
- typed same-order contention outcomes;
- current rejection placement;
- business-UOW observations; and
- harness-validity evidence.

It does not supply the production objective or policy boundary required to turn
those observations into admission control.

## Future Handoff

Future capacity or load-admission work still needs separately owned decisions
about, at minimum:

- production arrival behavior;
- relevant resource and connection constraints;
- queueing or backpressure expectations;
- target service objectives and safety margin; and
- whether admission is global, per-key, or otherwise scoped.

Only after those are explicit should a production admission mechanism be
selected.

## Public Interpretation Boundary

PR7 does not authorize:

- `safe_workers = 8`;
- a rate limit derived from latency;
- a production throughput guarantee;
- a saturation threshold;
- connection-pool sizing;
- automatic PRE/IN switching;
- autoscaling policy; or
- SLO definition.

The tested worker levels are experiment-local evidence points, not production
settings.

## Reusable Principle

```text
Single-execution cost
does not reveal concurrency behavior.

Bounded concurrency behavior
does not establish production capacity.

Capacity evidence
does not automatically define load-admission policy.
```

Detailed evidence:

- [PostgreSQL Bounded Concurrency Method](postgres_bounded_concurrency_method.md)
- [PostgreSQL Bounded Concurrency Report](postgres_bounded_concurrency_report.md)
