"""Static import policy qualification: parsed source, never executed."""
from pathlib import Path

import pytest

from elpis_grid81_adjudication import verifier
from elpis_grid81_adjudication.import_boundary import check_import_boundary

BYPASSES = [
    "import  subprocess",
    "import\tsubprocess as process",
    "import os, subprocess as process",
    "from subprocess import run",
    "from subprocess import (\n    run as invoke,\n)",
    '__import__("subprocess")',
    '__import__(name="subprocess")',
    'load = __import__\nload("subprocess")',
    'import builtins as b\nb.__import__("subprocess")',
    'from builtins import __import__ as load\nload("subprocess")',
    'import importlib\nimportlib.import_module("subprocess")',
    'import importlib as il\nil.import_module("subprocess")',
    'from importlib import import_module as load\nload("subprocess")',
    'import importlib as il\nload = il.import_module\nother = load\nother("subprocess")',
    'import importlib\nmodule = "subprocess"\nimportlib.import_module(module)',
    'from . import subprocess',
    'from project.subprocess import run',
]


@pytest.mark.parametrize("source", BYPASSES)
def test_structural_import_bypasses_rejected(tmp_path, source):
    (tmp_path / "verifier.py").write_text(source)
    ok, violations = verifier.check_authority_boundary(tmp_path)
    assert ok is False
    assert len(violations) == 1
    assert violations[0].endswith("imports subprocess")


@pytest.mark.parametrize("module", verifier.FORBIDDEN_IMPORTS)
@pytest.mark.parametrize("form", ["import {module}", 'import importlib\nimportlib.import_module("{module}")'])
def test_every_listed_prohibition_is_detectable(tmp_path, module, form):
    (tmp_path / "source.py").write_text(form.format(module=module))
    assert not verifier.check_authority_boundary(tmp_path)[0]


@pytest.mark.parametrize("source", [
    '# import subprocess\ntext = "from subprocess import run"',
    'fixture = \'__import__("subprocess")\'',
    'import subprocess_tools',
    'def compute(value):\n    return value + 1',
])
def test_inert_text_and_unrelated_modules_pass(tmp_path, source):
    (tmp_path / "verifier.py").write_text(source)
    assert verifier.check_authority_boundary(tmp_path) == (True, [])


def test_invalid_source_fails_closed(tmp_path):
    (tmp_path / "bad.py").write_text("from subprocess import")
    ok, violations = verifier.check_authority_boundary(tmp_path)
    assert not ok
    assert "SyntaxError" in violations[0]


def test_empty_or_missing_source_fails_closed(tmp_path):
    assert not verifier.check_authority_boundary(tmp_path)[0]
    assert not verifier.check_authority_boundary(tmp_path / "absent")[0]


def test_real_package_positive():
    assert verifier.check_authority_boundary(Path(verifier.__file__).parent) == (True, [])


def test_nested_source_is_scanned_and_order_is_stable(tmp_path):
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "__init__.py").write_text("from subprocess import run")
    (tmp_path / "a.py").write_text("import torch")
    first = verifier.check_authority_boundary(tmp_path)
    assert not first[0]
    assert len(first[1]) == 2
    assert first == verifier.check_authority_boundary(tmp_path)
    assert "a.py" in first[1][0]


def test_run_static_uses_actual_import_boundary(tmp_path, monkeypatch):
    source = tmp_path / "verifier.py"
    source.write_text("from subprocess import run")
    monkeypatch.setattr(verifier, "__file__", str(source))
    check = verifier.Verifier(tmp_path, tmp_path)
    check.verify_static()
    record = next(c for c in check.checks if c["check"] == "static_import_boundary")
    assert record["status"] == "FAIL"


@pytest.mark.parametrize("inject", [False, True])
def test_policy_authority_check_can_fail(tmp_path, inject):
    files = {
        "G51B_ADJUDICATION_RECORD_INVENTORY.jsonl": {"claims_not_made": ["inert"]},
        "G51B_PROPOSAL_DISPOSITION_INVENTORY.jsonl": {"group_id": "other", "group_relevant": False},
        "G51B_CAPABILITY_REVIEW_REQUEST_INVENTORY.jsonl": {
            "request_state": "REVIEW_NOT_REQUESTED", "claims_not_made": ["inert"]},
        "G51B_ABSTENTION_INVENTORY.jsonl": {"kind": "none"},
    }
    if inject:
        files["G51B_ADJUDICATION_RECORD_INVENTORY.jsonl"]["nested"] = {"activation": True}
    import json
    for name, record in files.items():
        (tmp_path / name).write_text(json.dumps(record) + "\n")
    check = verifier.Verifier(tmp_path, tmp_path)
    check.verify_policy()
    record = next(c for c in check.checks if c["check"] == "authority_boundary")
    assert record["status"] == ("FAIL" if inject else "PASS")


def test_missing_inventories_cannot_claim_authority(tmp_path):
    check = verifier.Verifier(tmp_path, tmp_path)
    check.verify_policy()
    assert next(c for c in check.checks if c["check"] == "authority_boundary")["status"] == "FAIL"
