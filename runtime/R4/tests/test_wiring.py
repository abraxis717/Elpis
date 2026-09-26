from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path

import torch

from DarwinianMatrix.controller.episode import (
    DarwinianEpisodeState,
    EpisodeDisposition,
    advance_episode,
)
from DarwinianMatrix.ecology.engine import PRODUCER, EcologyState
from DarwinianMatrix.geometry import build_neighbor_table
from DarwinianMatrix.projector.constraints import (
    ClampOperation,
    ClampProposal,
    ClampState,
    ClampTransaction,
    apply_clamp_transaction,
)
from DarwinianMatrix.trm.reference_solver import DeterministicSudokuReferenceAdapter
from elpis_ecs.scheduler import SCHEDULER_V1
from elpis_ecs_context.contracts import (
    ContextProjection,
    HistoryBinding,
    ProjectionRequest,
)
from elpis_evolution_path_gate import (
    GENESIS_DIGEST,
    EvolutionPathAssertion,
    EvolutionPathGate,
    GateExecuted,
    GateRejected,
)
from elpis_runtime_r4 import (
    PROFILE,
    RUNTIME_ADMISSION,
    execute_guarded_darwinian_attempt,
)

GRID = torch.tensor([
    5,3,4,6,7,8,9,1,2,
    6,7,2,1,9,5,3,4,8,
    1,9,8,3,4,2,5,6,7,
    8,5,9,7,6,1,4,2,3,
    4,2,6,8,5,3,7,9,1,
    7,1,3,9,2,4,8,5,6,
    9,6,1,5,3,7,2,8,4,
    2,8,7,4,1,9,6,3,5,
    3,4,5,2,8,6,1,7,9,
])


