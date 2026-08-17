# Postmortem: From Local Environment Capability to Declared CI Dependency

*Why a Stage 4B.5 performance experiment passed in a Git worktree but failed twice in clean CI, and why the worktree itself was not the root cause.*

[← Back to Postmortems Index](README.md)

**Recorded on:** 2026-08-15

**Document role:** Historical engineering postmortem. The current CI workflow
owns present configuration; this note preserves the incident, correction, and
transferable dependency-classification lesson.

## Summary

During the final Stage 4B.5 performance-characterization work, the same change
passed local validation but failed CI twice for two different reasons.

Both failures initially appeared related to the use of a Git worktree.

That interpretation was incomplete.

The worktree itself was not defective, and previous worktree-based development
had not caused CI failures. The important difference was that this performance
experiment depended on environment capabilities that ordinary repository tests
had never required.

The local Stage 4B.5 worktree implicitly had access to:

```text
the main repository's complete Git object/history database
+
the main repository's existing Python virtual environment
```

The clean GitHub Actions runner did not provide those capabilities by default.

The two CI failures were:

```text
Failure A
historical Git blobs required by the benchmark were absent from a shallow CI
checkout

Failure B
the benchmark treated execution inside a Python virtual environment as a
canonical-evidence requirement even though hosted CI Python was otherwise valid
```

The corrections were intentionally different.

For the first failure, historical Git access was a real experiment dependency,
so CI was changed to fetch complete history.

For the second failure, virtual-environment identity was not a correctness
property of the experiment, so that requirement was removed rather than forcing
CI to imitate the local workstation.

The broader lesson is:

> Local environment capability is not the same thing as a declared test
> dependency.

A rich local development environment can silently satisfy requirements that a
clean CI environment does not know exist.

The purpose of CI is not to reproduce every incidental property of the local
machine. It is to expose which properties are truly required, which must be
declared explicitly, and which should not have been requirements at all.

---

## 1. The Trigger

Stage 4B.5 introduced a performance-characterization surface comparing multiple
runtime shapes.

Conceptually:

```text
A = historical Stage 4B.2 behavior
B = current Stage 4B.5 behavior
C = B plus semantic composition
```

The comparison was not implemented by maintaining a duplicated copy of the old
Stage 4B.2 source inside the current tree.

Instead, the experiment reconstructed historical source from pinned Git
history.

This created a new kind of repository dependency:

```text
current checkout contents
+
historical repository objects
```

Ordinary unit and integration tests had mostly depended on the first category.

The performance experiment depended on both.

At the same time, the Stage 4B.5 worktree had no independent `.venv` and used
the existing Python environment from the main repository.

Locally, both requirements appeared naturally satisfied.

CI exposed that neither assumption had been classified explicitly.

---

## 2. Why the Worktree Looked Suspicious

The two failures happened during worktree-based development, and both appeared
only near the final performance-analysis portion of Stage 4B.5.

That correlation made the following explanation tempting:

```text
worktree
→ unusual repository layout
→ CI failure
```

But a Git worktree is not an independent shallow clone.

The local topology was closer to:

```text
main Git repository
├── shared object database and history
├── main working tree
├── Stage 4B.5 worktree
└── other worktrees
```

The Stage 4B.5 worktree therefore had access to historical Git objects already
present in the main repository.

It could also invoke the main repository's existing Python virtual environment.

The worktree did not create the invalid assumptions.

It made those assumptions easy to satisfy locally.

The more accurate relationship was:

```text
rich local worktree environment
→ implicit dependency remains invisible
→ local validation passes
→ clean CI removes implicit capability
→ undeclared assumption becomes observable
```

The worktree was a masking condition, not the root cause.

---

## 3. Failure A — Historical Git Objects Were Missing in CI

The first failure came from the historical comparison surface.

The benchmark required a pinned historical source artifact from an earlier
commit.

Locally, this worked because the repository already contained the required
object.

The effective local assumption was:

```text
if a historical commit is addressable from this repository,
the benchmark may treat its blobs as available input
```

That assumption was true on the long-lived local clone.

It was not true on the default clean CI checkout.

The original CI checkout was shallow.

