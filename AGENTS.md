# AGENTS.md — Streaming System + Compass

## Repository boundary

* Work only inside the current Streaming System + Compass repository.
* Treat the Git repository root returned by `git rev-parse --show-toplevel` as the project workspace and default writable root.
* Do not access, inspect, or modify sibling repositories or unrelated directories unless the current task explicitly requires and authorizes it.
* Before doing any work, confirm:

  * the current working directory
  * the Git repository root
  * the current branch
  * the working-tree status
* If the current directory is not inside the expected repository, stop and report the mismatch.

## Project posture

This repository is a high-assurance streaming-system and semantic-governance project.

* Existing domain terms, authority boundaries, state-transition rules, validation vocabulary, and naming choices are deliberate design decisions.
* Do not treat established terminology as casual wording that may be freely normalized or replaced.
* Technical success is not equivalent to semantic correctness.
* Candidate evidence is not automatically accepted history.
* Projection state is not automatically authoritative state.
* Snapshot state is derived evidence, not accepted authority.
* Operational diagnosis, semantic outcome, governance evidence, runtime decision, retry policy, execution strategy, and action execution are separate concerns unless the repository explicitly states otherwise.
* The user retains final semantic and architectural authority.

When documents disagree, do not silently reconcile them. Identify the disagreement, cite the relevant repository-relative paths, and request review.

## Default operating mode

* Default to inspection, explanation, and proposal.
* Do not modify files unless the current task explicitly authorizes a defined edit scope.
* Plan before editing.
* Before an authorized edit, state:

  * the exact files expected to change
  * the purpose of each change
  * any important non-goals
* Prefer small, reviewable changes.
* Do not perform opportunistic cleanup, broad reformatting, naming normalization, or unrelated fixes.
* Do not implement code merely because a document describes possible future work.
* Do not convert exploratory notes into authoritative decisions.
* Do not broaden a task from documentation into production behavior, or from tests into production policy, without explicit authorization.

## Protected existing work

The repository may contain intentional uncommitted work.

* Record the initial `git status --short --branch` before inspection or edits.
* Treat every pre-existing modified or untracked file as protected.
* Do not edit, format, rename, move, delete, restore, stage, or otherwise alter protected existing work unless the current task explicitly identifies the file and authorizes the action.
* Files explicitly identified by the current task as authorized existing work may be inspected or edited only within the stated scope.
* Do not treat authorized existing work as accidental contamination.
* Compare the final Git status with the initial status.
* Stop and report any unexpected change.

## Production-code clarity

When production-code changes are authorized:

* Provide complete docstrings for public production functions, methods, and classes.
* Document, where relevant:

  * responsibility
  * inputs
  * outputs
  * important invariants
  * failure behavior
  * transaction or concurrency ownership
  * explicit non-goals
* Add explanatory comments around non-obvious:

  * transaction behavior
  * concurrency control
  * authority boundaries
  * evidence preservation
  * serialization contracts
  * failure-state handling
* Do not add comments that merely restate syntax.
* Tests should use comments only where they clarify non-obvious setup, concurrency schedules, failure injection, or evidence expectations.
* Preserve the distinction among:

  * physical database behavior
  * technical evidence
  * semantic interpretation
  * policy or retry authorization

## Python environment

The expected repository-local Python virtual environment is:

```text id="hcu8nk"
.venv
```

Rules:

* Resolve commands from the repository root.
* Do not rely on an inherited or previously activated shell environment.
* For Python commands, use the repository-local interpreter explicitly:

```text id="yyfmfb"
./.venv/bin/python
```

Run pytest through the same interpreter:

```bash id="x7mtzk"
./.venv/bin/python -m pytest
```

Before Python-based validation, verify:

```bash id="jw2b72"
./.venv/bin/python -c "import sys; print(sys.executable)"
```

Confirm that the resolved interpreter is located under the current repository's `.venv` directory.

