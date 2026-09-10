"""Guarded future PR4 PostgreSQL composition; importing performs no database I/O.

Calling this factory requires separate live-run authorization. Retained lane
connections are never reduced to the writer bound. No pool or arrival policy.
"""

from contextlib import ExitStack, contextmanager
import os

from psycopg.conninfo import conninfo_to_dict
from psycopg.pq import TransactionStatus

from experiments.load_capacity_protection.evidence import ConnectionFact, RuntimeProvenance, idempotency_evidence
from experiments.load_capacity_protection.model import LoadDurableStatus
from experiments.load_capacity_protection.postgres_runtime import PostgresLoadLane
from experiments.load_capacity_protection.pr4_characterization import ObservedAdmission
from experiments.load_capacity_protection.pr4_model import ProtectionMode, VerificationEvidence, prepare_workload
from experiments.load_capacity_protection.pr4_runner import PreparedRuntime
from experiments.load_capacity_protection.runner import _problem, _require_empty
from src.storage.postgres_connection import connect_postgres
from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_idempotency_store import PostgresIdempotencyStore


def cleanup_accepted_rows(control, plan, scheduled, accepted):
    """Delete exact verified accepted pairs only, after caller-owned quiescence.

The runner verifies the entire cell before calling. This helper checks declared
identity membership and test database again. Refused identities never enter this
deletion list. Physical storage, WAL, sequences and caches remain unrestored.
"""
    workload = prepare_workload(plan, scheduled)
    allowed = {item.workload_index: item for item in workload}
    if (type(accepted) is not tuple or len({i.workload_index for i in accepted}) != len(accepted)
            or any(allowed.get(i.workload_index) != i for i in accepted)):
        raise ValueError("cleanup requires exact declared identity subset")
    if control.autocommit:
        raise ValueError("cleanup requires autocommit disabled")
    control.rollback()
    with control.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        if cursor.fetchone()[0] != plan.test_database:
            raise ValueError("cleanup connection differs from declared test database")
    control.rollback()
    if accepted:
        with control.transaction():
            with control.cursor() as cursor:
                for table in ("idempotency_records", "order_events"):
                    for item in accepted:
                        cursor.execute(
                            f"DELETE FROM {table} WHERE request_id = %s AND order_id = %s",
                            (item.signature.request_id, item.signature.order_id),
                        )
    _require_empty(control, workload)


@contextmanager
def postgres_runtime(plan, scheduled, workload, admission):
    """Open N lane connections and one control in the declared test database.

TEST_DATABASE_URL is consumed only on explicit factory execution; never recorded.
Every opened connection is guarded and closed even after partial setup failure.
The supplied shared observer is injected unchanged into every protected lane.
"""
    if workload != prepare_workload(plan, scheduled):
        raise ValueError("runtime workload differs from declaration")
    if scheduled.protection.mode is ProtectionMode.PROTECTED:
        if not isinstance(admission, ObservedAdmission) or admission.bound != plan.protection_bound:
            raise ValueError("declared shared admission required")
    elif admission is not None:
        raise ValueError("unprotected capacity_admission must be None")
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        raise ValueError("TEST_DATABASE_URL is required")
    if conninfo_to_dict(database_url).get("dbname") != plan.test_database:
        raise ValueError("TEST_DATABASE_URL does not name declared test database")
    facts = []
    with ExitStack() as resources:
        def connect(lane_id):
            connection = connect_postgres(database_url, connect_timeout_seconds=plan.connect_timeout_seconds)
            resources.callback(connection.close)
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_database(), current_setting('transaction_isolation')")
                database, isolation = cursor.fetchone()
            if database != plan.test_database or not database.endswith("_test"):
                raise ValueError("connected database differs from declared test database")
            if connection.autocommit:
                raise ValueError("retained connections require autocommit disabled")
            connection.rollback()
            if connection.info.transaction_status is not TransactionStatus.IDLE:
                raise ValueError("connection is not idle after guard")
            facts.append(ConnectionFact(
                lane_id, database, connection.info.server_version, connection.info.backend_pid,
                isolation, connection.autocommit,
            ))
            return connection

        control = connect(None)
        _require_empty(control, workload)
        lanes = tuple(PostgresLoadLane(i, connect(i), capacity_admission=admission)
                      for i in range(scheduled.identity.configured_concurrency))
        if len({fact.backend_pid for fact in facts}) != len(facts):
            raise ValueError("lane and control connections must be distinct")

        def verify(item):
            control.rollback()
            history, decision, count, idempotency_count = (), None, None, None
            try:
                history = tuple(PostgresEventStore(control).load(item.signature.order_id))
                decision = idempotency_evidence(PostgresIdempotencyStore(control).check(item.signature))
                with control.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM order_events WHERE request_id = %s",
                                   (item.signature.request_id,))
                    count = cursor.fetchone()[0]
                    cursor.execute(
                        "SELECT COUNT(*) FROM idempotency_records WHERE request_id = %s OR order_id = %s",
                        (item.signature.request_id, item.signature.order_id),
                    )
                    idempotency_count = cursor.fetchone()[0]
                return VerificationEvidence(
                    LoadDurableStatus.PRESENT if history or count else LoadDurableStatus.ABSENT,
                    history, decision, count, (), identity_idempotency_count=idempotency_count,
                )
            except Exception as error:
                return VerificationEvidence(
                    LoadDurableStatus.UNKNOWN, history, decision, count, ("verification_unavailable",),
                    _problem("verification", error), identity_idempotency_count=idempotency_count,
                )

        runtime = lanes[0].validation_runtime
        def name(value):
            return f"{type(value).__module__}.{type(value).__name__}"
        provenance = RuntimeProvenance(
            tuple(facts), lanes[0].config.validation_placement.value,
            "src.pipeline.transactional.postgres_admission.PostgresOptimisticAdmissionGate",
            runtime.mode.value, name(runtime), name(runtime.dispatcher.strict_validator),
        )
        yield PreparedRuntime(
            lanes, provenance, name(runtime.policy), verify,
            lambda accepted: cleanup_accepted_rows(control, plan, scheduled, accepted),
        )
