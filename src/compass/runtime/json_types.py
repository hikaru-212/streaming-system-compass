from __future__ import annotations

import math
from types import MappingProxyType
from typing import Mapping, TypeAlias


JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | tuple["JsonValue", ...] | Mapping[str, "JsonValue"]
JsonObject: TypeAlias = Mapping[str, JsonValue]


MAX_JSON_DEPTH = 32


def ensure_json_object(
    value: Mapping[str, object],
    *,
    field_name: str = "value",
    depth: int = 0,
) -> JsonObject:
    """
    Return an immutable JSON-safe object mapping.

    This helper accepts only JSON-compatible values and recursively freezes
    mappings and sequences so runtime governance evidence cannot be mutated
    after a contract object is constructed.

    The depth limit is intentional contract hardening. Receipt evidence must be
    finite, bounded, JSON-safe summary evidence rather than an arbitrary object
    graph or unbounded recursive payload.
    """

    _require_json_depth(depth, field_name)

    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")

    return MappingProxyType(
        {
            _ensure_json_key(key, field_name): ensure_json_value(
                item,
                field_name=f"{field_name}.{key}",
                depth=depth + 1,
            )
            for key, item in value.items()
        }
    )


def ensure_json_value(
    value: object,
    *,
    field_name: str = "value",
    depth: int = 0,
) -> JsonValue:
    """
    Validate and freeze a JSON-safe value.

    Accepted values are JSON primitives, lists / tuples of JSON-safe values,
    and mappings with string keys and JSON-safe values.

    This helper intentionally rejects Python runtime objects, arbitrary object
    graphs, non-finite floats, non-string mapping keys, and overly deep nested
    payloads.
    """

    _require_json_depth(depth, field_name)

    if value is None:
        return None

    if isinstance(value, str):
        return value

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{field_name} must be a finite JSON number")
        return value

    if isinstance(value, Mapping):
        return ensure_json_object(
            value,
            field_name=field_name,
            depth=depth,
        )

    if isinstance(value, (list, tuple)):
        return tuple(
            ensure_json_value(
                item,
                field_name=f"{field_name}[{index}]",
                depth=depth + 1,
            )
            for index, item in enumerate(value)
        )

    raise TypeError(f"{field_name} must be JSON-safe")


def _require_json_depth(depth: int, field_name: str) -> None:
    if depth > MAX_JSON_DEPTH:
        raise ValueError(
            f"{field_name} exceeds maximum JSON depth of {MAX_JSON_DEPTH}"
        )


def _ensure_json_key(key: object, field_name: str) -> str:
    if not isinstance(key, str):
        raise TypeError(f"{field_name} keys must be strings")
    if not key:
        raise ValueError(f"{field_name} keys must be non-empty strings")
    return key