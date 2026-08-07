# Stage 4B.1 PR1 — Projection Snapshot-Assisted Resolution Trace Boundary

[← Back to Stage 4B.1](README.md)

## Status

```text
Stage 4B.1
= current formal development stage

this note
= source-grounded PR1 boundary and final PR2 contract record

ProjectionSnapshotAssistedResolutionTrace
= implemented in PR2

ProjectionSnapshotAssistedResolutionExecution
= implemented in PR2

resolve_order_with_trace(...)
= not implemented; remains PR3 work
```

This note preserves the PR1 planning boundary and records the final PR2 immutable
contract. It does not add a traced resolver API or change current resolver
behavior.

## 1. Purpose

Stage 4B.1 owns:

```text
one execution path's bounded progress and terminal stage
```

The first producer-specific slice is:

```text
ProjectionSnapshotAssistedResolutionTrace
```

It is an in-memory diagnostic companion to one snapshot-assisted resolution
execution. It does not own:

- compact `DecisionReceipt` governance evidence;
- multiple attempts or attempt relationships;
- retry candidacy or authorization;
- fallback selection;
- runtime policy;
- execution strategy;
- runtime action.

Those responsibilities remain separate even when later orchestration can
observe more than one artifact.

## 2. Source-Grounded Baseline

This boundary is grounded in:

- [`projection_snapshot_assisted_state_resolver.py`](../../../src/pipeline/projection/projection_snapshot_assisted_state_resolver.py);
- [`test_projection_snapshot_assisted_state_resolver.py`](../../../tests/unit/pipeline/projection/test_projection_snapshot_assisted_state_resolver.py);
- [`read_side_outcome_mapping.py`](../../../src/compass/runtime/read_side_outcome_mapping.py);
- [`read_side_decision_receipt_mapping.py`](../../../src/compass/runtime/read_side_decision_receipt_mapping.py).

The current resolver owns no database transaction, snapshot-trust decision,
fallback, mutation, or runtime action. The existing read-side adapters consume
the primary result; they do not expose snapshot `source_event_sequence` or infer
it from `source_global_position`.

## 3. Existing Resolver Path

The current execution order is:

```text
constructor validation
→ trusted snapshot precondition
→ exact snapshot lookup
→ snapshot compatibility
→ snapshot hydration
→ paginated tail loading with per-record source validation
→ complete validated tail accumulation
→ replay of the complete validated tail
→ successful result
```

Inside the current tail helper, each loaded page is source-validated before it
is appended to the accumulated tail. Across the complete resolver execution,
all pagination and source validation finish before the replay loop begins.

Therefore:

```text
complete tail validation
occurs before
tail replay
```

This ordering has two important consequences:

- a tail source or source-contract failure can have validation progress but has
  no successfully replayed tail event;
- a replay failure occurs only after the complete tail has passed source
  validation, so validation progress may be ahead of replay progress.

Constructor validation rejects a non-positive `tail_event_limit` before an
execution result can exist. The trusted snapshot precondition is checked before
snapshot lookup. Snapshot lookup uses the exact caller-supplied trusted snapshot
identity; it does not select a latest snapshot.

## 4. Existing Exits

The current typed exits are:

| Status | Current meaning |
|---|---|
| `INVALID_SNAPSHOT_PRECONDITION` | No trusted snapshot identity was supplied. |
| `MISSING_SNAPSHOT` | Exact lookup returned no snapshot. |
| `INVALID_SNAPSHOT_COMPATIBILITY` | A loaded snapshot failed compatibility validation or hydration raised the currently handled `ValueError`. |
| `TAIL_EVENT_SOURCE_CONTRACT_VIOLATION` | Tail loading or source validation raised the currently handled `ValueError`. |
| `TAIL_REPLAY_FAILED` | Tail replay raised the currently handled reducer `ValueError`. |
| `RESOLVED_FROM_SNAPSHOT` | Snapshot hydration and complete validated-tail replay succeeded. |

Unexpected exceptions currently propagate. In particular, snapshot lookup has
no result-producing exception catch, and hydration, tail loading, source
validation, and replay catch only their current `ValueError` boundaries.