def d(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def ecology_state() -> EcologyState:
    state=EcologyState()
    state.ctype[3280]=PRODUCER
    state.genome[3280]=0.5
    state.energy[3280]=1.0
    state.lineage[3280]=3280
    state.validate()
    return state


def forced_clamps() -> ClampState:
    state=ClampState.empty("branch46d-episode")
    proposal=ClampProposal(
        proposal_id="force-six",
        operation=ClampOperation.ASSERT,
        slot_id="slot-a",
        evidence_digest="a"*64,
        cell_index=0,
        value=6,
    )
    tx=ClampTransaction(
        transaction_id="assert-six",
        episode_id=state.episode_id,
        expected_state_digest=state.digest(),
        proposals=(proposal,),
    )
    result=apply_clamp_transaction(state=state,transaction=tx)
    assert result.accepted
    return result.state


def initial_state(*, meta_budget: int=3, structural_budget: int=4):
    return DarwinianEpisodeState.initial(
        episode_id="branch46d-episode",
        previous_grid=GRID,
        ecology_state=ecology_state(),
        meta_attempt_budget=meta_budget,
        structural_attempt_budget=structural_budget,
        clamp_state=forced_clamps(),
    )


def accepted_adapter():
    return DeterministicSudokuReferenceAdapter()


def rejected_adapter():
    return DeterministicSudokuReferenceAdapter(max_search_nodes=0)


def projection() -> ContextProjection:
    source=HistoryBinding(
        genesis_digest=d("genesis"),
        mailbox_capacity=64,
        scheduler_protocol=SCHEDULER_V1,
        event_count=0,
        head_event_digest=d("history-head"),
        final_state_root=d("history-root"),
    )
    return ContextProjection(
        source=source,
        request=ProjectionRequest(),
        records=(),
        total_matches=0,
        record_bytes_used=2,
        budget_exhausted=(),
    )


def gate() -> EvolutionPathGate:
    return EvolutionPathGate(
        allowed_component_scopes=("components/DarwinianMatrix",),
        resource_budget_digest=d("resource-budget"),
        evaluation_contract_digest=d("evaluation-contract"),
    )


def assertion(state, p, *, previous_path=GENESIS_DIGEST):
    return EvolutionPathAssertion(
        episode_id=state.episode_id,
        episode_state_digest=state.digest(),
        structural_attempt_index=state.structural_attempt_index,
        previous_structural_attempt_digest=state.previous_structural_attempt_digest,
        previous_path_receipt_digest=previous_path,
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


def common_kwargs(state, adapter):
    return dict(
        state=state,
        random_seed=717,
        adapter=adapter,
        target_viability=1_000_000.0,
        neighbors=build_neighbor_table(),
    )


def test_runtime_r4_is_explicitly_inactive():
    assert PROFILE == "EVOLUTION_PATH_DARWINIAN_GUARDED_ATTEMPT_R0"
    assert RUNTIME_ADMISSION is False


def test_rejected_path_assertion_executes_zero_darwinian_attempts(monkeypatch):
    state=initial_state()
    p=projection()
    bad=replace(assertion(state,p),episode_state_digest=d("stale"))

    def forbidden(**kwargs):
        raise AssertionError("Darwinian advance executed after rejected path assertion")

    import DarwinianMatrix.controller.episode as episode
    monkeypatch.setattr(episode,"advance_episode",forbidden)

    result=execute_guarded_darwinian_attempt(
        gate=gate(),assertion=bad,projection=p,
        **common_kwargs(state,accepted_adapter()),
    )
    assert isinstance(result,GateRejected)
    assert result.reason == "STALE_EPISODE_STATE"
    assert result.advance_calls == 0
    assert state.structural_attempt_index == 0


def test_committed_attempt_is_exactly_transparent_through_gate():
    state=initial_state()
    p=projection()
    a=assertion(state,p)
    kwargs=common_kwargs(state,accepted_adapter())

    direct=advance_episode(**kwargs)
    guarded=execute_guarded_darwinian_attempt(
        gate=gate(),assertion=a,projection=p,**kwargs
    )

    assert isinstance(guarded,GateExecuted)
    assert guarded.advance_calls == 1
    assert guarded.result.state.digest() == direct.state.digest()
    assert guarded.result.structural_result.attempt_record.attempt_digest == direct.structural_result.attempt_record.attempt_digest
    assert guarded.result.structural_result.refinement_result.result_digest == direct.structural_result.refinement_result.result_digest
    assert guarded.receipt.path_assertion_digest == a.digest
    assert guarded.receipt.structural_attempt_digest == direct.structural_result.attempt_record.attempt_digest
    assert guarded.receipt.episode_state_before_digest == state.digest()
    assert guarded.receipt.episode_state_after_digest == direct.state.digest()
    assert guarded.receipt.previous_path_receipt_digest == GENESIS_DIGEST


def test_rejected_darwinian_attempt_is_still_transparently_recorded():
    state=initial_state()
    p=projection()
    a=assertion(state,p,previous_path=d("previous-path"))
    kwargs=common_kwargs(state,rejected_adapter())

    direct=advance_episode(**kwargs)
    guarded=execute_guarded_darwinian_attempt(
        gate=gate(),assertion=a,projection=p,**kwargs
    )

    assert isinstance(guarded,GateExecuted)
    assert guarded.advance_calls == 1
    assert not direct.structural_result.committed
    assert guarded.result.state.digest() == direct.state.digest()
    assert guarded.receipt.attempt_outcome == direct.structural_result.attempt_record.outcome
    assert guarded.receipt.structural_attempt_digest == direct.structural_result.attempt_record.attempt_digest
    assert guarded.receipt.previous_path_receipt_digest == d("previous-path")


def test_terminal_attempt_binds_existing_clamp_close_receipt():
    state=initial_state(structural_budget=1)
    p=projection()
    a=assertion(state,p)
    guarded=execute_guarded_darwinian_attempt(
        gate=gate(),assertion=a,projection=p,
        **common_kwargs(state,rejected_adapter()),
    )

    assert isinstance(guarded,GateExecuted)
    assert guarded.result.state.disposition == EpisodeDisposition.STRUCTURAL_ATTEMPT_BUDGET_EXHAUSTED
    assert guarded.result.clamp_close_receipt is not None
    assert guarded.receipt.close_receipt_digest == guarded.result.clamp_close_receipt.receipt_digest


def test_history_binding_mismatch_fails_before_darwinian_advance(monkeypatch):
    state=initial_state()
    p=projection()
    bad=replace(assertion(state,p),history_final_state_root=d("wrong-root"))

    def forbidden(**kwargs):
        raise AssertionError("advance must not execute")

    import DarwinianMatrix.controller.episode as episode
    monkeypatch.setattr(episode,"advance_episode",forbidden)
    result=execute_guarded_darwinian_attempt(
        gate=gate(),assertion=bad,projection=p,
        **common_kwargs(state,accepted_adapter()),
    )
    assert isinstance(result,GateRejected)
    assert result.reason == "HISTORY_ROOT_MISMATCH"
    assert result.advance_calls == 0


def test_wiring_source_has_no_model_token_or_selection_authority():
    source=(Path(__file__).resolve().parents[1]/"src/elpis_runtime_r4/wiring.py").read_text()
    assert "elpis_reference" not in source
    assert "elpis_runtime_r2" not in source
    assert "elpis_runtime_r3" not in source
    assert "torch" not in source
    assert "select(" not in source
    assert "atomic_materialize" not in source
    assert "DarwinianMatrix.controller.episode" in source
