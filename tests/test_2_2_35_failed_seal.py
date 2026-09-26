from __future__ import annotations
from tools import release_git

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILED_VERSION = "2.2.35"
FAILED_TAG = "Elpis2.2.35"
FAILED_CANDIDATE = "4eeaf8e5b20fc468012f98812b3cec31ab8bd85a"
FAILED_MANIFEST_FIRST_COMMIT = "abe9011aa8b445c7df113188162652cc745f2de2"
MANIFEST_REL = "manifests/Elpis2.2.35.RELEASE_MANIFEST.json"
MANIFEST_SHA256 = "4a6450c922220bb7be57d29337163c1c43876aa98f9a7ee45efa08738ba6adbb"


def _git(*args: str):
    return release_git.run(ROOT, *args, text=True)


def test_235_failed_hosted_candidate_is_preserved_exactly():
    manifest = ROOT / MANIFEST_REL
    assert manifest.is_file()
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == MANIFEST_SHA256

    data = json.loads(manifest.read_text())
    assert data["version"] == FAILED_VERSION
    assert data["release_tag"] == FAILED_TAG

    assert _git("cat-file", "-e", FAILED_CANDIDATE + "^{commit}").returncode == 0
    assert _git("cat-file", "-e", FAILED_MANIFEST_FIRST_COMMIT + "^{commit}").returncode == 0

    history = [
        x
        for x in _git("log", "--format=%H", "--reverse", "--", MANIFEST_REL).stdout.splitlines()
        if x
    ]
    assert history
    assert history[0] == FAILED_MANIFEST_FIRST_COMMIT

    first = _git("show", FAILED_MANIFEST_FIRST_COMMIT + ":" + MANIFEST_REL)
    assert first.returncode == 0
    assert hashlib.sha256(first.stdout.encode()).hexdigest() == MANIFEST_SHA256

    current = _git("show", FAILED_CANDIDATE + ":" + MANIFEST_REL)
    assert current.returncode == 0
    assert hashlib.sha256(current.stdout.encode()).hexdigest() == MANIFEST_SHA256


def test_235_remains_untagged_and_unpublished():
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
