"""Deterministic, stdout-only E0R3 adjudication with synthetic software fixtures.

Run from the source root with PYTHONPATH=src:. and bytecode writing disabled.
This harness replays E0R2 as predecessor evidence, not as successor authority.
"""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import struct

from elpis_reference.ecs_r0 import (
    Candidate, FrozenTheta, MutationRequest, Opcode, R0Error, Status,
    equivalent, mutate, permute, verify_authority,
)
from elpis_reference.structural_guidance.e0r3_participation import (
    ParticipationOperation, apply_participation, bind_participation,
    reverse_bind, validate_binding,
)
from elpis_reference.structural_guidance._authority.c2r6p0.contracts import domain_digest
from tools.ecs_r0_e0r2 import adjudicate as predecessor_adjudicate
from tools.ecs_r0_e0r2 import synthetic_candidate

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_HEAD = "713137ef52ed884ffea2324942811452a4510144"
WIDTHS = (36, 48, 72)
QUALIFIED = "ISOLATED_R0_PARTICIPATION_REFERENT_QUALIFIED"
NONCLAIMS = (
    "Native participation representability in the predecessor Semantic-IR/Projector",
    "General Grid81 equivalence, writable capacity or decomposition",
    "Historical E1/E2 qualification or new E2 materialization authority",
    "Learned-refinement efficacy, scientific improvement or Darwinian benefit",
    "Runtime admission, execution authority or general semantic correctness",
    "Autonomous mutation or autonomous self-improvement",
    "Cryptographic authorization, historical replay protection or intrinsic column lineage",
)


def _check(condition: bool, code: str) -> None:
    if not condition:
        raise R0Error(code)


def qualification_candidate(width: int) -> Candidate:
    """Mixed signed exact zero, smallest subnormal, duplicate and unique columns."""
    raw = bytearray(synthetic_candidate(width).theta.data)
    for row in range(6):
        start = row * width * 8
        raw[start:start + 8] = struct.pack("<Q", (row % 2) << 63)
        raw[start + 8:start + 16] = struct.pack("<Q", 1 if row == 0 else 1 << 63)
        raw[start + 16:start + 24] = raw[start + 24:start + 32]
    return Candidate.bind(FrozenTheta(width, raw, REPO_ROOT))


def _operation(binding, slot, op):
    return ParticipationOperation(binding.referents[slot].semantic_id, op)


def _edit(candidate, slot, op):
    binding = bind_participation(candidate)
    return apply_participation(candidate, binding, _operation(binding, slot, op)).candidate


def _unchanged_state(candidate):
    return (candidate.theta.data, candidate.mask, candidate.digest, candidate.materialize())


def _reject(candidate, binding, operation, code):
    before = _unchanged_state(candidate)
    table_before = binding.digest
    try:
        apply_participation(candidate, binding, operation)
    except R0Error as exc:
        _check(exc.code == code, f"UNEXPECTED_REJECTION:{exc.code}:{code}")
    else:
        raise R0Error(f"ADVERSARY_ACCEPTED:{code}")
    _check(_unchanged_state(candidate) == before and binding.digest == table_before,
           "PARTIAL_MUTATION")
    return code


