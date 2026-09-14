"""Tests for source chain binding and census."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from elpis_grid81_promotion_planner.source_binding import (
    build_source_chain,
    census_g53b1,
    census_g53c,
    census_g53d,
    _resolve_config_directory,
)
from elpis_grid81_promotion_planner.canonical import SourceChain

CONFIG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "fixtures", "source_config.json"
)
with open(CONFIG) as _f:
    config = json.load(_f)


def test_config_directory_expands_environment(monkeypatch):
    monkeypatch.setenv("ELPIS_CANON", "/tmp/elpis-canon-root")
    resolved = _resolve_config_directory(
        {"g53b1_directory": "${ELPIS_CANON}/Elpis_Canon/reports/G5_3B"},
        "g53b1_directory",
    )
    assert resolved == "/tmp/elpis-canon-root/Elpis_Canon/reports/G5_3B"


def test_config_directory_rejects_unresolved_environment(monkeypatch):
    monkeypatch.delenv("ELPIS_I5_MISSING_ROOT", raising=False)
    with pytest.raises(
        ValueError,
        match="SOURCE_DIRECTORY_UNRESOLVED:g53b1_directory",
    ):
        _resolve_config_directory(
            {"g53b1_directory": "${ELPIS_I5_MISSING_ROOT}/reports"},
            "g53b1_directory",
        )


def test_build_source_chain():
    chain = build_source_chain(config)
    assert isinstance(chain, SourceChain)


def test_g53b1_phase_id():
    chain = build_source_chain(config)
    assert chain.g53b1.phase_id == "G5.3B.1"


def test_g53c_phase_id():
    chain = build_source_chain(config)
    assert chain.g53c.phase_id == "G5.3C"


def test_g53d_phase_id():
    chain = build_source_chain(config)
    assert chain.g53d.phase_id == "G5.3D"


def test_g53b1_disposition():
    chain = build_source_chain(config)
    assert "G53B" in chain.g53b1.disposition


def test_g53c_lifecycle_state():
    chain = build_source_chain(config)
    assert chain.g53c.lifecycle_state == "GRANTED_UNCONSUMED"


def test_g53c_has_artifact_digest():
    chain = build_source_chain(config)
    assert chain.g53c.artifact_digest is not None
    assert ":" in chain.g53c.artifact_digest


def test_g53c_has_capability_digest():
    chain = build_source_chain(config)
    assert chain.g53c.capability_digest is not None


def test_g53c_has_shadow_receipt_digest():
    chain = build_source_chain(config)
    assert len(chain.g53c.shadow_receipt_digest) == 64


def test_g53c_has_resulting_state_digest():
    chain = build_source_chain(config)
    assert len(chain.g53c.resulting_state_digest) == 64


def test_g53c_has_resulting_ledger_head():
    chain = build_source_chain(config)
    assert len(chain.g53c.resulting_ledger_head) == 64


def test_g53d_has_bundle_digest():
    chain = build_source_chain(config)
    assert len(chain.g53d.bundle_digest) == 64


def test_evidence_files_present():
    chain = build_source_chain(config)
    assert len(chain.g53b1.evidence_files) > 0
    assert len(chain.g53c.evidence_files) > 0
    assert len(chain.g53d.evidence_files) > 0


def test_chain_digest_deterministic():
    chain1 = build_source_chain(config)
    chain2 = build_source_chain(config)
    assert chain1.chain_digest == chain2.chain_digest


def test_missing_manifest_raises():
    bad_config = dict(config)
    bad_config["g53b1_directory"] = "/nonexistent"
    try:
        build_source_chain(bad_config)
        assert False, "Should raise FileNotFoundError"
    except FileNotFoundError:
        pass


def test_evidence_files_sorted():
    chain = build_source_chain(config)
    for phase in [chain.g53b1, chain.g53c, chain.g53d]:
        names = [fn for fn, _, _ in phase.evidence_files]
        assert names == sorted(names), f"Evidence files not sorted for {phase.phase_id}"
