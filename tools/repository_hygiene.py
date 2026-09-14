"""Repository hygiene scanner.

Detects repository-poisoning hazards: generated operational debris that does
not belong in source authority. This is a conservative, evidence-driven,
deterministic guard against the class of contamination that accumulates in a
long-lived repository -- committed caches, bytecode, virtual environments,
local build outputs, temporary test trees, databases, downloaded archives,
model/checkpoint material, editor/runtime state, and qualification scratch.

Design notes
------------
* **Conservative.** A path is reported only when it matches a well-understood
  debris pattern. Ambiguous paths are not reported. False positives are a
  defect; the scanner would rather miss an unusual hazard than flag legitimate
  source authority.
* **Allowlist.** Legitimate files that happen to match a debris pattern (e.g.
  vendored data, scientific evidence, a checked-in reference weight) are
  excluded via ``tools/hygiene_allowlist.json``. The allowlist is the explicit
  authority for "this looks like debris but is not."
* **Deterministic.** Traversal and findings are sorted; no network access, no
  wall-clock dependence.
* **No deletion.** The scanner only reports. It never deletes or rewrites
  anything. Deletion authority stays with the operator.

Categories
----------
bytecode, python_cache, virtualenv, build_output, database, archive,
model_weight, editor_state, os_state, log, secret, coverage, scratch.

Run as a CLI::

    python tools/repository_hygiene.py [ROOT] [--json] [--tracked-only]

or as a module::

    from tools.repository_hygiene import scan
    findings = scan(Path("..."))
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Finding:
    """A repository hygiene hazard."""

    path: str
    category: str
    tracked: bool
    reason: str


# ---------------------------------------------------------------------------
# Debris patterns
# ---------------------------------------------------------------------------
# Each entry: (category, matcher). matchers are applied to the *name* of a
# file or directory. Directory matchers that should stop descent are marked.

_NAME_PATTERNS: list[tuple[str, str, bool]] = [
    # (category, regex, stop_descent)
    ("bytecode", r"\.py[cod]$", False),
    ("bytecode", r"\.pyd$", False),
    ("bytecode", r"^__pycache__$", True),
    ("python_cache", r"^\.pytest_cache$", True),
    ("python_cache", r"^\.mypy_cache$", True),
    ("python_cache", r"^\.ruff_cache$", True),
    ("python_cache", r"^\.hypothesis$", True),
    ("python_cache", r"^\.ipynb_checkpoints$", True),
    ("python_cache", r"^\.tox$", True),
    ("virtualenv", r"^\.venv$", True),
    ("virtualenv", r"^venv$", True),
    ("virtualenv", r"\.egg-info$", True),
    ("virtualenv", r"\.egg$", False),
    ("build_output", r"^build$", True),
    ("build_output", r"^dist$", True),
    ("build_output", r"^node_modules$", True),
    ("build_output", r"^CMakeFiles$", True),
    ("build_output", r"^CMakeCache\.txt$", False),
    ("build_output", r"^cmake_install\.cmake$", False),
    ("build_output", r"\.o$", False),
    ("build_output", r"\.so$", False),
    ("build_output", r"\.a$", False),
    ("build_output", r"^Makefile$", False),
    ("database", r"\.db$", False),
    ("database", r"\.sqlite$", False),
    ("database", r"\.sqlite3$", False),
    ("archive", r"\.tar$", False),
    ("archive", r"\.tar\.gz$", False),
    ("archive", r"\.tgz$", False),
    ("archive", r"\.tar\.xz$", False),
    ("archive", r"\.zip$", False),
    ("archive", r"\.7z$", False),
    ("archive", r"\.bz2$", False),
    ("model_weight", r"\.gguf$", False),
    ("model_weight", r"\.safetensors$", False),
    ("model_weight", r"\.pt$", False),
    ("model_weight", r"\.pth$", False),
    ("model_weight", r"\.bin$", False),
    ("model_weight", r"\.onnx$", False),
    ("model_weight", r"\.ckpt$", False),
    ("model_weight", r"\.pkl$", False),
    ("model_weight", r"\.pickle$", False),
    ("model_weight", r"\.npy$", False),
    ("model_weight", r"\.npz$", False),
    ("model_weight", r"\.h5$", False),
    ("model_weight", r"\.hdf5$", False),
    ("editor_state", r"\.sw[px]$", False),
    ("editor_state", r"\.swn$", False),
    ("editor_state", r"\.bak$", False),
    ("editor_state", r"\.orig$", False),
    ("editor_state", r"\.rej$", False),
    ("editor_state", r"\.tmp$", False),
    ("editor_state", r"\.temp$", False),
    ("editor_state", r"^\.idea$", True),
    ("editor_state", r"^\.vscode$", True),
    ("os_state", r"^\.DS_Store$", False),
    ("os_state", r"^Thumbs\.db$", False),
    ("log", r"\.log$", False),
    ("secret", r"^\.env$", False),
    ("secret", r"\.key$", False),
    ("secret", r"\.pem$", False),
    ("secret", r"\.crt$", False),
    ("coverage", r"^coverage$", True),
    ("coverage", r"^htmlcov$", True),
    ("coverage", r"\.cover$", False),
    ("coverage", r"^\.coverage$", False),
    ("scratch", r"^\.nfs\.\d+$", False),
]

_COMPILED = [
    (category, re.compile(pattern), stop)
    for category, pattern, stop in _NAME_PATTERNS
]


def _classify(name: str) -> Optional[tuple[str, bool]]:
    """Return (category, stop_descent) for *name*, or None if clean."""
    for category, regex, stop in _COMPILED:
        if regex.search(name):
            return category, stop
    return None


# ---------------------------------------------------------------------------
# Allowlist
# ---------------------------------------------------------------------------

def _load_allowlist(root: Path) -> set[str]:
    """Load the hygiene allowlist as a set of repository-relative paths."""
    allowlist = root / "tools" / "hygiene_allowlist.json"
    if not allowlist.is_file():
        return set()
    try:
        data = json.loads(allowlist.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    entries = data.get("allow", []) if isinstance(data, dict) else []
    return {str(entry) for entry in entries}


# ---------------------------------------------------------------------------
# Tracked-file discovery
# ---------------------------------------------------------------------------

def _tracked_files(root: Path) -> set[str]:
    """Return repository-relative paths of tracked files, or empty set."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return set()
    if result.returncode != 0:
        return set()
    return {
        entry
        for entry in result.stdout.split("\0")
        if entry
    }


