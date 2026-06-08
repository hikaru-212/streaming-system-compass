from decimal import Decimal

from psycopg import Connection

from src.core.order.enums import OrderStatus
from src.core.order.state import OrderState
from src.storage.postgres_projection_store import PostgresProjectionStore


def make_state(
    *,
    order_id: str,
    status: OrderStatus,
    total_amount: Decimal,
    paid_amount: Decimal,
    version: int,
) -> OrderState:
    return OrderState(
        order_id=order_id,
        status=status,
        total_amount=total_amount,
        paid_amount=paid_amount,
        version=version,
    )


def test_load_missing_projection_state_returns_none(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionStore(db_connection)

    state = store.load_state("missing-order")

    assert state is None


def test_save_and_load_created_projection_state(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionStore(db_connection)

    expected = make_state(
        order_id="order-001",
        status=OrderStatus.CREATED,
        total_amount=Decimal("100.00"),
        paid_amount=Decimal("0.00"),
        version=1,
    )

    store.save_state(expected)
    db_connection.commit()

    actual = store.load_state("order-001")

    assert actual == expected


def test_save_and_load_paid_projection_state(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionStore(db_connection)

    expected = make_state(
        order_id="order-001",
        status=OrderStatus.PAID,
        total_amount=Decimal("100.00"),
        paid_amount=Decimal("100.00"),
        version=2,
    )

    store.save_state(expected)
    db_connection.commit()

    actual = store.load_state("order-001")

    assert actual == expected


def test_save_state_upserts_existing_projection_state(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionStore(db_connection)

    created = make_state(
        order_id="order-001",
        status=OrderStatus.CREATED,
        total_amount=Decimal("100.00"),
        paid_amount=Decimal("0.00"),
        version=1,
    )
    paid = make_state(
        order_id="order-001",
        status=OrderStatus.PAID,
        total_amount=Decimal("100.00"),
        paid_amount=Decimal("100.00"),
        version=2,
    )

    store.save_state(created)
    store.save_state(paid)
    db_connection.commit()

    actual = store.load_state("order-001")

    assert actual == paid

    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM projection_states
            WHERE order_id = %s
            """,
            ("order-001",),
        )
        row = cursor.fetchone()

    assert row is not None
    assert row[0] == 1


def test_save_state_preserves_decimal_values(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionStore(db_connection)

    expected = make_state(
        order_id="order-decimal",
        status=OrderStatus.PAID,
        total_amount=Decimal("123.45"),
        paid_amount=Decimal("123.45"),
        version=2,
    )

    store.save_state(expected)
    db_connection.commit()

    actual = store.load_state("order-decimal")

    assert actual is not None
    assert actual.total_amount == Decimal("123.45")
    assert actual.paid_amount == Decimal("123.45")


def test_save_state_persists_last_sequence_from_state_version(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionStore(db_connection)

    state = make_state(
        order_id="order-sequence",
        status=OrderStatus.PAID,
        total_amount=Decimal("100.00"),
        paid_amount=Decimal("100.00"),
        version=2,
    )

    store.save_state(state)
    db_connection.commit()

    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT version, last_sequence
            FROM projection_states
            WHERE order_id = %s
            """,
            ("order-sequence",),
        )
        row = cursor.fetchone()

    assert row is not None
    version, last_sequence = row

    assert version == 2
    assert last_sequence == 2


def test_clear_removes_projection_states(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionStore(db_connection)

    state = make_state(
        order_id="order-001",
        status=OrderStatus.CREATED,
        total_amount=Decimal("100.00"),
        paid_amount=Decimal("0.00"),
        version=1,
    )

    store.save_state(state)
    db_connection.commit()

    assert store.load_state("order-001") is not None

    store.clear()
    db_connection.commit()

    assert store.load_state("order-001") is None


def test_multiple_orders_do_not_overwrite_each_other(
    db_connection: Connection,
    clean_database: None,
) -> None:
    store = PostgresProjectionStore(db_connection)

    order_a = make_state(
        order_id="order-a",
        status=OrderStatus.CREATED,
        total_amount=Decimal("100.00"),
        paid_amount=Decimal("0.00"),
        version=1,
    )
    order_b = make_state(
        order_id="order-b",
        status=OrderStatus.PAID,
        total_amount=Decimal("200.00"),
        paid_amount=Decimal("200.00"),
        version=2,
    )

    store.save_state(order_a)
    store.save_state(order_b)
    db_connection.commit()

    assert store.load_state("order-a") == order_a
    assert store.load_state("order-b") == order_b