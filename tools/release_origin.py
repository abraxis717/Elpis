"""Verify an SSH tag using caller-supplied, external signer authority.

The repository may provide an object identity; it cannot provide its trust root.
No signing or key generation is performed here.
"""
from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess



def _repository_git_env() -> dict[str, str]:
    """Minimal environment for repository-location observations."""
    env = dict(os.environ)

    forbidden = {
        "GIT_COMMON_DIR",
        "GIT_CONFIG",
        "GIT_CONFIG_COUNT",
        "GIT_CONFIG_PARAMETERS",
        "GIT_GRAFT_FILE",
        "GIT_IMPLICIT_WORK_TREE",
        "GIT_PREFIX",
        "GIT_SHALLOW_FILE",
        "GIT_NAMESPACE",
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_REPLACE_REF_BASE",
    }

    for key in list(env):
        if key in forbidden or key.startswith("GIT_CONFIG"):
            env.pop(key, None)

    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    return env


def _repository_storage_roots(root: Path) -> tuple[Path, ...]:
    """Return every physical filesystem root controlled by this checkout.

    A linked worktree's visible checkout, per-worktree Git directory, and
    common Git directory can live in different filesystem trees. Signer trust
    authority must be independent of all of them.
    """

    root = root.resolve(strict=True)
    env = _repository_git_env()

    commands = (
        ("worktree", ("rev-parse", "--show-toplevel")),
        ("git_dir", ("rev-parse", "--absolute-git-dir")),
        (
            "git_common_dir",
            (
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
            ),
        ),
    )

    observed = []

    for label, args in commands:
        proc = subprocess.run(
            [
                "git",
                "--no-replace-objects",
                "-C",
                str(root),
                *args,
            ],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

        if proc.returncode != 0:
            raise ValueError(
                "ORIGIN_REPOSITORY_STORAGE_UNAVAILABLE:"
                + label
                + ":"
                + (proc.stderr or "")[-1000:]
            )

        value = (proc.stdout or "").strip()

        if not value:
            raise ValueError(
                "ORIGIN_REPOSITORY_STORAGE_INVALID:"
                + label
            )

        candidate = Path(value).resolve(strict=True)

        if not candidate.is_dir():
            raise ValueError(
                "ORIGIN_REPOSITORY_STORAGE_INVALID:"
                + label
            )

        observed.append(candidate)

    unique = []
    for candidate in observed:
        if candidate not in unique:
            unique.append(candidate)

    # If one storage root physically contains another, scanning the parent
    # already covers the child. Keep only the minimal non-overlapping roots.
    roots = []
    for candidate in unique:
        contained = any(
            candidate != other
            and candidate.is_relative_to(other)
            for other in unique
        )
        if not contained:
            roots.append(candidate)

    if not roots:
        raise ValueError("ORIGIN_REPOSITORY_STORAGE_INVALID")

    return tuple(sorted(roots, key=lambda item: str(item)))

def _validate_trust_root_storage(root: Path, authority: Path) -> tuple[int, int, int, int]:
    root = root.resolve(strict=True)
    authority = authority.resolve(strict=True)

    info = authority.stat()

    if not stat.S_ISREG(info.st_mode):
        raise ValueError("ORIGIN_TRUST_ROOT_NOT_REGULAR_FILE")

    if info.st_uid != os.geteuid():
        raise ValueError("ORIGIN_TRUST_ROOT_OWNER_UNSAFE")

    if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise ValueError("ORIGIN_TRUST_ROOT_MODE_UNSAFE")

    identity = (info.st_dev, info.st_ino)

    # Path-external is insufficient. A trust root outside the visible
    # worktree may still hardlink repository-controlled storage in either
    # the checkout, the linked-worktree Git directory, or the common Git
    # directory. Scan every physical repository storage root.
    for storage_root in _repository_storage_roots(root):
        for directory, _directories, filenames in os.walk(
            storage_root,
            followlinks=False,
        ):
            base = Path(directory)

            for filename in filenames:
                candidate = base / filename

                try:
                    candidate_info = candidate.stat(
                        follow_symlinks=False
                    )
                except FileNotFoundError:
                    continue

                if (
                    stat.S_ISREG(candidate_info.st_mode)
                    and (
                        candidate_info.st_dev,
                        candidate_info.st_ino,
                    )
                    == identity
                ):
                    raise ValueError(
                        "ORIGIN_TRUST_ROOT_IN_REPOSITORY_STORAGE"
                    )

    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
    )


