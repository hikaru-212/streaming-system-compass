from dataclasses import FrozenInstanceError

import pytest

from src.pipeline.transactional.admission import (
    AdmissionResult,
    AdmissionVerdict,
    AppendVersionMismatchEvidence,
    StreamAdmissionResult,
)


def test_append_version_mismatch_evidence_is_frozen_hashable_structure():
    evidence = AppendVersionMismatchEvidence(
        expected_current_version=1,
        observed_current_version=2,
    )
    same_evidence = AppendVersionMismatchEvidence(
        expected_current_version=1,
        observed_current_version=2,
    )

    assert evidence == same_evidence
    assert hash(evidence) == hash(same_evidence)
    assert repr(evidence) == (
        "AppendVersionMismatchEvidence(expected_current_version=1, "
        "observed_current_version=2)"
    )
    with pytest.raises(FrozenInstanceError):
        evidence.expected_current_version = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("expected_current_version", True),
        ("observed_current_version", "2"),
    ],
)
def test_append_version_mismatch_evidence_requires_exact_integer_versions(
    field_name,
    field_value,
):
    values = {
        "expected_current_version": 1,
        "observed_current_version": 2,
    }
    values[field_name] = field_value

    with pytest.raises(TypeError, match=f"{field_name} must be int"):
        AppendVersionMismatchEvidence(**values)


@pytest.mark.parametrize(
    ("expected_current_version", "observed_current_version", "message"),
    [
        (-1, 2, "expected_current_version must be non-negative"),
        (1, -1, "observed_current_version must be non-negative"),
        (1, 1, "must differ"),
    ],
)
def test_append_version_mismatch_evidence_requires_non_negative_unequal_versions(
    expected_current_version,
    observed_current_version,
    message,
):
    with pytest.raises(ValueError, match=message):
        AppendVersionMismatchEvidence(
            expected_current_version=expected_current_version,
            observed_current_version=observed_current_version,
        )


def test_stream_admission_result_admitted_property_is_true_for_admitted():
    result = StreamAdmissionResult(
        verdict=AdmissionVerdict.ADMITTED,
        reason="stream admitted",
        order_id="order-1",
    )

    assert result.admitted is True


def test_stream_admission_result_admitted_property_is_false_for_lock_timeout():
    result = StreamAdmissionResult(
        verdict=AdmissionVerdict.LOCK_TIMEOUT,
        reason="stream lock timeout",
        order_id="order-1",
    )

    assert result.admitted is False


def test_stream_admission_result_admitted_property_is_false_for_infrastructure_error():
    result = StreamAdmissionResult(
        verdict=AdmissionVerdict.INFRASTRUCTURE_ERROR,
        reason="database unavailable",
        order_id="order-1",
    )

    assert result.admitted is False


def test_admission_result_admitted_property_is_true_for_admitted():
    result = AdmissionResult(
        verdict=AdmissionVerdict.ADMITTED,
        reason="candidate event admitted",
        candidate_event_id="candidate-event-1",
        accepted_event_id="candidate-event-1",
    )

    assert result.admitted is True
    assert result.append_version_mismatch_evidence is None


def test_admission_result_admitted_property_is_false_for_stale_write():
    result = AdmissionResult(
        verdict=AdmissionVerdict.STALE_WRITE,
        reason="stale writer rejected",
        candidate_event_id="candidate-event-1",
        accepted_event_id=None,
    )

    assert result.admitted is False
    assert result.append_version_mismatch_evidence is None


def test_admission_result_retains_version_evidence_as_structural_state():
    evidence = AppendVersionMismatchEvidence(
        expected_current_version=1,
        observed_current_version=2,
    )
    result = AdmissionResult(
        verdict=AdmissionVerdict.STALE_WRITE,
        reason="append version mismatch",
        candidate_event_id="candidate-event-1",
        append_version_mismatch_evidence=evidence,
    )
    same_result = AdmissionResult(
        verdict=AdmissionVerdict.STALE_WRITE,
        reason="append version mismatch",
        candidate_event_id="candidate-event-1",
        append_version_mismatch_evidence=evidence,
    )
    coarse_result = AdmissionResult(
        verdict=AdmissionVerdict.STALE_WRITE,
        reason="append version mismatch",
        candidate_event_id="candidate-event-1",
    )

    assert result == same_result
    assert result != coarse_result
    assert result.append_version_mismatch_evidence is evidence
    assert hash(result) == hash(same_result)
    assert "append_version_mismatch_evidence=" in repr(result)
    assert "expected_current_version=1" in repr(result)
    assert "observed_current_version=2" in repr(result)


def test_admission_result_rejects_wrong_version_evidence_type():
    with pytest.raises(
        TypeError,
        match="append_version_mismatch_evidence must be",
    ):
        AdmissionResult(
            verdict=AdmissionVerdict.STALE_WRITE,
            reason="append version mismatch",
            candidate_event_id="candidate-event-1",
            append_version_mismatch_evidence=object(),  # type: ignore[arg-type]
        )


def test_admission_result_version_evidence_requires_stale_write():
    evidence = AppendVersionMismatchEvidence(
        expected_current_version=1,
        observed_current_version=2,
    )

    with pytest.raises(ValueError, match="requires STALE_WRITE verdict"):
        AdmissionResult(
            verdict=AdmissionVerdict.ADMITTED,
            reason="candidate event admitted",
            candidate_event_id="candidate-event-1",
            accepted_event_id="candidate-event-1",
            append_version_mismatch_evidence=evidence,
        )


def test_admission_result_version_evidence_requires_no_accepted_event():
    evidence = AppendVersionMismatchEvidence(
        expected_current_version=1,
        observed_current_version=2,
    )

    with pytest.raises(ValueError, match="requires no accepted_event_id"):
        AdmissionResult(
            verdict=AdmissionVerdict.STALE_WRITE,
            reason="append version mismatch",
            candidate_event_id="candidate-event-1",
            accepted_event_id="accepted-event-1",
            append_version_mismatch_evidence=evidence,
        )


def test_admission_result_version_evidence_requires_candidate_event_id():
    evidence = AppendVersionMismatchEvidence(
        expected_current_version=1,
        observed_current_version=2,
    )

    with pytest.raises(ValueError, match="requires candidate_event_id"):
        AdmissionResult(
            verdict=AdmissionVerdict.STALE_WRITE,
            reason="append version mismatch",
            candidate_event_id=None,  # type: ignore[arg-type]
            append_version_mismatch_evidence=evidence,
        )


def test_admission_result_admitted_property_is_false_for_lock_timeout():
    result = AdmissionResult(
        verdict=AdmissionVerdict.LOCK_TIMEOUT,
        reason="lock timeout",
        candidate_event_id="candidate-event-1",
        accepted_event_id=None,
    )

    assert result.admitted is False


def test_admission_result_admitted_property_is_false_for_infrastructure_error():
    result = AdmissionResult(
        verdict=AdmissionVerdict.INFRASTRUCTURE_ERROR,
        reason="database unavailable",
        candidate_event_id="candidate-event-1",
        accepted_event_id=None,
    )

    assert result.admitted is False