Later traced execution must preserve that behavior:

```text
currently propagating exception
→ continues to propagate
→ no guaranteed trace execution result
```

The first traced API must not use generic exception capture to guarantee a
trace.

## 5. Primary Result Ownership

```text
ProjectionSnapshotAssistedResolutionResult
= primary resolution result
```

Its existing public data and behavior remain unchanged:

- `order_id`;
- `status`;
- `resolved_state`;
- `snapshot_id`;
- `source_global_position`;
- `reason`;
- status-derived `is_resolved` behavior.

The primary result owns final resolved state:

```text
resolved_state
= present only in the successful primary result
```

An unsuccessful result must continue to omit `resolved_state`. A trace must not
contain either the complete state or an internally available partially replayed
`OrderState`.

The existing semantic-outcome adapter continues to receive the primary result's
current status and reason. The existing DecisionReceipt adapter continues to
validate result shape and preserve snapshot lineage without reconstructing
snapshot sequence progress.

## 6. Trace Ownership

The initial trace is producer-specific and in memory:

```text
ProjectionSnapshotAssistedResolutionTrace
```

PR2 implements the immutable contract in:

```text
src/pipeline/projection/
  projection_snapshot_assisted_resolution_trace.py
```

The final terminal-stage vocabulary is:

```text
SNAPSHOT_PRECONDITION
SNAPSHOT_LOOKUP
SNAPSHOT_COMPATIBILITY
SNAPSHOT_HYDRATION
TAIL_SOURCE
TAIL_REPLAY
COMPLETED
```

The final trace fields are:

```text
terminal_stage
snapshot_source_event_sequence
last_validated_tail_event_sequence
last_successfully_replayed_tail_event_sequence
source_expected_event_sequence
observed_event_sequence
observed_order_id
observed_event_id
```

All sequence and observed-identity fields are optional bounded scalars. Their
presence is constrained by terminal stage:

- precondition, lookup, and conservative compatibility traces contain no
  validated snapshot base or tail evidence;
- hydration and later stages require the validated snapshot base;
- `TAIL_SOURCE` requires the expected source sequence, may preserve validation
  progress, has no replay progress, and carries either a complete observed-event
  triplet or no observed event;
- `TAIL_REPLAY` requires complete validation progress and a complete observed
  event triplet, while successfully replayed progress may be null or a shorter
  prefix;
- `COMPLETED` contains no failure-only expected or observed evidence and has
  either null tail progress or equal validation and replay progress.

The immutable execution envelope contains exactly:

```text
ProjectionSnapshotAssistedResolutionExecution
  result: ProjectionSnapshotAssistedResolutionResult
  trace: ProjectionSnapshotAssistedResolutionTrace
```

It validates only the source-grounded result-status/terminal-stage relationship.
It does not reinterpret or reconstruct the existing primary result.

The event-identity representation is:

```text
observed_event_id: str | None
```

The accepted tail record exposes its event identity through `event.event_id`.
`request_id` is separate request-correlation evidence and must not be used as
event identity. The trace must not parse or convert the string event identity
into `UUID`; doing so could add validation and exception behavior that the
resolver does not currently own.

PR2 deliberately omits `replay_expected_event_sequence`: after complete source
validation, the replay boundary and observed event sequence already carry that
relationship without duplicating evidence. PR2 also omits compatibility-failure
kind, `source_global_position`, requested order identity, primary-result status
and reason, snapshot identity, resolved state, and every persistence or policy
field.

## 7. Progress Semantics

The first trace must keep three boundaries distinct:

```text
snapshot_source_event_sequence
= immutable snapshot base boundary

last_validated_tail_event_sequence
= null until at least one tail record passes source validation

last_successfully_replayed_tail_event_sequence
= null until at least one tail record is successfully reduced
```

The snapshot sequence is not replayed-tail progress. A successful snapshot with
no tail therefore has a snapshot base boundary but null validation and replay
tail progress.

On a source-contract failure after one or more valid tail records, validation
progress may be present while replay progress remains null because replay has
not started. On a replay failure, the complete tail is already validated while
replay progress identifies only the successfully reduced prefix.

