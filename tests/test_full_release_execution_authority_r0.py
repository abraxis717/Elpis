import os
import subprocess
from pathlib import Path

import pytest

from tools import full_release


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args],
        text=True,
    ).strip()


def _init(repo: Path):
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Astra Test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "astra@example.invalid"],
        check=True,
    )


def test_full_release_base_env_is_sealed(monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_REPLACE_REF_BASE", "refs/evil/")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("SSL_CERT_FILE", "/tmp/evil-ca")

    env = full_release.base_env()

    assert "GIT_CONFIG_COUNT" not in env
    assert "GIT_REPLACE_REF_BASE" not in env
    assert "HTTPS_PROXY" not in env
    assert "SSL_CERT_FILE" not in env
    assert env["GIT_CONFIG_GLOBAL"] == os.devnull
    assert env["GIT_CONFIG_SYSTEM"] == os.devnull


def test_full_release_git_ignores_replace_objects(tmp_path):
    repo = tmp_path / "repo"
    _init(repo)

    (repo / "x").write_text("A\n")
    subprocess.run(["git", "-C", str(repo), "add", "x"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "A"], check=True)
    a = _git(repo, "rev-parse", "HEAD")

    (repo / "x").write_text("B\n")
    subprocess.run(["git", "-C", str(repo), "add", "x"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "B"], check=True)
    b = _git(repo, "rev-parse", "HEAD")

    subprocess.run(["git", "-C", str(repo), "replace", b, a], check=True)

    control = subprocess.check_output(
        ["git", "-C", str(repo), "show", f"{b}:x"],
        text=True,
    )
    hardened = full_release.git(repo, "show", f"{b}:x")

    assert control.strip() == "A"
    assert hardened == "B"


def test_local_url_rewrite_is_rejected(tmp_path):
    repo = tmp_path / "repo"
    _init(repo)

    subprocess.run(
        [
            "git", "-C", str(repo), "config", "--local",
            "url.file:///tmp/evil.git.insteadOf",
            "https://github.com/abraxis717/Elpis.git",
        ],
        check=True,
    )

    with pytest.raises(
        full_release.FullReleaseError,
        match="EFFECTIVE_GIT_URL_REWRITE_FORBIDDEN",
    ):
        full_release.require_no_local_url_rewrite(repo)


def test_authority_commit_disables_precommit_hook(tmp_path):
    repo = tmp_path / "repo"
    _init(repo)

    target = repo / "authority.json"
    target.write_text('{"value":"base"}\n')
    subprocess.run(["git", "-C", str(repo), "add", "authority.json"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "base"], check=True)

    intended = b'{"value":"intended"}\n'
    target.write_bytes(intended)
    subprocess.run(["git", "-C", str(repo), "add", "authority.json"], check=True)

    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text(
        "#!/bin/sh\n"
        "printf '{\"value\":\"forged\"}\\n' > authority.json\n"
        "git add authority.json\n"
        "printf ran > ../hook-ran\n"
    )
    hook.chmod(0o755)

    proc = full_release.authority_commit(repo, "authority")
    assert proc.returncode == 0

    commit = full_release.git(repo, "rev-parse", "HEAD")

    assert not (tmp_path / "hook-ran").exists()
    assert (
        full_release.committed_path_bytes(
            repo, commit, "authority.json"
        ) == intended
    )



def test_effective_url_rewrite_from_local_include_is_rejected(
    tmp_path,
):
    repo = tmp_path / "repo"
    _init(repo)

    included = tmp_path / "included.gitconfig"
    included.write_text(
        '[url "file:///tmp/evil.git"]\n'
        '    pushInsteadOf = https://github.com/abraxis717/Elpis.git\n'
    )

    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "config",
            "--local",
            "include.path",
            str(included),
        ],
        check=True,
    )

    old = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "config",
            "--local",
            "--get-regexp",
            r"^url\..*\.(insteadOf|pushInsteadOf)$",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert old.returncode == 1
    assert old.stdout == b""

    with pytest.raises(
        full_release.FullReleaseError,
        match="EFFECTIVE_GIT_URL_REWRITE_FORBIDDEN",
    ):
        full_release.require_no_local_url_rewrite(repo)



def test_full_release_rejects_effective_git_https_override(
    tmp_path,
):
    repo = tmp_path / "repo"
    _init(repo)

    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "config",
            "--local",
            "http.proxy",
            "http://127.0.0.1:9",
        ],
        check=True,
    )

    with pytest.raises(
        full_release.FullReleaseError,
        match="EFFECTIVE_GIT_HTTPS_OVERRIDE_FORBIDDEN",
    ):
        full_release.require_no_local_url_rewrite(repo)
