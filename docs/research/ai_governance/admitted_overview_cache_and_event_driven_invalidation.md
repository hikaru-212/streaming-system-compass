# Admitted Overviews, Cache Freshness, and Event-Driven Invalidation

[← Back to AI Governance Index](README.md)

**Recorded on:** 2026-06-24

## Research Status

Public conceptual note.

This document records a research direction for handling source-grounded AI overviews after they have been admitted for use. It is not an implementation specification, an ADR, a cache schema, a policy table, or a Stage 4 commitment.

The purpose is to preserve the public idea:

```text
admitted overview
≠ permanently trustworthy overview
```

A generated artifact may be source-grounded at one point in time, but later become stale when the underlying source material changes.

---

## Problem Context

AI systems often generate summaries or overviews from source material.

If an overview has already passed a source-grounded review, it may be tempting to reuse it from cache.

Caching can reduce cost and latency.

However, reuse introduces a new governance problem:

```text
An overview may have been valid when admitted,
but invalid or incomplete after the source environment changes.
```

This is especially important when generated artifacts are used by downstream agents, dashboards, decision-support tools, or workflows.

A cached overview can become future context.

If it is stale, future reasoning may be grounded in outdated meaning.

---

## Core Distinction

This note separates three states:

```text
generated overview
```

```text
admitted overview
```

```text
still-valid overview
```

Admission at creation time does not guarantee validity forever.

A system may need to know when an admitted artifact should be reused, refreshed, revalidated, downgraded, blocked, or escalated.

---

## Why Time Matters

Source-grounded generation is not a one-time problem.

The source environment may change after admission:

- new documents appear
- previous sources are corrected
- metrics are redefined
- legal or compliance status changes
- product behavior changes
- dashboards are updated
- source lineage becomes clearer
- conflicting evidence emerges
- business definitions evolve

When this happens, an older admitted overview may no longer reflect the current source environment.

The risk is not only that the cache is old.

The risk is that the system may continue treating old generated language as trusted context.

---

## Public Conceptual Flow

A safer system may treat admitted overviews as time-bounded semantic artifacts:

```text
source material
→ generated overview
→ source-grounded admission
→ admitted overview
→ reuse only while freshness and source assumptions remain acceptable
```

If the source environment changes, the system may need to re-check the overview before reuse.

The exact implementation may vary.

The important principle is that reuse should be governed by evidence freshness, not only by cache availability.

---

## Invalidation as Semantic Governance

Traditional cache invalidation often asks:

```text
Is this cached object still technically reusable?
```

For generated semantic artifacts, the stronger question is:

```text
Is this cached meaning still safe to reuse?
```

A cached overview may still exist, deserialize correctly, and match a query key.

That does not prove it is still semantically valid.

For AI governance, invalidation should consider whether the evidence environment has changed in a way that could affect the meaning of the overview.

---

## Possible Refresh Signals

A system may need to refresh or revalidate an admitted overview when signals suggest that its source assumptions may no longer hold.

Examples include:

- relevant source material changed
- new conflicting evidence appeared
- source authority changed
- a high-risk topic received updated evidence
- the overview depends on time-sensitive information
- the business definition behind a term changed
- downstream use became higher risk than originally expected

This list is conceptual.

It does not define a concrete invalidation policy, event model, metadata structure, or refresh algorithm.

---

## Relationship to Compass

Compass treats accepted history as authority and derived artifacts as subordinate.

This research direction applies a similar idea to generated overviews:

```text
source evidence = authority boundary
admitted overview = derived semantic artifact
```

A derived semantic artifact may be useful, but it should remain accountable to the sources that justified it.

If the source environment changes, the artifact may need to be reviewed again.

---

## Example: Previously Admitted Overview

Suppose an AI system generates an overview about a company, metric, or business process.

At creation time, the overview may be supported by available sources.

Later, new evidence appears or old source material is corrected.

A naive system may continue serving the old overview because the cached object still exists.

A safer system would ask whether the overview remains valid under the updated source environment.

The answer may be:

- reuse it
- refresh it
- revise it
- mark uncertainty
- block it
- escalate it for review

The important point is that cache reuse becomes a semantic decision, not only a performance optimization.

---

## Non-goals

This public note intentionally does not define:

- cache metadata schemas
- hash fields
- TTL values
- invalidation rules
- event-routing designs
- source-scoring algorithms
- admission status enums
- runtime policy tables
- refresh pipelines
- implementation-specific storage design

Those details should remain private research or future implementation work until the project intentionally chooses to publish them.

---

## Key Principle

A cached generated artifact may be cheap to reuse, but that does not make it safe to reuse.

For source-grounded AI systems, the cache question is not only:

```text
Do we already have an answer?
```

It is also:

```text
Is this admitted answer still grounded in the current source environment?
```

The goal is not to avoid caching.

The goal is to prevent stale generated meaning from becoming trusted future context.
