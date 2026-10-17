"""Strict PR9 JSON codec; no PR5 schema changes or executable type loading."""

from dataclasses import fields, is_dataclass
from decimal import Decimal
from enum import Enum
import json
from types import UnionType
from typing import get_args, get_origin, get_type_hints
from uuid import UUID

from experiments.load_capacity_protection import pr9_model as model
from src.core.order.enums import CommandType, EventType, OrderStatus
from src.core.order.events import OrderEvent
from src.core.order.proofs import Proof
from src.pipeline.postgres_writer_request import WriterRetryEventKind, WriterRetryObservation
from src.pipeline.transactional.admission import AdmissionVerdict
from src.pipeline.transactional.postgres_write_side import PostgresWriteSideOutcome
from src.pipeline.transactional.postgres_write_side_measurement import (
    PostgresWriteSideMeasurement, PostgresWriteSideMeasurementAvailability,
    PostgresWriteSidePhaseMeasurement, PostgresWriteSidePhaseMeasurementState,
)
from src.pipeline.transactional.writer_capacity import (
    WriterAttemptIdentity, WriterCapacityEventKind, WriterCapacityObservation, WriterCapacityObservationFailure,
)
from src.pipeline.writer_retry_policy import WriterRetryPolicy
from src.storage.idempotency_store import IdempotencyVerdict, RequestSignature


_TYPES = (
    model.Plan, model.Cell, model.Source, model.ConnectionEvidence, model.ResultEvidence,
    model.MeasurementEvidence, model.WaitEvidence, model.DurableEvidence, model.RequestEvidence,
    model.CellEvidence, model.UnobservedRequestEvidence, model.RunEvidence, OrderEvent, Proof, RequestSignature, WriterRetryPolicy,
    WriterRetryObservation, WriterAttemptIdentity, WriterCapacityObservation, WriterCapacityObservationFailure,
    PostgresWriteSideMeasurement, PostgresWriteSidePhaseMeasurement,
    CommandType, EventType, OrderStatus, WriterRetryEventKind, AdmissionVerdict, PostgresWriteSideOutcome,
    PostgresWriteSideMeasurementAvailability, PostgresWriteSidePhaseMeasurementState,
    WriterCapacityEventKind, IdempotencyVerdict,
)
_REGISTRY = {t.__name__: t for t in _TYPES}


def _encode(value):
    if isinstance(value, Enum):
        return {"type": type(value).__name__, "value": value.value}
    if isinstance(value, (UUID, Decimal)):
        return {"type": type(value).__name__, "value": str(value)}
    if type(value) is tuple:
        return {"type": "tuple", "value": [_encode(item) for item in value]}
    if is_dataclass(value) and type(value) in _TYPES:
        return {"type": type(value).__name__, "value": {f.name: _encode(getattr(value, f.name)) for f in fields(value)}}
    if value is None or type(value) in (str, bool, int, float):
        return value
    raise TypeError("unregistered evidence type")


def _matches(value, annotation):
    origin, args = get_origin(annotation), get_args(annotation)
    if origin is UnionType or str(origin) == "typing.Union":
        return any(_matches(value, member) for member in args)
    if origin is tuple:
        return type(value) is tuple and all(_matches(item, args[0]) for item in value)
    return type(value) is annotation


def _decode(value):
    if not isinstance(value, dict):
        if value is None or type(value) in (str, bool, int, float):
            return value
        raise ValueError("untagged container")
    if set(value) != {"type", "value"}:
        raise ValueError("invalid tagged evidence")
    name, raw = value["type"], value["value"]
    if name == "tuple":
        if type(raw) is not list:
            raise ValueError("tuple payload must be a list")
        return tuple(_decode(item) for item in raw)
    if name in ("UUID", "Decimal"):
        if type(raw) is not str:
            raise ValueError("invalid scalar")
        result = UUID(raw) if name == "UUID" else Decimal(raw)
        if isinstance(result, Decimal) and not result.is_finite():
            raise ValueError("nonfinite decimal")
        return result
    cls = _REGISTRY.get(name)
    if cls is None:
        raise ValueError("unknown evidence type")
    if issubclass(cls, Enum):
        return cls(raw)
    if type(raw) is not dict or set(raw) != {f.name for f in fields(cls)}:
        raise ValueError("evidence fields differ from schema")
    decoded = {key: _decode(item) for key, item in raw.items()}
    hints = get_type_hints(cls)
    if any(not _matches(item, hints[key]) for key, item in decoded.items()):
        raise ValueError("evidence field type mismatch")
    return cls(**decoded)


def dumps_evidence(evidence: model.RunEvidence) -> str:
    if type(evidence) is not model.RunEvidence:
        raise TypeError("PR9 RunEvidence required")
    return json.dumps({"method": model.METHOD, "schema": model.SCHEMA, "evidence": _encode(evidence)},
                      indent=2, sort_keys=True, allow_nan=False) + "\n"


def loads_evidence(text: str) -> model.RunEvidence:
    def reject(value):
        raise ValueError("nonfinite JSON value")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    envelope = json.loads(text, parse_constant=reject, object_pairs_hook=unique)
    if (type(envelope) is not dict or set(envelope) != {"method", "schema", "evidence"}
            or envelope["method"] != model.METHOD or type(envelope["schema"]) is not int
            or envelope["schema"] != model.SCHEMA):
        raise ValueError("not PR9 method/schema evidence")
    result = _decode(envelope["evidence"])
    if type(result) is not model.RunEvidence:
        raise ValueError("PR9 RunEvidence required")
    return result
