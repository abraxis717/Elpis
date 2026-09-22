from __future__ import annotations

import json
from pathlib import Path
import runpy
import tomllib

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.2.25"
TAG = "Elpis2.2.25"
MANIFEST_REL = "manifests/Elpis2.2.25.RELEASE_MANIFEST.json"


def test_225_release_identity_is_immutable_published_history():
    manifest = ROOT / MANIFEST_REL
    assert manifest.is_file()
    data = json.loads(manifest.read_text())
    assert data["schema"] == "elpis.release-manifest.v3"
    assert data["version"] == VERSION
    assert data["release_tag"] == TAG

    assertions = json.loads(
        (ROOT / "PUBLICATION_ASSERTIONS.json").read_text()
    )["publication_assertions"]
    rows = [row for row in assertions if row.get("version") == VERSION]
    assert len(rows) == 1
    row = rows[0]
    assert row["manifest_sha256"] == (
        "82d630c37bbf7f8741f91142c5d8b0f9deee39d8f8d62dfe03852450a523772d"
    )
    assert row["peeled_commit"] == (
        "37fdac9edf34d421093f61a1481a73f850d18610"
    )
    assert row["tag_object"] == (
        "4434f663dff5884898d4056ab4f8cf1579bf6a87"
    )

    note = ROOT / "RELEASE_NOTES/Elpis2.2.25.md"
    assert note.is_file()
    assert note.read_text().count("## Version: v2.2.25") == 1

def test_225_manifest_write_once_lifecycle_contract():
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
    assert isinstance(data["git_tree_oid"], str)
    assert data["git_tree_oid"]
    assert data["git_object_format"] in {"sha1", "sha256"}
    assert isinstance(data["file_count"], int)
    assert data["file_count"] > 0


def test_225_publication_fact_is_append_only_and_exact_after_closeout():
    assertions = json.loads(
        (ROOT / "PUBLICATION_ASSERTIONS.json").read_text()
    )["publication_assertions"]

    rows = [row for row in assertions if row.get("version") == VERSION]
    assert len(rows) == 1
    row = rows[0]

    assert row["release_tag"] == TAG
    assert row["manifest_path"] == MANIFEST_REL
    assert row["manifest_sha256"] == (
        "82d630c37bbf7f8741f91142c5d8b0f9deee39d8f8d62dfe03852450a523772d"
    )
    assert row["peeled_commit"] == (
        "37fdac9edf34d421093f61a1481a73f850d18610"
    )
    assert row["peeled_object_type"] == "commit"
    assert row["tag_object"] == (
        "4434f663dff5884898d4056ab4f8cf1579bf6a87"
    )
    assert row["tag_object_type"] == "tag"

    assert row["github_release"] == {
        "published_at": "2026-09-21T20:06:12Z",
        "release_id": 393259406,
        "repository": "abraxis717/Elpis",
        "tag_name": TAG,
    }

    expected_runs = {
        "pypi_publish": 35648963280,
        "release_event_ci": 35648963275,
        "tag_ci": 35648118816,
        "tag_component_attribution": 35648117607,
        "tag_platform_matrix": 35648118808,
        "tag_reference_runtime": 35648118463,
    }
    assert {
        name: witness["run_id"]
        for name, witness in row["github_actions"].items()
    } == expected_runs
    assert all(
        witness["conclusion"] == "success"
        and witness["head_sha"]
        == "37fdac9edf34d421093f61a1481a73f850d18610"
        for witness in row["github_actions"].values()
    )

    files = {x["filename"]: x for x in row["pypi"]["files"]}
    assert row["pypi"]["project"] == "elpisai"
    assert row["pypi"]["version"] == VERSION
    assert files["elpisai-2.2.25-py3-none-any.whl"]["sha256"] == (
        "882017fa6913fb9c851f876446827b5eaf746b8252ba8b640754f5a775967820"
    )
    assert files["elpisai-2.2.25.tar.gz"]["sha256"] == (
        "45ec3d11ce9d1c46975230bafd9941ef8fabb34a21a326dcf61cb1ca7148a1f6"
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


def test_225_packaging_boundary_ships_inference_not_runtime_r3():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    where = pyproject["tool"]["setuptools"]["packages"]["find"]["where"]
    include = pyproject["tool"]["setuptools"]["packages"]["find"]["include"]
    assert "src" in where
    assert "elpis*" in include
    assert "runtime/R3/src" not in where
    assert (ROOT / "src/elpis/inference/__init__.py").is_file()
    assert (ROOT / "runtime/R3/src/elpis_runtime_r3/__init__.py").is_file()


def test_225_preserves_224_publication_authority():
    rows = json.loads(
        (ROOT / "PUBLICATION_ASSERTIONS.json").read_text()
    )["publication_assertions"]
    row = [x for x in rows if x.get("version") == "2.2.24"]
    assert len(row) == 1
    assert row[0]["manifest_sha256"] == (
        "7a7d4c340678fd97f0a33967a803cc7fdc5645d1f6056f51f07632a91195abdf"
    )
    assert row[0]["peeled_commit"] == (
        "f75ea4fed361aa0aba9538d396375ea413ab6744"
    )
    assert row[0]["tag_object"] == (
        "9d38a35cd9de0ed61bbb098b8bb11800d776ea5e"
    )
