from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from elpis_fractal_spine.provider_activation import InferenceDriverRegistry
import elpis_fractal_spine.plugin_discovery as discovery


class _FakeEntryPoint:
    def __init__(self, *, name, group, value, loaded):
        self.name = name
        self.group = group
        self.value = value
        self._loaded = loaded
        self.load_calls = 0

    def load(self):
        self.load_calls += 1
        return self._loaded


class _FakeDistribution:
    def __init__(self, *, name, version, entry_points):
        self.metadata = {"Name": name}
        self.version = version
        self.entry_points = tuple(entry_points)


class _DudProvider:
    def acquire(self, request):
        return object()

    def release(self, binding):
        return None

    def execute(self, request, *, residency=None):
        return object()


def _factory(context):
    return _DudProvider()


def _dist(name, version, *eps):
    return _FakeDistribution(
        name=name,
        version=version,
        entry_points=eps,
    )


def test_module_import_performs_no_discovery_or_plugin_load(monkeypatch):
    calls = {"distributions": 0}

    def forbidden_distributions():
        calls["distributions"] += 1
        raise AssertionError("plugin discovery ran during module import")

    monkeypatch.setattr(
        discovery.metadata,
        "distributions",
        forbidden_distributions,
    )
    importlib.reload(discovery)
    assert calls["distributions"] == 0


def test_metadata_candidates_are_exact_sorted_and_do_not_load(monkeypatch):
    target_b = _FakeEntryPoint(
        name="fms.checkpoint.v1",
        group=discovery.ENTRY_POINT_GROUP,
        value="pkg_b:factory",
        loaded=_factory,
    )
    target_a = _FakeEntryPoint(
        name="fms.checkpoint.v1",
        group=discovery.ENTRY_POINT_GROUP,
        value="pkg_a:factory",
        loaded=_factory,
    )
    unrelated = _FakeEntryPoint(
        name="unrelated.driver",
        group=discovery.ENTRY_POINT_GROUP,
        value="unrelated:factory",
        loaded=_factory,
    )
    other_group = _FakeEntryPoint(
        name="fms.checkpoint.v1",
        group="other.group",
        value="other:factory",
        loaded=_factory,
    )
    monkeypatch.setattr(
        discovery.metadata,
        "distributions",
        lambda: (
            _dist("ZuluDriver", "2.0", target_b, unrelated),
            _dist("AlphaDriver", "1.0", target_a, other_group),
        ),
    )

    candidates = discovery.installed_inference_driver_candidates(
        "fms.checkpoint.v1"
    )
    assert tuple(c.distribution_name for c in candidates) == (
        "AlphaDriver",
        "ZuluDriver",
    )
    assert all(
        c.entry_point_group == discovery.ENTRY_POINT_GROUP
        for c in candidates
    )
    assert target_a.load_calls == 0
    assert target_b.load_calls == 0
    assert unrelated.load_calls == 0
    assert other_group.load_calls == 0


def test_zero_match_fails_closed_without_registry_mutation(monkeypatch):
    unrelated = _FakeEntryPoint(
        name="unrelated.driver",
        group=discovery.ENTRY_POINT_GROUP,
        value="unrelated:factory",
        loaded=_factory,
    )
    monkeypatch.setattr(
        discovery.metadata,
        "distributions",
        lambda: (_dist("Other", "1", unrelated),),
    )
    registry = InferenceDriverRegistry()

    with pytest.raises(
        discovery.InstalledInferenceDriverNotFoundError
    ):
        discovery.register_installed_inference_driver(
            registry,
            "fms.checkpoint.v1",
        )

    assert registry.registered_driver_ids() == ()
    assert unrelated.load_calls == 0


