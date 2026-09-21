from __future__ import annotations

import hashlib
import json
from pathlib import Path
import runpy
import tomllib

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.2.24"
TAG = "Elpis2.2.24"
MANIFEST_REL = "manifests/Elpis2.2.24.RELEASE_MANIFEST.json"


def test_224_release_identity_is_immutable_published_history():
    manifest = ROOT / MANIFEST_REL
    assert manifest.is_file()
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == (
        "7a7d4c340678fd97f0a33967a803cc7fdc5645d1f6056f51f07632a91195abdf"
    )

    data = json.loads(manifest.read_text())
    assert data["schema"] == "elpis.release-manifest.v3"
    assert data["version"] == VERSION
    assert data["release_tag"] == TAG

    rows = json.loads(
        (ROOT / "PUBLICATION_ASSERTIONS.json").read_text()
    )["publication_assertions"]
    row = [x for x in rows if x.get("version") == VERSION]
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

    note = ROOT / "RELEASE_NOTES/Elpis2.2.24.md"
    assert note.is_file()
    assert note.read_text().count("## Version: v2.2.24") == 1

    ns = runpy.run_path(str(ROOT / "tools/verify_public_release.py"))
    assert ns["RELEASE_IDENTITIES"][VERSION] == {
        "primitive_closure_commit":
            "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit":
            "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    }

def test_224_active_assembly_is_r2_16_16_without_canonical_only_gap():
    selector = json.loads(
        (ROOT / "manifests/ACTIVE_COMPONENT_ASSEMBLY.json").read_text()
    )
    canonical = json.loads(
        (ROOT / selector["canonical_manifest"]).read_text()
    )
    registry = json.loads(
        (ROOT / selector["component_registry"]).read_text()
    )
    public = json.loads(
        (ROOT / selector["public_registry"]).read_text()
    )

    can_ids = {x["component_id"] for x in canonical["components"]}
    reg_ids = {x["component_id"] for x in registry["components"]}
    pub_ids = {x["component_id"] for x in public["components"]}

    assert selector["active_assembly"] == "ELPIS_CANONICAL_ASSEMBLY_R2"
    assert canonical["component_count"] == 16
    assert registry["component_count"] == 16
    assert public["component_count"] == 16
    assert selector["canonical_only_component_ids"] == []
    assert can_ids == reg_ids == pub_ids


def test_224_release_guard_ci_is_lifecycle_aware():
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "python tools/run_mutation_suite_ci.py" in ci
    assert "      - run: python tools/mutation_suite.py\\n" not in ci

    wrapper = (ROOT / "tools/run_mutation_suite_ci.py").read_text()
    assert "MUTATION_SUITE_REQUIRES_UNPUBLISHED_SUCCESSOR_VERSION:" in wrapper
    assert "returncode == 2" in wrapper


def test_224_manifest_write_once_lifecycle_contract():
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
        # Valid preseal state: authority is declared but first committed bytes
        # have not yet been materialized.
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


def test_224_publication_fact_is_append_only_and_exact_after_closeout():
    assertions = json.loads(
        (ROOT / "PUBLICATION_ASSERTIONS.json").read_text()
    )["publication_assertions"]

    rows = [row for row in assertions if row.get("version") == VERSION]
    assert len(rows) == 1
    row = rows[0]

    assert row["release_tag"] == TAG
    assert row["manifest_path"] == MANIFEST_REL
    assert row["manifest_sha256"] == (
        "7a7d4c340678fd97f0a33967a803cc7fdc5645d1f6056f51f07632a91195abdf"
    )
    assert row["peeled_commit"] == (
        "f75ea4fed361aa0aba9538d396375ea413ab6744"
    )
    assert row["peeled_object_type"] == "commit"
    assert row["tag_object"] == (
        "9d38a35cd9de0ed61bbb098b8bb11800d776ea5e"
    )
    assert row["tag_object_type"] == "tag"

    assert row["github_release"] == {
        "published_at": "2026-09-20T21:41:34Z",
        "release_id": 392583798,
        "repository": "abraxis717/Elpis",
        "tag_name": TAG,
    }

    assert row["github_actions"] == {
        "pypi_publish": {
            "conclusion": "success",
            "event": "release",
            "head_sha": "f75ea4fed361aa0aba9538d396375ea413ab6744",
            "run_id": 35539483836,
            "workflow": "pypi-publish",
        },
        "release_event_ci": {
            "conclusion": "success",
            "event": "release",
            "head_sha": "f75ea4fed361aa0aba9538d396375ea413ab6744",
            "run_id": 35539483844,
            "workflow": "CI",
        },
        "tag_ci": {
            "conclusion": "success",
            "event": "push",
            "head_sha": "f75ea4fed361aa0aba9538d396375ea413ab6744",
            "run_id": 35539076848,
            "workflow": "CI",
        },
        "tag_component_attribution": {
            "conclusion": "success",
            "event": "push",
            "head_sha": "f75ea4fed361aa0aba9538d396375ea413ab6744",
            "run_id": 35539076852,
            "workflow": "Component attribution",
        },
        "tag_platform_matrix": {
            "conclusion": "success",
            "event": "push",
            "head_sha": "f75ea4fed361aa0aba9538d396375ea413ab6744",
            "run_id": 35539076838,
            "workflow": "platform-matrix",
        },
        "tag_reference_runtime": {
            "conclusion": "success",
            "event": "push",
            "head_sha": "f75ea4fed361aa0aba9538d396375ea413ab6744",
            "run_id": 35539076874,
            "workflow": "reference-runtime",
        },
    }

    assert row["pypi"] == {
        "project": "elpisai",
        "version": VERSION,
        "files": [
            {
                "filename": "elpisai-2.2.24-py3-none-any.whl",
                "packagetype": "bdist_wheel",
                "sha256": (
                    "9d3ca0a9e99b1d06470a3c175898fd08c8d63bc76e4cb2eb00ea25b7f6c9bf10"
                ),
                "upload_time_iso_8601": "2026-09-20T21:43:56.105091Z",
                "yanked": False,
            },
            {
                "filename": "elpisai-2.2.24.tar.gz",
                "packagetype": "sdist",
                "sha256": (
                    "966daeb10f03a1a1d01e008e83ae25d106c0d4c4a4436d3ccea7b1465b0907b2"
                ),
                "upload_time_iso_8601": "2026-09-20T21:43:58.295074Z",
                "yanked": False,
            },
        ],
    }

    legacy = json.loads(
        (ROOT / "PUBLISHED_RELEASES.json").read_text()
    )["published_releases"]
    assert not any(row.get("version") == VERSION for row in legacy)


def test_223_sealed_manifest_and_publication_assertion_remain_exact():
    rel = "manifests/Elpis2.2.23.RELEASE_MANIFEST.json"
    manifest = ROOT / rel
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == (
        "e680bf31b56431e6f9122bc5029ef8d8e64a2fd0a8c10fed398a68939d567a1f"
    )

    rows = json.loads(
        (ROOT / "PUBLICATION_ASSERTIONS.json").read_text()
    )["publication_assertions"]
    row = [x for x in rows if x.get("version") == "2.2.23"]
    assert len(row) == 1
    assert row[0]["manifest_sha256"] == (
        "e680bf31b56431e6f9122bc5029ef8d8e64a2fd0a8c10fed398a68939d567a1f"
    )
