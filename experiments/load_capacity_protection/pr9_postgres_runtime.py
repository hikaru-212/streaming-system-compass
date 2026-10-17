"""Guarded PR9 retained-connection fixture; import performs no database I/O.

Executing this factory requires a separately approved live plan. There is no
schema setup, migration, cleanup, pool or row deletion in this module.
"""

from contextlib import contextmanager
from dataclasses import dataclass, replace
import os

from psycopg.conninfo import conninfo_to_dict
from psycopg.pq import TransactionStatus

from experiments.load_capacity_protection.pr9_characterization import ProductionLane
from experiments.load_capacity_protection.pr9_model import ConnectionEvidence, DurableEvidence
from src.storage.postgres_connection import connect_postgres
from src.storage.postgres_event_store import PostgresEventStore
from src.storage.postgres_idempotency_store import PostgresIdempotencyStore
from src.storage.idempotency_store import IdempotencyVerdict


@dataclass
class PreparedRuntime:
    lanes: tuple
    connections: list[ConnectionEvidence]
    verify: object


def read_durable(control, signature):
    """Read history, raw identity counts and exact idempotency linkage after drain.

    Partial/unavailable reads remain unknown, never inferred absence. Only the
    separate control connection is used. Provider messages and DSNs are omitted.
    """
    history, event_count, idem_count, verdict, idem_signature, event = (), None, None, None, None, None
    failure = None
    try:
        control.rollback()
        history = tuple(PostgresEventStore(control).load(signature.order_id))
        decision = PostgresIdempotencyStore(control).check(signature)
        verdict = decision.verdict
        if decision.record is not None:
            idem_signature, event = decision.record.signature, decision.record.accepted_event
        with control.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM order_events WHERE request_id = %s", (signature.request_id,))
            event_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM idempotency_records WHERE request_id = %s OR order_id = %s",
                           (signature.request_id, signature.order_id))
            idem_count = cursor.fetchone()[0]
    except Exception as error:
        failure = type(error).__name__
    finally:
        try:
            control.rollback()
        except Exception as error:
            failure = failure or type(error).__name__
    return DurableEvidence(history, event_count, idem_count, verdict, idem_signature, event, failure)


def require_fresh(evidence):
    """Reject contaminated or unverified fixtures before any writer dispatch."""
    if (evidence.failure is not None or evidence.accepted_events or evidence.request_event_count != 0
            or evidence.identity_idempotency_count != 0 or evidence.idempotency_verdict is not IdempotencyVerdict.MISS
            or evidence.idempotency_signature is not None or evidence.idempotency_event is not None):
        raise ValueError("fixture identities are not verified fresh")


@contextmanager
def postgres_runtime(plan, cell, signatures, clock_ns):
    """Open N exclusive retained lane connections plus one verification control.

    TEST_DATABASE_URL is read only on explicit factory execution and never enters
    evidence. Every connection must name the declared *_test fixture. All opened
    resources close after quiescence, including partial setup failures. Rows are
    retained; a future cleanup requires separate exact authorization.
    """
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url or conninfo_to_dict(database_url).get("dbname") != plan.test_database:
        raise ValueError("TEST_DATABASE_URL must name the declared test database")
    connections, facts = [], []
    def timestamp():
        try:
            value = clock_ns()
            return value if type(value) is int and value >= 0 else None
        except BaseException:
            return None
    try:
        def connect(lane):
            connection = connect_postgres(database_url, connect_timeout_seconds=plan.connect_timeout_seconds)
            connections.append(connection)
            opened = timestamp()
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_database(), current_setting('transaction_isolation')")
                database, isolation = cursor.fetchone()
            if database != plan.test_database or not database.endswith("_test") or connection.autocommit:
                raise ValueError("connection fixture or autocommit mismatch")
            connection.rollback()
            if connection.info.transaction_status != TransactionStatus.IDLE:
                raise ValueError("connection is not idle after fixture guard")
            facts.append(ConnectionEvidence(lane, id(connection), connection.info.backend_pid, database,
                connection.info.server_version, isolation, connection.autocommit, opened))
            return connection

        control = connect(None)
        for signature in signatures:
            require_fresh(read_durable(control, signature))
        lanes = tuple(ProductionLane(index, connect(index)) for index in range(cell.concurrency))
        if len({f.backend_pid for f in facts}) != len(facts):
            raise ValueError("distinct lane and control backends required")
        yield PreparedRuntime(lanes, facts, lambda signature: read_durable(control, signature))
    finally:
        for connection in reversed(connections):
            failure = None
            try:
                connection.close()
            except Exception as error:
                failure = type(error).__name__
            for index, fact in enumerate(facts):
                if fact.connection_id == id(connection):
                    facts[index] = replace(fact, closed_ns=timestamp() if failure is None else None,
                                           close_failure=failure)
