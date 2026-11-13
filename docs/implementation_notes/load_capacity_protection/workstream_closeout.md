# Load / Capacity Protection — Workstream Closeout

[← Back to Load / Capacity Protection](README.md)

## Final Status

| Responsibility | Final status | Scope |
|---|---|---|
| Research and characterization | COMPLETE | PR0–PR11 resolve the scoped evidence, mechanism, ownership and qualification investigations. Evidence collection is closed. |
| Production-capable opt-in mechanism | IMPLEMENTED AND VALIDATED | Shared writer occupancy admission and explicit bounded retry with delayed backoff; deterministic mechanism checks and fixture-scoped live PostgreSQL characterization. |
| Actual production deployment | NOT QUALIFIED | No tracked production caller enables retry; the caller resource/lifetime contract and numerical deployment policy remain unestablished. |

PR11 is merged into `feat/load-capacity-protection`. This closes the current
workstream; it does not start PR12, enable retry or authorize merging the umbrella
branch into `main`. Completion of the investigation does not require pretending
that deployment qualification has passed.

This document owns the final workstream status and re-entry boundary. Accepted
ADRs continue to govern architectural decisions; reports/manifests retain their
measurement and provenance contracts. Historical “NOT STARTED” and “ready for
human review” labels describe those earlier stages and remain unchanged. Current
navigation reflects completed work. This closeout adds no architectural decision
and performs no new evidence reconciliation or live execution.

## Established Results and Boundaries

- [PR1 characterization](pr1_unprotected_characterization_report.md) and
  [PR2 interpretation](pr2_capacity_interpretation.md) establish a fixture-scoped
  degradation region and an experimental headroom choice. They do not establish
  universal PostgreSQL capacity or production numerical limits.
- [PR3 admission](pr3_bounded_inflight_admission.md) and
  [PR4 comparison](pr4_protected_vs_unprotected_report.md) establish an explicit,
  shared, process-local writer-body bound. Fail-fast refusal displaces pressure
  outside that region. **Writer occupancy protection is not complete overload
  protection**, nor a connection, caller, arrival-rate or retry-pressure bound.
- [PR5 retry amplification](pr5_retry_refusal_amplification_report.md) shows that
  bounded immediate retry can amplify attempts without improving completion.
  Backoff improves eventual completion in the tested composition, with longer
  drain and pacing of later fresh work. [PR7](pr7_retry_attempt_policy_selection.md)
  selects only the opt-in finite-budget/delayed-backoff class.
- [PR8](pr8_bounded_retry_backoff.md) implements that class through
  `PostgresWriterRequest` and its builder. Retry remains explicit;
  `retry_policy=None` preserves one attempt. Only verified pre-body capacity
  refusal can continue under configured policy and remaining budget. Normal
  results and native/semantic/ambiguous failures terminate; exhaustion remains
  capacity-specific. Logical identity stays stable across serial attempts.
- [PR9](pr9_production_retry_validation_report.md) validates the actual
  production-capable composition against a contemporaneous disabled baseline.
  It demonstrates completion/resource trade-offs, **not increased DB capacity**:
  overload completion increases while paired throughput stays broadly similar
  and drain time increases. Protected overlap remains bounded. Backoff retains
  existing synchronous threads and connections without a writer permit or active
  business transaction; observed wait boundaries are IDLE → IDLE. Configured
  connection count does not increase. Retained-lane pacing means not every extra
  completion is attributable to direct retry recovery.
- [PR10](pr10_retry_waiting_ownership_decision.md), accepted in
  [ADR 0032](../../adr/0032_keep_capacity_retry_synchronous_under_explicit_caller_resource_budgets.md),
  retains synchronous waiting **conditionally**, for callers meeting explicit
  resource/lifetime/custody obligations. Same-connection retention is a topology
  choice, not semantic identity. [PR11](pr11_caller_resource_envelope_audit.md)
  finds no tracked production retry-enabled consumer and no qualified deployment.

[ADR 0031](../../adr/0031_separate_resource_occupancy_retry_and_arrival_protection.md)
keeps occupancy, retry pressure and arrival-rate protection separate. Capacity
refusal is evidence, not automatic retry or Stage 4E reinvocation authority.
Stage 4E/DecisionReceipt remain outside the retry composition; no A3 or authority
refund is introduced.

Experimental bounds, offered concurrency, eight attempts and fixed 5 ms backoff
are not production defaults or optimal settings. No Rate Limiter, Token Bucket,
pool, queue, async scheduler or production jitter mechanism has been selected.
Deferral does not establish that any is permanently unnecessary. Fixture-scoped
CREATE results, application elapsed timings and finite-workload completion do not
qualify other workloads, distributed scope, production SLOs or hard deadlines.

## Evidence and Publication Index

Existing manifests own exact source revisions, cohort identities, asset names,
byte sizes and hashes; their linked compact CSVs retain repetition-level results.
The following Release URLs match the tracked reports/manifests. This closeout
neither downloads nor independently revalidates published assets.

