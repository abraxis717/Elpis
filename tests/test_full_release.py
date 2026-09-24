from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/full_release.py"


def load():
    spec = importlib.util.spec_from_file_location("full_release_under_test", TOOL)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_full_release_plan_has_preseal_and_exact_sealed_qualification():
    m = load()
    plan = m.plan(ROOT)
    assert plan["mode"] == "DRY_RUN_NO_COMMANDS"
    assert plan["command"] == "python tools/full_release.py --execute"
    stages = plan["stages"]
    assert stages.index("preseal_qualification") < stages.index("seal_v3_and_commit")
    assert stages.index("seal_v3_and_commit") < stages.index("exact_sealed_qualification")
    assert stages[-1] == "terminal_closed_receipt"


def test_full_release_terminal_state_is_git_private():
    source = TOOL.read_text(encoding="utf-8")
    assert "git_common_dir" in source
    assert "elpis-full-release-v1" in source
    assert 'private / "CLOSED.json"' in source
    assert "preseal_qualification_sha256" in source


def test_full_release_uses_real_installed_wheel_qualification():
    source = TOOL.read_text(encoding="utf-8")
    assert "installed_artifact_check" in source
    assert '"build",' in source
    assert '"--no-isolation",' in source
    assert '"artifacts": artifacts' in source
    assert '"pip", "install", "--no-deps"' in source
    assert "INSTALLED_ARTIFACT_IMPORT_PASS" in source
    for key in ("root_tests", "release_lifecycle", "negative_mutations", "installed_artifact", "native"):
        assert f'"{key}"' in source
    assert "tools/run_mutation_suite_ci.py" in source
    assert "tools/run_inference_native_locus.py" in source


def test_full_release_outer_mutations_are_lock_and_journal_guarded():
    source = TOOL.read_text(encoding="utf-8")
    assert "class OuterJournal" in source
    assert "_exclusive_lock" in source
    for stage in ("seal_commit", "assertion_commit", "ratification_commit", "final_main_push"):
        assert f'"{stage}"' in source
    assert "FULL_RELEASE_JOURNAL_CHAIN_INVALID" in source


def test_full_release_reuses_hardened_boundary_for_closeout_observation():
    source = TOOL.read_text(encoding="utf-8")
    assert "orchestrator_io.LiveBoundary" in source
    assert 'boundary.workflows("MAIN_HOSTED_GREEN", intent)' in source
    block = source[source.index("def closeout_runs"):source.index("def ensure_final_push")]
    assert "for page in range" not in block


def test_full_release_final_push_uses_fixed_repository_url():
    source = TOOL.read_text(encoding="utf-8")
    assert 'return f"https://github.com/{REPOSITORY}.git"' in source
    block = source[source.index("def ensure_final_push"):source.index("def plan")]
    assert "remote_url()" in block
    assert '"origin"' not in block
    assert "--force-with-lease=refs/heads/main:" in block


def test_outer_journal_hash_chain_and_completion(tmp_path):
    m = load()
    path = tmp_path / "journal.json"
    journal = m.OuterJournal(path)
    journal.begin("seal_commit", {"development_sha": "a" * 40})
    journal.returned("seal_commit", {"candidate_sha": "b" * 40})
    journal.complete("seal_commit", {"candidate_sha": "b" * 40})
    assert journal.completed("seal_commit")
    assert journal.active() is None

    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["events"][0]["data"]["development_sha"] = "c" * 40
    path.write_text(json.dumps(raw), encoding="utf-8")
    try:
        m.OuterJournal(path)
    except m.FullReleaseError as exc:
        assert "FULL_RELEASE_JOURNAL_CHAIN_INVALID" in str(exc)
    else:
        raise AssertionError("tampered journal unexpectedly accepted")


def test_full_release_delegates_remote_publication_to_existing_orchestrator():
    source = TOOL.read_text(encoding="utf-8")
    assert "tools/release_orchestrator.py" in source
    assert "GITHUB_RELEASE_PUBLISHED" not in source


def test_full_release_never_force_pushes_a_tag():
    source = TOOL.read_text(encoding="utf-8")
    assert "--force-with-lease=refs/heads/main:" in source
    assert "refs/tags/" not in source
    assert "update-ref" not in source


def test_full_release_direct_cli_resolves_repository_release_modules():
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, str(TOOL)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["mode"] == "DRY_RUN_NO_COMMANDS"
    assert payload["command"] == "python tools/full_release.py --execute"


def test_lower_release_entrypoints_have_deterministic_direct_script_fallbacks():
    import subprocess
    import sys

    machine = (ROOT / "tools" / "release_orchestrator.py").read_text(encoding="utf-8")
    boundary = (ROOT / "tools" / "release_orchestrator_io.py").read_text(encoding="utf-8")

    assert machine.count("except (ModuleNotFoundError, ImportError):") == 2
    assert boundary.count("except (ModuleNotFoundError, ImportError):") == 1

    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "release_orchestrator.py"), "--help"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr


def test_installed_artifact_build_is_exported_from_git_tree():
    source = TOOL.read_text(encoding="utf-8")
    block = source[
        source.index("def installed_artifact_check"):
        source.index("def qualification_checks")
    ]
    assert '"git", "archive", "--format=tar"' in block
    assert "snapshot.extract_git_archive" in block
    assert '"--no-isolation"' in block
    assert '"SOURCE_DATE_EPOCH"' in block
    assert "proc = run(source, build_argv, env=build_env)" in block
    assert "proc = run(root, build_argv, env=env)" not in block
