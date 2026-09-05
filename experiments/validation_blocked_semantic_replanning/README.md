# Validation-Blocked Semantic Replanning

## Status

```text
Status:
PR0 / architecture boundary

Implementation:
NOT YET AUTHORIZED

Feasibility:
PARTIALLY SUFFICIENT
```

This document preserves the reviewed read-only source audit at commit
`c5b8aec573dedc38f7e4b46b88f521bd03044f2e`. PR0 defines the research boundary;
it does not make the experiment executable or authorize later implementation.

> No currently inspected ordinary public-writer input establishes the desired
> changed-intent `VALIDATION_BLOCKED → semantic replanning` scenario.

Current production retains exact typed rule identity for a genuine FullProof
validation block. It does not yet establish the complete machine input or a
legitimate ordinary production scenario needed for the intended changed-intent
repair witness. Evidence sufficiency and production-path reachability are
separate questions. Adding evidence alone would not resolve reachability.

## Research question and target architecture

> Can a semantic validation failure provide bounded evidence that helps a
> planner construct a different business intent, while the repaired intent
> remains only a proposal and must re-enter the full Compass governance path
> as a new request?

The following is a **target architecture**, not current executable behavior:

```text
Request R1
→ Candidate A
→ VALIDATION_BLOCKED
→ bounded typed failure evidence
→ deterministic planner
→ RepairProposal
→ new intent
→ Request R2
→ new RequestSignature
→ normal public writer
→ fresh candidate
→ semantic validation again
→ ALLOW or BLOCK
```

`RepairProposal` names a conditional experiment-local responsibility here. No
planner, proposal type, executor, or PostgreSQL witness is implemented by PR0.
An ALLOW decision would still require normal append admission and successful
transaction completion before an accepted effect could be claimed.

## Core semantic boundary

```text
failure evidence
!= repair proposal
!= new candidate
!= authority
!= accepted fact

agent correction
!= semantic truth
```

A planner may use eligible failure evidence to construct another proposal.
The planner must not authorize acceptance. A proposal must remain separate
from candidate construction, submission authority, and accepted history.
The repaired intent must undergo normal production governance again.

## Current production path and reachability

The public operations are
`PostgresTransactionalWriteSide.create_order()` and `.pay_order()` in
[`src/pipeline/transactional/postgres_write_side.py`](../../src/pipeline/transactional/postgres_write_side.py).
They accept `request_id`, `order_id`, and `amount`; the selected operation
supplies `CommandType.CREATE` or `CommandType.PAY`.

The caller does not submit an arbitrary candidate event:

```text
create_order / pay_order arguments
→ RequestSignature
→ accepted history
→ aggregate reconstruction
→ aggregate command
→ internally constructed OrderEvent candidate
→ FullProof validation
```

Both operations delegate through `_execute_command()` to the configured
validation-placement path.

### PRE_TRANSACTION

The default path, `_execute_pre_transaction_command()`, performs:

```text
RequestSignature construction
→ preliminary PostgresIdempotencyStore.check()
  → REPLAY / CONFLICT may terminate before validation
→ PostgresEventStore.load(order_id)
→ close the preliminary read transaction
→ _rehydrate_aggregate_from_history()
→ _build_validation_context()
→ aggregate.create() / aggregate.pay()
→ _invoke_validation()
→ non-ALLOW action
→ VALIDATION_BLOCKED result
```

The block returns before the business write transaction, append admission,
and idempotency persistence. On an allowing path, an authoritative idempotency
re-check and append-time admission are still required inside the write
transaction.

### IN_TRANSACTION

`_execute_in_transaction_command()` constructs the signature, enters the
business unit of work, checks idempotency, and prepares the stream before
loading history and constructing the aggregate, validation context, and
candidate. A validation block explicitly rolls back the unit of work before
returning. Its result also retains successful stream-preparation evidence.

Neither blocked path appends the candidate or records a successful request.
Transaction completion remains owned by
[`PostgresWriteSideUnitOfWork`](../../src/pipeline/transactional/postgres_unit_of_work.py).

