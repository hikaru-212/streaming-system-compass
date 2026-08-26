# Semantic Models

[← Back to Research Notes](../README.md)

Semantic models are public, non-authoritative research abstractions. They compress implementation details into candidate semantic structures but do not override current source, tests, accepted ADRs, accepted boundary notes, or accepted closeouts.

Their adequacy, minimality, and conformance properties may remain open.

* [Compass Quotient Model v1](./compass_quotient_model_v1.md) — the current public candidate semantic compression of the completed Stage 4 boundary.

v0 was an internal historical working model and is not published.

[ADR 0030](../../adr/0030_preserve_legacy_stale_write_carrier_and_normalize_at_the_semantic_abstraction_boundary.md) explains why the historical `STALE_WRITE` implementation carrier is preserved while this research model normalizes only at the semantic abstraction boundary.
