from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import struct

import pytest

from elpis_reference import ecs_r0 as r0
from elpis_reference.structural_guidance.e0r3_participation import (
    apply_participation,
    bind_participation,
    ParticipationOperation,
)

ROOT = Path(__file__).resolve().parents[1]


def _candidate(width: int = 36) -> r0.Candidate:
    raw = bytearray()
    for row in range(6):
        for slot in range(width):
            value = 0.0 if slot == 0 else float((row + 1) * 100 + slot)
            raw.extend(struct.pack("<d", value))
    return r0.Candidate.bind(r0.FrozenTheta(width, bytes(raw), ROOT))


def test_candidate_participation_binding_matches_qualified_adapter():
    candidate = _candidate()
    through_candidate = candidate.participation_binding()
    direct = bind_participation(candidate)

    assert through_candidate == direct
    assert through_candidate.digest == direct.digest
    assert len(through_candidate.referents) == candidate.width
    assert through_candidate.candidate_digest == candidate.digest


def test_candidate_participation_mutation_matches_direct_e0r3_and_r0():
    candidate = _candidate()
    binding = candidate.participation_binding()
    referent = binding.referents[4]

    via_candidate = candidate.mutate_participation(
        binding,
        referent.semantic_id,
        r0.Opcode.DISABLE_COLUMN,
    )
    via_e0r3 = apply_participation(
        candidate,
        binding,
        ParticipationOperation(
            referent.semantic_id,
            r0.Opcode.DISABLE_COLUMN,
        ),
    )
    via_r0 = r0.mutate(
        candidate,
        r0.MutationRequest(
            r0.Opcode.DISABLE_COLUMN,
            candidate.digest,
            candidate.address(4),
        ),
    )

    assert via_candidate == via_e0r3 == via_r0
    assert via_candidate.changed is True
    assert via_candidate.candidate.mask[4] is r0.Status.DISABLED
    assert candidate.mask[4] is r0.Status.ACTIVE


def test_candidate_participation_stale_binding_fails_closed():
    candidate = _candidate()
    binding = candidate.participation_binding()
    referent = binding.referents[3]

    disabled = candidate.mutate_participation(
        binding,
        referent.semantic_id,
        r0.Opcode.DISABLE_COLUMN,
    ).candidate

    with pytest.raises(r0.R0Error, match="STALE_CANDIDATE"):
        disabled.mutate_participation(
            binding,
            referent.semantic_id,
            r0.Opcode.RESTORE_COLUMN,
        )


def test_candidate_participation_forged_binding_fails_closed():
    candidate = _candidate()
    binding = candidate.participation_binding()
    referent = binding.referents[2]

    forged_refs = list(binding.referents)
    forged_refs[2] = replace(
        referent,
        address=replace(
            referent.address,
            slot_index=3,
        ),
    )
    forged = replace(binding, referents=tuple(forged_refs))

    with pytest.raises(r0.R0Error):
        candidate.mutate_participation(
            forged,
            referent.semantic_id,
            r0.Opcode.DISABLE_COLUMN,
        )


def test_candidate_participation_frozen_zero_precondition_is_r0_owned():
    candidate = _candidate()
    binding = candidate.participation_binding()
    frozen = binding.referents[0]

    with pytest.raises(r0.R0Error, match="MUTATION_PRECONDITION"):
        candidate.mutate_participation(
            binding,
            frozen.semantic_id,
            r0.Opcode.DISABLE_COLUMN,
        )
