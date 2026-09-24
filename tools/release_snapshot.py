"""Physical release snapshots. Git index flags are never file authority."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess

try:
    from tools import release_tree_digest as tree
except ImportError:
    import release_tree_digest as tree


def extract_git_archive(archive, destination: Path) -> None:
    """Extract only files, directories and contained symlinks on Python 3.11.0+.

    Validate the whole archive before writing; links are created last. Never
    delegate path interpretation, hardlinks or special files to tarfile.
    """
    entries = {}
    for member in archive.getmembers():
        name = tree.normalized_path(member.name.rstrip("/"))
        if name in entries or PurePosixPath(name).parts[0] == ".git":
            raise ValueError("ARCHIVE_PATH_INVALID:" + name)
        if not (member.isfile() or member.isdir() or member.issym()):
            raise ValueError("ARCHIVE_TYPE_INVALID:" + name)
        entries[name] = member
    for name, member in entries.items():
        for parent in PurePosixPath(name).parents:
            if str(parent) in entries and not entries[str(parent)].isdir():
                raise ValueError("ARCHIVE_PARENT_INVALID:" + name)
        if member.issym():
            target = destination / name
            if not (target.parent / member.linkname).resolve().is_relative_to(destination.resolve()):
                raise ValueError("ARCHIVE_SYMLINK_ESCAPE:" + name)
    for name, member in entries.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if member.isdir():
            path.mkdir(exist_ok=True)
        elif member.isfile():
            with archive.extractfile(member) as source, path.open("xb") as target:
                target.write(source.read())
            path.chmod(0o755 if member.mode & 0o111 else 0o644)
    for name, member in entries.items():
        if member.issym():
            (destination / name).symlink_to(member.linkname)
    # Also catches indirect symlink chains which individually looked contained.
    tree.physical_files(destination)


def compare_physical(live: Path, sealed: Path, *, mutable=()) -> list[str]:
    """Exact physical membership, path type, bytes and executable-bit equality."""
    try:
        left, right = tree.physical_files(live), tree.physical_files(sealed)
        ignored = set(mutable)
        errors = ["SNAPSHOT_MEMBERSHIP_MISMATCH:" + p for p in sorted((left ^ right) - ignored)]
        for path in sorted((left & right) - ignored):
            if tree._payload(live, path) != tree._payload(sealed, path):
                errors.append("SNAPSHOT_PAYLOAD_MISMATCH:" + path)
            elif not (live / path).is_symlink() and bool((live / path).stat().st_mode & 0o111) != bool((sealed / path).stat().st_mode & 0o111):
                errors.append("SNAPSHOT_MODE_MISMATCH:" + path)
        return errors
    except (OSError, ValueError, RuntimeError) as exc:
        return ["SNAPSHOT_PHYSICAL_INVALID:" + str(exc)]


def postpublication_errors(live: Path, sealed: Path, published: dict) -> list[str]:
    """Only one append and the current ratification may differ from the seal."""
    try:
        registry = "PUBLICATION_ASSERTIONS.json"
        old = json.loads((sealed / registry).read_bytes())
        new = json.loads((live / registry).read_bytes())
        expected = dict(old, publication_assertions=old["publication_assertions"] + [published])
        if new != expected:
            return ["SNAPSHOT_ASSERTION_DELTA_INVALID"]
        ratification = f"RELEASE_RATIFICATIONS/{published['release_tag']}.json"
        tracked = subprocess.run(["git", "--no-replace-objects", "-C", str(live),
                                  "ls-tree", "-z", "HEAD", "--", ratification], capture_output=True)
        if tracked.returncode:
            return ["SNAPSHOT_HEAD_UNAVAILABLE"]
        if tracked.stdout and not (live / ratification).exists():
            return ["SNAPSHOT_RATIFICATION_MISSING"]
        canonical = (json.dumps(published, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode()
        record = {
            "schema": "elpis.release-ratification.v1", "version": published["version"],
            "release_tag": published["release_tag"], "sealed_commit": published["peeled_commit"],
            "manifest_sha256": published["manifest_sha256"],
            "publication_assertion_sha256": hashlib.sha256(canonical).hexdigest(),
        }
        # The assertion-only closeout stage is also a valid snapshot. If a
        # ratification exists it must be the exact authority, never arbitrary data.
        if (live / ratification).exists() and json.loads((live / ratification).read_bytes()) != record:
            return ["SNAPSHOT_RATIFICATION_INVALID"]
        for path in (registry, ratification):
            if (live / path).is_symlink():
                return ["SNAPSHOT_AUTHORITY_SYMLINK:" + path]
        return compare_physical(live, sealed, mutable=(registry, ratification))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return ["SNAPSHOT_AUTHORITY_INVALID:" + str(exc)]
