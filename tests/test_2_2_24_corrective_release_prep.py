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


def test_224_release_identity_is_atomic_and_ratified():
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
    assert "nanbeige" not in section.lower()

    note = ROOT / f"RELEASE_NOTES/Elpis{VERSION}.md"
    assert note.is_file()
    note_text = note.read_text()
    assert note_text.count(f"## Version: v{VERSION}") == 1
    assert "nanbeige" not in note_text.lower()

    assert (ROOT / "CHANGELOG.md").read_text().startswith(f"## Elpis{VERSION}")

    ns = runpy.run_path(str(ROOT / "tools/verify_public_release.py"))
    assert ns["RELEASE_VERSION"] == VERSION
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


def test_224_manifest_is_predeclared_and_not_materialized():
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


def test_224_does_not_predeclare_publication_fact():
    assertions = json.loads(
        (ROOT / "PUBLICATION_ASSERTIONS.json").read_text()
    )["publication_assertions"]
    assert not any(row.get("version") == VERSION for row in assertions)

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
