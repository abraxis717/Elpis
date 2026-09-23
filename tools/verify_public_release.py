#!/usr/bin/env python3
"""Fail-closed, VERSION-driven public release verifier."""

from __future__ import annotations

import ast
import argparse
import hashlib
import io
import json
import os
import re
import runpy
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from pathlib import Path


sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parent.parent

RELEASE_VERSION = (REPO / "VERSION").read_text(encoding="utf-8").strip()
PACKAGE_NAME = "elpisai"
# Ratified repository identities, never inferred from a manifest's claims.
RELEASE_IDENTITIES = {
    "2.1.2": {
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.3": {
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.4": {
        # Release-integrity successor only: no primitive/runtime closure moved.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # This field is the original Elpis2.0.0 distribution baseline, not predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.5": {
        # Furyan scientific-source successor; primitive/runtime closure unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.6": {
        # Security/integrity successor; primitive/runtime closure unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.7": {
        # README-paper successor; primitive/runtime closure unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.8": {
        # Runtime/correctness successor; the ratified Elpis2.0.0 primitive
        # closure identity remains the primitive baseline.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.9": {
        # Structural-correctness/runtime-boundary successor; primitive closure
        # remains the ratified Elpis2.0.0 baseline.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.10": {
        # Local release successor; primitive closure remains the ratified baseline.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.11": {
        # APW R0 evidence successor; primitive/runtime closure is unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.12": {
        # ECS structural-authority publication successor; primitive/runtime closure unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.13": {
        # Executable ECS R0 and repository-hardening successor; primitive/runtime closure unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.14": {
        # Hosted-completeness and elpisai distribution successor; primitive/runtime closure unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.15": {
        # Reference-runtime elpisai metadata repair; primitive/runtime closure unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.16": {
        # README Paper R1 / distribution-metadata successor; primitive/runtime closure unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.17": {
        # Grid81 canonical-writer engineering successor; primitive/runtime closure unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.18": {
        # Corrective successor to failed untagged 2.1.17; primitive/runtime closure unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.19": {
        # Sealed-control copy-harness corrective successor; primitive/runtime closure unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.20": {
        # Hosted-CI history/tag checkout corrective successor; primitive/runtime closure unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.21": {
        # Publication-registry cycle corrective successor; runtime closure unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.22": {
        # Structural-guidance authority-integrity successor; primitive/runtime closure unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.23": {
        # ECS evidence/layout and release-note archive successor; primitive/runtime closure unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.24": {
        # Publisher R1, Regex V2, and ECS M1A engineering successor; primitive closure unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.25": {
        # Corrective successor to tagged-but-unpublished 2.1.24; primitive closure unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.26": {
        # Repository-identity/distribution-metadata successor; primitive/runtime closure unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.27": {
        # Bounded AST-policy/release-infrastructure maintenance successor;
        # primitive/runtime closure unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.0": {
        # Release-integrity, portability, and qualified internal-capability
        # successor; primitive closure remains the ratified Elpis2.0.0 baseline.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.1": {
        # Release-information coherence corrective successor.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },

    "2.2.2": {
        # README/public-release-information contract corrective successor;
        # primitive/runtime closure and original Elpis2.0.0 baseline unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },

    "2.2.3": {
        # PyPI publication-workflow repair successor; primitive/runtime
        # closure and original Elpis2.0.0 baseline unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },

    "2.2.4": {
        # Publication-workflow contract-test corrective successor; primitive/runtime
        # closure and original Elpis2.0.0 baseline unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },

    "2.2.5": {
        # Runtime-composition integration successor; primitive closure and
        # original Elpis2.0.0 distribution baseline remain unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.6": {
        # Hosted-completeness and release-hygiene corrective successor;
        # primitive/runtime closure and original distribution baseline unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.7": {
        # Hosted repository-hygiene mechanics corrective successor;
        # primitive/runtime closure and original distribution baseline unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.8": {
        # Red-team hardening and release-lifecycle corrective successor;
        # primitive/runtime closure and original distribution baseline unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.9": {
        # Release-metadata corrective successor to failed untagged 2.2.8;
        # primitive/runtime closure, frozen authority, and original distribution baseline unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.10": {
        # Release-information coherence corrective successor to tagged-unpublished 2.2.9;
        # primitive/runtime closure, frozen authority, and original distribution baseline unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.11": {
        # Post-publication correctness/portability corrective successor;
        # primitive/runtime closure, frozen authority, and original distribution baseline unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.12": {
        # Bounded-feedback and platform-driver portability successor;
        # primitive closure and original distribution baseline unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.13": {
        # Corrective successor to immutable tagged-unpublished Elpis2.2.12;
        # primitive/runtime closure and original distribution baseline unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.14": {
        # Integrity and authority-boundary successor; ratified primitive closure
        # and original distribution baseline remain unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.15": {
        # Corrective hosted-CI convergence successor; primitive/runtime closure
        # and original distribution baseline remain unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.16": {
        # Annotated-tag checkout corrective successor; primitive/runtime closure
        # and original distribution baseline remain unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.17": {
        # CI annotated-tag checkout corrective successor; primitive/runtime closure
        # and original distribution baseline remain unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.18": {
        # Git-less publication-projection corrective successor.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.19": {
        # Explicit publication-authority corrective successor.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.20": {
        # Publication-authority v2 lifecycle successor; primitive/runtime
        # closure and original distribution baseline remain unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.21": {
        # Isolated native inference / bounded Needle3 successor;
        # primitive closure and original distribution baseline unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.22": {
        # Corrective hosted-CI successor to the untagged 2.2.21 seal;
        # primitive closure and original distribution baseline unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.23": {
        # ECSContextProjector integration successor; primitive closure
        # and original distribution baseline remain unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.24": {
        # Active-assembly and release-lifecycle corrective successor;
        # primitive closure and original distribution baseline unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.25": {
        # Qualified inference-infrastructure R0 successor; primitive closure
        # and original distribution baseline remain unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.26": {
        # Hosted-native qualification and Runtime R3 integrity corrective successor;
        # primitive closure and original distribution baseline remain unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.27": {
        # Hosted native workflow-context corrective successor to untagged 2.2.26;
        # primitive closure and original distribution baseline remain unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.28": {
        # Red-team corrective successor; primitive closure and original
        # distribution baseline remain unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.29": {
        # Postrelease corrective successor; primitive closure and original
        # distribution baseline remain unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.30": {
        # Postrelease corrective successor; primitive closure and original
        # distribution baseline remain unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.2.31": {
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
}
RELEASE_MANIFEST_REL = Path(f"manifests/Elpis{RELEASE_VERSION}.RELEASE_MANIFEST.json")
DISTRIBUTION_MANIFEST_REL = Path(f"manifests/Elpis{RELEASE_VERSION}.DISTRIBUTION_MANIFEST.json")
MANIFEST_REL = (DISTRIBUTION_MANIFEST_REL
                if (REPO / DISTRIBUTION_MANIFEST_REL).exists()
                else RELEASE_MANIFEST_REL)
MANIFEST = REPO / MANIFEST_REL
PUBLICATION_REGISTRY_REL = Path("PUBLISHED_RELEASES.json")
IGNORE_PARTS = {".git"}
EPHEMERAL_PARTS = {"build", "dist", "__pycache__", ".venv",
                   ".pytest_cache", ".mypy_cache", ".ruff_cache"}
ALLOWLIST_REL = Path("tools/public_scan_allowlist.json")


def release_identity():
    identity = RELEASE_IDENTITIES.get(RELEASE_VERSION)
    if identity is None:
        raise ValueError(f"UNKNOWN_RELEASE_IDENTITY: {RELEASE_VERSION}")
    if any(value == "UNSEALED" for value in identity.values()):
        raise ValueError(f"UNSEALED_RELEASE_IDENTITY: {RELEASE_VERSION}")
    return identity


def ephemeral(rel: Path) -> bool:
    return bool(set(rel.parts) & EPHEMERAL_PARTS) or any(
        part.endswith(".egg-info") for part in rel.parts
    )


BINARY_SUFFIXES = {
    ".so", ".a", ".o", ".pyc",
    ".egg", ".gguf", ".safetensors", ".pt",
}

TEXT_SUFFIXES = {
    ".py", ".c", ".cpp", ".h",
    ".json", ".toml", ".yaml", ".yml",
    ".md", ".txt", ".cff", ".cmake", ".sh",
}

SECRET_PATTERNS = (
    (
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
        "private key",
    ),
    (
        r"(?<![A-Za-z0-9_])ghp_[A-Za-z0-9]{36}(?![A-Za-z0-9_])",
        "GitHub PAT",
    ),
    (
        r"(?<![A-Za-z0-9_])github_pat_[A-Za-z0-9_]{20,}"
        r"(?![A-Za-z0-9_])",
        "GitHub PAT",
    ),
    (
        r"(?<![A-Za-z0-9_])sk-(?:proj|svcacct|admin)-"
        r"[A-Za-z0-9_-]{20,}(?![A-Za-z0-9_])",
        "OpenAI-style key",
    ),
    (
        r"(?<![A-Za-z0-9_])sk-[A-Za-z0-9]{48,}"
        r"(?![A-Za-z0-9_])",
        "OpenAI-style key",
    ),
    (
        r"(?<![A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])",
        "AWS key",
    ),
    (
        r"(?<![A-Za-z0-9_])AIza[A-Za-z0-9_-]{35}"
        r"(?![A-Za-z0-9_])",
        "Google API key",
    ),
    (
        r"(?<![A-Za-z0-9_])glpat-[A-Za-z0-9_-]{20,}"
        r"(?![A-Za-z0-9_])",
        "GitLab PAT",
    ),
    (
        r"(?<![A-Za-z0-9_])xox[baprs]-[A-Za-z0-9-]{20,}"
        r"(?![A-Za-z0-9_])",
        "Slack token",
    ),
)
PRIVATE_PATH_PATTERNS = (
    r"(?<![A-Za-z0-9._-])/mnt/[A-Za-z0-9._-]+"
    r"(?:/[^\s\"<>]*)?",
    r"(?<![A-Za-z0-9._-])/(?:home|Users)/[A-Za-z0-9._-]+"
    r"(?:/[^\s\"<>]*)?",
    r"(?i)(?<![A-Za-z0-9_])[A-Z]:\\Users\\[A-Za-z0-9._-]+"
    r"(?:\\[^\s\"<>]*)?",
)



def digest(path: Path) -> str:
    if path.is_symlink():
        payload = path.readlink().as_posix().encode()
    else:
        payload = path.read_bytes()

    return hashlib.sha256(payload).hexdigest()


def ignored(rel: Path) -> bool:
    return bool(set(rel.parts) & IGNORE_PARTS)


def release_paths() -> list[Path]:
    return sorted(path for path in REPO.rglob("*")
                  if not ignored(path.relative_to(REPO)))


def actual_files() -> set[str]:
    """Return manifest-authority membership for this verification context.

    A live Git checkout derives release membership only from tracked paths.
    Clone-local ignored or untracked residue is not publication authority and
    is handled separately by physical-tree safety scans. A Git-less exported
    tree has no tracking metadata, so its physical non-ephemeral file set is
    the only available authority; arbitrary undeclared junk therefore remains
    visible and fails manifest exactness.
    """
    if (REPO / ".git").exists():
        proc = subprocess.run(
            ["git", "-C", str(REPO), "ls-files", "-z"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                "git ls-files failed while verifying release tree: "
                + proc.stderr.decode("utf-8", errors="replace")
            )

        out: set[str] = set()
        for raw in proc.stdout.split(b"\0"):
            if not raw:
                continue
            rel = Path(raw.decode("utf-8"))
            if ignored(rel) or rel in {MANIFEST_REL, PUBLICATION_REGISTRY_REL}:
                continue
            path = REPO / rel
            if path.is_file() or path.is_symlink():
                out.add(rel.as_posix())
            else:
                raise RuntimeError(
                    f"tracked release path missing from working tree: {rel.as_posix()}"
                )
        return out

    out: set[str] = set()
    for path in release_paths():
        rel = path.relative_to(REPO)
        if (
            ignored(rel)
            or ephemeral(rel)
            or rel in {MANIFEST_REL, PUBLICATION_REGISTRY_REL}
        ):
            continue
        if path.is_file() or path.is_symlink():
            out.add(rel.as_posix())
    return out

def load_manifest():
    errors = []

    if not MANIFEST.exists():
        return {}, [
            f"missing {MANIFEST_REL.as_posix()}"
        ]

    try:
        data = json.loads(MANIFEST.read_text())
    except Exception as exc:
        return {}, [f"invalid manifest: {exc}"]

    if not isinstance(data, dict):
        return {}, ["invalid manifest: root must be an object"]

    expected_schema = (
        "elpis.distribution-manifest.v1"
        if MANIFEST_REL == DISTRIBUTION_MANIFEST_REL
        else "elpis.release-manifest.v2"
    )
    if data.get("schema") == "elpis.release-manifest.v3" and MANIFEST_REL != DISTRIBUTION_MANIFEST_REL:
        compact = runpy.run_path(str(Path(__file__).with_name("release_tree_digest.py")))
        try:
            compact["require_successor"](RELEASE_VERSION)
        except ValueError as exc:
            errors.append(str(exc))
        expected_schema = compact["SCHEMA"]

    try:
        identity = release_identity()
    except ValueError as exc:
        return data, [str(exc)]

    expected = {
        "schema": expected_schema,
        "release_name": f"Elpis{RELEASE_VERSION}",
        "release_tag": f"Elpis{RELEASE_VERSION}",
        "version": RELEASE_VERSION,
        "package_name": PACKAGE_NAME,
        "primitive_closure_commit": identity["primitive_closure_commit"],
        "runtime_status": "VALIDATED_SOURCE",
        "full_elpis_runtime_admission": True,
        "request_guidance_gate_default": False,
        "output_authority_granted": 0,
        "validation_authority_propagated": False,
        "generated_source_executed": False,
        "execution_authorized": False,
        "experiments_shipped": False,
        "nanbeige_host_shipped": False,
    }

    if RELEASE_VERSION != "2.1.2" or MANIFEST_REL == DISTRIBUTION_MANIFEST_REL:
        expected["base_release_commit"] = identity["base_release_commit"]
    if MANIFEST_REL == DISTRIBUTION_MANIFEST_REL:
        expected["distribution_version"] = RELEASE_VERSION
        expected["tag_immutable"] = True

    for key, value in expected.items():
        if data.get(key) != value:
            errors.append(
                f"manifest {key} mismatch: "
                f"{data.get(key)!r}"
            )

    return data, errors


def _published_current_record():
    records = []

    legacy_path = REPO / "PUBLISHED_RELEASES.json"
    if legacy_path.is_file():
        payload = json.loads(legacy_path.read_text(encoding="utf-8"))
        records.extend(payload.get("published_releases", []))

    successor_path = REPO / "PUBLICATION_ASSERTIONS.json"
    if successor_path.is_file():
        payload = json.loads(successor_path.read_text(encoding="utf-8"))
        records.extend(payload.get("publication_assertions", []))

    current = [
        row
        for row in records
        if isinstance(row, dict) and row.get("version") == RELEASE_VERSION
    ]
    if len(current) > 1:
        raise RuntimeError(
            "CURRENT_PUBLICATION_RECORD_CARDINALITY:"
            + str(len(current))
        )
    return current[0] if current else None


def _verify_v3_release_snapshot(compact, data):
    try:
        from tools import release_snapshot as snapshot
        from tools import publication_assertions_v2 as publication
    except ImportError:
        import release_snapshot as snapshot
        import publication_assertions_v2 as publication
    published = _published_current_record()

    if published is None or not (REPO / ".git").exists():
        errors = compact["verify_record"](
            REPO,
            MANIFEST_REL.as_posix(),
            data,
        )
        if (REPO / ".git").exists():
            # The compact manifest historically describes tracked membership.
            # Snapshot presentation adds the stricter physical contract.
            proc = _git_repository_command(["ls-tree", "-rz", "--name-only", "HEAD"])
            if proc.returncode:
                return errors + ["GIT_AUTHORITY_UNAVAILABLE"]
            expected = set(proc.stdout.split("\0")) - {""}
            try:
                actual = compact["physical_files"](REPO)
                difference = (actual ^ expected) - {MANIFEST_REL.as_posix()}
                if difference:
                    errors.append("SNAPSHOT_MEMBERSHIP_MISMATCH:" + repr(sorted(difference)))
                for rel in compact["publication_registry_exclusions"](data["publication_policy"]):
                    if rel in expected:
                        raw = subprocess.run(["git", "--no-replace-objects", "-C", str(REPO), "show", "HEAD:" + rel], capture_output=True)
                        if raw.returncode or compact["_payload"](REPO, rel) != (b"F", raw.stdout):
                            errors.append("SNAPSHOT_AUTHORITY_CHANGED:" + rel)
            except (OSError, ValueError, RuntimeError) as exc:
                errors.append("SNAPSHOT_PHYSICAL_INVALID:" + str(exc))
        return errors

    if published.get("manifest_path") != MANIFEST_REL.as_posix():
        return ["PUBLISHED_MANIFEST_PATH_MISMATCH"]

    manifest_sha = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    if published.get("manifest_sha256") != manifest_sha:
        return ["PUBLISHED_MANIFEST_SHA256_MISMATCH"]

    if published.get("peeled_object_type") != "commit":
        return ["PUBLISHED_PEELED_OBJECT_TYPE_INVALID"]

    peeled = published.get("peeled_commit")
    if not isinstance(peeled, str) or not re.fullmatch(r"[0-9a-f]{40,64}", peeled):
        return ["PUBLISHED_PEELED_COMMIT_INVALID"]

    authority_errors = publication.validation_errors(REPO)
    if authority_errors:
        return authority_errors
    tag_ref = "refs/tags/" + published["release_tag"]
    if (_git_resolve_commit(tag_ref) != peeled
            or _git_resolve_tag_object(tag_ref) != published.get("tag_object")):
        return ["GIT_AUTHORITY_UNAVAILABLE"]
    if not _git_is_ancestor(peeled, "HEAD"):
        return ["SNAPSHOT_HEAD_NOT_DESCENDANT"]

    proc = subprocess.run(
        ["git", "-C", str(REPO), "archive", "--format=tar", peeled],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        return [
            "PUBLISHED_SEAL_ARCHIVE_FAILED:"
            + proc.stderr.decode("utf-8", "replace").strip()
        ]

    with tempfile.TemporaryDirectory() as td:
        sealed_root = Path(td)
        with tarfile.open(
            fileobj=io.BytesIO(proc.stdout),
            mode="r:",
        ) as archive:
            snapshot.extract_git_archive(archive, sealed_root)

        sealed_manifest = sealed_root / MANIFEST_REL
        if not sealed_manifest.is_file():
            return ["PUBLISHED_SEAL_MANIFEST_MISSING"]

        if hashlib.sha256(sealed_manifest.read_bytes()).hexdigest() != manifest_sha:
            return ["PUBLISHED_SEAL_MANIFEST_SHA256_MISMATCH"]

        errors = compact["verify_record"](
            sealed_root,
            MANIFEST_REL.as_posix(),
            data,
        )
        if _git_resolve_commit("HEAD") == peeled:
            errors += snapshot.compare_physical(REPO, sealed_root)
        else:
            errors += snapshot.postpublication_errors(REPO, sealed_root, published)
        return errors


def check_manifest():
    data, errors = load_manifest()
    if data.get("schema") == "elpis.release-manifest.v3":
        compact = runpy.run_path(str(Path(__file__).with_name("release_tree_digest.py")))
        errors += _verify_v3_release_snapshot(compact, data)
        return not errors, errors
    return _check_inventory_manifest(data, errors)


def _check_inventory_manifest(data, errors):
    """Historical release v2 / distribution v1 byte and membership rules."""
    entries = data.get("files", [])

    if not isinstance(entries, list):
        return False, errors + [
            "manifest files must be a list"
        ]

    declared = {}

    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("invalid manifest file entry")
            continue

        rel = entry.get("path")
        expected = entry.get("sha256")

        if not isinstance(rel, str) or not rel:
            errors.append("invalid manifest path")
            continue

        if rel in declared:
            errors.append(f"duplicate path: {rel}")
            continue

        if (
            not isinstance(expected, str)
            or len(expected) != 64
        ):
            errors.append(
                f"invalid digest for {rel}"
            )
            continue

        declared[rel] = expected

    actual = actual_files()

    for rel in sorted(set(declared) - actual):
        errors.append(f"MISSING: {rel}")

    for rel in sorted(actual - set(declared)):
        errors.append(f"UNDECLARED: {rel}")

    for rel in sorted(set(declared) & actual):
        if digest(REPO / rel) != declared[rel]:
            errors.append(
                f"DIGEST MISMATCH: {rel}"
            )

    if data.get("file_count") != len(declared):
        errors.append("manifest file_count mismatch")

    return not errors, errors


_DECLARED_TEXT_VERSION_PATTERNS = {
    "README.md": re.compile(
        r"(?m)^\*\*Release line: Elpis"
        r"([0-9]+\.[0-9]+\.[0-9]+)"
        r"\*\*[ \t]*$"
    ),
    f"RELEASE_NOTES/Elpis{RELEASE_VERSION}.md": re.compile(
        r"(?m)^## Version: v"
        r"([0-9]+\.[0-9]+\.[0-9]+)"
        r"[ \t]*$"
    ),
}


def check_declared_text_version():
    errors = []

    for rel, pattern in (
        _DECLARED_TEXT_VERSION_PATTERNS.items()
    ):
        path = REPO / rel

        try:
            text = path.read_text(
                encoding="utf-8",
                errors="strict",
            )
        except (OSError, UnicodeError) as exc:
            errors.append(
                "DECLARED_TEXT_VERSION_INVALID: "
                f"{rel}: {exc}"
            )
            continue

        matches = pattern.findall(text)

        if len(matches) != 1:
            errors.append(
                "DECLARED_TEXT_VERSION_INVALID: "
                f"{rel}: declarations={len(matches)}"
            )
            continue

        declared = matches[0]

        if declared != RELEASE_VERSION:
            errors.append(
                "DECLARED_TEXT_VERSION_MISMATCH: "
                f"{rel}: "
                f"declared={declared} "
                f"expected={RELEASE_VERSION}"
            )

    return not errors, errors


def check_package():
    errors = []
    data = tomllib.loads(
        (REPO / "pyproject.toml").read_text()
    )
    project = data["project"]

    if project.get("name") != PACKAGE_NAME:
        errors.append(f"package name is not {PACKAGE_NAME}")

    if project.get("version") != RELEASE_VERSION:
        errors.append(f"package version is not {RELEASE_VERSION}")

    if (REPO / "VERSION").read_text().strip() != RELEASE_VERSION:
        errors.append("VERSION mismatch")

    if not any(
        isinstance(dep, str) and dep.startswith("scipy")
        for dep in project.get("dependencies", [])
    ):
        errors.append("SciPy dependency missing")

    return not errors, errors


def constant_assignment(path: Path, name: str):
    tree = ast.parse(
        path.read_text(),
        filename=str(path),
    )

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == name
                    and isinstance(node.value, ast.Constant)
                ):
                    return node.value.value

        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
            and isinstance(node.value, ast.Constant)
        ):
            return node.value.value

    raise RuntimeError(
        f"{name} constant assignment not found"
    )


_RUNTIME_FORBIDDEN_IMPORT_ROOTS = {
    "subprocess",
    "importlib",
    "ctypes",
    "runpy",
}
_RUNTIME_FORBIDDEN_BUILTIN_CALLS = {
    "compile",
    "eval",
    "exec",
    "__import__",
}

# This is intentionally a bounded regression tripwire, not a Python sandbox
# and not a proof that arbitrary execution is impossible. It rejects only the
# explicitly enumerated import/call/dynamic-lookup forms implemented below.
RUNTIME_POLICY_TRIPWIRE_SCOPE = (
    "enumerated_ast_execution_tripwire_not_python_sandbox"
)


def _runtime_static_string(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _runtime_static_string(node.left)
        right = _runtime_static_string(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _runtime_policy_findings(path: Path):
    tree = ast.parse(
        path.read_text(encoding="utf-8"),
        filename=str(path),
    )
    module_aliases = {}
    symbol_aliases = {}
    findings = set()

    def add(kind, detail):
        findings.add(f"{kind}:{detail}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".", 1)[0]
                module_aliases[bound] = alias.name
                root_name = alias.name.split(".", 1)[0]
                if root_name in _RUNTIME_FORBIDDEN_IMPORT_ROOTS:
                    add("execution_import", alias.name)

        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root_name = module.split(".", 1)[0] if module else ""
            if root_name in _RUNTIME_FORBIDDEN_IMPORT_ROOTS:
                add("execution_import", module)
            for alias in node.names:
                if alias.name == "*":
                    continue
                bound = alias.asname or alias.name
                target = f"{module}.{alias.name}" if module else alias.name
                symbol_aliases[bound] = target

                if module == "os" and alias.name == "system":
                    add("execution_import", "os.system")
                if (
                    module == "builtins"
                    and alias.name in _RUNTIME_FORBIDDEN_BUILTIN_CALLS
                ):
                    add("execution_import", f"builtins.{alias.name}")

    def resolve_name(name):
        if name in symbol_aliases:
            return symbol_aliases[name]
        if name in module_aliases:
            return module_aliases[name]
        return name

    def resolve_object(node):
        if isinstance(node, ast.Name):
            return resolve_name(node.id)
        return None

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        target = None
        if isinstance(node.func, ast.Name):
            target = resolve_name(node.func.id)
        elif (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
        ):
            base = resolve_name(node.func.value.id)
            target = f"{base}.{node.func.attr}"

        if target in _RUNTIME_FORBIDDEN_BUILTIN_CALLS:
            add("execution_call", target)
        if target in {
            f"builtins.{name}"
            for name in _RUNTIME_FORBIDDEN_BUILTIN_CALLS
        }:
            add("execution_call", target)
        if target == "os.system":
            add("execution_call", target)

        if target is not None:
            root_name = target.split(".", 1)[0]
            if root_name in _RUNTIME_FORBIDDEN_IMPORT_ROOTS:
                add("execution_call", target)

        if target in {"getattr", "builtins.getattr"} and len(node.args) >= 2:
            object_name = resolve_object(node.args[0])
            attribute = _runtime_static_string(node.args[1])
            if attribute is None:
                continue

            if (
                object_name in {"__builtins__", "builtins"}
                and attribute in _RUNTIME_FORBIDDEN_BUILTIN_CALLS
            ):
                add(
                    "dynamic_execution_lookup",
                    f"{object_name}.{attribute}",
                )

            if object_name == "os" and attribute == "system":
                add("dynamic_execution_lookup", "os.system")

            if object_name is not None:
                root_name = object_name.split(".", 1)[0]
                if root_name in _RUNTIME_FORBIDDEN_IMPORT_ROOTS:
                    add(
                        "dynamic_execution_lookup",
                        f"{object_name}.{attribute}",
                    )

    return sorted(findings)



_RUNTIME_AUTHORITY_LITERAL_FIELDS = frozenset({
    "execution_authorized",
    "validation_authorized",
})


def _runtime_authority_literal_findings(tree):
    """Reject explicit competing authority literals in runtime.py."""
    findings = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg not in _RUNTIME_AUTHORITY_LITERAL_FIELDS:
                    continue
                if (
                    isinstance(kw.value, ast.Constant)
                    and kw.value.value is not False
                ):
                    findings.add(
                        f"{kw.arg}:non_false_call_literal:"
                        f"line={getattr(node, 'lineno', 0)}"
                    )

        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if not (
                    isinstance(key, ast.Constant)
                    and key.value in _RUNTIME_AUTHORITY_LITERAL_FIELDS
                ):
                    continue
                if (
                    isinstance(value, ast.Constant)
                    and value.value is not False
                ):
                    findings.add(
                        f"{key.value}:non_false_dict_literal:"
                        f"line={getattr(node, 'lineno', 0)}"
                    )

    return sorted(findings)


def check_runtime_boundary():
    errors = []

    root = (
        REPO
        / "src/elpis_reference/structural_guidance"
    )

    try:
        admitted = constant_assignment(
            root / "authority.py",
            "FULL_ELPIS_RUNTIME_ADMISSION",
        )
    except Exception as exc:
        errors.append(str(exc))
    else:
        if admitted is not True:
            errors.append(
                "FULL_ELPIS_RUNTIME_ADMISSION != True"
            )

    admission_tree = ast.parse(
        (root / "admission.py").read_text()
    )

    default = None

    for node in admission_tree.body:
        if not (
            isinstance(node, ast.ClassDef)
            and node.name
            == "StructuralGuidanceAdmissionConfig"
        ):
            continue

        for item in node.body:
            if (
                isinstance(item, ast.AnnAssign)
                and isinstance(item.target, ast.Name)
                and item.target.id == "enabled"
                and isinstance(item.value, ast.Constant)
            ):
                default = item.value.value

    if default is not False:
        errors.append(
            "guidance request gate default != False"
        )

    for source in sorted(root.rglob("*.py")):
        try:
            findings = _runtime_policy_findings(source)
        except (OSError, UnicodeError, SyntaxError) as exc:
            errors.append(
                "runtime boundary source invalid: "
                f"{source.relative_to(root).as_posix()}: {exc}"
            )
            continue

        relative = source.relative_to(root).as_posix()
        for finding in findings:
            errors.append(
                f"RUNTIME_POLICY:{relative}:{finding}"
            )

    runtime = root / "runtime.py"
    tree = ast.parse(
        runtime.read_text(),
        filename=str(runtime),
    )

    for finding in _runtime_authority_literal_findings(tree):
        errors.append(
            f"RUNTIME_AUTHORITY_LITERAL:{finding}"
        )

    execution_false = False
    validation_false = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if (
                    kw.arg == "execution_authorized"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value is False
                ):
                    execution_false = True

                if (
                    kw.arg == "validation_authorized"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value is False
                ):
                    validation_false = True

    terminal_fn = next(
        (
            node
            for node in tree.body
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == "_terminal_result"
            )
        ),
        None,
    )

    if terminal_fn is None:
        errors.append(
            "_terminal_result function absent"
        )
    else:
        for node in ast.walk(terminal_fn):
            if not isinstance(node, ast.Dict):
                continue

            for key, value in zip(
                node.keys,
                node.values,
            ):
                if not (
                    isinstance(key, ast.Constant)
                    and isinstance(key.value, str)
                    and isinstance(value, ast.Constant)
                    and value.value is False
                ):
                    continue

                if key.value == "execution_authorized":
                    execution_false = True

                if key.value == "validation_authorized":
                    validation_false = True

    result_class = next(
        (
            node
            for node in tree.body
            if (
                isinstance(node, ast.ClassDef)
                and node.name
                == "StructuralGuidanceRuntimeResultV1"
            )
        ),
        None,
    )

    execution_guard = False
    validation_guard = False

    if result_class is None:
        errors.append(
            "StructuralGuidanceRuntimeResultV1 absent"
        )
    else:
        validate_fn = next(
            (
                node
                for node in result_class.body
                if (
                    isinstance(node, ast.FunctionDef)
                    and node.name == "validate"
                )
            ),
            None,
        )

        if validate_fn is None:
            errors.append(
                "terminal validate method absent"
            )
        else:
            for node in ast.walk(validate_fn):
                if not (
                    isinstance(node, ast.Compare)
                    and len(node.ops) == 1
                    and isinstance(node.ops[0], ast.IsNot)
                    and len(node.comparators) == 1
                    and isinstance(
                        node.comparators[0],
                        ast.Constant,
                    )
                    and node.comparators[0].value is False
                    and isinstance(node.left, ast.Attribute)
                    and isinstance(node.left.value, ast.Name)
                    and node.left.value.id == "self"
                ):
                    continue

                if node.left.attr == "execution_authorized":
                    execution_guard = True

                if node.left.attr == "validation_authorized":
                    validation_guard = True

    if not execution_false:
        errors.append(
            "terminal execution_authorized=False absent"
        )

    if not validation_false:
        errors.append(
            "terminal validation_authorized=False absent"
        )

    if not execution_guard:
        errors.append(
            "execution authority fail-closed guard absent"
        )

    if not validation_guard:
        errors.append(
            "validation authority fail-closed guard absent"
        )

    if "VALIDATED_SOURCE" not in runtime.read_text():
        errors.append(
            "VALIDATED_SOURCE terminal absent"
        )

    return not errors, errors


def check_public_boundary():
    errors = []

    if (REPO / "experiments").exists():
        errors.append(
            "top-level experiments/ shipped"
        )

    if (
        REPO / "native/elpis-nanbeige42-host"
    ).exists():
        errors.append(
            "Nanbeige host adapter shipped"
        )

    return not errors, errors


def scan_findings():
    from collections import Counter
    findings = Counter()
    errors = []
    for path in release_paths():
        if not (path.is_file() or path.is_symlink()):
            continue
        rel = path.relative_to(REPO).as_posix()
        if path.suffix not in TEXT_SUFFIXES and path.name not in {"VERSION", "LICENSE", "CMakeLists.txt"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except (OSError, UnicodeError) as exc:
            errors.append(f"TEXT_SCAN_DECODE_FAILED: {rel}: {exc}")
            continue
        patterns = list(SECRET_PATTERNS) + [
            (pattern, "PRIVATE_PATH")
            for pattern in PRIVATE_PATH_PATTERNS
        ]
        for pattern, desc in patterns:
            kind = desc if desc == "PRIVATE_PATH" else f"SECRET:{desc}"
            for match in re.finditer(pattern, text):
                literal_digest = hashlib.sha256(match.group().encode("utf-8")).hexdigest()
                findings[(rel, kind, literal_digest)] += 1
    return findings, errors


def emitted_allowlist():
    findings, errors = scan_findings()
    if errors:
        raise ValueError("; ".join(errors))
    return [{
                "path": p, "kind": k, "sha256": h, "count": n,
                "file_sha256": digest(REPO / p),
            }
            for (p, k, h), n in sorted(findings.items())]


def check_private_data():
    findings, errors = scan_findings()
    try:
        entries = json.loads((REPO / ALLOWLIST_REL).read_text(encoding="utf-8"))
        allowlist = {}
        for entry in entries:
            key = (entry["path"], entry["kind"], entry["sha256"])
            if key in allowlist or type(entry["count"]) is not int or entry["count"] < 1:
                raise ValueError("invalid or duplicate allowlist entry")
            if type(entry.get("file_sha256")) is not str or not re.fullmatch(r"[0-9a-f]{64}", entry["file_sha256"]):
                raise ValueError("allowlist entry missing valid file_sha256")
            file_path = REPO / entry["path"]
            if not file_path.is_file() or digest(file_path) != entry["file_sha256"]:
                raise ValueError(f"allowlist containing-file digest mismatch: {entry['path']}")
            allowlist[key] = entry["count"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return False, errors + [f"INVALID ALLOWLIST: {exc}"]
    for key, count in sorted(findings.items()):
        if count > allowlist.get(key, 0):
            errors.append(f"{key[1]}: {key[0]}: not allowlisted (count {count})")
    for key, count in sorted(allowlist.items()):
        if findings.get(key, 0) < count:
            errors.append(f"STALE ALLOWLIST ENTRY: {key[0]}: {key[1]}")
    return not errors, errors


def check_artifacts():
    errors = []

    for path in release_paths():
        rel = path.relative_to(REPO)
        if ephemeral(rel):
            errors.append(f"EPHEMERAL ARTIFACT PRESENT: {rel}")
        if path.suffix in BINARY_SUFFIXES:
            errors.append(
                f"BINARY/ARTIFACT: {rel}"
            )

        if path.is_symlink():
            target = path.resolve()

            if not target.is_relative_to(REPO):
                errors.append(
                    f"SYMLINK ESCAPE: {rel}"
                )

    return not errors, errors

def _git_repository_command(args):
    return subprocess.run(
        ["git", "-C", str(REPO), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def _git_resolve_commit(ref):
    proc = _git_repository_command(
        ["rev-parse", "--verify", f"{ref}^{{commit}}"]
    )
    if proc.returncode != 0:
        return None
    value = proc.stdout.strip()
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", value):
        return None
    return value


def _git_resolve_tag_object(ref):
    proc = _git_repository_command(
        ["rev-parse", "--verify", ref]
    )
    if proc.returncode != 0:
        return None
    value = proc.stdout.strip()
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", value):
        return None
    object_type = _git_repository_command(
        ["cat-file", "-t", value]
    )
    if (
        object_type.returncode != 0
        or object_type.stdout.strip() != "tag"
    ):
        return None
    return value


def _git_is_ancestor(ancestor, descendant):
    proc = _git_repository_command(
        ["merge-base", "--is-ancestor", ancestor, descendant]
    )
    return proc.returncode == 0


def _git_is_shallow_repository():
    proc = _git_repository_command(
        ["rev-parse", "--is-shallow-repository"]
    )
    return (
        proc.returncode == 0
        and proc.stdout.strip() == "true"
    )


def check_repository_identity(
    require_git=False,
    require_tag=False,
    require_tag_at_head=False,
):
    errors = []

    if require_tag_at_head and not require_tag:
        return False, ["REPOSITORY_IDENTITY_MODE_INVALID"]

    if not (REPO / ".git").exists():
        if require_git:
            errors.append("REPOSITORY_GIT_REQUIRED")
        return not errors, errors

    try:
        identity = release_identity()
    except Exception as exc:
        return False, [f"REPOSITORY_IDENTITY_TABLE:{exc}"]

    expected_tag = f"Elpis{RELEASE_VERSION}"
    expected_tag_ref = f"refs/tags/{expected_tag}"
    tag_commit = _git_resolve_commit(expected_tag_ref)
    tag_object = _git_resolve_tag_object(expected_tag_ref)
    head_commit = _git_resolve_commit("HEAD")

    if head_commit is None:
        errors.append("HEAD_COMMIT_UNRESOLVED")

    if tag_commit is None and require_tag:
        errors.append(
            f"RELEASE_TAG_COMMIT_MISSING:{expected_tag}"
        )

    if tag_commit is not None and tag_object is None:
        errors.append(
            f"RELEASE_TAG_NOT_ANNOTATED:{expected_tag}"
        )

    for field in (
        "primitive_closure_commit",
        "base_release_commit",
    ):
        commit = identity.get(field)
        if not (
            isinstance(commit, str)
            and re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", commit)
        ):
            errors.append(
                f"RELEASE_IDENTITY_INVALID:{field}"
            )
            continue

        resolved = _git_resolve_commit(commit)
        if resolved != commit:
            if _git_is_shallow_repository():
                errors.append(
                    f"REPOSITORY_HISTORY_INCOMPLETE:"
                    f"{field}:{commit}"
                )
            else:
                errors.append(
                    f"RELEASE_IDENTITY_COMMIT_MISSING:"
                    f"{field}:{commit}"
                )
            continue

        if (
            head_commit is not None
            and not _git_is_ancestor(commit, head_commit)
        ):
            errors.append(
                f"RELEASE_IDENTITY_NOT_ANCESTOR_OF_HEAD:"
                f"{field}:{commit}:{head_commit}"
            )

        if (
            tag_commit is not None
            and not _git_is_ancestor(commit, tag_commit)
        ):
            errors.append(
                f"RELEASE_IDENTITY_NOT_ANCESTOR:"
                f"{field}:{commit}:{expected_tag}"
            )

    if tag_commit is not None and head_commit is not None:
        if require_tag_at_head and tag_commit != head_commit:
            errors.append(
                f"RELEASE_TAG_NOT_HEAD:"
                f"{expected_tag}:{tag_commit}:{head_commit}"
            )
        elif not _git_is_ancestor(tag_commit, head_commit):
            errors.append(
                f"RELEASE_TAG_NOT_ANCESTOR_OF_HEAD:"
                f"{expected_tag}:{tag_commit}:{head_commit}"
            )

    return not errors, errors



def check_repository_immutability() -> tuple[bool, list[str]]:
    gate_path = REPO / "tools" / "verify_immutable_evidence.py"
    baseline_path = REPO / "tools" / "immutable_evidence_baseline_v1.json"
    if not gate_path.is_file():
        return False, [f"MISSING_IMMUTABILITY_GATE:{gate_path.relative_to(REPO)}"]
    if not baseline_path.is_file():
        return False, [f"MISSING_IMMUTABILITY_BASELINE:{baseline_path.relative_to(REPO)}"]
    try:
        gate = runpy.run_path(str(gate_path))
        report = gate["verify"](REPO, baseline_path, check_history=(REPO / ".git").exists())
    except Exception as exc:
        return False, [f"{type(exc).__name__}: {exc}"]
    if not isinstance(report, dict) or report.get("status") != "PASS":
        return False, [f"IMMUTABILITY_REPORT_NONPASS:{report!r}"]
    return True, []

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", action="store_true")
    parser.add_argument("--candidate", action="store_true")
    parser.add_argument("--allowed-signers", type=Path, default=os.environ.get("ELPIS_ALLOWED_SIGNERS"))
    parser.add_argument("--require-origin", action="store_true")
    for flag in ("print-manifest", "emit-allowlist", "verify-candidate-repository-identity", "verify-repository-identity"):
        parser.add_argument("--" + flag, action="store_true")
    args = parser.parse_args()
    if (args.development and args.candidate) or (args.development and args.require_origin):
        parser.error("development checks do not verify release origin")
    development = "--development" in sys.argv
    if "--print-manifest" in sys.argv:
        print(MANIFEST_REL.as_posix())
        return 0
    if "--emit-allowlist" in sys.argv:
        print(json.dumps(emitted_allowlist(), indent=2) )
        return 0
    identity_flags = {
        "--verify-candidate-repository-identity",
        "--verify-repository-identity",
    } & set(sys.argv[1:])
    if len(identity_flags) > 1:
        print("[FAIL] Repository identity")
        print("  -> REPOSITORY_IDENTITY_MODE_CONFLICT")
        return 1
    if "--verify-candidate-repository-identity" in identity_flags:
        ok, errors = check_repository_identity(
            require_git=True,
        )
        print(
            f"[{'PASS' if ok else 'FAIL'}] "
            "Repository identity"
        )
        for error in errors:
            print(f"  -> {error}")
        return 0 if ok else 1
    if "--verify-repository-identity" in identity_flags:
        ok, errors = check_repository_identity(
            require_git=True,
            require_tag=True,
            require_tag_at_head=True,
        )
        print(
            f"[{'PASS' if ok else 'FAIL'}] "
            "Repository identity"
        )
        for error in errors:
            print(f"  -> {error}")
        return 0 if ok else 1
    checks = (
        *((("Elpis2 manifest", check_manifest),) if not development else ()),
        ("Package identity", check_package),
        ("Repository identity", check_repository_identity),
        ("Declared-text version", check_declared_text_version),
        ("Runtime boundary", check_runtime_boundary),
        ("Portable public boundary", check_public_boundary),
        ("Secret/private-path scan", check_private_data),
        ("Binary/artifact scan", check_artifacts),
    )

    passed = True

    if not development and not args.candidate and (args.require_origin or args.allowed_signers or tuple(map(int, RELEASE_VERSION.split('.'))) >= (2, 2, 31)):
        try:
            try:
                from tools.release_origin import verify_tag
            except ImportError:
                from release_origin import verify_tag
            tag = "Elpis" + RELEASE_VERSION
            verify_tag(REPO, _git_resolve_tag_object("refs/tags/" + tag) or "",
                       _git_resolve_commit("refs/tags/" + tag) or "", tag, args.allowed_signers)
        except (OSError, ValueError) as exc:
            print("[FAIL] Release origin: " + str(exc))
            passed = False

    for name, fn in checks:
        if name == "Repository identity" and not (REPO / ".git").exists():
            print("[N/A] Repository identity: Git metadata absent")
            continue
        ok, errors = fn()
        print(
            f"[{'PASS' if ok else 'FAIL'}] {name}"
        )

        if not ok:
            passed = False

        for error in errors:
            print(f"  -> {error}")

    if passed:
        if development:
            print(f"PASS: Elpis{RELEASE_VERSION} development checks; no release-snapshot or origin claim")
            return 0
        if args.candidate:
            print(f"PASS: Elpis{RELEASE_VERSION} candidate snapshot verified; no publication claim")
            return 0
        print(
            f"PASS: Elpis{RELEASE_VERSION} public release verified"
        )
        return 0

    print(
        f"FAIL: Elpis{RELEASE_VERSION} public release verification failed"
    )
    return 1


if __name__ == "__main__":
    immutable_ok, immutable_errors = check_repository_immutability()
    if not immutable_ok:
        print("REPOSITORY_IMMUTABILITY: FAIL", file=sys.stderr)
        for immutable_error in immutable_errors:
            print(f"  -> {immutable_error}", file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(main())
