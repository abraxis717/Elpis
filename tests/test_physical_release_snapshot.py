"""Run the successor verifier against immutable 2.2.30 fixtures, never edit the tag."""
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import tarfile

import pytest

from tools import release_snapshot as snapshot

ROOT = Path(__file__).resolve().parents[1]
BASE = "11b9a7eb8c3f1811b7cc4e3b58f2f2dea771d924"
SOURCE = "src/elpis_reference/cli.py"


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE)


@pytest.fixture
def checkout(tmp_path):
    root = tmp_path / "repo"
    git(ROOT, "clone", "--quiet", "--shared", str(ROOT), str(root))
    git(root, "checkout", "--quiet", "--detach", BASE)
    git(root, "config", "user.name", "Fixture")
    git(root, "config", "user.email", "fixture@example.invalid")
    return root


def verify(root):
    ns = runpy.run_path(str(ROOT / "tools/verify_public_release.py"))
    fn = ns["check_manifest"]
    rel = Path("manifests/Elpis2.2.30.RELEASE_MANIFEST.json")
    fn.__globals__.update(REPO=root, RELEASE_VERSION="2.2.30", MANIFEST_REL=rel, MANIFEST=root / rel)
    return fn()


@pytest.mark.parametrize("ref", [BASE, "Elpis2.2.30"])
def test_exact_historical_checkout(checkout, ref):
    git(checkout, "checkout", "--quiet", "--detach", ref)
    assert verify(checkout) == (True, [])


@pytest.mark.parametrize("attack", ["unstaged", "staged", "committed", "skip-worktree",
    "assume-unchanged", "untracked", "ignored", "hidden-delete", "symlink", "directory",
    "nested-git", "executable", "ratification", "historical-registry"])
def test_physical_attacks(checkout, attack):
    source = checkout / SOURCE
    if attack in {"skip-worktree", "assume-unchanged", "hidden-delete"}:
        git(checkout, "update-index", "--assume-unchanged" if attack == "assume-unchanged" else "--skip-worktree", SOURCE)
    if attack in {"unstaged", "staged", "committed", "skip-worktree", "assume-unchanged"}:
        source.write_text(source.read_text() + "\nimport os; os.system('echo hostile')\n")
        if attack in {"staged", "committed"}:
            git(checkout, "add", SOURCE)
        if attack == "committed":
            git(checkout, "-c", "commit.gpgsign=false", "commit", "-qm", "hostile fixture")
    elif attack in {"untracked", "ignored", "nested-git"}:
        rel = "src/elpis_reference/hostile.py"
        if attack == "ignored":
            (checkout / ".git/info/exclude").write_text(rel + "\n")
        if attack == "nested-git":
            rel = "src/elpis_reference/.git/hostile.py"
            (checkout / rel).parent.mkdir()
        (checkout / rel).write_text("import os\n")
    elif attack in {"hidden-delete", "symlink", "directory"}:
        source.unlink()
        if attack == "symlink":
            source.symlink_to("model.py")
        elif attack == "directory":
            source.mkdir()
    elif attack == "executable":
        source.chmod(source.stat().st_mode ^ 0o111)
    elif attack == "ratification":
        (checkout / "RELEASE_RATIFICATIONS/Elpis2.2.30.json").write_text("{}")
    elif attack == "historical-registry":
        p = checkout / "PUBLISHED_RELEASES.json"
        p.write_bytes(p.read_bytes() + b"\n")
    ok, errors = verify(checkout)
    assert not ok, attack
    assert errors


def test_tag_mutation_and_tag_deletion_fail(checkout):
    git(checkout, "checkout", "--quiet", "--detach", "Elpis2.2.30")
    p = checkout / SOURCE
    p.write_text(p.read_text() + "\n# hostile\n")
    assert not verify(checkout)[0]
    git(checkout, "checkout", "--quiet", "--detach", BASE)
    git(checkout, "tag", "-d", "Elpis2.2.30")
    assert not verify(checkout)[0]


def test_assertion_only_closeout_is_valid(checkout):
    (checkout / "RELEASE_RATIFICATIONS/Elpis2.2.30.json").unlink()
    assert verify(checkout) == (True, [])


@pytest.mark.parametrize("name,kind,target", [
    ("../escape", tarfile.REGTYPE, ""), ("/escape", tarfile.REGTYPE, ""),
    ("a", tarfile.SYMTYPE, "../escape"), ("a", tarfile.LNKTYPE, "x"),
    ("a", tarfile.FIFOTYPE, ""),
])
def test_archive_rejects_unsafe_members(tmp_path, name, kind, target):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w") as archive:
        member = tarfile.TarInfo(name)
        member.type, member.linkname = kind, target
        archive.addfile(member)
    data.seek(0)
    with tarfile.open(fileobj=data) as archive, pytest.raises(ValueError):
        snapshot.extract_git_archive(archive, tmp_path)


def test_development_verdict_cannot_claim_public_release():
    source = (ROOT / "tools/verify_public_release.py").read_text()
    assert "development checks; no release-snapshot or origin claim" in source
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "python tools/verify_public_release.py --development" in ci
    assert "if: github.event_name == 'release' || startsWith(github.ref, 'refs/tags/')" in ci
