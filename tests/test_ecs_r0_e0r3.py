"""Adversarial adapter qualification; no temporary files or evidence writes."""
from dataclasses import FrozenInstanceError, replace
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from elpis_reference import ecs_r0 as r0
from elpis_reference.structural_guidance.e0r3_participation import (
    ParticipationOperation, apply_participation,
    bind_participation, reverse_bind, validate_binding,
)
from tools import ecs_r0_e0r3 as harness

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def authority_root(monkeypatch):
    monkeypatch.setenv("ELPIS_ECS_AUTHORITY_ROOT", str(ROOT))


@pytest.fixture(params=(36, 48, 72))
def bound(request):
    candidate = harness.qualification_candidate(request.param)
    return candidate, bind_participation(candidate)


def operation(binding, slot=1, op=r0.Opcode.DISABLE_COLUMN):
    return ParticipationOperation(binding.referents[slot].semantic_id, op)


def test_all_slots_qualified_with_mixed_byte_and_identity_adversaries(bound):
    candidate, binding = bound
    report = harness.qualify_width(candidate.width)
    assert report["binding_digest"] == binding.digest
    assert report["round_trips"] == candidate.width - 1
    assert report["referents"] == candidate.width
    assert report["writable_referents"] == candidate.width - 1
    assert report["participation_referent_qualification"] == "QUALIFIED"
    assert len(report["rejections"]) == 16
    assert candidate.theta.is_zero(0)
    assert not candidate.theta.is_zero(1)  # One subnormal amid signed zeros.
    assert candidate.theta.column(2) == candidate.theta.column(3)


@pytest.mark.parametrize("field,value", [
    ("ontology_id", "wrong"), ("ontology_version", "R1"),
    ("primitive_contract_digest", "0" * 64), ("d", 5), ("d", 6.0),
    ("N", 81), ("N", True), ("ordered_frozen_sidecar_digest", "0" * 64),
    ("operational_gauge_id", "wrong"), ("slot_index", -1),
    ("slot_index", 81), ("slot_index", True), ("slot_index", 1.0),
    ("expected_pre_status", "DISABLED"), ("expected_pre_status", "FROZEN_ZERO"),
    ("pre_state_equivalence_digest", "0" * 64),
])
def test_every_r0_address_field_is_bound_even_with_recomputed_digest(bound, field, value):
    candidate, binding = bound
    refs = list(binding.referents)
    refs[1] = replace(refs[1], address=replace(refs[1].address, **{field: value}))
    forged = replace(binding, referents=tuple(refs))
    assert len(forged.digest) == 64  # A valid content hash is not authorization.
    before = (candidate.digest, candidate.materialize(), candidate.mask, binding.digest)
    with pytest.raises(r0.R0Error):
        apply_participation(candidate, forged, operation(binding))
    assert (candidate.digest, candidate.materialize(), candidate.mask, binding.digest) == before


@pytest.mark.parametrize("field", tuple(r0.EditAddress.__dataclass_fields__))
def test_permissive_equality_cannot_forge_address_fields(bound, field):
    class EqualToAnything:
        def __eq__(self, other):
            return True
    candidate, binding = bound
    refs = list(binding.referents)
    refs[1] = replace(refs[1], address=replace(refs[1].address, **{field: EqualToAnything()}))
    with pytest.raises(r0.R0Error, match="ADDRESS_FIELD_TYPE"):
        reverse_bind(candidate, replace(binding, referents=tuple(refs)), refs[1].semantic_id)


@pytest.mark.parametrize("fault,code", [
    ("missing", "REVERSE_BINDING_LENGTH"), ("extra", "REVERSE_BINDING_LENGTH"),
    ("list", "REVERSE_BINDING_LENGTH"), ("record", "PARTICIPATION_REFERENT_TYPE"),
    ("address", "EDIT_ADDRESS"), ("id", "REFERENT_ID_TYPE"),
    ("digest", "STALE_CANDIDATE"), ("digest_type", "CANDIDATE_DIGEST_FORMAT"),
])
def test_closed_binding_shape(bound, fault, code):
    candidate, binding = bound
    refs = binding.referents
    bad = {
        "missing": replace(binding, referents=refs[:-1]),
        "extra": replace(binding, referents=refs + refs[:1]),
        "list": replace(binding, referents=list(refs)),
        "record": replace(binding, referents=(None,) + refs[1:]),
        "address": replace(binding, referents=(replace(refs[0], address=None),) + refs[1:]),
        "id": replace(binding, referents=(replace(refs[0], semantic_id=1),) + refs[1:]),
        "digest": replace(binding, candidate_digest="0" * 64),
        "digest_type": replace(binding, candidate_digest=True),
    }[fault]
    with pytest.raises(r0.R0Error, match=code):
        validate_binding(candidate, bad)


def test_no_caller_writability_cell_lane_or_reverse_address_override(bound):
    candidate, binding = bound
    zero = binding.referents[0]
    assert not zero.writable
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        zero.writable = True
    for field in ("writable", "cell", "lane", "slot_index", "address", "values"):
        with pytest.raises(TypeError):
            ParticipationOperation(zero.semantic_id, r0.Opcode.RESTORE_COLUMN, **{field: 1})
    with pytest.raises(TypeError):
        replace(zero, writable=True)
    assert reverse_bind(candidate, binding, zero.semantic_id) == candidate.address(0)


