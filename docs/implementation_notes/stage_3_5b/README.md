# Stage 3.5B — Durable Write-Side Baseline

[← Back to Implementation Notes](../README.md)

This folder preserves implementation notes for the completed Stage 3.5B durable write-side baseline.

Stage 3.5B moved the write-side from in-memory persistence toward durable PostgreSQL-backed semantics while preserving Compass Layer 1 before accepted-history mutation.

## Core Boundaries

```text
accepted history = authority
candidate event ≠ accepted fact
transaction atomicity ≠ concurrency admission
validation mode ≠ validation placement
```

## Notes

- [PR Breakdown](./pr_breakdown.md)

## Status

Stage 3.5B is complete at the durable write-side baseline level.

Later write-side hardening, production database roles, audit tables, and broader runtime governance remain outside this folder unless they become part of a future implementation stage.