| Evidence | Interpretation | Provenance / compact results | Published raw evidence |
|---|---|---|---|
| Unprotected characterization | [PR1 report](pr1_unprotected_characterization_report.md), [PR2 interpretation](pr2_capacity_interpretation.md) | [PR1 manifest](../../../experiments/load_capacity_protection/results/pr1_evidence_manifest.json) | [PR1 Release](https://github.com/hikaru-212/streaming-system-compass/releases/tag/load-capacity-pr1-evidence-v1) |
| Protected versus unprotected | [PR4 report](pr4_protected_vs_unprotected_report.md) | [PR4 manifest](../../../experiments/load_capacity_protection/results/pr4_evidence_manifest.json) | [PR4 Release](https://github.com/hikaru-212/streaming-system-compass/releases/tag/load-capacity-pr4-evidence-v1) |
| Experiment-owned retry policies | [PR5 report](pr5_retry_refusal_amplification_report.md) | [PR5 manifest](../../../experiments/load_capacity_protection/results/pr5_evidence_manifest.json) | [PR5 Release](https://github.com/hikaru-212/streaming-system-compass/releases/tag/load-capacity-pr5-evidence-v1) |
| Production-path retry comparison | [PR9 report](pr9_production_retry_validation_report.md) | [PR9 manifest](../../../experiments/load_capacity_protection/results/pr9_evidence_manifest.json) | [PR9 Release](https://github.com/hikaru-212/streaming-system-compass/releases/tag/load-capacity-pr9-evidence-v1) |

Evidence collections remain closed. PR9's archived canonical `final.json` is the
complete matrix evidence; smoke and cumulative checkpoint snapshots are not
additional recorded samples. No dataset, raw archive or measured value is copied
or modified here. Earlier evidence and Releases retain their existing meaning.

## Remaining Deployment Obligations

The [PR11 qualification matrix](pr11_caller_resource_envelope_audit.md#8-qualification-matrix)
is the detailed audit. Before enablement, one named caller must establish:

1. **Population and scope:** enforce concurrent logical callers C independently
   of the shared writer-body bound B; account for every instance/process and gate.
2. **Connection/thread budgets:** include active and waiting callers, retained
   idle lanes, H other connection consumers, and explicit headroom. Under the
   documented one-connection-per-lane assumptions, C+H is conditional accounting,
   not a limit enforced by B.
3. **Numerical policy and lifetime:** select a finite attempt budget and complete
   positive delay schedule against caller objectives. Define acquisition,
   execution/finalization and resource-retention constraints. Finite attempts
   and nominal delay sums do not bound total invocation lifetime; dispatch expiry
   and cooperative cancellation do not interrupt an executing writer.
4. **Custody and session context:** own acquisition/closure and exclusive
   connection access, non-autocommit business execution, IDLE entry/waits, and
   absence of external lifecycle/execution or session advisory locks during
   waits. IDLE alone does not establish exclusive custody or absence of locks.
5. **Operational lifecycle:** own stop-intake, cancellation, shutdown/drain,
   connection disposition and result delivery on every terminal path. Preserve
   accepted results and ambiguous-effect evidence; do not reset a live logical
   budget by rebuilding owners. Observe attempts, waits and retained resources,
   then validate the actual integration and its claimed envelope.

These are unresolved deployment obligations, not newly implemented controls or a
qualification checklist passed by PR9. No-retry remains a valid disabled policy.

## Conditions for Reopening Work

Implementation is not the automatic successor to this closeout. Re-entry needs
an identified requirement or defect, an exact responsibility/scope, reviewable
validation criteria, and separate human authorization for the proposed work.

| Concrete trigger | Smallest justified re-entry responsibility |
|---|---|
| A named production caller seeks retry enablement | First establish the obligations above. Authorize only the integration/configuration and any specific missing enforcement demonstrated by that contract; qualify that caller before deployment. |
| A caller cannot meet a required resource-retention deadline, cancellation or shutdown guarantee using current seams | Design the missing lifecycle/termination ownership and accepted-result/cleanup failure contract before implementing it. A finite retry count is not a substitute. |
| A caller establishes that connection ownership during backoff is unacceptable | Separately design PR10 Option C: retry above per-attempt acquisition, preserving budget, provenance, equivalent session context and cleanup semantics. Option B is not selected; a provider/factory does not imply a pool. |
| A demonstrated thread budget requires thread-free waiting | Reopen the deferred scheduler/async ownership decision with pending-work bounds, cancellation, fairness, shutdown and restart responsibilities. Thread retention alone is insufficient justification. |
| Residual attempt/arrival pressure or backlog requirements exceed a named caller's objectives | Collect separately authorized evidence at the relevant boundary and compare alternatives before selecting rate/burst control, jitter or queueing. Do not infer a mechanism from refusal counts alone. |
| A reproducible correctness, provenance or authority defect is found | Scope a focused repair and regression witness; preserve original evidence and distinguish any invalidated claim explicitly. Do not silently reinterpret accepted results. |

New workload/topology or numerical-policy questions may justify targeted
characterization rather than implementation. They need their own method,
comparison and live-run approval; they do not reopen historical cohorts or permit
silent retuning. PR9 performance cannot be assumed to transfer to a changed
ownership model. No PR12 implementation or umbrella-to-main merge is authorized.
