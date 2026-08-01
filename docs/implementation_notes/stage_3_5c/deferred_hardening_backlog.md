# Stage 3.5C Deferred Hardening and Follow-Up Backlog

## Purpose

The Stage 3.5C–3.5E committed-history cursor repair is considered correct for
the currently supported baseline after the original PostgreSQL commit-inversion
reproduction, repaired no-skip tests, state/progress rollback tests,
snapshot-tail tests, permission tests, and complete repository test execution.

This provisional file records non-blocking follow-ups discovered during final
review. It exists both to prevent real risks from being silently forgotten and
to prevent deliberate non-goals or unmeasured performance concerns from being
misrepresented as active correctness defects.

## Current Repaired Baseline

- Projection progress is durable and per order.
- The only production projection identity is `order_state_projection`, epoch
  `1`.
- Eligible events are exact-next by order-local sequence.
- `global_position` is accepted-event lineage and eligible-event scheduling
  metadata, not a complete committed-history frontier.
- Projection state and per-order progress share one exact PostgreSQL connection
  and one top-level transaction.
- Snapshot tails use the same `order_id` and ascending order-local sequence.
- One active worker is the supported baseline.
- Accepted history in `order_events` remains business authority; projection
  state, progress, checkpoints, and snapshots remain derived evidence.

## Classification Discipline

This backlog uses the following classifications:

- `DEFERRED_HARDENING`
- `PERFORMANCE_VALIDATION`
- `TEST_INFRASTRUCTURE`
- `TEST_COVERAGE`
- `OPERATIONAL_CUTOVER`
- `DOCUMENTATION_CLEANUP`
- `API_SURFACE_CLEANUP`
- `ACCEPTED_NON_GOAL`

Deferred does not mean implemented. Source-supported does not mean directly
tested. A performance concern does not mean a proven performance defect. An
accepted non-goal does not mean an active bug. Every item below states its
current evidence, why it does not block the repair, and the concrete event that
would justify reopening it.

## Deferred Hardening and Follow-Up Items

