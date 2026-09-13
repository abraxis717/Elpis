from __future__ import annotations

import json
from pathlib import Path
import re

from tools.ci_secret_scan import scan_private_paths_with_allowlist


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".py", ".c", ".cpp", ".h", ".hpp", ".json", ".toml",
    ".yaml", ".yml", ".md", ".txt", ".cff", ".cmake", ".sh",
}
PATTERNS = (
    re.compile(
        r"(?<![A-Za-z0-9._-])/mnt/[A-Za-z0-9._-]+"
        r"(?:/[^\s\"<>]*)?"
    ),
    re.compile(
        r"(?<![A-Za-z0-9._-])/(?:home|Users)/[A-Za-z0-9._-]+"
        r"(?:/[^\s\"<>]*)?"
    ),
    re.compile(
        r"(?i)(?<![A-Za-z0-9_])[A-Z]:\\Users\\[A-Za-z0-9._-]+"
        r"(?:\\[^\s\"<>]*)?"
    ),
)


def _text_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if ".git" in rel.parts:
            continue
        if path.suffix in TEXT_SUFFIXES or path.name in {
            "VERSION", "LICENSE", "CMakeLists.txt"
        }:
            yield path


def test_public_tree_contains_no_host_specific_absolute_paths() -> None:
    findings = []
    for path in _text_files():
        text = path.read_text(encoding="utf-8", errors="strict")
        for pattern in PATTERNS:
            for match in pattern.finditer(text):
                findings.append(
                    (path.relative_to(ROOT).as_posix(), match.group(0))
                )
    assert findings == []


def test_public_path_allowlist_is_zero() -> None:
    entries = json.loads(
        (ROOT / "tools/public_scan_allowlist.json").read_text(
            encoding="utf-8"
        )
    )
    assert [
        entry for entry in entries
        if entry.get("kind") == "PRIVATE_PATH"
    ] == []


def test_ci_private_path_scanner_requires_no_allowlist_debt() -> None:
    assert scan_private_paths_with_allowlist(ROOT) == []


def test_generic_scanner_still_detects_synthetic_host_paths(
    tmp_path: Path,
) -> None:
    mount = "/" + "mnt/" + "example_volume/project"
    home = "/" + "home/" + "example_user/project"
    (tmp_path / "probe.txt").write_text(
        mount + "\n" + home + "\n",
        encoding="utf-8",
    )
    findings = scan_private_paths_with_allowlist(tmp_path)
    assert findings