### Candidate ownership limits the scenario

[`OrderAggregate`](../../src/core/order/aggregate.py) reconstructs state through
`apply()` and constructs candidate sequence and predecessor proof from that
state. The writer derives the validation context from the same loaded accepted
history. The public arguments do not include sequence or predecessor proof.

Consequently, these plausible changed-intent failures occur earlier:

```text
illegal CREATE/PAY state
→ aggregate/domain rejection

incorrect PAY amount
→ aggregate/domain rejection

non-positive normalized amount
→ money/domain rejection
```

They are not `VALIDATION_BLOCKED`. The aggregate raises before returning a
candidate for FullProof evaluation. Money normalization and positive-value
enforcement are owned by
[`src/core/common/money.py`](../../src/core/common/money.py).

Concurrent history advancement after the writer's observation is checked at
append admission; it does not automatically turn that internally coherent
candidate/context pair into a FullProof validation block.

## Failure ownership

| Failure family | Current surface |
|---|---|
| Domain/candidate-construction rejection | Exception before a completed semantic-validation result; no normally returned `PostgresWriteSideResult` for that rejection. |
| FullProof semantic failure | `ValidationVerdict.FAILED` → policy BLOCK → `VALIDATION_BLOCKED`. |
| Stream/append admission failure | `ADMISSION_REJECTED`, with stream or append admission evidence. |
| Infrastructure/runtime failure | Admission infrastructure result or propagated exception, depending on source. |

The admission vocabulary and PostgreSQL translations are defined in
[`admission.py`](../../src/pipeline/transactional/admission.py) and
[`postgres_admission.py`](../../src/pipeline/transactional/postgres_admission.py).
There is no universal failure envelope that makes these families equivalent.

This experiment targets only a genuine FullProof semantic validation block.
A domain exception must not be substituted without explicitly changing the
research question in a later reviewed decision. The completed
[Stage 4B.5 boundary](../../docs/implementation_notes/stage_4b_5/README.md)
already distinguishes these enforcement owners.

## Evidence boundary

### Stable typed evidence

For the genuine FullProof evidence path, current source establishes:

```text
VALIDATION_BLOCKED PostgresWriteSideResult
→ exact ValidationDecision
→ exact ValidationDecisionWithRuleEvidence runtime carrier
→ exact OrderRuleViolationEvidence
```

The production ownership chain is:

```text
FullProofValidator.validate_with_rule_evidence()
→ FullProofValidationEvidence
→ ValidationRuntime.decide_with_rule_evidence()
→ ValidationDecisionWithRuleEvidence
→ writer retains carrier.decision and the carrier
→ result.observed_rule_violation exposes the exact observation
```

[`ValidationResult`, `ValidationDecision`, and their enums](../../src/compass/transition/types.py)
separate semantic verdict from enforcement action. The
[`FullProof producer bundle`](../../src/compass/transition/rule_evaluation_evidence.py)
correlates the result and violation with the same candidate. The
[`runtime carrier`](../../src/compass/transition/runtime.py) preserves those
source objects without parsing text or rerunning validation.

| Stable evidence | Current contract |
|---|---|
| Terminal write-side outcome | `PostgresWriteSideOutcome.VALIDATION_BLOCKED`. |
| Semantic verdict | `ValidationVerdict.FAILED` on this FullProof failure path. |
| Enforcement action | `EnforcementAction.BLOCK` under the current validation policy. |
| Candidate identity | `candidate_event_id`, correlated across the producer bundle. |
| Rule identity | `OrderCorrectnessRuleId`, identifying one observed supported rule violation. |
| Contract identity | `contract_id`, currently `order.correctness`. |
| Contract edition/version | `contract_version`, currently `0`; no separate per-rule version field. |
| Exact runtime rule-violation carrier | `validation_decision_evidence`, with the identical decision retained by the result. |

