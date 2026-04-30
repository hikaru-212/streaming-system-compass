from src.bootstrap.build_transactional_runtime import build_transactional_runtime


def build_demo_registry():
    """
    Thin wrapper for local demo usage.

    This file remains under experiments/ because its role is:
    - manual execution
    - smoke-style demo
    - local verification

    The actual runtime composition lives in src/bootstrap/.
    """
    return build_transactional_runtime()


def main() -> None:
    registry = build_demo_registry()

    print("---- create ----")
    print(registry.handle_create("create-001", "order-123", 100.0))

    print("---- pay ----")
    print(registry.handle_pay("pay-001", "order-123", 100.0))

    print("---- retry same pay request ----")
    print(registry.handle_pay("pay-001", "order-123", 100.0))

    print("---- same request_id, different payload -> conflict ----")
    print(registry.handle_pay("pay-001", "order-123", 10.0))


if __name__ == "__main__":
    main()