Do not use the system Python, Homebrew Python, pyenv Python, or another project's virtual environment.

Do not create, delete, rebuild, relocate, or modify `.venv`.

Do not inspect or modify `.venv` contents except as needed to verify the interpreter or investigate an explicitly authorized dependency issue.

Do not run `pip install`, `pip uninstall`, dependency upgrades, or lock-file updates unless the current task explicitly authorizes the exact action.

If `.venv` is missing, invalid, or lacks a required tool, stop and report the problem rather than creating or repairing the environment.

## Git and repository safety

Read-only Git commands may be used when relevant, including:

```text id="kykdck"
git status
git diff
git diff --check
git branch --show-current
git rev-parse --show-toplevel
git ls-files
narrowly scoped git log
```

By default, do not perform Git mutations.

The following require explicit authorization in the current task:

* staging or committing
* pushing, pulling, or fetching
* creating, deleting, or switching branches
* merging, rebasing, cherry-picking, or reverting
* creating or deleting tags
* stashing changes
* modifying remotes

Never use destructive operations such as:

* force-push
* broad reset
* broad restore
* repository-wide cleaning
* deleting untracked files without exact review

A destructive operation is permitted only when the current task:

* names the exact operation
* identifies the affected scope
* explains why it is necessary
* explicitly authorizes it

Do not amend existing commits unless explicitly requested.

Do not use broad staging commands when unrelated or protected files exist.

Prefer exact paths.

## Commands, dependencies, and external access

Do not install, remove, or upgrade dependencies unless the current task explicitly authorizes the exact action.

Do not run package managers merely to inspect the repository.

Do not use network access, remote services, external APIs, cloud environments, or deployment systems unless the current task explicitly authorizes the exact use.

Do not deploy anything without explicit authorization.

Do not start databases, containers, background workers, or long-running services for a documentation-only task.

Do not execute repository scripts merely to infer what they might do.

Prefer non-mutating inspection commands.

When a task authorizes PostgreSQL access, distinguish:

* read-only inspection
* test-database mutation
* migration application
* persistent environment changes

Do not infer authorization for one category from authorization for another.

## Secrets and sensitive files

Do not read untracked or secret-bearing `.env` files, credential files, tokens, private keys, local database contents, or secret-manager configuration.

Tracked example files such as `.env.example` may be inspected when relevant, but they are documentation and must not be treated as proof of live credentials.

Do not print or copy secrets into output.

Do not inspect ignored files unless the current task explicitly identifies a safe file.

Stop and ask before opening a file whose sensitivity is unclear.

## Documentation authority

Documentation categories have complementary responsibilities rather than one universal hierarchy.

When claims conflict, use the following guidance:

* Current source, executable tests, and migrations govern implemented behavior.
* Accepted ADRs govern accepted architectural decisions and rationale.
* Explicitly current boundary notes govern responsibility and ownership boundaries.
* Current stage closeouts govern stage completion and declared non-goals.
* Implementation notes preserve stage- and PR-specific design, implementation, validation, and chronology.
* Postmortems preserve reconstructable engineering, architectural, learning, or preventive episodes.
* Reasoning notes preserve non-authoritative derivation and inference paths.
* Research, philosophy, overview, and navigation retain their narrower exploratory, methodological, orientational, or navigational roles.

Do not silently rewrite a historical document merely because a later source or decision supersedes part of it.

Prefer a short current-status or authority banner when clarification is authorized.

## Documentation-editing rules

When an edit is explicitly authorized:

* Preserve the repository's existing Markdown style.
* Use repository-relative paths.
* Verify that every linked or referenced file exists.
* Avoid duplicating complete document content inside an index.
* Summarize relevance rather than rewriting the underlying document.
* Keep inferred commentary visibly separate from established repository claims.
* Do not alter historical records to make current terminology appear retroactive.
* Do not mark a document as accepted, authoritative, superseded, obsolete, or implemented without repository evidence.
* Keep public conceptual notes separate from implementation contracts.
* Keep current guarantees separate from candidate mechanisms and future work.

