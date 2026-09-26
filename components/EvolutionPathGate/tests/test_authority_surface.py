from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src/elpis_evolution_path_gate"


def test_component_manifest_preserves_inactive_authority_boundaries():
    manifest = json.loads((ROOT / "COMPONENT_MANIFEST.json").read_text())
    assert manifest["component_id"] == "EvolutionPathGate"
    assert manifest["runtime_admission"] is False
    authority = manifest["authority"]
    assert authority["semantic_authority"] is False
    assert authority["token_authority"] is False
    assert authority["canonical_mutation_authority"] is False
    assert authority["parent_mutation_authority"] is False
    assert authority["path_precondition_authority"] is True
    assert authority["path_ledger_record_authority"] is True
    assert authority["rrsi_selection_gate_authority"] is True
    assert authority["child_workspace_materialization_authority"] is True


def test_source_has_no_forbidden_model_or_token_runtime_imports():
    forbidden = {
        "torch",
        "elpis_runtime_r3",
        "elpis_reference",
        "elpis.inference",
        "DarwinianMatrix",
    }
    found = set()
    for path in SRC.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.add(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module)
    for name in found:
        assert not any(name == f or name.startswith(f + ".") for f in forbidden), name
