# Stage 4B.5 PR Breakdown

[← Back to Stage 4B.5](README.md)

## Purpose

This note defines the implementation sequence for:

```text
Stage 4B.5 — Order Correctness Contract v0
```

Stage 4B.5 exists so that current correctness enforcement can be described by
stable, machine-readable rule identities without turning the declarative
contract into executable authority.

The concrete end-state for this stage is not merely:

```text
FAILED / BLOCKED
```

It is:

```text
existing Stage 4A semantic outcome
+
same-invocation stable rule-level refinement
```

for supported Compass correctness rejections.

The first downstream motivation is evidence-grounded Agent feedback and later
Retry Governance:

```text
coarse semantic rejection
→ exact violated correctness rule
→ narrower next-candidate space
→ later retry policy consumes evidence
```

Stage 4B.5 does not itself authorize retry, prescribe repair, or decide why an
Agent reasoned incorrectly.

Two closeout supplements are now explicitly planned after the final semantic
wiring is frozen:

```text
1. Runtime Governance Overhead Characterization
   → quantify the incremental cost of the new semantic-governance path

2. Deterministic Python → YAML Contract Projection
   → provide a human/AI-readable contract view without creating a second
     semantic authority or adding YAML parsing to the production request path
```

These supplements complete the Stage 4B.5 evidence and readability story
without changing the stage's core runtime responsibility.

---

## Current Status

```text
PR1 — COMPLETE / MERGED
PR2 — COMPLETE / MERGED
PR3 — COMPLETE / MERGED
PR4 — COMPLETE / MERGED

Combined PR5 + PR6
— COMPLETE / MERGED
— exact rule evidence preserved through ValidationRuntime
— exact rule evidence propagated through PostgreSQL write-side execution

PR7 — COMPLETE / MERGED
Supplement A — HARNESS IMPLEMENTED / CANONICAL RUN NOT STARTED
Supplement B — PLANNED
PR8 — CLOSEOUT
```

Current delivered chain:

```text
Order Correctness Contract V0
→ executable-authority parity
→ FullProof rule-evaluation evidence
→ ValidationRuntime evidence preservation
→ ValidationPolicy on the identical ValidationResult
→ PostgreSQL write-side same-invocation propagation
→ existing normal / trace / measurement delivery surfaces
→ Stage 4A SemanticOutcome mapping
→ terminal Order-rule refinement composition
```

The active supplement gap is:

```text
matched A/B/C characterization
→ semantic-path micro cost
+ PostgreSQL end-to-end cost
→ environment-qualified governance-overhead evidence
```

The semantic path is frozen. Supplement A now characterizes its incremental
runtime cost without reopening Stage 4B.2 or treating YAML projection as a
runtime dependency.

---

## Stage Principle

```text
current executable correctness
→ declarative correctness contract
→ executable-authority parity
→ producer-owned rule-evaluation evidence
→ same-invocation evidence propagation
→ hierarchical semantic refinement
→ bounded live feedback
→ measured governance overhead
→ readable deterministic contract projection
→ closeout
```

Preserve:

```text
rule identity != technical status
rule identity != SemanticOutcomeCode
SemanticOutcome != rule violation evidence
rule evidence != RuntimeDecision
rule evidence != retry authorization
retry decision evidence != rule violation evidence
contract != executable authority
Order business logic != Compass validation
Python canonical contract != generated YAML projection
generated YAML != production runtime authority
```

Dependency direction:

```text
Order/domain semantics
        ↑
Compass validation / evidence
```

Order core must not depend on Compass.

---

## Branch Workflow

Stage 4B.5 uses the integration branch:

```text
feat/stage4b5-order-correctness-contract
```

Current sequence:

```text
feat/stage4b5-order-correctness-contract
├── docs/stage4b5-pr1-source-grounded-order-correctness-boundary
├── feat/stage4b5-pr2-order-correctness-contract-v0
├── test/stage4b5-pr3-executable-authority-parity
├── feat/stage4b5-pr4-rule-evaluation-evidence
├── feat/stage4b5-pr5-pr6-rule-evidence-propagation
├── feat/stage4b5-pr7-semantic-rule-feedback-composition
├── supplement: runtime-governance-overhead-characterization
├── supplement: python-to-yaml-contract-projection
└── docs/stage4b5-pr8-closeout
```

PR5 and PR6 were originally planned as separate runtime-preservation and
write-side-propagation PRs.

