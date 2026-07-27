from types import SimpleNamespace

from src.compass.transition.types import ValidationMode
from src.pipeline.transactional.postgres_admission import (
    PostgresOptimisticAdmissionGate,
)
from src.pipeline.transactional.postgres_write_side import (
    _default_admission_gate_factory,
)
from src.pipeline.transactional.postgres_write_side_config import (
    PostgresWriteSideConfig,
    ValidationPlacement,
)


def test_default_postgres_write_side_config_uses_strict_pre_transaction():
    config = PostgresWriteSideConfig()

    assert config.validation_mode == ValidationMode.STRICT
    assert config.validation_placement == ValidationPlacement.PRE_TRANSACTION


def test_postgres_write_side_config_can_select_in_transaction_validation():
    config = PostgresWriteSideConfig(
        validation_mode=ValidationMode.STRICT,
        validation_placement=ValidationPlacement.IN_TRANSACTION,
    )

    assert config.validation_mode == ValidationMode.STRICT
    assert config.validation_placement == ValidationPlacement.IN_TRANSACTION


def test_default_admission_gate_factory_remains_optimistic():
    event_store = object()

    gate = _default_admission_gate_factory(
        SimpleNamespace(event_store=event_store),
    )

    assert isinstance(gate, PostgresOptimisticAdmissionGate)
    assert gate.event_store is event_store


def test_validation_placement_values_are_stable():
    assert ValidationPlacement.IN_TRANSACTION.value == "IN_TRANSACTION"
    assert ValidationPlacement.PRE_TRANSACTION.value == "PRE_TRANSACTION"
