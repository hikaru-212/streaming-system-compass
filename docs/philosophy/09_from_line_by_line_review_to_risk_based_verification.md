# From Line-by-Line Review to Risk-Based Verification

## Status

Design-philosophy / development-methodology note.

This document records how human review intensity changes with semantic authority,
blast radius, architectural maturity, and the strength of executable evidence.
It does not define runtime behavior, correctness-contract authority, or an ADR.

## How My AI-Assisted Development Workflow Changed as the Architecture Stabilized

Early in this project, I treated almost every meaningful pull request as
something I had to inspect deeply.

I read the production code.
I read the tests.
I questioned individual fields.
I tried to construct counterexamples by hand.
If a model looked correct, I still asked what invalid state it could represent.

That level of attention was useful because the project was still defining its
semantic foundations.

Later, my behavior changed.

By the time I reached rule-evidence propagation and write-side integration, I
was no longer willing to read every test with the same intensity. I cared much
more about whether the important invariants were represented, whether the
failure boundaries were adversarially tested, whether the full regression suite
remained green, and whether the change stayed inside a bounded architectural
scope.

At first, that felt like I might simply be becoming less careful.

I now think the more useful explanation is different:

```text
the architecture stabilized
→ the location of risk changed
→ my review strategy changed with it
```

The important question is not whether every pull request receives the same
amount of human attention.

The important question is:

```text
Where can one wrong assumption contaminate everything downstream?
```

That is where deep review belongs.

---

## 1. The Early Phase: Representation Errors Have Large Blast Radius

A good example came from the Order Correctness Contract.

The first typed representation looked reasonable.

It had typed identifiers.
It had typed propositions.
It had typed categories.
It had typed subjects.
The dataclass could be immutable.
The approved canonical objects could all pass tests.

But there was a deeper problem.

The representation still allowed something conceptually like:

```text
RuleId
× Proposition
× Category
× Subject
```

Every field could be individually valid while the resulting combination was
semantically meaningless.

The tests could prove:

```text
these chosen valid examples are correct
```

without proving:

```text
invalid combinations cannot be represented
```

That was not a small implementation bug.

It was an upstream representation problem.

If accepted, it could contaminate:

```text
contract construction
→ runtime evidence
→ semantic mapping
→ future machine consumers
→ retry governance
```

The correct response was not simply to add more happy-path tests.

The representation itself had to change.

The contract became identity-driven:

```text
rule_id
→ {proposition, category, subject}

transition_rule_id
→ transition relationship

amount_rule_id
→ amount relationship

(contract_id, version)
→ complete contract edition
```

At that stage, deep human review was high leverage.

The key work was not reading every assertion.

It was finding the wrong state space.

---

## 2. Green Tests Mean More After the State Space Is Constrained

A green suite does not automatically prove correctness.

That remains true.

But the meaning of a green suite changes when several conditions already hold:

```text
upstream semantic contract is stable

representation has explicit invariants

public construction paths exclude known illegal states

the current PR has narrow ownership

high-value failure boundaries have focused adversarial tests

the full regression surface remains green
```

Under those conditions, a green suite becomes much stronger evidence than it was
during the initial semantic-design phase.

The difference is not the color of the test output.

The difference is the architecture around it.

Consider two situations.

### Situation A — Defining the semantic model

A PR changes:

```text
correctness contract
rule vocabulary
field dependencies
authority boundaries
```

If the model is wrong, every downstream consumer may become wrong in a
consistent way.

The tests can all be green while testing the wrong model.

This deserves deep human inspection.

### Situation B — Propagating an already accepted semantic artifact

A later PR changes:

```text
runtime carrier
write-side propagation
optional evidence delivery
```

The upstream rule vocabulary is unchanged.
The validator mappings are unchanged.
The contract authority is unchanged.
The semantic meaning is unchanged.

The important questions are now different:

```text
Was validation executed exactly once?

Was evidence lost?

Was evidence reconstructed?

Can evidence from invocation A be attached to result B?

Does OFF fabricate evidence?

Can a post-validation outcome erase an observation that already happened?

Can a pre-validation return pretend validation happened?

Did legacy callers break?
```

These are bounded integration invariants.

They are much more amenable to adversarial tests and regression coverage.

