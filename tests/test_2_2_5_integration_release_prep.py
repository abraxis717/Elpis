from __future__ import annotations

import json
from pathlib import Path
import runpy
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_225_release_artifacts_remain_historical():
    data = json.loads((ROOT / "manifests/Elpis2.2.5.RELEASE_MANIFEST.json").read_text())
    assert data["schema"] == "elpis.release-manifest.v2"
    assert data["package_name"] == "elpisai"
    assert data["version"] == "2.2.5"
    assert data["release_name"] == "Elpis2.2.5"
    assert data["release_tag"] == "Elpis2.2.5"

    note = ROOT / "RELEASE_NOTES/Elpis2.2.5.md"
    assert note.is_file()
    text = note.read_text()
    for marker in (
        "G5.2B capability authority",
        "G5.3B capability consumption",
        "G5.3C durable shadow application",
        "durable atomic canonical publication",
    ):
        assert marker in text

def test_225_identity_remains_ratified_but_unpublished():
    ns = runpy.run_path(str(ROOT / "tools/verify_public_release.py"))
    assert ns["RELEASE_IDENTITIES"]["2.2.5"] == {
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    }

    published = json.loads((ROOT / "PUBLISHED_RELEASES.json").read_text())
    versions = {entry["version"] for entry in published["published_releases"]}
    assert "2.2.5" not in versions

def test_224_manifest_and_release_note_remain_historical():
    data = json.loads((ROOT / "manifests/Elpis2.2.4.RELEASE_MANIFEST.json").read_text())
    assert data["version"] == "2.2.4"
    assert data["release_tag"] == "Elpis2.2.4"
    assert (ROOT / "RELEASE_NOTES/Elpis2.2.4.md").is_file()


def test_release_note_index_retains_225():
    text = (ROOT / "RELEASE_NOTES/README.md").read_text()
    assert "Elpis2.2.5.md" in text
