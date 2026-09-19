from __future__ import annotations

from dataclasses import replace
import hashlib
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

import elpis_fractal_spine.isolated_provider_activation as isolated_activation
from elpis_fractal_spine.isolated_driver import (
    SupervisorPolicy,
    WheelAuthority,
    canonicalize_context,
)
from elpis_fractal_spine.isolated_driver.errors import (
    ContextError,
    LifecycleError,
    RegistryError,
)
from elpis_fractal_spine.isolated_provider_activation import (
    ActivatedIsolatedInferenceProvider,
    activate_isolated_model_provider,
)
from elpis_fractal_spine.provider_activation import InferenceDriverRegistry

from test_isolated_driver_activation import REGISTRY
from test_isolated_driver_authority import DRIVER, make_wheel


ROOT = Path(__file__).resolve().parents[1]

MODEL_PORTS = (
    ROOT
    / "components"
    / "TRMFractalSpine"
    / "registry"
    / "model_ports.toml"
)


def _synthetic_args(tmp_path, *, authority=None):
    ports = tmp_path / "ports.toml"
    ports.write_text(REGISTRY, encoding="utf-8")

    if authority is None:
        wheel_path, authority = make_wheel(tmp_path)
    else:
        wheel_path = tmp_path / "unused.whl"

    return {
        "model_id": "test-model",
        "model_ports_path": ports,
        "expected_model_ports_sha256":
            hashlib.sha256(REGISTRY.encode()).hexdigest(),
        "authority": authority,
        "wheel_path": wheel_path,
        "runtime_context": {"opaque": ["local", 1]},
        "policy": SupervisorPolicy(tmp_path),
        "expected_adapter_id": "synthetic.adapter.v1",
        "expected_admission_status": "TEST_ONLY",
        "expected_authority_class": "PROPOSAL_ONLY",
    }


def test_real_isolated_host_activation_starts_and_returns_bound_receipts(
    tmp_path,
):
    args = _synthetic_args(tmp_path)

    with activate_isolated_model_provider(**args) as activated:
        assert isinstance(
            activated,
            ActivatedIsolatedInferenceProvider,
        )

        assert activated.model_id == "test-model"
        assert activated.port_id == "synthetic.port"
        assert activated.driver_id == DRIVER
        assert activated.adapter_id == "synthetic.adapter.v1"

        assert activated.registry_sha256 == (
            hashlib.sha256(REGISTRY.encode()).hexdigest()
        )

        assert activated.authority_digest == (
            args["authority"].digest
        )

        assert activated.startup_receipt is activated.provider.receipt

        assert (
            activated.startup_receipt.authority_digest
            == args["authority"].digest
        )

        assert (
            activated.startup_receipt.context_digest
            == canonicalize_context(
                args["runtime_context"]
            ).digest
        )


def test_registry_digest_failure_occurs_before_worker_start(
    tmp_path,
    monkeypatch,
):
    args = _synthetic_args(tmp_path)
    args["expected_model_ports_sha256"] = "0" * 64

    monkeypatch.setattr(
        isolated_activation,
        "activate_isolated_provider",
        lambda **kwargs: pytest.fail(
            "worker start attempted before registry authority passed"
        ),
    )

    with pytest.raises(
        RegistryError,
        match="identity",
    ):
        activate_isolated_model_provider(**args)


def test_registry_driver_identity_is_bound_to_wheel_authority(
    tmp_path,
    monkeypatch,
):
    args = _synthetic_args(tmp_path)

    args["authority"] = replace(
        args["authority"],
        driver_id="different.driver.v1",
    )

    monkeypatch.setattr(
        isolated_activation,
        "activate_isolated_provider",
        lambda **kwargs: pytest.fail(
            "worker start attempted after driver mismatch"
        ),
    )

    with pytest.raises(
        RegistryError,
        match="identity|policy",
    ):
        activate_isolated_model_provider(**args)


