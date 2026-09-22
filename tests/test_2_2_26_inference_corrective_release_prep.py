from __future__ import annotations

import hashlib
import json
from pathlib import Path
import runpy
import tomllib

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.2.26"
TAG = "Elpis2.2.26"
MANIFEST_REL = "manifests/Elpis2.2.26.RELEASE_MANIFEST.json"


def test_226_release_identity_is_immutable_untagged_failed_hosted_main_evidence():
    manifest = ROOT / MANIFEST_REL
    assert manifest.is_file()
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == (
        "b31cf459bf2ff8d08206b22f1fe6fc6c258c5d5e6daf502129cf03d1863c5838"
    )
    data = json.loads(manifest.read_text())
    assert data["version"] == VERSION
    assert data["release_tag"] == TAG
    note = ROOT / "RELEASE_NOTES/Elpis2.2.26.md"
    assert note.is_file()
    assert note.read_text().count("## Version: v2.2.26") == 1

def test_226_manifest_write_once_lifecycle_contract():
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
    assert isinstance(data["file_count"], int)
    assert data["file_count"] > 0
    assert isinstance(data["git_tree_oid"], str)
    assert data["git_tree_oid"]
    assert data["git_object_format"] in {"sha1", "sha256"}

def test_226_publication_fact_is_absent_before_external_closeout():
    assertions = json.loads(
        (ROOT / "PUBLICATION_ASSERTIONS.json").read_text()
    )["publication_assertions"]
    assert not any(row.get("version") == VERSION for row in assertions)

    legacy = json.loads(
        (ROOT / "PUBLISHED_RELEASES.json").read_text()
    )["published_releases"]
    assert not any(row.get("version") == VERSION for row in legacy)

    failed = json.loads((ROOT / "FAILED_RELEASES.json").read_text())
    records = failed.get(
        "failed_releases",
        failed if isinstance(failed, list) else [],
    )
    assert not any(
        isinstance(row, dict) and row.get("version") == VERSION
        for row in records
    )


def test_226_native_hosted_historical_149_result_is_preserved():
    note = (ROOT / "RELEASE_NOTES/Elpis2.2.26.md").read_text()
    assert (
        "Require the complete native-backed inference + Runtime R3 locus "
        "to execute exactly 149/149 tests with zero skips, failures, or errors."
    ) in note
    assert "Native-backed Runtime R3/inference locus: 149/149 PASS, zero skips." in note

def test_226_runtime_r3_corrective_is_source_only():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    where = pyproject["tool"]["setuptools"]["packages"]["find"]["where"]
    include = pyproject["tool"]["setuptools"]["packages"]["find"]["include"]
    assert "src" in where
    assert "elpis*" in include
    assert "runtime/R3/src" not in where

    tx = (
        ROOT / "runtime/R3/src/elpis_runtime_r3/transaction.py"
    ).read_text()
    assert "_validate_request_latents" in tx
    assert "_failure_request_identity" in tx
    assert "_validated_states" in tx
    assert "receipt provenance" in tx

    assert (
        ROOT / "runtime/R3/tests/test_r3_corrective_226.py"
    ).is_file()


def test_226_preserves_225_publication_authority():
    rows = json.loads(
        (ROOT / "PUBLICATION_ASSERTIONS.json").read_text()
    )["publication_assertions"]
    row = [x for x in rows if x.get("version") == "2.2.25"]
    assert len(row) == 1
    assert row[0]["manifest_sha256"] == (
        "82d630c37bbf7f8741f91142c5d8b0f9deee39d8f8d62dfe03852450a523772d"
    )
    assert row[0]["peeled_commit"] == (
        "37fdac9edf34d421093f61a1481a73f850d18610"
    )
    assert row[0]["tag_object"] == (
        "4434f663dff5884898d4056ab4f8cf1579bf6a87"
    )
