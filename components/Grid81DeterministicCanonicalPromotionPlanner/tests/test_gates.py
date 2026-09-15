"""Tests for promotion gates."""

import json
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from elpis_grid81_promotion_planner.source_binding import build_source_chain
from elpis_grid81_promotion_planner.gates import (
    evaluate_gates,
    GATE_DEFINITIONS,
    first_failure,
    _check_replay_protection,
)
from elpis_grid81_promotion_planner.decision import make_decision, DECISION_NOT_READY

CONFIG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "fixtures", "source_config.json"
)
with open(CONFIG) as _f:
    config = json.load(_f)


def _load_config():
    with open(CONFIG) as f:
        return json.load(f)


def test_gate_count():
    chain = build_source_chain(_load_config())
    results = evaluate_gates(chain)
    assert len(results) == 19


def test_no_unestablished_phase_disposition_gate():
    assert all(gate_id != "GATE_ALL_PHASE_DISPOSITIONS_PRESENT" for gate_id, _, _ in GATE_DEFINITIONS)


def test_gate_order_deterministic():
    chain = build_source_chain(_load_config())
    r1 = evaluate_gates(chain)
    r2 = evaluate_gates(chain)
    for i in range(len(r1)):
        assert r1[i].gate_id == r2[i].gate_id
        assert r1[i].gate_ordinal == r2[i].gate_ordinal


def test_gate_digests_deterministic():
    chain = build_source_chain(_load_config())
    r1 = evaluate_gates(chain)
    r2 = evaluate_gates(chain)
    for i in range(len(r1)):
        assert r1[i].digest == r2[i].digest


def test_established_gate_set_excludes_unstructured_disposition():
    assert len(GATE_DEFINITIONS) == 19
    assert all(
        gate_id != "GATE_ALL_PHASE_DISPOSITIONS_PRESENT"
        for gate_id, _, _ in GATE_DEFINITIONS
    )

def test_missing_phase_rejected():
    bad_config = dict(_load_config())
    bad_config["g53b1_directory"] = "/nonexistent/g53b1"
    try:
        build_source_chain(bad_config)
        assert False, "Should raise FileNotFoundError"
    except FileNotFoundError:
        pass


def test_gate_ids_unique():
    ids = [gid for gid, _, _ in GATE_DEFINITIONS]
    assert len(ids) == len(set(ids))


def test_gate_ordinal_ascending():
    ordinals = [ord_ for _, ord_, _ in GATE_DEFINITIONS]
    for i in range(len(ordinals) - 1):
        assert ordinals[i] < ordinals[i + 1]

def _replay_chain(tmp_path, payload):
    source = tmp_path / "g53b1"
    source.mkdir()
    (source / "G53B_REPLAY_AUDIT.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )
    return SimpleNamespace(
        g53b1=SimpleNamespace(source_directory=str(source))
    )


def test_replay_protection_missing_status_fields_fails_closed(tmp_path):
    chain = _replay_chain(tmp_path, {"audit": "present"})
    assert _check_replay_protection(chain) is False


def test_replay_protection_explicit_legacy_true_is_accepted(tmp_path):
    chain = _replay_chain(tmp_path, {"replay_protection": True})
    assert _check_replay_protection(chain) is True


def test_replay_protection_conflicting_status_fields_fail_closed(tmp_path):
    chain = _replay_chain(
        tmp_path,
        {
            "replay_protection_qualified": True,
            "replay_protection": False,
        },
    )
    assert _check_replay_protection(chain) is False

def test_replay_protection_non_mapping_payloads_fail_closed(tmp_path):
    payloads = ([], "qualified", 1, True, None)
    for index, payload in enumerate(payloads):
        case = tmp_path / f"case-{index}"
        case.mkdir()
        chain = _replay_chain(case, payload)
        assert _check_replay_protection(chain) is False

