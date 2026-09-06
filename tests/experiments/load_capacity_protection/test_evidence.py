"""Pure schema/readback tests; no DB, filesystem output, or wall-clock assertions."""

from dataclasses import fields, replace
from contextlib import contextmanager
from decimal import Decimal
from io import StringIO
import json

import pytest

from experiments.load_capacity_protection.evidence import (
    CellEvidence, Cohort, LoadRunPlan, LocalProvenance, ProducerEvidence,
    RequestEvidence, RunProblem, VerificationEvidence, descriptive_statistics,
    dumps_evidence, loads_evidence, project_observation,
    read_evidence, write_evidence,
)
from experiments.load_capacity_protection.model import (
    LoadAcknowledgement, LoadDurableStatus, LoadDurableVerification, LoadRequestObservation,
    LoadFailureEvidence, LoadOuterPhase,
)
from src.compass.transition.types import (
    EnforcementAction, ValidationDecision, ValidationMode, ValidationResult, ValidationVerdict,
)
from src.pipeline.transactional.admission import (
    AdmissionResult, AdmissionVerdict, AppendVersionMismatchEvidence, StreamAdmissionResult,
)
from src.pipeline.transactional.postgres_write_side import PostgresWriteSideOutcome
from src.pipeline.transactional.postgres_write_side_measurement import (
    PostgresWriteSideMeasurement, PostgresWriteSideMeasurementAvailability,
    PostgresWriteSidePhaseMeasurement, PostgresWriteSidePhaseMeasurementState,
)
from tests.experiments.load_capacity_protection.test_model import (
    accepted, cell_identity, event_for, work_item, writer_failure,
)


def plan(**changes):
    values = dict(
        run_id="run-a", k=1, concurrency_levels=(2,), warmups=0, repetitions=1,
        ordering_seed=17, amount=Decimal("10.00"), test_database="compass_test",
        control_connections=1, connection_budget=3, connect_timeout_seconds=5,
        stop_policy="stop_claims_and_drain_without_deadline",
        cleanup_policy="delete_verified_cell_rows",
    )
    return LoadRunPlan(**(values | changes))


def local():
    return LocalProvenance(None, None, None, None, None, None, None, None)


def evidence(*observations, planned=None):
    planned = planned if planned is not None else tuple(o.item for o in observations)
    return CellEvidence(
        plan(k=len(planned)), cell_identity(), Cohort.RECORDED, planned,
        tuple(project_observation(o) for o in observations), local(), None,
        None, None, None, None, False, (), (),
    )


def test_raw_roundtrip_preserves_selected_meaning_without_producer_messages():
    observation = accepted()
    observation = replace(observation, result=replace(
        observation.result, idempotency_decision=replace(
            observation.result.idempotency_decision, reason="private diagnostic DO NOT EXPORT",
        ),
    ))
    original = evidence(observation)
    encoded = dumps_evidence(original)
    decoded = loads_evidence(encoded)
    assert decoded == original
    assert decoded is not original
    assert "DO NOT EXPORT" not in encoded
    assert decoded.observations[0].result.outcome is observation.result.outcome
    assert descriptive_statistics(decoded) == descriptive_statistics(original)


@pytest.mark.parametrize("field, version", [("schema_version", 99), ("method_version", "unknown")])
def test_unsupported_versions_are_rejected(field, version):
    document = json.loads(dumps_evidence(evidence(accepted())))
    document[field] = version
    with pytest.raises(ValueError, match="unsupported"):
        loads_evidence(json.dumps(document))


def test_missing_timestamps_and_provenance_stay_explicitly_missing():
    raw = evidence(LoadRequestObservation(cell_identity(), work_item()))
    decoded = loads_evidence(dumps_evidence(raw))
    assert decoded.local == local()
    assert all(getattr(decoded.local, f.name) is None for f in fields(LocalProvenance))
    assert decoded.observations[0].offer_ns is None
    assert decoded.runtime is None
    assert decoded.setup_elapsed_ns is None
    assert descriptive_statistics(decoded)["completed_run_elapsed_ns"] is None
    assert descriptive_statistics(decoded)["samples"]["external_writer_call_ns"] == ()


