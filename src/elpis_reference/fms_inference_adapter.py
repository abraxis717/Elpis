from __future__ import annotations

import ctypes
from dataclasses import dataclass
import hashlib
import io
import mmap
import os
from pathlib import Path

from elpis_fractal_spine.contracts import (
    InferenceExecutionRequest,
    InferenceExecutionResult,
    ModelResidencyBinding,
    ModelResidencyRequest,
    ResidencyAbsentPolicy,
)

_FMS_HOT = 0
_FMS_WARM = 1
_FMS_COLD = 2
_FMS_FOLD_DOWN = 0
_FMS_REJECT = 1
_FMS_E_UNSUPPORTED = -5
_TIER_TO_INT = {"HOT": 0, "WARM": 1, "COLD": 2}
_INT_TO_TIER = {0: "HOT", 1: "WARM", 2: "COLD"}


class _NativeStats(ctypes.Structure):
    _fields_ = [
        ("tier_bytes", ctypes.c_uint64 * 3),
        ("domain_bytes", ctypes.c_uint64 * 3),
        ("objects", ctypes.c_uint64),
        ("pinned_bytes", ctypes.c_uint64),
        ("forced_cpu_fallbacks", ctypes.c_uint64),
        ("forced_placements", ctypes.c_uint64),
    ]


class _NativeFMS:
    def __init__(
        self,
        library: Path,
        *,
        cold_root: Path,
        warm_budget_bytes: int,
        cold_budget_bytes: int,
        absent_policy: ResidencyAbsentPolicy,
    ):
        self.lib = ctypes.CDLL(str(Path(library)))
        self._ctx = ctypes.c_void_p()
        self._configure_abi()
        cold_root = Path(cold_root)
        cold_root.mkdir(parents=True, exist_ok=True)
        policy = (
            _FMS_FOLD_DOWN
            if absent_policy is ResidencyAbsentPolicy.FOLD_DOWN
            else _FMS_REJECT
        )
        rc = self.lib.elpis_fms_inference_create(
            os.fsencode(cold_root),
            ctypes.c_uint64(int(warm_budget_bytes)),
            ctypes.c_uint64(int(cold_budget_bytes)),
            ctypes.c_int(policy),
            ctypes.byref(self._ctx),
        )
        self._check(rc, "create")

    def _configure_abi(self):
        vp = ctypes.POINTER(ctypes.c_void_p)
        ip = ctypes.POINTER(ctypes.c_int)
        up = ctypes.POINTER(ctypes.c_uint64)
        self.lib.elpis_fms_inference_create.argtypes = [
            ctypes.c_char_p, ctypes.c_uint64, ctypes.c_uint64,
            ctypes.c_int, vp,
        ]
        self.lib.elpis_fms_inference_create.restype = ctypes.c_int
        self.lib.elpis_fms_inference_destroy.argtypes = [ctypes.c_void_p]
        self.lib.elpis_fms_inference_register_checkpoint.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64,
            ctypes.c_int, ip,
        ]
        self.lib.elpis_fms_inference_register_checkpoint.restype = ctypes.c_int
        self.lib.elpis_fms_inference_acquire_checkpoint.argtypes = [
            ctypes.c_void_p, ctypes.c_int, vp, up, ip,
        ]
        self.lib.elpis_fms_inference_acquire_checkpoint.restype = ctypes.c_int
        self.lib.elpis_fms_inference_release_checkpoint.argtypes = [ctypes.c_void_p]
        self.lib.elpis_fms_inference_release_checkpoint.restype = ctypes.c_int
        self.lib.elpis_fms_inference_unregister_checkpoint.argtypes = [ctypes.c_void_p]
        self.lib.elpis_fms_inference_unregister_checkpoint.restype = ctypes.c_int
        self.lib.elpis_fms_inference_hot_available.argtypes = [ctypes.c_void_p]
        self.lib.elpis_fms_inference_hot_available.restype = ctypes.c_int
        self.lib.elpis_fms_inference_backend_name.argtypes = [ctypes.c_void_p]
        self.lib.elpis_fms_inference_backend_name.restype = ctypes.c_char_p
        self.lib.elpis_fms_inference_get_stats.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(_NativeStats),
        ]
        self.lib.elpis_fms_inference_get_stats.restype = ctypes.c_int
        self.lib.elpis_fms_inference_strerror.argtypes = [ctypes.c_int]
        self.lib.elpis_fms_inference_strerror.restype = ctypes.c_char_p

    def _check(self, rc: int, op: str):
        if int(rc) < 0:
            raw = self.lib.elpis_fms_inference_strerror(int(rc))
            detail = raw.decode(errors="replace") if raw else str(rc)
            raise RuntimeError(f"FMS {op} failed: {detail} ({int(rc)})")

    def register(self, ptr: int, size: int, want_tier: str) -> str:
        actual = ctypes.c_int(-1)
        rc = self.lib.elpis_fms_inference_register_checkpoint(
            self._ctx, ctypes.c_void_p(ptr), ctypes.c_uint64(size),
            ctypes.c_int(_TIER_TO_INT[want_tier]), ctypes.byref(actual),
        )
        self._check(rc, "register")
        return _INT_TO_TIER[int(actual.value)]

    def acquire(self, want_tier: str) -> tuple[int, int, str]:
        ptr, size, actual = ctypes.c_void_p(), ctypes.c_uint64(), ctypes.c_int(-1)
        rc = self.lib.elpis_fms_inference_acquire_checkpoint(
            self._ctx, ctypes.c_int(_TIER_TO_INT[want_tier]),
            ctypes.byref(ptr), ctypes.byref(size), ctypes.byref(actual),
        )
        self._check(rc, "lease acquire")
        return int(ptr.value), int(size.value), _INT_TO_TIER[int(actual.value)]

    def release(self):
        self._check(
            self.lib.elpis_fms_inference_release_checkpoint(self._ctx),
            "lease release",
        )

    def unregister(self):
        self._check(
            self.lib.elpis_fms_inference_unregister_checkpoint(self._ctx),
            "unregister",
        )

    @property
    def hot_available(self) -> bool:
        return bool(self.lib.elpis_fms_inference_hot_available(self._ctx))

    @property
    def backend_name(self) -> str:
        raw = self.lib.elpis_fms_inference_backend_name(self._ctx)
        return raw.decode(errors="replace") if raw else "unknown"

    def stats(self) -> dict[str, object]:
        s = _NativeStats()
        self._check(
            self.lib.elpis_fms_inference_get_stats(self._ctx, ctypes.byref(s)),
            "stats",
        )
        return {
            "tier_bytes": tuple(int(x) for x in s.tier_bytes),
            "domain_bytes": tuple(int(x) for x in s.domain_bytes),
            "objects": int(s.objects),
            "pinned_bytes": int(s.pinned_bytes),
            "forced_cpu_fallbacks": int(s.forced_cpu_fallbacks),
            "forced_placements": int(s.forced_placements),
        }

    def close(self):
        if self._ctx:
            self.lib.elpis_fms_inference_destroy(self._ctx)
            self._ctx = ctypes.c_void_p()


