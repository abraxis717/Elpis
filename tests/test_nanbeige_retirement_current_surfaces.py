from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RETIRED = "elpis_nanbeige42_host"


def test_current_active_selector_has_no_canonical_only_gap():
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

    canonical_ids = {x["component_id"] for x in canonical["components"]}
    registry_ids = {x["component_id"] for x in registry["components"]}
    public_ids = {x["component_id"] for x in public["components"]}

    assert canonical["component_count"] == 16
    assert registry["component_count"] == 16
    assert public["component_count"] == 16
    assert canonical_ids == registry_ids == public_ids
    assert selector["canonical_only_component_ids"] == []
    assert selector["retired_component_ids"] == [RETIRED]
    assert RETIRED not in canonical_ids


def test_current_component_map_reports_r2_without_retired_host():
    cp = subprocess.run(
        [sys.executable, str(ROOT / "tools/print_component_map.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert "Assembly: ELPIS_CANONICAL_ASSEMBLY_R2" in cp.stdout
    assert "Canonical: 16" in cp.stdout
    assert "Public: 16" in cp.stdout
    assert "nanbeige" not in cp.stdout.lower()


def test_current_ci_uses_active_r2_gate_and_map():
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "python tools/verify_active_component_assembly.py" in ci
    assert "python tools/print_component_map.py" in ci
    assert "python tools/verify_canonical_assembly.py" not in ci


def test_current_docs_do_not_advertise_nanbeige():
    for rel in ("README.md", "docs/COMPONENTS.md", "native/README.md"):
        text = (ROOT / rel).read_text(encoding="utf-8").lower()
        assert "nanbeige" not in text, rel


def test_legacy_r1_is_still_explicitly_historical_not_current():
    selector = json.loads(
        (ROOT / "manifests/ACTIVE_COMPONENT_ASSEMBLY.json").read_text()
    )
    legacy = selector["legacy_r1"]
    assert legacy["status"] == "HISTORICAL_CLOSED_AUTHORITY"
    assert legacy["canonical_manifest"] == "ELPIS_CANONICAL_MANIFEST.json"
    assert legacy["component_registry"] == "COMPONENT_REGISTRY.json"
