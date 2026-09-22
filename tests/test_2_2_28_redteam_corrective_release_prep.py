from __future__ import annotations

import json
from pathlib import Path
import runpy
import tomllib

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.2.28"
TAG = "Elpis2.2.28"
MANIFEST_REL = "manifests/Elpis2.2.28.RELEASE_MANIFEST.json"


def test_228_active_successor_identity_is_atomic_and_manifest_lifecycle():
    assert (ROOT / "VERSION").read_text().strip() == VERSION
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert pyproject["project"]["name"] == "elpisai"
    assert pyproject["project"]["version"] == VERSION
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
    if not manifest.exists():
        return
    data = json.loads(manifest.read_text())
    assert data["schema"] == "elpis.release-manifest.v3"
    assert data["package_name"] == "elpisai"
    assert data["version"] == VERSION
    assert data["release_name"] == TAG
    assert data["release_tag"] == TAG
    assert data["publication_policy"] == "elpis.publication-membership.v2"
    assert data["tree_digest_algorithm"] == "elpis.publication-tree.sha256.v1"
    assert data["full_elpis_runtime_admission"] is True
    assert data["execution_authorized"] is False
    assert data["generated_source_executed"] is False
    assert data["experiments_shipped"] is False
    assert data["output_authority_granted"] == 0
    assert data["request_guidance_gate_default"] is False
    assert data["validation_authority_propagated"] is False
    assert isinstance(data["publication_tree_sha256"], str)
    assert len(data["publication_tree_sha256"]) == 64
    assert isinstance(data["file_count"], int) and data["file_count"] > 0

def test_228_manifest_is_predeclared_write_once_only():
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


def test_228_native_is_required_by_orchestrator_and_publication_authority():
    from tools import publication_assertions_v2 as pub
    from tools import release_orchestrator as orch

    intent = {"version": VERSION}
    assert "main_inference_native" in orch.action_specs("MAIN_HOSTED_GREEN", intent)
    assert "tag_inference_native" in orch.action_specs("TAG_HOSTED_GREEN", intent)
    assert pub.required_actions(TAG)["tag_inference_native"] == (
        "inference-native-r0",
        "push",
    )


def test_228_publication_fact_is_absent_before_external_closeout():
    assertions = json.loads(
        (ROOT / "PUBLICATION_ASSERTIONS.json").read_text()
    )["publication_assertions"]
    assert not any(row.get("version") == VERSION for row in assertions)
