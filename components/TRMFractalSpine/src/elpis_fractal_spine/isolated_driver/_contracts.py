"""Strict primitive wire forms of the existing four provider dataclasses."""
from dataclasses import fields as dataclass_fields

from ..contracts import (
    InferenceExecutionRequest, InferenceExecutionResult, ModelResidencyBinding,
    ModelResidencyRequest, ResidencyAbsentPolicy,
)
from .context import canonical_bytes, decode_json
from .errors import ContextError, ProtocolError
from .protocol import fields

_SCHEMAS = {
    ModelResidencyRequest: {"model_id": str, "preferred_tier": str, "absent_policy": str},
    ModelResidencyBinding: {"model_id": str, "requested_tier": str, "actual_tier": str,
                            "backend_id": str, "device_id": str, "binding_id": str},
    InferenceExecutionRequest: {"request_id": str, "model_id": str, "input_space": str,
                                "output_space": str, "input_payload": list,
                                "model_path": (str, type(None)), "max_steps": int},
    InferenceExecutionResult: {"status": str, "output_payload": (list, type(None)),
                               "iteration_count": int, "backend_id": str,
                               "device_id": str, "residency_tier": str},
}


def from_wire(kind: type, value: object) -> object:
    schema = _SCHEMAS[kind]
    fields(value, set(schema))
    for name, expected in schema.items():
        allowed = expected if type(expected) is tuple else (expected,)
        if type(value[name]) not in allowed:
            raise ProtocolError(f"invalid contract field type: {name}")
    try:
        canonical_bytes(value)
        kwargs = dict(value)
        if kind is ModelResidencyRequest:
            kwargs["absent_policy"] = ResidencyAbsentPolicy(kwargs["absent_policy"])
        for name in ("input_payload", "output_payload"):
            if name in kwargs and kwargs[name] is not None:
                kwargs[name] = tuple(kwargs[name])
        return kind(**kwargs)
    except (ValueError, TypeError, ContextError) as exc:
        raise ProtocolError("invalid provider dataclass") from exc


def to_wire(value: object, kind: type) -> dict:
    if type(value) is not kind:
        raise ProtocolError("provider value has unexpected dataclass type")
    result = {field.name: getattr(value, field.name) for field in dataclass_fields(kind)}
    if kind is ModelResidencyRequest:
        if type(result["absent_policy"]) is not ResidencyAbsentPolicy:
            raise ProtocolError("invalid residency absent policy")
        result["absent_policy"] = result["absent_policy"].value
    try:
        result = decode_json(canonical_bytes(result))
    except ContextError as exc:
        raise ProtocolError("provider contract is not bounded JSON") from exc
    from_wire(kind, result)
    return result
