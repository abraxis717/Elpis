from __future__ import annotations

from pathlib import Path
import runpy
import subprocess


REPO = Path(__file__).resolve().parents[1]
LOCAL_STATE = ".local_tool_state"


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

    (repo / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    (repo / "PUBLISHED_RELEASES.json").write_text("{}\n", encoding="utf-8")
    local = repo / LOCAL_STATE / "runner" / "lock"
    local.parent.mkdir(parents=True)
    local.write_text("clone-local\n", encoding="utf-8")

    _git(repo, "add", "tracked.txt", "PUBLISHED_RELEASES.json")
    exclude = repo / ".git" / "info" / "exclude"
    exclude.write_text(
        exclude.read_text(encoding="utf-8") + f"\n{LOCAL_STATE}/\n",
        encoding="utf-8",
    )
    return repo


def _verifier_namespace(repo: Path):
    ns = runpy.run_path(str(REPO / "tools" / "verify_public_release.py"))
    actual_files = ns["actual_files"]
    actual_files.__globals__["REPO"] = repo
    actual_files.__globals__["MANIFEST_REL"] = Path(
        "manifests/Elpis9.9.9.RELEASE_MANIFEST.json"
    )
    return ns


def test_sealer_manifest_membership_uses_git_tracked_tree(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    ns = runpy.run_path(str(REPO / "tools" / "seal_release.py"))
    tree_files = ns["tree_files"]
    tree_files.__globals__["REPO"] = repo

    files = tree_files(Path("manifests/Elpis9.9.9.RELEASE_MANIFEST.json"))

    assert files == ["tracked.txt"]


def test_verifier_manifest_membership_uses_git_tracked_tree(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    ns = _verifier_namespace(repo)

    assert ns["actual_files"]() == {"tracked.txt"}


def test_git_ignored_untracked_source_is_not_manifest_authority_but_is_scanned(
    tmp_path: Path,
) -> None:
    repo = _fixture_repo(tmp_path)
    packageable = repo / "src" / "pkg" / "_aux_rt.py"
    packageable.parent.mkdir(parents=True)
    packageable.write_text(
        "import subprocess\nPAYLOAD = (eval, compile, subprocess.run)\n",
        encoding="utf-8",
    )
    exclude = repo / ".git" / "info" / "exclude"
    exclude.write_text(
        exclude.read_text(encoding="utf-8") + "src/pkg/_aux_rt.py\n",
        encoding="utf-8",
    )

    ns = _verifier_namespace(repo)
    files = ns["actual_files"]()
    physical = {
        path.relative_to(repo).as_posix()
        for path in ns["release_paths"]()
        if path.is_file() or path.is_symlink()
    }

    assert "src/pkg/_aux_rt.py" not in files
    assert not any(path.startswith(f"{LOCAL_STATE}/") for path in files)
    assert "src/pkg/_aux_rt.py" in physical
    assert any(path.startswith(f"{LOCAL_STATE}/") for path in physical)


def test_nonignored_untracked_file_is_not_git_manifest_authority(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    (repo / "extra.txt").write_text("untracked\n", encoding="utf-8")
    ns = _verifier_namespace(repo)

    assert ns["actual_files"]() == {"tracked.txt"}


def test_gitless_export_uses_physical_tree_and_junk_fails_closed(tmp_path: Path) -> None:
    export = tmp_path / "exported-public-tree"
    export.mkdir()
    (export / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    (export / "PUBLISHED_RELEASES.json").write_text("{}\n", encoding="utf-8")

    ns = _verifier_namespace(export)
    assert ns["actual_files"]() == {"tracked.txt"}

    junk = export / LOCAL_STATE / "runner" / "lock"
    junk.parent.mkdir(parents=True)
    junk.write_text("undeclared\n", encoding="utf-8")

    assert ns["actual_files"]() == {
        "tracked.txt",
        f"{LOCAL_STATE}/runner/lock",
    }