Source-grounded audit showed that a standalone PR5 would expose an intentionally
dormant runtime API with no production consumer. Human review therefore combined
the two responsibilities into one coherent production delivery:

```text
rule evidence producer
→ runtime preservation
→ real PostgreSQL write-side consumer
```

This keeps the production seam concrete and avoids speculative public
abstraction.

If live aggregate/domain command-rejection evidence becomes a Stage 4B.5
completion requirement, insert a separately scoped producer PR before closeout.
Do not imply universal Order rule-evidence coverage unless such producers are
actually implemented.

---

# PR1 — Source-Grounded Order Correctness Boundary

## Status

```text
COMPLETE / MERGED
```

Purpose: freeze the source-grounded Stage 4B.5 responsibility, enforcement
ownership, rule-category boundary, rule-identity principles, and live
Agent-feedback motivation before production contract implementation.

Important preserved decisions:

```text
event_id
= may exist on a candidate before acceptance

positive amount
= normalized monetary value > 0

full-payment equality
= normal command/candidate/admission trust-chain responsibility;
  trusted apply(event) does not independently revalidate it

Order Correctness Contract
= multiple correctness categories, not one flat DOMAIN_INVARIANT list
```

Aggregate/domain command rejection is not the same thing as Compass
`ValidationResult(FAILED)` followed by policy `BLOCK`.

---

# PR2 — Immutable Order Correctness Contract V0

## Status

```text
COMPLETE / MERGED
```

Canonical identity:

```text
contract_id = order.correctness
contract_version = 0
```

The contract contains 18 stable rule identities across:

```text
COMMAND_LEGALITY
CANDIDATE_CONSTRUCTION
TRUSTED_APPLICATION
TRANSITION_TRUTH
```

Final representation invariant:

```text
rule_id
→ {semantic_proposition, category, subject}

transition_rule_id
→ {command, predecessor_status, candidate_event_type, resulting_status}

amount_rule_id
→ {command, constraint}

(contract_id, contract_version)
→ complete registered contract edition
```

The supported public construction path does not expose arbitrary free
composition of dependent semantic fields.

Testing principle:

```text
define universe
→ define allowed relation
→ derive forbidden complement
→ exhaustively reject invalid states where practical
```

Happy paths are baseline evidence, not sufficient proof that invalid semantic
states are excluded.

The accepted authority decision remains:

```text
Python canonical contract
= semantic authority

generated YAML
= deterministic readability projection only
```

Stage 4B.5 does not require production runtime parsing of YAML.

---

# PR3 — Python Executable-Authority Parity

## Status

```text
COMPLETE / MERGED
```

Responsibility: provide executable evidence that the accepted declarative
contract still describes the current Python authority.

Parity covers:

- `OrderAggregate`;
- shared Money behavior;
- candidate event and Proof construction;
- trusted `apply(event)` preconditions/effects;
- included Compass Layer 1 transition-truth checks.

Boundary:

```text
parity = evidence that representations agree
parity != independent proof that both are semantically correct
```

No production behavior is changed by PR3.

---

# PR4 — Typed Rule-Evaluation Evidence

## Status

```text
COMPLETE / MERGED
```

Responsibility: introduce the first source-legitimate typed rule-level evidence
producer.

Current producer:

```text
FullProofValidator
```

PR4 does not parse free-text reasons or metadata. Exact rule identity is emitted
at the validation branch that already knows which predicate failed.

Order-semantic evidence:

```text
src/core/order/rule_violation_evidence.py
```

owns:

```text
OrderRuleViolationEvidence(
    contract_id,
    contract_version,
    rule_id,
    candidate_event_id,
)
```

Compass producer-specific evidence:

```text
src/compass/transition/rule_evaluation_evidence.py
```

owns:

```text
FULL_PROOF_SUPPORTED_RULE_IDS
FullProofValidationEvidence
```

Existing API:

```text
validate(...)
→ ValidationResult
```

Evidence-aware API:

```text
validate_with_rule_evidence(...)
→ FullProofValidationEvidence
```

Both use one shared internal validation branch tree.

PR4 currently supports exactly six `TRANSITION_TRUTH` rule IDs.

Important invariants:

```text
PASSED → no violation evidence
FAILED → exactly one supported violation evidence
ValidationResult candidate ID == violation candidate ID
```

The producer remains fail-fast:

```text
observed violation
= terminating supported failure observed by this invocation

observed violation
!= complete set of all candidate violations
```

Reviewed validation before merge included:

```text
41 focused PR4 tests
9 existing FullProofValidator regression tests
92 PR2 + PR3 regression tests
1,296 complete unit tests
git diff --check
```

