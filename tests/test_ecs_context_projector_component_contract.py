from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "tools/verify_ecs_context_projector.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "verify_ecs_context_projector_test_module",
        VERIFIER,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ecs_context_projector_component_authority_is_self_consistent():
    result = _module().verify(ROOT)
    assert result["component_id"] == "ECSContextProjector"
    assert result["source_file_count"] >= 8


def test_ecs_context_projector_denies_admission_and_mutation_authority():
    module = _module()
    manifest = __import__("json").loads(
        (ROOT / "components/ECSContextProjector/COMPONENT_MANIFEST.json").read_text()
    )
    for key in module.DENIED:
        assert manifest[key] is False