| ID | Classification | Finding | Current evidence | Why it is deferred | Revisit trigger | Likely owner/stage | Candidate validation or action |
|---|---|---|---|---|---|---|---|
| C35C-DEF-001 | `PERFORMANCE_VALIDATION` | Eligible-event discovery may repeatedly examine old processed history after removal of the unsafe global scalar lower bound. | `src/storage/postgres_projection_eligible_event_source.py` joins accepted events to per-order progress, orders eligible rows deterministically, and limits the result. Correctness does not depend on query speed, and no production-scale `EXPLAIN (ANALYZE, BUFFERS)` evidence exists. | This is an unmeasured performance risk, not a demonstrated correctness or performance defect. Speculative indexes or query redesign could add cost without improving the actual plan. | Representative production-size history, measurable worker lag, or unacceptable query-plan cost. | Stage 3.5C storage/performance hardening. | Capture representative plans and buffer costs, then tune only from measured evidence. |
| C35C-DEF-002 | `DEFERRED_HARDENING` | The database physically permits another non-empty projection name and positive epoch through privileged raw SQL. | `src/pipeline/projection/order_projection_definition.py` and the PostgreSQL stores accept only `order_state_projection`, epoch `1`, before SQL. `db/migrations/006_create_projection_order_progress.sql` constrains name shape and positive epoch but not those exact values. | Unsupported rows do not affect the supported Python runtime because every production read and write uses the immutable current identity. The schema may intentionally remain physically extensible. | A second projection definition is proposed, raw-SQL progress writers become supported, or audit consumers require the database itself to reject unsupported identities. | Stage 3.5C schema/API hardening. | Decide explicitly between an exact database `CHECK` and documented physical extensibility. |
| C35C-DEF-003 | `OPERATIONAL_CUTOVER` | A terminal progress/state mismatch can be hidden behind `no_event` after an incorrect human reset. | Normal `src/pipeline/projection/postgres_worker.py` execution cannot durably split state and progress because both writes share one transaction. If progress remains at the accepted-history tip while state is missing or behind, no exact-next event may be eligible and the worker may return `no_event`. ADR 0020 requires coordinated reset. | This shape requires administrative misuse, corruption, or an incomplete cutover; it is not produced by the supported worker path. | A production cutover, automated rebuild tooling, repeated operator error, or a requirement for startup integrity checks. | Stage 3.5C operational/rebuild boundary. | Add a preflight, audit command, or cutover validator that compares state, progress, and accepted history without automatic mutation. |
| C35C-DEF-004 | `TEST_INFRASTRUCTURE` | Independent integration-test connections begin in `INTRANS`. | `tests/integration/conftest.py::db_connection_factory` runs the database-name safety `SELECT`, which opens an implicit transaction. Current tests explicitly call `rollback()` when they require top-level transaction ownership. | Existing tests correctly close the transaction at their call sites, and changing the shared fixture during repair closeout would broaden scope. | More tests forget the rollback, another false transaction-ownership failure occurs, or the fixture contract is centrally revised. | Repository integration-test infrastructure. | Make the factory roll back after its safety check and return an idle connection, then remove only redundant call-site cleanup. |
| C35C-DEF-005 | `TEST_INFRASTRUCTURE` | Security-test role membership may persist after the test session. | `tests/integration/security/helpers.py` grants runtime-role membership to the connected test owner. `RESET ROLE` restores session state but does not revoke cluster-level membership; `tests/integration/security/conftest.py` currently does not track newly added memberships. | The current isolated test cluster uses these memberships to run `SET ROLE` probes, and the behavior does not weaken production runtime permissions. | Shared test clusters, ephemeral-owner requirements, role contamination between suites, or security-audit requirements. | Stage 3.5E security-test infrastructure. | Track memberships added by the fixture and revoke only those, or document them as one-time test-cluster setup. |
| C35C-DEF-006 | `OPERATIONAL_CUTOVER` | Migration 006 builds the accepted-event lineage unique index non-concurrently. | The composite index in `db/migrations/006_create_projection_order_progress.sql` supports the progress foreign key and its lineage correctness contract. Building it on a large existing `order_events` table can block writes. | The repository is pre-production and has no measured large-table deployment requirement or lock-duration evidence. | A large retained accepted-history table, a bounded-downtime deployment objective, or measured unacceptable lock duration. | Database deployment/migration planning. | Measure index-build time and locking, then design an online migration sequence if required. |
| C35C-DEF-007 | `TEST_COVERAGE` | Focused PostgreSQL evidence is missing for three trigger/concurrency schedules. | `tests/integration/storage/test_read_side_schema_constraints.py` and `tests/integration/storage/test_postgres_projection_progress_store.py` already prove valid initial progress, accepted-event lineage, exact-next updates, stale/regressive rejection, and rollback ownership. Source also requires initial sequence 1 and immutable identity. Missing focused schedules are a raw initial insert at sequence 2, direct identity mutation during update, and two concurrent exact-next updates. | The contract is covered as a whole by source guards and multiple PostgreSQL integration tests; these are targeted adversarial additions, not evidence that progress is generally untested. | Trigger logic changes, multiple raw-SQL writers appear, or concurrent progress mutation enters supported scope. | Stage 3.5C storage integration tests. | Add three narrow real-PostgreSQL tests with explicit transaction ownership and no sleeps. |
| C35C-DEF-008 | `TEST_COVERAGE` | No adversarial test commits a writer between component reads of one repeatable-read observation. | `src/pipeline/projection/postgres_snapshot_observation.py` and `src/pipeline/projection/replay_validator.py` establish one same-connection `REPEATABLE READ READ ONLY` top-level transaction. Existing tests prove connection/outer-transaction guards and normal results. | The isolation contract is source-supported and PostgreSQL-defined; the missing evidence is one controlled schedule, not a known implementation failure. | The observation boundary becomes runtime-critical, isolation setup changes, or stronger executable evidence is required for audit. | Stage 3.5C replay / Stage 3.5D snapshot tests. | Add one independent writer connection that commits between instrumented component reads and assert the original observation remains stable. |
| C35C-DEF-009 | `DEFERRED_HARDENING` | Migration 006 is designed for one-shot ordered application rather than repeat-safe reruns. | Normal migration execution applies `db/migrations/006_create_projection_order_progress.sql` once. Trigger creation is unconditional even though some table/index statements are guarded. | Migration tracking should prevent reapplication, and repeatability is not an established repository migration contract. | Migration policy changes to require safe reruns, recovery from partial application becomes supported, or migration tooling stops tracking applied versions. | Database migration infrastructure. | Document one-shot semantics or make every object creation repeat-safe under a separately reviewed policy. |
| C35C-DEF-010 | `API_SURFACE_CLEANUP` | Some storage connection exposure is unused or narrowly used. | Repository search shows `PostgresAcceptedHistoryEventSource.connection` and `PostgresProjectionSnapshotStore.connection` are not consumed. `PostgresEventStore.connection` is used by `DurableReplayValidator` solely to enforce exact same-connection construction and own its observation transaction. | Removing public surface during correctness closeout risks weakening connection-identity enforcement or mixing cleanup with the repair. | API stabilization, adapter reuse, static unused-member review, or a storage-boundary cleanup task. | Stage 3.5C/3.5D storage API maintenance. | Remove only proven-unused exposure; retain or replace `PostgresEventStore.connection` with an equally strong ownership/identity boundary. |
| C35C-DEF-012 | `DOCUMENTATION_CLEANUP` | Two broken relative links predate the Stage 3.5C repair. | `docs/development/README.md` links to `../implementation_notes/projection_snapshot_schema_baseline.md`; `docs/postmortems/README.md` links to `../philosophy/from_local_etl_to_streaming_system_compass.md`. Repository comparison shows both links existed before this repair. | They are unrelated pre-existing documentation defects and do not affect runtime or repair evidence. | A repository link-checking or documentation-maintenance task. | Repository documentation maintenance. | Locate the intended targets and correct the links without folding unrelated edits into the cursor repair. |
| C35C-DEF-013 | `DOCUMENTATION_CLEANUP` | Two large explanatory documents are optional rather than runtime-repair prerequisites. | `docs/architecture/aggregate_local_progress_partition_logs_and_commit_boundaries.md` and `docs/postmortems/from_architectural_warning_to_executable_invariant.md` explain external analogies and engineering history. Omitting them does not change schema, worker, snapshot, permission, cutover, or test behavior. | Their external comparisons and narrative claims require separate editorial ownership and human review. | The human architect chooses to preserve them as independent architecture/history artifacts. | Separate documentation/editorial review. | Commit separately after review, move them, or omit them without treating omission as weakening the production repair. |

