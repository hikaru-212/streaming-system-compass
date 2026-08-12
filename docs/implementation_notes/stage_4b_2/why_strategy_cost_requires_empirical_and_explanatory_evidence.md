# Why Strategy Cost Requires Empirical and Explanatory Evidence

[← Back to Stage 4B.2](README.md)

## Status

```text
Stage 4B.2 engineering rationale
= PUBLIC DECISION NOTE

Primary evidence
= PR6 Level-B comparison
+ post-PR6 explanatory characterization

Production policy
= NONE
```

This note explains why Stage 4B.2 required both empirical comparison and a
separate explanatory layer.

It does not preserve the full discovery process. Detailed measurements,
experiment protocols, and execution evidence remain in the canonical PR6 and
post-PR6 reports.

## Context

The two current PostgreSQL write compositions differ in more than validation
placement.

At a high level, they also differ in transaction topology, idempotency
lifecycle, admission behavior, and where rejected work terminates.

Therefore:

```text
architectural intuition
!= observed complete-composition cost
```

A design can correctly move work outside a business UOW without guaranteeing
that the complete request will have lower end-to-end latency.

## Why Empirical Comparison Was Required

Without a controlled comparison, Stage 4B.2 could describe where work was
intended to occur but could not establish how the complete supported
compositions actually behaved in the recorded environment.

PR6 therefore treated performance expectations as hypotheses rather than
architecture facts.

The canonical comparison established an environment-qualified ordering for the
current PRE/OCC and IN/pessimistic compositions.

It did not establish a universal strategy winner.

## Why Comparison Was Not Enough

PR6 compared complete production compositions.

That is useful for answering:

```text
What did the current complete strategies cost
under this fixed recorded protocol?
```

It is not sufficient for answering:

```text
Which individual mechanism caused the difference?
```

Because multiple topology dimensions changed together, the project preserved:

```text
comparison
!= explanation
```

The post-PR6 characterization therefore used narrower evidence to explain cost
placement without rewriting the canonical comparison as causal proof.

## What the Explanatory Evidence Established

The accepted explanatory work showed that the current PRE path performs
additional durable read-lifecycle work before its later write-side business
UOW, while retaining a shorter application business-UOW interval in the
recorded accepted path.

This makes the following observations coherent:

```text
higher complete-request elapsed

and

shorter write-side application business-UOW elapsed
```

The evidence also preserved an important trade-off: preliminary idempotency can
support earlier REPLAY or CONFLICT termination, so its accepted-path cost is
not by itself evidence that the check should be removed.

## Why This Matters

The practical value of the tests was not to confirm an initial intuition.

It was to separate four different questions:

```text
What is the architecture intended to separate?

What did the complete execution actually cost?

Where was important cost observed?

What conclusions are still not authorized?
```

That separation prevents a lower end-to-end number from being mistaken for a
complete architecture decision.

## Public Interpretation Boundary

The accepted evidence supports:

- complete-composition comparison in one recorded environment;
- bounded explanation of important current cost placement;
- separation of end-to-end elapsed from application business-UOW elapsed; and
- preservation of early-exit trade-offs.

It does not establish:

- universal PRE inferiority or IN superiority;
- a production strategy switch;
- a causal percentage for the observed difference;
- exact server-side SQL or lock occupancy;
- safe removal of preliminary idempotency;
- production capacity; or
- rate-admission policy.

## Reusable Principle

```text
Architecture defines the boundary to reason about.

Measurement establishes what happened within that boundary.

Comparison establishes observed ordering.

Explanatory evidence clarifies cost placement.

None of those automatically creates production policy.
```

Detailed evidence:

- [PostgreSQL Strategy Comparison Report](postgres_strategy_comparison_report.md)
- [PostgreSQL Idempotency and Transaction-Lifecycle Supplemental Report](postgres_idempotency_transaction_lifecycle_report.md)
- [ADR 0025 — PR6 Comparison Requires Separate Explanatory Characterization](../../adr/0025_pr6_comparison_requires_separate_explanatory_characterization.md)