class _LeaseReader(io.RawIOBase):
    def __init__(self, ptr: int, size_bytes: int, expected_sha256: str):
        super().__init__()
        if not ptr or size_bytes <= 0:
            raise ValueError("lease reader requires non-empty FMS object")
        self._ptr = int(ptr)
        self.size_bytes = int(size_bytes)
        self.expected_sha256 = str(expected_sha256)
        self._pos = 0

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self._pos

    def seek(self, offset: int, whence: int = io.SEEK_SET):
        if whence == io.SEEK_SET:
            pos = offset
        elif whence == io.SEEK_CUR:
            pos = self._pos + offset
        elif whence == io.SEEK_END:
            pos = self.size_bytes + offset
        else:
            raise ValueError("unsupported whence")
        if pos < 0:
            raise ValueError("negative seek position")
        self._pos = min(int(pos), self.size_bytes)
        return self._pos

    def read(self, size: int = -1):
        if self._pos >= self.size_bytes:
            return b""
        remaining = self.size_bytes - self._pos
        size = remaining if size is None or size < 0 else min(int(size), remaining)
        out = ctypes.string_at(self._ptr + self._pos, size)
        self._pos += size
        return out

    def readinto(self, buffer):
        view = memoryview(buffer).cast("B")
        if self._pos >= self.size_bytes:
            return 0
        count = min(len(view), self.size_bytes - self._pos)
        target = (ctypes.c_ubyte * count).from_buffer(view)
        ctypes.memmove(ctypes.addressof(target), self._ptr + self._pos, count)
        self._pos += count
        return count


@dataclass(frozen=True)
class FMSCheckpointAuthority:
    path: str
    sha256: str
    size_bytes: int
    registration_tier: str
    backend_id: str
    hot_available: bool


