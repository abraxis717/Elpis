from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tomllib

from elpis_fractal_spine.isolated_driver import bind_model_port

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "components/TRMFractalSpine/registry/model_ports.toml"
AUTHORITY = ROOT / "drivers/needle3/QUALIFIED_RUNTIME.json"
BUILD = ROOT / "drivers/needle3/BUILD_CONTRACT.json"


def test_registry_uses_exact_file_identity_not_legacy_port_digest_recomputation():
    raw = REGISTRY.read_bytes()
    data = tomllib.loads(raw.decode())
    row = next(x for x in data["port"] if x["model_id"] == "Cactus.Needle3")
    assert row.get("port_digest") == ""
    assert hashlib.sha256(raw).hexdigest()


def test_needle3_port_is_bounded_disabled_and_exact():
    raw = REGISTRY.read_bytes()
    bound = bind_model_port(
        model_ports_path=REGISTRY,
        expected_sha256=hashlib.sha256(raw).hexdigest(),
        model_id="Cactus.Needle3",
        expected_driver_id="cactus.needle3.native.v1",
        expected_adapter_id="needle3-tool-proposal.v1",
        expected_admission_status="BOUNDED_NEEDLE3_TOOL_PROPOSAL_V1",
        expected_load_policy="ON_DEMAND",
        expected_authority_class="PROPOSAL_ONLY",
    )
    assert bound.port_id == "tool-proposal.needle3"

    data = tomllib.loads(raw.decode())
    row = next(x for x in data["port"] if x["model_id"] == "Cactus.Needle3")
    assert row["enabled"] is False
    assert row["network_allowed"] is False
    assert row["remote_code_allowed"] is False
    assert row["runtime_sha256"] == "59bb3ef1692d6e07845cb034c82e1d40a77814090b21b7d1d70aafa4287c9247"
    assert row["anchor_sha256"] == "6d827543a6a7e66a01b4535d3c6638f2e48e521f1b0c496adc006ece91045e53"
    assert row.get("port_digest") == ""


def test_needle3_runtime_authority_and_build_contract_are_frozen():
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    assert hashlib.sha256(AUTHORITY.read_bytes()).hexdigest() == "6d827543a6a7e66a01b4535d3c6638f2e48e521f1b0c496adc006ece91045e53"
    assert authority["driver"]["wheel_sha256"] == "59bb3ef1692d6e07845cb034c82e1d40a77814090b21b7d1d70aafa4287c9247"
    assert authority["model"]["sha256"] == "c9d915eca282ed42d1a09b143b592adb4cc6744ffe2d294adf5cfc5548170c38"
    assert authority["semantic_output"]["keys"] == [
        "type", "success", "function_calls", "confidence"
    ]

    build = json.loads(BUILD.read_text(encoding="utf-8"))
    assert build["distribution_version"] == "0.1.1"
    assert build["admission"]["model_port_added_by_this_phase"] is True
    assert build["admission"]["execution_authority_granted"] is True
    assert build["admission"]["production_wheel_authority_frozen"] is True


def test_legacy_pickle_needle_remains_quarantined():
    data = tomllib.loads(REGISTRY.read_text(encoding="utf-8"))
    row = next(x for x in data["port"] if x["model_id"] == "cactus-needle-26m")
    assert row["admission_status"] == "QUARANTINED"
    assert row["driver_id"] == "disabled.v1"
    assert row["load_policy"] == "NEVER"
    assert row["checkpoint_format"] == "pickle-prohibited"
