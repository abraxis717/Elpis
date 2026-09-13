from __future__ import annotations

from pathlib import Path
import runpy
import subprocess


REPO = Path(__file__).resolve().parents[1]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")

    (repo / "tracked.txt").write_text("tracked\\n", encoding="utf-8")
    (repo / "PUBLISHED_RELEASES.json").write_text("{}\\n", encoding="utf-8")
    local = repo / ".astra_tmp" / "codex-bwrap-synthetic-mount-targets-1000"
    local.mkdir(parents=True)
    (local / "lock").write_text("clone-local\\n", encoding="utf-8")

    _git(repo, "add", "tracked.txt", "PUBLISHED_RELEASES.json")
    return repo


def test_sealer_manifest_membership_uses_git_tracked_tree(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    ns = runpy.run_path(str(REPO / "tools" / "seal_release.py"))
    tree_files = ns["tree_files"]
    tree_files.__globals__["REPO"] = repo

    files = tree_files(Path("manifests/Elpis9.9.9.RELEASE_MANIFEST.json"))

    assert files == ["tracked.txt"]


def test_verifier_manifest_membership_uses_git_tracked_tree(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    ns = runpy.run_path(str(REPO / "tools" / "verify_public_release.py"))
    actual_files = ns["actual_files"]
    actual_files.__globals__["REPO"] = repo
    actual_files.__globals__["MANIFEST_REL"] = Path(
        "manifests/Elpis9.9.9.RELEASE_MANIFEST.json"
    )

    files = actual_files()

    assert files == {"tracked.txt"}

def test_git_ignored_packageable_source_is_manifest_visible(tmp_path: Path) -> None:
    repo = tmp_path / "repo_ignored_packageable"
    repo.mkdir()
    _git(repo, "init")

    (repo / "tracked.txt").write_text("tracked\\n", encoding="utf-8")
    (repo / "PUBLISHED_RELEASES.json").write_text("{}\\n", encoding="utf-8")
    packageable = repo / "src" / "pkg" / "_aux_rt.py"
    packageable.parent.mkdir(parents=True)
    packageable.write_text(
        "import subprocess\\nPAYLOAD = (eval, compile, subprocess.run)\\n",
        encoding="utf-8",
    )
    local = repo / ".astra_tmp" / "codex-bwrap-synthetic-mount-targets-1000" / "lock"
    local.parent.mkdir(parents=True)
    local.write_text("clone-local\\n", encoding="utf-8")

    _git(repo, "add", "tracked.txt", "PUBLISHED_RELEASES.json")
    exclude = repo / ".git" / "info" / "exclude"
    exclude.write_text(
        exclude.read_text(encoding="utf-8")
        + "\\n.astra_tmp/\\nsrc/pkg/_aux_rt.py\\n",
        encoding="utf-8",
    )

    ns = runpy.run_path(str(REPO / "tools" / "verify_public_release.py"))
    actual_files = ns["actual_files"]
    g = actual_files.__globals__
    g["REPO"] = repo
    g["MANIFEST_REL"] = Path("manifests/Elpis9.9.9.RELEASE_MANIFEST.json")

    files = actual_files()

    assert "src/pkg/_aux_rt.py" in files
    assert not any(path.startswith(".astra_tmp/") for path in files)


def test_nonignored_untracked_file_is_manifest_visible(tmp_path: Path) -> None:
    repo = tmp_path / "repo_untracked"
    repo.mkdir()
    _git(repo, "init")

    (repo / "tracked.txt").write_text("tracked\\n", encoding="utf-8")
    (repo / "PUBLISHED_RELEASES.json").write_text("{}\\n", encoding="utf-8")
    (repo / "extra.txt").write_text("untracked\\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt", "PUBLISHED_RELEASES.json")

    ns = runpy.run_path(str(REPO / "tools" / "verify_public_release.py"))
    actual_files = ns["actual_files"]
    g = actual_files.__globals__
    g["REPO"] = repo
    g["MANIFEST_REL"] = Path("manifests/Elpis9.9.9.RELEASE_MANIFEST.json")

    assert "extra.txt" in actual_files()
