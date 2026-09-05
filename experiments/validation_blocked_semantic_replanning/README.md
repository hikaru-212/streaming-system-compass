# Validation-Blocked Semantic Replanning

## Status

```text
Status:
Commit 4 / Level 1 executable closeout

Documentation boundary:
SELECTED / reviewed

Model-level implementation scope:
LEVEL 1 COMPLETE

Governed fixture implementation:
ESTABLISHED IN COMMIT 3

Semantic-replanning planner:
IMPLEMENTED / A, B, C1, C2 EXECUTED

Production integration:
NOT AUTHORIZED

Existing Order VALIDATION_BLOCKED evidence feasibility:
PARTIALLY SUFFICIENT
```

Commit 1, `0fe0cd5` (`docs: define semantic replanning experiment boundary`),
preserved the reviewed source audit at
`c5b8aec573dedc38f7e4b46b88f521bd03044f2e`. Its PR0 boundary required a genuine
production FullProof validation block and left implementation unauthorized.

Commit 2, `6d20709`, selected the separate experiment-owned bounded
operational/configuration proposal model. Commit 3, `a335e1a`, established the
governed fixture in [model.py](model.py), independently of a planner.

The current Commit 4 work implements the pure planner and executes both revised
proposal outcomes through that unchanged fixture. The focused suite passed
before this closeout update. Level 1 is complete within the trusted in-process
model; production integration remains unauthorized. Commit 4 implements and
witnesses deterministic semantic replanning.

The original production finding remains valid:

> No currently inspected ordinary public-writer input establishes the desired
> changed-intent `VALIDATION_BLOCKED → semantic replanning` scenario.

Current production retains exact typed rule identity for a genuine FullProof
validation block. It does not yet establish the complete machine input or a
legitimate ordinary production scenario needed for the intended changed-intent
production repair witness. Evidence sufficiency and production-path
reachability are separate questions. Adding evidence alone would not resolve
reachability. This finding does not require the selected experiment-owned
fixture to alter Order or impersonate its production result types.

## Research question and target architecture

> Can a semantic validation failure provide bounded evidence that helps a
> planner construct a meaningfully different intent, while the revised intent
> remains only a proposal and must undergo full governance again as a new
> request?

### Level 1 — executed experiment-owned model

The executed proof level is an **experiment-owned governed semantic-replanning
model**. The focused witnesses establish this model path:

```text
Request R1
→ structurally valid operational/configuration proposal A
→ fixture semantic validation BLOCK
→ bounded typed failure evidence
→ deterministic planner
→ repair proposal
→ new intent
→ Request R2
→ fresh complete fixture request identity
→ normal fixture submission boundary
→ fresh semantic validation
→ ALLOW or BLOCK
```

ALLOW is a decision, not an accepted effect. The fixture's deterministic state
owner must separately complete the accepted-state transition. Planning owns
neither submission nor that transition. Within this trusted in-process
experiment, a deterministic proposal-producing actor consumes bounded evidence
from an observed governed rejection to formulate a different intent. The
revised proposal remains non-authoritative and independently passes through
the same fixture submission boundary. A valid revision is accepted, while an
invalid revision is rejected again without changing accepted state.

### Level 2 — stronger production integration, still gated

The original PR0 target was:

```text
PostgresTransactionalWriteSide
→ candidate
→ genuine FullProof VALIDATION_BLOCKED
→ exact live PostgresWriteSideResult
→ bounded evidence / repair proposal
→ new intent / new RequestSignature
→ normal production writer and fresh validation
→ ALLOW or BLOCK
```

This production-oriented target and its reachability limits are retained as
audit history, not selected Level 1 work. A future production integration
requires a real production consumer, a production-owned proposal surface,
production semantic validator, production state/effect owner, and real
PostgreSQL integration. No such configuration consumer is established here.
A new producer would need its own reviewed semantics; it must not claim to be
the existing Order FullProof path merely by reusing result vocabulary.

```text
Level 1 success
!= production semantic-replanning support
```

The experiment name retains the broader research question. Level 1 results
must be identified as model-level semantic rejection, not current production
`VALIDATION_BLOCKED`. The production audit below remains evidence about the
existing Order system, not the fixture's implementation contract.

