from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/full_release.py"


def load():
    spec = importlib.util.spec_from_file_location("full_release_under_test", TOOL)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_full_release_plan_ends_in_terminal_closeout():
    m = load()
    plan = m.plan(ROOT)
    assert plan["mode"] == "DRY_RUN_NO_COMMANDS"
    assert plan["command"] == "python tools/full_release.py --execute"
    assert plan["stages"][-1] == "terminal_closed_receipt"
    assert "publication_assertion_commit" in plan["stages"]
    assert "separate_ratification_commit" in plan["stages"]
    assert "final_main_fast_forward" in plan["stages"]
    assert "required_closeout_hosted_workflows" in plan["stages"]


def test_full_release_terminal_state_is_git_private():
    source = TOOL.read_text(encoding="utf-8")
    assert "git_common_dir" in source
    assert "elpis-full-release-v1" in source
    assert 'private / "CLOSED.json"' in source


def test_full_release_uses_exact_lower_level_qualification_categories():
    source = TOOL.read_text(encoding="utf-8")
    for key in ("root_tests", "release_lifecycle", "negative_mutations", "installed_artifact", "native"):
        assert f'"{key}"' in source
    assert "tools/run_mutation_suite_ci.py" in source
    assert "verify_inference_native_locus.py" in source


def test_full_release_delegates_remote_publication_to_existing_orchestrator():
    source = TOOL.read_text(encoding="utf-8")
    assert "tools/release_orchestrator.py" in source
    assert "GITHUB_RELEASE_PUBLISHED" not in source


def test_full_release_never_force_pushes_a_tag():
    source = TOOL.read_text(encoding="utf-8")
    assert "--force-with-lease=refs/heads/main:" in source
    assert "refs/tags/" not in source
    assert "update-ref" not in source
