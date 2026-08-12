# Stage 4B.3 — Trust Mechanics Characterization

[← Back to Stage 4B.3](README.md)

## Status

Stage 4B.3 PR2 executable characterization is implemented, and its scoped
PostgreSQL validation has been completed by the human operator:

* focused Stage 4B.3 PR2 characterization cases: `5 passed in 0.33s`;
* corroborating atomicity / delivery cases: `2 passed in 0.16s`;
* all three affected projection integration files: `29 passed in 1.21s`;
* projection-definition unit suite: `7 passed in 0.08s`.

These results record only the named runs; they do not claim broader test
coverage.

## Purpose

PR2 turns the current mechanics that matter to projection-trust contract design
into focused executable scenarios. It characterizes existing replay observation,
mutable projection state, repaired per-order progress, worker transaction
delivery, and worker identity. It does not implement projection trust.

## Characterized Mechanics

### Replay `MATCH` is not progress-qualified

Accepted history and matching projection state can produce
`ReplayValidationResult.MATCH` while no `projection_order_progress` row exists.
The validator does not inspect or repair that progress.

### Replay equality belongs to one database observation

The validator's `REPEATABLE READ READ ONLY` transaction observes accepted
history and projection state in one PostgreSQL snapshot. A deterministic
interleaving establishes the snapshot with the accepted-history read, commits an
independent same-version projection-state content change, and then permits the
validator to read projection state. The in-flight validation still observes the
original state and returns `MATCH`; an independent observer sees the changed
state and unchanged progress, and a fresh validation returns `DRIFT`.

This characterizes both boundaries:

```text
MATCH
= observation-scoped point-in-time state consistency
!= progress-qualified validated boundary

same sequence/version
!= same projection-state content
```

### State/progress disagreement is not a typed worker outcome

When projection state is already at sequence 1 but repaired progress is missing,
eligibility treats progress as sequence zero and selects accepted event sequence
1. The canonical reducer then rejects the transition because state requires
sequence 2. PR2 narrows the existing test to that exact sequence disagreement;
it does not add a general disagreement matrix or recovery policy.

### Caller-visible `applied` follows transaction commit

Current tests already establish that state and repaired progress share the
worker-owned transaction, roll back together when progress fails, and are both
visible to an independent observer after `process_next()` returns `applied`.

PR2 adds a commit-time failure schedule using a connection-local temporary table
and an initially deferred PostgreSQL unique constraint. The real state and
progress operations succeed inside the transaction, but the deferred violation
fails transaction commit. No applied result reaches the caller, and an
independent observer sees neither state nor repaired progress.

### `worker_name` is operational identity

Two sequential workers with different names use the same fixed projection
definition and epoch. The first applies sequence 1; the second continues the
same order's repaired progress by applying sequence 2. Durable progress reaches
sequence 2 and cites the second accepted event.

The supported Python path remains fixed to `order_state_projection`, epoch `1`.
The database schema's more permissive physical identity shape does not broaden
the supported production runtime identity.

## Executable Evidence

| Evidence | Test |
| --- | --- |
| `MATCH` with no repaired progress | `test_validate_order_returns_match_when_projection_matches_replay` |
| Repeatable-read observation and independent same-version state mutation | `test_validate_order_keeps_repeatable_read_observation_when_state_changes_between_reads` |
| State ahead of missing progress reaches the expected reducer sequence failure | `test_process_next_fails_fast_when_projection_state_is_ahead_of_checkpoint` |
| Progress failure rolls state and progress back together | `test_projection_state_and_progress_rollback_together_on_progress_failure` |
| Commit-time failure prevents applied delivery and durable writes | `test_commit_failure_prevents_applied_delivery_and_rolls_back_state_and_progress` |
| Independent observer sees both writes after successful return | `test_worker_processes_late_committing_lower_global_position_per_order` |
| Different worker names continue the same per-order progress | `test_worker_name_is_not_independent_projection_progress_identity` |
| Supported Python projection name and epoch remain fixed | `test_postgres_worker_uses_only_current_projection_definition` and related definition-guard tests |

## What PR2 Proves

The completed focused PostgreSQL execution provides executable evidence that:

* replay `MATCH` does not imply repaired-progress qualification;
* one replay result is scoped to one stable repeatable-read observation;
* projection-state content can change independently while sequence/version and
  repaired progress remain unchanged;
* current state/progress disagreement can surface through reducer invariants
  without becoming a typed trust or recovery result;
* worker body completion is not caller-visible committed completion;
* caller-visible `applied` is correlated with successful transaction exit;
* `worker_name` does not partition repaired per-order progress.

## What PR2 Does Not Prove

PR2 does not prove continuing projection trust, domain correctness, global
catch-up, freshness, history completeness, snapshot trust, or runtime action
authority. It does not define a validated-boundary contract, projection-advance
evidence, state binding, reducer identity, serializer, trust checkpoint,
persistence, policy, strategy, retry, rebuild, quarantine, or remediation.

## Historical PR3 Implications

These implications described what contract work would have required if PR3 had
proceeded. ADR 0026 later concluded that no additional Stage 4B.3 runtime layer
is currently justified, so PR3 does not proceed. The characterization findings
remain valid historical/reference evidence.

Had PR3 proceeded, it could not have treated raw `MATCH`, sequence/version
equality, worker body success, or `worker_name` as projection-trust identity.
Immutable evidence contracts would have needed to keep an observation-scoped
replay comparison distinct from repaired-progress lineage and from one
commit-correlated projection advance. Missing progress and missing
state-content binding would have needed to remain explicitly unqualified.

## Historical Open Questions After PR2

At PR2 completion, architecture questions remained about state-content binding,
live projection-logic identity, preservation or requalification of the original
read-only observation, and whether durable trust checkpoints would be needed.
PR2 did not resolve those questions. ADR 0026 later determined that they do not
currently justify another Stage 4B.3 runtime layer; they are re-entry
considerations, not unfinished PR2 validation.