@pytest.mark.parametrize("op", [r0.Opcode.ABSTAIN, "DISABLE_COLUMN", None, True])
def test_only_explicit_r0_participation_opcodes(bound, op):
    candidate, binding = bound
    with pytest.raises(r0.R0Error, match="PARTICIPATION_OPCODE"):
        apply_participation(candidate, binding, operation(binding, op=op))


def test_delegates_exactly_once_to_existing_mutation_authority(bound, monkeypatch):
    candidate, binding = bound
    original = r0.mutate
    calls = []
    def spy(state, request):
        result = original(state, request)
        calls.append((state, request, result))
        return result
    monkeypatch.setattr(r0, "mutate", spy)
    result = apply_participation(candidate, binding, operation(binding))
    assert len(calls) == 1
    state, request, authority_result = calls[0]
    assert state is candidate and result is authority_result
    assert request == r0.MutationRequest(r0.Opcode.DISABLE_COLUMN,
                                         candidate.digest, candidate.address(1))


def test_bad_unselected_tail_rejects_before_mutation(bound, monkeypatch):
    candidate, binding = bound
    def forbidden(*args):
        pytest.fail("mutation was invoked before validating the complete binding")
    monkeypatch.setattr(r0, "mutate", forbidden)
    refs = binding.referents
    tail = replace(refs[-1], address=replace(refs[-1].address, expected_pre_status="DISABLED"))
    with pytest.raises(r0.R0Error, match="STALE_ADDRESS"):
        apply_participation(candidate, replace(binding, referents=refs[:-1] + (tail,)),
                            operation(binding))


def test_authority_is_reverified_without_trusting_binding_digest(bound, monkeypatch):
    candidate, binding = bound
    def rejected(*args):
        raise r0.R0Error("AUTHORITY_DIGEST_MISMATCH")
    monkeypatch.setattr(r0, "verify_authority", rejected)
    for action in (lambda: bind_participation(candidate),
                   lambda: reverse_bind(candidate, binding, binding.referents[1].semantic_id),
                   lambda: apply_participation(candidate, binding, operation(binding))):
        with pytest.raises(r0.R0Error, match="AUTHORITY_DIGEST_MISMATCH"):
            action()


def test_fully_symmetric_permutation_retains_gauge_slots_not_intrinsic_lineage(bound):
    candidate, _ = bound
    width = candidate.width
    raw = b"".join(candidate.theta.column(3)[row * 8:row * 8 + 8] * width for row in range(6))
    symmetric = r0.Candidate.bind(r0.FrozenTheta(width, raw, ROOT))
    moved, reverse = r0.permute(symmetric, tuple(reversed(range(width))))
    table = bind_participation(symmetric)
    # R0 cannot distinguish identical ordered states; do not invent a lineage ID.
    assert table == bind_participation(moved)
    assert reverse_bind(moved, table, table.referents[1].semantic_id).slot_index == 1
    assert reverse[1] == width - 2
    left = apply_participation(symmetric, table, operation(table)).candidate
    right = apply_participation(moved, table, operation(table, reverse[1])).candidate
    assert r0.equivalent(left, right) and left.digest != right.digest
    with pytest.raises(r0.R0Error, match="STALE_CANDIDATE"):
        validate_binding(right, bind_participation(left))


def test_exact_state_return_recreates_identity_without_historical_replay_claim(bound):
    candidate, binding = bound
    disabled = apply_participation(candidate, binding, operation(binding)).candidate
    next_binding = bind_participation(disabled)
    assert next_binding.digest != binding.digest
    restored = apply_participation(disabled, next_binding,
        operation(next_binding, op=r0.Opcode.RESTORE_COLUMN)).candidate
    assert bind_participation(restored) == binding
    validate_binding(restored, binding)


def test_stdout_harness_deterministic_across_fresh_processes_and_hash_seeds():
    outputs = []
    for seed in ("1", "77"):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED=seed,
                   PYTHONPATH=os.pathsep.join((str(ROOT / "src"), str(ROOT))))
        cp = subprocess.run([sys.executable, "-B", "tools/ecs_r0_e0r3.py"], cwd=ROOT,
                            env=env, capture_output=True, text=True, check=True)
        assert cp.stderr == ""
        outputs.append(cp.stdout)
    assert outputs[0] == outputs[1]
    result = json.loads(outputs[0])
    assert result["terminal_state"] == harness.QUALIFIED
    assert result["baseline_predecessor_head"] == harness.BASELINE_HEAD
    assert result["predecessor_condition"] == "SEMANTIC_IR_INSUFFICIENT"
    assert result["predecessor_replayed"]
    assert result["widths_exercised"] == [36, 48, 72]
    assert not result["canonical_grid81_written"]
    assert not result["E1_executed"] and not result["E2_executed"]
    assert result["remaining_nonclaims"] == list(harness.NONCLAIMS)


def test_failed_qualification_cannot_print_success(monkeypatch, capsys):
    def fail(width):
        raise r0.R0Error("INJECTED_QUALIFICATION_FAILURE")
    monkeypatch.setattr(harness, "qualify_width", fail)
    assert harness.main() == 1
    result = json.loads(capsys.readouterr().out)
    assert result["terminal_state"] == "PARTICIPATION_REFERENT_NOT_QUALIFIED"
    assert result["failure_code"] == "INJECTED_QUALIFICATION_FAILURE"
    assert result["widths_exercised"] is None
    for field in ("round_trip_status", "frozen_zero_status", "reverse_binding_status",
                  "stale_forgery_status", "permutation_status"):
        assert result[field] == "NOT_CERTIFIED"
    assert harness.QUALIFIED not in json.dumps(result)
