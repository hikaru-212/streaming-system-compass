# Reasoning Notes

[← Back to Docs Home](../README.md)

This directory contains reasoning notes for **Streaming System + Compass**.

Reasoning notes are non-authoritative, usually source-grounded records whose
dominant value is the derivation or inference path: how an assumption was
challenged, a missing premise or responsibility became visible, multiple states
were separated, or a reusable diagnostic model was constructed.

These notes preserve how a question became more precise. They do not establish
current runtime behavior, accepted architecture, or implementation commitment.
Current source, tests, migrations, accepted ADRs, current boundary notes, and
stage closeouts remain the owning evidence for those claims.

Substantial reasoning does not by itself make a document a reasoning note. A
reasoning note belongs here when no single concrete engineering, architectural,
or learning episode is the dominant subject of the document.

Some notes retain historical titles containing “Postmortem.” Their placement in
this directory records the approved category classification without rewriting
their historical wording.

---

## Inclusion Criteria

A reasoning note belongs here when:

- a reusable derivation or inference path is its dominant value;
- no single concrete episode that actually occurred is the dominant subject;
- it shows how an assumption, missing premise, or responsibility gap was found;
- it separates concepts, states, guarantees, or ownership boundaries that were
  previously conflated;
- it is usually grounded in repository source, tests, documentation, or an
  engineering question;
- it may have contributed to a later test, repair, ADR, or boundary note, while
  remaining a non-authoritative account of the reasoning path; or
- a hypothetical scenario is used to clarify an actual repository boundary
  rather than to propose a future system.

---

## Exclusion Criteria

A document does not belong here when its dominant purpose is:

- recording one identifiable engineering, architectural, or learning episode
  that can be reconstructed through context, problem, correction, and lesson;
- recording a preventive discovery that found and resolved a real unsafe path,
  failed test, regression, broken migration, inconsistency, missing guarantee,
  architectural-model error, recurring code-reading failure, or stage-premise
  drift;
- proposing a possible future system, algorithm, policy, or governance
  mechanism;
- defining a broad design philosophy or working worldview;
- prescribing stage-level or PR-level implementation work;
- recording an accepted architecture decision;
- defining a current module or cross-boundary responsibility; or
- presenting a public illustrative case whose central value is the case rather
  than a repository-grounded derivation.

---

## Relationship to Postmortems

A postmortem records a concrete engineering episode. This includes actual
incidents and preventive engineering discoveries where a real unsafe path,
failed test, regression, broken migration, source-grounded inconsistency, or
missing guarantee was found and concretely repaired before production impact.
It also includes identifiable architectural-model corrections, recurring
engineering-learning failures, design near-misses, and stage-premise drift.

A postmortem may contain substantial reasoning. What makes it a postmortem is
one dominant episode that actually occurred and can be reconstructed through
context, problem, correction, and lesson.

A reasoning note may begin with an engineering question or contribute to a
later repair, but it belongs here when the reusable derivation, inference path,
missing-premise discovery, or conceptual separation is primary without one
dominant concrete episode.

---

## Relationship to Research

A research note explores a possible future system, algorithm, policy, or
governance mechanism. Research is not moved here merely because it contains
reasoning.

Reasoning notes are instead anchored to understanding an existing repository
boundary, responsibility gap, or engineering question. When the main value is
an unimplemented future proposal, the document remains research.

---

## Relationship to Philosophy

Philosophy notes preserve broad mental models, working methods, and project
worldviews. Reasoning notes are narrower records of how one repository question,
assumption, or boundary was derived and clarified.

---

## Relationship to Implementation Notes

Implementation notes define stage-level or PR-level scope, sequencing,
non-goals, hazards, and validation plans. Reasoning notes may explain why that
work became necessary, but they do not prescribe implementation or prove that
the work is complete.

---

## Relationship to ADRs and Boundary Notes

ADRs record accepted decisions and their trade-offs. Boundary notes define
current module-level or cross-boundary ownership. Reasoning notes may motivate
or explain those documents, but they do not replace them and must defer to their
accepted, current claims.

When reasoning becomes an accepted architecture decision, promote the decision
to an ADR. When it becomes a current ownership or responsibility contract,
promote the contract to a boundary note. Preserve the reasoning note as
historical derivation and link it to the owning document rather than rewriting
history into current authority.

---

## Relationship to Public Case Studies

