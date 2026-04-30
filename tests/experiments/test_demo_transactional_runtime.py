from src.pipeline.transactional.registry import OrderRegistry


def test_build_demo_registry_returns_registry():
    from experiments.demo_transactional_runtime import build_demo_registry

    registry = build_demo_registry()

    assert isinstance(registry, OrderRegistry)


def test_demo_registry_can_run_create_and_pay_flow():
    from experiments.demo_transactional_runtime import build_demo_registry

    registry = build_demo_registry()

    created = registry.handle_create("create-001", "order-123", 100.0)
    paid = registry.handle_pay("pay-001", "order-123", 100.0)

    assert created.sequence == 1
    assert paid.sequence == 2

    history = registry.store.load("order-123")
    assert len(history) == 2
    assert history[0] == created
    assert history[1] == paid


def test_demo_registry_create_retry_replays_prior_event():
    from experiments.demo_transactional_runtime import build_demo_registry

    registry = build_demo_registry()

    first = registry.handle_create("create-001", "order-123", 100.0)
    second = registry.handle_create("create-001", "order-123", 100.0)

    assert second == first

    history = registry.store.load("order-123")
    assert len(history) == 1