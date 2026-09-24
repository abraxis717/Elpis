import os
import subprocess
from pathlib import Path

import pytest

from tools import release_orchestrator as machine
from tools import release_git
from tools.release_orchestrator_io import (
    LiveBoundary,
    Runner,
    sealed_subprocess_env,
)


def test_sealed_environment_drops_graph_config_proxy_and_ca(monkeypatch):
    poisoned = {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "url.file:///tmp/evil.insteadOf",
        "GIT_CONFIG_VALUE_0": "https://github.com/abraxis717/Elpis.git",
        "GIT_REPLACE_REF_BASE": "refs/evil/",
        "GIT_DIR": "/tmp/evil.git",
        "GIT_WORK_TREE": "/tmp/evil",
        "HTTPS_PROXY": "http://127.0.0.1:9",
        "https_proxy": "http://127.0.0.1:9",
        "SSL_CERT_FILE": "/tmp/evil-ca.pem",
        "SSL_CERT_DIR": "/tmp/evil-ca-dir",
    }
    for key, value in poisoned.items():
        monkeypatch.setenv(key, value)

    env = sealed_subprocess_env()

    for key in poisoned:
        assert key not in env

    assert env["GIT_CONFIG_NOSYSTEM"] == "1"
    assert env["GIT_CONFIG_SYSTEM"] == os.devnull
    assert env["GIT_CONFIG_GLOBAL"] == os.devnull
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GH_PROMPT_DISABLED"] == "1"


def test_runner_does_not_forward_poisoned_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("SSL_CERT_FILE", "/tmp/evil-ca.pem")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")

    result = Runner().command(
        [
            os.sys.executable,
            "-c",
            (
                "import os;"
                "print(os.environ.get('HTTPS_PROXY'));"
                "print(os.environ.get('SSL_CERT_FILE'));"
                "print(os.environ.get('GIT_CONFIG_COUNT'))"
            ),
        ],
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert result.stdout.decode().splitlines() == ["None", "None", "None"]


class CaptureRunner:
    def __init__(self):
        self.argv = None

    def command(self, argv, *, cwd, data=None):
        self.argv = list(argv)

        class Result:
            returncode = 0
            stdout = b"deadbeef"
            stderr = b""

        return Result()


def test_live_boundary_git_disables_replace_objects(tmp_path):
    runner = CaptureRunner()
    boundary = LiveBoundary(
        tmp_path,
        tmp_path / "qualification.json",
        runner=runner,
    )

    boundary.git("rev-parse", "HEAD")

    assert runner.argv[:2] == ["git", "--no-replace-objects"]


def test_local_url_rewrite_is_forbidden(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        [
            "git", "-C", str(tmp_path), "config", "--local",
            "url.file:///tmp/evil.git.insteadOf",
            "https://github.com/abraxis717/Elpis.git",
        ],
        check=True,
    )

    boundary = LiveBoundary(
        tmp_path,
        tmp_path / "qualification.json",
    )

    with pytest.raises(machine.ReleaseError, match="EFFECTIVE_GIT_URL_REWRITE_FORBIDDEN"):
        boundary.verify_git_transport_policy()



def test_effective_url_rewrite_from_local_include_is_forbidden(
    tmp_path,
):
    repo = tmp_path / "repo"
    repo.mkdir()

    subprocess.run(
        ["git", "init", "-q", str(repo)],
        check=True,
    )

    included = tmp_path / "included.gitconfig"
    included.write_text(
        '[url "file:///tmp/evil.git"]\n'
        '    insteadOf = https://github.com/abraxis717/Elpis.git\n'
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

    # Demonstrate the old local-only URL-key census would see no key:
    # the local file contains include.path, while the rewrite itself is
    # resolved only through the effective configuration stack.
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

    boundary = LiveBoundary(
        repo,
        repo / "qualification.json",
    )

    with pytest.raises(
        machine.ReleaseError,
        match="EFFECTIVE_GIT_URL_REWRITE_FORBIDDEN",
    ):
        boundary.verify_git_transport_policy()



def test_sealed_environment_drops_git_https_overrides(
    monkeypatch,
):
    poisoned = {
        "GIT_SSL_NO_VERIFY": "1",
        "GIT_SSL_CAINFO": "/tmp/evil-ca.pem",
        "GIT_SSL_CAPATH": "/tmp/evil-ca",
        "GIT_HTTP_PROXY": "http://127.0.0.1:9",
        "GIT_PROXY_COMMAND": "/tmp/evil-proxy",
    }

    for key, value in poisoned.items():
        monkeypatch.setenv(key, value)

    env = sealed_subprocess_env()

    for key in poisoned:
        assert key not in env


def test_effective_git_https_override_is_forbidden(
    tmp_path,
):
    subprocess.run(
        ["git", "init", "-q", str(tmp_path)],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "config",
            "--local",
            "http.sslVerify",
            "false",
        ],
        check=True,
    )

    boundary = LiveBoundary(
        tmp_path,
        tmp_path / "qualification.json",
    )

    with pytest.raises(
        machine.ReleaseError,
        match="EFFECTIVE_GIT_HTTPS_OVERRIDE_FORBIDDEN",
    ):
        boundary.verify_git_transport_policy()


def test_shared_release_git_ignores_repository_env(
    tmp_path,
    monkeypatch,
):
    real = tmp_path / "real"
    evil = tmp_path / "evil"

    subprocess.run(
        ["git", "init", "-q", str(real)],
        check=True,
    )
    subprocess.run(
        ["git", "init", "-q", str(evil)],
        check=True,
    )

    monkeypatch.setenv(
        "GIT_DIR",
        str(evil / ".git"),
    )
    monkeypatch.setenv(
        "GIT_WORK_TREE",
        str(evil),
    )

    proc = release_git.run(
        real,
        "rev-parse",
        "--show-toplevel",
        text=True,
    )

    assert proc.returncode == 0
    assert proc.stdout.strip() == str(real)



def test_sealed_environment_drops_git_topology_selection(monkeypatch):
    poisoned = {
        'GIT_COMMON_DIR': '/tmp/evil-common',
        'GIT_CONFIG': '/tmp/evil-config',
        'GIT_CONFIG_PARAMETERS': "'x.y=z'",
        'GIT_GRAFT_FILE': '/tmp/evil-grafts',
        'GIT_IMPLICIT_WORK_TREE': '1',
        'GIT_PREFIX': 'evil/',
        'GIT_SHALLOW_FILE': '/tmp/evil-shallow',
        'GIT_NAMESPACE': 'evil',
    }
    for key, value in poisoned.items():
        monkeypatch.setenv(key, value)
    env = sealed_subprocess_env()
    for key in poisoned:
        assert key not in env
