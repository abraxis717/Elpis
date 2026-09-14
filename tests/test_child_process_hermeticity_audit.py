"""Tests for the child-process hermeticity audit.

The audit must be evidence-driven and conservative: it reports a finding only
when a child Python process provably imports repository-local source and
declares no source roots, and it must not flag legitimate declarations.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from audit_child_process_hermeticity import (  # noqa: E402
    Finding,
    audit,
    repo_local_packages,
)


# ---------------------------------------------------------------------------
# Synthetic fixture repository
# ---------------------------------------------------------------------------

def _make_repo(tmp_path: Path) -> Path:
    """Build a minimal repository the audit can reason about."""
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\n"
        "pythonpath = ['src']\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "mypkg").mkdir(parents=True)
    (tmp_path / "src" / "mypkg" / "__init__.py").write_text(
        "VALUE = 1\n", encoding="utf-8"
    )
    (tmp_path / "tests").mkdir()
    return tmp_path


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# repo_local_packages
# ---------------------------------------------------------------------------

def test_repo_local_packages_derives_declared_roots(tmp_path):
    _make_repo(tmp_path)
    packages = repo_local_packages(tmp_path)
    assert "mypkg" in packages
    assert "tools" not in packages  # no tools/__init__.py in fixture


# ---------------------------------------------------------------------------
# Defective child: imports repo-local source, no root declared
# ---------------------------------------------------------------------------

def test_detects_ambient_reliance(tmp_path):
    _make_repo(tmp_path)
    _write(
        tmp_path / "tests" / "test_bad.py",
        "import os\n"
        "import subprocess\n"
        "import sys\n"
        "\n"
        "def test_bad():\n"
        "    code = 'import mypkg\\nprint(mypkg.VALUE)'\n"
        "    env = os.environ.copy()\n"
        "    env['PYTHONHASHSEED'] = '1'\n"
        "    subprocess.run([sys.executable, '-c', code], env=env, check=True)\n",
    )
    findings = audit(tmp_path)
    assert len(findings) == 1
    assert findings[0].path == "tests/test_bad.py"
    assert findings[0].reason


def test_detects_module_level_child(tmp_path):
    _make_repo(tmp_path)
    _write(
        tmp_path / "tests" / "test_bad2.py",
        "import os\n"
        "import subprocess\n"
        "import sys\n"
        "\n"
        "CODE = 'import mypkg'\n"
        "subprocess.run([sys.executable, '-c', CODE], env=os.environ.copy())\n",
    )
    findings = audit(tmp_path)
    assert len(findings) == 1
    assert findings[0].path == "tests/test_bad2.py"


# ---------------------------------------------------------------------------
# Legitimate declarations: must NOT be flagged
# ---------------------------------------------------------------------------

def test_explicit_pythonpath_not_flagged(tmp_path):
    _make_repo(tmp_path)
    _write(
        tmp_path / "tests" / "test_ok1.py",
        "import os\n"
        "import subprocess\n"
        "import sys\n"
        "\n"
        "def test_ok():\n"
        "    code = 'import mypkg'\n"
        "    env = os.environ.copy()\n"
        "    env['PYTHONPATH'] = str(Path(__file__).parent.parent / 'src')\n"
        "    subprocess.run([sys.executable, '-c', code], env=env, check=True)\n",
    )
    assert audit(tmp_path) == []


def test_literal_dict_env_not_flagged(tmp_path):
    _make_repo(tmp_path)
    _write(
        tmp_path / "tests" / "test_ok2.py",
        "import subprocess\n"
        "import sys\n"
        "\n"
        "def test_ok():\n"
        "    subprocess.run(\n"
        "        [sys.executable, '-c', 'import mypkg'],\n"
        "        env={'PYTHONPATH': '/abs/src'},\n"
        "        check=True,\n"
        "    )\n",
    )
    assert audit(tmp_path) == []


def test_child_sys_path_insert_not_flagged(tmp_path):
    _make_repo(tmp_path)
    _write(
        tmp_path / "tests" / "test_ok3.py",
        "import os\n"
        "import subprocess\n"
        "import sys\n"
        "\n"
        "def test_ok():\n"
        "    code = 'import sys; sys.path.insert(0, \"/abs/src\")\\nimport mypkg'\n"
        "    subprocess.run([sys.executable, '-c', code], env=os.environ.copy())\n",
    )
    assert audit(tmp_path) == []


def test_helper_env_not_flagged(tmp_path):
    _make_repo(tmp_path)
    _write(
        tmp_path / "tests" / "test_ok4.py",
        "import subprocess\n"
        "import sys\n"
        "\n"
        "def _child_env():\n"
        "    return {'PYTHONPATH': '/abs/src'}\n"
        "\n"
        "def test_ok():\n"
        "    subprocess.run([sys.executable, '-c', 'import mypkg'],\n"
        "                    env=_child_env(), check=True)\n",
    )
    assert audit(tmp_path) == []


def test_non_python_child_not_flagged(tmp_path):
    _make_repo(tmp_path)
    _write(
        tmp_path / "tests" / "test_ok5.py",
        "import subprocess\n"
        "\n"
        "def test_ok():\n"
        "    subprocess.run(['git', 'rev-parse', 'HEAD'], check=True)\n",
    )
    assert audit(tmp_path) == []


def test_non_repo_module_not_flagged(tmp_path):
    _make_repo(tmp_path)
    _write(
        tmp_path / "tests" / "test_ok6.py",
        "import os\n"
        "import subprocess\n"
        "import sys\n"
        "\n"
        "def test_ok():\n"
        "    subprocess.run([sys.executable, '-m', 'json.tool'],\n"
        "                    env=os.environ.copy())\n",
    )
    assert audit(tmp_path) == []


def test_no_env_inherits_ambient_and_is_flagged(tmp_path):
    _make_repo(tmp_path)
    _write(
        tmp_path / "tests" / "test_bad3.py",
        "import subprocess\n"
        "import sys\n"
        "\n"
        "def test_bad():\n"
        "    subprocess.run([sys.executable, '-c', 'import mypkg'])\n",
    )
    findings = audit(tmp_path)
    assert len(findings) == 1


def test_direct_environ_copy_call_is_flagged(tmp_path):
    _make_repo(tmp_path)
    _write(
        tmp_path / "tests" / "test_bad4.py",
        "import os\n"
        "import subprocess\n"
        "import sys\n"
        "\n"
        "def test_bad():\n"
        "    subprocess.run([sys.executable, '-c', 'import mypkg'],\n"
        "                    env=os.environ.copy())\n",
    )
    findings = audit(tmp_path)
    assert len(findings) == 1


# ---------------------------------------------------------------------------
# Determinism and real repository
# ---------------------------------------------------------------------------

def test_audit_is_deterministic(tmp_path):
    _make_repo(tmp_path)
    _write(
        tmp_path / "tests" / "test_bad.py",
        "import os\n"
        "import subprocess\n"
        "import sys\n"
        "\n"
        "def test_bad():\n"
        "    env = os.environ.copy()\n"
        "    subprocess.run([sys.executable, '-c', 'import mypkg'], env=env)\n",
    )
    first = audit(tmp_path)
    second = audit(tmp_path)
    assert first == second
    assert [f.line for f in first] == [f.line for f in second]


def test_real_repository_is_clean():
    """After the hermeticity repairs, the real repo has no findings."""
    findings = audit(ROOT)
    assert findings == [], [f"{f.path}:{f.line}" for f in findings]


def test_finding_is_frozen_dataclass():
    finding = Finding(path="a.py", line=1, reason="r")
    with pytest.raises(Exception):
        finding.line = 2  # frozen
