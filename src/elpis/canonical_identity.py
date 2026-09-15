# Cross-component canonical content identity v1.
#
# New cross-component identities use:
# SHA256(UTF8(domain) || NUL || canonical_json_bytes(payload)).
# Historical protocol/domain digests retain their existing semantics until an
# explicit versioned migration.

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
import hashlib
import json
import math
from typing import Any


class CanonicalIdentityError(ValueError):
    pass


def _normalize(value: Any) -> Any:
    if is_dataclass(value):
        return _normalize(asdict(value))
    if isinstance(value, Enum):
        return _normalize(value.value)
    if isinstance(value, bytes):
        return {"__bytes__": value.hex()}
    if isinstance(value, tuple):
        return [_normalize(item) for item in value]
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        if any(type(key) is not str for key in value):
            raise CanonicalIdentityError("CANONICAL_MAP_KEY_NOT_STRING")
        return {key: _normalize(value[key]) for key in sorted(value)}
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise CanonicalIdentityError("CANONICAL_NONFINITE_FLOAT")
        return value
    raise CanonicalIdentityError(
        f"CANONICAL_UNSUPPORTED_TYPE:{type(value).__name__}"
    )


def canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            _normalize(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except CanonicalIdentityError:
        raise
    except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError) as exc:
        raise CanonicalIdentityError(
            f"CANONICAL_SERIALIZATION_FAILED:{exc}"
        ) from exc


def domain_framed_bytes(domain: str, value: Any) -> bytes:
    if type(domain) is not str or not domain:
        raise CanonicalIdentityError("CANONICAL_DOMAIN_INVALID")
    if "\x00" in domain:
        raise CanonicalIdentityError("CANONICAL_DOMAIN_CONTAINS_NUL")
    return domain.encode("utf-8") + b"\x00" + canonical_json_bytes(value)


def content_digest(domain: str, value: Any) -> str:
    return hashlib.sha256(domain_framed_bytes(domain, value)).hexdigest()