def test_failure_and_later_durability_never_upgrade_acknowledgement():
    observation = writer_failure()
    observation = replace(observation, verification=LoadDurableVerification(
        LoadDurableStatus.PRESENT, (event_for(observation.item),),
    ))
    decoded = loads_evidence(dumps_evidence(evidence(observation)))
    raw, = decoded.observations
    assert raw.result is raw.measurement is None
    assert raw.failure.sqlstate == "08006"
    assert raw.failure.exception_class == "psycopg.OperationalError"
    assert raw.verification.status is LoadDurableStatus.PRESENT
    assert raw.acknowledgement is LoadAcknowledgement.UNKNOWN
    assert decoded.accounting.acknowledged_accepted == 0
    assert "traceback" not in dumps_evidence(decoded)


def test_partial_work_retains_unobserved_planned_items_and_no_completed_throughput():
    raw = evidence(accepted(), planned=(work_item(0), work_item(1)))
    decoded = loads_evidence(dumps_evidence(raw))
    assert decoded.incomplete
    assert decoded.accounting.residual_workload_indices == (1,)
    stats = descriptive_statistics(decoded)
    assert stats["observed_elapsed_ns"] == 45
    assert stats["completed_run_elapsed_ns"] is None
    assert stats["acknowledged_accepted_per_second"] is None


def test_all_production_phase_states_and_decimal_values_survive_roundtrip():
    measured = PostgresWriteSidePhaseMeasurement(PostgresWriteSidePhaseMeasurementState.MEASURED, 0)
    phases = {f.name: measured for f in fields(PostgresWriteSideMeasurement)}
    phases["rollback_finalization"] = PostgresWriteSidePhaseMeasurement(
        PostgresWriteSidePhaseMeasurementState.NOT_REACHED,
    )
    phases["pessimistic_advisory_try_lock_call"] = PostgresWriteSidePhaseMeasurement(
        PostgresWriteSidePhaseMeasurementState.NOT_APPLICABLE,
    )
    phases["validation_runtime_call"] = PostgresWriteSidePhaseMeasurement(
        PostgresWriteSidePhaseMeasurementState.NOT_COLLECTED,
    )
    observation = replace(
        accepted(), measurement=PostgresWriteSideMeasurement(**phases),
        measurement_availability=PostgresWriteSideMeasurementAvailability.AVAILABLE,
    )
    original = evidence(observation)
    decoded = loads_evidence(dumps_evidence(original))
    assert decoded == original
    assert decoded.observations[0].measurement.producer_write_invocation.elapsed_ns == 0
    assert decoded.planned[0].signature.amount.as_tuple() == Decimal("10.00").as_tuple()


def test_aggregate_generation_keeps_raw_samples_and_has_no_policy_or_percentiles():
    raw = evidence(accepted())
    before = dumps_evidence(raw)
    stats = descriptive_statistics(raw)
    assert stats["samples"]["external_writer_call_ns"] == (20,)
    assert stats["sample_counts"]["external_writer_call_ns"] == 1
    assert stats["acknowledged_accepted_per_second"] == 1_000_000_000 / 45
    assert dumps_evidence(raw) == before
    names = set(stats)
    for cls in (CellEvidence, ProducerEvidence, RequestEvidence, LoadRunPlan):
        names.update(f.name for f in fields(cls))
    assert not names & {"knee", "safe_concurrency", "recommended_limit", "p99", "p95", "p50"}


def test_reader_rejects_changed_counts_unknown_types_and_missing_fields():
    original = json.loads(dumps_evidence(evidence(accepted())))
    bad = json.loads(json.dumps(original))
    bad["accounting"]["fields"]["planned"] = 100
    with pytest.raises(ValueError, match="reconcile"):
        loads_evidence(json.dumps(bad))
    bad = json.loads(json.dumps(original))
    bad["cell"]["record"] = "os.system"
    with pytest.raises(ValueError, match="unknown"):
        loads_evidence(json.dumps(bad))
    del original["cell"]["fields"]["runtime"]
    with pytest.raises(ValueError, match="missing"):
        loads_evidence(json.dumps(original))