def verify_tag(root: Path, oid: str, target: str, tag: str, allowed_signers: Path | None) -> dict:
    if allowed_signers is None:
        raise ValueError("ORIGIN_TRUST_ROOT_REQUIRED")
    authority = Path(allowed_signers).resolve(strict=True)
    if authority.is_relative_to(root.resolve()):
        raise ValueError("ORIGIN_TRUST_ROOT_IN_REPOSITORY")

    authority_identity = _validate_trust_root_storage(root, authority)
    raw = authority.read_bytes()
    # Deliberately narrow v1 profile. No wildcard principals or options that
    # could silently broaden namespaces. Git verifies namespace 'git'.
    lines = [line for line in raw.decode("ascii").splitlines() if line and not line.startswith("#")]
    if not lines:
        raise ValueError("ORIGIN_SIGNERS_INVALID")
    for line in lines:
        parts = line.split()
        if len(parts) != 3 or not re.fullmatch(r"[A-Za-z0-9_.@+-]+", parts[0]) or parts[1] != "ssh-ed25519":
            raise ValueError("ORIGIN_SIGNERS_INVALID")
        try:
            key = base64.b64decode(parts[2], validate=True)
        except ValueError as exc:
            raise ValueError("ORIGIN_SIGNERS_INVALID") from exc
        if len(key) != 51 or key[:19] != b"\0\0\0\x0bssh-ed25519\0\0\0\x20":
            raise ValueError("ORIGIN_SIGNERS_INVALID")
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", oid):
        raise ValueError("ORIGIN_OBJECT_INVALID")
    def git(*args):
        p = subprocess.run(["git", "--no-replace-objects", "-C", str(root), *args],
                           capture_output=True, env=_repository_git_env())
        if p.returncode:
            raise ValueError("ORIGIN_GIT_VERIFICATION_FAILED:" + p.stderr.decode(errors="replace"))
        return p.stdout
    if git("cat-file", "-t", oid).strip() != b"tag":
        raise ValueError("ORIGIN_ANNOTATED_TAG_REQUIRED")
    payload = git("cat-file", "tag", oid)
    headers = payload.split(b"\n\n", 1)[0].splitlines()
    if headers[:3] != [f"object {target}".encode(), b"type commit", f"tag {tag}".encode()]:
        raise ValueError("ORIGIN_TAG_TARGET_OR_NAME_MISMATCH")
    if (payload.count(b"-----BEGIN SSH SIGNATURE-----\n") != 1
            or payload.count(b"-----END SSH SIGNATURE-----\n") != 1
            or not payload.endswith(b"-----END SSH SIGNATURE-----\n")
            or b"-----BEGIN PGP SIGNATURE-----" in payload):
        raise ValueError("ORIGIN_SSH_SIGNATURE_REQUIRED")
    # Git selects the verifier from the last recognized BEGIN marker, rather
    # than gpg.format. Strict SSH armor prevents an embedded OpenPGP/X509 marker
    # from routing verification to a repository-configured alternative program.
    armor = payload.split(b"-----BEGIN SSH SIGNATURE-----\n", 1)[1]
    encoded = armor.removesuffix(b"-----END SSH SIGNATURE-----\n").replace(b"\n", b"")
    try:
        signature = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise ValueError("ORIGIN_SSH_ARMOR_INVALID") from exc
    if not signature.startswith(b"SSHSIG"):
        raise ValueError("ORIGIN_SSH_ARMOR_INVALID")
    program = shutil.which("ssh-keygen")
    if not program:
        raise ValueError("ORIGIN_SSH_KEYGEN_UNAVAILABLE")
    git("-c", "gpg.format=ssh", "-c", "gpg.ssh.program=" + program,
        "-c", "gpg.minTrustLevel=fully",
        "-c", "gpg.ssh.allowedSignersFile=" + str(authority),
        "verify-tag", oid)
    if authority.read_bytes() != raw:
        raise ValueError("ORIGIN_TRUST_ROOT_CHANGED")
    if _validate_trust_root_storage(root, authority) != authority_identity:
        raise ValueError("ORIGIN_TRUST_ROOT_CHANGED")
    return {"tag_object": oid, "allowed_signers_sha256": hashlib.sha256(raw).hexdigest(),
            "signature_format": "ssh-ed25519"}