Conceptually:

```text
local repository

HEAD
│
├── recent commits
├── Stage 4B.5 history
├── Stage 4B.2 history
└── older Git objects
```

versus:

```text
clean CI checkout

HEAD
└── only the fetched shallow boundary
```

When the benchmark requested a pinned historical blob, the CI repository simply
did not contain the object.

This was not a benchmark logic failure.

It was a missing declared data dependency.

---

## 4. Why Failure A Required a CI Change

The historical source was not incidental.

It was part of the experiment definition.

Without the historical Git object, the A/B/C comparison was incomplete.

Therefore the correct response was not to weaken the benchmark or silently
substitute current source.

The experiment required:

```text
pinned historical source identity
+
retrievable historical Git object
```

CI therefore had to satisfy that real requirement.

The checkout configuration was changed from shallow history to complete history:

```yaml
fetch-depth: 0
```

The important distinction is:

```text
historical Git access
= required experiment input
```

This was a legitimate environment dependency that needed to be made explicit.

---

## 5. Failure B — Virtualenv Identity Was Mistaken for Evidence Validity

After historical Git access was corrected, CI failed again.

The second failure came from a different assumption.

The canonical performance runner required the interpreter to report that it was
running inside a Python virtual environment.

Conceptually, the precondition was:

```text
working tree is clean
+
Python is running inside a virtual environment
```

Locally this passed because the Stage 4B.5 worktree used the main repository's
`.venv`.

The CI runner used a hosted Python toolchain that could:

```text
import the project
install the required dependencies
run pytest
execute the performance harness
```

but it did not satisfy the specific virtual-environment identity check.

The experiment therefore rejected an otherwise valid execution environment.

This exposed a different category of error:

```text
local development convention
was encoded as
experiment correctness requirement
```

Those are not equivalent.

---

## 6. Why Failure B Required Removing a Constraint

There were two possible responses.

The first would have been to make CI create a virtual environment solely to
satisfy the benchmark check.

That would have made CI resemble the local machine more closely.

But it would not have answered the important question:

> Does the experiment require a virtual environment in order for its evidence
> to be valid?

The answer was no.

The benchmark required controlled source, dependencies, execution procedure,
database conditions where applicable, and a clean repository state.

It did not require a specific relationship between:

```text
sys.prefix
and
sys.base_prefix
```

Virtualenv identity was therefore not evidence.

It was an incidental local execution detail.

The correct repair was:

```text
remove the unnecessary virtualenv precondition
```

and explicitly test that the canonical runner accepts a valid hosted Python
toolchain.

This avoided turning a workstation convention into an artificial CI contract.

---

## 7. Two Failures, One Higher-Level Root Cause

The two CI failures should not be collapsed into one implementation bug.

They had different immediate causes.

| Failure | Immediate cause | Classification | Correct response |
|---|---|---|---|
| Historical source unavailable | shallow CI checkout did not contain pinned historical Git objects | real experiment dependency was undeclared in CI | fetch required history |
| Hosted Python rejected | canonical runner required virtualenv identity | incidental local property was mistaken for correctness | remove the requirement |

However, they share one higher-level root cause:

```text
the performance tooling was not yet environment-portable
because local capabilities had not been separated into:

A. required experiment dependencies
B. optional development conveniences
```

The local environment satisfied both classes automatically.

CI forced the distinction.

---

## 8. The Composition Error

No individual mechanism was obviously wrong.

The local design combined:

```text
Git worktree
+
shared long-lived repository history
+
main-repository virtualenv reuse
+
performance harness with historical-source reconstruction
+
canonical environment preconditions
```

Each component had a reasonable purpose.

The failure existed in their composition.

### Worktree

Provided an isolated filesystem checkout while sharing Git repository metadata
and objects.

### Long-lived local clone

Already contained historical commits required by the benchmark.

### Shared virtualenv

Allowed the worktree to execute without creating or repairing its own
environment.

### Historical benchmark

Correctly required an earlier implementation for comparison.

### Canonical preconditions

Attempted to protect evidence quality, but included one condition stronger than
the evidence actually required.

Together they produced two false implications:

```text
historical object is available locally
=
historical object is part of the declared CI checkout contract
```

and:

```text
benchmark runs through local .venv
=
virtualenv identity is required for benchmark validity
```

Neither implication was justified.

---

## 9. Why Previous Worktree Development Did Not Fail

The repository had used worktrees before without similar CI failures.

That is important evidence against treating worktree usage itself as the defect.

Most earlier tests followed a simpler dependency shape:

```text
current checkout
→ import current production source
→ execute unit/integration behavior
→ assert current invariant
```

A shallow checkout was sufficient because old repository objects were not test
inputs.

Likewise, the interpreter only needed to be capable of running the project.
Whether it was technically inside a virtual environment was rarely part of the
semantic test oracle.

The Stage 4B.5 performance experiment changed both conditions.

It introduced:

```text
historical repository state
as experiment input
```

and attempted to strengthen reproducibility with environment checks.

That new surface exposed assumptions that earlier worktree-based development
never exercised.

The relevant change was therefore not:

```text
worktree introduced
```

but:

```text
test dependency model became richer
```

---

## 10. Why Local Passing Tests Were Not Misleading

The local results were not false.

They demonstrated that the benchmark worked under the local environment that
was actually used.

What they did not prove was:

```text
the benchmark can reconstruct all required inputs
from a clean declared CI environment
```

This is the same distinction that appears elsewhere in the project:

```text
behavior works under one supplied environment
≠
all required preconditions have been made explicit
```

The local run validated implementation behavior.

The CI run validated environment portability.

Both were useful evidence.

Neither should be interpreted as replacing the other.

---

## 11. The Evidence-Level Change

The two failures improved the experiment contract.

Before CI:

```text
historical source works because local Git history happens to exist

canonical runner works because local Python happens to be a venv
```

After CI:

```text
historical source works because complete Git history is an explicit CI input

canonical runner works because interpreter capability matters,
not virtualenv identity
```

The environment contract became narrower and more honest.

The resulting principle is:

```text
declare what the experiment actually needs
and remove what it merely happens to use locally
```

---

## 12. Why Reproducing the Entire Local Machine Would Be the Wrong Fix

A common reaction to local/CI mismatch is:

```text
make CI look exactly like local
```

That can hide the real design question.

For each mismatch, the correct first question is:

> Is this property part of the executable contract, or only part of my local
> setup?

For Stage 4B.5:

```text
full Git history
→ yes, because pinned historical source is benchmark input

virtualenv identity
→ no, because it does not determine benchmark correctness
```

If CI had simply recreated every local property, both failures could have been
made green without improving the experiment model.

The stronger repair classified each dependency before changing the environment.

---

## 13. Root Cause

The root cause is best stated at the environment-contract level.

> The Stage 4B.5 performance experiment depended on local environment
> capabilities that had not yet been classified as explicit benchmark
> dependencies versus incidental development conveniences.

The worktree contributed to the masking effect because it inherited capabilities
from the long-lived main repository.

It did not create the CI failures.

More specifically:

```text
Root cause
performance tooling lacked an explicit portable environment contract

Contributing condition
worktree shared a rich local Git repository and reused the main .venv

Manifestation A
historical Git dependency was real but undeclared in CI

Manifestation B
virtualenv identity was declared as required even though it was not semantically
necessary
```

---

## 14. Corrective Actions

### 14.1 Declare historical Git history as benchmark input

CI now fetches the repository history required for pinned historical-source
reconstruction.

The benchmark remains tied to exact historical identity rather than copying or
approximating an old implementation.

### 14.2 Remove virtualenv identity from canonical evidence requirements

The runner no longer treats "inside a virtualenv" as proof of evidence validity.

A valid hosted Python toolchain is acceptable when the actual benchmark
dependencies and preconditions are satisfied.

### 14.3 Preserve clean-working-tree validation

Repository cleanliness remains meaningful because uncommitted source drift could
invalidate the relationship between the recorded run and the intended code
identity.

This is different from virtualenv identity:

```text
clean source state
→ directly relevant to evidence provenance

virtualenv identity
→ not directly relevant to evidence provenance
```

