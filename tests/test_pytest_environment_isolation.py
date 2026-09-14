from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_pytest_harness_does_not_export_repository_pythonpath():
    assert "PYTHONPATH" not in os.environ


def test_conftest_contains_no_pythonpath_environment_mutation():
    source = (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert "PYTHONPATH" not in source
    assert "os.environ" not in source
