from __future__ import annotations

import ast
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "drivers" / "fms_posix"
SETUP = DRIVER / "setup.py"
INIT = DRIVER / "src" / "elpis_fms_posix_driver" / "__init__.py"
DRIVER_PYPROJECT = DRIVER / "pyproject.toml"
ROOT_PYPROJECT = ROOT / "pyproject.toml"


def test_driver_subproject_build_backend_is_local_setuptools():
    data = tomllib.loads(
        DRIVER_PYPROJECT.read_text(encoding="utf-8")
    )
    build = data["build-system"]
    assert build["build-backend"] == "setuptools.build_meta"
    assert "wheel" in build["requires"]
    assert any(req.startswith("setuptools") for req in build["requires"])


def test_driver_version_and_core_dependency_are_root_derived():
    setup = SETUP.read_text(encoding="utf-8")
    root = tomllib.loads(
        ROOT_PYPROJECT.read_text(encoding="utf-8")
    )["project"]
    assert 'REPO_ROOT / "pyproject.toml"' in setup
    assert 'ROOT_VERSION = _root_project["version"]' in setup
    assert 'install_requires=[f"elpisai=={ROOT_VERSION}"]' in setup
    assert f'version="{root["version"]}"' not in setup
    assert 'version="2.2.12"' not in setup


def test_driver_declares_exact_plugin_entry_point():
    setup = SETUP.read_text(encoding="utf-8")
    assert '"elpis.inference_drivers.v1"' in setup
    assert (
        '"fms.checkpoint.v1=elpis_fms_posix_driver:factory"'
        in setup
    )


def test_driver_builds_canonical_bridge_from_repository_sources():
    setup = SETUP.read_text(encoding="utf-8")
    assert '"native" / "hacf"' in setup
    assert '"native" / "hacf_bridge"' in setup
    assert '"fms_inference_bridge"' in setup
    assert "ELPIS_FMS_POSIX_NATIVE_BUILD_ROOT" in setup
    assert "Extension(" in setup
    assert (
        '"elpis_fms_posix_driver._fms_inference_bridge"'
        in setup
    )


def test_driver_module_import_surface_is_no_torch_and_no_hardware_probe():
    source = INIT.read_text(encoding="utf-8").lower()
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "torch" not in imported
    for token in ("cuda", "mps", "rocm", "vulkan", "metal"):
        assert token not in source


def test_driver_factory_requires_runtime_data_not_bridge_authority():
    source = INIT.read_text(encoding="utf-8")
    assert 'runtime_context["checkpoint_path"]' in source
    assert 'runtime_context["cold_root"]' in source
    assert 'runtime_context["bridge_library"]' not in source
    assert 'runtime_context.get("bridge_library"' not in source
    assert "ELPIS_FMS_INFERENCE_BRIDGE" not in source
    assert "resources.as_file" in source


def test_driver_factory_constructs_qualified_adapter_with_fold_down():
    source = INIT.read_text(encoding="utf-8")
    assert "FMSCheckpointInferenceAdapter(" in source
    assert "bridge_library=Path(bridge_path)" in source
    assert "ResidencyAbsentPolicy.FOLD_DOWN" in source
