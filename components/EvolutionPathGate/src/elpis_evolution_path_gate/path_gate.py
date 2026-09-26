from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .canonical import domain_digest, require_digest


GENESIS_DIGEST = "0" * 64


@dataclass(frozen=True)
class EvolutionPathAssertion:
    episode_id: str
    episode_state_digest: str
    structural_attempt_index: int
    previous_structural_attempt_digest: str
    previous_path_receipt_digest: str
    candidate_manifest_digest: str
    hypothesis_digest: str
    component_scope: tuple[str, ...]
    edit_count: int
    edit_budget: int
    resource_budget_digest: str
    evaluation_contract_digest: str
    history_projection_digest: str
    history_head_event_digest: str
    history_final_state_root: str

    def __post_init__(self) -> None:
        if not self.episode_id:
            raise ValueError("episode_id required")
        if type(self.structural_attempt_index) is not int or self.structural_attempt_index < 0:
            raise ValueError("invalid structural_attempt_index")
        if type(self.edit_count) is not int or self.edit_count < 0:
            raise ValueError("invalid edit_count")
        if type(self.edit_budget) is not int or self.edit_budget < 0:
            raise ValueError("invalid edit_budget")
        if type(self.component_scope) is not tuple or any(
            type(x) is not str or not x for x in self.component_scope
        ):
            raise ValueError("invalid component_scope")
        for value in (
            self.episode_state_digest,
            self.previous_structural_attempt_digest,
            self.previous_path_receipt_digest,
            self.candidate_manifest_digest,
            self.hypothesis_digest,
            self.resource_budget_digest,
            self.evaluation_contract_digest,
            self.history_projection_digest,
            self.history_head_event_digest,
            self.history_final_state_root,
        ):
            require_digest(value)

    def payload(self) -> dict:
        return {
            "schema": "elpis.evolution-path-assertion.v0",
            "episode_id": self.episode_id,
            "episode_state_digest": self.episode_state_digest,
            "structural_attempt_index": self.structural_attempt_index,
            "previous_structural_attempt_digest": self.previous_structural_attempt_digest,
            "previous_path_receipt_digest": self.previous_path_receipt_digest,
            "candidate_manifest_digest": self.candidate_manifest_digest,
            "hypothesis_digest": self.hypothesis_digest,
            "component_scope": list(self.component_scope),
            "edit_count": self.edit_count,
            "edit_budget": self.edit_budget,
            "resource_budget_digest": self.resource_budget_digest,
            "evaluation_contract_digest": self.evaluation_contract_digest,
            "history_projection_digest": self.history_projection_digest,
            "history_head_event_digest": self.history_head_event_digest,
            "history_final_state_root": self.history_final_state_root,
        }

    @property
    def digest(self) -> str:
        return domain_digest("elpis.evolution-path-assertion.v0", self.payload())


@dataclass(frozen=True)
class PathTransitionReceipt:
    path_assertion_digest: str
    episode_state_before_digest: str
    structural_attempt_digest: str
    refinement_result_digest: str
    episode_state_after_digest: str
    attempt_outcome: str
    close_receipt_digest: str | None
    previous_path_receipt_digest: str
    gate_disposition: str = "PATH_ASSERTION_ADMITTED_ATTEMPT_EXECUTED"

    def __post_init__(self) -> None:
        for value in (
            self.path_assertion_digest,
            self.episode_state_before_digest,
            self.structural_attempt_digest,
            self.refinement_result_digest,
            self.episode_state_after_digest,
            self.previous_path_receipt_digest,
        ):
            require_digest(value)
        if self.close_receipt_digest is not None:
            require_digest(self.close_receipt_digest)
        if not self.attempt_outcome:
            raise ValueError("attempt_outcome required")

    def payload(self) -> dict:
        return {
            "schema": "elpis.evolution-path-transition-receipt.v0",
            "path_assertion_digest": self.path_assertion_digest,
            "episode_state_before_digest": self.episode_state_before_digest,
            "structural_attempt_digest": self.structural_attempt_digest,
            "refinement_result_digest": self.refinement_result_digest,
            "episode_state_after_digest": self.episode_state_after_digest,
            "attempt_outcome": self.attempt_outcome,
            "close_receipt_digest": self.close_receipt_digest,
            "previous_path_receipt_digest": self.previous_path_receipt_digest,
            "gate_disposition": self.gate_disposition,
        }

    @property
    def receipt_digest(self) -> str:
        return domain_digest(
            "elpis.evolution-path-transition-receipt.v0", self.payload()
        )


