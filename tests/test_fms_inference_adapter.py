from __future__ import annotations

import ctypes
import hashlib
import importlib.util
import os
from pathlib import Path
import pytest

from elpis_fractal_spine.contracts import (
    ModelResidencyRequest,
    ResidencyAbsentPolicy,
)
from elpis_reference.fms_inference_adapter import (
    _FMS_E_UNSUPPORTED, _LeaseReader, _NativeFMS,
)


def _bridge():
    raw = os.environ.get("ELPIS_FMS_INFERENCE_BRIDGE")
    return Path(raw) if raw else None


def test_lease_reader_is_seekable():
    payload = bytearray(b"abcdef0123456789")
    view = (ctypes.c_ubyte * len(payload)).from_buffer(payload)
    reader = _LeaseReader(
        ctypes.addressof(view), len(payload),
        hashlib.sha256(payload).hexdigest(),
    )
    assert reader.read(4) == b"abcd"
    assert reader.seek(-4, 2) == len(payload) - 4
    assert reader.read() == b"6789"


@pytest.mark.skipif(_bridge() is None, reason="native bridge not supplied")
def test_posix_hot_fold_down_is_warm(tmp_path):
    bridge = _NativeFMS(
        _bridge(), cold_root=tmp_path / "cold",
        warm_budget_bytes=1 << 20, cold_budget_bytes=1 << 20,
        absent_policy=ResidencyAbsentPolicy.FOLD_DOWN,
    )
    payload = bytearray((i % 251 for i in range(8192)))
    view = (ctypes.c_ubyte * len(payload)).from_buffer(payload)
    try:
        assert bridge.register(ctypes.addressof(view), len(payload), "HOT") == "WARM"
        assert bridge.hot_available is False
        ptr, size, tier = bridge.acquire("HOT")
        assert tier == "WARM"
        assert ctypes.string_at(ptr, size) == bytes(payload)
        stats = bridge.stats()
        assert stats["objects"] == 1
        assert stats["tier_bytes"][1] == len(payload)
        assert stats["domain_bytes"][0] == len(payload)
        bridge.release()
        bridge.unregister()
    finally:
        bridge.close()


@pytest.mark.skipif(_bridge() is None, reason="native bridge not supplied")
def test_posix_hot_reject_is_unsupported(tmp_path):
    bridge = _NativeFMS(
        _bridge(), cold_root=tmp_path / "cold",
        warm_budget_bytes=1 << 20, cold_budget_bytes=1 << 20,
        absent_policy=ResidencyAbsentPolicy.REJECT,
    )
    payload = bytearray(b"x" * 4096)
    view = (ctypes.c_ubyte * len(payload)).from_buffer(payload)
    actual = ctypes.c_int(-1)
    try:
        rc = bridge.lib.elpis_fms_inference_register_checkpoint(
            bridge._ctx, ctypes.c_void_p(ctypes.addressof(view)),
            ctypes.c_uint64(len(payload)), ctypes.c_int(0),
            ctypes.byref(actual),
        )
        assert rc == _FMS_E_UNSUPPORTED
        assert bridge.stats()["objects"] == 0
    finally:
        bridge.close()


@pytest.mark.skipif(
    not (_bridge() and os.environ.get("ELPIS_FPRM_MODEL")
         and importlib.util.find_spec("torch") is not None),
    reason="real adapter test requires bridge/checkpoint/torch",
)
def test_real_checkpoint_lease_hash(tmp_path):
    from elpis_reference.fms_inference_adapter import FMSCheckpointInferenceAdapter
    from elpis_reference.model import MODEL_SHA256
    checkpoint = Path(os.environ["ELPIS_FPRM_MODEL"])
    adapter = FMSCheckpointInferenceAdapter(
        checkpoint, bridge_library=_bridge(), cold_root=tmp_path / "cold",
    )
    try:
        assert adapter.authority.registration_tier == "WARM"
        binding = adapter.acquire(ModelResidencyRequest(
            model_id="FPRM.Samsung_TRM",
            preferred_tier="HOT",
            absent_policy=ResidencyAbsentPolicy.FOLD_DOWN,
        ))
        assert binding.actual_tier == "WARM"
        reader = adapter._lease_reader
        h = hashlib.sha256()
        reader.seek(0)
        while True:
            chunk = reader.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
        assert h.hexdigest() == MODEL_SHA256
        adapter.release(binding)
    finally:
        adapter.close()
