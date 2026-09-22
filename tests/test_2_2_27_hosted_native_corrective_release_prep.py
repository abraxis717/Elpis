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


def test_227_release_identity_is_atomic_and_prepublication():
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
    assert FAILED_226_COMMIT in text
    assert FAILED_226_MANIFEST_SHA in text
    assert str(FAILED_226_RUN_ID) in text
    assert "RUNNER_TEMP" in text
    assert "GITHUB_ENV" in text

    assert (ROOT / "CHANGELOG.md").read_text().startswith(f"## Elpis{VERSION}")
    ns = runpy.run_path(str(ROOT / "tools/verify_public_release.py"))
    assert ns["RELEASE_VERSION"] == VERSION
    assert ns["RELEASE_IDENTITIES"][VERSION] == {
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    }


def test_227_manifest_is_predeclared_and_not_materialized():
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


def test_227_native_workflow_uses_runner_runtime_environment_not_job_expression():
    workflow = (ROOT / ".github/workflows/inference-native-r0.yml").read_text()
    contract = (ROOT / "tests/test_inference_native_hosted_ci.py").read_text()
    assert "${{ runner.temp }}" not in workflow
    assert "RUNNER_TEMP" in workflow
    assert "GITHUB_ENV" in workflow
    assert 'ELPIS_INFERENCE_WORKSPACE="${RUNNER_TEMP}/elpis-inference-native"' in workflow
    assert "NATIVE_INFERENCE_LOCUS_149_OF_149_PASS" in workflow
    assert "NATIVE_PROVIDER_CORE_7_OF_7_PASS" in workflow
    assert "149" in contract
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
