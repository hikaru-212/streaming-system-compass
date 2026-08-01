"""Immutable identity for the repaired durable order-state projection."""

from typing import Final


ORDER_STATE_PROJECTION_NAME: Final[str] = "order_state_projection"
"""Stable projection-definition name for the current order-state reducer."""

ORDER_STATE_PROJECTION_EPOCH: Final[int] = 1
"""Only supported production epoch for repaired per-order progress."""


def require_current_order_state_projection(
    *,
    projection_name: str,
    projection_epoch: int,
) -> None:
    """Require the one projection definition supported by production.

    Responsibility:
    - validate that a PostgreSQL projection operation targets
      ``order_state_projection`` epoch 1.

    Inputs:
    - ``projection_name``: requested projection-definition identity;
    - ``projection_epoch``: requested repaired progress epoch.

    Output:
    - ``None`` when both values match the immutable production constants;
    - ``ValueError`` before database access for any unsupported value.

    Invariants:
    - the current ``projection_states`` table is shared and keyed only by
      ``order_id``;
    - epoch 1 prevents legacy progress reinterpretation but does not provide a
      general multi-version runtime.

    Non-goals:
    - selecting a projection dynamically;
    - supporting concurrent epochs or parallel rebuilds;
    - performing a derived-state reset or migration.
    """
    if projection_name != ORDER_STATE_PROJECTION_NAME:
        raise ValueError(
            "unsupported projection_name; expected "
            f"{ORDER_STATE_PROJECTION_NAME!r}"
        )
    if projection_epoch != ORDER_STATE_PROJECTION_EPOCH:
        raise ValueError(
            "unsupported projection_epoch; expected "
            f"{ORDER_STATE_PROJECTION_EPOCH}"
        )
