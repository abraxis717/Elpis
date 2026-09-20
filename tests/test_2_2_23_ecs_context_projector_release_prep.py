from __future__ import annotations

import hashlib
import json
from pathlib import Path
import runpy
import tomllib

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.2.23"

PROTECTED_HEAD_SHA256 = {
    "ELPIS_CANONICAL_MANIFEST.json":
        "1f48892c45c29c713d45c9cacc58314235589cc4984156ad9113f705ec22ba00",
    "COMPONENT_REGISTRY.json":
        "660e30abcec3e761b29ebb81e7d5ad25195099413e127a8a7f91e466ecbbb402",
    "manifests/PUBLIC_COMPONENT_REGISTRY.json":
        "67bef85dac088c98c7d0af45508c5f2491154fd93c476c3830b6db702676ba73",
    "manifests/PUBLIC_DEPENDENCY_GRAPH.json":
        "f977e342820bf861fd49584d1c1cf4d2367677667cc5b7a1c0d24e2f80777ad4",
    "tools/verify_canonical_assembly.py":
        "02bb2ebd9e796b8b1986580ad82e85950b40161172ba4ad8039bbab600bd522a",
}

CORE = {
    "__init__.py":
        "38209b7560752dadb9fa15f9fb09d0b5aa81d60048023ea551ba407cc0217051",
    "contracts.py":
        "424741f6390e68ca4930237c9c710109f359521ee2738978e3615489f1779e6c",
    "projector.py":
        "459aa5608678f0e28e5528bb7a5f2e8ecd0183fae4e42aefce5cd0de0eca2f55",
}
ADAPTER = "d74dbe83b5c52636ff677dfc05b467ee072c5384896f966a0ddf46cc233705e0"


def _sha(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def test_223_release_identity_is_atomic_and_ratified():
    assert (ROOT / "VERSION").read_text().strip() == VERSION

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert pyproject["project"]["name"] == "elpisai"
    assert pyproject["project"]["version"] == VERSION

    assert f'version: "{VERSION}"' in (ROOT / "CITATION.cff").read_text()

    readme = (ROOT / "README.md").read_text()
    assert f"**Release line: Elpis{VERSION}**" in readme
    release = readme.split("## Release Notes", 1)[1].split(
        "## Install and quick start", 1
    )[0]
    assert release.strip().startswith(f"**Elpis{VERSION}**")
    assert f"RELEASE_NOTES/Elpis{VERSION}.md" in readme

    note = ROOT / f"RELEASE_NOTES/Elpis{VERSION}.md"
    assert note.is_file()
    assert note.read_text().count(f"## Version: v{VERSION}") == 1

    assert (ROOT / "CHANGELOG.md").read_text().startswith(
        f"## Elpis{VERSION}"
    )

    ns = runpy.run_path(str(ROOT / "tools/verify_public_release.py"))
    assert ns["RELEASE_VERSION"] == VERSION
    assert ns["RELEASE_IDENTITIES"][VERSION] == {
        "primitive_closure_commit":
            "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit":
            "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    }


def test_223_projector_bytes_and_non_authority_boundary_are_exact():
    component = ROOT / "components/ECSContextProjector"
    for name, digest in CORE.items():
        assert hashlib.sha256(
            (component / "src/elpis_ecs_context" / name).read_bytes()
        ).hexdigest() == digest

    assert hashlib.sha256(
        (component / "src/elpis_ecs_context/kernel_adapter.py").read_bytes()
    ).hexdigest() == ADAPTER

    manifest = json.loads(
        (component / "COMPONENT_MANIFEST.json").read_text()
    )
    assert manifest["component_id"] == "ECSContextProjector"
    assert manifest["qualification_disposition"] == (
        "QUALIFIED_READ_ONLY_COMPONENT"
    )
    assert manifest["runtime_admission"] is False
    assert manifest["public_registry_admission"] is False
    assert manifest["canonical_admission_authority"] is False
    assert manifest["mutation_authority"] is False
    assert manifest["execution_authority"] is False


def test_223_keeps_legacy_canonical_public_assembly_exact():
    for rel, digest in PROTECTED_HEAD_SHA256.items():
        assert _sha(rel) == digest, rel

    canonical = json.loads(
        (ROOT / "ELPIS_CANONICAL_MANIFEST.json").read_text()
    )
    registry = json.loads((ROOT / "COMPONENT_REGISTRY.json").read_text())
    public = json.loads(
        (ROOT / "manifests/PUBLIC_COMPONENT_REGISTRY.json").read_text()
    )
    graph = json.loads(
        (ROOT / "manifests/PUBLIC_DEPENDENCY_GRAPH.json").read_text()
    )

    canonical_ids = [x["component_id"] for x in canonical["components"]]
    registry_ids = [x["component_id"] for x in registry["components"]]
    public_ids = [x["component_id"] for x in public["components"]]

    assert "ECSContextProjector" not in canonical_ids
    assert "ECSContextProjector" not in registry_ids
    assert "ECSContextProjector" not in public_ids
    assert "ECSContextProjector" not in graph["nodes"]

    assert canonical["component_count"] == 17
    assert public["component_count"] == 16
    assert set(canonical_ids) - set(public_ids) == {
        "elpis_nanbeige42_host"
    }


def test_223_distribution_and_ci_bind_internal_projector():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    find = pyproject["tool"]["setuptools"]["packages"]["find"]

    assert "components/ECSContextProjector/src" in find["where"]
    assert "elpis_ecs_context*" in find["include"]

    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    attr = (
        ROOT / ".github/workflows/component-attribution.yml"
    ).read_text()

    assert "python tools/verify_ecs_context_projector.py" in ci
    assert "owner: components/ECSContextProjector" in attr
    assert "components/ECSContextProjector/src:" in attr


def test_223_manifest_path_is_predeclared_but_not_materialized():
    rel = "manifests/Elpis2.2.23.RELEASE_MANIFEST.json"
    immutable = json.loads(
        (ROOT / "tools/immutable_evidence_baseline_v1.json").read_text()
    )
    assert immutable["write_once_paths"][rel] == {
        "release": "Elpis2.2.23",
        "rule": "FIRST_COMMITTED_BLOB_IMMUTABLE",
    }

    temporality = json.loads(
        (ROOT / "tools/runtime_admission_temporality_v1.json").read_text()
    )
    expected = {
        "byte_authority": "FIRST_COMMITTED_BLOB_IMMUTABLE",
        "category": "HISTORICAL_RELEASE_SNAPSHOT",
        "locator": "/full_elpis_runtime_admission",
        "path": rel,
        "qualname": "<json>",
        "release": "Elpis2.2.23",
        "syntax": "json_key",
        "value": True,
    }
    assert expected in temporality["future_write_once_declarations"]

    manifest = ROOT / rel
    if not manifest.exists():
        # Explicit pre-seal lifecycle: the path is predeclared write-once
        # authority but has not yet been materialized.
        return

    # Once materialized, validate the selected release identity instead of
    # incorrectly demanding perpetual absence.
    data = json.loads(manifest.read_text())
    assert data["schema"] == "elpis.release-manifest.v3"
    assert data["package_name"] == "elpisai"
    assert data["version"] == VERSION
    assert data["release_name"] == f"Elpis{VERSION}"
    assert data["release_tag"] == f"Elpis{VERSION}"
