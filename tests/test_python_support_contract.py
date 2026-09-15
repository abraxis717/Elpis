from __future__ import annotations

from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def _project() -> dict:
    return tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]


def _platform_matrix() -> str:
    return (ROOT / ".github/workflows/platform-matrix.yml").read_text(
        encoding="utf-8"
    )


def test_advertised_python_range_matches_qualified_numpy1_boundary():
    project = _project()
    assert project["requires-python"] == ">=3.11,<3.13"
    assert "numpy>=1.26,<2" in project["dependencies"]
    assert "scipy>=1.11,<2" in project["dependencies"]


def test_platform_matrix_qualifies_every_advertised_python_minor():
    workflow = _platform_matrix()
    assert "python-version:" in workflow
    assert "- '3.11'" in workflow
    assert "- '3.12'" in workflow
    assert "'3.13'" not in workflow
    assert "python-version: ${{ matrix.python-version }}" in workflow


def test_platform_matrix_resolves_real_base_dependencies():
    workflow = _platform_matrix()
    assert "python -m pip install -e ." in workflow
    assert "python -m pip install -e . --no-deps" not in workflow
    assert "import numpy, scipy, sys" in workflow
    assert "tests/test_python_support_contract.py" in workflow


def test_base_dependency_matrix_keeps_torch_optional():
    workflow = _platform_matrix()
    assert "PLATFORM_MATRIX_TORCH_ABSENT" in workflow
    assert "find_spec('torch') is None" in workflow
    assert "[trm]" not in workflow
