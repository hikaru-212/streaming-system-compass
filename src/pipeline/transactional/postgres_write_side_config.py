from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.compass.transition.types import ValidationMode


class ValidationPlacement(Enum):
    """
    Controls where Compass validation runs relative to the PostgreSQL
    transaction boundary.

    This is intentionally separate from ValidationMode.

    ValidationMode answers:
    - how strong validation is

    ValidationPlacement answers:
    - where validation runs relative to the database transaction
    """

    IN_TRANSACTION = "IN_TRANSACTION"
    PRE_TRANSACTION = "PRE_TRANSACTION"


@dataclass(frozen=True)
class PostgresWriteSideConfig:
    """
    Configuration for PostgreSQL-backed transactional write-side execution.

    This config intentionally does not own:
    - concrete database connections
    - concrete admission gate instances
    - retry policy
    - SemanticOutcome mapping
    - runtime decision policy

    It only defines write-side orchestration strategy.
    """

    validation_mode: ValidationMode = ValidationMode.STRICT
    validation_placement: ValidationPlacement = ValidationPlacement.IN_TRANSACTION