"""Compact release authority; see docs/COMPACT_RELEASE_AUTHORITY.md.

No Git objects, indexes, or persistent inventories are written by this module.
The historical v2 implementation deliberately does not use this policy.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess


SCHEMA = "elpis.release-manifest.v3"
ALGORITHM = "elpis.publication-tree.sha256.v1"
POLICY = "elpis.publication-membership.v1"
DOMAIN = b"elpis.publication-tree.v1\0"
EPHEMERAL_PARTS = {
    "build", "dist", "__pycache__", ".venv", ".pytest_cache",
    ".mypy_cache", ".ruff_cache",
}
IDENTITY_FIELDS = {
    "schema", "package_name", "release_name", "release_tag", "version",
    "primitive_closure_commit", "base_release_commit", "runtime_status",
    "full_elpis_runtime_admission", "request_guidance_gate_default",
    "output_authority_granted", "validation_authority_propagated",
    "generated_source_executed", "execution_authorized", "experiments_shipped",
    "nanbeige_host_shipped",
}
TREE_FIELDS = {
    "tree_digest_algorithm", "publication_policy", "publication_tree_sha256",
    "file_count", "git_tree_oid", "git_object_format",
}


def require_successor(version: str) -> None:
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) or tuple(
        map(int, version.split("."))
    ) <= (2, 2, 6):
        raise ValueError("V3_REQUIRES_SUCCESSOR_AFTER_2_2_6")


def normalized_path(value: str) -> str:
    path = PurePosixPath(value)
    if (not value or "\\" in value or "\0" in value or path.is_absolute()
            or ".." in path.parts or path.as_posix() != value or value == "."):
        raise ValueError(f"PUBLICATION_PATH_INVALID:{value!r}")
    value.encode("utf-8", errors="strict")
    return value


def excluded(value: str, manifest_rel: str) -> bool:
    return ".git" in PurePosixPath(value).parts or value in {
        manifest_rel, "PUBLISHED_RELEASES.json",
    }


def physical_files(root: Path) -> set[str]:
    """Scan even ignored/untracked paths; never follow directory symlinks."""
    result = set()
    def scan_error(error):
        raise error

    for directory, dirs, files in os.walk(root, followlinks=False, onerror=scan_error):
        dirs[:] = [name for name in dirs if name != ".git"]
        for name in dirs + files:
            path = Path(directory) / name
            rel = path.relative_to(root).as_posix()
            if ".git" in PurePosixPath(rel).parts:
                continue
            normalized_path(rel)
            parts = PurePosixPath(rel).parts
            if set(parts) & EPHEMERAL_PARTS or any(p.endswith(".egg-info") for p in parts):
                raise ValueError(f"EPHEMERAL ARTIFACT PRESENT:{rel}")
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                if not path.resolve().is_relative_to(root.resolve()):
                    raise ValueError(f"SYMLINK ESCAPE:{rel}")
                result.add(rel)
            elif stat.S_ISREG(mode):
                result.add(rel)
            elif not stat.S_ISDIR(mode):
                raise ValueError(f"PUBLICATION_FILE_TYPE_UNSUPPORTED:{rel}")
    return result


def _git(root: Path, *args: str) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=False,
    )
    if proc.returncode:
        raise ValueError("PUBLICATION_GIT_ERROR:" + proc.stderr.decode("utf-8", "replace").strip())
    return proc.stdout


def git_entries(root: Path, manifest_rel: str, *, head: bool) -> dict[str, tuple[str, str]]:
    command = ("ls-tree", "-rz", "--full-tree", "HEAD") if head else ("ls-files", "--stage", "-z")
    result = {}
    for entry in _git(root, *command).split(b"\0"):
        if not entry:
            continue
        meta, raw = entry.split(b"\t", 1)
        rel = normalized_path(raw.decode("utf-8"))
        if excluded(rel, manifest_rel):
            continue
        mode, second, third = meta.decode("ascii").split()
        oid = third if head else second
        if mode not in {"100644", "100755", "120000"}:
            raise ValueError(f"PUBLICATION_GIT_MODE_UNSUPPORTED:{rel}:{mode}")
        if not head and (third != "0" or rel in result):
            raise ValueError(f"PUBLICATION_INDEX_UNMERGED:{rel}")
        result[rel] = mode, oid
    return result


def publication_paths(root: Path, manifest_rel: str) -> list[str]:
    normalized_path(manifest_rel)
    physical = physical_files(root)
    paths = set(git_entries(root, manifest_rel, head=False)) if (root / ".git").exists() else {
        rel for rel in physical if not excluded(rel, manifest_rel)
    }
    missing = paths - physical
    if missing:
        raise ValueError("PUBLICATION_FILE_MISSING:" + sorted(missing)[0])
    return sorted(paths, key=lambda rel: rel.encode("utf-8"))


def _payload(root: Path, rel: str) -> tuple[bytes, bytes]:
    normalized_path(rel)
    path = root / rel
    # A caller of the direct digest API gets the same traversal protection.
    for parent in path.relative_to(root).parents:
        if (root / parent).is_symlink():
            raise ValueError(f"PUBLICATION_SYMLINK_PARENT:{rel}")
    if path.is_symlink():
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"SYMLINK ESCAPE:{rel}")
        return b"L", os.readlink(path).encode("utf-8")
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError(f"PUBLICATION_FILE_TYPE_UNSUPPORTED:{rel}")
    return b"F", path.read_bytes()


def tree_digest(root: Path, paths: list[str]) -> str:
    """SHA256(domain || u64(count) || framed records), with big-endian u64s."""
    ordered = sorted((normalized_path(p) for p in paths), key=lambda p: p.encode("utf-8"))
    if len(set(ordered)) != len(ordered):
        raise ValueError("PUBLICATION_DUPLICATE_PATH")
    digest = hashlib.sha256(DOMAIN)
    digest.update(len(ordered).to_bytes(8, "big"))
    for rel in ordered:
        encoded = rel.encode("utf-8")
        kind, content = _payload(root, rel)
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(kind)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest()


def _object_digest(kind: bytes, content: bytes, object_format: str) -> str:
    return hashlib.new(object_format, kind + b" " + str(len(content)).encode("ascii") + b"\0" + content).hexdigest()


def git_tree_digest(entries: dict[str, tuple[str, str]], object_format: str) -> str:
    """Native Git tree hashing, including Git's directory sort terminator."""
    tree = {}
    for rel, leaf in entries.items():
        node = tree
        parts = PurePosixPath(normalized_path(rel)).parts
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = leaf

    def encode(node):
        content = bytearray()
        for name, value in sorted(node.items(), key=lambda pair: (
            pair[0].encode("utf-8") + (b"/" if isinstance(pair[1], dict) else b"")
        )):
            mode, oid = ("40000", encode(value)) if isinstance(value, dict) else value
            content.extend(mode.encode("ascii") + b" " + name.encode("utf-8") + b"\0" + bytes.fromhex(oid))
        return _object_digest(b"tree", bytes(content), object_format)

    return encode(tree)


