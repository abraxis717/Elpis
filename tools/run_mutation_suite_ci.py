#!/usr/bin/env python3
"""Lifecycle-aware CI entry point for the release-wide mutation suite.

The underlying mutation suite is deliberately restricted to an unpublished
successor VERSION. A publication-closeout commit necessarily still names the
just-published VERSION, so that restriction returns rc=2 with one exact
diagnostic. CI treats only that exact state as N/A; all other mutation-suite
results retain their ordinary meaning.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
VERSION_PATH = ROOT / "VERSION"
MUTATION_SUITE = ROOT / "tools/mutation_suite.py"
PREFIX = "MUTATION_SUITE_REQUIRES_UNPUBLISHED_SUCCESSOR_VERSION:"


def classify_result(
    *,
    version: str,
    returncode: int,
    stdout: str,
    stderr: str,
) -> tuple[bool, str]:
    if returncode == 0:
        return True, "MUTATION_SUITE_EXECUTED_PASS"

    expected = PREFIX + version
    if (
        returncode == 2
        and stdout.strip() == expected
        and stderr.strip() == ""
    ):
        return True, f"MUTATION_SUITE_NA_PUBLISHED_VERSION:{version}"

    return (
        False,
        "MUTATION_SUITE_CI_FAILURE:"
        f"rc={returncode}:"
        f"stdout={stdout.strip()!r}:"
        f"stderr={stderr.strip()!r}",
    )


def main() -> int:
    version = VERSION_PATH.read_text(encoding="utf-8").strip()
    if not version:
        print("MUTATION_SUITE_CI_FAILURE:EMPTY_VERSION", file=sys.stderr)
        return 1

    proc = subprocess.run(
        [sys.executable, str(MUTATION_SUITE)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    ok, diagnostic = classify_result(
        version=version,
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )

    if ok:
        if proc.returncode == 0:
            if proc.stdout:
                sys.stdout.write(proc.stdout)
            if proc.stderr:
                sys.stderr.write(proc.stderr)
        print(diagnostic)
        return 0

    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    print(diagnostic, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