## Completed Order boundary — preserved unchanged

```text
Existing Order domain
= completed deterministic business domain
= not modified for this experiment

Agent semantic-replanning experiment
= separate experiment-owned governed proposal model
```

The current Order domain exposes deterministic CREATE/PAY commands with
aggregate-owned candidate construction. This experiment does not alter that
completed responsibility. Many business-invalid inputs are already resolved
before FullProof validation; the existing FullProof rules largely protect
transition/proof consistency against accepted history.

The experiment must not weaken `OrderAggregate` checks, add an artificial
Order policy or amount ceiling, expose arbitrary `OrderEvent` construction,
allow Agent control over sequence/proof/version fields, or reinterpret domain
exceptions as `VALIDATION_BLOCKED`. These ownership boundaries remain intact.

## Selected Agent-era setting

The proposal-producing actor may be probabilistic or autonomous. Its question
is distinct from deterministic governance:

```text
Agent / planner:
What operational change should I propose?

Deterministic governance:
May this proposed effect become authoritative?
```

Operational observations may leave several choices plausible. An authoritative
constraint limits admissibility without necessarily determining the optimal
configuration. Agent participation is meaningful where that judgment remains
unresolved; it should not recompute an answer deterministic authority already
uniquely supplies.

The repository's
[probabilistic-agency research](../../docs/research/ai_governance/probabilistic_agency_inside_deterministic_business_workflows.md)
distinguishes:

```text
Delegation
!= Influence
!= Semantic Admission
```

For this model, delegation concerns choosing an operational proposal;
influence is restricted to the permitted action/value and bounded target;
semantic admission remains independently deterministic. The
[operational rate-budget case study](../../docs/semantic_admission/consensus_is_not_semantic_authority_rate_limiter.md)
provides conceptual motivation. Neither research note establishes a current
production configuration contract or requires multi-agent consensus.

The following numbers and rate-budget example describe an **experiment
model, not existing production behavior**:

```text
current configuration = 100
independently owned authoritative maximum = 120

Agent proposes 300
→ semantic BLOCK
→ bounded rejection evidence
→ deterministic planner proposes 120
→ fresh governance
→ ALLOW

independent equivalent baseline:
planner proposes 200
→ fresh governance
→ BLOCK again
```

The maximum does not instruct the planner to choose exactly 120. Selecting
that value is a bounded planner policy; other admissible values may represent
different operational tradeoffs. A deterministic stand-in can test governance
separation without proving Agent reasoning quality or optimal configuration.

## Core semantic boundary

```text
failure evidence
!= repair proposal
!= new candidate
!= authority
!= accepted fact

agent correction
!= semantic truth

proposal
!= authority
!= accepted truth

validation evidence
!= repair policy
```

A planner may use eligible failure evidence to construct another proposal.
The planner must not authorize acceptance. A proposal must remain separate
from candidate construction, submission authority, and accepted history.
The revised intent must undergo the applicable governance path again: the
fixture path for Level 1, and a separately reviewed production path for Level 2.

## Implemented planner and source custody

[planner.py](planner.py) defines only the closed `RateBudgetRepairPolicy` enum
and pure `plan_rate_budget_repair()` function, with local input checks. The
function accepts:

```text
exact live BlockedSubmission
+ caller-retained exact original RateBudgetProposal
+ caller-owned new_request_id
+ explicit RateBudgetRepairPolicy
→ new RateBudgetProposal
```

The existing immutable `RateBudgetProposal` is sufficient. No `RepairProposal`
wrapper is needed because test composition retains the source result, original
proposal, and selected policy; no other consumer needs bundled correlation.
The output contains only request ID, action, target, and proposed rate. It
carries no verdict, evidence, accepted state, authority, owner, or callback.

The function requires exact supported input types, including an actual
`BlockedSubmission` type rather than raw rejection evidence. It requires
`blocked_submission.decision.proposal is original_proposal`, checks that the
rejected rate exceeds the retained maximum, and refuses the original request
ID or an unchanged semantic rate. Normal proposal construction checks nonblank
IDs and preserves spelling. It performs no validation, submission, or writes.

