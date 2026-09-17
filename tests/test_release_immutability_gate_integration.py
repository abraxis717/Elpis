from __future__ import annotations

import runpy
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=ROOT/"tools/verify_public_release.py"
SEALER=ROOT/"tools/seal_release.py"
CI=ROOT/".github/workflows/ci.yml"


def test_public_release_exports_immutability_check_and_current_tree_passes():
    ns=runpy.run_path(str(PUBLIC))
    ok,errors=ns["check_repository_immutability"]()
    assert ok is True, errors
    assert errors==[]


def test_public_release_cli_guard_precedes_main_dispatch():
    text=PUBLIC.read_text(encoding="utf-8")
    block=text[text.rfind('if __name__ == "__main__":'):]
    assert "check_repository_immutability()" in block
    assert block.index("check_repository_immutability()") < block.index("main(")
    assert "REPOSITORY_IMMUTABILITY: FAIL" in block


def test_public_release_history_anchor_is_required_only_in_git_checkout():
    text=PUBLIC.read_text(encoding="utf-8")
    assert 'check_history=(REPO / ".git").exists()' in text


def test_sealer_enforces_immutability_at_final_prewrite_boundary():
    text=SEALER.read_text(encoding="utf-8")
    load='verifier = runpy.run_path(str(REPO / "tools/verify_public_release.py"))'
    call='verifier["check_repository_immutability"]()'
    assert load in text and call in text
    assert text.index(load) < text.index('identity = verifier["release_identity"]()')
    assert text.index("REFUSED: SYMLINK ESCAPE") < text.index(call)
    assert text.index("REFUSED: ephemeral artifacts present:") < text.index(call)
    assert text.index(call) < text.index("if manifest.exists():")
    segment=text[text.rfind("if stray:"):text.index("if manifest.exists():")]
    assert "if not override:" in segment


def test_hosted_ci_has_independent_immutability_step():
    text=CI.read_text(encoding="utf-8")
    assert text.count("run: python tools/verify_immutable_evidence.py")==1
    assert "Verify immutable repository evidence and identities" in text


def test_public_release_embedded_gate_rejects_model_identity_mutation(tmp_path):
    repo=tmp_path/"repo"
    subprocess.run(
        ["git","clone","-q","--no-hardlinks",str(ROOT),str(repo)],
        check=True,
    )
    shutil.copy2(PUBLIC, repo/"tools/verify_public_release.py")

    model=repo/"src/elpis_reference/model.py"
    text=model.read_text(encoding="utf-8")
    old="6daec5f499d115beb14e23f3a9cf56d1166b99c1ccd36b185a19ea5dfec9a137"
    assert old in text
    model.write_text(text.replace(old,"0"*64,1),encoding="utf-8")

    ns=runpy.run_path(str(repo/"tools/verify_public_release.py"))
    ok,errors=ns["check_repository_immutability"]()
    assert ok is False
    assert any("FROZEN_IDENTITY_DRIFT" in item for item in errors)