[`OrderRuleViolationEvidence`](../../src/core/order/rule_violation_evidence.py)
contains exactly `contract_id`, `contract_version`, `rule_id`, and
`candidate_event_id`. It does not contain observed/expected operands, a repair
instruction, or authority. It describes one observed failure, not a complete
violation set or a priority ranking.

This relationship is supported live in-process custody. It does not establish
authenticity, durable provenance, or cross-process binding. The carrier's
references are read-only; the nested `ValidationResult` and its metadata are
not deeply immutable.

The evidence carrier is optional across the broader writer compatibility
surface. Legacy `decide()`-only runtimes and non-FullProof validators do not
provide this exact rule observation. A coarse `VALIDATION_BLOCKED` outcome
alone therefore does not establish the evidence required by this experiment.

### Available but not an accepted repair contract

`ValidationResult.metadata` is `Dict[str, Any]`. FullProof branches retain
comparison details such as actual/expected sequence, claimed/expected
predecessor identity or version, and actual/required status in this open
dictionary. Those branch-specific values are structured diagnostics, not an
accepted typed operand contract for semantic repair.

Human-readable `reason` text is diagnostic only. It must not be parsed to
derive repair values or machine policy. Neither metadata availability nor a
reason string closes the current evidence gap.

The declarative
[`Order correctness contract`](../../src/core/order/correctness_contract.py)
contains typed rule knowledge, including allowed transitions and amount
constraints. It does not supply the current invocation's observed operands
or become a second executable correctness authority.

### Not retained in the result

For the genuine blocked path, `PostgresWriteSideResult` does not retain:

- the full candidate object or failed candidate payload;
- the complete `ValidationContext`;
- accepted history; or
- the original `RequestSignature`.

The writer retains the exact validator output, including metadata and timing
fields, through the decision carrier. The absent candidate, context, history,
and request signature are not fields discarded from `ValidationResult`; they
were not captured there in the first place.

A future live experiment may combine:

```text
exact PostgresWriteSideResult
+ caller-retained RequestSignature
```

The caller may retain request custody. Result-local absence does not by itself
justify changing production. Typed rule-specific observed and expected
operands remain missing as an accepted repair input. Any necessary evidence
responsibility must be reviewed after a legitimate scenario is identified.

### Terminal semantic refinement

[`map_postgres_write_side_result_to_semantic_rule_feedback()`](../../src/compass/runtime/write_side_rule_feedback.py)
is an explicit composition after the writer returns; the public writer does
not automatically invoke it. It derives the existing `SemanticOutcome` and
retains the exact rule observation as terminal `rule_refinement`.

For `VALIDATION_BLOCKED`, refined feedback requires exact Order rule evidence
and raises if it is absent. The coarse semantic mapper can still accept a
legacy evidence-less block. Refinement does not infer a rule from reason,
metadata, or semantic outcome code, and does not authorize repair or execution.

## Existing FullProof rule assessment

[`FullProofValidator`](../../src/compass/transition/validators.py) reports the
first observed failure from these six supported identities. The rule names
below are members of `OrderCorrectnessRuleId`.

| Existing rule | Failure it can identify | Limitation for changed-intent replanning |
|---|---|---|
| `TRANSITION_SEQUENCE_MATCHES_ACCEPTED_NEXT_VERSION` | Candidate sequence differs from accepted predecessor version plus one. | Public writer generates sequence; correcting sequence alone does not establish different business intent. |
| `TRANSITION_PROOF_PREV_EVENT_ID_MATCHES_ACCEPTED` | Claimed predecessor event identity differs from accepted history. | Public writer derives the proof; a corrected predecessor claim is not itself a changed request payload. |
| `TRANSITION_PROOF_PREV_VERSION_MATCHES_ACCEPTED` | Claimed predecessor version differs from accepted history. | Same candidate-construction boundary; proof correction alone does not establish changed intent. |
| `TRANSITION_PROOF_PREV_STATUS_MATCHES_ACCEPTED` | Claimed predecessor status differs from accepted history. | Same candidate-construction boundary; proof correction alone does not establish changed intent. |
| `TRANSITION_EVENT_TYPE_LEGAL_FROM_ACCEPTED_STATUS` | Candidate event type is illegal from the accepted predecessor status. | Public aggregate commands reject illegal CREATE/PAY states before returning a candidate. |
| `TRANSITION_CANDIDATE_EVENT_TYPE_SUPPORTED` | Candidate event type is unsupported. | Public CREATE/PAY operations generate supported event types rather than accepting arbitrary event types. |