These checks freeze a trusted live composition, not authenticated provenance.
Both `BlockedSubmission` and `RateBudgetRejectionEvidence` are publicly
constructible. Exact types, source object correlation, and coherent operands
cannot prove that a fixture actually produced an arbitrary supplied carrier.
Trusted composition supplies the observed result; there is no signing,
capability token, provenance registry, durable lineage, or global ID memory.

### Two explicit proposal policies

| Policy | Transformation | Rejected 300 against maximum 120 |
|---|---|---|
| `USE_OBSERVED_MAXIMUM` | Use the exact retained `contract.maximum_rate`. | Propose 120. |
| `REDUCE_OBSERVED_RATE_BY_ONE_THIRD` | Compute `(2 * rejected_rate.value) // 3` in exact integer units. | Propose 200, without clamping to the maximum. |

The reduction policy's name describes its transformation, not its correctness.
It intentionally can produce another inadmissible proposal. Neither policy
calls the validator or decides ALLOW/BLOCK for its output.

```text
maximum = 120
= validation evidence

choose 120
= planner policy

same semantic rejection evidence
→ reduction policy proposes 200
→ explicit fresh submission
→ governance BLOCKs again
```

The cosmetic-repair guard remains explicit. There is no reachable unchanged
rate under coherent current inputs: the maximum is strictly smaller than the
rejected rate, and `floor(2*r/3) < r` for the positive rejected integer `r`.
No synthetic policy was introduced merely to exercise that guard.

No Executor is needed. Tests explicitly call the planner and then, separately,
`fixture.submit(revised_proposal)`. The unchanged fixture owns fresh validation
and the accepted-state transition; the planner receives neither that owner nor
any execution callback.

## Established experiment ownership and fixture evidence

The implementation is an experiment-owned model, not a production configuration
subsystem. Commit 3 established these local responsibilities:

- `RateBudgetProposal` for bounded intent and complete fixture request identity;
- `RateBudgetContract` and `AcceptedRateBudgetState` for independent authority
  and an immutable state observation;
- pure `validate_rate_budget()` for the inclusive maximum check;
- `RateBudgetValidationAllowed` or `RateBudgetRejectionEvidence` retaining exact
  proposal and contract inputs; and
- `GovernedRateBudgetFixture.submit()` for fresh validation and an accepted-state
  transition, returning `AcceptedSubmission` or `BlockedSubmission`.

Model responsibilities belong under `experiments/`, with model tests under
`tests/experiments/`. No production promotion or production consumer is
currently justified. PostgreSQL integration tests are not a Level 1 delivery.

The proposer may choose a requested value within the permitted proposal
surface. It does not own the authoritative limit, contract edition, accepted
state, internal event identity, sequence, predecessor proof, or database
version. The system must obtain authoritative context independently of the
proposal; a proposer-supplied limit cannot authorize that same proposal.

A structurally valid proposal must be able to reach either semantic ALLOW or
semantic BLOCK. Construction must not silently clamp the proposed value or
replace it with an admissible one. This is a new fixture proposal/admission
distinction, not permission to move or remove existing Order domain checks.

### Typed evidence established by the fixture

The original fixture design requirements are now supplied by these
**experiment-local contracts**, not production evidence types:

| Evidence responsibility | Current fixture source |
|---|---|
| Validation verdict | Rejection property `verdict = FAILED`. |
| Enforcement action | Rejection property `enforcement_action = BLOCK`. |
| Proposal correlation | Exact `decision.proposal`, retaining the original request ID and intent. |
| Rule identity | Fixed `RATE_BUDGET_WITHIN_MAXIMUM` rejection property. |
| Contract identity/version | Exact `decision.contract`, including its supplied identity and positive edition number. |
| Target/context identity | Proposal/contract target and exact live contract custody; no state revision or durable context identity. |
| Typed proposed value | `proposal.proposed_rate`, a nonnegative exact integer in abstract fixture units/sec. |
| Typed permitted constraint | `contract.maximum_rate`, in the same canonical quantity type. |

Preserve three separate inputs:

```text
operational observations
!= validation evidence
!= planner policy
```

