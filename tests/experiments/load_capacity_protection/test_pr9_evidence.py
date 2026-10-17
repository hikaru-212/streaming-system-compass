"""Independent PR9 schema preserves enums, signatures, missing data and raw events."""

from dataclasses import replace
import json

import pytest

from experiments.load_capacity_protection.pr9_evidence import dumps_evidence, loads_evidence
from experiments.load_capacity_protection.pr9_model import RunEvidence
from tests.experiments.load_capacity_protection.test_pr9_runner import run_fixture, plan


def test_complete_production_path_roundtrip_preserves_missing_values(monkeypatch):
    evidence, _, _ = run_fixture(monkeypatch)
    encoded = dumps_evidence(evidence)
    assert loads_evidence(encoded) == evidence
    refused = next(r for r in loads_evidence(encoded).cells[0].requests if r.result is None)
    assert refused.measurements == ()
    assert any(e.pre_body_refusal is None for e in refused.retry)
    assert "pr9-production-retry-validation-v1" in encoded


@pytest.mark.parametrize("change", [lambda d: d.update(schema=5), lambda d: d.update(method="pr5"),
                                    lambda d: d.update(extra=True), lambda d: d["evidence"].update(type="os.system"),
                                    lambda d: d["evidence"]["value"].update(problems=[])])
def test_codec_rejects_schema_type_and_unknown_fields(change):
    document = json.loads(dumps_evidence(RunEvidence(plan(), (), ())))
    change(document)
    with pytest.raises((TypeError, ValueError)):
        loads_evidence(json.dumps(document))


def test_codec_rejects_duplicate_keys_and_nonfinite_json():
    with pytest.raises(ValueError):
        loads_evidence('{"schema":1,"schema":1}')
    with pytest.raises(ValueError):
        loads_evidence('{"schema":NaN}')


def test_unavailable_measurement_roundtrip_keeps_primary_acknowledgement(monkeypatch):
    from src.pipeline.transactional.postgres_write_side_measurement import PostgresWriteSideMeasurementAvailability as Availability
    from experiments.load_capacity_protection.pr9_characterization import summarize
    evidence, _, _ = run_fixture(monkeypatch)
    cell = evidence.cells[1]
    request = next(r for r in cell.requests if r.measurements)
    unavailable = replace(request.measurements[0], availability=Availability.UNAVAILABLE, measurement=None)
    request = replace(request, measurements=(unavailable,))
    cell = replace(cell, requests=tuple(request if r.index == request.index else r for r in cell.requests))
    evidence = replace(evidence, cells=(cell,))
    restored = loads_evidence(dumps_evidence(evidence))
    assert restored == evidence
    assert summarize(restored.cells[0])["acknowledged_accepted"] == 2
    assert not summarize(restored.cells[0])["valid"]
