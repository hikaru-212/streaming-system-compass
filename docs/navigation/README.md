# Documentation Navigation

## Purpose

This directory provides cross-folder navigation for the Compass documentation. The repository's existing folders continue to preserve document type, purpose, and chronology, including:

- ADRs
- architecture
- boundary notes
- implementation notes
- overview
- postmortems
- reasoning notes
- semantic admission
- roadmap
- research
- philosophy

This navigation layer answers a different question:

> Which documents should a reader follow to understand a system responsibility, professional engineering area, or conceptual lens?

Navigation files route readers across those existing structures. They are not sources of Compass architecture authority and do not change the role or status of the documents they reference.

## Start Here

Begin with the [Compass Reading Path](COMPASS_READING_PATH.md).

It offers several bounded routes through the repository:

- one-document reading;
- three-document reading;
- five-document reading;
- deep architecture reading;
- paths selected by professional background;
- current maturity guidance.

Use it to choose an appropriate level of depth before entering a detailed topic index or source-document sequence across the documentation set.

For a high-level public orientation, use the [Overview index](../overview/README.md). For non-authoritative derivation records, use the [Reasoning Notes index](../reasoning_notes/README.md). Postmortems remain the place for reconstructable engineering, architectural, learning, or preventive episodes.

## Topic Indexes

The [Topic Indexes](topic_indexes/README.md) organize documents by system responsibility and professional engineering context. Their README describes the current topic coverage and routes readers to the individual indexes.

## Optional Lenses

The [Mathematical Structure Documentation Index](optional_lenses/MATHEMATICAL_STRUCTURE_DOCUMENT_INDEX.md) provides an optional cross-document mathematical reading lens. It is not a Compass runtime area or an architecture taxonomy.

## Authority Note

Reading paths and indexes route readers; source documents preserve their original authority and chronology. Exact implementation truth comes from source, tests, migrations, accepted ADRs, current boundary notes, and stage closeouts. Navigation summaries do not override the document that owns an underlying claim.
