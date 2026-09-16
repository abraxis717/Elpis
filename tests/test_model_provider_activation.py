from __future__ import annotations

import inspect
import sys
import tomllib
from pathlib import Path

import pytest

from elpis_fractal_spine.provider_activation import (
    DriverNotRegisteredError,
    DuplicateDriverRegistrationError,
    InferenceDriverRegistry,
    InvalidInferenceProviderError,
    activate_model_provider,
)

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "components/TRMFractalSpine/registry/models.toml"
MODEL_PORTS = ROOT / "components/TRMFractalSpine/registry/model_ports.toml"
MODEL_ID = "FPRM.Samsung_TRM"


class _DudProvider:
    def acquire(self, request):
        return object()

    def release(self, binding):
        return None

    def execute(self, request, *, residency=None):
        return object()


def _fprm_port():
    data = tomllib.loads(MODEL_PORTS.read_text(encoding="utf-8"))
    rows = [row for row in data["port"] if row["model_id"] == MODEL_ID]
    assert len(rows) == 1
    return data, rows[0]


def test_model_registry_contains_one_bounded_fprm_identity():
    data = tomllib.loads(MODELS.read_text(encoding="utf-8"))
    rows = [row for row in data["model"] if row["model_id"] == MODEL_ID]
    assert len(rows) == 1
    row = rows[0]
    assert row["residency_tier"] == "HOT"
    assert row["authority_class"] == "PROPOSAL_ONLY"
    assert row["checkpoint_sha256"] == (
        "6daec5f499d115beb14e23f3a9cf56d1166b99c1ccd36b185a19ea5dfec9a137"
    )
    assert row["deterministic_mode"] == "BOUNDED_R2_SUDOKU_FEEDBACK_V1"
    assert "loader_import" not in row
    assert not Path(row["path"]).is_absolute()


def test_model_ports_contains_one_disabled_on_demand_fprm_port():
    data, row = _fprm_port()
    assert data["network_allowed"] is False
    assert data["remote_code_allowed"] is False
    assert row["enabled"] is False
    assert row["load_policy"] == "ON_DEMAND"
    assert row["driver_id"] == "fms.checkpoint.v1"
    assert row["adapter_id"] == "fprm.sudoku-feedback.v1"
    assert row["admission_status"] == "BOUNDED_R2_SUDOKU_FEEDBACK_V1"
    assert row["network_allowed"] is False
    assert row["remote_code_allowed"] is False


def test_historical_ports_remain_never_and_fprm_is_only_on_demand():
    data = tomllib.loads(MODEL_PORTS.read_text(encoding="utf-8"))
    on_demand = []
    for row in data["port"]:
        if row["model_id"] == MODEL_ID:
            assert row["load_policy"] == "ON_DEMAND"
            on_demand.append(row["port_id"])
        else:
            assert row["load_policy"] == "NEVER"
    assert on_demand == ["runtime.r2.fprm-samsung-trm"]


def test_registry_has_no_builtin_driver_or_arbitrary_toml_import():
    registry = InferenceDriverRegistry()
    assert registry.registered_driver_ids() == ()
    source = inspect.getsource(
        sys.modules["elpis_fractal_spine.provider_activation"]
    ).lower()
    assert "importlib" not in source
    assert "entry_points" not in source
    _, row = _fprm_port()
    assert "loader_import" not in row


def test_missing_driver_fails_closed_before_factory_or_inference():
    registry = InferenceDriverRegistry()
    with pytest.raises(DriverNotRegisteredError):
        activate_model_provider(
            model_id=MODEL_ID,
            model_ports_path=MODEL_PORTS,
            driver_registry=registry,
            runtime_context={
                "checkpoint_path": "/must/not/be/opened",
                "bridge_library": "/must/not/be/loaded",
            },
        )


def test_duplicate_driver_registration_fails_closed():
    registry = InferenceDriverRegistry()
    registry.register("fms.checkpoint.v1", lambda context: _DudProvider())
    with pytest.raises(DuplicateDriverRegistrationError):
        registry.register(
            "fms.checkpoint.v1",
            lambda context: _DudProvider(),
        )


def test_invalid_provider_surface_fails_closed():
    registry = InferenceDriverRegistry()
    registry.register("fms.checkpoint.v1", lambda context: object())
    with pytest.raises(InvalidInferenceProviderError):
        activate_model_provider(
            model_id=MODEL_ID,
            model_ports_path=MODEL_PORTS,
            driver_registry=registry,
            runtime_context={},
        )


def test_dud_driver_activation_adds_no_torch_modules():
    before = frozenset(
        name for name in sys.modules
        if name == "torch" or name.startswith("torch.")
    )
    registry = InferenceDriverRegistry()
    registry.register("fms.checkpoint.v1", lambda context: _DudProvider())
    activated = activate_model_provider(
        model_id=MODEL_ID,
        model_ports_path=MODEL_PORTS,
        driver_registry=registry,
        runtime_context={"opaque": "local-only"},
    )
    after = frozenset(
        name for name in sys.modules
        if name == "torch" or name.startswith("torch.")
    )
    assert after == before
    assert activated.driver_id == "fms.checkpoint.v1"
    assert activated.adapter_id == "fprm.sudoku-feedback.v1"
    assert isinstance(activated.provider, _DudProvider)


def test_runtime_context_is_read_only_to_driver_factory():
    observed = {}

    def factory(context):
        observed.update(context)
        with pytest.raises(TypeError):
            context["new"] = "forbidden"
        return _DudProvider()

    registry = InferenceDriverRegistry()
    registry.register("fms.checkpoint.v1", factory)
    activate_model_provider(
        model_id=MODEL_ID,
        model_ports_path=MODEL_PORTS,
        driver_registry=registry,
        runtime_context={"checkpoint_path": "opaque-local-path"},
    )
    assert observed == {"checkpoint_path": "opaque-local-path"}
