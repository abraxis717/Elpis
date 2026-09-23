from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.2.27"
TAG = "Elpis2.2.27"
MANIFEST_REL = "manifests/Elpis2.2.27.RELEASE_MANIFEST.json"
FAILED_226_MANIFEST_SHA = (
    "b31cf459bf2ff8d08206b22f1fe6fc6c258c5d5e6daf502129cf03d1863c5838"
)


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


def test_227_publication_fact_is_append_only_and_exact_after_closeout():
    assertions = json.loads(
        (ROOT / "PUBLICATION_ASSERTIONS.json").read_text()
    )["publication_assertions"]
    rows = [row for row in assertions if row.get("version") == VERSION]
    assert len(rows) == 1
    row = rows[0]
    assert row["manifest_sha256"] == (
        "97b7e2e7ed4615c961b3fddb104871733a7eaf82b918528d45a40ef6028bedd2"
    )
    assert row["peeled_commit"] == (
        "21e9b0e592d043dec5060efec2162be984360b6e"
    )
    assert row["tag_object"] == (
        "7266a55363a37a5b551e512eeceda89701d5706b"
    )


def test_227_preserves_untagged_failed_226_exactly():
    manifest = ROOT / "manifests/Elpis2.2.26.RELEASE_MANIFEST.json"
    assert manifest.is_file()
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == FAILED_226_MANIFEST_SHA
    data = json.loads(manifest.read_text())
    assert data["version"] == "2.2.26"
    assert data["release_tag"] == "Elpis2.2.26"


def test_227_native_workflow_historical_result_and_runner_fix_are_preserved():
    note = (ROOT / "RELEASE_NOTES/Elpis2.2.27.md").read_text()
    assert "RUNNER_TEMP" in note
    assert "GITHUB_ENV" in note

    workflow = (ROOT / ".github/workflows/inference-native-r0.yml").read_text()
    runner = (ROOT / "tools/run_inference_native_locus.py").read_text()
    contract = (ROOT / "tests/test_inference_native_hosted_ci.py").read_text()

    assert "${{ runner.temp }}" not in workflow
    assert "RUNNER_TEMP" in workflow
    assert "GITHUB_ENV" in workflow
    assert "tools/verify_inference_native_locus.py --check" in workflow
    assert workflow.count("python tools/run_inference_native_locus.py") == 2
    assert "--section provider" in workflow
    assert "--section locus" in workflow
    assert "PASS_NATIVE_EXECUTED_EXACT_SET" in runner
    assert "FORBIDDEN_JOB_LEVEL_RUNNER_CONTEXT" in contract


def test_227_runtime_and_packaging_authority_are_unchanged():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    where = pyproject["tool"]["setuptools"]["packages"]["find"]["where"]
    include = pyproject["tool"]["setuptools"]["packages"]["find"]["include"]
    assert "src" in where
    assert "elpis*" in include
    assert "runtime/R3/src" not in where
    assert (ROOT / "runtime/R3/tests/test_r3_corrective_226.py").is_file()
