from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tomllib


ROOT = Path(__file__).resolve().parents[1]
DATA = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_pytest_source_roots_equal_setuptools_package_roots() -> None:
    pytest_roots = DATA["tool"]["pytest"]["ini_options"]["pythonpath"]
    setuptools_roots = DATA["tool"]["setuptools"]["packages"]["find"]["where"]
    assert pytest_roots == setuptools_roots


def test_pytest_source_roots_are_repository_relative_and_present() -> None:
    roots = DATA["tool"]["pytest"]["ini_options"]["pythonpath"]
    assert roots
    for rel in roots:
        path = Path(rel)
        assert not path.is_absolute(), rel
        assert ".." not in path.parts, rel
        assert (ROOT / path).is_dir(), rel


def test_subprocess_pythonpath_is_bootstrapped_from_same_roots() -> None:
    expected = [
        str((ROOT / rel).resolve())
        for rel in DATA["tool"]["pytest"]["ini_options"]["pythonpath"]
    ]
    inherited = os.environ.get("PYTHONPATH", "").split(os.pathsep)
    assert inherited[: len(expected)] == expected


def test_fresh_child_imports_project_packages_from_this_checkout() -> None:
    script = """
from pathlib import Path
import DarwinianMatrix
import elpis
import elpis_reference
root = Path.cwd().resolve()
for mod in (DarwinianMatrix, elpis, elpis_reference):
    path = Path(mod.__file__).resolve()
    assert path.is_relative_to(root), (mod.__name__, path, root)
"""
    subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=os.environ.copy(),
        check=True,
    )


def _load_conftest_module():
    import importlib.util

    path = ROOT / "tests/conftest.py"
    spec = importlib.util.spec_from_file_location(
        "elpis_root_test_conftest_contract",
        path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_git_authority_exception_set_is_exact() -> None:
    module = _load_conftest_module()
    expected = frozenset(
        {
            "tests/test_grid81_writer_successor_assembly_verifier_r0.py",
            "tests/test_grid81_writer_successor_component_manifests_r0.py",
            "tests/test_published_releases_registry.py",
            "tests/test_seal_release_mutations.py",
        }
    )
    assert module.GIT_AUTHORITY_TEST_MODULES == expected
    for rel in expected:
        assert (ROOT / rel).is_file(), rel


def test_git_authority_marker_is_registered() -> None:
    markers = DATA["tool"]["pytest"]["ini_options"]["markers"]
    assert markers == [
        (
            "requires_git: repository provenance/sealing tests "
            "requiring a live Git checkout"
        )
    ]