def qualify_width(width: int) -> dict:
    candidate = qualification_candidate(width)
    binding = bind_participation(candidate)
    validate_binding(candidate, binding)
    _check(binding == bind_participation(qualification_candidate(width)) and
           binding.digest == bind_participation(candidate).digest, "NONDETERMINISTIC_BINDING")
    _check(len({r.semantic_id for r in binding.referents}) == width and
           len({r.address.slot_index for r in binding.referents}) == width,
           "REFERENT_COLLISION")
    round_trips = 0
    for slot, referent in enumerate(binding.referents):
        _check(reverse_bind(candidate, binding, referent.semantic_id) == candidate.address(slot),
               "REVERSE_ADDRESS_CHANGED")
        _check(referent.writable == (slot != 0), "FROZEN_WRITABILITY_CHANGED")
        if slot == 0:
            continue
        before = _unchanged_state(candidate)
        operation = _operation(binding, slot, Opcode.DISABLE_COLUMN)
        result = apply_participation(candidate, binding, operation)
        direct = mutate(candidate, MutationRequest(Opcode.DISABLE_COLUMN,
                                                   candidate.digest, candidate.address(slot)))
        _check(result == direct and result.changed, "R0_AUTHORITY_RESULT_MISMATCH")
        disabled = result.candidate
        expected = bytearray(candidate.theta.data)
        for row in range(6):
            offset = (row * width + slot) * 8
            expected[offset:offset + 8] = b"\0" * 8
        _check(disabled.materialize() == bytes(expected) and
               all(status is (Status.DISABLED if i == slot else candidate.mask[i])
                   for i, status in enumerate(disabled.mask)), "WHOLE_COLUMN_DISABLE_FAILED")
        restored = _edit(disabled, slot, Opcode.RESTORE_COLUMN)
        _check(restored.theta is candidate.theta and disabled.theta is candidate.theta and
               _unchanged_state(restored) == before and _unchanged_state(candidate) == before and
               bind_participation(restored) == binding, "EXACT_ROUND_TRIP_FAILED")
        round_trips += 1

    rejections = {}
    def reject(label, state, table, operation, code):
        rejections[label] = _reject(state, table, operation, code)

    for op in (Opcode.DISABLE_COLUMN, Opcode.RESTORE_COLUMN):
        reject(f"frozen_zero_{op.value}", candidate, binding,
               _operation(binding, 0, op), "MUTATION_PRECONDITION")
    active_op = _operation(binding, 1, Opcode.DISABLE_COLUMN)
    disabled = _edit(candidate, 1, Opcode.DISABLE_COLUMN)
    disabled_binding = bind_participation(disabled)
    reject("stale_after_mutation", disabled, binding, active_op, "STALE_CANDIDATE")
    reject("wrong_candidate", _edit(candidate, 4, Opcode.DISABLE_COLUMN), binding,
           active_op, "STALE_CANDIDATE")
    raw = bytearray(candidate.theta.data)
    raw[32:40] = struct.pack("<d", -99.0)
    other = Candidate.bind(FrozenTheta(width, raw, REPO_ROOT))
    reject("wrong_theta", other, binding, active_op, "STALE_CANDIDATE")
    # Even rebinding the outer digest cannot authorize an old theta/address.
    reject("crossed_theta_outer_digest", other,
           replace(binding, candidate_digest=other.digest), active_op, "STALE_ADDRESS")
    reject("restore_active", candidate, binding,
           _operation(binding, 1, Opcode.RESTORE_COLUMN), "MUTATION_PRECONDITION")
    reject("disable_disabled", disabled, disabled_binding,
           _operation(disabled_binding, 1, Opcode.DISABLE_COLUMN), "MUTATION_PRECONDITION")
    reject("crossed_operation", disabled, disabled_binding, active_op,
           "UNKNOWN_PARTICIPATION_REFERENT")

    def forged(label, index, referent, code):
        refs = list(binding.referents)
        refs[index] = referent
        reject(label, candidate, replace(binding, referents=tuple(refs)), active_op, code)

    zero, first, second = binding.referents[:3]
    forged("forged_frozen_writable", 0, replace(zero, address=replace(
        zero.address, expected_pre_status=Status.ACTIVE.value)), "STALE_ADDRESS")
    forged("slot_collision", 2, replace(second, address=first.address),
           "REVERSE_BINDING_COLLISION")
    forged("referent_collision", 2, replace(second, semantic_id=first.semantic_id),
           "REVERSE_BINDING_COLLISION")
    forged("reverse_mismatch", 1, replace(first, semantic_id=second.semantic_id),
           "REVERSE_BINDING_MISMATCH")
    # Reordered valid records must not change operational address meaning.
    refs = list(binding.referents)
    refs[1], refs[2] = refs[2], refs[1]
    reject("table_reorder", candidate, replace(binding, referents=tuple(refs)),
           active_op, "REVERSE_BINDING_ORDER")

    left = _edit(candidate, 4, Opcode.DISABLE_COLUMN)
    right = _edit(candidate, 5, Opcode.DISABLE_COLUMN)
    _check(left.mask.count(Status.ACTIVE) == right.mask.count(Status.ACTIVE) and
           not equivalent(left, right) and
           bind_participation(left).digest != bind_participation(right).digest,
           "SAME_COUNT_MASK_ALIAS")
    duplicate_left = _edit(candidate, 2, Opcode.DISABLE_COLUMN)
    duplicate_right = _edit(candidate, 3, Opcode.DISABLE_COLUMN)
    _check(equivalent(duplicate_left, duplicate_right) and
           duplicate_left.digest != duplicate_right.digest and
           bind_participation(duplicate_left).digest != bind_participation(duplicate_right).digest,
           "EQUIVALENCE_USED_AS_OPERATIONAL_IDENTITY")
    reject("equivalent_mask_crossing", duplicate_right, bind_participation(duplicate_left),
           _operation(bind_participation(duplicate_left), 2, Opcode.RESTORE_COLUMN),
           "STALE_CANDIDATE")

    moved, reverse = permute(duplicate_left, tuple(reversed(range(width))))
    moved_binding = bind_participation(moved)
    _check(equivalent(duplicate_left, moved), "PERMUTATION_EQUIVALENCE_FAILED")
    for old, new in enumerate(reverse):
        address = reverse_bind(moved, moved_binding, moved_binding.referents[new].semantic_id)
        _check(address == moved.address(new) and
               duplicate_left.theta.column(old) == moved.theta.column(new) and
               duplicate_left.mask[old] is moved.mask[new], "PERMUTATION_REVERSE_FAILED")
    reject("implicit_permutation_rebinding", moved, bind_participation(duplicate_left),
           _operation(bind_participation(duplicate_left), 2, Opcode.RESTORE_COLUMN),
           "STALE_CANDIDATE")
    restored_moved = _edit(moved, reverse[2], Opcode.RESTORE_COLUMN)
    expected_moved, _ = permute(candidate, tuple(reversed(range(width))))
    _check(_unchanged_state(restored_moved) == _unchanged_state(expected_moved),
           "PERMUTATION_TRANSITION_DID_NOT_COMMUTE")
    return {
        "N": width, "referents": width, "writable_referents": width - 1,
        "theta_digest": candidate.theta.digest, "candidate_digest": candidate.digest,
        "binding_digest": binding.digest,
        "participation_referent_qualification": "QUALIFIED",
        "round_trip_status": "EXACT_BYTES_AND_R0_IDENTITY_RESTORED",
        "round_trips": round_trips, "frozen_zero_status": "BOTH_OPERATIONS_REJECTED",
        "reverse_binding_status": "ALL_SLOTS_UNIQUE_AND_VALIDATED",
        "stale_forgery_status": "ALL_LISTED_ADVERSARIES_REJECTED",
        "permutation_status": "EXPLICIT_REVERSE_MAP_PRESERVES_TRANSITION",
        "same_count_different_mask": "DISTINCT_BINDINGS",
        "equivalent_duplicate_column_masks": "DISTINCT_OPERATIONAL_BINDINGS",
        "failure_atomicity": "INPUTS_UNCHANGED", "rejections": rejections,
    }


