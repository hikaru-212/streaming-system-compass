from src.pipeline.transactional.admission import (
    AdmissionResult,
    AdmissionVerdict,
)


def test_admission_result_admitted_property_is_true_for_admitted():
    result = AdmissionResult(
        verdict=AdmissionVerdict.ADMITTED,
        reason="candidate event admitted",
        candidate_event_id="candidate-event-1",
        accepted_event_id="candidate-event-1",
    )

    assert result.admitted is True


def test_admission_result_admitted_property_is_false_for_stale_write():
    result = AdmissionResult(
        verdict=AdmissionVerdict.STALE_WRITE,
        reason="stale writer rejected",
        candidate_event_id="candidate-event-1",
        accepted_event_id=None,
    )

    assert result.admitted is False


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