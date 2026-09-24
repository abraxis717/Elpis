"""Fail-closed qualification environment authority (not a dependency resolver)."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import platform
import re
import subprocess
import sys


def normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def read_lock(path: Path) -> tuple[str, dict]:
    raw = path.read_bytes()
    entries = {}
    for line in raw.decode().replace("\\\n", " ").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9.+!-]+)((?:\s+--hash=sha256:[a-f0-9]{64})+)", line)
        if not match:
            raise ValueError("QUALIFICATION_LOCK_UNPINNED_OR_UNHASHED:" + line)
        name = normalized(match[1])
        if name in entries:
            raise ValueError("QUALIFICATION_LOCK_DUPLICATE:" + name)
        entries[name] = {"version": match[2], "hashes": re.findall(r"sha256:([a-f0-9]{64})", match[3])}
    if not entries:
        raise ValueError("QUALIFICATION_LOCK_EMPTY")
    return hashlib.sha256(raw).hexdigest(), entries


def supported_python(version=None) -> None:
    version = sys.version_info if version is None else version
    if tuple(version[:2]) not in {(3, 11), (3, 12)}:
        raise ValueError("QUALIFICATION_PYTHON_UNSUPPORTED")



def distribution_content_identity(dist) -> dict:
    name = normalized(dist.metadata["Name"])
    files = dist.files

    if not files:
        raise ValueError(
            "QUALIFICATION_DISTRIBUTION_FILES_MISSING:" + name
        )

    prefix = Path(sys.prefix).resolve()
    rows = []
    seen = set()

    for item in sorted(files, key=lambda value: value.as_posix()):
        rel = item.as_posix()

        # Wheel/RECORD metadata in real distributions can contain the
        # same installed relative path more than once. Content authority
        # is over distinct installed paths, not duplicate metadata rows.
        if rel in seen:
            continue
        seen.add(rel)

        candidate = Path(dist.locate_file(item))

        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError as exc:
            raise ValueError(
                "QUALIFICATION_DISTRIBUTION_FILE_MISSING:"
                + name
                + ":"
                + rel
            ) from exc

        if not resolved.is_relative_to(prefix):
            raise ValueError(
                "QUALIFICATION_DISTRIBUTION_FILE_OUTSIDE_ENV:"
                + name
                + ":"
                + rel
            )

        if not resolved.is_file():
            raise ValueError(
                "QUALIFICATION_DISTRIBUTION_FILE_NOT_REGULAR:"
                + name
                + ":"
                + rel
            )

        raw = resolved.read_bytes()
        rows.append(
            {
                "path": rel,
                "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )

    canonical = json.dumps(
        rows,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")

    return {
        "file_count": len(rows),
        "sha256": hashlib.sha256(canonical).hexdigest(),
    }

def authority(root: Path) -> dict:
    supported_python()
    config = Path(sys.prefix) / "pyvenv.cfg"
    if sys.prefix == sys.base_prefix or not config.is_file() or "include-system-site-packages = false" not in config.read_text().lower():
        raise ValueError("QUALIFICATION_ISOLATED_VENV_REQUIRED")
    key = f"release-{sys.platform}-{platform.machine().lower()}-py{sys.version_info.major}{sys.version_info.minor}"
    lock = root / "qualification/locks" / (key + ".lock")
    if not lock.is_file():
        raise ValueError("QUALIFICATION_PLATFORM_LOCK_MISSING:" + key)
    digest, expected = read_lock(lock)
    required = {"pip", "pytest", "numpy", "scipy", "torch", "setuptools", "wheel", "build", "twine"}
    if not required <= expected.keys():
        raise ValueError("QUALIFICATION_RELEASE_PROFILE_INCOMPLETE")
    installed = {}
    installed_content = {}
    for dist in metadata.distributions():
        name = normalized(dist.metadata["Name"])
        if name in installed:
            raise ValueError("QUALIFICATION_DUPLICATE_DISTRIBUTION:" + name)
        installed[name] = dist.version
        installed_content[name] = distribution_content_identity(dist)

    if installed != {
        name: entry["version"]
        for name, entry in expected.items()
    }:
        raise ValueError("QUALIFICATION_INSTALLED_GRAPH_MISMATCH")

    if set(installed_content) != set(installed):
        raise ValueError("QUALIFICATION_INSTALLED_CONTENT_INCOMPLETE")
    report_path = Path(sys.prefix) / "qualification-install.json"
    report = json.loads(report_path.read_bytes())
    observed = {}
    for item in report["install"]:
        name = normalized(item["metadata"]["name"])
        sha = item["download_info"]["archive_info"]["hashes"]["sha256"]
        if name not in expected or sha not in expected[name]["hashes"] or item["metadata"]["version"] != expected[name]["version"]:
            raise ValueError("QUALIFICATION_INSTALL_HASH_MISMATCH:" + name)
        observed[name] = sha
    if set(observed) != set(expected):
        raise ValueError("QUALIFICATION_INSTALL_REPORT_INCOMPLETE")
    subprocess.run([sys.executable, "-m", "pip", "check"], check=True, capture_output=True)
    return {
        "schema": "elpis.qualification-environment.v2",
        "profile": key,
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "executable_sha256":
            hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
        "lock_sha256": digest,
        "installed": installed,
        "installed_content": installed_content,
        "artifacts": observed,
        "install_report_sha256":
            hashlib.sha256(report_path.read_bytes()).hexdigest(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(authority(args.root), sort_keys=True, indent=2))
