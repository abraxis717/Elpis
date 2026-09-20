from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_PACKAGES = {
    "elpis_p0", "elpis_fractal_spine", "elpis_grid81_semantics",
    "elpis_grid81_typed", "elpis_grid81_groups", "elpis_grid81_adjudication",
    "elpis_grid81_capability_authority", "elpis_grid81_consumption_compiler",
    "elpis_grid81_application_executor", "elpis_grid81_promotion_planner",
    "c_numpy_cortex", "elpis_header", "elpis_runtime_r0", "elpis_runtime_r1",
    "elpis_ecs_context",
}

def test_active_component_assembly_matches_public_registry_exactly():
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

    canonical_ids = {c["component_id"] for c in canonical["components"]}
    registry_ids = {c["component_id"] for c in registry["components"]}
    public_ids = {c["component_id"] for c in public["components"]}

    assert canonical["component_count"] == 16
    assert registry["component_count"] == 16
    assert public["component_count"] == 16
    assert canonical_ids == registry_ids == public_ids
    assert selector["canonical_only_component_ids"] == []
    assert "elpis_nanbeige42_host" not in canonical_ids
    assert not (ROOT / "native/elpis-nanbeige42-host").exists()
    assert not (ROOT / "components/elpis_nanbeige42_host").exists()


def test_active_component_assembly_verifier_is_green():
    cp = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/verify_active_component_assembly.py"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stdout + cp.stderr

def test_package_discovery_declares_all_nested_source_roots():
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    find = config["tool"]["setuptools"]["packages"]["find"]
    includes = set(find["include"])
    assert {name + "*" for name in EXPECTED_PACKAGES} <= includes
    assert "runtime/R0/src" in find["where"]
    assert "runtime/R1/src" in find["where"]
    assert "components/ECSContextProjector/src" in find["where"]
    assert "components/Pipeline/P0ControlProtocol/src" in find["where"]
    assert "native/elpis-header/src" in find["where"]

def test_ci_has_complete_top_level_suite_and_read_only_assembly_gate():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "python -m pytest -q -p no:cacheprovider tests/" in workflow
    assert "python tools/verify_active_component_assembly.py" in workflow
    assert "python tools/print_component_map.py" in workflow
    assert "python tools/qualify_allocator_budget.py" in workflow


def test_distribution_identity_is_elpisai_without_import_or_cli_rename():
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    project = config["project"]
    find = config["tool"]["setuptools"]["packages"]["find"]
    assert project["name"] == "elpisai"
    assert project["scripts"]["elpis"] == "elpis_reference.cli:main"
    assert "elpis*" in find["include"]
    assert "elpis_reference*" in find["include"]

def test_reference_runtime_uses_elpisai_distribution_metadata():
    workflow = (ROOT / ".github/workflows/reference-runtime.yml").read_text()
    assert 'version("elpisai")' in workflow
    assert 'version("elpis")' not in workflow