## Documentation navigation and indexing

For documentation-navigation, taxonomy, or indexing tasks:

* Existing folders classify documents primarily by document type, purpose, or development context.
* Cross-topic indexes are a separate navigation layer and may reference documents across multiple folders.
* Treat the relationship between topics and documents as many-to-many.
* An index is navigational metadata, not a source of architectural authority.
* Do not classify a document from its filename alone.
* Read enough of each document to support its classification.
* Preserve exact project terminology and capitalization.
* Distinguish:

  * explicit repository statements
  * reasonable indexing inferences
  * unresolved or ambiguous classifications
* Mark uncertain classifications as `Needs review`.
* Do not invent a canonical topic taxonomy and present it as an existing Compass design.
* Do not hide contradictions or duplicated concepts. Surface them for review.
* Do not move, rename, delete, or rewrite source documents merely to make an index cleaner unless the current task separately authorizes those changes.

A topic-index entry should normally identify:

* the document path
* the document role
* why the document belongs to the topic
* its reading level or relevance
* any uncertainty, historical status, or current-authority qualification

## Safe workflow for broad documentation audits

For broad documentation-taxonomy, navigation, or indexing tasks, use the following workflow unless the current task defines a narrower process:

1. Confirm workspace, Git root, branch, working-tree status, active instructions, and Python interpreter when Python validation is relevant.
2. Inspect the directory and file inventory without modifying anything.
3. Reconstruct the current documentation categories from their README files and actual contents.
4. Propose classifications or navigation changes before editing.
5. Report ambiguous, contradictory, duplicated, or potentially outdated documents.
6. Obtain explicit approval for moves, renames, category creation, or broad index changes.
7. Modify only the authorized files.
8. Validate referenced paths and inspect the final diff.

For a large documentation set, work in bounded batches.

Do not claim the entire repository was reviewed unless all relevant files were actually read.

## Pull-request description style

Use the PR-description style that matches the change type.

For PRs containing production code, tests, migrations, schemas, runtime configuration, or behavioral changes:

* use a checklist-oriented description
* make implemented and deferred deliverables visible
* include validation and test completion items
* distinguish completed behavior from follow-up hardening

For documentation-only PRs:

use a narrative structure such as:

```text id="nwxylh"
Purpose;
Scope;
major documentation changes;
authority or ownership changes;
Validation;
Non-goals;
Follow-up.
```

A checklist is optional and should not be added merely for stylistic uniformity.

Do not rewrite historical PR descriptions solely to normalize formatting.

## Validation and completion reports

Use validation proportional to the authorized scope.

For documentation-only changes, relevant checks may include:

* verify the authorized file list
* verify referenced paths exist
* check relative Markdown links
* run `git diff --check`
* inspect the scoped diff
* confirm protected files were not changed
* report unresolved classifications or contradictions

For code or database changes, use the repository's relevant unit, integration, schema, permission, concurrency, and type checks as authorized by the task.

At completion, report:

* what was inspected
* what changed
* the exact files changed
* validation performed
* unresolved questions or contradictions
* anything not inspected or not completed
* final Git status
* whether anything was staged or committed

Do not claim success beyond the evidence collected.

## Stop conditions

Stop and request guidance when:

* the requested scope is ambiguous
* required changes exceed the explicitly authorized scope
* a classification depends on resolving an architectural contradiction
* an existing document appears stale but is not explicitly superseded
* moving, deleting, or renaming files is necessary but was not explicitly authorized
* unexpected working-tree changes are present
* repository boundaries or active instructions are unclear
* a command would require unapproved network access, credentials, elevated permissions, or destructive behavior
* a production change would require inventing semantic vocabulary, authority, retry behavior, or operational policy not already approved
* evidence is insufficient to distinguish current behavior from a reasonable inference
