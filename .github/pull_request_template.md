## Purpose

Explain why this PR exists.

Describe the stage, boundary, or problem this PR addresses.

This section should answer:

- Why is this PR needed now?
- What project stage or issue does it support?
- What semantic / architectural boundary does it clarify or implement?

## Scope

List what this PR changes.

Use concrete bullets.

Examples:

- Add ...
- Rename ...
- Implement ...
- Document ...
- Align ...

## Non-goals

List what this PR intentionally does not do.

This is important for preventing scope creep.

Examples:

- No ...
- Does not ...
- This PR does not implement ...

## Design Notes / Boundary Notes

Explain important design decisions, naming rules, lifecycle rules, or trade-offs.

Use this section when the PR involves architecture meaning, not just code.

Examples:

- candidate_event_id vs accepted_event_id
- Python runtime behavior vs durable database evidence
- why this PR uses psycopg instead of ORM
- why UUIDv7 is deferred
- why metadata_json is only a container, not an implemented timing system

## Validation Plan

Explain how this PR should be verified.

Use bullets or checklist-style items.

Examples:

- Run `pytest`
- Verify migration creates expected tables
- Verify duplicate event sequence is rejected
- Verify Decimal round-trip
- Verify rejected candidates do not enter accepted history

## Checklist

Use checkboxes for concrete completion tracking.

Examples:

- [ ] Code changes completed
- [ ] Tests added or updated
- [ ] Docs updated
- [ ] Existing tests pass
- [ ] Non-goals remain out of scope

## Related Issues

Use closing keywords only if this PR fully resolves the issue.

Examples:

Closes #3

Or:

Related to #3