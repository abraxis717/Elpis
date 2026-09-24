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
import subprocess


def verify_tag(root: Path, oid: str, target: str, tag: str, allowed_signers: Path | None) -> dict:
    if allowed_signers is None:
        raise ValueError("ORIGIN_TRUST_ROOT_REQUIRED")
    authority = Path(allowed_signers).resolve(strict=True)
    if authority.is_relative_to(root.resolve()):
        raise ValueError("ORIGIN_TRUST_ROOT_IN_REPOSITORY")
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
                           capture_output=True, env=dict(os.environ, GIT_NO_REPLACE_OBJECTS="1"))
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
    program = shutil.which("ssh-keygen")
    if not program:
        raise ValueError("ORIGIN_SSH_KEYGEN_UNAVAILABLE")
    git("-c", "gpg.format=ssh", "-c", "gpg.ssh.program=" + program,
        "-c", "gpg.minTrustLevel=fully",
        "-c", "gpg.ssh.allowedSignersFile=" + str(authority),
        "-c", "gpg.ssh.revocationFile=", "verify-tag", oid)
    if authority.read_bytes() != raw:
        raise ValueError("ORIGIN_TRUST_ROOT_CHANGED")
    return {"tag_object": oid, "allowed_signers_sha256": hashlib.sha256(raw).hexdigest(),
            "signature_format": "ssh-ed25519"}
