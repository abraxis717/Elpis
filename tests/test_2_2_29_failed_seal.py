from __future__ import annotations
from tools import release_git

import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FAILED_VERSION = "2.2.29"
FAILED_TAG = "Elpis2.2.29"
FAILED_COMMIT = "f4022927b40e720acdca9775d7de123a511add99"
FAILED_PARENT = "ba39ff1d869e5edc545d7713506ca442676bf75b"
MANIFEST_REL = "manifests/Elpis2.2.29.RELEASE_MANIFEST.json"
MANIFEST_SHA256 = "19b8e7aeb1589f2ec230290db41ad70171cb3c8430fa619dc8b900e990eab885"


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return release_git.run(
        ROOT,
        *args,
        text=True,
    )


def test_229_failed_seal_is_preserved_exactly():
    manifest = ROOT / MANIFEST_REL
    assert manifest.is_file()
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == MANIFEST_SHA256

    data = json.loads(manifest.read_text())
    assert data["version"] == FAILED_VERSION
    assert data["release_tag"] == FAILED_TAG

    assert _git("cat-file", "-e", FAILED_COMMIT + "^{commit}").returncode == 0
    parent = _git("rev-parse", FAILED_COMMIT + "^").stdout.strip()
    assert parent == FAILED_PARENT

    names = _git(
        "diff-tree", "--no-commit-id", "--name-only", "-r", FAILED_COMMIT
    ).stdout.splitlines()
    assert names == [MANIFEST_REL]

    raw = _git("show", FAILED_COMMIT + ":" + MANIFEST_REL)
    assert raw.returncode == 0
    assert hashlib.sha256(raw.stdout.encode()).hexdigest() == MANIFEST_SHA256


def test_229_remains_untagged_and_unpublished():
    assert _git("tag", "--list", FAILED_TAG).stdout.strip() == ""

    for rel, key in (
        ("PUBLICATION_ASSERTIONS.json", "publication_assertions"),
        ("PUBLISHED_RELEASES.json", "published_releases"),
        ("FAILED_RELEASES.json", "failed_releases"),
    ):
        rows = json.loads((ROOT / rel).read_text())[key]
        assert not any(
            isinstance(row, dict) and row.get("version") == FAILED_VERSION
            for row in rows
        )