---

## 3. The Review Strategy Became Risk-Based

I now think of the work in three broad review classes.

## Class 1 — Semantic and Representation PRs

Examples:

```text
correctness contract
stable rule vocabulary
identity relationships
contract version semantics
authority ownership
```

These receive the strongest human review.

I want to inspect:

- the production representation;
- the state space it permits;
- functional dependencies between fields;
- counterexamples;
- invalid Cartesian products;
- which object is authoritative;
- what future consumers will assume.

The main question is:

```text
If this assumption is wrong, how much of the future architecture becomes wrong?
```

This is where "the tests are green" is least persuasive by itself.

---

## Class 2 — Authority-Mapping PRs

Examples:

```text
validator failure branch
→ stable rule identity
```

The semantic model already exists, but an executable authority is being mapped
to it.

Human review should concentrate on the high-value mapping points:

```text
which producer owns this evidence?

which exact branches may emit which identities?

can PASSED carry a violation?

can FAILED omit the required evidence?

can one producer claim a rule outside its authority?

is identity reconstructed from text instead of emitted at the authority point?
```

I do not need to manually read every parametrized case once the universe and
allowed relation are clear.

The tests can exhaust the finite complement.

The human should verify that the universe and relation are the right ones.

---

## Class 3 — Propagation and Integration PRs

Examples:

```text
producer evidence
→ runtime
→ policy
→ PostgreSQL write side
→ trace / measurement delivery
```

Here the semantic contract is already frozen.

The review focus becomes:

```text
same invocation
compatibility
single execution
failure boundaries
absence versus not-evaluated
state leakage
wrapper consistency
```

For this class, I am much more willing to rely on:

```text
focused adversarial tests
+
full regression suite
+
source-scope review
```

That is not because integration code is unimportant.

It is because the highest-risk semantic decisions have already been constrained
upstream.

---

## 4. A Concrete Example: Same Candidate ID Is Not Same Invocation

The rule-evidence propagation work illustrates why targeted failure tests matter
more than reading every test line.

The system needed to preserve:

```text
ValidationResult
+
OrderRuleViolationEvidence
```

through one trusted invocation.

A weak implementation could say:

```text
validation_result.candidate_event_id
==
violation.candidate_event_id

therefore:
same invocation
```

That is false.

Two different invocations can evaluate the same candidate identity.

So the useful adversarial test is not another happy path.

It is:

```text
Invocation A
candidate_id = X

Invocation B
candidate_id = X

decision from B
+
evidence carrier from A
→ must be rejected
```

The implementation therefore preserves object identity through the supported
in-process path:

```text
decision.validation_result
is
producer.validation_result

write_result.validation_decision
is
runtime_carrier.decision
```

This does not provide cryptographic authenticity or cross-process provenance.

It provides a bounded construction guarantee for the actual production path.

That is exactly the level of claim the implementation can support.

---

## 5. Another Boundary: Evidence Must Follow What Actually Happened

The PostgreSQL write side has both PRE_TRANSACTION and IN_TRANSACTION validation
placements.

That creates a subtle evidence boundary.

In PRE_TRANSACTION, validation may occur before the authoritative idempotency
check.

So this sequence is possible:

```text
preliminary idempotency MISS
→ validation ALLOW
→ authoritative idempotency REPLAY
```

The final outcome is REPLAY.

But validation really happened.

Therefore the correct result is:

```text
REPLAY
+
preserved validation observation
```

It would be wrong to erase the evidence just because validation was not the
terminal outcome.

The opposite case exists too.

In IN_TRANSACTION, stream preparation may reject before validation.

Then:

```text
ADMISSION_REJECTED
+
no validation evidence
```

is correct because validation never occurred.

This gives a broader rule:

```text
validation happened
→ preserve the observation

validation never happened
→ do not fabricate the observation
```

This is the kind of invariant I care about reviewing directly.

I do not need to read every surrounding test once this boundary is explicitly
covered.

---

## 6. Full Regression Is a Blast-Radius Check, Not a Proof of Truth

When the combined runtime/write-side propagation work reached a green complete
suite, the important interpretation was not:

```text
all tests passed
→ the design must be correct
```

The stronger but narrower statement was:

