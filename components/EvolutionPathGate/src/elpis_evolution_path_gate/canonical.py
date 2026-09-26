from __future__ import annotations

import hashlib
import json
from pathlib import Path


def canonical_json_bytes(obj: object) -> bytes:
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def domain_digest(domain: str, payload: object) -> str:
    return hashlib.sha256(
        domain.encode("utf-8") + b"\x00" + canonical_json_bytes(payload)
    ).hexdigest()


def require_digest(value: str) -> None:
    if type(value) is not str or len(value) != 64:
        raise ValueError("digest must be 64 lowercase hex characters")
    if any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError("digest must be lowercase hex")


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
