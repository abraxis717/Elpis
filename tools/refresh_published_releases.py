#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parent.parent
TAG_RE = re.compile(r"^Elpis(\d+)\.(\d+)\.(\d+)$")
SCHEMA = "elpis.published-releases.v1"
SOURCE_OF_TRUTH = "refs/tags/Elpis<semver>"
ENTRY_KEYS = {
    "manifest_path",
    "manifest_sha256",
    "peeled_commit",
    "release_tag",
    "version",
}


def _paths(root: Path) -> tuple[Path, Path]:
    return root / "PUBLISHED_RELEASES.json", root / "FAILED_RELEASES.json"


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode:
        raise ValueError(
            "GIT_AUTHORITY_UNAVAILABLE:"
            + " ".join(args)
            + ":"
            + proc.stderr.strip()
        )
    return proc.stdout.strip()


def semver_key(tag: str) -> tuple[int, int, int]:
    match = TAG_RE.fullmatch(tag)
    if match is None:
        raise ValueError(f"INVALID_RELEASE_TAG:{tag}")
    return tuple(int(x) for x in match.groups())


def failed_tags(root: Path) -> set[str]:
    _, failed_path = _paths(root)
    payload = json.loads(failed_path.read_text(encoding="utf-8"))
    if payload.get("schema") != "elpis.failed-releases.v1":
        raise ValueError("INVALID_FAILED_RELEASES_SCHEMA")
    records = payload.get("failed_releases")
    if not isinstance(records, list):
        raise ValueError("INVALID_FAILED_RELEASES_RECORDS")
    tags: set[str] = set()
    versions: set[str] = set()
    for index, item in enumerate(records):
        if not isinstance(item, dict):
            raise ValueError(f"INVALID_FAILED_RELEASE_RECORD:{index}")
        tag = item.get("release_tag")
        version = item.get("version")
        if not isinstance(tag, str) or TAG_RE.fullmatch(tag) is None:
            raise ValueError(f"INVALID_FAILED_RELEASE_TAG:{index}")
        if version != tag.removeprefix("Elpis"):
            raise ValueError(f"FAILED_RELEASE_VERSION_TAG_MISMATCH:{tag}")
        if tag in tags or version in versions:
            raise ValueError(f"DUPLICATE_FAILED_RELEASE:{tag}")
        tags.add(tag)
        versions.add(version)
    return tags


def load_registry(root: Path) -> dict:
    registry, _ = _paths(root)
    payload = json.loads(registry.read_text(encoding="utf-8"))
    if payload.get("schema") != SCHEMA:
        raise ValueError("INVALID_PUBLISHED_RELEASES_SCHEMA")
    if payload.get("source_of_truth") != SOURCE_OF_TRUTH:
        raise ValueError("INVALID_PUBLISHED_RELEASES_SOURCE_OF_TRUTH")
    if set(payload) != {"published_releases", "schema", "source_of_truth"}:
        raise ValueError("INVALID_PUBLISHED_RELEASES_TOP_LEVEL_FIELDS")
    if not isinstance(payload.get("published_releases"), list):
        raise ValueError("INVALID_PUBLISHED_RELEASES_RECORDS")
    return payload


def expected_entry(root: Path, tag: str) -> dict:
    version = tag.removeprefix("Elpis")
    semver_key(tag)
    manifest_rel = Path("manifests") / f"{tag}.RELEASE_MANIFEST.json"
    manifest = root / manifest_rel
    if not manifest.is_file():
        raise ValueError(f"PUBLISHED_MANIFEST_MISSING:{tag}")
    peeled = git(root, "rev-parse", "--verify", f"refs/tags/{tag}^{{}}")
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", peeled):
        raise ValueError(f"PUBLISHED_TAG_PEELED_COMMIT_INVALID:{tag}")
    return {
        "manifest_path": manifest_rel.as_posix(),
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "peeled_commit": peeled,
        "release_tag": tag,
        "version": version,
    }