Public case studies use an illustrative scenario to explain a broadly useful
boundary or governance problem. Reasoning notes primarily preserve an internal,
repository-grounded inference path. A note should not move here merely because
a public case study explains how people reasoned about its example.

---

## Current Reasoning Notes

| Document                                                                                                                                                                                                                                                    | Reasoning Area                                  | Dominant Value                                                                                                                             |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| [Autocommit, Transaction Boundaries, and Partial-Write Risk](autocommit_boundary_and_partial_write_risk.md)                                                                                                                                                 | Transaction Boundary / Concurrency              | Separates statement execution, transaction ownership, and logical operation atomicity.                                                     |
| [Documentation Scope vs Enterprise Design Docs](docs_vs_enterprise_design_docs.md)                                                                                                                                                                          | Documentation Scope / Project Positioning       | Derives the distinction between semantic documentation and enterprise operational design.                                                  |
| [From ](from_created_at_freshness_to_committed_history_boundaries.md)[`created_at`](from_created_at_freshness_to_committed_history_boundaries.md)[ Freshness to Committed-History Boundaries](from_created_at_freshness_to_committed_history_boundaries.md) | Snapshot Freshness / Event-Log Cursor Semantics | Derives commit, visibility, gap, lineage, and cursor distinctions from a freshness question.                                               |
| [From Error Semantics to Interleaving Reasoning](from_error_semantics_to_interleaving_reasoning.md)                                                                                                                                                         | Failure Semantics / PostgreSQL Concurrency      | Connects Stage 4 semantic and evidence ownership with PostgreSQL transaction, MVCC, locking, and uniqueness knowledge to derive controlled interleaving questions. |
| [From Exception Strings to Governable Outcomes](from_exception_strings_to_governable_outcomes.md)                                                                                                                                                           | Error Model / Governance                        | Traces the conceptual transition from interruption strings to structured semantic outcomes.                                                |
| [From Git Local–Remote Drift to Database Immutability Boundaries](from_git_sync_to_db_immutability.md)                                                                                                                                                      | Database Boundary / Immutability                | Transfers a local/remote state distinction into durable database-boundary reasoning.                                                       |
| [From In-Memory Correctness to Durable Consistency](from_in_memory_correctness_to_durable_consistency.md)                                                                                                                                                   | Durable Persistence / Consistency               | Separates single-runtime correctness from guarantees that survive time and restart.                                                        |
| [From Local PostgreSQL Setup to Defense-in-Depth Boundaries](from_local_postgres_to_defense_in_depth.md)                                                                                                                                                    | Security / Defense in Depth                     | Derives how configuration, credentials, permissions, schema, validation, and transactions protect different boundaries.                    |
| [From Projection Concerns to Event Truth](from_projection_concerns_to_event_truth.md)                                                                                                                                                                       | Event Truth / Source of Truth                   | Traces the architectural derivation from projection concerns to accepted-history entry.                                                    |
| [From Replay / Rebuild Validation to Layer 2 Governance](from_replay_rebuild_validation_to_layer2_governance.md)                                                                                                                                            | Replay / Layer 2 Boundary                       | Separates correctness evidence from later semantic interpretation and governance.                                                          |
| [From Runtime Behavior to Durable Evidence](from_runtime_behavior_to_durable_evidence.md)                                                                                                                                                                   | Runtime Evidence / Observability                | Derives why transient behavior is not durable evidence unless deliberately preserved.                                                      |
| [From Statement Success to Owner-Liveness](from_statement_success_to_owner_liveness.md)                                                                                                                                                                     | PostgreSQL Persistence / Transaction Liveness   | Derives the missing owner-resolution premise from statement success, caller-owned transaction completion, and invisible uncommitted state. |
| [Retry Amplification, Local Correctness, and Semantic Diagnosis](retry_amplification_local_correctness_and_semantic_diagnosis.md)                                                                                                                             | Retry Amplification / Governance Boundaries     | Separates observed client behavior from a plausible amplification model, then derives why failure evidence, diagnosis, retry authorization, and execution need distinct owners. |

---

## Reasoning Note Principle

A useful reasoning note makes the derivation inspectable:

```text
question or assumption
→ missing premise or responsibility
→ separated concepts or states
→ corrected model
→ current owner or unresolved boundary
```

The corrected model remains reasoning history until an owning source, test,
migration, ADR, boundary note, or stage closeout establishes current authority.
