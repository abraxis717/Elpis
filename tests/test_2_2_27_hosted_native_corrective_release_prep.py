from __future__ import annotations

import hashlib
import json
from pathlib import Path
import runpy
import tomllib

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.2.27"
TAG = "Elpis2.2.27"
MANIFEST_REL = "manifests/Elpis2.2.27.RELEASE_MANIFEST.json"
FAILED_226_COMMIT = "61b8b12dc44e7389ba690abd1ad36f168f9080cc"
FAILED_226_MANIFEST_SHA = (
    "b31cf459bf2ff8d08206b22f1fe6fc6c258c5d5e6daf502129cf03d1863c5838"
)
FAILED_226_RUN_ID = 35732077852


def test_227_release_identity_is_immutable_published_evidence():
    manifest = ROOT / MANIFEST_REL
    assert manifest.is_file()
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == (
        "97b7e2e7ed4615c961b3fddb104871733a7eaf82b918528d45a40ef6028bedd2"
    )
    data = json.loads(manifest.read_text())
    assert data["version"] == VERSION
    assert data["release_name"] == TAG
    assert data["release_tag"] == TAG

    note = ROOT / "RELEASE_NOTES/Elpis2.2.27.md"
    assert note.is_file()
    assert note.read_text().count("## Version: v2.2.27") == 1

    rows = json.loads(
        (ROOT / "PUBLICATION_ASSERTIONS.json").read_text()
    )["publication_assertions"]
    current = [row for row in rows if row.get("version") == VERSION]
    assert len(current) == 1
    assert current[0]["peeled_commit"] == (
        "21e9b0e592d043dec5060efec2162be984360b6e"
    )
    assert current[0]["tag_object"] == (
        "7266a55363a37a5b551e512eeceda89701d5706b"
    )
def test_227_manifest_write_once_lifecycle_contract():
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

def test_227_publication_fact_is_append_only_and_exact_after_closeout():
    assertions = json.loads(
        (ROOT / "PUBLICATION_ASSERTIONS.json").read_text()
    )["publication_assertions"]

    rows = [row for row in assertions if row.get("version") == VERSION]
    assert len(rows) == 1
    row = rows[0]

    assert row["release_tag"] == TAG
    assert row["manifest_path"] == MANIFEST_REL
    assert row["manifest_sha256"] == (
        "97b7e2e7ed4615c961b3fddb104871733a7eaf82b918528d45a40ef6028bedd2"
    )
    assert row["peeled_commit"] == (
        "21e9b0e592d043dec5060efec2162be984360b6e"
    )
    assert row["peeled_object_type"] == "commit"
    assert row["tag_object"] == (
        "7266a55363a37a5b551e512eeceda89701d5706b"
    )
    assert row["tag_object_type"] == "tag"

    assert row["github_release"] == {
        "published_at": "2026-09-22T15:26:23Z",
        "release_id": 393864563,
        "repository": "abraxis717/Elpis",
        "tag_name": TAG,
    }

    expected_runs = {
        "pypi_publish": 35747353209,
        "release_event_ci": 35747353359,
        "tag_ci": 35745434226,
        "tag_component_attribution": 35745434345,
        "tag_platform_matrix": 35745434363,
        "tag_reference_runtime": 35745434339,
    }
    assert {
        name: witness["run_id"]
        for name, witness in row["github_actions"].items()
    } == expected_runs
    assert all(
        witness["conclusion"] == "success"
        and witness["head_sha"]
        == "21e9b0e592d043dec5060efec2162be984360b6e"
        for witness in row["github_actions"].values()
    )

    files = {x["filename"]: x for x in row["pypi"]["files"]}
    assert row["pypi"]["project"] == "elpisai"
    assert row["pypi"]["version"] == VERSION
    assert files["elpisai-2.2.27-py3-none-any.whl"]["sha256"] == (
        "1e511c0baff24c77b7ef554e89543a4259071df3897186c220213c99e9974870"
    )
    assert files["elpisai-2.2.27.tar.gz"]["sha256"] == (
        "54d558b79348e66600b8444ba282766838fa60089498fb7f9dba1afb63530ba4"
    )
    assert all(not x["yanked"] for x in files.values())

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


def test_227_preserves_untagged_failed_226_exactly():
    manifest = ROOT / "manifests/Elpis2.2.26.RELEASE_MANIFEST.json"
    assert manifest.is_file()
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == FAILED_226_MANIFEST_SHA
    data = json.loads(manifest.read_text())
    assert data["version"] == "2.2.26"
    assert data["release_tag"] == "Elpis2.2.26"

    assertions = json.loads(
        (ROOT / "PUBLICATION_ASSERTIONS.json").read_text()
    )["publication_assertions"]
    assert not any(row.get("version") == "2.2.26" for row in assertions)
    legacy = json.loads(
        (ROOT / "PUBLISHED_RELEASES.json").read_text()
    )["published_releases"]
    assert not any(row.get("version") == "2.2.26" for row in legacy)
    failed = json.loads((ROOT / "FAILED_RELEASES.json").read_text())
    assert not any(row.get("version") == "2.2.26"
                   for row in failed.get("failed_releases", []))


def test_227_native_workflow_historical_result_and_runner_fix_are_preserved():
    note = (ROOT / "RELEASE_NOTES/Elpis2.2.27.md").read_text()
    assert "RUNNER_TEMP" in note
    assert "GITHUB_ENV" in note

    workflow = (ROOT / ".github/workflows/inference-native-r0.yml").read_text()
    contract = (ROOT / "tests/test_inference_native_hosted_ci.py").read_text()
    assert "${{ runner.temp }}" not in workflow
    assert "RUNNER_TEMP" in workflow
    assert "GITHUB_ENV" in workflow
    assert "NATIVE_PROVIDER_CORE_7_OF_7_PASS" in workflow
    assert "NATIVE_INFERENCE_LOCUS_EXACT_SET_PASS" in workflow
    assert "tools/verify_inference_native_locus.py --check" in workflow
    assert "FORBIDDEN_JOB_LEVEL_RUNNER_CONTEXT" in contract

def test_227_runtime_and_packaging_authority_are_unchanged():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    where = pyproject["tool"]["setuptools"]["packages"]["find"]["where"]
    include = pyproject["tool"]["setuptools"]["packages"]["find"]["include"]
    assert "src" in where
    assert "elpis*" in include
    assert "runtime/R3/src" not in where
    assert (ROOT / "runtime/R3/tests/test_r3_corrective_226.py").is_file()


def test_227_preserves_225_publication_authority():
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
