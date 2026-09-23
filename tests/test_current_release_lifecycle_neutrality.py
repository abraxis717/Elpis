from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_current_release_has_no_preparation_only_pytest_contract():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    token = version.replace(".", "_")
    offenders = sorted(
        p.relative_to(ROOT).as_posix()
        for p in (ROOT / "tests").glob(f"test_{token}_*prep*.py")
    )
    assert offenders == [], (
        "CURRENT_RELEASE_PREP_ONLY_TEST_FORBIDDEN:"
        + ",".join(offenders)
    )
