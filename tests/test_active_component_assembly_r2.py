from __future__ import annotations

import hashlib
import json
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "tools/verify_active_component_assembly.py"
RETIRED = "elpis_nanbeige42_host"

LEGACY = {
    "ELPIS_CANONICAL_MANIFEST.json":
        "1f48892c45c29c713d45c9cacc58314235589cc4984156ad9113f705ec22ba00",
    "COMPONENT_REGISTRY.json":
        "660e30abcec3e761b29ebb81e7d5ad25195099413e127a8a7f91e466ecbbb402",
    "manifests/PUBLIC_COMPONENT_REGISTRY.json":
        "67bef85dac088c98c7d0af45508c5f2491154fd93c476c3830b6db702676ba73",
    "manifests/PUBLIC_DEPENDENCY_GRAPH.json":
        "f977e342820bf861fd49584d1c1cf4d2367677667cc5b7a1c0d24e2f80777ad4",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_active_r2_verifier_is_green():
    verify = runpy.run_path(str(VERIFY))["verify"]
    assert verify(ROOT) == []


def test_active_r2_is_exact_16_16_without_canonical_only_entry():
    selector = json.loads(
        (ROOT / "manifests/ACTIVE_COMPONENT_ASSEMBLY.json").read_text()
    )
    canonical = json.loads((ROOT / selector["canonical_manifest"]).read_text())
    registry = json.loads((ROOT / selector["component_registry"]).read_text())
    public = json.loads((ROOT / selector["public_registry"]).read_text())

    can = {x["component_id"] for x in canonical["components"]}
    reg = {x["component_id"] for x in registry["components"]}
    pub = {x["component_id"] for x in public["components"]}

    assert canonical["component_count"] == 16
    assert registry["component_count"] == 16
    assert public["component_count"] == 16
    assert can == reg == pub
    assert selector["canonical_only_component_ids"] == []
    assert RETIRED not in can | reg | pub


def test_legacy_r1_bytes_are_untouched():
    for rel, expected in LEGACY.items():
        assert _sha(ROOT / rel) == expected, rel


def test_retired_host_paths_are_absent():
    assert not (ROOT / "components/elpis_nanbeige42_host").exists()
    assert not (ROOT / "native/elpis-nanbeige42-host").exists()


def test_projector_is_not_opportunistically_admitted():
    selector = json.loads(
        (ROOT / "manifests/ACTIVE_COMPONENT_ASSEMBLY.json").read_text()
    )
    canonical = json.loads((ROOT / selector["canonical_manifest"]).read_text())
    public = json.loads((ROOT / selector["public_registry"]).read_text())

    can = {x["component_id"] for x in canonical["components"]}
    pub = {x["component_id"] for x in public["components"]}

    assert "ECSContextProjector" not in can
    assert "ECSContextProjector" not in pub