The necessary distinction is:

```text
validator can reject candidate X
!=
ordinary production command path can legitimately produce candidate X
```

No qualifying first rule is selected by PR0. Sequence mismatch is a small
validator-level demonstration, but it does not establish the requested
changed-intent public-writer scenario. PAY amount equality is a genuine
business constraint, but its current rejection belongs to the domain path.

The existing
[rule-evidence propagation test](../../tests/integration/pipeline/transactional/test_postgres_write_side_rule_evidence_propagation.py)
uses `_SequencedFullProofValidator` to alter `actual_prev_version` before
delegating to FullProof. It demonstrates exact evidence propagation. That
test mechanism must not be described as proof that an ordinary production
command produced a semantically invalid intent against unchanged context.

### No current amount-limit example

Current inspected Order production does not contain this rule:

```text
requested amount = 300
maximum allowed = 120
→ VALIDATION_BLOCKED
```

This is not current repository behavior. It must not supply the planned
implementation scenario. A conceptual example outside current source cannot
justify inventing a business rule solely for this experiment.

## New intent and request identity

```text
Re-observation recovery
→ same RequestSignature

Semantic replanning
→ new semantic intent
→ new RequestSignature
```

The complete
[`RequestSignature`](../../src/storage/idempotency_store.py)
contains `request_id`, `command_type`, `order_id`, and `amount`. Sequence,
predecessor proof, candidate event ID, and timestamps are not request fields.
Changing only those candidate fields does not establish changed business
intent. A fresh request ID alone also does not prove a semantic correction.

The experiment requires a fresh `request_id` for repaired intent. Existing
public CREATE/PAY operations already construct a signature from the new
arguments; no production signature change is currently justified.

[`PostgresIdempotencyStore`](../../src/storage/postgres_idempotency_store.py)
looks up `request_id` and compares a versioned fingerprint of command type,
order ID, and canonical money amount. A merely different representation of
the same canonical amount need not be a different semantic payload.

Current idempotency behavior is qualified by accepted-request memory:

```text
accepted request
+ existing idempotency record
+ same request_id
+ changed canonical payload
→ CONFLICT

failed validation
+ no accepted effect
+ no idempotency record
+ reused request_id
→ may still observe MISS
```

Fresh request identity for semantic repair is an intended semantic ownership
rule for this experiment, not a universal behavior already enforced after
every failed invocation by the database. PR0 does not change idempotency.
Durable `derived_from` lineage is not required for the first live experiment.

## Stage 4E separation

```text
Stage 4E
= another invocation of the SAME complete request

Semantic replanning
= submission of a DIFFERENT intent as a new request
```

The current
[Stage 4E evaluator](../../src/compass/runtime/postgres_write_side_reinvocation_authority.py)
has reviewed positive profiles for preparation lock timeout and coherent
append version advancement. A well-typed `VALIDATION_BLOCKED` result satisfies
neither and receives `NoReinvocationAuthority`. Validation block must not be
classified as retryable by this experiment.

The
[invocation owner](../../src/pipeline/transactional/postgres_write_side_invocation_owner.py)
retains and dispatches the same complete signature. Do not use
`ReinvocationAuthorization`, `invoke_authorized_reinvocation()`, the prior
same-request `RecoveryProposal`, or `ControlledExecutor` for changed intent.

No Stage 4E authorization is required merely to independently submit a new
request through the normal application boundary. However:

```text
failure evidence
!= authority to submit arbitrary work
```

