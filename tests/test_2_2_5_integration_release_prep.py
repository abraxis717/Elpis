from __future__ import annotations

import json
from pathlib import Path
import runpy
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_225_current_release_metadata_is_coherent():
    assert (ROOT / "VERSION").read_text().strip() == "2.2.5"
    assert tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"] == "2.2.5"
    assert 'version: "2.2.5"' in (ROOT / "CITATION.cff").read_text()
    readme = (ROOT / "README.md").read_text()
    assert "**Release line: Elpis2.2.5**" in readme
    assert "RELEASE_NOTES/Elpis2.2.5.md" in readme
    assert "capability authority -> consumption compiler -> durable application" in readme
    text = (ROOT / "RELEASE_NOTES/Elpis2.2.5.md").read_text()
    for marker in ("G5.2B capability authority", "G5.3B capability consumption", "G5.3C durable shadow application", "durable atomic canonical publication"):
        assert marker in text


def test_225_identity_is_ratified_and_publication_registry_is_pending():
    ns = runpy.run_path(str(ROOT / "tools/verify_public_release.py"))
    assert ns["RELEASE_VERSION"] == "2.2.5"
    assert ns["release_identity"]() == {
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    }

    manifest = ROOT / "manifests/Elpis2.2.5.RELEASE_MANIFEST.json"
    if manifest.exists():
        data = json.loads(manifest.read_text())
        assert data["schema"] == "elpis.release-manifest.v2"
        assert data["package_name"] == "elpisai"
        assert data["version"] == "2.2.5"
        assert data["release_name"] == "Elpis2.2.5"
        assert data["release_tag"] == "Elpis2.2.5"
        paths = {entry["path"] for entry in data["files"]}
        for required in (
            "RELEASE_NOTES/Elpis2.2.5.md",
            "tests/test_2_2_5_integration_release_prep.py",
            "tests/test_grid81_authority_consumption_runtime_integration.py",
            "tests/test_grid81_candidate_publication_runtime_integration.py",
            "tests/test_grid81_promotion_candidate_runtime_integration.py",
        ):
            assert required in paths

    published = json.loads((ROOT / "PUBLISHED_RELEASES.json").read_text())
    assert "2.2.5" not in json.dumps(published, sort_keys=True)


def test_224_manifest_and_release_note_remain_historical():
    data = json.loads((ROOT / "manifests/Elpis2.2.4.RELEASE_MANIFEST.json").read_text())
    assert data["version"] == "2.2.4"
    assert data["release_tag"] == "Elpis2.2.4"
    assert (ROOT / "RELEASE_NOTES/Elpis2.2.4.md").is_file()


def test_release_note_index_tracks_225():
    text = (ROOT / "RELEASE_NOTES/README.md").read_text()
    assert "Current: [`Elpis2.2.5.md`](Elpis2.2.5.md)" in text
    for version in ("2.2.5", "2.2.4", "2.2.3", "2.2.2", "2.2.1", "2.2.0"):
        assert f"Elpis{version}.md" in text
