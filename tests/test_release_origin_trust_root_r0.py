import os
from pathlib import Path
import subprocess

import pytest

from tools import release_origin


def git(*args, cwd=None):
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def repository(path: Path) -> Path:
    path.mkdir()
    git("init", "-q", str(path))
    return path


def committed_repository(path: Path) -> Path:
    repository(path)

    git(
        "config",
        "user.name",
        "Elpis Test",
        cwd=path,
    )
    git(
        "config",
        "user.email",
        "elpis-test@example.invalid",
        cwd=path,
    )

    (path / "tracked.txt").write_text("authority\n")

    git("add", "tracked.txt", cwd=path)
    git(
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-q",
        "-m",
        "initial",
        cwd=path,
    )

    return path


def test_external_hardlink_to_repository_storage_is_rejected(
    tmp_path,
):
    repo = repository(tmp_path / "repo")
    external = tmp_path / "external"
    external.mkdir()

    inside = repo / "repository-owned-signers"
    inside.write_text("authority\n")

    authority = external / "allowed_signers"
    os.link(inside, authority)

    with pytest.raises(
        ValueError,
        match="ORIGIN_TRUST_ROOT_IN_REPOSITORY_STORAGE",
    ):
        release_origin._validate_trust_root_storage(
            repo,
            authority,
        )


def test_external_hardlink_to_common_git_storage_is_rejected(
    tmp_path,
):
    repo = committed_repository(tmp_path / "main")
    worktree = tmp_path / "linked-worktree"

    git(
        "worktree",
        "add",
        "-q",
        "-b",
        "trust-root-test",
        str(worktree),
        cwd=repo,
    )

    common = Path(
        git(
            "rev-parse",
            "--path-format=absolute",
            "--git-common-dir",
            cwd=worktree,
        )
    )

    # This file is outside the visible linked worktree but inside
    # repository-controlled common Git storage.
    inside = common / "repository-owned-signers"
    inside.write_text("authority\n")

    external = tmp_path / "external"
    external.mkdir()

    authority = external / "allowed_signers"
    os.link(inside, authority)

    assert not authority.is_relative_to(worktree)
    assert not common.is_relative_to(worktree)

    with pytest.raises(
        ValueError,
        match="ORIGIN_TRUST_ROOT_IN_REPOSITORY_STORAGE",
    ):
        release_origin._validate_trust_root_storage(
            worktree,
            authority,
        )


def test_storage_root_census_includes_external_common_git_dir(
    tmp_path,
):
    repo = committed_repository(tmp_path / "main")
    worktree = tmp_path / "linked-worktree"

    git(
        "worktree",
        "add",
        "-q",
        "-b",
        "storage-census-test",
        str(worktree),
        cwd=repo,
    )

    roots = release_origin._repository_storage_roots(
        worktree
    )

    common = Path(
        git(
            "rev-parse",
            "--path-format=absolute",
            "--git-common-dir",
            cwd=worktree,
        )
    ).resolve()

    assert worktree.resolve() in roots
    assert common in roots


def test_group_writable_signer_authority_is_rejected(
    tmp_path,
):
    repo = repository(tmp_path / "repo")
    external = tmp_path / "external"
    external.mkdir()

    authority = external / "allowed_signers"
    authority.write_text("authority\n")
    authority.chmod(0o660)

    with pytest.raises(
        ValueError,
        match="ORIGIN_TRUST_ROOT_MODE_UNSAFE",
    ):
        release_origin._validate_trust_root_storage(
            repo,
            authority,
        )


def test_world_writable_signer_authority_is_rejected(
    tmp_path,
):
    repo = repository(tmp_path / "repo")
    external = tmp_path / "external"
    external.mkdir()

    authority = external / "allowed_signers"
    authority.write_text("authority\n")
    authority.chmod(0o666)

    with pytest.raises(
        ValueError,
        match="ORIGIN_TRUST_ROOT_MODE_UNSAFE",
    ):
        release_origin._validate_trust_root_storage(
            repo,
            authority,
        )


def test_independent_owner_only_signer_authority_is_accepted(
    tmp_path,
):
    repo = repository(tmp_path / "repo")
    external = tmp_path / "external"
    external.mkdir()

    authority = external / "allowed_signers"
    authority.write_text("authority\n")
    authority.chmod(0o600)

    identity = (
        release_origin._validate_trust_root_storage(
            repo,
            authority,
        )
    )

    st = authority.stat()

    assert identity[:2] == (
        st.st_dev,
        st.st_ino,
    )
    assert identity[3] == os.geteuid()
