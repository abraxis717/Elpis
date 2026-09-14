"""Tests for the repository hygiene scanner.

The scanner must be conservative and evidence-driven: it reports well-
understood debris patterns, honours the allowlist, is deterministic, and does
not flag legitimate source authority.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from repository_hygiene import (  # noqa: E402
    Finding,
    _classify,
    scan,
)


# ---------------------------------------------------------------------------
# _classify unit checks
# ---------------------------------------------------------------------------

def test_classify_bytecode():
    assert _classify("module.pyc")[0] == "bytecode"
    assert _classify("module.pyo")[0] == "bytecode"
    assert _classify("__pycache__")[0] == "bytecode"
    assert _classify("__pycache__")[1] is True  # stop descent


def test_classify_caches():
    assert _classify(".pytest_cache")[0] == "python_cache"
    assert _classify(".mypy_cache")[0] == "python_cache"
    assert _classify(".ruff_cache")[0] == "python_cache"
    assert _classify(".hypothesis")[0] == "python_cache"


def test_classify_virtualenv():
    assert _classify(".venv")[0] == "virtualenv"
    assert _classify("venv")[0] == "virtualenv"
    assert _classify("pkg.egg-info")[0] == "virtualenv"


def test_classify_build_output():
    assert _classify("build")[0] == "build_output"
    assert _classify("dist")[0] == "build_output"
    assert _classify("foo.o")[0] == "build_output"
    assert _classify("foo.so")[0] == "build_output"


def test_classify_database_archive_weight():
    assert _classify("state.db")[0] == "database"
    assert _classify("state.sqlite3")[0] == "database"
    assert _classify("bundle.tar.gz")[0] == "archive"
    assert _classify("model.gguf")[0] == "model_weight"
    assert _classify("model.safetensors")[0] == "model_weight"
    assert _classify("weights.bin")[0] == "model_weight"


def test_classify_editor_os_log_secret():
    assert _classify("file.swp")[0] == "editor_state"
    assert _classify(".DS_Store")[0] == "os_state"
    assert _classify("run.log")[0] == "log"
    assert _classify(".env")[0] == "secret"
    assert _classify("key.pem")[0] == "secret"


def test_classify_clean_names():
    assert _classify("module.py") is None
    assert _classify("README.md") is None
    assert _classify("test_foo.py") is None
    assert _classify("manifest.json") is None
    assert _classify("src") is None
    assert _classify("components") is None


# ---------------------------------------------------------------------------
# scan on synthetic repositories
# ---------------------------------------------------------------------------

def _make_repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "pkg").mkdir()
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src" / "pkg" / "module.py").write_text("X = 1\n", encoding="utf-8")
    return tmp_path


def test_clean_repo_has_no_findings(tmp_path):
    _make_repo(tmp_path)
    assert scan(tmp_path) == []


def test_detects_bytecode(tmp_path):
    _make_repo(tmp_path)
    (tmp_path / "src" / "pkg" / "module.pyc").write_bytes(b"")
    findings = scan(tmp_path)
    assert [f.path for f in findings] == ["src/pkg/module.pyc"]
    assert findings[0].category == "bytecode"


def test_detects_pycache_dir_and_does_not_descend(tmp_path):
    _make_repo(tmp_path)
    cache = tmp_path / "src" / "pkg" / "__pycache__"
    cache.mkdir()
    (cache / "module.cpython-311.pyc").write_bytes(b"")
    findings = scan(tmp_path)
    # The __pycache__ directory itself is reported; its contents are not
    # descended into (no duplicate finding for the inner .pyc).
    assert [f.path for f in findings] == ["src/pkg/__pycache__"]


def test_detects_virtualenv(tmp_path):
    _make_repo(tmp_path)
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / ".venv" / "bin" / "python").write_text("", encoding="utf-8")
    findings = scan(tmp_path)
    assert [f.path for f in findings] == [".venv"]


def test_detects_database_and_archive(tmp_path):
    _make_repo(tmp_path)
    (tmp_path / "state.db").write_bytes(b"")
    (tmp_path / "bundle.tar.gz").write_bytes(b"")
    findings = scan(tmp_path)
    assert {f.path for f in findings} == {"state.db", "bundle.tar.gz"}
    assert {f.category for f in findings} == {"database", "archive"}


def test_detects_model_weight(tmp_path):
    _make_repo(tmp_path)
    (tmp_path / "model.gguf").write_bytes(b"")
    findings = scan(tmp_path)
    assert [f.path for f in findings] == ["model.gguf"]
    assert findings[0].category == "model_weight"


def test_detects_editor_and_os_state(tmp_path):
    _make_repo(tmp_path)
    (tmp_path / "file.swp").write_bytes(b"")
    (tmp_path / ".DS_Store").write_bytes(b"")
    findings = scan(tmp_path)
    assert {f.path for f in findings} == {"file.swp", ".DS_Store"}


def test_detects_log_and_secret(tmp_path):
    _make_repo(tmp_path)
    (tmp_path / "run.log").write_text("", encoding="utf-8")
    (tmp_path / ".env").write_text("", encoding="utf-8")
    findings = scan(tmp_path)
    assert {f.path for f in findings} == {"run.log", ".env"}


def test_detects_build_output(tmp_path):
    _make_repo(tmp_path)
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "out.o").write_bytes(b"")
    findings = scan(tmp_path)
    assert [f.path for f in findings] == ["build"]


# ---------------------------------------------------------------------------
# Allowlist
# ---------------------------------------------------------------------------

def test_allowlist_suppresses_finding(tmp_path):
    _make_repo(tmp_path)
    (tmp_path / "model.gguf").write_bytes(b"")
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "hygiene_allowlist.json").write_text(
        json.dumps({"allow": ["model.gguf"]}), encoding="utf-8"
    )
    assert scan(tmp_path) == []


def test_allowlist_does_not_suppress_other_paths(tmp_path):
    _make_repo(tmp_path)
    (tmp_path / "model.gguf").write_bytes(b"")
    (tmp_path / "state.db").write_bytes(b"")
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "hygiene_allowlist.json").write_text(
        json.dumps({"allow": ["model.gguf"]}), encoding="utf-8"
    )
    findings = scan(tmp_path)
    assert [f.path for f in findings] == ["state.db"]


def test_missing_allowlist_is_fine(tmp_path):
    _make_repo(tmp_path)
    (tmp_path / "state.db").write_bytes(b"")
    findings = scan(tmp_path)
    assert [f.path for f in findings] == ["state.db"]


def test_malformed_allowlist_is_ignored(tmp_path):
    _make_repo(tmp_path)
    (tmp_path / "state.db").write_bytes(b"")
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "hygiene_allowlist.json").write_text(
        "{not json", encoding="utf-8"
    )
    findings = scan(tmp_path)
    assert [f.path for f in findings] == ["state.db"]


# ---------------------------------------------------------------------------
# Determinism and real repository
# ---------------------------------------------------------------------------

def test_scan_is_deterministic(tmp_path):
    _make_repo(tmp_path)
    (tmp_path / "state.db").write_bytes(b"")
    (tmp_path / "model.gguf").write_bytes(b"")
    (tmp_path / "run.log").write_text("", encoding="utf-8")
    first = scan(tmp_path)
    second = scan(tmp_path)
    assert first == second
    assert [f.path for f in first] == sorted(f.path for f in first)


def test_real_repository_is_clean():
    """The real repository has no tracked or untracked debris."""
    findings = scan(ROOT)
    assert findings == [], [f"{f.path} [{f.category}]" for f in findings]


def test_finding_is_frozen_dataclass():
    finding = Finding(path="a.db", category="database", tracked=False, reason="r")
    with pytest.raises(Exception):
        finding.category = "other"
