from __future__ import annotations

from dataclasses import replace
import hashlib
import math
from pathlib import Path
from types import MappingProxyType

import pytest

from elpis_fractal_spine.contracts import ModelResidencyRequest
from elpis_fractal_spine.isolated_driver import (
    bind_model_port, canonicalize_context, activate_isolated_provider, SupervisorPolicy,
)
from elpis_fractal_spine.isolated_driver.errors import AuthorityError, ContextError, RegistryError, LifecycleError
from test_isolated_driver_authority import DRIVER, PROVIDER, make_wheel
from test_isolated_driver_supervisor import request

REGISTRY = '''schema_version = "elpis.model-ports.v1"
network_allowed = false
remote_code_allowed = false
[[port]]
port_id = "synthetic.port"
model_id = "test-model"
driver_id = "synthetic.inference.v1"
adapter_id = "synthetic.adapter.v1"
admission_status = "TEST_ONLY"
authority_class = "PROPOSAL_ONLY"
load_policy = "ON_DEMAND"
enabled = false
network_allowed = false
remote_code_allowed = false
'''


def bind(tmp_path, text=REGISTRY, **kwargs):
    path = tmp_path / "ports.toml"
    path.write_text(text)
    args = dict(model_ports_path=path, expected_sha256=hashlib.sha256(text.encode()).hexdigest(),
                model_id="test-model", expected_driver_id=DRIVER, expected_adapter_id="synthetic.adapter.v1",
                expected_admission_status="TEST_ONLY", expected_load_policy="ON_DEMAND",
                expected_authority_class="PROPOSAL_ONLY")
    args.update(kwargs)
    return bind_model_port(**args)


def test_bound_authority_and_activation(tmp_path):
    port = bind(tmp_path)
    path, authority = make_wheel(tmp_path)
    assert port.registry_sha256 == hashlib.sha256(REGISTRY.encode()).hexdigest()
    with pytest.raises(AttributeError):
        port.driver_id = "changed"
    with activate_isolated_provider(bound_port=port, authority=authority, wheel_path=path,
                                    runtime_context=canonicalize_context({}), policy=SupervisorPolicy(tmp_path)) as p:
        assert p.execute(request()).status == "OK"
        with pytest.raises(LifecycleError):
            p.acquire(ModelResidencyRequest("wrong-model"))
    with pytest.raises(AuthorityError):
        activate_isolated_provider(bound_port=replace(port, driver_id="different.v1"), authority=authority,
                                   wheel_path=path, runtime_context=canonicalize_context({}), policy=SupervisorPolicy(tmp_path))
    with pytest.raises(AuthorityError):
        activate_isolated_provider(bound_port=replace(port, load_policy="NEVER"), authority=authority,
                                   wheel_path=path, runtime_context=canonicalize_context({}), policy=SupervisorPolicy(tmp_path))


@pytest.mark.parametrize("old,new", [
    ('"elpis.model-ports.v1"', '"wrong"'),
    ("network_allowed = false", "network_allowed = true"),
    ("remote_code_allowed = false", "remote_code_allowed = true"),
    ("enabled = false", "enabled = true"),
    ('"synthetic.inference.v1"', '"wrong.v1"'),
    ('"synthetic.adapter.v1"', '"wrong.v1"'),
    ('"TEST_ONLY"', '"ADMITTED"'),
    ('"ON_DEMAND"', '"NEVER"'),
    ('"PROPOSAL_ONLY"', '"WRITER"'),
])
def test_registry_policy_mismatches(tmp_path, old, new):
    with pytest.raises(RegistryError):
        bind(tmp_path, REGISTRY.replace(old, new))


@pytest.mark.parametrize("key", ["network_allowed", "remote_code_allowed"])
def test_row_only_and_top_only_permissions(tmp_path, key):
    old = key + " = false"
    for text in (REGISTRY.replace(old, key + " = true", 1),
                 REGISTRY[:REGISTRY.rindex(old)] + REGISTRY[REGISTRY.rindex(old):].replace(old, key + " = true")):
        with pytest.raises(RegistryError):
            bind(tmp_path, text)


