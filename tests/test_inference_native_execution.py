from __future__ import annotations

import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/run_inference_native_locus.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("native_execution", TOOL)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def authority():
    nodeids = ("a.py::test_a", "b.py::test_b")
    tool = load_tool()
    return {
        "count": 2,
        "nodeids": list(nodeids),
        "nodeids_sha256": tool.digest_lines(nodeids),
    }


def test_exact_execution_validator_accepts_only_exact_ordered_set():
    tool = load_tool()
    section = authority()
    totals = {"tests": 2, "failures": 0, "errors": 0, "skipped": 0}
    assert tool.validate_execution(
        section,
        section["nodeids"],
        totals,
    ) == section["nodeids_sha256"]


def test_same_cardinality_wrong_executed_set_is_rejected():
    tool = load_tool()
    section = authority()
    totals = {"tests": 2, "failures": 0, "errors": 0, "skipped": 0}
    with pytest.raises(ValueError, match="NODE_SET_MISMATCH"):
        tool.validate_execution(section, ("a.py::test_a", "x.py::test_x"), totals)


def test_skip_or_failure_cannot_satisfy_exact_execution():
    tool = load_tool()
    section = authority()
    with pytest.raises(ValueError, match="JUNIT_NONPASS"):
        tool.validate_execution(
            section,
            section["nodeids"],
            {"tests": 2, "failures": 0, "errors": 0, "skipped": 1},
        )


def test_hosted_native_workflow_uses_execution_runner_for_both_sections():
    workflow = (ROOT / ".github/workflows/inference-native-r0.yml").read_text(
        encoding="utf-8"
    )
    invocation = "python tools/run_inference_native_locus.py"
    assert workflow.count(invocation) == 2
    assert "--section provider" in workflow
    assert "--section locus" in workflow
    assert "NATIVE_PROVIDER_CORE_7_OF_7_PASS" not in workflow
    assert "NATIVE_INFERENCE_LOCUS_EXACT_SET_PASS" not in workflow
