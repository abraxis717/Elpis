"""Deterministic receipt for the bounded R2 Sudoku feedback profile."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from typing import Any

# v1 shipped in Elpis2.2.13 with a bare SHA256(canonical_json(payload)).
# New receipts use v2 and the cross-component Canonical Identity v1 framing:
# SHA256(UTF8(schema) || NUL || canonical_json(payload)).
# Keep v1 verification semantics indefinitely unless a later explicit migration
# contract retires them.
LEGACY_SCHEMA = "elpis.runtime-r2-feedback-receipt.v1"
SCHEMA = "elpis.runtime-r2-feedback-receipt.v2"
PROFILE = "SUDOKU_FEEDBACK_V1"
RUNTIME_ADMISSION = True


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _legacy_v1_digest(payload: Any) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _canonical_identity_digest(domain: str, payload: Any) -> str:
    # R2 remains an independently buildable zero-dependency wheel. This is the
    # exact Canonical Identity v1 framing used by elpis.canonical_identity;
    # repository-level conformance tests bind these bytes to that authority.
    if type(domain) is not str or not domain or "\x00" in domain:
        raise ValueError("R2_CANONICAL_DOMAIN_INVALID")
    framed = domain.encode("utf-8") + b"\x00" + _canonical_bytes(payload)
    return hashlib.sha256(framed).hexdigest()


def _digest(schema: str, payload: Any) -> str:
    if schema == LEGACY_SCHEMA:
        return _legacy_v1_digest(payload)
    if schema == SCHEMA:
        return _canonical_identity_digest(schema, payload)
    raise ValueError(f"R2_RECEIPT_SCHEMA_UNSUPPORTED:{schema}")


@dataclass(frozen=True)
class R2FeedbackRuntimeReceipt:
    schema: str
    profile: str
    run_id: str
    refinement_step_index: int
    prior_proposal_digest: str
    diagnostic_digest: str
    residual_digest: str
    resolution_digest: str
    release_binding_table_digest: str
    immutable_givens_digest: str
    release_plan_digest: str
    release_transaction_digest: str | None
    clamp_state_before_digest: str
    clamp_state_after_digest: str
    released_cells: tuple[int, ...]
    model_input_changed_cells: tuple[int, ...]
    learned_status: str | None
    learned_solution_digest: str | None
    learned_iteration_count: int
    traversal_digest: str
    runtime_receipt_digest: str

    def _payload_without_receipt_digest(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["released_cells"] = list(self.released_cells)
        payload["model_input_changed_cells"] = list(
            self.model_input_changed_cells
        )
        payload.pop("runtime_receipt_digest")
        return payload

    def verify(self) -> bool:
        if self.profile != PROFILE:
            return False
        try:
            expected = _digest(
                self.schema,
                self._payload_without_receipt_digest(),
            )
        except ValueError:
            return False
        return self.runtime_receipt_digest == expected

    def to_canonical_json(self) -> str:
        payload = asdict(self)
        payload["released_cells"] = list(self.released_cells)
        payload["model_input_changed_cells"] = list(
            self.model_input_changed_cells
        )
        return _canonical_bytes(payload).decode("utf-8")

    @classmethod
    def create(cls, **kwargs: Any) -> "R2FeedbackRuntimeReceipt":
        if "runtime_receipt_digest" in kwargs:
            raise TypeError("runtime_receipt_digest is derived")
        if "schema" in kwargs:
            raise TypeError("schema is derived")
        candidate = cls(
            schema=SCHEMA,
            profile=PROFILE,
            runtime_receipt_digest="",
            **kwargs,
        )
        digest = _digest(
            candidate.schema,
            candidate._payload_without_receipt_digest(),
        )
        return replace(candidate, runtime_receipt_digest=digest)
