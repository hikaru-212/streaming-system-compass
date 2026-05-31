from src.compass.transition.types import ValidationMode
from src.pipeline.transactional.postgres_write_side_config import (
    PostgresWriteSideConfig,
    ValidationPlacement,
)


def test_default_postgres_write_side_config_uses_strict_in_transaction():
    config = PostgresWriteSideConfig()

    assert config.validation_mode == ValidationMode.STRICT
    assert config.validation_placement == ValidationPlacement.IN_TRANSACTION


def test_postgres_write_side_config_can_select_pre_transaction_validation():
    config = PostgresWriteSideConfig(
        validation_mode=ValidationMode.STRICT,
        validation_placement=ValidationPlacement.PRE_TRANSACTION,
    )

    assert config.validation_mode == ValidationMode.STRICT
    assert config.validation_placement == ValidationPlacement.PRE_TRANSACTION


def test_validation_placement_values_are_stable():
    assert ValidationPlacement.IN_TRANSACTION.value == "IN_TRANSACTION"
    assert ValidationPlacement.PRE_TRANSACTION.value == "PRE_TRANSACTION"