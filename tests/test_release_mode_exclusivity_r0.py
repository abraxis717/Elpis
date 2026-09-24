import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "tools" / "verify_public_release.py"


def run(*args):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(VERIFIER), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )


def assert_mode_conflict(*args):
    proc = run(*args)
    assert proc.returncode != 0
    combined = proc.stdout + proc.stderr
    assert (
        "cannot be combined" in combined
        or "mutually exclusive" in combined
    )


def test_development_cannot_select_candidate_identity_only_mode():
    assert_mode_conflict(
        "--development",
        "--verify-candidate-repository-identity",
    )


def test_candidate_cannot_select_candidate_identity_only_mode():
    assert_mode_conflict(
        "--candidate",
        "--verify-candidate-repository-identity",
    )


def test_development_cannot_select_release_identity_only_mode():
    assert_mode_conflict(
        "--development",
        "--verify-repository-identity",
    )


def test_candidate_cannot_select_release_identity_only_mode():
    assert_mode_conflict(
        "--candidate",
        "--verify-repository-identity",
    )


def test_output_only_modes_are_exclusive():
    assert_mode_conflict(
        "--print-manifest",
        "--emit-allowlist",
    )


def test_identity_only_modes_are_exclusive():
    assert_mode_conflict(
        "--verify-candidate-repository-identity",
        "--verify-repository-identity",
    )
