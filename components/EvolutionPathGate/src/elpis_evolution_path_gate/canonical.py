from __future__ import annotations

import hashlib
from pathlib import Path

from elpis.canonical_identity import (
    canonical_json_bytes as _canonical_json_bytes,
    content_digest,
)


def canonical_json_bytes(obj: object) -> bytes:
    return _canonical_json_bytes(obj)


def domain_digest(domain: str, payload: object) -> str:
    # Elpis2.2.36 integration: structured identities are owned by
    # Canonical Identity v1. EPG payloads are JSON-compatible, so this
    # preserves the extracted Branch46C digest bytes.
    return content_digest(domain, payload)


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
