from __future__ import annotations

import json
from pathlib import Path
import runpy
import tomllib

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.2.30"
TAG = "Elpis2.2.30"
MANIFEST_REL = "manifests/Elpis2.2.30.RELEASE_MANIFEST.json"


def test_230_closed_identity_is_immutable_history():
    import hashlib
    data = json.loads((ROOT / MANIFEST_REL).read_text())
    assert hashlib.sha256((ROOT / MANIFEST_REL).read_bytes()).hexdigest() == "dad01d27de0e5acc478b7aa6d010ac1138b927dfc07c54cfea3a115ad04b92a6"
    assert data["schema"] == "elpis.release-manifest.v3"
    assert data["version"] == VERSION and data["release_tag"] == TAG
    records = json.loads((ROOT / "PUBLICATION_ASSERTIONS.json").read_text())["publication_assertions"]
    row, = [r for r in records if r["version"] == VERSION]
    assert row["tag_object"] == "049c72e92c53ac927d2bef1c0b4d52a0ce1df1f6"
    assert row["peeled_commit"] == "912921b78f9766494e137f9f472b59fc4fc53b17"
    assert (ROOT / f"RELEASE_NOTES/{TAG}.md").is_file()
    ns = runpy.run_path(str(ROOT / "tools/verify_public_release.py"))
    assert ns["RELEASE_IDENTITIES"][VERSION] == {
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    }


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