def test_reader_rejects_duplicate_keys_and_live_objects():
    with pytest.raises(ValueError, match="duplicate"):
        loads_evidence('{"schema_version": 1, "schema_version": 1}')
    with pytest.raises(TypeError, match="allowed"):
        dumps_evidence(replace(evidence(accepted()), runtime=object()))


def test_safe_verification_failure_and_partial_reads_survive_readback():
    original = evidence(writer_failure())
    request = replace(original.observations[0], verification=VerificationEvidence(
        LoadDurableStatus.UNKNOWN, (event_for(work_item()),), None, None,
        ("verification_unavailable",), RunProblem("verification", "exception", "psycopg.Error", "08006"),
    ))
    original = replace(original, observations=(request,))
    assert loads_evidence(dumps_evidence(original)) == original


def test_producer_admission_and_validation_facts_survive_without_diagnostic_metadata():
    original = accepted()
    validation = ValidationDecision(EnforcementAction.ALLOW, ValidationResult(
        ValidationVerdict.PASSED, "private reason", "candidate-a", "FullProofValidator",
        ValidationMode.STRICT, 0.0, 0.0, 0.0, {"private": "unbounded metadata"},
    ))
    result = replace(
        original.result, outcome=PostgresWriteSideOutcome.ADMISSION_REJECTED, accepted_event=None,
        stream_admission_result=StreamAdmissionResult(
            AdmissionVerdict.ADMITTED, "private reason", original.item.signature.order_id,
        ),
        admission_result=AdmissionResult(
            AdmissionVerdict.STALE_WRITE, "private reason", "candidate-a", None,
            AppendVersionMismatchEvidence(0, 1),
        ),
        validation_decision=validation,
    )
    original = replace(original, result=result,
                       acknowledgement=LoadAcknowledgement.NO_NEW_ACKNOWLEDGED_ACCEPTED_WRITE)
    text = dumps_evidence(evidence(original))
    decoded = loads_evidence(text)
    producer = decoded.observations[0].result
    assert producer.preparation_verdict is AdmissionVerdict.ADMITTED
    assert producer.append_verdict is AdmissionVerdict.STALE_WRITE
    assert producer.version_mismatch == AppendVersionMismatchEvidence(0, 1)
    assert producer.validation_verdict is ValidationVerdict.PASSED
    assert producer.validation_action is EnforcementAction.ALLOW
    assert producer.validator_name == "FullProofValidator"
    assert "private" not in text and "unbounded metadata" not in text
    assert decoded.accounting.terminal == 1 and decoded.accounting.acknowledged_accepted == 0


def test_pre_entry_failure_roundtrip_has_no_manufactured_writer_interval():
    ack = LoadAcknowledgement.NO_NEW_ACKNOWLEDGED_ACCEPTED_WRITE
    observation = LoadRequestObservation(
        cell_identity(), work_item(), offer_ns=0, terminal_observation_ns=10,
        failure=LoadFailureEvidence("builtins.RuntimeError", LoadOuterPhase.SCHEDULING, False, ack),
        acknowledgement=ack,
    )
    decoded = loads_evidence(dumps_evidence(evidence(observation)))
    assert decoded.observations[0].writer_entry_ns is None
    assert decoded.accounting.terminal == 1 and decoded.accounting.writer_entered == 0


def test_explicit_file_output_and_readback_never_overwrite_existing_evidence():
    class MemoryPath:
        content = None

        @contextmanager
        def open(self, mode, *, encoding):
            assert mode == "x" and encoding == "utf-8"
            if self.content is not None:
                raise FileExistsError("already retained")
            with StringIO() as output:
                yield output
                self.content = output.getvalue()

        def read_text(self, *, encoding):
            assert encoding == "utf-8"
            return self.content

    path = MemoryPath()
    original = evidence(accepted())
    write_evidence(path, original)
    assert read_evidence(path) == original
    first = path.content
    with pytest.raises(FileExistsError):
        write_evidence(path, original)
    assert path.content == first
