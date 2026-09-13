"""Isolated E0R3 participation adapter; not a Projector extension or E1/E2.

Identity is exactly the R0 MutationRequest binding: the full candidate digest
and every EditAddress field. Candidate.digest already commits the verified R0
authority, ordered frozen sidecar, gauge and complete mask. No observations,
Grid81 cells, intrinsic column identities or caller-selected aliases enter it.

Referents are public, deterministic state descriptors, not security tokens.
They expire when bound state changes; returning to the exact same R0 state
recreates them (no historical replay protection). Permutations require explicit
R0 permute() old-slot -> new-slot addressing followed by a fresh binding. Never
transport identity using equivalence_digest or column-byte matching: duplicate
columns are legal and slots denote an operational gauge, not intrinsic entities.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from elpis_reference import ecs_r0 as r0
from ._authority.c2r6p0.contracts import domain_digest


@dataclass(frozen=True, slots=True)
class ParticipationReferent:
    semantic_id: str
    address: r0.EditAddress

    @property
    def writable(self) -> bool:
        """Informational only until the entire binding has been validated."""
        return self.address.expected_pre_status in (
            r0.Status.ACTIVE.value, r0.Status.DISABLED.value)


@dataclass(frozen=True, slots=True)
class ParticipationBinding:
    candidate_digest: str
    referents: tuple[ParticipationReferent, ...]

    @property
    def digest(self) -> str:
        """Content identity, never a caller-supplied trust receipt."""
        return domain_digest("elpis.ecs.r0.e0r3.participation-binding.v1", asdict(self))


@dataclass(frozen=True, slots=True)
class ParticipationOperation:
    """One explicit referent operation; deliberately not SemanticOperationV1."""
    referent_id: str
    op: r0.Opcode


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise r0.R0Error(code)


def _semantic_id(candidate_digest: str, slot: int) -> str:
    # Slot suffix is injective within the bound gauge, even for equal columns.
    return f"participation.{candidate_digest}.{slot:03d}"


def bind_participation(candidate: r0.Candidate) -> ParticipationBinding:
    _require(type(candidate) is r0.Candidate, "CANDIDATE_TYPE")
    digest = candidate.digest  # Includes fresh verification of frozen authority.
    return ParticipationBinding(digest, tuple(
        ParticipationReferent(_semantic_id(digest, slot), candidate.address(slot))
        for slot in range(candidate.width)))


def validate_binding(candidate: r0.Candidate, binding: ParticipationBinding) -> None:
    """Re-derive every address; a recomputed digest cannot bless a forged table."""
    _require(type(candidate) is r0.Candidate, "CANDIDATE_TYPE")
    _require(type(binding) is ParticipationBinding, "PARTICIPATION_BINDING_TYPE")
    _require(type(binding.candidate_digest) is str, "CANDIDATE_DIGEST_FORMAT")
    _require(binding.candidate_digest == candidate.digest, "STALE_CANDIDATE")
    _require(type(binding.referents) is tuple and
             len(binding.referents) == candidate.width, "REVERSE_BINDING_LENGTH")
    ids, slots = set(), set()
    for position, referent in enumerate(binding.referents):
        _require(type(referent) is ParticipationReferent, "PARTICIPATION_REFERENT_TYPE")
        _require(type(referent.semantic_id) is str, "REFERENT_ID_TYPE")
        address = referent.address
        _require(type(address) is r0.EditAddress, "EDIT_ADDRESS")
        # Reject bool-as-int and objects with permissive equality before any
        # equality, hashing or address lookup can treat them as authoritative.
        for name in r0.EditAddress.__dataclass_fields__:
            expected_type = int if name in ("d", "N", "slot_index") else str
            _require(type(getattr(address, name)) is expected_type, "ADDRESS_FIELD_TYPE")
        _require(referent.semantic_id not in ids and address.slot_index not in slots,
                 "REVERSE_BINDING_COLLISION")
        ids.add(referent.semantic_id)
        slots.add(address.slot_index)
        expected = candidate.address(address.slot_index)
        _require(address == expected, "STALE_ADDRESS")
        _require(referent.semantic_id == _semantic_id(binding.candidate_digest,
                                                      address.slot_index),
                 "REVERSE_BINDING_MISMATCH")
        _require(position == address.slot_index, "REVERSE_BINDING_ORDER")


def reverse_bind(candidate: r0.Candidate, binding: ParticipationBinding,
                 referent_id: str) -> r0.EditAddress:
    """Resolve exactly one validated semantic referent to its full R0 address."""
    validate_binding(candidate, binding)
    _require(type(referent_id) is str, "REFERENT_ID_TYPE")
    for referent in binding.referents:
        if referent.semantic_id == referent_id:
            return referent.address
    raise r0.R0Error("UNKNOWN_PARTICIPATION_REFERENT")


def apply_participation(candidate: r0.Candidate, binding: ParticipationBinding,
                        operation: ParticipationOperation) -> r0.MutationResult:
    """Resolve then delegate. R0 alone checks preconditions and constructs state.

    No candidate/table is changed in place and no partial batch is possible.
    Exact-zero and illegal repeated transitions are rejected by R0 mutate().
    A successful result has passed its existing validated-state constructor.
    """
    _require(type(operation) is ParticipationOperation, "PARTICIPATION_OPERATION_TYPE")
    _require(type(operation.op) is r0.Opcode and operation.op in (
        r0.Opcode.DISABLE_COLUMN, r0.Opcode.RESTORE_COLUMN), "PARTICIPATION_OPCODE")
    address = reverse_bind(candidate, binding, operation.referent_id)
    return r0.mutate(candidate, r0.MutationRequest(
        operation.op, binding.candidate_digest, address))
