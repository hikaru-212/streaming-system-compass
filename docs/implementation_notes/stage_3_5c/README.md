# Stage 3.5C — Durable Read-Side Baseline

[← Back to Implementation Notes](../README.md)

This folder preserves implementation notes for the completed Stage 3.5C durable read-side baseline.

Stage 3.5C moved the read-side runtime from in-memory stores toward durable PostgreSQL-backed projection state, checkpoint progress, global-position consumption, and replay / rebuild validation.

## Core Boundaries

```text
accepted history = authority
projection state = derived read model
checkpoint = operational progress metadata
accepted-history replay = authority path
```

## Notes

- [PR Breakdown](./pr_breakdown.md)

## Status

Stage 3.5C is complete at the durable read-side baseline level.

Later snapshot trust, Compass Layer 2 semantic validation, worker leasing, checkpoint locking, and distributed projection orchestration remain outside this folder unless they become part of a future implementation stage.
