from __future__ import annotations

import json
import hashlib
from pathlib import Path
import runpy
import shutil
import subprocess
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "tools" / "verify_canonical_assembly.py"


def _load_verifier():
    return runpy.run_path(str(VERIFIER))["verify"]


def _write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def _fixture(tmp_path: Path, *, compact: bool = False) -> Path:
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
    if not compact and (ROOT / authority).is_file():
        target = dst / authority
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / authority, target)
    else:
        # Current pre-seal qualification must not create a current manifest.
        # This tiny synthetic successor only supplies assembly byte pins.
        (dst / "VERSION").write_text("9.9.9\n", encoding="utf-8")
        authority = Path("manifests/Elpis9.9.9.RELEASE_MANIFEST.json")

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

    if compact:
        _seal_compact_fixture(dst)
    elif not (dst / authority).exists():
        _write_json(dst / authority, {
            "schema": "elpis.release-manifest.v2",
            "files": [
                {"path": path.relative_to(dst).as_posix(),
                 "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                for path in sorted(dst.rglob("COMPONENT_MANIFEST.json"))
            ],
        })

    return dst


def _seal_compact_fixture(repo: Path) -> Path:
    # A synthetic future fixture, never a seal of the current release.
    version = (repo / "VERSION").read_text().strip()
    assert version == "9.9.9"
    rel = f"manifests/Elpis{version}.RELEASE_MANIFEST.json"
    historical = json.loads((ROOT / "manifests/Elpis2.2.5.RELEASE_MANIFEST.json").read_text())
    data = {k: v for k, v in historical.items() if k not in {"files", "file_count"}}
    data.update(schema="elpis.release-manifest.v3", version=version,
                release_name=f"Elpis{version}", release_tag=f"Elpis{version}")
    compact = runpy.run_path(str(ROOT / "tools/release_tree_digest.py"))
    data.update(compact["build_record"](repo, rel))
    _write_json(repo / rel, data)
    return repo / rel


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


def test_compact_assembly_authenticates_without_file_pins(tmp_path: Path) -> None:
    repo = _fixture(tmp_path, compact=True)
    assert _load_verifier()(repo) == []
    data = json.loads((repo / "manifests/Elpis9.9.9.RELEASE_MANIFEST.json").read_text())
    assert "files" not in data


@pytest.mark.parametrize("mutation", ["component_byte", "registry_byte", "add", "delete", "rename"])
def test_compact_assembly_rejects_tree_mutation(tmp_path: Path, mutation: str) -> None:
    repo = _fixture(tmp_path, compact=True)
    assert _load_verifier()(repo) == []
    component = repo / "components/Grid81/COMPONENT_MANIFEST.json"
    if mutation == "component_byte":
        component.write_bytes(component.read_bytes() + b" ")
    elif mutation == "registry_byte":
        path = repo / "manifests/PUBLIC_COMPONENT_REGISTRY.json"
        path.write_bytes(path.read_bytes() + b" ")
    elif mutation == "add":
        (repo / "added.txt").write_text("new publication member")
    elif mutation == "delete":
        component.unlink()
    else:
        component.rename(component.with_name("renamed.json"))
    assert "RELEASE_AUTHORITY:V3_PUBLICATION_TREE_SHA256_MISMATCH" in _load_verifier()(repo)


def test_compact_assembly_still_recomputes_structure(tmp_path: Path) -> None:
    repo = _fixture(tmp_path, compact=True)
    path = repo / "manifests/PUBLIC_DEPENDENCY_GRAPH.json"
    graph = json.loads(path.read_text())
    graph["edges"] = graph["edges"][:-1]
    _write_json(path, graph)
    _seal_compact_fixture(repo)
    assert _load_verifier()(repo) == ["GRAPH_DEPENDENCY_EDGES"]


@pytest.mark.parametrize("field,value,marker", [
    ("publication_tree_sha256", "0" * 64, "V3_PUBLICATION_TREE_SHA256_MISMATCH"),
    ("publication_policy", "unrecognized", "V3_PUBLICATION_POLICY_INVALID"),
    ("version", "9.9.8", "V3_RELEASE_SELECTION_MISMATCH"),
    ("release_tag", "Elpis9.9.8", "V3_RELEASE_SELECTION_MISMATCH"),
    ("files", [], "V3_AUTHORITY_FIELDS_INVALID"),
])
def test_compact_assembly_rejects_invalid_authority(tmp_path, field, value, marker):
    repo = _fixture(tmp_path, compact=True)
    path = repo / "manifests/Elpis9.9.9.RELEASE_MANIFEST.json"
    data = json.loads(path.read_text())
    data[field] = value
    _write_json(path, data)
    assert f"RELEASE_AUTHORITY:{marker}" in _load_verifier()(repo)


def test_compact_assembly_rejects_ephemeral_contamination(tmp_path: Path) -> None:
    repo = _fixture(tmp_path, compact=True)
    (repo / "build").mkdir()
    assert "RELEASE_AUTHORITY:EPHEMERAL ARTIFACT PRESENT:build" in _load_verifier()(repo)


def test_compact_assembly_rejects_distribution_schema_substitution(tmp_path: Path) -> None:
    repo = _fixture(tmp_path, compact=True)
    authority = repo / "manifests/Elpis9.9.9.RELEASE_MANIFEST.json"
    authority.rename(repo / "manifests/Elpis9.9.9.DISTRIBUTION_MANIFEST.json")
    assert "RELEASE_AUTHORITY:V3_RELEASE_SELECTION_MISMATCH" in _load_verifier()(repo)


def test_compact_assembly_does_not_authenticate_untracked_component(tmp_path: Path) -> None:
    repo = _fixture(tmp_path, compact=True)

    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args]).decode().strip()

    git("init", "-q")
    git("config", "user.name", "Assembly Fixture")
    git("config", "user.email", "assembly@example.invalid")
    git("add", ".")
    git("commit", "-qm", "fixture")
    authority = _seal_compact_fixture(repo)
    assert _load_verifier()(repo) == []
    component = "components/Grid81/COMPONENT_MANIFEST.json"
    git("rm", "--cached", component)
    git("commit", "-qm", "omit component from publication")
    _seal_compact_fixture(repo)
    # The tree authority is valid for the smaller tracked publication, but the
    # untracked physical component must not acquire authentication from it.
    compact = runpy.run_path(str(ROOT / "tools/release_tree_digest.py"))
    assert compact["verify_record"](repo, authority.relative_to(repo).as_posix(),
                                    json.loads(authority.read_text())) == []
    assert _load_verifier()(repo) == ["RELEASE_MANIFEST_PIN_MISSING:Grid81_Canonical_Substrate"]


def test_compact_byte_mutation_reaches_aggregate_control(tmp_path: Path) -> None:
    repo = _fixture(tmp_path, compact=True)
    check = _load_verifier()
    component = repo / "components/Grid81/COMPONENT_MANIFEST.json"
    component.write_bytes(component.read_bytes() + b" ")
    assert "RELEASE_AUTHORITY:V3_PUBLICATION_TREE_SHA256_MISMATCH" in check(repo)
    # Disable only the aggregate verifier in this isolated namespace. A valid
    # JSON whitespace mutation must now pass, demonstrating the guard's role.
    compact = runpy.run_path(str(ROOT / "tools/release_tree_digest.py"))
    compact["verify_record"] = lambda *args: []
    check.__globals__["runpy"] = SimpleNamespace(run_path=lambda path: compact)
    assert check(repo) == []
