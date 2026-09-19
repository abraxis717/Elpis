"""Version 1: uint32 big-endian length + canonical UTF-8 JSON object.

No recovery/resynchronization is attempted. One request is in flight per worker.
All descriptors used with deadline I/O must be nonblocking.
"""
from __future__ import annotations

import os
import selectors
import struct
import time

from .context import MAX_JSON_BYTES, canonical_bytes, decode_json
from .errors import ContextError, ProtocolError, WorkerTimeout

VERSION = 1
DEFAULT_FRAME_BYTES = 1024 * 1024
HARD_FRAME_BYTES = MAX_JSON_BYTES
OPERATIONS = frozenset({"start", "factory", "acquire", "execute", "release", "close"})


def frame_limit(value: int) -> None:
    if type(value) is not int or not 256 <= value <= HARD_FRAME_BYTES:
        raise ProtocolError("frame limit outside 256..4194304")


def message(operation: str, request_id: int, payload: dict) -> dict:
    result = {"v": VERSION, "op": operation, "id": request_id, "payload": payload}
    validate_message(result)
    return result


def fields(value: object, names: set[str]) -> dict:
    if type(value) is not dict or set(value) != names:
        raise ProtocolError("unexpected payload fields")
    return value


def validate_message(value: object) -> dict:
    fields(value, {"v", "op", "id", "payload"})
    if type(value["v"]) is not int or value["v"] != VERSION:
        raise ProtocolError("protocol version mismatch")
    if type(value["op"]) is not str or value["op"] not in OPERATIONS:
        raise ProtocolError("unknown operation")
    if type(value["id"]) is not int or not 1 <= value["id"] < 2**63:
        raise ProtocolError("invalid request id")
    if type(value["payload"]) is not dict:
        raise ProtocolError("payload must be an object")
    return value


def encode_frame(value: dict, max_bytes: int = DEFAULT_FRAME_BYTES) -> bytes:
    frame_limit(max_bytes)
    validate_message(value)
    try:
        data = canonical_bytes(value, max_bytes=max_bytes)
    except ContextError as exc:
        raise ProtocolError("message exceeds JSON contract/size") from exc
    return struct.pack("!I", len(data)) + data


def decode_payload(data: bytes, max_bytes: int = DEFAULT_FRAME_BYTES) -> dict:
    try:
        value = decode_json(data, max_bytes=max_bytes)
        validate_message(value)
        if canonical_bytes(value, max_bytes=max_bytes) != data:
            raise ProtocolError("wire JSON is not canonical")
        return value
    except ContextError as exc:
        raise ProtocolError("invalid wire JSON") from exc


def _ready(fd: int, event: int, deadline: float) -> None:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise WorkerTimeout("worker pipe deadline exceeded")
    with selectors.DefaultSelector() as selector:
        selector.register(fd, event)
        if not selector.select(remaining):
            raise WorkerTimeout("worker pipe deadline exceeded")


def _read_exact(fd: int, size: int, deadline: float) -> bytes:
    result = bytearray()
    while len(result) < size:
        _ready(fd, selectors.EVENT_READ, deadline)
        try:
            chunk = os.read(fd, min(64 * 1024, size - len(result)))
        except BlockingIOError:
            continue
        except OSError as exc:
            raise ProtocolError("worker pipe read failed") from exc
        if not chunk:
            raise ProtocolError("truncated frame/worker EOF")
        result.extend(chunk)
    return bytes(result)


def read_frame(fd: int, *, deadline: float, max_bytes: int = DEFAULT_FRAME_BYTES) -> dict:
    frame_limit(max_bytes)
    size = struct.unpack("!I", _read_exact(fd, 4, deadline))[0]
    if not 1 <= size <= max_bytes:
        raise ProtocolError("frame size outside bound")
    return decode_payload(_read_exact(fd, size, deadline), max_bytes)


def write_frame(fd: int, value: dict, *, deadline: float,
                max_bytes: int = DEFAULT_FRAME_BYTES) -> None:
    data = memoryview(encode_frame(value, max_bytes))
    while data:
        _ready(fd, selectors.EVENT_WRITE, deadline)
        try:
            written = os.write(fd, data)
        except BlockingIOError:
            continue
        except OSError as exc:
            raise ProtocolError("worker pipe write failed") from exc
        if written <= 0:
            raise ProtocolError("worker pipe closed")
        data = data[written:]


def check_response(value: dict, operation: str, request_id: int) -> dict:
    validate_message(value)
    if value["op"] != operation or value["id"] != request_id:
        raise ProtocolError("response operation/request id mismatch")
    payload = value["payload"]
    if payload.get("ok") is True:
        fields(payload, {"ok", "value"})
    elif payload.get("ok") is False:
        fields(payload, {"ok", "error"})
        error = fields(payload["error"], {"category", "message"})
        if error["category"] not in ("infrastructure", "sandbox", "provider") or type(error["message"]) is not str or len(error["message"]) > 2048:
            raise ProtocolError("invalid error envelope")
    else:
        raise ProtocolError("invalid response envelope")
    return payload