The experiment driver will own its explicitly bounded submission behavior,
subject to the implementation entry gate. The proposal grants neither
submission authority nor acceptance. Existing Stage 4C current-response
authority also does not authorize repair or another attempt; its
[profile boundary](../../src/compass/runtime/write_side_runtime_decision.py)
remains unchanged.

## DecisionReceipt separation

```text
PostgresWriteSideResult
= live execution result

DecisionReceipt
= durable semantic aftermath / later recovery evidence
```

The first experiment should consume live result evidence directly.
`DecisionReceipt` is not a required first-version dependency. Making it
mandatory would introduce an unnecessary persistence/recovery dependency.

The current
[DecisionReceipt boundary](../../docs/boundary_notes/decision_receipt_boundary.md)
permits live evidence consumers without prior receipt persistence. A receipt
preserves selected governance evidence, not authority or accepted fact;
materialization alone does not prove transaction durability.

A later crash/restart experiment may revisit committed durable evidence after
the live semantic-replanning boundary is proven. It would need to establish
sufficient persisted inputs and re-observe current state independently. This
document does not claim that current receipts can reconstruct a repair input
or authorize recovered work.

## Relationship to the previous autonomous experiment

The completed
[deterministic autonomous-governance experiment](../deterministic_autonomous_governance/README.md)
already established:

```text
proposal
!= authority
!= execution
```

Its planner proposes one fresh same-request invocation after append staleness.
Independent Stage 4E evaluation and owner-local one-shot capability determine
whether that proposal can execute. Its PostgreSQL positive witness reaches
authoritative REPLAY, rather than changing intent and validating a repair.

This experiment would add a different question:

```text
semantic failure
→ different proposed intent
→ new request
→ governance again
```

Reuse the architectural discipline of exact live source custody, deterministic
composition, and proposal/authority/execution separation. Do not reuse or
generalize the previous same-request proposal and executor contracts.

No current production consumer was identified that needs to consume or persist
a `RepairProposal`. Conditional implementation should default to an
experiment-local type, using existing request and result contracts where
appropriate. A production planner contract is not currently justified.

## Desired witnesses — gated

All four witnesses remain gated until a legitimate production scenario is
approved. These are intended observations, not completed results.

### Witness A — original intent fails closed

```text
R1
→ genuine FullProof VALIDATION_BLOCKED
→ no accepted event
→ no idempotency record for R1
```

The failure must come from the real semantic validation boundary. A domain
exception, fabricated runtime block, or append conflict is not this witness.

### Witness B — evidence informs a proposal

```text
exact live R1 result
+ bounded typed failure evidence
+ caller-retained R1 identity
→ deterministic repair proposal R2
```

Planning performs no writes. The proposal does not create an accepted event,
invoke a writer, or authorize submission. Required machine inputs must have
explicit source ownership rather than being reconstructed from diagnostics.

### Witness C1 — correct repair is re-governed

```text
R2
→ fresh request identity
→ meaningfully changed intent
→ normal public writer
→ fresh candidate and FullProof validation
→ PASSED / ALLOW
→ normal append admission and successful commit
→ accepted effect
```

The witness must not terminate through prior-request replay or validation OFF.
Acceptance must remain a result of full normal governance, not planner output.

### Witness C2 — incorrect repair is blocked again

Starting from an independent equivalent baseline:

```text
R3
→ fresh request identity
→ incorrect semantic repair
→ normal public writer
→ fresh candidate and FullProof validation
→ FAILED / BLOCK
→ VALIDATION_BLOCKED
→ no accepted effect
```

C1 and C2 are separate witnesses. They are not a retry-until-correct loop.
A negative repair that raises before FullProof validation does not satisfy C2.
The paired witnesses must preserve `agent correction != semantic truth`.

## Falsification and invalid shortcuts

The intended experiment is not proven if:

- the original failure is only a domain exception;
- BLOCK is synthetically fabricated by an alternate test runtime;
- validation context is manually corrupted while claiming normal production behavior;
- repair values are parsed from `reason`;
- open metadata is silently promoted to stable machine policy;
- only sequence, proof, or candidate ID changes while changed business intent is claimed;
- the planner writes directly;
- the repaired request bypasses the normal public writer;
- the repaired request bypasses validation;
- Stage 4E is used to mutate the request;
- direct event-store append replaces normal governance;
- only the successful repair is shown; or
- the invalid repair fails before FullProof validation.

Fault injection can establish a narrower propagation or robustness claim. It
must remain labeled as such and must not stand in for the research question.

## Implementation entry gate

PR1 is not automatically authorized when PR0 merges. Implementation may proceed
only after review establishes:

1. A legitimate ordinary production input/path that reaches genuine FullProof
   `VALIDATION_BLOCKED`.
2. The failed condition represents a semantic property relevant to a
   meaningfully changed intent.
3. Sufficient bounded machine-readable evidence exists, or a separately
   reviewed evidence responsibility is justified.
4. The planner does not require parsing human-readable text.
5. Repaired intent can be submitted as a new request through normal governance.
6. Both successful and invalid repair witnesses can reach semantic validation
   honestly.

```text
PR0 merge
!= authorization to implement PR1
```

Until this gate is satisfied, implementation remains unauthorized. Missing
operands do not authorize a new evidence type, and an unreachable candidate
does not authorize a new candidate API or business rule. No production change
set is selected by PR0.

## Conditional PR plan

### PR0 — Architecture Boundary

Documentation only, confined to this README. Preserve current evidence,
reachability limits, responsibility separation, witnesses, and the entry gate.
Validation consists of source/link review, complete diff inspection, whitespace
checking, and verification of the single-file change boundary.

Status after merge:

```text
research boundary defined
implementation gated
```

### PR1 — Conditional Deterministic Repair Model

Entry requires PR0 acceptance, satisfaction of the implementation entry gate,
and explicit authorization for this implementation scope.

Possible scope is an experiment-local `RepairProposal`, one deterministic
planner, and unit tests. Planning performs no writes. There is no production
planner contract, authority artifact, executor lifecycle, or recovery loop.

Unit tests would cover the approved evidence source and transformation, exact
live source custody, unsupported/missing evidence handling, independence from
reason text, fresh request identity, meaningful intent change, and absence of
planning side effects. Exit requires that bounded model and its tests to be
reviewed and complete; it does not establish the PostgreSQL witnesses.

### PR2 — Conditional PostgreSQL Witness and Closeout

Entry requires the approved PR1 model, explicit implementation authorization,
and authorization for the bounded test-database operations.

Positive and negative semantic-repair witnesses belong together. PR2 must
prove A, B, C1, and C2 through real normal governance, including fresh semantic
validation, accepted-history/idempotency observations, and no writes during
planning. Closeout must distinguish observed results from remaining limits.

Do not create PR3 only for symmetry. If a genuine production evidence
responsibility is necessary before PR1, it must be reviewed as its own
prerequisite responsibility rather than inserted incidentally into planner
work. PR0 neither approves that responsibility nor expands an existing
production owner to absorb it.

## Explicit non-goals

The first version does not introduce:

- LLM;
- DecisionReceipt dependency;
- restart recovery;
- multi-attempt loop;
- retry budget;
- backoff;
- scheduler;
- A3/A4/A5;
- durable repair lineage;
- workflow engine;
- generic recovery policy;
- Stage 4D selector;
- new Quotient Model version;
- generic autonomous agent framework;
- new business rule invented solely for the experiment; or
- production `RepairProposal` without a production consumer.

PR0 changes no production source, tests, migrations, dependencies, environment
configuration, Stage 4E, DecisionReceipt, SemanticOutcome, Stage 4C, Order
aggregate, correctness contract, FullProof validator, validation evidence
types, RequestSignature, idempotency behavior, previous experiments, roadmap,
or ADR files. It implements no planner, proposal, executor, PostgreSQL witness,
candidate API, semantic rule, evidence type, or typed operand structure.
