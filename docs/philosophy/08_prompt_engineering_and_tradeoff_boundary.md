# Prompt Engineering and the Trade-off Boundary

Why constrained generation does not replace architectural judgment.

---

## Purpose

This note records a boundary in AI-assisted engineering work:

```text
better prompt
≠
accepted design
```

Prompt engineering can improve the quality of candidate outputs.

It can narrow the model's response pattern, ask for stricter reasoning, surface invariants, discourage shallow implementation, and encourage more architecture-aware suggestions.

However, a prompt does not remove the need for project-specific judgment.

A strong AI-generated answer may still be mismatched with the current project stage, scale, risk budget, or implementation goal.

---

## Core Claim

Prompt engineering is locally useful.

It can make generated outputs more relevant, disciplined, and reviewable.

But it does not solve the trade-off problem.

The important distinction is:

```text
prompt-constrained candidate
≠
project-admitted design
```

A better prompt may produce a better candidate.

It does not make the candidate accepted.

---

## Why Prompts Help

A prompt gives the model additional constraints.

For example, asking for a senior system-architecture review may cause the output to emphasize:

- invariants
- preconditions
- failure boundaries
- side-effect isolation
- dependency direction
- testability
- operational risk
- maintainability

This is useful because the model is less likely to return a generic answer.

A good prompt can reduce the chance of shallow outputs such as:

- syntax-only fixes
- over-simplified helper extraction
- tests that only prove trivial behavior
- architecture changes made only for neatness
- green tests that do not prove the intended boundary

In that sense, prompt engineering can act as a soft boundary around the candidate-generation process.

---

## Why Prompts Are Not Enough

A prompt can guide generation.

It cannot fully decide architectural trade-offs.

A model may produce a technically sophisticated design that is still wrong for the current context.

Examples:

- the design may be correct for a larger scale than the current project needs
- the abstraction may be elegant but premature
- the testing strategy may be rigorous but misaligned with the current risk
- the implementation may use a mature enterprise pattern before the project has the runtime need for it
- the suggested feature may increase maintenance cost more than it increases correctness
- the proposal may optimize a path that is not currently the bottleneck

This is not simply a model-quality problem.

It is a trade-off problem.

Trade-offs require knowing what the project is currently trying to prove, what can be deferred, what is worth maintaining, and what would create unnecessary semantic or operational debt.

---

## Candidate Architecture vs Accepted Architecture

In AI-assisted development, generated architecture should be treated as a candidate.

```text
AI-generated design
→ candidate architecture
→ repository-specific review
→ accepted / rejected / deferred design
```

The model may generate strong material.

The human project owner still decides:

- whether the design belongs to the current stage
- whether the abstraction is justified
- whether the implementation cost is worth the benefit
- whether the proposed boundary matches the actual repository boundary
- whether the suggestion preserves the intended system semantics
- whether the idea should be implemented now, documented for later, or rejected

This preserves architectural ownership.

---

## Relationship to Compass

Compass treats candidate events as things that must be admitted before entering accepted history.

This philosophy note applies the same discipline to AI-assisted design work:

```text
candidate event
→ admission boundary
→ accepted history
```

and:

```text
candidate design
→ project-specific review
→ accepted architecture
```

The shared principle is:

```text
candidate output must not become system truth by default
```

A prompt can improve the candidate.

It does not replace admission.

---

## Relationship to AI Suggestions Are Candidate Actions

The note `AI Suggestions Are Candidate Actions` records why AI-generated explanations and designs must be checked against actual repository boundaries before becoming accepted documentation or implementation.

This note adds a narrower point:

```text
Even a well-prompted model can produce a strong but mis-scoped candidate.
```

Therefore, prompt engineering should be treated as a candidate-generation improvement, not as a correctness guarantee.

---

## Practical Rule

When using AI for architecture or code suggestions, ask:

1. Did the prompt produce a better candidate?
2. Does the candidate match the current project stage?
3. Does it solve a real boundary problem?
4. Does it introduce unnecessary maintenance cost?
5. Is this implementation needed now, or should it be deferred?
6. Does it preserve the repository's accepted design direction?

If the answer is uncertain, the design should remain a candidate.

---

## Summary

Prompt engineering is useful because it can improve candidate generation.

It is limited because it cannot replace project-specific trade-off judgment.

The Compass-style rule is:

```text
A better prompt may produce a better candidate.
It does not make the candidate accepted.
```
