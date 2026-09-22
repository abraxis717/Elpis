from __future__ import annotations

import json
from pathlib import Path
import runpy
import tomllib

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.2.26"
TAG = "Elpis2.2.26"
MANIFEST_REL = "manifests/Elpis2.2.26.RELEASE_MANIFEST.json"


def test_226_release_identity_is_atomic_and_prepublication():
    assert (ROOT / "VERSION").read_text().strip() == VERSION

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert pyproject["project"]["name"] == "elpisai"
    assert pyproject["project"]["version"] == VERSION
    assert f'version: "{VERSION}"' in (ROOT / "CITATION.cff").read_text()

    readme = (ROOT / "README.md").read_text()
    assert f"**Release line: Elpis{VERSION}**" in readme
    section = readme.split("## Release Notes", 1)[1].split(
        "## Install and quick start", 1
    )[0]
    assert section.strip().startswith(f"**Elpis{VERSION}**")
    assert f"RELEASE_NOTES/Elpis{VERSION}.md" in readme

    note = ROOT / f"RELEASE_NOTES/Elpis{VERSION}.md"
    assert note.is_file()
    text = note.read_text()
    assert text.count(f"## Version: v{VERSION}") == 1
    assert "149/149 PASS" in text
    assert "deterministic internal provenance validation" in text
    assert "Runtime R3 remains source-only" in text

    assert (ROOT / "CHANGELOG.md").read_text().startswith(f"## Elpis{VERSION}")

    ns = runpy.run_path(str(ROOT / "tools/verify_public_release.py"))
    assert ns["RELEASE_VERSION"] == VERSION
    assert ns["RELEASE_IDENTITIES"][VERSION] == {
        "primitive_closure_commit":
            "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit":
            "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    }


def test_226_manifest_is_predeclared_and_not_materialized():
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
    assert not (ROOT / MANIFEST_REL).exists()


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


def test_226_native_hosted_contract_is_exact_149_and_zero_skip():
    workflow = (
        ROOT / ".github/workflows/inference-native-r0.yml"
    ).read_text()
    contract = (
        ROOT / "tests/test_inference_native_hosted_ci.py"
    ).read_text()
    expected = "expected = {'tests': 149, 'failures': 0, 'errors': 0, 'skipped': 0}"
    assert expected in workflow
    assert "NATIVE_INFERENCE_LOCUS_149_OF_149_PASS" in workflow
    assert "ELPIS_FMS_FILE_LIBRARY" in workflow
    assert "ELPIS_INFERENCE_WORKSPACE" in workflow
    assert "149" in contract
    assert "132" not in workflow
    assert "132" not in contract


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