Operational observations may inform preference. Validation evidence reports
the failed comparison, such as `proposed = 300` and `maximum = 120`. Planner
policy determines whether and what to propose next. The evidence does not
mean `repair instruction = set exactly 120`.

The planner consumes exact live fixture rejection evidence and caller-retained
original intent. These fixture carriers have no reason or open metadata field
to parse into policy. A revised request receives fresh validation against the
fixture owner's retained contract; old rejection evidence cannot authorize its
acceptance. The fixture has no contract replacement, concurrency, or durable
history responsibility.

## Separation from Load / Capacity Protection

```text
Load / Capacity Protection
= whether the system can safely accept more work

Operational Configuration Governance
= whether an Agent-proposed configuration change is semantically authorized
```

A rate-budget example can appear in both discussions without merging their
responsibilities. Level 1 neither runs a traffic controller nor implements a
real rate limiter. Resource headroom is not authority to exceed a contractual
limit, and overload is not itself proof of semantic invalidity. The existing
[capacity-pressure boundary](../../docs/roadmap/deferred_architecture_backlog.md#capacity-pressure-evidence-checkpoint)
likewise separates capacity controls from semantic correctness.

## Preserved production audit — Order path and reachability

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

## Preserved production audit — failure ownership

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

Original PR0 targeted only a genuine FullProof semantic validation block.
The selected Level 1 now targets genuine fixture semantic validation, not
domain-exception replanning. Domain rejection must not be relabeled as either
fixture semantic BLOCK or production `VALIDATION_BLOCKED`. The completed
[Stage 4B.5 boundary](../../docs/implementation_notes/stage_4b_5/README.md)
already distinguishes these enforcement owners.

## Preserved production audit — evidence boundary

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
alone therefore does not establish the original production repair input.

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

A future eligible live production consumer may combine:

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

## Preserved production audit — FullProof rule assessment

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

No qualifying Order rule was selected by PR0, and the scope refinement does
not select one. Sequence mismatch is a small validator-level demonstration,
but it does not establish the original
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

This is not current Order behavior. It must not supply an Order implementation
scenario or justify inventing an Order rule. The separately selected
configuration fixture uses an explicitly experiment-owned constraint; it does
not claim that this amount rule exists in production.

## New intent and request identity

```text
Re-observation recovery
→ same RequestSignature

Semantic replanning
→ new semantic intent
→ new complete request identity
```

For existing Order requests, complete identity is represented by
[`RequestSignature`](../../src/storage/idempotency_store.py)
and contains `request_id`, `command_type`, `order_id`, and `amount`. Sequence,
predecessor proof, candidate event ID, and timestamps are not request fields.
Changing only those candidate fields does not establish changed business
intent. A fresh request ID alone also does not prove a semantic correction.

The experiment requires a fresh `request_id` for revised intent.
`RateBudgetProposal` retains that ID, the permitted action, target, and canonical
proposed rate. The planner checks difference from R1's ID only; the caller owns
global freshness. It generates no UUID, clock value, counter, or prior-ID store.
A revised request also changes the rate while preserving action and target.

Existing public CREATE/PAY operations construct Order signatures from their
arguments. That does not make `RequestSignature` a configuration contract.
Level 1 must not disguise configuration values as Order amounts or extend the
production signature to fit the fixture. No production signature change is
justified.

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
every failed invocation by the database. This experiment does not change
idempotency, and the fixture explicitly has no request-memory contract.
Durable `derived_from` lineage is not required for Level 1.

## Stage 4E separation

```text
Stage 4E
= same complete request re-observation authority

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

Test composition owns the explicitly bounded submissions. Level 1 uses the
fixture submission boundary without Stage 4E artifacts. The proposal grants neither
submission authority nor acceptance. Existing Stage 4C current-response
authority also does not authorize repair or another attempt; its
[profile boundary](../../src/compass/runtime/write_side_runtime_decision.py)
remains unchanged.

## DecisionReceipt separation

```text
PostgresWriteSideResult
= live execution result

Level 1 fixture rejection
= live model result / immediate planner input

DecisionReceipt
= durable semantic aftermath / later recovery evidence
```

The model consumes live fixture rejection evidence directly.
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

This experiment demonstrates a different model-level consequence:

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
a `RepairProposal`. Commit 4 returns the existing experiment-local
`RateBudgetProposal` directly. Existing Order request/result types are not
generic configuration contracts. A production planner contract is not justified.

## Level 1 executed witnesses

The focused [replanning tests](../../tests/experiments/validation_blocked_semantic_replanning/test_replanning.py)
execute A/B/C1/C2 through the unchanged Commit 3 fixture. The parameterized
`test_a_b_and_independent_regoverned_revision` starts from a new baseline for
each C1/C2 case. None claims production FullProof or PostgreSQL integration.

### Witness A — original intent fails closed

```text
R1 = fixture-request-001, proposed rate 300
→ structurally valid proposal A
→ actual fixture semantic validation BLOCK
→ exact initial accepted-state object retained at 100
```

The real fixture compares 300 against the independently supplied maximum 120.
The result retains exact R1 and contract objects, `FAILED`, `BLOCK`, and
`RATE_BUDGET_WITHIN_MAXIMUM`. No synthetic decision or context corruption is
used for this witness.

### Witness B — evidence informs a proposal

```text
exact live R1 fixture rejection
+ bounded typed failure evidence
+ caller-retained R1 identity
→ deterministic repair proposal R2
```

Planning performs no writes. The proposal does not change accepted state,
invoke submission, or authorize execution. Required machine inputs must have
explicit source ownership rather than being reconstructed from diagnostics.

Both policy cases assert a new immutable proposal, changed ID/rate, unchanged
action/target, and unchanged original proposal, evidence, contract, and accepted
state. Transparent submission and validation observers remain at one call each
through planning.

### Witness C1 — correct repair is re-governed

```text
USE_OBSERVED_MAXIMUM → R2 = fixture-request-002, proposed rate 120
→ fresh request identity
→ meaningfully changed operational/configuration intent
→ normal fixture submission boundary
→ fresh semantic validation ALLOW
→ deterministic accepted-state transition
→ accepted fixture rate 120
```

The explicit second submission creates a fresh `RateBudgetValidationAllowed`
bound to R2 and the owner's contract by identity. The installed state is exactly
the state returned by `AcceptedSubmission`; it changes only after validation.

### Witness C2 — incorrect repair is blocked again

Starting from an independent equivalent baseline:

```text
REDUCE_OBSERVED_RATE_BY_ONE_THIRD → R3 = fixture-request-003, proposed rate 200
→ fresh request identity
→ incorrect semantic repair
→ structurally valid proposal
→ normal fixture submission boundary
→ fresh semantic validation BLOCK
→ exact initial accepted-state object retained at 100
```

C1 and C2 are separate witnesses. They are not a retry-until-correct loop.
A negative repair that raises before fixture semantic validation does not
satisfy C2. C1 and C2 use equivalent authoritative state and contract baselines;
C2 must not depend on C1 having changed the configuration.
The new rejection is distinct from R1's evidence and retains R3 and the contract
by identity, with typed operands 200 and 120. The paired witnesses establish
`agent correction != semantic truth` within this model.

### Same evidence, different policy

`test_same_live_evidence_supports_different_proposal_policies` supplies the same
exact live blocked result and retained R1 to both policies, with distinct new
IDs. It observes proposed rates 120 and 200 without any additional validation,
submission, or accepted-state mutation. Together with C1/C2 this establishes
`validation evidence != repair policy`; governance evaluates each revised
intent independently.

### Operand, identity, and refusal evidence

The focused tests also establish:

- real rejection of 150 under maximum 80 leads the maximum policy to propose
  80, retaining caller-supplied ID spelling;
- exact integer reduction for non-divisible and large rates, including a
  canonical zero output without adding a positive-rate constraint;
- TypeError for accepted results, standalone ALLOW, raw rejection evidence,
  exception objects, arbitrary objects/dataclasses, unsupported subclasses,
  and malformed top-level policy/identity/proposal types;
- ValueError for value-equal reconstructed original proposals, reused or blank
  request IDs, and type-correct but incoherent manually constructed rejections;
- output contains only the four existing proposal fields and remains immutable.

Manually constructed incoherent carriers appear only in negative coherence
tests. They do not establish an observed governed rejection or authenticate
any coherent manually constructed carrier.

### Executed validation and proof limits

From the repository root, using the verified repository-local interpreter:

```bash
PYTHONDONTWRITEBYTECODE=1 \
./.venv/bin/python -m pytest \
-p no:cacheprovider \
tests/experiments/validation_blocked_semantic_replanning \
-q
```

Result: **52 passed in 0.06s**. This includes the unchanged
[Commit 3 fixture tests](../../tests/experiments/validation_blocked_semantic_replanning/test_fixture.py)
and Commit 4 replanning witnesses. Test-local observers delegate to the real
submission and validation functions: each branch records one call for R1,
zero during planning, and one fresh call for the explicit revised submission.

No unrestricted integration suite, Docker, PostgreSQL, migration, or dependency
operation was run for this closeout. There is no claim of automatic Agent
repair, optimal configuration, authenticated/durable provenance, globally
unique request identity, production/PostgreSQL semantic replanning, LLM safety,
a real rate limiter, eventual correction, or retry semantics.

## Level 2 production witnesses — retained stronger proof obligation

The original production witnesses remain unproven:

| Witness | Original PR0 production obligation |
|---|---|
| A | An ordinary public-writer request reaches genuine FullProof `VALIDATION_BLOCKED`, with no accepted event or idempotency record for that request. |
| B | Exact live `PostgresWriteSideResult`, bounded typed evidence, and caller-retained identity inform a proposal without writes. |
| C1 | Meaningfully changed intent and fresh request identity enter the normal production writer, receive fresh validation ALLOW, pass append admission, and commit an accepted effect. |
| C2 | An independent equivalent baseline receives an invalid revised intent with fresh identity; it reaches genuine semantic BLOCK and produces no accepted effect. |

Level 1 cannot discharge these obligations. A future non-Order production
consumer would require an explicitly reviewed update identifying its actual
proposal, validator, result, and effect owners. It must not reuse the name
FullProof for a different producer, fabricate `PostgresWriteSideResult`, or
modify completed Order responsibilities to satisfy the old example.

## Falsification and invalid shortcuts

Neither proof level is established by:

- substituting a structural/domain exception for semantic rejection;
- fabricating BLOCK instead of evaluating the proposal against the constraint;
- corrupting context while claiming independently obtained authority;
- parsing repair values from `reason`;
- silently promoting open metadata to stable machine policy;
- changing only sequence, proof, or candidate ID while claiming changed intent;
- letting the planner write directly;
- bypassing the applicable normal submission or semantic validation boundary;
- using Stage 4E to mutate a request;
- replacing governed acceptance with a direct state write or event-store append;
- showing only the successful repair; or
- using an invalid repair that fails before semantic validation.

An experiment-owned validator genuinely evaluating its declared fixture
constraint is a Level 1 producer. It is not an alternate test runtime allowed
to fabricate an existing production block. Relabeling its result as current
FullProof `VALIDATION_BLOCKED` would invalidate a Level 2 claim.

Fault injection can establish a narrower propagation or robustness claim. It
must remain labeled as such and must not stand in for the research question.

## Level 1 gate closeout and retained production gate

### Level 1 fixture gate — established by Commit 3

Commit 3 established the permitted action/target, exact integer fixture units,
independent maximum constraint, immutable proposal/state/evidence, and sole
submission-state owner. Its tests establish structurally valid input reaching
both semantic ALLOW and semantic BLOCK. Commit 4 leaves the fixture and those
tests unchanged; the focused run confirms their continued behavior.

### Level 1 planner gate — witnessed by Commit 4

The reviewed Commit 4 design followed the fixture. Executable evidence now
satisfies the bounded planner gate:

1. The blocked rate is revised from 300 to 120 or 200, changing actual intent.
2. Exact live typed evidence and retained request identity supply sufficient
   bounded machine input, without reason parsing or metadata-based policy.
3. Planning performs no writes, submission, or validation.
4. A revised intent receives fresh request identity and the full fixture
   governance path, including fresh validation.
5. Valid and invalid revisions reach semantic validation from independent
   equivalent baselines, producing acceptance and another block respectively.

```text
LEVEL 1 COMPLETE
!= production integration authorization
```

### Level 2 production gate

The original PR0 gate required a legitimate ordinary production path reaching
genuine FullProof `VALIDATION_BLOCKED`, a meaningfully repairable condition,
sufficient bounded machine-readable evidence, no text parsing, a fresh request
through normal governance, and honest positive/negative validation witnesses.
Its rule was `PR0 merge != authorization to implement PR1`.

Level 1 closeout remains separate; it does not declare that original
production gate satisfied. Production integration remains NOT AUTHORIZED.
Reopening it requires a real production consumer and separately reviewed
proposal surface, semantic validator/evidence, state/effect owner, and real
PostgreSQL integration. Any change from the original FullProof-specific proof
must be explicit. Research motivation and Level 1 success alone do not justify
production promotion, a generic candidate API, or changes to Order.

## Commit sequence on the existing experiment branch

The experiment continues on `experiment/validation-blocked-semantic-replanning`
with multiple commits. Numbered PR0/PR1 child branches are not required. This
sequence refines the original PR0/PR1/PR2 plan preserved in Commit 1.

### Commit 1 — complete

`docs: define semantic replanning experiment boundary` (`0fe0cd5`).

Documentation-only PR0 established the source audit, partial production
evidence sufficiency, reachability limitation, and original implementation
gate. It did not implement a planner or production witness.

### Commit 2 — complete

`docs: select experiment-owned Agent proposal boundary` (`6d20709`).

This documentation-only refinement selected Level 1, froze Order, preserved
Level 2 limits, and placed fixture establishment before planner work.

### Commit 3 — complete

`experiment: establish governed operational configuration fixture` (`a335e1a`).

Established [model.py](model.py) and its fixture tests without a planner.
Semantic ALLOW can precede the exact governed state transition; semantic BLOCK
retains exact typed evidence with zero accepted-state change. This remains an
in-memory model without production integration or request memory.

### Commit 4 — Level 1 executable closeout

`experiment: demonstrate deterministic semantic replanning`.

Added [planner.py](planner.py) and
[test_replanning.py](../../tests/experiments/validation_blocked_semantic_replanning/test_replanning.py),
then updated this README after the focused witnesses passed. The existing
proposal type carries the revised intent; no wrapper or executor was added.
A/B/C1/C2 establish no planning writes, exact live custody, changed intent and
request identity, fresh validation, and independent valid/invalid revisions.

The paired witnesses support only the model-level closeout:
`agent correction != semantic truth` and `validation evidence != repair policy`.
No production planner contract, retry loop, or automatic promotion to Level 2
follows. No extra numbered closeout commit is needed merely for symmetry.

If a real production consumer later justifies Level 2, its production
responsibility must receive separate review and may require a separate
production branch/PR. It must not be inserted incidentally into this experiment.

## Explicit non-goals

The first version does not introduce:

- LLM;
- modifications to the completed Order domain, its checks, or correctness rules;
- an artificial Order policy or fake amount ceiling;
- Agent control over sequence, proof, internal event identity, or version fields;
- a production configuration subsystem or new production domain;
- a real traffic controller or real rate limiter;
- a multi-agent consensus implementation;
- a generic candidate-submission API;
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
- Stage 4E changes or reuse of same-request authority for changed intent;
- new Quotient Model version;
- generic autonomous agent framework;
- new production business rule invented solely for the experiment; or
- production `RepairProposal` without a production consumer.

The selected fixture constraint is explicitly experiment-owned. It is not a
new production business rule or an amendment to Order correctness.

Commit 4 changes only the new experiment-local planner, its new test module,
and this README closeout. It changes no Commit 3 model or fixture test,
production source, migrations, dependencies, environment configuration,
Stage 4E, DecisionReceipt, SemanticOutcome, Stage 4C, Order aggregate,
correctness contract, FullProof validator, production validation evidence,
RequestSignature, idempotency behavior, previous experiment, roadmap, or ADR.
