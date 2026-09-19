"""Bounded deterministic JSON, shared by context and the wire codec."""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from types import MappingProxyType

from elpis.canonical_identity import content_digest

from .errors import ContextError

MAX_DEPTH = 32
MAX_ELEMENTS = 100_000
MAX_JSON_BYTES = 4 * 1024 * 1024
DEFAULT_CONTEXT_BYTES = 1024 * 1024
MIN_INT = -(2**63)
MAX_INT = 2**63 - 1


def canonical_bytes(value: object, *, max_bytes: int = MAX_JSON_BYTES) -> bytes:
    """Accept builtins and mappingproxy only; never invoke custom serializers.

    Integers are signed 64 bit. Tuples normalize to arrays. Container depth,
    total values/keys, and encoded UTF-8 size are independently bounded.
    """
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_JSON_BYTES:
        raise ContextError("invalid JSON byte limit")
    active: set[int] = set()
    count = 0
    size = 0

    def visit(item: object, depth: int) -> object:
        nonlocal count, size
        count += 1
        if count > MAX_ELEMENTS or depth > MAX_DEPTH:
            raise ContextError("JSON element/depth limit exceeded")
        kind = type(item)
        if item is None or kind is bool:
            size += 5 if item is False else 4
        elif kind is int:
            if not MIN_INT <= item <= MAX_INT:
                raise ContextError("integer outside signed 64-bit range")
            size += len(str(item))
        elif kind is float:
            if not math.isfinite(item):
                raise ContextError("non-finite float")
            size += len(json.dumps(item))
        elif kind is str:
            # Bound before allocating an escaped representation of a huge string.
            if len(item) > max_bytes:
                raise ContextError("JSON byte limit exceeded")
            try:
                size += len(json.dumps(item, ensure_ascii=False).encode("utf-8"))
            except UnicodeError as exc:
                raise ContextError("string is not valid UTF-8") from exc
        elif kind in (dict, MappingProxyType, list, tuple):
            identity = id(item)
            if identity in active:
                raise ContextError("cyclic JSON container")
            active.add(identity)
            size += 2 + max(0, len(item) - 1)
            try:
                if kind in (dict, MappingProxyType):
                    result = {}
                    for key, child in item.items():
                        if type(key) is not str:
                            raise ContextError("object keys must be strings")
                        visit(key, depth + 1)
                        size += 1
                        result[key] = visit(child, depth + 1)
                else:
                    result = [visit(child, depth + 1) for child in item]
            finally:
                active.remove(identity)
            if size > max_bytes:
                raise ContextError("JSON byte limit exceeded")
            return result
        else:
            raise ContextError("unsupported JSON value type")
        if size > max_bytes:
            raise ContextError("JSON byte limit exceeded")
        return item

    normalized = visit(value, 0)
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(encoded) > max_bytes:
        raise ContextError("JSON byte limit exceeded")
    return encoded


def decode_json(data: bytes, *, max_bytes: int = MAX_JSON_BYTES) -> object:
    if type(data) is not bytes or not data or len(data) > max_bytes:
        raise ContextError("invalid JSON byte length")

    def pairs(items: list) -> dict:
        result = {}
        for key, value in items:
            if key in result:
                raise ContextError("duplicate JSON key")
            result[key] = value
        return result

    def bad_constant(value: str) -> None:
        raise ContextError("non-finite JSON constant")

    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=bad_constant)
        canonical_bytes(value, max_bytes=max_bytes)
        return value
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ContextError("invalid JSON encoding") from exc


@dataclass(frozen=True)
class CanonicalContext:
    data: bytes

    def __post_init__(self) -> None:
        value = decode_json(self.data, max_bytes=DEFAULT_CONTEXT_BYTES)
        if type(value) is not dict or canonical_bytes(value) != self.data:
            raise ContextError("context must be a canonical JSON object")

    @property
    def digest(self) -> str:
        return content_digest(
            "elpis.inference.isolated.runtime-context.v1",
            self.decode(),
        )

    def decode(self) -> dict:
        return decode_json(self.data, max_bytes=DEFAULT_CONTEXT_BYTES)


def canonicalize_context(value: object) -> CanonicalContext:
    return CanonicalContext(canonical_bytes(value, max_bytes=DEFAULT_CONTEXT_BYTES))
