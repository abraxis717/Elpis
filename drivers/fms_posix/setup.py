from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib

from setuptools import Extension, find_packages, setup
from setuptools.command.build_ext import build_ext


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]

with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
    _root_project = tomllib.load(handle)["project"]

ROOT_VERSION = _root_project["version"]
ROOT_REQUIRES_PYTHON = _root_project["requires-python"]

if not isinstance(ROOT_VERSION, str) or not ROOT_VERSION:
    raise RuntimeError("root project.version is unavailable")
if not isinstance(ROOT_REQUIRES_PYTHON, str) or not ROOT_REQUIRES_PYTHON:
    raise RuntimeError("root project.requires-python is unavailable")


class CMakeFMSBridgeBuild(build_ext):
    """Build the canonical FMS inference bridge outside the source tree."""

    def run(self):
        for extension in self.extensions:
            self.build_extension(extension)

    def build_extension(self, extension):
        configured = os.environ.get("ELPIS_FMS_POSIX_NATIVE_BUILD_ROOT")
        if configured:
            build_root = Path(configured).resolve()
            build_root.mkdir(parents=True, exist_ok=True)
        else:
            build_root = Path(
                tempfile.mkdtemp(prefix="elpis_fms_posix_native_")
            ).resolve()

        hacf_build = build_root / "hacf"
        bridge_build = build_root / "bridge"
        hacf_build.mkdir(parents=True, exist_ok=True)
        bridge_build.mkdir(parents=True, exist_ok=True)

        hacf_source = REPO_ROOT / "native" / "hacf"
        bridge_source = REPO_ROOT / "native" / "hacf_bridge"

        subprocess.run(
            [
                "cmake",
                "-S",
                str(hacf_source),
                "-B",
                str(hacf_build),
                "-DCMAKE_BUILD_TYPE=Release",
                "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
            ],
            check=True,
        )
        subprocess.run(
            ["cmake", "--build", str(hacf_build), "-j2"],
            check=True,
        )

        subprocess.run(
            [
                "cmake",
                "-S",
                str(bridge_source),
                "-B",
                str(bridge_build),
                "-DCMAKE_BUILD_TYPE=Release",
                "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
                "-DCMAKE_SKIP_RPATH=ON",
                f"-DHACF_INCLUDE_DIR={REPO_ROOT / 'native' / 'hacf' / 'include'}",
                f"-DHACF_LIB_DIR={hacf_build}",
            ],
            check=True,
        )
        subprocess.run(
            [
                "cmake",
                "--build",
                str(bridge_build),
                "--target",
                "fms_inference_bridge",
                "-j2",
            ],
            check=True,
        )

        candidates = list(
            bridge_build.rglob("libfms_inference_bridge.so")
        )
        if not candidates:
            candidates = list(
                bridge_build.rglob("libfms_inference_bridge.dylib")
            )
        if len(candidates) != 1:
            raise RuntimeError(
                f"expected one canonical FMS inference bridge, got {candidates!r}"
            )

        destination = Path(
            self.get_ext_fullpath(extension.name)
        ).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(candidates[0], destination)


setup(
    name="elpis-inference-driver-fms-posix",
    version=ROOT_VERSION,
    description="Elpis reference POSIX/CPU FMS checkpoint inference driver",
    python_requires=ROOT_REQUIRES_PYTHON,
    install_requires=[f"elpisai=={ROOT_VERSION}"],
    package_dir={"": "src"},
    packages=find_packages("src"),
    ext_modules=[
        Extension(
            "elpis_fms_posix_driver._fms_inference_bridge",
            sources=[],
        )
    ],
    cmdclass={"build_ext": CMakeFMSBridgeBuild},
    entry_points={
        "elpis.inference_drivers.v1": [
            "fms.checkpoint.v1=elpis_fms_posix_driver:factory",
        ]
    },
    zip_safe=False,
)
