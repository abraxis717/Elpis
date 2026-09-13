from __future__ import annotations

import json
from pathlib import Path
import runpy
import shutil


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "tools" / "verify_canonical_assembly.py"


def _load_verifier():
    return runpy.run_path(str(VERIFIER))["verify"]


def _write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def _fixture(tmp_path: Path) -> Path:
    dst = tmp_path / "repo"
    dst.mkdir()

    for rel in (
        "VERSION",
        "ELPIS_CANONICAL_MANIFEST.json",
        "COMPONENT_REGISTRY.json",
        "manifests/PUBLIC_COMPONENT_REGISTRY.json",
        "manifests/PUBLIC_DEPENDENCY_GRAPH.json",
    ):
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)

    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    dist = Path(f"manifests/Elpis{version}.DISTRIBUTION_MANIFEST.json")
    relman = Path(f"manifests/Elpis{version}.RELEASE_MANIFEST.json")
    authority = dist if (ROOT / dist).is_file() else relman
    target = dst / authority
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / authority, target)

    public = json.loads(
        (ROOT / "manifests/PUBLIC_COMPONENT_REGISTRY.json").read_text(
            encoding="utf-8"
        )
    )
    for item in public["components"]:
        rel = Path(item["public_path"]) / "COMPONENT_MANIFEST.json"
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)

    return dst


def test_current_assembly_recomputes_cleanly(tmp_path: Path) -> None:
    repo = _fixture(tmp_path)
    assert _load_verifier()(repo) == []


def test_component_count_is_derived_not_magic_pinned(tmp_path: Path) -> None:
    repo = _fixture(tmp_path)
    path = repo / "manifests/PUBLIC_COMPONENT_REGISTRY.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["component_count"] = value["component_count"] + 1
    _write_json(path, value)

    assert "PUBLIC_COMPONENT_COUNT" in _load_verifier()(repo)


def test_component_manifest_byte_mutation_breaks_release_pin(
    tmp_path: Path,
) -> None:
    repo = _fixture(tmp_path)
    path = repo / "components/Grid81/COMPONENT_MANIFEST.json"
    path.write_bytes(path.read_bytes() + b"\n")

    errors = _load_verifier()(repo)
    assert "RELEASE_MANIFEST_DIGEST:Grid81_Canonical_Substrate" in errors


def test_public_dependency_mutation_is_caught_by_manifest_and_graph(
    tmp_path: Path,
) -> None:
    repo = _fixture(tmp_path)
    path = repo / "manifests/PUBLIC_COMPONENT_REGISTRY.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    for item in value["components"]:
        if item["component_id"] == "G53c_Capability_Application_Executor":
            item["dependencies"] = []
            break
    _write_json(path, value)

    errors = _load_verifier()(repo)
    assert "MANIFEST_DEPENDENCY_BINDING:G53c_Capability_Application_Executor" in errors
    assert "REGISTRY_DEPENDENCY_BINDING:G53c_Capability_Application_Executor" in errors
    assert "GRAPH_DEPENDENCY_EDGES" in errors


def test_graph_edge_mutation_is_caught_by_recomputation(tmp_path: Path) -> None:
    repo = _fixture(tmp_path)
    path = repo / "manifests/PUBLIC_DEPENDENCY_GRAPH.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["edges"] = value["edges"][:-1]
    _write_json(path, value)

    assert "GRAPH_DEPENDENCY_EDGES" in _load_verifier()(repo)


def test_legacy_digest_pair_must_still_agree(tmp_path: Path) -> None:
    repo = _fixture(tmp_path)
    path = repo / "ELPIS_CANONICAL_MANIFEST.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["components"][0]["manifest_digest"] = "0" * 64
    _write_json(path, value)

    assert "LEGACY_DIGEST_BINDING:HACF_R3" in _load_verifier()(repo)


def test_canonical_only_host_must_remain_unshipped(tmp_path: Path) -> None:
    repo = _fixture(tmp_path)
    path = repo / "components/elpis_nanbeige42_host"
    path.mkdir(parents=True)

    errors = _load_verifier()(repo)
    assert (
        "CANONICAL_ONLY_PATH_SHIPPED:components/elpis_nanbeige42_host"
        in errors
    )