```text
the new bounded guarantees were added

and

the repository's existing tested behavior did not observe a regression
```

That is a blast-radius statement.

It matters because additive architecture can still be destructive.

A new evidence field might change equality.
A new runtime API might break old validator doubles.
A new execution path might rerun validation.
A trace wrapper might copy a different result.
A measurement wrapper might execute a different algorithm.
An OFF path might accidentally become PASSED.

A full regression suite gives broad evidence against those classes of damage.

It becomes especially valuable when the production change is intentionally
small and the upstream semantics remain unchanged.

---

## 7. AI Changed What I Spend Human Attention On

AI can produce a large amount of code and tests quickly.

That makes line-by-line human review of everything increasingly expensive.

The wrong response would be:

```text
AI generated it
→ tests are green
→ accept everything
```

The more useful response is to move human attention to the places where it has
the highest leverage.

I increasingly want AI to do:

- repetitive implementation;
- finite-state enumeration;
- parametrized complement testing;
- regression execution;
- mechanical propagation checks;
- search across callers and test doubles;
- source-grounded compatibility audits.

I want human review to concentrate on:

- semantic authority;
- state-space definition;
- ownership;
- impossible-state design;
- failure boundaries;
- counterexamples;
- whether the tests are proving the right relation;
- whether a PR silently widened its responsibility.

This is not removing humans from the loop.

It is changing what the human loop protects.

---

## 8. The Warning Sign: When to Return to Deep Review

Risk-based review only works while the PR remains bounded.

If an integration PR suddenly needs to modify:

```text
correctness_contract.py
validators.py
SemanticOutcome
DecisionReceipt
write-side execution
OrderAggregate
```

at the same time, the review class has changed.

That is no longer mechanical propagation.

The blast radius has expanded across semantic layers.

At that point I should stop relying primarily on regression evidence and return
to deep source review.

A useful heuristic is:

```text
closer to semantic authority
→ stronger human review

farther downstream on a frozen contract
→ more reliance on adversarial tests + regression
```

Another useful warning sign is a new abstraction without a concrete consumer.

If a proposed API exists only because the roadmap predicted it, but no current
production caller needs it, the right action may be to stop or combine the PR.

That happened when the planned evidence-preserving runtime PR was audited.

The runtime seam was technically valid.

But by itself it had no production consumer.

The work was therefore combined with the PostgreSQL write-side propagation
boundary where the evidence was actually needed.

That made the abstraction concrete rather than speculative.

---

## 9. This Is Not Less Rigorous; It Moves Rigor Upstream

My workflow now looks less like:

```text
read every changed line
→ read every test
→ approve
```

and more like:

```text
identify review class
→ locate semantic authority
→ define the failure universe
→ inspect high-value invariants
→ let tests exhaust bounded state spaces
→ run broad regression
→ escalate review if scope crosses authority boundaries
```

The amount of manual reading may decrease.

The rigor does not have to decrease with it.

In fact, this can be more rigorous because the review is explicitly aligned with
risk.

The hardest bugs are often not syntax bugs.

They are incorrect models that remain internally consistent.

Those deserve deep attention.

Once the model is constrained and the authority boundaries are stable, the next
risk is often propagation correctness and compatibility.

Those deserve adversarial tests and broad regression.

Treating both situations identically is not necessarily more careful.

It can simply spend attention where it has less leverage.

---

## 10. The Development Model I Want to Keep

The workflow I want going forward is:

```text
1. Define the semantic boundary.

2. Ask what invalid states the representation still permits.

3. Harden the public construction path.

4. Establish executable-authority parity.

5. Add producer-owned evidence at the real authority point.

6. Propagate that evidence without reconstructing or reinterpreting it.

7. Test forbidden pairings, state leakage, absence semantics, and failure paths.

8. Run the complete regression surface to measure blast radius.

9. Increase human review again whenever a later change crosses semantic
   authority boundaries.

10. Treat green tests as bounded evidence, never as proof that the model itself
    is universally correct.
```

That is the main change in my development style.

I am not trying to inspect less because details no longer matter.

I am trying to distinguish between details that can cause a local defect and
assumptions that can corrupt the architecture beneath every future detail.

The second category deserves most of my attention.
