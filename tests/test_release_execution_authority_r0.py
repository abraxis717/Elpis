import os
import subprocess
from pathlib import Path

import pytest

from tools import release_orchestrator as machine
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

    with pytest.raises(machine.ReleaseError, match="LOCAL_GIT_URL_REWRITE_FORBIDDEN"):
        boundary.verify_git_transport_policy()