def adjudicate() -> dict:
    predecessor = predecessor_adjudicate()
    _check(predecessor["terminal_state"] == "SEMANTIC_IR_INSUFFICIENT" and
           all(row["participation_writable_referents"] == 0 for row in predecessor["widths"]),
           "PREDECESSOR_CONDITION_CHANGED")
    widths = [qualify_width(width) for width in WIDTHS]
    return {
        "schema": "elpis.ecs.r0.e0r3-result.v1",
        "baseline_predecessor_head": BASELINE_HEAD,
        "predecessor_condition": predecessor["terminal_state"],
        "predecessor_replayed": True,
        "predecessor_evidence_digest": domain_digest("elpis.ecs.r0.e0r3.predecessor.v1", predecessor),
        "authority_digest": verify_authority(REPO_ROOT),
        "widths_exercised": list(WIDTHS), "widths": widths,
        "terminal_state": QUALIFIED,
        "bounded_claim": (
            "An isolated successor adapter provides deterministic, authority-bound "
            "whole-column participation referents sufficient for qualified R0 "
            "disable/restore round trips and reverse binding at widths 36, 48 and 72."
        ),
        "canonical_grid81_written": False, "E1_executed": False, "E2_executed": False,
        "remaining_nonclaims": list(NONCLAIMS),
    }


def main() -> int:
    try:
        result = adjudicate()
    except R0Error as exc:
        result = {
            "schema": "elpis.ecs.r0.e0r3-result.v1",
            "baseline_predecessor_head": BASELINE_HEAD,
            "predecessor_condition": "SEMANTIC_IR_INSUFFICIENT",
            "predecessor_replayed": None,  # Failed run certifies no replay result.
            "terminal_state": "PARTICIPATION_REFERENT_NOT_QUALIFIED",
            "failure_code": exc.code,
            "widths_requested": list(WIDTHS),
            "widths_exercised": None,  # Do not assert uncompleted coverage.
            "participation_referent_qualification": "INCOMPLETE_OR_FAILED",
            "round_trip_status": "NOT_CERTIFIED",
            "frozen_zero_status": "NOT_CERTIFIED",
            "reverse_binding_status": "NOT_CERTIFIED",
            "stale_forgery_status": "NOT_CERTIFIED",
            "permutation_status": "NOT_CERTIFIED",
            "bounded_claim": "No successful successor qualification established by this run.",
            "remaining_nonclaims": list(NONCLAIMS),
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
