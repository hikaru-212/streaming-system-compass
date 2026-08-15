# Test Specifications and Proof-Obligation Candidates

[← Back to Docs Home](../README.md)

## Purpose

This directory contains non-authoritative proof-obligation candidates derived
from accepted architecture, contracts, and executable evidence.

A test specification identifies a scenario, invariant, uncertainty window, or
evidence oracle that may deserve source review and executable
characterization. It does not change system semantics, establish architecture,
or prove that the current repository already satisfies the candidate
obligation.

```text
test specification
≠ system semantics

AI-generated derivability
≠ architecture authority
```

Authority remains with accepted architecture, contracts, ADRs, current
production behavior, and executable evidence in their owning scopes. A test
specification must defer to those sources when they disagree.

## Candidate Statuses

| Status | Meaning |
|---|---|
| `EXPERIMENTAL` | Preserves a candidate derivation or research experiment that has not been accepted for implementation. |
| `ACCEPTED_FOR_IMPLEMENTATION` | Human review has approved the candidate for a bounded implementation effort; this does not make the specification architecture authority. |
| `EXECUTABLY_CHARACTERIZED` | Executable evidence now characterizes the candidate scenario; the executable evidence, not this label, owns the demonstrated behavior. |
| `DEFERRED` | The obligation remains potentially useful but awaits a later stage, consumer, contract, or test seam. |
| `REJECTED` | Review determined that the candidate is unsupported, misleading, redundant, or outside the intended system boundary. |

Status changes record review disposition. They do not create or revise runtime
contracts.

## Working Loop

The intended loop is:

```text
accepted architectural knowledge
+ existing executable evidence
→ candidate proof obligation
→ source and human review
→ executable characterization
→ new evidence
→ architecture re-evaluation when necessary
```

This may be described as AI-assisted specification-driven adversarial
verification or dynamic proof-obligation generation. The repository is not
claiming formal state-space exhaustiveness, model checking, theorem proving,
machine-checked proof, or full formal verification.

AI can help derive, challenge, and draft candidate scenarios. Human review
must still decide whether the premises are admissible, the semantics are
correct, the scenario belongs in project scope, and implementation should
proceed.

## Current Specifications

| Document | Status | Classification | Authority qualification |
|---|---|---|---|
| [Stage 4B.1 Write-Side Adversarial Derivation](stage4b1_write_side_adversarial_derivation_from_docs_and_baseline_tests.md) | `EXPERIMENTAL` | Non-authoritative test specification and documentation-quality research artifact | Evaluates reconstructable derivability from historical documentation and the first six characterization scenarios. The derivation run predates and did not inspect or admit the later four advanced PR4 characterization scenarios as test premises. Conversation-context contamination remains explicit, so it does not claim blind independent discovery or accepted Stage 4B.1 architecture. |

## Boundary

These documents do not authorize production changes, retry policy, runtime
decisions, action execution, or new persistence contracts. When a candidate
reveals a possible architectural gap, the owning architecture must be reviewed
separately rather than silently rewritten through a test specification.
