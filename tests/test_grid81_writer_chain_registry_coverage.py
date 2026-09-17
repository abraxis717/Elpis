from __future__ import annotations

import json
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "manifests/GRID81_WRITER_CHAIN_SUCCESSOR_REGISTRY_R0.json"
GRAPH = ROOT / "manifests/GRID81_WRITER_CHAIN_SUCCESSOR_DEPENDENCY_GRAPH_R0.json"
PUBLIC = ROOT / "manifests/PUBLIC_COMPONENT_REGISTRY.json"
VERIFY = ROOT / "tools/verify_grid81_writer_successor_assembly.py"

SUCCESSOR_IDS = {
    "Grid81_Canonical_Promotion_Authority",
    "Grid81_Canonical_Candidate_Constructor",
    "Grid81_Atomic_Canonical_Publisher",
}
EXPECTED_ORDER = [
    "G53e_Canonical_Promotion_Planner",
    "Grid81_Canonical_Promotion_Authority",
    "Grid81_Canonical_Candidate_Constructor",
    "Grid81_Atomic_Canonical_Publisher",
    "Grid81_Canonical_Substrate",
]


def test_writer_chain_registry_covers_every_flow_node_with_exact_record_binding():
    ns = runpy.run_path(str(VERIFY))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    public = json.loads(PUBLIC.read_text(encoding="utf-8"))

    assert registry["component_count"] == 3
    assert {item["component_id"] for item in registry["components"]} == SUCCESSOR_IDS
    assert registry["writer_chain_order"] == EXPECTED_ORDER
    assert registry["writer_chain_node_count"] == len(EXPECTED_ORDER)
    assert registry["writer_chain_node_binding_hash_contract"] == (
        "sha256(canonical-json(bound registry record))"
    )

    bindings = registry["writer_chain_nodes"]
    assert [item["node_id"] for item in bindings] == EXPECTED_ORDER
    assert len({item["node_id"] for item in bindings}) == len(EXPECTED_ORDER)

    successor_by_id = {
        item["component_id"]: item for item in registry["components"]
    }
    public_by_id = {
        item["component_id"]: item for item in public["components"]
    }

    for item in bindings:
        node_id = item["node_id"]
        assert item["component_id"] == node_id
        if node_id in SUCCESSOR_IDS:
            assert item["binding_source"] == "SUCCESSOR_COMPONENT_REGISTRY"
            bound = successor_by_id[node_id]
        else:
            assert item["binding_source"] == "PUBLIC_COMPONENT_REGISTRY"
            bound = public_by_id[node_id]
        expected = ns["_sha_bytes"](ns["_canonical_bytes"](bound))
        assert item["binding_sha256"] == expected

    assert ns["verify"](ROOT) == []


def test_dependency_graph_binds_expanded_registry_self_hash():
    ns = runpy.run_path(str(VERIFY))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))

    assert registry["registry_self_hash"] == ns["_self_hash"](
        registry, "registry_self_hash"
    )
    assert graph["registry_self_hash"] == registry["registry_self_hash"]
    assert graph["graph_self_hash"] == ns["_self_hash"](graph, "graph_self_hash")


def test_legacy_public_registry_membership_is_not_expanded():
    public = json.loads(PUBLIC.read_text(encoding="utf-8"))
    assert public["component_count"] == 16
    public_ids = {item["component_id"] for item in public["components"]}
    assert SUCCESSOR_IDS.isdisjoint(public_ids)
    assert "G53e_Canonical_Promotion_Planner" in public_ids
    assert "Grid81_Canonical_Substrate" in public_ids
