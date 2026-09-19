from __future__ import annotations

import os
import struct
import time

import pytest

from elpis_fractal_spine.contracts import (ModelResidencyRequest, ModelResidencyBinding,
                                         InferenceExecutionRequest, InferenceExecutionResult)
from elpis_fractal_spine.isolated_driver._contracts import from_wire, to_wire
from elpis_fractal_spine.isolated_driver.errors import ProtocolError, WorkerTimeout
from elpis_fractal_spine.isolated_driver.protocol import (
    check_response, decode_payload, encode_frame, message, read_frame, write_frame,
)


def read_bytes(data, *, keep_open=False):
    reader, writer = os.pipe()
    os.set_blocking(reader, False)
    try:
        os.write(writer, data)
        if not keep_open:
            os.close(writer)
            writer = None
        return read_frame(reader, deadline=time.monotonic() + 0.1)
    finally:
        os.close(reader)
        if writer is not None:
            os.close(writer)


def test_canonical_frame_roundtrip():
    value = message("execute", 3, {"b": [1, True], "a": "utf8:ž"})
    encoded = encode_frame(value)
    assert encoded == encode_frame(dict(reversed(list(value.items()))))
    assert read_bytes(encoded) == value


@pytest.mark.parametrize("data", [b"", b"\0", b"\0\0\0", struct.pack("!I", 0),
                                 struct.pack("!I", 0xFFFFFFFF), struct.pack("!I", 4) + b"{}"])
def test_invalid_and_truncated_frames(data):
    with pytest.raises(ProtocolError):
        read_bytes(data)


def test_oversize_header_rejected_before_payload_read():
    start = time.monotonic()
    with pytest.raises(ProtocolError, match="size"):
        read_bytes(struct.pack("!I", 1024 * 1024 + 1), keep_open=True)
    assert time.monotonic() - start < 0.1


@pytest.mark.parametrize("payload", [b"\xff", b"no-json", b"[]", b"null", b"{}", b'{"x":NaN}',
    b'{"id":1,"op":"close","payload":{},"v":2}',
    b'{"id":1,"op":"eval","payload":{},"v":1}',
    b'{"id":true,"op":"close","payload":{},"v":1}',
    b'{"id":1,"op":"close","payload":[],"v":1}',
    b'{"id":1,"id":1,"op":"close","payload":{},"v":1}',
    b'{"id":1,"op":"close","payload":{},"v":1,"extra":0}',
    b'{ "id":1,"op":"close","payload":{},"v":1}',
])
def test_invalid_json_schema_and_version(payload):
    with pytest.raises(ProtocolError):
        decode_payload(payload)


def test_crossed_response_and_error_schema():
    for operation, sequence, payload in [("acquire", 4, {"ok": True, "value": None}),
                                         ("execute", 3, {"ok": True, "value": None}),
                                         ("execute", 4, {"ok": 1, "value": None}),
                                         ("execute", 4, {"ok": True, "value": None, "extra": 0}),
                                         ("execute", 4, {"ok": False, "error": {"category": "import.me", "message": "x"}})]:
        with pytest.raises(ProtocolError):
            check_response(message(operation, sequence, payload), "execute", 4)


def test_read_and_write_deadlines():
    reader, writer = os.pipe()
    os.set_blocking(reader, False)
    os.set_blocking(writer, False)
    try:
        with pytest.raises(WorkerTimeout):
            read_frame(reader, deadline=time.monotonic() + 0.02)
        while True:
            try:
                os.write(writer, b"x" * 4096)
            except BlockingIOError:
                break
        with pytest.raises(WorkerTimeout):
            write_frame(writer, message("close", 1, {}), deadline=time.monotonic() + 0.02)
    finally:
        os.close(reader)
        os.close(writer)


@pytest.mark.parametrize("value", [ModelResidencyRequest("test-model"),
    ModelResidencyBinding("test-model", "HOT", "HOT", "backend", "cpu", "binding"),
    InferenceExecutionRequest("request", "test-model", "in", "out", (1, 2), None, 1),
    InferenceExecutionResult("OK", (1, 2), 1, "backend", "cpu", "HOT")])
def test_existing_dataclass_roundtrips_and_extra_field_rejection(value):
    wire = to_wire(value, type(value))
    assert from_wire(type(value), wire) == value
    with pytest.raises(ProtocolError):
        from_wire(type(value), {**wire, "extra": "forbidden"})


@pytest.mark.parametrize("change", [{"iteration_count": -1}, {"iteration_count": True},
                                    {"backend_id": ""}, {"residency_tier": "invalid"},
                                    {"output_payload": b"bytes"}])
def test_dataclass_validators_and_wire_types(change):
    wire = to_wire(InferenceExecutionResult("OK", (1,), 0, "b", "cpu", "HOT"), InferenceExecutionResult)
    with pytest.raises(ProtocolError):
        from_wire(InferenceExecutionResult, {**wire, **change})


def test_hard_frame_ceiling_and_encoded_size():
    with pytest.raises(ProtocolError):
        encode_frame(message("execute", 1, {}), 4 * 1024 * 1024 + 1)
    with pytest.raises(ProtocolError):
        encode_frame(message("execute", 1, {"value": "ž" * 200}), 256)