---

# Combined PR5 + PR6 — Runtime Preservation and PostgreSQL Rule-Evidence Propagation

## Branch

```text
feat/stage4b5-pr5-pr6-rule-evidence-propagation
```

## Status

```text
IMPLEMENTED

Step 1 — ValidationRuntime preservation
= HUMAN-VALIDATED

Step 2 — PostgreSQL propagation
= HUMAN-VALIDATED before final hardening

Final adversarial hardening
= ADDED
= final rerun required before commit / PR
```

Validated checkpoints before the final six hardening cases:

```text
26 runtime tests passed

67 PR4 + runtime tests passed

37 focused PostgreSQL propagation tests passed

104 combined focused tests passed

2,461 complete repository tests passed

git diff --check passed
```

The final hardening pass adds six additional focused cases for:

```text
PRE post-validation authoritative REPLAY
PRE post-validation authoritative CONFLICT

PRE post-validation concurrency-preparation rejection
PRE post-validation append rejection
IN post-validation append rejection

IN pre-validation stream rejection
```

These cases must be rerun before the branch is considered final.

## Responsibility

Close the production wiring gap between the accepted PR4 producer and the real
PostgreSQL write-side.

The combined delivery preserves:

```text
ValidationDecision
+
OrderRuleViolationEvidence | None
```

through one trusted in-process invocation.

Target flow:

```text
candidate
→ FullProofValidator.validate_with_rule_evidence(...) exactly once
→ FullProofValidationEvidence
→ ValidationRuntime
→ existing ValidationPolicy on the identical ValidationResult
→ ValidationDecisionWithRuleEvidence
→ PostgreSQL write-side PRE / IN execution
→ PostgresWriteSideResult
→ existing normal / trace / measurement delivery surfaces
```

## Why PR5 and PR6 Were Combined

A source-grounded PR5 audit found that an isolated evidence-aware runtime API
would have no production caller.

The first concrete consumer is the existing PostgreSQL write-side.

Therefore:

```text
standalone dormant runtime seam
→ rejected

runtime preservation + real write-side propagation
→ accepted coherent production delivery
```

This keeps the new API justified by a concrete consumer and avoids speculative
production surface.

## Runtime Carrier

`ValidationRuntime` now owns a construction-controlled generic carrier:

```text
ValidationDecisionWithRuleEvidence
    decision: ValidationDecision
    observed_violation: OrderRuleViolationEvidence | None
```

The carrier does not expose `FullProofValidationEvidence` beyond the
producer-handling boundary.

For FullProof:

```text
one FullProof evidence invocation
→ exact ValidationResult
→ policy exactly once
→ exact ValidationDecision
→ exact OrderRuleViolationEvidence object
```

For NoOp / OFF:

```text
SKIPPED
→ ALLOW
→ no rule violation evidence
```

For legacy validate-only validators:

```text
existing ValidationResult
→ existing ValidationPolicy
→ existing decision semantics
→ no fabricated rule evidence
```

Legacy `ValidationRuntime.decide(...)` remains unchanged.

## PostgreSQL Result Extension

`PostgresWriteSideResult` now carries optional additive sibling evidence:

```text
validation_decision_evidence:
    ValidationDecisionWithRuleEvidence | None
```

The field is optional and excluded from primary equality / representation.

Public generic view:

```text
result.validation_decision
result.observed_rule_violation
```

The write-side boundary does not expose `FullProofValidationEvidence`.

When a carrier exists:

```text
result.validation_decision
is
result.validation_decision_evidence.decision
```

must hold.

Equal-valued but distinct decisions are rejected.

Candidate-ID equality alone is not accepted as same-invocation proof.

## Same-Invocation Guarantee

Supported in-process chain:

```text
carrier.decision.validation_result
is
FullProofValidationEvidence.validation_result

PostgresWriteSideResult.validation_decision
is
carrier.decision

PostgresWriteSideResult.observed_rule_violation
is
carrier.observed_violation
```

This is:

```text
supported in-process construction provenance
```

It is not:

```text
cryptographic authenticity
durable provenance
serialized provenance
cross-process provenance
persistence proof
accepted-history proof
retry authorization
```

## PRE / IN Propagation Semantics

Evidence follows whether validation actually occurred.

### PRE_TRANSACTION

Validation occurs before the authoritative business UOW.

Therefore post-validation outcomes preserve the carrier:

```text
VALIDATION_BLOCKED
authoritative REPLAY
authoritative CONFLICT
post-validation stream/admission rejection
ACCEPTED
```

Preliminary replay/conflict before validation carry no validation evidence.

### IN_TRANSACTION

Some outcomes occur before validation.

Therefore:

```text
authoritative REPLAY / CONFLICT before validation
pre-validation stream rejection
→ no validation evidence
```

After validation:

```text
VALIDATION_BLOCKED
append rejection
ACCEPTED
→ preserve the exact runtime carrier
```

Core semantic rule:

```text
validation happened
→ preserve that invocation's observation even if a later terminal outcome differs

validation never happened
→ do not fabricate validation evidence
```

## Trace / Measurement Compatibility

No new public CREATE/PAY evidence APIs were added.

No separate normal / trace / measurement / trace+measurement execution
algorithms were created.

The existing shared producer spine remains:

```text
CREATE / PAY
→ _execute_command(...)
→ PRE_TRANSACTION or IN_TRANSACTION
→ PostgresWriteSideResult
```

Trace and measurement continue to wrap the exact producer result.

Therefore rule evidence naturally survives:

```text
normal
measurement
trace
trace + measurement
```

without duplicated validation orchestration.

## High-Value Adversarial Coverage

Focused tests establish:

```text
legacy decide-only runtime remains valid

FullProof validation executes exactly once

ValidationPolicy executes exactly once

policy receives the identical PR4 ValidationResult object

exact violation object survives runtime and write-side propagation

same candidate ID != same invocation

equal-valued distinct ValidationDecision != same invocation

cross-invocation carrier pairing is rejected

OFF preserves SKIPPED and produces no false rule evidence

pre-validation return produces no validation evidence

post-validation terminal change does not erase validation evidence

failure/success sequences do not leak evidence across invocations

validator/policy/runtime exceptions do not trigger hidden revalidation fallback

reason / metadata cannot select typed rule identity
```

The complete repository regression suite remains the compatibility check for the
existing production surface.

## Non-Goals

The combined PR does not:

- change `SemanticOutcome`;
- change `DecisionReceipt`;
- authorize retry;
- implement Agent feedback transport;
- persist or serialize rule evidence;
- provide cross-process provenance;
- add universal Order rule-evidence producers;
- change Order aggregate or Money semantics;
- add new public write-side execution modes;
- reopen Stage 4B.2;
- make YAML part of the production request path.

---

# PR7 — Semantic Rule-Feedback Composition

## Branch

```text
feat/stage4b5-pr7-semantic-rule-feedback-composition
```

## Responsibility

Compose the existing Stage 4A semantic interpretation with the same-invocation
Stage 4B.5 rule-level refinement without changing the Stage 4A API.

This implements hierarchical semantic refinement:

```text
Stage 4A coarse semantic class
+
Stage 4B.5 exact correctness-rule refinement
```

Central supported case:

```text
SemanticOutcome:
COMPASS_VALIDATION_BLOCKED

+

OrderRuleViolationEvidence:
exact stable rule identity
```

Do not:

- replace `COMPASS_VALIDATION_BLOCKED` with new per-rule outcome codes;
- add rule ID directly to `SemanticOutcome`;
- change unrelated Stage 4A outcomes;
- reconstruct rule identity from text or metadata;
- manually pair independently supplied artifacts and call that same-invocation provenance.

Preferred model:

```text
SemanticOutcome
= coarse cross-system semantic classification

OrderRuleViolationEvidence
= domain-specific rule-level refinement
```

Conceptually:

```text
existing PostgresWriteSideResult
→ existing Stage 4A SemanticOutcome mapper

same-invocation write-side evidence
→ sibling OrderRuleViolationEvidence

both
→ bounded feedback / enriched semantic view
```

A minimal shape may be:

```text
semantic_outcome: SemanticOutcome
observed_violation: OrderRuleViolationEvidence | None
```

but the exact type remains source-grounded until PR7 implementation review.

Compatibility rule:

```text
COMPASS_VALIDATION_BLOCKED
→ may carry B4.5 refinement

LOCK_TIMEOUT / OCC / idempotency / success
→ existing Stage 4A semantics remain unchanged
→ no false B4.5 refinement
```

Same-invocation provenance is mandatory.

---

# Post-PR7 Decision Gate — Domain / Command Rejection Coverage

After PR7, decide whether Stage 4B.5 completion requires typed live rule evidence
for failures before `FullProofValidator`, including:

- illegal CREATE/PAY aggregate state;
- normalized amount <= 0;
- PAY amount != total;
- candidate-construction failures.

Possible decisions:

```text
A. close with current FullProof / Compass producer scope documented;

B. add a separately reviewed domain-command evidence producer PR;

C. expand only when the Retry Governance demo requires those failure families.
```

Do not imply universal rule-evidence coverage unless it actually exists.

---

# Supplement A — Runtime Governance Overhead Characterization

## Current supplement status

```text
source-grounded A/B/C method
= COMPLETE

guarded harness and evidence schema
= IMPLEMENTED / AWAITING REVIEW

canonical micro and PostgreSQL recorded runs
= NOT RUN
```

See [Runtime Governance Overhead Characterization Method](runtime_governance_overhead_method.md)
for the A-control isolation decision, exact timing boundaries, fixed schedules,
statistics, safety gates, evidence layout, and human-run commands. No benchmark
result is claimed before those fixed runs execute.

## Position

```text
PR7 complete
→ semantic/runtime path frozen
→ run comparable performance characterization
→ do not reopen Stage 4B.2
```

## Purpose

Quantify the incremental runtime cost introduced by Stage 4B.5 semantic
governance after the production path is complete.

Stage 4B.2 remains:

```text
COMPLETE / CLOSED
```

Its accepted measurements serve as a historical control where comparable.

The new question is:

```text
What additional runtime cost is introduced by
machine-readable rule evidence,
same-invocation transport,
SemanticOutcome translation,
and rule-level refinement?
```

## Comparison Model

Where historical harness compatibility permits, distinguish:

```text
A — Stage 4B.2 historical baseline
    legacy validation / write-side path before rule-evidence wiring

B — Combined PR5 + PR6
    evidence production
    + runtime carrier
    + write-side propagation

C — PR7 final semantic path
    B
    + SemanticOutcome translation
    + rule-level refinement
```

Interpret:

```text
B - A
= rule-evidence production and transport delta

C - B
= semantic translation / refinement delta

C - A
= total measured Stage 4B.5 governance delta
```

Do not claim perfect causal isolation when historical environments, code, or
database conditions are not comparable. Record comparability limits explicitly.

## Measurement Layers

Use two complementary views.

### Micro / Semantic-Path Cost

Measure the bounded transformation path where practical:

```text
ValidationResult
→ policy decision
→ evidence carrier
→ SemanticOutcome
→ semantic refinement
```

This isolates costs that may be hidden by PostgreSQL latency.

### End-to-End Write-Side Cost

Measure representative production-style flows, including at minimum:

```text
CREATE / PAY
PRE_TRANSACTION / IN_TRANSACTION
accepted path / validation-blocked path
```

Report:

```text
sample count
median / p50
p95
p99 where sample size supports it
absolute delta
relative delta
environment and database configuration
```

Do not treat a statistically visible micro-delta as automatically operationally
important. Interpret the cost relative to end-to-end write latency.

## Non-Goals

This supplement does not:

- reopen Stage 4B.2;
- redefine measurement vocabulary;
- set production SLOs;
- set capacity thresholds;
- select validation strategy;
- authorize disabling governance for performance reasons;
- claim benchmark portability across environments.

Its purpose is characterization:

```text
correctness / governance has a cost
→ measure that cost
→ determine whether it is material in the tested write path
```

---

# Supplement B — Deterministic Python → YAML Contract Projection

## Purpose

Produce a readable YAML representation of the accepted Order Correctness
Contract V0 without introducing a second semantic authority.

Authority remains:

```text
ORDER_CORRECTNESS_CONTRACT_V0
Python objects
= canonical semantic authority
```

Projection:

```text
canonical Python contract
→ deterministic serializable mapping
→ generated YAML
```

The YAML exists for:

```text
human review
AI readability
documentation
demo output
external inspection
```

It does not drive production validation in Stage 4B.5.

## Required Projection Content

The YAML view should preserve, at minimum:

```text
contract_id
contract_version

all 18 stable rule identities

for every rule:
- stable rule ID
- semantic proposition
- correctness category
- subject

transition relationships:
- rule identity
- command
- predecessor status
- candidate event type
- resulting status

amount relationships:
- rule identity
- command
- constraint
```

The YAML may organize these fields hierarchically for readability rather than
forcing users to read only dotted stable-ID strings.

Stable IDs remain present because they are machine identities.

## Projection Invariants

Tests should prove:

```text
Python contract rule count == YAML rule count

Python stable IDs == YAML stable IDs

Python propositions == YAML propositions

Python categories == YAML categories

Python subjects == YAML subjects

Python transition relationships == YAML transition relationships

Python amount relationships == YAML amount relationships
```

A round-trip or parsed-projection parity check may validate exporter correctness.

That does not make YAML authoritative.

## Production Boundary

Stage 4B.5 explicitly does not require:

```text
YAML
→ runtime parse
→ reconstruct Python contract
→ validate production requests
```

Doing so would add runtime parsing, deployment, schema, version-skew, failure,
and performance concerns without a current consumer.

If a future consumer justifies YAML-driven runtime configuration, treat that as
a new architecture decision with separate correctness and performance evidence.

Current rule:

```text
Python → YAML
= readability projection

YAML → production runtime
= deferred
```

---

# PR8 — Stage 4B.5 Closeout

## Branch

```text
docs/stage4b5-pr8-closeout
```

## Responsibility

Record the final delivered Stage 4B.5 boundary and hand off cleanly to future
Retry Governance.

Required closeout record:

- why Stage 4B.5 exists;
- canonical contract identity/version;
- stable 18-rule surface;
- identity-driven representation hardening;
- executable-authority parity scope;
- supported rule-evaluation producers;
- PR4 evidence layering and dependency direction;
- combined PR5+PR6 production evidence-preservation path;
- runtime and write-side same-invocation object-identity guarantee;
- PRE/IN evidence-presence boundaries;
- compatibility with normal / trace / measurement delivery;
- hierarchical SemanticOutcome refinement;
- supported live semantic + rule feedback path;
- unsupported aggregate/domain rejection coverage, if deferred;
- Runtime Governance Overhead Characterization results and limitations;
- deterministic Python → YAML projection and authority boundary;
- relationship to Stage 4A / 4B / 4B.1 / 4B.2;
- bridge to future Retry Governance;
- explicit statement that rule feedback constrains candidate space but does not
  authorize retry.

Closeout should include or link a stage-level rationale answering:

```text
Why is FAILED/BLOCK insufficient for a machine consumer?

Why is free-text reason insufficient?

Why does stable rule identity matter?

How does rule-level evidence narrow the next candidate space?

Why is retry still a separate governance decision?

What runtime overhead does this governance path introduce?

Why is YAML a readability projection rather than a second authority?
```

---

## Future Retry-Governance Handoff

Stage 4B.5 should hand future work an evidence chain such as:

```text
SemanticOutcome
+
optional RuleViolationEvidence
        ↓
Retry Policy
        ↓
RetryDecisionEvidence
        ↓
next-attempt constraint / regeneration
```

Preserve:

```text
RuleViolationEvidence != RetryDecisionEvidence
RetryDecisionEvidence != Agent self-reported rationale
```

Future Retry Policy should be able to show:

```text
which evidence was consumed
→ which policy decision was made
→ why another attempt was authorized or denied
```

Persistence is not required for the first retry-governance demo unless a
concrete durability consumer appears.

---

## Stage Completion Boundary

Stage 4B.5 is complete when:

1. the source-grounded correctness boundary is documented and accepted;
2. a canonical immutable contract with stable identity/version exists;
3. stable rule identities exist for the approved scope;
4. invalid semantic combinations are excluded from the supported construction
   path;
5. parity evidence covers the approved executable owners;
6. `FullProofValidator` can produce exact typed rule-level evidence without text
   parsing or duplicate validation logic;
7. production validation preserves that evidence through one trusted invocation;
8. PostgreSQL write-side execution preserves same-invocation object identity;
9. validation evidence remains present for post-validation terminal outcomes and
   absent for pre-validation terminal outcomes;
10. legacy validators, runtime doubles, and existing write-side APIs remain
    compatibility-safe;
11. existing Stage 4A `COMPASS_VALIDATION_BLOCKED` can be paired with the exact
    B4.5 rule refinement without changing the Stage 4A API;
12. unrelated Stage 4A outcomes remain semantically unchanged;
13. unsupported aggregate/domain typed rule feedback is documented truthfully;
14. the incremental runtime-governance overhead is characterized against a
    bounded baseline with comparability limitations stated;
15. a deterministic Python → YAML contract projection exists and parity checks
    prove it reflects the canonical Python contract;
16. YAML remains a readability projection and does not become a second writable
    authority or mandatory production runtime dependency;
17. retry authorization, strategy, repair, and Agent reasoning remain separately
    owned.

A green suite is evidence for the defined scope.

It is not proof that no future semantic bug exists.
