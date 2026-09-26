from __future__ import annotations

from dataclasses import dataclass, replace
from types import SimpleNamespace
import hashlib

import pytest

from elpis_evolution_path_gate import (
    EvolutionPathAssertion,
    EvolutionPathGate,
    GateExecuted,
    GateRejected,
)


def d(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


@dataclass(frozen=True)
class FakeState:
    episode_id: str
    structural_attempt_index: int
    previous_structural_attempt_digest: str
    state_digest: str

    def digest(self) -> str:
        return self.state_digest


def projection():
    return SimpleNamespace(
        projection_digest=d("projection"),
        source=SimpleNamespace(
            head_event_digest=d("head"),
            final_state_root=d("root"),
        ),
    )


def state():
    return FakeState(
        episode_id="episode-r0",
        structural_attempt_index=2,
        previous_structural_attempt_digest=d("attempt-head"),
        state_digest=d("state-before"),
    )


def assertion(**overrides):
    s = state()
    p = projection()
    base = EvolutionPathAssertion(
        episode_id=s.episode_id,
        episode_state_digest=s.digest(),
        structural_attempt_index=s.structural_attempt_index,
        previous_structural_attempt_digest=s.previous_structural_attempt_digest,
        previous_path_receipt_digest=d("path-head"),
        candidate_manifest_digest=d("candidate"),
        hypothesis_digest=d("hypothesis"),
        component_scope=("components/DarwinianMatrix",),
        edit_count=1,
        edit_budget=2,
        resource_budget_digest=d("resource-budget"),
        evaluation_contract_digest=d("evaluation-contract"),
        history_projection_digest=p.projection_digest,
        history_head_event_digest=p.source.head_event_digest,
        history_final_state_root=p.source.final_state_root,
    )
    return replace(base, **overrides)


def gate():
    return EvolutionPathGate(
        allowed_component_scopes=("components/DarwinianMatrix",),
        resource_budget_digest=d("resource-budget"),
        evaluation_contract_digest=d("evaluation-contract"),
    )


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"episode_id": "wrong"}, "EPISODE_ID_MISMATCH"),
        ({"episode_state_digest": d("stale")}, "STALE_EPISODE_STATE"),
        ({"structural_attempt_index": 3}, "STRUCTURAL_ATTEMPT_INDEX_MISMATCH"),
        ({"previous_structural_attempt_digest": d("stale-head")}, "STRUCTURAL_ATTEMPT_HEAD_MISMATCH"),
        ({"edit_count": 3}, "EDIT_BUDGET_EXCEEDED"),
        ({"component_scope": ()}, "EMPTY_COMPONENT_SCOPE"),
        ({"component_scope": ("components/Other",)}, "COMPONENT_SCOPE_NOT_ALLOWED"),
        ({"resource_budget_digest": d("other-resource")}, "RESOURCE_BUDGET_MISMATCH"),
        ({"evaluation_contract_digest": d("other-eval")}, "EVALUATION_CONTRACT_MISMATCH"),
        ({"history_projection_digest": d("other-projection")}, "HISTORY_PROJECTION_MISMATCH"),
        ({"history_head_event_digest": d("other-head")}, "HISTORY_HEAD_MISMATCH"),
        ({"history_final_state_root": d("other-root")}, "HISTORY_ROOT_MISMATCH"),
    ],
)
def test_fail_closed_before_advance(changes, expected):
    calls = 0

    def advance(**kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("advance must not execute")

    result = gate().execute(
        assertion=assertion(**changes),
        state=state(),
        projection=projection(),
        advance=advance,
        advance_kwargs={},
    )
    assert isinstance(result, GateRejected)
    assert result.reason == expected
    assert result.advance_calls == 0
    assert calls == 0


def make_advance(outcome: str):
    def advance(*, state, **kwargs):
        after = FakeState(
            episode_id=state.episode_id,
            structural_attempt_index=state.structural_attempt_index + 1,
            previous_structural_attempt_digest=d("attempt-new"),
            state_digest=d("state-after-" + outcome),
        )
        return SimpleNamespace(
            state=after,
            structural_result=SimpleNamespace(
                attempt_record=SimpleNamespace(
                    attempt_digest=d("attempt-record-" + outcome),
                    outcome=outcome,
                ),
                refinement_result=SimpleNamespace(
                    result_digest=d("refinement-" + outcome),
                ),
            ),
            clamp_close_receipt=None,
        )
    return advance


@pytest.mark.parametrize(
    "outcome",
    ["STRUCTURAL_FRAME_COMMITTED", "STRUCTURAL_REFINEMENT_REJECTED"],
)
def test_admitted_attempt_is_transparently_bound_without_reinterpretation(outcome):
    result = gate().execute(
        assertion=assertion(),
        state=state(),
        projection=projection(),
        advance=make_advance(outcome),
        advance_kwargs={"opaque": "value"},
    )
    assert isinstance(result, GateExecuted)
    assert result.admitted is True
    assert result.advance_calls == 1
    assert result.receipt.attempt_outcome == outcome
    assert result.receipt.path_assertion_digest == assertion().digest
    assert result.receipt.previous_path_receipt_digest == d("path-head")
    assert len(result.receipt.receipt_digest) == 64