class FMSCheckpointInferenceAdapter:
    def __init__(
        self,
        checkpoint_path: Path,
        *,
        bridge_library: Path,
        cold_root: Path,
        absent_policy: ResidencyAbsentPolicy = ResidencyAbsentPolicy.FOLD_DOWN,
        warm_budget_bytes: int | None = None,
        cold_budget_bytes: int | None = None,
    ):
        from .model import MODEL_FILENAME, MODEL_SHA256, verify_model

        path = Path(checkpoint_path)
        if path.name != MODEL_FILENAME:
            raise RuntimeError("noncanonical FPRM checkpoint filename")
        size = path.stat().st_size
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        digest = h.hexdigest()
        if digest != MODEL_SHA256:
            raise RuntimeError("FPRM checkpoint SHA-256 mismatch")
        strict = verify_model(path)
        if strict["sha256"] != MODEL_SHA256 or strict["strict_load"] is not True:
            raise RuntimeError("strict FPRM checkpoint verification failed")

        self._native = _NativeFMS(
            bridge_library,
            cold_root=cold_root,
            warm_budget_bytes=int(warm_budget_bytes or max(size * 2, 128 << 20)),
            cold_budget_bytes=int(cold_budget_bytes or max(size * 2, 128 << 20)),
            absent_policy=absent_policy,
        )
        self._path, self._sha256, self._size = path, digest, size
        self._active = None
        self._lease_reader = None
        self._closed = False
        self._serial = 0

        with path.open("rb") as f:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_COPY)
            try:
                first = ctypes.c_ubyte.from_buffer(mm)
                actual = self._native.register(
                    ctypes.addressof(first), size, "HOT"
                )
                del first
            finally:
                mm.close()

        self.authority = FMSCheckpointAuthority(
            str(path), digest, size, actual,
            f"fms:{self._native.backend_name}", self._native.hot_available,
        )

    def acquire(self, request: ModelResidencyRequest) -> ModelResidencyBinding:
        if self._closed or self._active is not None:
            raise RuntimeError("adapter unavailable for new lease")
        if request.model_id != "FPRM.Samsung_TRM":
            raise ValueError("wrong model_id")
        if request.preferred_tier not in _TIER_TO_INT:
            raise ValueError("unsupported executable residency tier")
        ptr, size, actual = self._native.acquire(request.preferred_tier)
        if size != self._size:
            self._native.release()
            raise RuntimeError("FMS lease size mismatch")
        self._serial += 1
        binding = ModelResidencyBinding(
            model_id=request.model_id,
            requested_tier=request.preferred_tier,
            actual_tier=actual,
            backend_id=f"fms:{self._native.backend_name}",
            device_id="opaque:fms-posix",
            binding_id=f"fms-checkpoint-{self._serial}",
        )
        self._lease_reader = _LeaseReader(ptr, size, self._sha256)
        self._active = binding
        return binding

    def execute(self, request: InferenceExecutionRequest, *, residency=None):
        if self._closed or residency is None or self._active != residency:
            raise RuntimeError("execution requires active adapter lease")
        if self._lease_reader is None:
            raise RuntimeError("missing active lease reader")
        if request.model_id != "FPRM.Samsung_TRM":
            raise ValueError("wrong model_id")
        if request.model_path is not None and Path(request.model_path) != self._path:
            raise ValueError("checkpoint path differs from adapter authority")
        if request.input_space != "grid81.sudoku.v1" or \
           request.output_space != "grid81.sudoku.v1":
            raise ValueError("unsupported model space")

        from .refinement import solve_sudoku
        self._lease_reader.seek(0)
        learned = solve_sudoku(
            tuple(int(v) for v in request.input_payload),
            model_path=self._lease_reader,
            device="cpu",
            max_steps=int(request.max_steps),
        )
        solution = (
            tuple(int(v) for v in learned.solution)
            if learned.solution is not None else None
        )
        return InferenceExecutionResult(
            status=learned.status,
            output_payload=solution,
            iteration_count=sum(int(step.step) for step in learned.steps),
            backend_id=residency.backend_id,
            device_id=residency.device_id,
            residency_tier=residency.actual_tier,
        )

    def release(self, binding):
        if self._active != binding:
            raise RuntimeError("release binding mismatch")
        self._native.release()
        self._active = None
        self._lease_reader = None

    def stats(self):
        return self._native.stats()

    def close(self):
        if self._closed:
            return
        if self._active is not None:
            self._native.release()
            self._active = None
            self._lease_reader = None
        self._native.unregister()
        self._native.close()
        self._closed = True

    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False