@dataclass(frozen=True)
class GateRejected:
    admitted: bool
    reason: str
    advance_calls: int


@dataclass(frozen=True)
class GateExecuted:
    admitted: bool
    result: Any
    receipt: PathTransitionReceipt
    advance_calls: int


class EvolutionPathGate:
    def __init__(
        self,
        *,
        allowed_component_scopes: tuple[str, ...],
        resource_budget_digest: str,
        evaluation_contract_digest: str,
    ) -> None:
        self.allowed_component_scopes = frozenset(allowed_component_scopes)
        require_digest(resource_budget_digest)
        require_digest(evaluation_contract_digest)
        self.resource_budget_digest = resource_budget_digest
        self.evaluation_contract_digest = evaluation_contract_digest

    def reject_reason(
        self,
        assertion: EvolutionPathAssertion,
        state: Any,
        projection: Any,
    ) -> str | None:
        if assertion.episode_id != state.episode_id:
            return "EPISODE_ID_MISMATCH"
        if assertion.episode_state_digest != state.digest():
            return "STALE_EPISODE_STATE"
        if assertion.structural_attempt_index != state.structural_attempt_index:
            return "STRUCTURAL_ATTEMPT_INDEX_MISMATCH"
        if (
            assertion.previous_structural_attempt_digest
            != state.previous_structural_attempt_digest
        ):
            return "STRUCTURAL_ATTEMPT_HEAD_MISMATCH"
        if assertion.edit_count > assertion.edit_budget:
            return "EDIT_BUDGET_EXCEEDED"
        if not assertion.component_scope:
            return "EMPTY_COMPONENT_SCOPE"
        if not set(assertion.component_scope).issubset(self.allowed_component_scopes):
            return "COMPONENT_SCOPE_NOT_ALLOWED"
        if assertion.resource_budget_digest != self.resource_budget_digest:
            return "RESOURCE_BUDGET_MISMATCH"
        if assertion.evaluation_contract_digest != self.evaluation_contract_digest:
            return "EVALUATION_CONTRACT_MISMATCH"
        if assertion.history_projection_digest != projection.projection_digest:
            return "HISTORY_PROJECTION_MISMATCH"
        if assertion.history_head_event_digest != projection.source.head_event_digest:
            return "HISTORY_HEAD_MISMATCH"
        if assertion.history_final_state_root != projection.source.final_state_root:
            return "HISTORY_ROOT_MISMATCH"
        return None

    def execute(
        self,
        *,
        assertion: EvolutionPathAssertion,
        state: Any,
        projection: Any,
        advance: Callable[..., Any],
        advance_kwargs: dict[str, Any],
    ) -> GateRejected | GateExecuted:
        reason = self.reject_reason(assertion, state, projection)
        if reason is not None:
            return GateRejected(False, reason, 0)

        calls = 0

        def counted(**kwargs: Any) -> Any:
            nonlocal calls
            calls += 1
            return advance(**kwargs)

        result = counted(state=state, **advance_kwargs)
        record = result.structural_result.attempt_record
        refinement = result.structural_result.refinement_result
        close_digest = (
            result.clamp_close_receipt.receipt_digest
            if result.clamp_close_receipt is not None
            else None
        )
        receipt = PathTransitionReceipt(
            path_assertion_digest=assertion.digest,
            episode_state_before_digest=state.digest(),
            structural_attempt_digest=record.attempt_digest,
            refinement_result_digest=refinement.result_digest,
            episode_state_after_digest=result.state.digest(),
            attempt_outcome=record.outcome,
            close_receipt_digest=close_digest,
            previous_path_receipt_digest=assertion.previous_path_receipt_digest,
        )
        return GateExecuted(True, result, receipt, calls)
