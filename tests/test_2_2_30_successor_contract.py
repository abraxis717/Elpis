from __future__ import annotations

import json
from pathlib import Path
import runpy
import tomllib

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.2.30"
TAG = "Elpis2.2.30"
MANIFEST_REL = "manifests/Elpis2.2.30.RELEASE_MANIFEST.json"


def test_230_current_identity_is_atomic_and_lifecycle_neutral():
    assert (ROOT / "VERSION").read_text().strip() == VERSION
    assert tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"] == VERSION
    assert f'version: "{VERSION}"' in (ROOT / "CITATION.cff").read_text()

    readme = (ROOT / "README.md").read_text()
    assert f"**Release line: Elpis{VERSION}**" in readme
    assert f"RELEASE_NOTES/Elpis{VERSION}.md" in readme
    assert (ROOT / f"RELEASE_NOTES/Elpis{VERSION}.md").is_file()
    assert (ROOT / "CHANGELOG.md").read_text().startswith(f"## Elpis{VERSION}")

    ns = runpy.run_path(str(ROOT / "tools/verify_public_release.py"))
    assert ns["RELEASE_VERSION"] == VERSION
    assert ns["RELEASE_IDENTITIES"][VERSION] == {
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    }

    manifest = ROOT / MANIFEST_REL
    if manifest.exists():
        data = json.loads(manifest.read_text())
        assert data["schema"] == "elpis.release-manifest.v3"
        assert data["version"] == VERSION
        assert data["release_name"] == TAG
        assert data["release_tag"] == TAG


def test_230_manifest_is_predeclared_write_once():
    immutable = json.loads(
        (ROOT / "tools/immutable_evidence_baseline_v1.json").read_text()
    )
    assert immutable["write_once_paths"][MANIFEST_REL] == {
        "release": TAG,
        "rule": "FIRST_COMMITTED_BLOB_IMMUTABLE",
    }

    temporality = json.loads(
        (ROOT / "tools/runtime_admission_temporality_v1.json").read_text()
    )
    expected = {
        "byte_authority": "FIRST_COMMITTED_BLOB_IMMUTABLE",
        "category": "HISTORICAL_RELEASE_SNAPSHOT",
        "locator": "/full_elpis_runtime_admission",
        "path": MANIFEST_REL,
        "qualname": "<json>",
        "release": TAG,
        "syntax": "json_key",
        "value": True,
    }
    assert expected in temporality["future_write_once_declarations"]