@pytest.mark.parametrize(
    "field,value",
    [
        ("expected_adapter_id", "wrong.adapter.v1"),
        ("expected_admission_status", "WRONG_STATUS"),
        ("expected_authority_class", "WRITER"),
    ],
)
def test_registry_policy_expectations_fail_before_worker(
    tmp_path,
    monkeypatch,
    field,
    value,
):
    args = _synthetic_args(tmp_path)
    args[field] = value

    monkeypatch.setattr(
        isolated_activation,
        "activate_isolated_provider",
        lambda **kwargs: pytest.fail(
            "worker start attempted after policy mismatch"
        ),
    )

    with pytest.raises(
        RegistryError,
        match="identity|policy",
    ):
        activate_isolated_model_provider(**args)


def test_invalid_context_fails_before_registry_or_worker(
    tmp_path,
    monkeypatch,
):
    args = _synthetic_args(tmp_path)
    args["runtime_context"] = {"bad": object()}

    monkeypatch.setattr(
        isolated_activation,
        "bind_model_port",
        lambda **kwargs: pytest.fail(
            "registry touched after invalid context"
        ),
    )

    monkeypatch.setattr(
        isolated_activation,
        "activate_isolated_provider",
        lambda **kwargs: pytest.fail(
            "worker touched after invalid context"
        ),
    )

    with pytest.raises(ContextError):
        activate_isolated_model_provider(**args)


def test_actual_fprm_model_port_binds_without_loading_provider(
    tmp_path,
    monkeypatch,
):
    raw = MODEL_PORTS.read_bytes()

    authority = WheelAuthority(
        "fms.checkpoint.v1",
        "synthetic-fms-driver",
        "1.0",
        "elpis.inference_drivers.v1",
        "driver_pkg:factory",
        "0" * 64,
    )

    context = canonicalize_context(
        {"checkpoint_path": "opaque-local-path"}
    )

    class FakeProvider:
        def __init__(self):
            self.closed = False
            self.receipt = SimpleNamespace(
                authority_digest=authority.digest,
                context_digest=context.digest,
            )

        def close(self):
            self.closed = True

    fake = FakeProvider()

    monkeypatch.setattr(
        isolated_activation,
        "activate_isolated_provider",
        lambda **kwargs: fake,
    )

    activated = activate_isolated_model_provider(
        model_id="FPRM.Samsung_TRM",
        model_ports_path=MODEL_PORTS,
        expected_model_ports_sha256=
            hashlib.sha256(raw).hexdigest(),
        authority=authority,
        wheel_path=tmp_path / "not-opened.whl",
        runtime_context=context,
        policy=SupervisorPolicy(tmp_path),
        expected_adapter_id="fprm.sudoku-feedback.v1",
        expected_admission_status=
            "BOUNDED_R2_SUDOKU_FEEDBACK_V1",
        expected_authority_class="PROPOSAL_ONLY",
    )

    assert activated.model_id == "FPRM.Samsung_TRM"
    assert activated.port_id == "runtime.r2.fprm-samsung-trm"
    assert activated.driver_id == "fms.checkpoint.v1"
    assert activated.adapter_id == "fprm.sudoku-feedback.v1"
    assert activated.provider is fake


def test_receipt_mismatch_closes_started_worker(
    tmp_path,
    monkeypatch,
):
    args = _synthetic_args(tmp_path)

    class FakeProvider:
        def __init__(self):
            self.closed = False
            self.receipt = SimpleNamespace(
                authority_digest="f" * 64,
                context_digest="e" * 64,
            )

        def close(self):
            self.closed = True

    fake = FakeProvider()

    monkeypatch.setattr(
        isolated_activation,
        "activate_isolated_provider",
        lambda **kwargs: fake,
    )

    with pytest.raises(
        LifecycleError,
        match="receipt",
    ):
        activate_isolated_model_provider(**args)

    assert fake.closed is True


def test_isolated_host_lane_has_no_trusted_registry_or_discovery_dependency():
    source = inspect.getsource(
        isolated_activation
    )

    for forbidden in (
        "InferenceDriverRegistry",
        "plugin_discovery",
        "activate_model_provider",
        "importlib",
        "entry_points",
    ):
        assert forbidden not in source

    assert (
        InferenceDriverRegistry().registered_driver_ids()
        == ()
    )