## Accepted Non-Goals and Revisit Triggers

| ID | Classification | Accepted non-goal and current boundary | Revisit trigger |
|---|---|---|---|
| C35C-NG-001 | `ACCEPTED_NON_GOAL` | **Poison-event starvation:** `LIMIT 1` selects the earliest eligible event by scheduling order. A permanently failing event may repeatedly block unrelated eligible orders. The repair adds no retry, quarantine, DLQ, attempt-log, or fairness policy. | Retry policy, quarantine, DLQ, poison-event attempt logging, or multi-order fairness enters runtime scope. |
| C35C-NG-002 | `ACCEPTED_NON_GOAL` | **Multi-worker orchestration:** leases, heartbeats, event claims, consumer groups, and distributed worker coordination are not implemented. One active worker remains supported. | Horizontal read-side scaling becomes a concrete requirement. |
| C35C-NG-003 | `ACCEPTED_NON_GOAL` | **Exactly-once/effectively-once:** state/progress transaction coupling and restartability do not imply exactly-once or effectively-once semantics. | External side effects, delivery acknowledgements, or a formally specified processing guarantee requires a new protocol. |
| C35C-NG-004 | `ACCEPTED_NON_GOAL` | **Global cross-order projection order:** current projections are aggregate-local. `global_position` schedules eligible work but does not prove a global committed-history frontier. | A real globally ordered projection requires a separate commit-safe publication contract. |
| C35C-NG-005 | `ACCEPTED_NON_GOAL` | **Concurrent projection epochs:** progress contains an epoch, but `projection_states` is not multi-versioned. Parallel epochs and online epoch rebuilds are unsupported. | An online epoch migration or parallel rebuild requires a versioned state-store design. |
| C35C-NG-006 | `ACCEPTED_NON_GOAL` | **Automatic cutover/rebuild:** current cutover is human-controlled. No startup reset, backfill, state swap, or automatic reconciliation is implemented. | Production deployment requires retained state or repeatable automated cutover. |
| C35C-NG-007 | `ACCEPTED_NON_GOAL` | **Automatic snapshot fallback or repair:** validator and resolver return evidence/results; they do not own fallback, rebuild, quarantine, or runtime action policy. | A separately approved runtime trust/fallback policy is introduced. |
| C35C-NG-008 | `ACCEPTED_NON_GOAL` | **Full snapshot lineage qualification:** current `MATCH` proves state reconstruction equivalence under the implemented comparison. Stronger source-event/global-position lineage and payload-integrity qualification remains deferred. | Durable validation receipts, automatic snapshot trust, or audit requirements demand complete lineage qualification. |
| C35C-NG-009 | `ACCEPTED_NON_GOAL` | **Legacy global checkpoint retirement:** the repaired worker neither reads nor advances legacy global checkpoints for correctness. Physical removal and broader checkpoint-infrastructure retirement are deferred. | No remaining consumer needs generic checkpoints and an additive retirement plan is approved. |

## Resolved Findings Not Carried Forward

The following are resolved and must not be reopened as deferred items:

- PostgreSQL commit inversion causing permanent projection omission;
- the global checkpoint being treated as a complete committed-history frontier;
- snapshot-tail pagination through unrelated orders;
- mixed worker-store connections;
- worker execution inside an outer transaction;
- runtime projection-worker `DELETE` permission on repaired progress;
- the ADR numbering conflict;
- unsupported runtime projection names or epochs through public Python APIs;
- missing migration 006 setup documentation;
- historical/current documentation wording aligned with ADR 0020 in the
  authoritative read-side, replay, snapshot, storage, and migration-comment
  contracts;
- the destructive security fixture lacking a `_test` guard, once the security
  fixture and complete-suite validation requested alongside this backlog pass.

Resolved means the current repair implements and tests the applicable contract.
It does not expand that contract into any accepted non-goal listed above.

## Record Metadata

- Branch: `fix/stage3-5c-committed-history-cursor`
- HEAD at recording: `4f64f0b551b8`
- Latest established full-suite evidence before this task: `965 passed`,
  `0 failed`, `0 errors`
- Provisional location: this backlog may later move to a repository-wide
  backlog or split into Stage 3.5C, Stage 3.5D, and Stage 3.5E follow-ups.

The security-fixture correction created alongside this file is not claimed as
validated by this document. The task completion report must record the actual
security-suite and full-suite results.
