from __future__ import annotations
import json, tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_224_release_artifacts_remain_preserved():
    assert (ROOT/"RELEASE_NOTES/Elpis2.2.4.md").is_file()
    data=json.loads((ROOT/"manifests/Elpis2.2.4.RELEASE_MANIFEST.json").read_text())
    assert data["version"]=="2.2.4"
    assert data["release_tag"]=="Elpis2.2.4"

def test_repaired_pypi_workflow_contract_is_current():
    text=(ROOT/".github/workflows/pypi-publish.yaml").read_text()
    for marker in (
        "  release:",
        "    types: [published]",
        "  workflow_dispatch:",
        "      release_tag:",
        "        required: true",
        "RELEASE_TAG: ${{ github.event.release.tag_name || inputs.release_tag }}",
        "ref: ${{ env.RELEASE_TAG }}",
        'test "Elpis$(cat VERSION)" = "${RELEASE_TAG}"',
        'test "$(git rev-parse HEAD)" = "$(git rev-list -n 1 "${RELEASE_TAG}")"',
        'python tools/verify_public_release.py --verify-repository-identity',
        'git archive --format=tar "${RELEASE_TAG}"',
        "      id-token: write",
        "pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33",
    ):
        assert marker in text, marker
    assert 'git rev-list -n 1 "${{ github.event.release.tag_name }})' not in text

def test_224_manifest_binds_contract_corrective():
    data=json.loads((ROOT/"manifests/Elpis2.2.4.RELEASE_MANIFEST.json").read_text())
    assert data["version"]=="2.2.4"
    assert data["release_tag"]=="Elpis2.2.4"
    paths={x["path"] for x in data["files"]}
    for path in (
        ".github/workflows/pypi-publish.yaml",
        "tests/test_pypi_trusted_publishing_contract.py",
        "manifests/Elpis2.2.3.RELEASE_MANIFEST.json",
        "RELEASE_NOTES/Elpis2.2.4.md",
    ):
        assert path in paths
