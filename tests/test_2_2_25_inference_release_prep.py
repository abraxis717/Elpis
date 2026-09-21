from __future__ import annotations

import json
from pathlib import Path
import runpy
import tomllib

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.2.25"
TAG = "Elpis2.2.25"
MANIFEST_REL = "manifests/Elpis2.2.25.RELEASE_MANIFEST.json"


def test_225_release_identity_is_atomic_and_ratified():
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
    assert "production DeepSeek V4.1 implementation" in text
    assert "no speculative speedup claim" in text

    assert (ROOT / "CHANGELOG.md").read_text().startswith(f"## Elpis{VERSION}")

    ns = runpy.run_path(str(ROOT / "tools/verify_public_release.py"))
    assert ns["RELEASE_VERSION"] == VERSION
    assert ns["RELEASE_IDENTITIES"][VERSION] == {
        "primitive_closure_commit":
            "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit":
            "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    }


def test_225_manifest_is_predeclared_and_not_materialized():
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


def test_225_publication_fact_is_absent_before_external_closeout():
    assertions = json.loads(
        (ROOT / "PUBLICATION_ASSERTIONS.json").read_text()
    )["publication_assertions"]
    assert not any(row.get("version") == VERSION for row in assertions)

    legacy = json.loads(
        (ROOT / "PUBLISHED_RELEASES.json").read_text()
    )["published_releases"]
    assert not any(row.get("version") == VERSION for row in legacy)

    failed = json.loads((ROOT / "FAILED_RELEASES.json").read_text())
    records = failed.get("failed_releases", failed if isinstance(failed, list) else [])
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