def validation_errors(root: Path, payload: dict | None = None) -> list[str]:
    try:
        data = load_registry(root) if payload is None else payload
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [str(exc)]

    errors: list[str] = []
    if data.get("schema") != SCHEMA:
        errors.append("INVALID_PUBLISHED_RELEASES_SCHEMA")
    if data.get("source_of_truth") != SOURCE_OF_TRUTH:
        errors.append("INVALID_PUBLISHED_RELEASES_SOURCE_OF_TRUTH")
    if set(data) != {"published_releases", "schema", "source_of_truth"}:
        errors.append("INVALID_PUBLISHED_RELEASES_TOP_LEVEL_FIELDS")

    records = data.get("published_releases")
    if not isinstance(records, list):
        return errors + ["INVALID_PUBLISHED_RELEASES_RECORDS"]

    try:
        failed = failed_tags(root)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return errors + [str(exc)]

    seen_tags: set[str] = set()
    seen_versions: set[str] = set()
    previous_key: tuple[int, int, int] | None = None
    for index, item in enumerate(records):
        if not isinstance(item, dict):
            errors.append(f"PUBLISHED_RECORD_INVALID:{index}")
            continue
        if set(item) != ENTRY_KEYS:
            errors.append(f"PUBLISHED_RECORD_FIELDS_INVALID:{index}")
            continue
        tag = item.get("release_tag")
        version = item.get("version")
        if not isinstance(tag, str) or TAG_RE.fullmatch(tag) is None:
            errors.append(f"PUBLISHED_RELEASE_TAG_INVALID:{index}")
            continue
        if version != tag.removeprefix("Elpis"):
            errors.append(f"PUBLISHED_VERSION_TAG_MISMATCH:{tag}")
        if tag in seen_tags or version in seen_versions:
            errors.append(f"PUBLISHED_RELEASE_DUPLICATE:{tag}")
        seen_tags.add(tag)
        seen_versions.add(version)
        key = semver_key(tag)
        if previous_key is not None and key <= previous_key:
            errors.append(f"PUBLISHED_RELEASE_ORDER_INVALID:{tag}")
        previous_key = key
        if tag in failed:
            errors.append(f"PUBLISHED_RELEASE_IS_FAILED:{tag}")

        expected_path = f"manifests/{tag}.RELEASE_MANIFEST.json"
        if item.get("manifest_path") != expected_path:
            errors.append(f"PUBLISHED_MANIFEST_PATH_MISMATCH:{tag}")
            continue
        manifest = root / expected_path
        if not manifest.is_file():
            errors.append(f"PUBLISHED_MANIFEST_MISSING:{tag}")
            continue
        actual_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
        if item.get("manifest_sha256") != actual_sha:
            errors.append(f"PUBLISHED_MANIFEST_SHA256_MISMATCH:{tag}")
        try:
            peeled = git(root, "rev-parse", "--verify", f"refs/tags/{tag}^{{}}")
        except ValueError:
            errors.append(f"PUBLISHED_RELEASE_TAG_MISSING:{tag}")
            continue
        if item.get("peeled_commit") != peeled:
            errors.append(f"PUBLISHED_PEELED_COMMIT_MISMATCH:{tag}")

    return errors


def encoded(payload: dict) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def append_tag(root: Path, tag: str) -> dict:
    raise ValueError(
        "LEGACY_PUBLISHED_REGISTRY_FROZEN_"
        "USE_PUBLICATION_ASSERTIONS_V2"
    )

    # Historical implementation intentionally retained below as dead source
    # for review continuity. The callable authority terminates above.
    semver_key(tag)
    current = load_registry(root)
    current_errors = validation_errors(root, current)
    if current_errors:
        raise ValueError("PUBLISHED_REGISTRY_PREAPPEND_NONPASS:" + "|".join(current_errors))
    if tag in failed_tags(root):
        raise ValueError(f"PUBLISHED_APPEND_FAILED_RELEASE:{tag}")

    records = current["published_releases"]
    if any(item["release_tag"] == tag for item in records):
        raise ValueError(f"PUBLISHED_APPEND_DUPLICATE_TAG:{tag}")
    version = tag.removeprefix("Elpis")
    if any(item["version"] == version for item in records):
        raise ValueError(f"PUBLISHED_APPEND_DUPLICATE_VERSION:{version}")
    if records and semver_key(tag) <= semver_key(records[-1]["release_tag"]):
        raise ValueError(f"PUBLISHED_APPEND_NOT_MONOTONIC:{tag}")

    candidate = {
        "published_releases": [*records, expected_entry(root, tag)],
        "schema": SCHEMA,
        "source_of_truth": SOURCE_OF_TRUTH,
    }
    errors = validation_errors(root, candidate)
    if errors:
        raise ValueError("PUBLISHED_REGISTRY_CANDIDATE_NONPASS:" + "|".join(errors))

    registry, _ = _paths(root)
    registry.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=registry.parent, delete=False
    ) as handle:
        temp = Path(handle.name)
        handle.write(encoded(candidate))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, registry)
    return candidate["published_releases"][-1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--append-tag")
    args = ap.parse_args()
    root = args.root.resolve()

    if args.check:
        errors = validation_errors(root)
        if errors:
            for error in errors:
                print(error)
            return 1
        count = len(load_registry(root)["published_releases"])
        print(f"PASS published-release registry validates {count} explicit publication assertions")
        return 0

    try:
        entry = append_tag(root, args.append_tag)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(str(exc))
        return 1
    print("APPENDED published-release assertion " + json.dumps(entry, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
