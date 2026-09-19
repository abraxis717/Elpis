"""Needle3 C-ABI provider.

This module executes only inside the Astra isolated worker.  It never creates
sockets, forks, execs another process, writes the model, or discovers plugins.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import math
import mmap
from pathlib import Path

from elpis_fractal_spine.contracts import (
    InferenceExecutionResult,
    ModelResidencyBinding,
)


_BACKEND = "cactus.needle3.native.v1"
_DEVICE = "cpu"
_LIBRARY_RELATIVE = Path("native/libelpis_needle3.so")
_MAX_OUTPUT_BYTES = 1024 * 1024
_MAX_NEW_TOKENS = 4096


def _sha256(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as source:
        while True:
            block = source.read(8 * 1024 * 1024)

            if not block:
                break

            h.update(block)

    return h.hexdigest()


def _string(
    context: dict,
    name: str,
    *,
    allow_empty: bool = False,
) -> str:
    value = context.get(name)

    if type(value) is not str:
        raise ValueError(
            f"{name} must be a string"
        )

    if not allow_empty and not value:
        raise ValueError(
            f"{name} cannot be empty"
        )

    return value


class Needle3Provider:
    """One process-global Needle3 model inside one Astra worker."""

    def __init__(self, context):
        if type(context) is not dict:
            raise TypeError(
                "Needle3 context must be an object"
            )

        allowed = {
            "model_id",
            "model_path",
            "model_sha256",
            "system_prompt",
            "tools_json",
            "tool_index_path",
            "max_new_tokens",
        }

        extra = (
            set(context)
            - allowed
        )

        if extra:
            raise ValueError(
                "unexpected Needle3 context fields: "
                + ",".join(sorted(extra))
            )

        self.model_id = _string(
            context,
            "model_id",
        )

        self.model_path = Path(
            _string(
                context,
                "model_path",
            )
        ).resolve(
            strict=True
        )

        self.model_sha256 = _string(
            context,
            "model_sha256",
        )

        if (
            len(self.model_sha256) != 64
            or any(
                char not in "0123456789abcdef"
                for char in self.model_sha256
            )
        ):
            raise ValueError(
                "model_sha256 must be lowercase SHA-256"
            )

        self.system_prompt = _string(
            context,
            "system_prompt",
            allow_empty=True,
        )

        self.tools_json = _string(
            context,
            "tools_json",
        )

        tools = json.loads(
            self.tools_json
        )

        if type(tools) is not list:
            raise ValueError(
                "tools_json must encode a JSON array"
            )

        self.tool_index_path = _string(
            context,
            "tool_index_path",
            allow_empty=True,
        )

        max_tokens = context.get(
            "max_new_tokens",
            512,
        )

        if (
            type(max_tokens) is not int
            or not 1
            <= max_tokens
            <= _MAX_NEW_TOKENS
        ):
            raise ValueError(
                "max_new_tokens outside bounded range"
            )

        self.max_new_tokens = (
            max_tokens
        )

        package = Path(
            __file__
        ).resolve().parent

        self.library_path = (
            package
            / _LIBRARY_RELATIVE
        ).resolve(
            strict=True
        )

        if not self.library_path.is_relative_to(
            package
        ):
            raise RuntimeError(
                "native runtime escaped wheel package"
            )

        actual_model_sha = _sha256(
            self.model_path
        )

        if actual_model_sha != self.model_sha256:
            raise ValueError(
                "Needle3 model SHA-256 mismatch"
            )

        self._lib = ctypes.CDLL(
            str(
                self.library_path
            ),
            mode=ctypes.RTLD_LOCAL,
        )

        self._bind_abi()

        self._model_file = None
        self._model_map = None
        self._model_buffer = None

        self._loaded = False
        self._held = False
        self._closed = False
        self._lease_counter = 0

    def _bind_abi(self) -> None:
        self._lib.needle_init.argtypes = [
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
        ]
        self._lib.needle_init.restype = (
            ctypes.c_int
        )

        self._lib.needle_complete.argtypes = [
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
        ]
        self._lib.needle_complete.restype = (
            ctypes.c_int
        )

        self._lib.needle_embed.argtypes = [
            ctypes.c_char_p,
            ctypes.POINTER(
                ctypes.c_float
            ),
            ctypes.c_int,
        ]
        self._lib.needle_embed.restype = (
            ctypes.c_int
        )

        self._lib.needle_reset.argtypes = []
        self._lib.needle_reset.restype = (
            None
        )

        self._lib.needle_load.argtypes = [
            ctypes.POINTER(
                ctypes.c_ubyte
            ),
            ctypes.c_ulonglong,
        ]
        self._lib.needle_load.restype = (
            ctypes.c_int
        )

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError(
                "Needle3 provider is closed"
            )

    def _load(self) -> None:
        self._ensure_open()

        if self._loaded:
            return

        source = self.model_path.open(
            "rb"
        )

        try:
            mapped = mmap.mmap(
                source.fileno(),
                0,
                access=mmap.ACCESS_COPY,
            )

            buffer = (
                ctypes.c_ubyte
                * len(mapped)
            ).from_buffer(
                mapped
            )

            load_rc = self._lib.needle_load(
                buffer,
                len(mapped),
            )

            if load_rc < 0:
                del buffer
                mapped.close()
                raise RuntimeError(
                    "needle_load failed: "
                    + str(load_rc)
                )

            init_rc = self._lib.needle_init(
                self.system_prompt.encode(
                    "utf-8"
                ),
                self.tools_json.encode(
                    "utf-8"
                ),
                self.tool_index_path.encode(
                    "utf-8"
                ),
            )

            if init_rc < 0:
                del buffer
                mapped.close()
                raise RuntimeError(
                    "needle_init failed: "
                    + str(init_rc)
                )

        except Exception:
            source.close()
            raise

        self._model_file = source
        self._model_map = mapped
        self._model_buffer = buffer
        self._loaded = True

    def acquire(self, request):
        self._ensure_open()

        if request.model_id != self.model_id:
            raise ValueError(
                "Needle3 residency model identity mismatch"
            )

        if self._held:
            raise RuntimeError(
                "Needle3 residency already acquired"
            )

        self._load()

        self._held = True
        self._lease_counter += 1

        return ModelResidencyBinding(
            model_id=self.model_id,
            requested_tier=request.preferred_tier,
            actual_tier="HOT",
            backend_id=_BACKEND,
            device_id=_DEVICE,
            binding_id=(
                "needle3-lease-"
                + str(
                    self._lease_counter
                )
            ),
        )

    def execute(
        self,
        request,
        *,
        residency=None,
    ):
        self._ensure_open()

        if not self._held:
            raise RuntimeError(
                "Needle3 execution requires acquired residency"
            )

        if request.model_id != self.model_id:
            raise ValueError(
                "Needle3 execution model identity mismatch"
            )

        if (
            residency is not None
            and (
                residency.model_id
                != self.model_id
                or residency.backend_id
                != _BACKEND
            )
        ):
            raise ValueError(
                "Needle3 residency binding mismatch"
            )

        if (
            type(request.input_payload)
            is not tuple
            or len(
                request.input_payload
            )
            != 1
            or type(
                request.input_payload[0]
            )
            is not str
        ):
            raise ValueError(
                "Needle3 input_payload must be one UTF-8 string"
            )

        prompt = request.input_payload[
            0
        ]

        max_tokens = min(
            self.max_new_tokens,
            request.max_steps,
        )

        output = (
            ctypes.create_string_buffer(
                _MAX_OUTPUT_BYTES
            )
        )

        rc = self._lib.needle_complete(
            prompt.encode(
                "utf-8"
            ),
            max_tokens,
            output,
            len(output),
        )

        if rc < 0:
            raise RuntimeError(
                "needle_complete failed: "
                + str(rc)
            )

        text = output.value.decode(
            "utf-8",
            errors="strict",
        )

        parsed = json.loads(
            text
        )

        if type(parsed) is not dict:
            raise ValueError(
                "Needle3 native output must be a JSON object"
            )

        if parsed.get("type") != "call":
            raise ValueError(
                "Needle3 native output type must be call"
            )

        if type(parsed.get("success")) is not bool:
            raise ValueError(
                "Needle3 native output success must be boolean"
            )

        calls = parsed.get("function_calls")
        if type(calls) is not list:
            raise ValueError(
                "Needle3 native output function_calls must be a list"
            )

        confidence = parsed.get("confidence")
        if (
            isinstance(confidence, bool)
            or type(confidence) not in (int, float)
            or not math.isfinite(float(confidence))
            or not 0.0 <= float(confidence) <= 1.0
        ):
            raise ValueError(
                "Needle3 native output confidence must be finite in [0,1]"
            )

        # Runtime timing/RAM/reasoning diagnostics are deliberately excluded
        # from the portable proposal payload.  They are non-authoritative and
        # may vary between otherwise identical executions.
        semantic = {
            "type": "call",
            "success": parsed["success"],
            "function_calls": calls,
            "confidence": float(confidence),
        }

        canonical = json.dumps(
            semantic,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

        tier = (
            residency.actual_tier
            if residency is not None
            else "HOT"
        )

        return InferenceExecutionResult(
            status="OK",
            output_payload=(
                canonical,
            ),
            iteration_count=1,
            backend_id=_BACKEND,
            device_id=_DEVICE,
            residency_tier=tier,
        )

    def release(self, binding):
        self._ensure_open()

        if (
            binding.model_id
            != self.model_id
            or binding.backend_id
            != _BACKEND
        ):
            raise ValueError(
                "Needle3 release binding mismatch"
            )

        if not self._held:
            raise RuntimeError(
                "Needle3 residency is not acquired"
            )

        self._lib.needle_reset()
        self._held = False

    def close(self):
        if self._closed:
            return

        if self._loaded:
            self._lib.needle_reset()

        # Keep the model mapping alive until process teardown. The donor C ABI
        # does not expose an unload primitive and may retain pointers into it.
        self._held = False
        self._closed = True