def test_wrong_digest_rejected_before_parse(tmp_path, monkeypatch):
    import elpis_fractal_spine.isolated_driver.registry as registry
    monkeypatch.setattr(registry.tomllib, "loads", lambda *a: pytest.fail("parsed before hash check"))
    with pytest.raises(RegistryError, match="identity"):
        bind(tmp_path, expected_sha256="0" * 64)


def test_duplicate_or_missing_model_rows(tmp_path):
    for text in (REGISTRY + "[[port]]\nmodel_id = 'test-model'\n", REGISTRY.replace("test-model", "another")):
        with pytest.raises(RegistryError):
            bind(tmp_path, text)


def test_registry_path_replaced_between_read_and_parse(tmp_path, monkeypatch):
    # Swap the pathname as soon as the first read returns, before hashing or
    # parsing. A hash-then-reopen implementation would see the replacement.
    original_open = Path.open
    replacement = tmp_path / "replacement.toml"
    replacement.write_text("invalid = [")
    count = 0
    class ReplacingReader:
        def __init__(self, handle):
            self.handle = handle
        def __enter__(self):
            return self
        def read(self, *args):
            raw = self.handle.read(*args)
            replacement.replace(tmp_path / "ports.toml")
            return raw
        def __exit__(self, *args):
            self.handle.close()
    def opening(path, mode="r", *args, **kwargs):
        nonlocal count
        handle = original_open(path, mode, *args, **kwargs)
        if path == tmp_path / "ports.toml" and "r" in mode:
            count += 1
            assert count == 1, "registry pathname reopened after byte binding"
            return ReplacingReader(handle)
        return handle
    monkeypatch.setattr(Path, "open", opening)
    port = bind(tmp_path)
    assert count == 1
    assert port.driver_id == DRIVER
    assert port.registry_sha256 == hashlib.sha256(REGISTRY.encode()).hexdigest()


def test_context_canonical_order_tuples_and_isolated_mutation(tmp_path):
    original = {"nested": {"items": [1, {"mutable": [2]}]}, "tuple": (3, 4)}
    context = canonicalize_context(original)
    assert context == canonicalize_context(dict(reversed(list(original.items()))))
    assert context.digest == canonicalize_context(MappingProxyType(original)).digest
    copy = context.decode()
    copy["nested"]["items"].append(9)
    assert len(original["nested"]["items"]) == 2
    source = PROVIDER + '''
def factory(context):
    context['nested']['items'][1]['mutable'].append(99)
    assert isinstance(context['tuple'], list)
    return Provider(context)
def result(self, request, *, residency=None):
    return InferenceExecutionResult('OK', tuple(self.context['nested']['items'][1]['mutable']), 1, 'b', 'cpu', 'HOT')
Provider.execute = result
'''
    path, authority = make_wheel(tmp_path, source)
    with activate_isolated_provider(bound_port=bind(tmp_path), authority=authority, wheel_path=path,
                                    runtime_context=context, policy=SupervisorPolicy(tmp_path)) as p:
        assert p.execute(request()).output_payload == (2, 99)
    assert original["nested"]["items"][1]["mutable"] == [2]


@pytest.mark.parametrize("value", [b"x", bytearray(b"x"), memoryview(b"x"), Path("file"),
                                   {1, 2}, object(), float("nan"), float("inf"), -float("inf"),
                                   2**63, -(2**63) - 1, {1: "key"}, "\ud800"])
def test_context_non_json_and_invalid_scalars(value):
    with pytest.raises(ContextError):
        canonicalize_context({"value": value})


def test_context_cycle_depth_elements_and_encoded_size():
    cyclic = []
    cyclic.append(cyclic)
    deep = []
    for _ in range(40):
        deep = [deep]
    for value in (cyclic, deep, [0] * 100_001, "x" * (1024 * 1024 + 1), "ž" * 600_000):
        with pytest.raises(ContextError):
            canonicalize_context({"value": value})


def test_context_rejects_custom_container_subclasses():
    class Custom(dict):
        pass
    with pytest.raises(ContextError):
        canonicalize_context(Custom())
