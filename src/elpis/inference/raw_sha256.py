"""Ordinary SHA-256 for raw deployment bytes, distinct from canonical identity."""
import hashlib

from .contracts import require


def raw_sha256(data=b""):
    require(
        isinstance(data, (bytes, bytearray, memoryview)),
        detail="raw SHA-256 bytes",
    )
    return hashlib.sha256(bytes(data))
