# Topic Documentation Indexes

## Purpose

This directory organizes Compass documentation by system responsibility and practical engineering context rather than by repository folder or document type.

The indexes provide focused reading paths across architecture documents, ADRs, boundary notes, implementation records, reasoning notes, postmortems, and other supporting material. A document may appear in more than one index when it makes a substantial contribution to multiple areas. Repeated placement is therefore a navigation choice, not a change in document ownership or authority.

## Topic Map

| Topic index | Primary engineering lens | Core question |
|---|---|---|
| [Write-side Documentation Index](WRITE_SIDE_DOCUMENT_INDEX.md) | Backend / transactional systems | How does a candidate become an accepted durable fact? |
| [Read-side Documentation Index](READ_SIDE_DOCUMENT_INDEX.md) | Data platform / event-driven read models | How does accepted history become derived projection state? |
| [Snapshot Trust Documentation Index](SNAPSHOT_DOCUMENT_INDEX.md) | Data platform / recovery / state acceleration | When can derived snapshot state be used safely? |
| [Durable History / Permission Documentation Index](DURABLE_HISTORY_PERMISSION_DOCUMENT_INDEX.md) | Database governance / platform security | Who may mutate which durable artifacts? |
| [SemanticOutcome Documentation Index](SEMANTIC_OUTCOME_DOCUMENT_INDEX.md) | Runtime governance / reliability / semantic control | How does technical evidence become semantic meaning? |

## How to Use These Indexes

Each index assigns a reading level for its own navigation purpose:

- Use `Start here` documents for orientation and the shortest entry into a topic.
- Use `Core` documents for current responsibility boundaries and central decisions.
- Use `Deep dive` documents for implementation mechanisms, evidence details, and narrower contracts.
- Use `Historical/supporting` documents for chronology, planning context, and design evolution.

These labels do not replace each document's existing role or status. When older planning material remains in the repository, later accepted decisions and completed boundaries govern current interpretation.

## Current Coverage

Topic indexes currently exist for:

- Write-side;
- Read-side / Projection;
- Snapshot Trust;
- Durable History / Permission;
- Stage 4A SemanticOutcome.

Stage 4A, Stage 4B, and Stage 4B.1 are complete. Current DecisionReceipt and
producer-specific trace material appears in the relevant indexes even though
there are no dedicated DecisionReceipt or DiagnosticTrace topic indexes. See
the [Stage 4B.1 closeout](../../implementation_notes/stage_4b_1/stage_4b_1_closeout.md)
for the completed trace boundary and Stage 4B.2 handoff.

[Reasoning Notes](../../reasoning_notes/README.md) are non-authoritative derivation records. [Postmortems](../../postmortems/README.md) reconstruct one concrete engineering, architectural, learning, or preventive episode. Their analytical depth does not determine their category.

## Navigation Boundary

Topic indexes do not replace their source documents. Professional labels are navigation lenses rather than exclusive ownership claims: a Data Platform document may also matter to Backend or Runtime Governance readers. Placement in an index does not change a document's authority. Source, tests, migrations, accepted ADRs, current boundaries, and closeouts govern the claims these indexes summarize.

Return to [Documentation Navigation](../README.md) or choose a route through the [Compass Reading Path](../COMPASS_READING_PATH.md).