def test_duplicate_match_fails_before_any_plugin_load(monkeypatch):
    first = _FakeEntryPoint(
        name="fms.checkpoint.v1",
        group=discovery.ENTRY_POINT_GROUP,
        value="one:factory",
        loaded=_factory,
    )
    second = _FakeEntryPoint(
        name="fms.checkpoint.v1",
        group=discovery.ENTRY_POINT_GROUP,
        value="two:factory",
        loaded=_factory,
    )
    monkeypatch.setattr(
        discovery.metadata,
        "distributions",
        lambda: (
            _dist("One", "1", first),
            _dist("Two", "1", second),
        ),
    )
    registry = InferenceDriverRegistry()

    with pytest.raises(
        discovery.InstalledInferenceDriverConflictError
    ):
        discovery.register_installed_inference_driver(
            registry,
            "fms.checkpoint.v1",
        )

    assert registry.registered_driver_ids() == ()
    assert first.load_calls == 0
    assert second.load_calls == 0


def test_pre_registered_driver_fails_before_metadata_or_load(monkeypatch):
    calls = {"distributions": 0}

    def forbidden_distributions():
        calls["distributions"] += 1
        raise AssertionError("metadata lookup should not run")

    monkeypatch.setattr(
        discovery.metadata,
        "distributions",
        forbidden_distributions,
    )
    registry = InferenceDriverRegistry()
    registry.register("fms.checkpoint.v1", _factory)

    with pytest.raises(
        discovery.InferenceDriverAlreadyRegisteredError
    ):
        discovery.register_installed_inference_driver(
            registry,
            "fms.checkpoint.v1",
        )

    assert calls["distributions"] == 0


def test_non_callable_plugin_fails_without_registry_mutation(monkeypatch):
    entry_point = _FakeEntryPoint(
        name="fms.checkpoint.v1",
        group=discovery.ENTRY_POINT_GROUP,
        value="bad:not_callable",
        loaded=object(),
    )
    monkeypatch.setattr(
        discovery.metadata,
        "distributions",
        lambda: (_dist("BadDriver", "1", entry_point),),
    )
    registry = InferenceDriverRegistry()

    with pytest.raises(
        discovery.InvalidInstalledInferenceDriverError
    ):
        discovery.register_installed_inference_driver(
            registry,
            "fms.checkpoint.v1",
        )

    assert entry_point.load_calls == 1
    assert registry.registered_driver_ids() == ()


def test_success_loads_only_exact_plugin_and_returns_provenance(monkeypatch):
    target = _FakeEntryPoint(
        name="fms.checkpoint.v1",
        group=discovery.ENTRY_POINT_GROUP,
        value="driver_pkg:factory",
        loaded=_factory,
    )
    unrelated = _FakeEntryPoint(
        name="unrelated.driver",
        group=discovery.ENTRY_POINT_GROUP,
        value="unrelated_pkg:factory",
        loaded=_factory,
    )
    monkeypatch.setattr(
        discovery.metadata,
        "distributions",
        lambda: (_dist("DriverPkg", "7.3.1", target, unrelated),),
    )
    registry = InferenceDriverRegistry()

    receipt = discovery.register_installed_inference_driver(
        registry,
        "fms.checkpoint.v1",
    )

    assert target.load_calls == 1
    assert unrelated.load_calls == 0
    assert registry.registered_driver_ids() == ("fms.checkpoint.v1",)
    assert receipt == discovery.InferenceDriverPluginReceipt(
        driver_id="fms.checkpoint.v1",
        distribution_name="DriverPkg",
        distribution_version="7.3.1",
        entry_point_group=discovery.ENTRY_POINT_GROUP,
        entry_point_value="driver_pkg:factory",
    )


def test_driver_id_matching_is_case_sensitive(monkeypatch):
    entry_point = _FakeEntryPoint(
        name="FMS.Checkpoint.V1",
        group=discovery.ENTRY_POINT_GROUP,
        value="driver_pkg:factory",
        loaded=_factory,
    )
    monkeypatch.setattr(
        discovery.metadata,
        "distributions",
        lambda: (_dist("DriverPkg", "1", entry_point),),
    )

    candidates = discovery.installed_inference_driver_candidates(
        "fms.checkpoint.v1"
    )
    assert candidates == ()
    assert entry_point.load_calls == 0
