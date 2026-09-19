from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest

from elpis_fractal_spine.contracts import (
    InferenceExecutionRequest,
    ModelResidencyRequest,
)

from elpis_fractal_spine.isolated_driver import (
    IsolatedProvider,
    SupervisorPolicy,
    WheelAuthority,
)

from elpis_fractal_spine.isolated_driver.sandbox import (
    seccomp_available,
)


ROOT = Path(__file__).resolve().parents[1]

DRIVER = (
    ROOT
    / "drivers"
    / "needle3"
)

PACKAGE = "elpis_needle3_driver"
DIST = "elpis-needle3-driver"
VERSION = "0.1.1"
GROUP = "elpis.inference_drivers.v1"
DRIVER_ID = "cactus.needle3.native.v1"
TARGET = "elpis_needle3_driver:factory"
INFO = "elpis_needle3_driver-0.1.1.dist-info"


FAKE_C = r"""
#include <stdio.h>
#include <string.h>

static int loaded = 0;
static int initialized = 0;

int needle_load(const unsigned char *cact, unsigned long long n) {
    if (!cact || n == 0) return -1;
    loaded = 1;
    return 0;
}

int needle_init(
    const char *system_prompt,
    const char *tools_json,
    const char *tool_index_path
) {
    (void)system_prompt;
    (void)tool_index_path;
    if (!loaded || !tools_json) return -2;
    initialized = 1;
    return 0;
}

int needle_complete(
    const char *input,
    int max_new_tokens,
    char *out,
    int out_capacity
) {
    (void)input;
    if (!loaded || !initialized || max_new_tokens < 1) return -3;

    const char *value =
        "{\"type\":\"call\",\"success\":true,"
        "\"function_calls\":[],\"confidence\":1.0,"
        "\"reasoning\":\"volatile diagnostic\","
        "\"prefill_tps\":123.4,\"decode_tps\":5.6,"
        "\"peak_ram_mb\":77.0}";

    int n = (int)strlen(value);

    if (out_capacity <= n) return -4;

    memcpy(out, value, (size_t)n + 1);
    return n;
}

int needle_embed(
    const char *input,
    float *out,
    int out_capacity
) {
    (void)input;

    if (!out) return 4;

    if (out_capacity < 4) return -5;

    out[0] = 1.0f;
    out[1] = 2.0f;
    out[2] = 3.0f;
    out[3] = 4.0f;

    return 4;
}

void needle_reset(void) {
    initialized = loaded ? 1 : 0;
}
"""


def _record(files):
    result = []

    for name, content in files.items():
        digest = base64.urlsafe_b64encode(
            hashlib.sha256(content).digest()
        ).decode().rstrip("=")

        result.append(
            f"{name},sha256={digest},{len(content)}\n"
        )

    result.append(
        f"{INFO}/RECORD,,\n"
    )

    return "".join(result).encode()


def _wheel(
    tmp_path: Path,
    library: Path,
):
    package_root = (
        DRIVER
        / "src"
        / PACKAGE
    )

    files = {
        f"{PACKAGE}/__init__.py":
            (
                package_root
                / "__init__.py"
            ).read_bytes(),

        f"{PACKAGE}/provider.py":
            (
                package_root
                / "provider.py"
            ).read_bytes(),

        f"{PACKAGE}/native/libelpis_needle3.so":
            library.read_bytes(),

        f"{INFO}/METADATA":
            (
                "Metadata-Version: 2.1\n"
                f"Name: {DIST}\n"
                f"Version: {VERSION}\n"
            ).encode(),

        f"{INFO}/WHEEL":
            (
                "Wheel-Version: 1.0\n"
                "Root-Is-Purelib: false\n"
                "Tag: py3-none-linux_x86_64\n"
            ).encode(),

        f"{INFO}/entry_points.txt":
            (
                f"[{GROUP}]\n"
                f"{DRIVER_ID} = {TARGET}\n"
            ).encode(),
    }

    files[
        f"{INFO}/RECORD"
    ] = _record(files)

    wheel = (
        tmp_path
        / "elpis_needle3_driver-0.1.1-py3-none-linux_x86_64.whl"
    )

    with zipfile.ZipFile(
        wheel,
        "w",
        compression=zipfile.ZIP_STORED,
    ) as archive:
        for name, content in files.items():
            archive.writestr(
                name,
                content,
            )

    authority = WheelAuthority(
        DRIVER_ID,
        DIST,
        VERSION,
        GROUP,
        TARGET,
        hashlib.sha256(
            wheel.read_bytes()
        ).hexdigest(),
    )

    return wheel, authority