Validation progress and replay progress must not be collapsed into one field.
`source_expected_event_sequence` remains owned by `TAIL_SOURCE`. PR2 omits a
replay-expected field rather than introducing a generic expected-sequence field
that could hide which stage produced it.

## 8. Global-Position Boundary

```text
source_global_position
= snapshot lineage only
```

It remains primary-result and DecisionReceipt snapshot-lineage evidence. It must
not become:

- tail validation progress;
- tail replay progress;
- source completeness;
- a snapshot-tail cursor;
- global catch-up proof.

Order-local tail progress uses event sequence only.

## 9. Safety Boundary

The initial trace must not contain:

- raw exception text;
- `str(exc)`;
- SQL;
- constraint diagnostics;
- stack traces;
- credentials;
- connection information;
- complete domain state;
- partial domain state;
- complete event payloads;
- arbitrary metadata dictionaries;
- retry authorization;
- fallback decisions;
- runtime actions;
- policy results;
- cost fields.

The existing primary result currently preserves some exception-derived reason
text on snapshot hydration, tail-source, and tail-replay failure paths. That
reason behavior remains unchanged for compatibility:

```text
existing primary-result reason
→ remains on the primary result
→ is not copied into the trace
→ is not parsed to infer stage, kind, identity, or progress
```

Any later compatibility kind or extension to the terminal-stage enum must come
from structured control flow, not from reason or exception-string parsing.

## 10. Final PR2 Contract and Provisional Traced API Direction

PR2 implements:

```text
ProjectionSnapshotAssistedResolutionTrace

ProjectionSnapshotAssistedResolutionExecution
  result
  trace
```

PR3 may introduce:

```text
resolve_order_with_trace(...)
```

The immutable trace and execution-envelope field sets are the final PR2
contract. The parallel traced resolver API remains direction rather than an
implemented API and belongs to PR3 only after PR2 is accepted.

The existing:

```text
resolve_order(...)
```

must remain unchanged in:

- arguments;
- return type;
- result values;
- status values;
- reason text;
- state-presence rules;
- call ordering;
- pagination behavior;
- exception propagation.

A later shared internal execution path is acceptable only if focused tests prove
this observable equivalence. The traced API must not replay incrementally while
pages are still loading or introduce a second divergent resolution algorithm.

## 11. Branch and PR Sequence

```text
feat/stage4b1-diagnostic-resolution-trace
├── PR1 documentation and boundary
├── PR2 immutable trace contract
├── PR3 parallel traced resolver API
└── later PR only if source-grounded need appears
```

Every PR branch targets:

```text
feat/stage4b1-diagnostic-resolution-trace
```

No Stage 4B.1 PR targets `feat/stage4-runtime-semantic-governance` directly.
Only after Stage 4B.1 closeout does the Stage 4B.1 integration branch merge back
into that Stage 4 integration branch.

## 12. Non-Goals

This boundary does not add or authorize:

- a repository-wide generic trace framework;
- trace persistence, serialization, retention, indexes, or a database table;
- migrations or dependencies;
- `DecisionReceipt` fields, linkage, or automatic materialization;
- complete or partial state capture;
- `trace_id` for navigation convenience;
- `AttemptLog` or multiple-attempt relationships;
- cost or measurement evidence;
- fallback, policy, strategy, retry, or action execution;
- observability infrastructure or deployment;
- runtime bootstrap or connection-pool integration.

## 13. Implementation Stop Conditions

Implementation must stop for human review if:

- existing result semantics would change;
- existing exception propagation would change;
- generic exception capture becomes necessary;
- complete-tail-before-replay ordering would change;
- exception strings would need parsing;
- event identity is no longer source-grounded;
- `request_id` would need to stand in for event identity;
- partial or complete domain state would enter the trace;
- `DecisionReceipt` changes appear necessary;
- trace persistence, serializer, migration, dependency, policy, strategy,
  fallback, retry, `AttemptLog`, cost evidence, or observability work appears
  necessary;
- the minimal internal progress-preservation refactor proves insufficient.

These conditions prevent a bounded producer trace from silently becoming a
result redesign, persistence project, policy layer, or generic exception log.
