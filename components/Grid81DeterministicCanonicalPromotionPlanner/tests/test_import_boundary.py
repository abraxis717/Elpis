"""Planner scans its own verifier files and shares the qualified AST policy."""
from pathlib import Path

import pytest

from elpis_grid81_promotion_planner import gates, import_boundary
from elpis_grid81_adjudication import import_boundary as adjudicator_boundary


@pytest.mark.parametrize("filename", [
    "gates.py", "verifier.py", "adversarial_matrix.py", "__init__.py", "nested/module.py",
])
@pytest.mark.parametrize("source", [
    "import  subprocess",
    "import\tsocket",
    "from subprocess import run",
    '__import__("subprocess")',
    'load = __import__\nload("subprocess")',
    'import importlib\nimportlib.import_module("subprocess")',
    'import importlib as il\nload = il.import_module\nload("subprocess")',
    'from importlib import import_module as load\nload("subprocess")',
    "from http import client",
])
def test_planner_bypasses_and_formerly_excluded_files(tmp_path, monkeypatch, filename, source):
    path = tmp_path / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)
    monkeypatch.setattr(gates, "__file__", str(tmp_path / "gates.py"))
    assert gates._check_no_executable_authority(None) is False


def test_planner_inert_fixture_strings_pass(tmp_path, monkeypatch):
    (tmp_path / "gates.py").write_text('fixture = \'__import__("subprocess")\'')
    monkeypatch.setattr(gates, "__file__", str(tmp_path / "gates.py"))
    assert gates._check_no_executable_authority(None) is True


def test_scanner_implementations_remain_identical():
    assert Path(import_boundary.__file__).read_bytes() == Path(adjudicator_boundary.__file__).read_bytes()
