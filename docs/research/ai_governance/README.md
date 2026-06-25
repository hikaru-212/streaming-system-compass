# AI Governance Research Notes

[← Back to Research Notes](../README.md)

This folder records AI governance research notes and architecture explorations related to the Streaming System + Compass project.

These notes are not implementation commitments.

They preserve ideas that may be useful for future system design, especially around:

* source-grounded generation
* semantic admission
* AI-generated summaries
* runtime verification
* agentic state mutation
* governance boundaries for generated artifacts
* cost and latency trade-offs in verification-heavy systems

A document in this folder means:

```text
This idea may be relevant to Compass,
but the project does not currently commit to implementing it.
```

## Notes

* [From Generated Language to Source-Grounded Semantic Admission](./from_generated_language_to_source_grounded_semantic_admission.md)
* [TTL and Event-Driven Invalidation for Source-Grounded AI Overviews](./admitted_overview_cache_and_event_driven_invalidation.md)

## Relationship to Compass

Compass currently focuses on protecting accepted history, validating candidate events, checking derived runtime state, and preserving semantic correctness under failure.

The research notes in this folder explore adjacent governance problems where the same principle may apply:

```text
generated output
→ candidate semantic artifact
→ source-grounded verification
→ semantic outcome
→ admit / retry / block / review
```

The shared idea is that generated artifacts should not automatically become trusted system truth.

However, these research notes are intentionally separate from the main implementation roadmap. They exist to preserve architecture reasoning, not to expand the current project scope.
