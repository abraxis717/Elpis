from __future__ import annotations

from pathlib import Path
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "tools/run_mutation_suite_ci.py"
MUTATION_SUITE = ROOT / "tools/mutation_suite.py"


def _classify():
    return runpy.run_path(str(WRAPPER))["classify_result"]


def test_classifier_accepts_normal_mutation_suite_pass():
    classify = _classify()
    ok, marker = classify(
        version="2.2.24",
        returncode=0,
        stdout="MUTATION SUITE PASSED\n",
        stderr="",
    )
    assert ok is True
    assert marker == "MUTATION_SUITE_EXECUTED_PASS"


def test_classifier_accepts_only_exact_published_version_na():
    classify = _classify()
    exact = (
        "MUTATION_SUITE_REQUIRES_UNPUBLISHED_SUCCESSOR_VERSION:"
        "2.2.23\n"
    )
    ok, marker = classify(
        version="2.2.23",
        returncode=2,
        stdout=exact,
        stderr="",
    )
    assert ok is True
    assert marker == "MUTATION_SUITE_NA_PUBLISHED_VERSION:2.2.23"


def test_classifier_rejects_wrong_version_na():
    classify = _classify()
    ok, _ = classify(
        version="2.2.24",
        returncode=2,
        stdout=(
            "MUTATION_SUITE_REQUIRES_UNPUBLISHED_SUCCESSOR_VERSION:"
            "2.2.23\n"
        ),
        stderr="",
    )
    assert ok is False


def test_classifier_rejects_extra_output_on_na():
    classify = _classify()
    ok, _ = classify(
        version="2.2.23",
        returncode=2,
        stdout=(
            "MUTATION_SUITE_REQUIRES_UNPUBLISHED_SUCCESSOR_VERSION:"
            "2.2.23\nextra\n"
        ),
        stderr="",
    )
    assert ok is False


def test_classifier_rejects_stderr_on_na():
    classify = _classify()
    ok, _ = classify(
        version="2.2.23",
        returncode=2,
        stdout=(
            "MUTATION_SUITE_REQUIRES_UNPUBLISHED_SUCCESSOR_VERSION:"
            "2.2.23\n"
        ),
        stderr="warning\n",
    )
    assert ok is False


def test_classifier_rejects_arbitrary_failure():
    classify = _classify()
    ok, _ = classify(
        version="2.2.24",
        returncode=1,
        stdout="MUTATION SUITE FAILED\n",
        stderr="",
    )
    assert ok is False


def test_current_published_tree_wrapper_accepts_exact_lifecycle_na():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert version == "2.2.23"

    raw = subprocess.run(
        [sys.executable, str(MUTATION_SUITE)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert raw.returncode == 2
    assert raw.stdout.strip() == (
        "MUTATION_SUITE_REQUIRES_UNPUBLISHED_SUCCESSOR_VERSION:"
        + version
    )
    assert raw.stderr == ""

    wrapped = subprocess.run(
        [sys.executable, str(WRAPPER)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert wrapped.returncode == 0, wrapped.stdout + wrapped.stderr
    assert (
        f"MUTATION_SUITE_NA_PUBLISHED_VERSION:{version}"
        in wrapped.stdout
    )


def test_unpublished_successor_gate_would_open():
    ns = runpy.run_path(str(MUTATION_SUITE))
    gate = ns["_mutation_suite_version_gate"]

    class FakePath:
        pass

    # Use a real temporary fixture so the production gate reads normal files.
    import json
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "VERSION").write_text("2.2.24\n", encoding="utf-8")
        (root / "PUBLISHED_RELEASES.json").write_text(
            json.dumps({"published_releases": [{"version": "2.2.22"}]}) + "\n",
            encoding="utf-8",
        )
        (root / "PUBLICATION_ASSERTIONS.json").write_text(
            json.dumps({"publication_assertions": [{"version": "2.2.23"}]}) + "\n",
            encoding="utf-8",
        )
        assert gate(root) is None