def checkout_tree(root: Path, manifest_rel: str, paths: list[str]) -> tuple[str, str]:
    object_format = _git(root, "rev-parse", "--show-object-format").decode("ascii").strip()
    if object_format not in {"sha1", "sha256"}:
        raise ValueError("PUBLICATION_GIT_OBJECT_FORMAT_UNSUPPORTED")
    head = git_entries(root, manifest_rel, head=True)
    index = git_entries(root, manifest_rel, head=False)
    if head != index:
        raise ValueError("PUBLICATION_GIT_INDEX_HEAD_MISMATCH")
    physical = {}
    for rel in paths:
        kind, content = _payload(root, rel)
        mode = "120000" if kind == b"L" else (
            "100755" if (root / rel).stat().st_mode & stat.S_IXUSR else "100644"
        )
        physical[rel] = mode, _object_digest(b"blob", content, object_format)
    if physical != head:
        raise ValueError("PUBLICATION_GIT_WORKTREE_HEAD_MISMATCH")
    return git_tree_digest(head, object_format), object_format


def build_record(root: Path, manifest_rel: str) -> dict:
    paths = publication_paths(root, manifest_rel)
    oid, object_format = checkout_tree(root, manifest_rel, paths) if (root / ".git").exists() else (None, None)
    return {
        "tree_digest_algorithm": ALGORITHM,
        "publication_policy": POLICY,
        "publication_tree_sha256": tree_digest(root, paths),
        "file_count": len(paths),
        "git_tree_oid": oid,
        "git_object_format": object_format,
    }


def verify_record(root: Path, manifest_rel: str, data: dict) -> list[str]:
    """Fail closed on extension inventories, unknown policies, or mismatches."""
    if set(data) != IDENTITY_FIELDS | TREE_FIELDS:
        return ["V3_AUTHORITY_FIELDS_INVALID"]
    if data.get("tree_digest_algorithm") != ALGORITHM or data.get("publication_policy") != POLICY:
        return ["V3_PUBLICATION_POLICY_INVALID"]
    if (type(data.get("file_count")) is not int or data["file_count"] < 0
            or not isinstance(data.get("publication_tree_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", data["publication_tree_sha256"])):
        return ["V3_TREE_RECORD_INVALID"]
    fmt, oid = data.get("git_object_format"), data.get("git_tree_oid")
    if not ((fmt is None and oid is None) or (
        fmt in ("sha1", "sha256") and isinstance(oid, str)
        and re.fullmatch(r"[0-9a-f]{%d}" % (40 if fmt == "sha1" else 64), oid)
    )):
        return ["V3_GIT_RECORD_INVALID"]
    try:
        actual = build_record(root, manifest_rel)
    except (ValueError, OSError, RuntimeError) as exc:
        return [str(exc)]
    errors = []
    for field in ("publication_tree_sha256", "file_count"):
        if data[field] != actual[field]:
            errors.append(f"V3_{field.upper()}_MISMATCH")
    if (root / ".git").exists():
        for field in ("git_tree_oid", "git_object_format"):
            if data[field] != actual[field]:
                errors.append(f"V3_{field.upper()}_MISMATCH")
    return errors
