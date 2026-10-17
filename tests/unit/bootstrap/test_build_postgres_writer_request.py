"""Builder retains opt-in settings and concrete-gate provenance restrictions."""

import pytest

from src.pipeline.transactional.writer_capacity import BoundedWriterAdmission, WriterCapacityObserver
from tests.unit.pipeline.test_postgres_writer_request import Clock, build


def test_observation_does_not_relax_concrete_gate_restriction():
    class Substitute(BoundedWriterAdmission):
        pass
    with pytest.raises(TypeError, match="concrete"):
        build(Substitute(1), Clock(), capacity_observer=WriterCapacityObserver(), measure_writer=True)


@pytest.mark.parametrize("options", [{"measure_writer": 1}, {"capacity_observer": object()}])
def test_invalid_observation_settings_fail_at_composition(options):
    with pytest.raises(TypeError):
        build(BoundedWriterAdmission(1), Clock(), **options)
