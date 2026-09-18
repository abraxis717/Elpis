from __future__ import annotations

from pathlib import Path
import runpy
import subprocess


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "tools" / "verify_public_release.py"
WORKFLOW = ROOT / ".github/workflows/pypi-publish.yaml"


def _git(repo: Path, *args: str, check: bool = True):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=check,
    )


def _commit(repo: Path, name: str) -> str:
    path = repo / "history.txt"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(name + "\n")
    _git(repo, "add", "history.txt")
    _git(repo, "commit", "-qm", name)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _fixture(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Lifecycle Probe")
    _git(repo, "config", "user.email", "probe@example.invalid")

    base = _commit(repo, "base")
    primitive = _commit(repo, "primitive")
    release = _commit(repo, "release")
    _git(
        repo,
        "tag",
        "-a",
        "Elpis9.9.9",
        "-m",
        "Elpis9.9.9 fixture",
        release,
    )
    successor = _commit(repo, "successor")

    ns = runpy.run_path(str(VERIFIER))
    check = ns["check_repository_identity"]
    g = check.__globals__
    g["REPO"] = repo
    g["RELEASE_VERSION"] = "9.9.9"
    g["RELEASE_IDENTITIES"] = {
        "9.9.9": {
            "primitive_closure_commit": primitive,
            "base_release_commit": base,
        }
    }
    return repo, check, g, {
        "base": base,
        "primitive": primitive,
        "release": release,
        "successor": successor,
    }


def test_candidate_mode_accepts_valid_tagged_successor_head(
    tmp_path: Path,
) -> None:
    _, check, _, _ = _fixture(tmp_path)
    ok, errors = check(require_git=True)
    assert ok, errors


def test_strict_mode_requires_release_tag_at_checked_out_head(
    tmp_path: Path,
) -> None:
    repo, check, _, commits = _fixture(tmp_path)

    ok, errors = check(
        require_git=True,
        require_tag=True,
        require_tag_at_head=True,
    )
    assert not ok
    assert any(
        error.startswith("RELEASE_TAG_NOT_HEAD:Elpis9.9.9:")
        for error in errors
    )

    _git(repo, "checkout", "-q", commits["release"])
    ok, errors = check(
        require_git=True,
        require_tag=True,
        require_tag_at_head=True,
    )
    assert ok, errors


def test_lightweight_release_tag_is_rejected_as_not_annotated(
    tmp_path: Path,
) -> None:
    repo, check, _, commits = _fixture(tmp_path)

    _git(repo, "tag", "-d", "Elpis9.9.9")
    _git(repo, "tag", "Elpis9.9.9", commits["release"])
    _git(repo, "checkout", "-q", commits["release"])

    ok, errors = check(
        require_git=True,
        require_tag=True,
        require_tag_at_head=True,
    )

    assert not ok
    assert "RELEASE_TAG_NOT_ANNOTATED:Elpis9.9.9" in errors
    assert not any(
        error.startswith("RELEASE_TAG_NOT_HEAD:")
        for error in errors
    )


def test_annotated_release_tag_object_passes_strict_identity_at_head(
    tmp_path: Path,
) -> None:
    repo, check, _, commits = _fixture(tmp_path)
    _git(repo, "checkout", "-q", commits["release"])

    assert (
        _git(repo, "cat-file", "-t", "refs/tags/Elpis9.9.9")
        .stdout.strip()
        == "tag"
    )
    ok, errors = check(
        require_git=True,
        require_tag=True,
        require_tag_at_head=True,
    )
    assert ok, errors


def test_pretag_candidate_passes_but_strict_mode_fails(
    tmp_path: Path,
) -> None:
    repo, check, _, _ = _fixture(tmp_path)
    _git(repo, "tag", "-d", "Elpis9.9.9")

    ok, errors = check(require_git=True)
    assert ok, errors

    ok, errors = check(
        require_git=True,
        require_tag=True,
        require_tag_at_head=True,
    )
    assert not ok
    assert errors == ["RELEASE_TAG_COMMIT_MISSING:Elpis9.9.9"]


def test_pretag_candidate_still_binds_identity_ancestry_to_head(
    tmp_path: Path,
) -> None:
    repo, check, g, commits = _fixture(tmp_path)
    _git(repo, "tag", "-d", "Elpis9.9.9")

    _git(repo, "checkout", "-q", "--orphan", "unrelated")
    for child in list(repo.iterdir()):
        if child.name != ".git" and child.is_file():
            child.unlink()
    unrelated = _commit(repo, "unrelated")
    _git(repo, "checkout", "-q", commits["successor"])

    g["RELEASE_IDENTITIES"]["9.9.9"][
        "primitive_closure_commit"
    ] = unrelated

    ok, errors = check(require_git=True)

    assert not ok
    assert any(
        error.startswith(
            "RELEASE_IDENTITY_NOT_ANCESTOR_OF_HEAD:"
            "primitive_closure_commit:"
        )
        for error in errors
    )


def test_missing_ratified_commit_fails_closed(tmp_path: Path) -> None:
    _, check, g, _ = _fixture(tmp_path)
    g["RELEASE_IDENTITIES"]["9.9.9"][
        "primitive_closure_commit"
    ] = "0" * 40

    ok, errors = check(require_git=True)

    assert not ok
    assert any(
        error.startswith(
            "RELEASE_IDENTITY_COMMIT_MISSING:"
            "primitive_closure_commit:"
        )
        for error in errors
    )


def test_identity_commit_must_be_ancestor_of_release_tag(
    tmp_path: Path,
) -> None:
    repo, check, g, commits = _fixture(tmp_path)

    _git(repo, "checkout", "-q", "--orphan", "unrelated")
    for child in list(repo.iterdir()):
        if child.name != ".git" and child.is_file():
            child.unlink()
    unrelated = _commit(repo, "unrelated")
    _git(repo, "checkout", "-q", commits["successor"])

    g["RELEASE_IDENTITIES"]["9.9.9"][
        "primitive_closure_commit"
    ] = unrelated

    ok, errors = check(require_git=True)

    assert not ok
    assert any(
        error.startswith(
            "RELEASE_IDENTITY_NOT_ANCESTOR:"
            "primitive_closure_commit:"
        )
        for error in errors
    )


def test_release_tag_must_be_ancestor_of_checked_out_head(
    tmp_path: Path,
) -> None:
    repo, check, _, _ = _fixture(tmp_path)

    _git(repo, "checkout", "-q", "--orphan", "other")
    for child in list(repo.iterdir()):
        if child.name != ".git" and child.is_file():
            child.unlink()
    _commit(repo, "other-head")

    ok, errors = check(require_git=True)

    assert not ok
    assert any(
        error.startswith(
            "RELEASE_TAG_NOT_ANCESTOR_OF_HEAD:"
            "Elpis9.9.9:"
        )
        for error in errors
    )


def test_gitless_archive_is_nonapplicable_unless_git_required(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "gitless"
    repo.mkdir()

    ns = runpy.run_path(str(VERIFIER))
    check = ns["check_repository_identity"]
    check.__globals__["REPO"] = repo

    assert check() == (True, [])
    assert check(require_git=True) == (
        False,
        ["REPOSITORY_GIT_REQUIRED"],
    )


def test_cli_exposes_candidate_and_strict_repository_modes() -> None:
    text = VERIFIER.read_text(encoding="utf-8")
    assert "--verify-candidate-repository-identity" in text
    assert "--verify-repository-identity" in text
    assert "require_tag_at_head=True" in text


def test_pypi_workflow_proves_strict_git_identity_before_archive() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    identity = text.index(
        "- name: Verify repository release identity"
    )
    export = text.index(
        "- name: Export immutable release tree"
    )
    assert identity < export
    assert (
        "python tools/verify_public_release.py "
        "--verify-repository-identity"
    ) in text


def test_shallow_candidate_checkout_is_proof_incomplete_then_full_history_passes(
    tmp_path: Path,
) -> None:
    repo, check, g, _ = _fixture(tmp_path)

    shallow = tmp_path / "shallow"
    subprocess.run(
        [
            "git",
            "clone",
            "-q",
            "--depth=1",
            "--no-tags",
            repo.resolve().as_uri(),
            str(shallow),
        ],
        check=True,
    )

    g["REPO"] = shallow

    ok, errors = check(require_git=True)
    assert not ok
    assert any(
        error.startswith(
            "REPOSITORY_HISTORY_INCOMPLETE:"
            "primitive_closure_commit:"
        )
        for error in errors
    )
    assert any(
        error.startswith(
            "REPOSITORY_HISTORY_INCOMPLETE:"
            "base_release_commit:"
        )
        for error in errors
    )
    assert not any(
        error.startswith("RELEASE_IDENTITY_COMMIT_MISSING:")
        for error in errors
    )

    _git(shallow, "fetch", "-q", "--unshallow", "--no-tags")

    ok, errors = check(require_git=True)
    assert ok, errors
