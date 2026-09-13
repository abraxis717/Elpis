from __future__ import annotations

from pathlib import Path
import runpy
import shutil

import pytest


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "tools" / "verify_public_release.py"
SOURCE_REL = Path("src/elpis_reference/structural_guidance")


def _fixture(tmp_path: Path):
    repo = tmp_path / "repo"
    source = repo / SOURCE_REL
    source.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / SOURCE_REL, source)

    ns = runpy.run_path(str(VERIFIER))
    check = ns["check_runtime_boundary"]
    check.__globals__["REPO"] = repo
    return repo, source, check


def _append(path: Path, payload: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n")
        handle.write(payload)
        if not payload.endswith("\n"):
            handle.write("\n")


def test_current_structural_guidance_tree_passes_expanded_policy(
    tmp_path: Path,
) -> None:
    _, _, check = _fixture(tmp_path)
    ok, errors = check()
    assert ok, errors


@pytest.mark.parametrize(
    ("relative", "payload", "needle"),
    [
        (
            "source_emitter.py",
            "import os as _os\n"
            "def _probe():\n"
            "    return _os.system('true')\n",
            "execution_call:os.system",
        ),
        (
            "materializer.py",
            "def _probe():\n"
            "    return getattr(__builtins__, 'ex' + 'ec')('x')\n",
            "dynamic_execution_lookup:__builtins__.exec",
        ),
        (
            "decoder_adapter.py",
            "def _probe():\n"
            "    return __import__('subprocess')\n",
            "execution_call:__import__",
        ),
        (
            "structural_validator.py",
            "import ctypes as _ctypes\n",
            "execution_import:ctypes",
        ),
        (
            "observer.py",
            "from runpy import run_path as _run_path\n",
            "execution_import:runpy",
        ),
        (
            "planner.py",
            "import subprocess as _sp\n",
            "execution_import:subprocess",
        ),
        (
            "planning_input.py",
            "import importlib as _importlib\n",
            "execution_import:importlib",
        ),
        (
            "runtime.py",
            "from os import system as _system\n"
            "def _probe_alias():\n"
            "    return _system('true')\n",
            "execution_call:os.system",
        ),
        (
            "runtime.py",
            "from builtins import eval as _eval\n"
            "def _probe_builtin_alias():\n"
            "    return _eval('1+1')\n",
            "execution_call:builtins.eval",
        ),
    ],
)
def test_alias_and_dynamic_execution_evasions_fail_closed(
    tmp_path: Path,
    relative: str,
    payload: str,
    needle: str,
) -> None:
    _, source, check = _fixture(tmp_path)
    _append(source / relative, payload)

    ok, errors = check()

    assert not ok
    assert any(
        error.startswith(f"RUNTIME_POLICY:{relative}:")
        and needle in error
        for error in errors
    ), errors


def test_recursive_nested_python_module_is_scanned(tmp_path: Path) -> None:
    _, source, check = _fixture(tmp_path)
    nested = source / "_c3_nested_probe" / "probe.py"
    nested.parent.mkdir(parents=True)
    nested.write_text(
        "import runpy as _runpy\n",
        encoding="utf-8",
    )

    ok, errors = check()

    assert not ok
    assert (
        "RUNTIME_POLICY:_c3_nested_probe/probe.py:"
        "execution_import:runpy"
    ) in errors


def test_normal_method_named_eval_is_not_builtin_execution(
    tmp_path: Path,
) -> None:
    _, source, check = _fixture(tmp_path)
    _append(
        source / "consumer.py",
        "def _safe_method_call(model):\n"
        "    return model.eval()\n",
    )

    ok, errors = check()

    assert ok, errors


def test_dynamic_getattr_os_system_alias_is_caught(
    tmp_path: Path,
) -> None:
    _, source, check = _fixture(tmp_path)
    _append(
        source / "source_input.py",
        "import os as _os\n"
        "def _probe_dynamic_os():\n"
        "    return getattr(_os, 'sys' + 'tem')('true')\n",
    )

    ok, errors = check()

    assert not ok
    assert (
        "RUNTIME_POLICY:source_input.py:"
        "dynamic_execution_lookup:os.system"
    ) in errors
