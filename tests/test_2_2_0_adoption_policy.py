from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "manifests/ELPIS_2_2_0_ADOPTION_POLICY_R0.json"


def _policy():
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                module = "." * node.level + module
            modules.add(module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


def _ecs_all() -> set[str]:
    path = ROOT / "ECS/runtime/elpis_ecs/__init__.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in node.targets
            )
        ):
            value = ast.literal_eval(node.value)
            return set(value)
    raise AssertionError("elpis_ecs.__all__ missing")


def test_policy_identity_and_release_guard() -> None:
    policy = _policy()
    assert policy["schema"] == "elpis.release-adoption-policy.v1"
    assert policy["target_release"] == "2.2.0"
    assert policy["predecessor_release"] == "2.1.27"
    assert policy["release_materialization_authorized"] is False


def test_exact_candidate_disposition_is_internal_qualified() -> None:
    policy = _policy()
    by_id = {item["id"]: item for item in policy["candidates"]}
    assert set(by_id) == {
        "E0R3_PARTICIPATION_REFERENT",
        "ECS_TOPOLOGY_PROJECTION",
        "ECS_TOPOLOGY_ANALYSIS",
        "DURABLE_APPLICATION_LEDGER_V2",
    }
    for item in by_id.values():
        assert item["disposition"] == "SHIP_INTERNAL_QUALIFIED"
        assert item["stable_package_root_api"] is False
        assert item["runtime_admission_change"] is False
        assert (ROOT / item["source"]).is_file()
        for test in item["tests"]:
            assert (ROOT / test).is_file()


def test_e0r3_is_not_package_root_reexported() -> None:
    imports = _imported_modules(
        ROOT / "src/elpis_reference/structural_guidance/__init__.py"
    )
    assert ".e0r3_participation" not in imports


def test_topology_modules_are_not_elpis_ecs_package_root_api() -> None:
    exported = _ecs_all()
    assert "topology" not in exported
    assert "topology_analysis" not in exported


def test_durable_ledger_v2_is_not_package_root_reexported() -> None:
    imports = _imported_modules(
        ROOT
        / "components/Grid81DeterministicCapabilityApplicationExecutor/"
        "src/elpis_grid81_application_executor/__init__.py"
    )
    assert ".durable_ledger_v2" not in imports


def test_public_component_metadata_does_not_admit_candidate_modules() -> None:
    policy = _policy()
    metadata = (
        "COMPONENT_REGISTRY.json",
        "ELPIS_CANONICAL_MANIFEST.json",
        "manifests/PUBLIC_COMPONENT_REGISTRY.json",
        "manifests/PUBLIC_DEPENDENCY_GRAPH.json",
    )
    needles = (
        "e0r3_participation",
        "topology_analysis",
        "durable_ledger_v2",
    )
    for rel in metadata:
        text = (ROOT / rel).read_text(encoding="utf-8").lower()
        for needle in needles:
            assert needle not in text, (rel, needle)


def test_science_evidence_policy_is_non_runtime_and_delocalized() -> None:
    policy = _policy()["science_evidence_disposition"]
    assert policy["branches"] == [36, 37, 38, 39, 40]
    assert policy["disposition"] == "SHIP_EVIDENCE_NOT_RUNTIME_API"
    assert policy["host_specific_paths_allowed"] is False
    assert policy["historical_release_manifests_mutated"] is False
