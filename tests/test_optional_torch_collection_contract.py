from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _tree(relative: str) -> ast.Module:
    return ast.parse((ROOT / relative).read_text(encoding="utf-8"))


def _tests(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    }


def _decorated_with(tree: ast.Module, decorator_name: str) -> set[str]:
    result = set()
    for name, node in _tests(tree).items():
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id == decorator_name:
                result.add(name)
    return result


def _module_level_importorskip(tree: ast.Module) -> bool:
    for node in tree.body:
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            continue
        fn = node.value.func
        if (
            isinstance(fn, ast.Attribute)
            and isinstance(fn.value, ast.Name)
            and fn.value.id == "pytest"
            and fn.attr == "importorskip"
        ):
            return True
    return False


def test_p0_validator_ingress_torch_scope_is_exact():
    tree = _tree("tests/test_p0_validator_ingress.py")
    assert len(_tests(tree)) == 13
    assert not _module_level_importorskip(tree)
    assert _decorated_with(tree, "requires_torch") == {
        "test_authorized_failure_still_releases_exactly_one_prebound_cell",
    }


def test_projector_release_adapter_torch_scope_is_exact():
    tree = _tree("tests/test_projector_release_adapter.py")
    tests = set(_tests(tree))
    expected_torch = {
        "test_release_uses_precommitted_owner_not_live_owner_copy",
        "test_wrong_precommitted_owner_fails_before_projector_mutation",
        "test_release_binding_is_exact_state_bound",
        "test_multi_cell_release_is_rejected_instead_of_truncated",
        "test_missing_binding_for_active_resolved_support_fails_closed",
        "test_release_preserves_unrelated_clamps",
        "test_inactive_resolved_support_is_deterministic_noop",
        "test_stale_projector_transaction_still_rejected",
    }
    assert len(tests) == 10
    assert not _module_level_importorskip(tree)
    assert _decorated_with(tree, "requires_torch") == expected_torch
    assert tests - expected_torch == {
        "test_structural_rejection_cannot_reach_release_adapter",
        "test_adapter_has_no_learned_model_dependency",
    }


def test_feedback_refinement_remains_wholly_torch_dependent():
    tree = _tree("tests/test_feedback_refinement.py")
    assert len(_tests(tree)) == 7
    assert _module_level_importorskip(tree)


def test_direct_semantic_replay_dependency_cannot_be_shadowed_by_module_skip():
    tree = _tree("tests/test_direct_semantic_replay.py")
    imports = [
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "test_p0_validator_ingress"
    ]
    assert len(imports) == 1
    assert {alias.name for alias in imports[0].names} == {"rejected", "diagnose"}
    p0_tree = _tree("tests/test_p0_validator_ingress.py")
    assert not _module_level_importorskip(p0_tree)
