"""Release-critical local Git execution boundary."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


_DROP = frozenset(
    {
        "GIT_NAMESPACE",
        "GIT_SHALLOW_FILE",
        "GIT_PREFIX",
        "GIT_IMPLICIT_WORK_TREE",
        "GIT_GRAFT_FILE",
        "GIT_CONFIG_PARAMETERS",
        "GIT_CONFIG_COUNT",
        "GIT_CONFIG",
        "GIT_COMMON_DIR",
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_REPLACE_REF_BASE",
        "GIT_PROXY_COMMAND",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "no_proxy",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
    }
)


def sealed_git_env() -> dict[str, str]:
    env = dict(os.environ)

    for key in tuple(env):
        if (
            key in _DROP
            or key.startswith("GIT_CONFIG")
            or key.startswith("GIT_SSL_")
            or key.startswith("GIT_HTTP_")
        ):
            env.pop(key, None)

    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    return env


def run(
    root: Path,
    *args: str,
    text: bool = False,
    data=None,
    disable_hooks: bool = False,
):
    argv = ["git", "--no-replace-objects"]

    if disable_hooks:
        argv += [
            "-c",
            "core.hooksPath=/dev/null",
        ]

    argv += list(args)

    return subprocess.run(
        argv,
        cwd=root,
        input=data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
        env=sealed_git_env(),
        check=False,
    )


def authority_command(argv, *, method="run", **kwargs):
    """Subprocess-compatible adapter for qualification authority readers.

    Mixed fixture helpers may also use this adapter; their explicitly supplied
    arguments remain intact while inherited Git selectors cannot choose storage.
    """
    if not argv or argv[0] != "git" or method not in {"run", "check_output", "check_call", "call", "Popen"}:
        raise ValueError("RELEASE_GIT_COMMAND_INVALID")
    kwargs["env"] = sealed_git_env()
    return getattr(subprocess, method)(
        ["git", "--no-replace-objects", *argv[1:]], **kwargs
    )

def run_stream(
    root: Path,
    *args: str,
    disable_hooks: bool = False,
):
    argv = ["git", "--no-replace-objects"]

    if disable_hooks:
        argv += [
            "-c",
            "core.hooksPath=/dev/null",
        ]

    argv += list(args)

    return subprocess.run(
        argv,
        cwd=root,
        env=sealed_git_env(),
        check=False,
    )