def _compile_fake_native(
    tmp_path: Path,
) -> Path:
    compiler = (
        shutil.which("cc")
        or shutil.which("clang")
        or shutil.which("gcc")
    )

    if compiler is None:
        pytest.skip(
            "C compiler unavailable"
        )

    source = (
        tmp_path
        / "fake_needle.c"
    )

    library = (
        tmp_path
        / "libelpis_needle3.so"
    )

    source.write_text(
        FAKE_C,
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            compiler,
            "-shared",
            "-fPIC",
            "-O2",
            str(source),
            "-o",
            str(library),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, (
        result.stdout
        + result.stderr
    )

    return library


def test_build_contract_refuses_cli_server_and_model_in_wheel():
    contract = json.loads(
        (
            DRIVER
            / "BUILD_CONTRACT.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    assert (
        contract["native_runtime"]["required_rpath"]
        == "$ORIGIN"
    )

    assert (
        contract["model_distribution"]["inside_wheel"]
        is False
    )

    assert (
        contract["astra"]["sandbox_must_remain_unchanged"]
        is True
    )

    assert (
        contract["astra"]["network_required"]
        is False
    )

    assert (
        contract["astra"]["process_creation_required"]
        is False
    )

    assert (
        contract["admission"]["execution_authority_granted"]
        is True
    )


@pytest.mark.skipif(
    sys.platform != "linux"
    or not seccomp_available(),
    reason="Astra Linux seccomp unavailable",
)
def test_driver_executes_inside_real_astra_sandbox_without_network_or_exec(
    tmp_path,
):
    library = _compile_fake_native(
        tmp_path
    )

    wheel, authority = _wheel(
        tmp_path,
        library,
    )

    model = (
        tmp_path
        / "needle3.cact"
    )

    model.write_bytes(
        b"synthetic-cact-model"
    )

    context = {
        "model_id":
            "Cactus.Needle3",

        "model_path":
            str(model),

        "model_sha256":
            hashlib.sha256(
                model.read_bytes()
            ).hexdigest(),

        "system_prompt":
            "Return bounded tool proposals.",

        "tools_json":
            "[]",

        "tool_index_path":
            "",

        "max_new_tokens":
            32,
    }

    provider = IsolatedProvider(
        authority=authority,
        wheel_path=wheel,
        runtime_context=context,
        policy=SupervisorPolicy(
            tmp_path
        ),
        model_id="Cactus.Needle3",
    )

    try:
        provider.start()

        assert (
            provider.receipt
            is not None
        )

        assert (
            provider.receipt.sandbox.seccomp
            is True
        )

        binding = provider.acquire(
            ModelResidencyRequest(
                "Cactus.Needle3"
            )
        )

        result = provider.execute(
            InferenceExecutionRequest(
                request_id="needle3-r3",
                model_id="Cactus.Needle3",
                input_space="text.utf8.v1",
                output_space="needle.function-call.native.v3",
                input_payload=(
                    "Choose a tool.",
                ),
                model_path=None,
                max_steps=8,
            ),
            residency=binding,
        )

        assert result.status == "OK"
        assert (
            result.backend_id
            == "cactus.needle3.native.v1"
        )

        payload = json.loads(
            result.output_payload[0]
        )

        assert payload == {
            "confidence": 1.0,
            "function_calls": [],
            "success": True,
            "type": "call",
        }

        assert set(payload) == {
            "confidence",
            "function_calls",
            "success",
            "type",
        }

        provider.release(
            binding
        )

    finally:
        provider.close()


def test_driver_source_contains_no_network_or_process_creation_surface():
    source = (
        DRIVER
        / "src"
        / PACKAGE
        / "provider.py"
    ).read_text(
        encoding="utf-8"
    )

    forbidden = (
        "socket.",
        "subprocess",
        "Popen",
        "fork(",
        "execve",
        "--serve",
        "http.client",
        "urllib",
        "requests",
    )

    for token in forbidden:
        assert token not in source


def test_root_elpis_package_does_not_ship_driver_source():
    root_pyproject = (
        ROOT
        / "pyproject.toml"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "drivers/needle3/src"
        not in root_pyproject
    )
