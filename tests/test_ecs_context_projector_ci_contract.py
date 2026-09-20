from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_root_ci_enforces_ecs_context_projector_authority():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert workflow.count("python tools/verify_ecs_context_projector.py") == 1
    assert "Qualify ECSContextProjector read-only component" in workflow


def test_component_attribution_owns_complete_ecs_context_projector_suite():
    workflow = (
        ROOT / ".github/workflows/component-attribution.yml"
    ).read_text(encoding="utf-8")

    assert workflow.count("owner: components/ECSContextProjector") == 1
    assert (
        'command: "python tools/verify_ecs_context_projector.py && '
        'python -m pytest -q -p no:cacheprovider '
        'components/ECSContextProjector/tests '
        'tests/test_ecs_context_projector_component_contract.py"'
        in workflow
    )
    assert "components/ECSContextProjector/src:" in workflow
    assert workflow.count("owner: components/ECSContextProjector") == workflow.count(
        "components/ECSContextProjector/src:"
    )
