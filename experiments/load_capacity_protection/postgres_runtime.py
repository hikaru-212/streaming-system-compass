"""Explicit PRE/OCC + STRICT PostgreSQL lane composition for PR1.

Construction binds an already-open connection without executing SQL. This is
not a live runner: connection creation, test-database guards, setup measurement,
and eventual cleanup remain with the caller, outside workload execution.
"""

from dataclasses import dataclass, field

from psycopg import Connection
from psycopg.pq import TransactionStatus

from experiments.load_capacity_protection.model import LoadWorkItem
from src.compass.transition.runtime import ValidationDispatcher, ValidationPolicy, ValidationRuntime
from src.compass.transition.types import ValidationMode
from src.compass.transition.validators import FullProofValidator, NoOpValidator
from src.core.order.enums import CommandType
from src.pipeline.transactional.postgres_admission import PostgresOptimisticAdmissionGate
from src.pipeline.transactional.postgres_unit_of_work import PostgresWriteSideUnitOfWork
from src.pipeline.transactional.postgres_write_side import PostgresTransactionalWriteSide
from src.pipeline.transactional.postgres_write_side_config import (
    PostgresWriteSideConfig,
    ValidationPlacement,
)
from src.pipeline.transactional.postgres_write_side_measurement import PostgresWriteSideMeasurementDelivery


def _optimistic_gate(uow: PostgresWriteSideUnitOfWork) -> PostgresOptimisticAdmissionGate:
    """Bind the current OCC gate to the production UOW's own event store."""
    return PostgresOptimisticAdmissionGate(uow.event_store)


@dataclass(frozen=True)
class PostgresLoadLane:
    """Retain one writer and exclusively assigned connection across CREATE calls.

The caller must supply distinct connections for distinct lanes, in scheduler
lane order, and must not use them concurrently elsewhere. This adapter does not
open, replace, commit, roll back, or close connections itself; production PRE
cleanup and UOW finalization retain their existing responsibilities. The caller
closes resources after scheduler quiescence, including on assertion failure.

Construction rejects closed, autocommit, or non-idle connections without SQL.
CREATE inputs are forwarded unchanged and the exact measured delivery is
returned. Other commands are fixture errors; native writer exceptions escape.
"""

    lane_id: int
    connection: Connection = field(repr=False, compare=False)
    config: PostgresWriteSideConfig = field(init=False)
    validation_runtime: ValidationRuntime = field(init=False, repr=False, compare=False)
    writer: PostgresTransactionalWriteSide = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if type(self.lane_id) is not int or self.lane_id < 0:
            raise ValueError("lane_id must be a non-negative integer")
        if self.connection.closed or self.connection.autocommit:
            raise ValueError("lane requires an open connection with autocommit disabled")
        if self.connection.info.transaction_status is not TransactionStatus.IDLE:
            raise ValueError("lane connection must be idle before composition")
        config = PostgresWriteSideConfig(
            validation_mode=ValidationMode.STRICT,
            validation_placement=ValidationPlacement.PRE_TRANSACTION,
        )
        runtime = ValidationRuntime(
            dispatcher=ValidationDispatcher(
                strict_validator=FullProofValidator(),
                off_validator=NoOpValidator(),
            ),
            policy=ValidationPolicy(),
            mode=ValidationMode.STRICT,
        )
        object.__setattr__(self, "config", config)
        object.__setattr__(self, "validation_runtime", runtime)
        object.__setattr__(self, "writer", PostgresTransactionalWriteSide(
            connection=self.connection,
            validation_runtime=runtime,
            admission_gate_factory=_optimistic_gate,
            config=config,
        ))

    def __call__(self, item: LoadWorkItem) -> PostgresWriteSideMeasurementDelivery:
        """Forward the original CREATE identity to the retained measured writer."""
        signature = item.signature
        if signature.command_type is not CommandType.CREATE:
            raise ValueError("the PR1 PostgreSQL lane supports only CREATE workload items")
        return self.writer.create_order_with_measurement(
            request_id=signature.request_id,
            order_id=signature.order_id,
            amount=signature.amount,
        )
