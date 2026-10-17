"""Explicit direct-writer composition, separate from DecisionReceipt/Stage 4E."""

from collections.abc import Callable
from time import monotonic, sleep

from psycopg import Connection

from src.compass.transition.runtime import ValidationRuntime
from src.pipeline.postgres_writer_request import PostgresWriterRequest
from src.pipeline.transactional.postgres_write_side import AdmissionGateFactory
from src.pipeline.transactional.postgres_write_side_config import PostgresWriteSideConfig
from src.pipeline.transactional.writer_capacity import BoundedWriterAdmission, WriterCapacityObserver
from src.pipeline.writer_retry_policy import WriterRetryPolicy
from src.storage.idempotency_store import RequestSignature


def build_postgres_writer_request(
    *,
    request_signature: RequestSignature,
    business_connection: Connection,
    validation_runtime: ValidationRuntime,
    capacity_admission: BoundedWriterAdmission | None = None,
    retry_policy: WriterRetryPolicy | None = None,
    admission_gate_factory: AdmissionGateFactory | None = None,
    write_side_config: PostgresWriteSideConfig | None = None,
    wait: Callable[[float], None] = sleep,
    clock: Callable[[], float] = monotonic,
    cancelled: Callable[[], bool] | None = None,
    expires_at: float | None = None,
    capacity_observer: WriterCapacityObserver | None = None,
    measure_writer: bool = False,
) -> PostgresWriterRequest:
    """Build one single-use direct CREATE/PAY request without performing I/O.

    The caller supplies the complete immutable signature, validation runtime
    and exclusively retained business connection. Optional writer configuration
    and concurrency admission retain their existing meaning. Share the same
    capacity_admission object across the intended process-local population.

    None retry_policy is the single-attempt baseline. An explicit validated
    WriterRetryPolicy enables only verified pre-body capacity retries through
    a concrete BoundedWriterAdmission. wait/clock provide the synchronous timing
    seam; cancelled and expires_at provide cooperative cancellation/dispatch
    expiry in that clock's domain. All validation errors propagate before I/O.

    The returned owner holds no lifecycle lock during attempts or waits. Enabled
    callers must provide an idle connection and hold no external execution locks
    or session advisory locks. They retain connection close/pool ownership.
    This root does not wrap existing Stage 4E owners, mint authority, auto-enable
    existing consumers, create connections, or read environment configuration.

    capacity_observer optionally records concrete-gate boundaries correlated to
    each attempt; its failures remain separate from business execution.
    measure_writer opts into existing measured public writer variants and the
    owner's separate measurements snapshot. Both default off and can be supplied
    identically with retry disabled or enabled. Missing timings remain missing.
    """
    return PostgresWriterRequest(
        request_signature=request_signature,
        business_connection=business_connection,
        validation_runtime=validation_runtime,
        capacity_admission=capacity_admission,
        retry_policy=retry_policy,
        admission_gate_factory=admission_gate_factory,
        write_side_config=write_side_config,
        wait=wait,
        clock=clock,
        cancelled=cancelled,
        expires_at=expires_at,
        capacity_observer=capacity_observer,
        measure_writer=measure_writer,
    )
