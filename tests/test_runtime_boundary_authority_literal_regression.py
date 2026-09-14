from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "tools/verify_public_release.py"


def _load_verifier():
    spec = importlib.util.spec_from_file_location(
        "elpis_public_release_verifier_regression",
        VERIFIER,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_runtime_authority_literal_guard_accepts_false_only():
    module = _load_verifier()
    tree = ast.parse(
        "def x():\n"
        "    return {\n"
        "        \"execution_authorized\": False,\n"
        "        \"validation_authorized\": False,\n"
        "    }\n"
    )
    assert module._runtime_authority_literal_findings(tree) == []


def test_runtime_authority_literal_guard_rejects_true_dict_literal():
    module = _load_verifier()
    tree = ast.parse(
        "def _backdoor():\n"
        "    return {\n"
        "        \"execution_authorized\": True,\n"
        "        \"validation_authorized\": True,\n"
        "    }\n"
    )
    findings = module._runtime_authority_literal_findings(tree)
    assert any("execution_authorized:non_false_dict_literal" in x for x in findings)
    assert any("validation_authorized:non_false_dict_literal" in x for x in findings)


def test_runtime_authority_literal_guard_rejects_true_call_literal():
    module = _load_verifier()
    tree = ast.parse(
        "def x(C):\n"
        "    return C(\n"
        "        execution_authorized=True,\n"
        "        validation_authorized=False,\n"
        "    )\n"
    )
    findings = module._runtime_authority_literal_findings(tree)
    assert any("execution_authorized:non_false_call_literal" in x for x in findings)