### 14.4 Add explicit hosted-Python regression coverage

The tests now preserve the corrected portability contract so a future refactor
does not silently reintroduce the local-only assumption.

---

## 15. New Review Rule for Environment-Sensitive Tests

For every benchmark, characterization runner, or reproducibility harness, classify
each environment assumption.

Use four categories:

```text
A. Required semantic/input dependency
B. Required reproducibility/provenance dependency
C. Local convenience
D. Unsupported accidental dependency
```

Examples from this incident:

```text
pinned historical Git blob
→ A

clean working tree
→ B

reuse main repository .venv
→ C

must be running inside any virtualenv
→ D
```

Before adding a precondition, ask:

1. What failure in the evidence occurs if this condition is absent?
2. Does the condition protect source identity, input identity, execution
   determinism, or result interpretation?
3. Is the condition merely how the current developer machine is configured?
4. Can a clean CI runner satisfy the true requirement through a different
   mechanism?
5. If CI lacks the property, should CI acquire it, or should the requirement be
   removed?
6. Is the required external state reproducibly addressable?
7. Does the test depend on repository history beyond the current checkout?
8. Does the test depend on files or interpreters located outside the worktree?
9. Would a fresh clone behave differently from the long-lived local clone?
10. Is that difference intentional and documented?

---

## 16. New Worktree Review Rule

A worktree should be treated as:

```text
filesystem isolation
with shared repository capability
```

not as:

```text
fresh independent clone
```

Therefore, when a test passes in a worktree and depends on Git-level behavior,
ask:

```text
Which capability comes from the checked-out tree?

Which capability comes from the shared Git object database?

Which capability comes from the main repository environment?

Which of those would exist in a clean clone?
```

This is especially important for tooling that uses:

```text
git show
git cat-file
git rev-parse
historical commit identities
generated diffs against old revisions
repository-root-relative environment paths
shared .venv paths
```

A worktree can be completely correct while still being a poor simulation of a
fresh CI checkout.

---

## 17. Relationship to Stage 4B.5

This incident did not invalidate the Stage 4B.5 runtime-governance performance
analysis.

It improved the provenance of that analysis.

The experiment deliberately compares current behavior with historical behavior.

That makes source identity part of the evidence model.

The incident therefore reinforces a broader Stage 4 principle already present
throughout the repository:

```text
evidence must describe what actually happened
without silently importing stronger meaning from its environment
```

For this experiment:

```text
Git history
is evidence input

Python virtualenv identity
is not benchmark meaning
```

Keeping those two claims separate is consistent with the same semantic
discipline used elsewhere in Compass.

---

## 18. What This Incident Was Not

This was not:

- a Git worktree correctness defect;
- a production runtime defect;
- a Stage 4B.5 semantic-governance defect;
- evidence that worktrees should be avoided;
- evidence that CI must always use full Git history;
- evidence that virtual environments are unnecessary for local development;
- evidence that local performance results were invalid.

It was a portability and dependency-classification defect in the experiment
harness and its CI contract.

Only workflows that require historical repository objects should pay the cost of
fetching them.

Developers may continue using virtual environments locally without making
virtualenv identity part of the evidence contract.

---

## 19. Reusable Lesson

The incident can be reduced to one sequence:

```text
local environment contains extra capability
→ experiment begins relying on that capability
→ local tests remain green
→ clean CI removes the capability
→ hidden assumption becomes visible
→ classify the assumption
→ declare real dependencies
→ delete incidental dependencies
```

The most reusable principle is:

> Do not ask CI to imitate the local machine before deciding which parts of the
> local machine are actually required.

A clean CI failure is often not merely an environment problem.

It can be evidence that the executable contract has not yet distinguished
requirements from conveniences.

---

## 20. Final Rule

For future performance and characterization work:

```text
local capability
≠ declared dependency

declared dependency
≠ incidental environment convention

clean CI
= independent evidence that the distinction is real
```

When a local-only assumption is exposed, the repair must first answer:

```text
Does correctness require this?
```

If yes:

```text
declare and provision it explicitly
```

If no:

```text
remove it from the executable contract
```

That distinction is the actual correction preserved by this postmortem.