# ---------------------------------------------------------------------------
# The scan
# ---------------------------------------------------------------------------

def scan(root: Path, tracked_only: bool = False) -> list[Finding]:
    """Scan *root* for repository hygiene hazards.

    Walks the working tree (skipping ``.git``), classifies each path, and
    reports findings not covered by the allowlist. ``tracked_only`` restricts
    findings to files that are tracked by Git.
    """
    root = root.resolve()
    allowlist = _load_allowlist(root)
    tracked = _tracked_files(root) if tracked_only else None

    findings: list[Finding] = []
    seen: set[str] = set()

    def _record(path: Path, category: str, reason: str) -> None:
        rel = path.relative_to(root).as_posix()
        if rel in seen:
            return
        seen.add(rel)
        if rel in allowlist:
            return
        if tracked is not None and rel not in tracked:
            return
        findings.append(
            Finding(
                path=rel,
                category=category,
                tracked=tracked is not None and rel in tracked,
                reason=reason,
            )
        )

    def _walk(directory: Path) -> None:
        try:
            entries = sorted(directory.iterdir())
        except OSError:
            return
        for entry in entries:
            name = entry.name
            if name == ".git":
                continue
            classification = _classify(name)
            if classification is not None:
                category, stop = classification
                _record(
                    entry,
                    category,
                    f"{category} debris: {name}",
                )
                if stop:
                    continue  # do not descend into a debris directory
            if entry.is_dir():
                _walk(entry)

    _walk(root)
    findings.sort(key=lambda f: (f.path, f.category))
    return findings


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="repository root to scan (default: current directory)",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit findings as JSON"
    )
    parser.add_argument(
        "--tracked-only",
        action="store_true",
        help="report only findings for files tracked by Git",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2

    findings = scan(root, tracked_only=args.tracked_only)
    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=2, sort_keys=True))
    else:
        if not findings:
            print("repository hygiene: OK (no debris detected)")
        for finding in findings:
            marker = "tracked" if finding.tracked else "untracked"
            print(f"{finding.path}: [{finding.category}] {marker}: {finding.reason}")
        if findings:
            print(f"repository hygiene: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
