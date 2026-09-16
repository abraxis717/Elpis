"""Deterministic receipt for the bounded R2 Sudoku feedback profile."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from typing import Any

SCHEMA = "elpis.runtime-r2-feedback-receipt.v1"
PROFILE = "SUDOKU_FEEDBACK_V1"
RUNTIME_ADMISSION = False


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _digest(payload: Any) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


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
        if self.schema != SCHEMA or self.profile != PROFILE:
            return False
        return self.runtime_receipt_digest == _digest(
            self._payload_without_receipt_digest()
        )

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
        candidate = cls(
            schema=SCHEMA,
            profile=PROFILE,
            runtime_receipt_digest="",
            **kwargs,
        )
        digest = _digest(candidate._payload_without_receipt_digest())
        return replace(candidate, runtime_receipt_digest=digest)
