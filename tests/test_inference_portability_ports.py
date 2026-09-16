from __future__ import annotations

import hashlib
import importlib.util
import inspect
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
TRM_SRC = ROOT / "components" / "TRMFractalSpine" / "src"
R2_SRC = ROOT / "runtime" / "R2" / "src"
SRC = ROOT / "src"
for path in (TRM_SRC, R2_SRC, SRC, ROOT / "components"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from elpis_fractal_spine.components import ModelResidency
from elpis_fractal_spine.contracts import (
    InferenceExecutionRequest,
    InferenceExecutionResult,
    LOGICAL_RESIDENCY_TIERS,
    ModelResidencyBinding,
    ModelResidencyRequest,
    ResidencyAbsentPolicy,
)


def test_logical_residency_vocabulary_and_legacy_compatibility():
    assert LOGICAL_RESIDENCY_TIERS == frozenset(
        {"ABSENT", "HOT", "WARM", "COLD"}
    )
    assert ModelResidency.HOT.value == "HOT"
    assert ModelResidency.WARM.value == "WARM"
    assert ModelResidency.COLD.value == "COLD"
    assert ModelResidency.ABSENT.value == "ABSENT"
    assert ModelResidency.PINNED_CPU.value == "PINNED_CPU"
    assert ModelResidency.PINNED_GPU.value == "PINNED_GPU"


def test_new_port_contracts_are_accelerator_name_agnostic():
    paths = (
        ROOT / "components" / "TRMFractalSpine" / "src"
        / "elpis_fractal_spine" / "contracts.py",
        ROOT / "components" / "TRMFractalSpine" / "src"
        / "elpis_fractal_spine" / "ports.py",
    )
    combined = "\n".join(
        path.read_text(encoding="utf-8").lower() for path in paths
    )
    for forbidden in ("cuda", "mps", "rocm", "vulkan", "metal"):
        assert forbidden not in combined


def test_residency_contract_is_logical_and_provider_identity_is_opaque():
    request = ModelResidencyRequest(
        model_id="model-x",
        preferred_tier="HOT",
        absent_policy=ResidencyAbsentPolicy.FOLD_DOWN,
    )
    binding = ModelResidencyBinding(
        model_id=request.model_id,
        requested_tier=request.preferred_tier,
        actual_tier="WARM",
        backend_id="backend-x",
        device_id="opaque-device-x",
        binding_id="binding-x",
    )
    assert binding.actual_tier == "WARM"
    with pytest.raises(ValueError):
        ModelResidencyRequest(model_id="x", preferred_tier="PINNED_GPU")


def test_r2_exposes_ports_without_importing_torch():
    import elpis_runtime_r2.wiring as wiring

    signature = inspect.signature(wiring.execute_feedback_transaction)
    assert "execution_port" in signature.parameters
    assert "residency_port" in signature.parameters
    assert "torch" not in sys.modules


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is None,
    reason="functional feedback-port wiring requires the TRM test environment",
)
def test_injected_ports_bypass_direct_model_execution(monkeypatch):
    import elpis_reference.feedback_refinement as feedback
    from DarwinianMatrix.projector.constraints import (
        ClampOperation,
        ClampProposal,
        ClampState,
        ClampTransaction,
        apply_clamp_transaction,
    )
    from elpis_reference.projector_release import (
        ReleaseBindingTableV1,
        ReleaseBindingTargetV1,
    )
    from elpis_reference.semantic_refinement import (
        SEMANTIC_OBJECT,
        ReverseTraceIndex,
        StructuralObservationRecord,
        TASK_REJECTION,
        TaskDiagnosticV1,
    )

    solved = tuple(
        int(v) for v in (
            "534678912672195348198342567859761423426853791713924856"
            "961537284287419635345286179"
        )
    )

    def h(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    state = ClampState.empty("port-injection")
    tx = ClampTransaction(
        transaction_id="initial",
        episode_id=state.episode_id,
        expected_state_digest=state.digest(),
        proposals=(
            ClampProposal(
                proposal_id="assert-0",
                operation=ClampOperation.ASSERT,
                slot_id="slot-0",
                evidence_digest=h("e0"),
                cell_index=0,
                value=solved[0],
            ),
        ),
    )
    state = apply_clamp_transaction(state=state, transaction=tx).state

    diagnostic = TaskDiagnosticV1(
        diagnostic_class=TASK_REJECTION,
        task_scope_id=state.episode_id,
        frame_index=0,
        subject_digest=feedback.samsung_proposal_digest(solved),
        producer_id="port-test",
        locus_namespace=SEMANTIC_OBJECT,
        locus_identity=h("semantic-cell-0"),
        reason_codes=("TASK_REQUIREMENT_UNSATISFIED",),
        details_digest=h("details"),
    )
    reverse_trace = ReverseTraceIndex((
        StructuralObservationRecord.create(
            source_semantic_object_digest=h("semantic-cell-0"),
            topology_vertex_digest=h("topology-0"),
            P7_capsule_digest=h("capsule-0"),
            P7_primary_cell_index=0,
        ),
    ))
    bindings = ReleaseBindingTableV1(
        episode_id=state.episode_id,
        clamp_state_digest=state.digest(),
        targets=(
            ReleaseBindingTargetV1(
                cell_index=0,
                owner="slot-0",
                locus_namespace=SEMANTIC_OBJECT,
                locus_identity=h("semantic-cell-0"),
            ),
        ),
    )

    class Residency:
        def __init__(self):
            self.released = []

        def acquire(self, request):
            assert request.preferred_tier == "HOT"
            assert request.absent_policy is ResidencyAbsentPolicy.FOLD_DOWN
            return ModelResidencyBinding(
                model_id=request.model_id,
                requested_tier=request.preferred_tier,
                actual_tier="WARM",
                backend_id="dud-residency",
                device_id="opaque-dud-device",
                binding_id="binding-1",
            )

        def release(self, binding):
            self.released.append(binding.binding_id)

    class Executor:
        def execute(self, request, *, residency=None):
            assert isinstance(request, InferenceExecutionRequest)
            assert request.model_id == "FPRM.Samsung_TRM"
            assert request.input_payload[0] == 0
            assert residency is not None
            assert residency.actual_tier == "WARM"
            return InferenceExecutionResult(
                status="SOLVED",
                output_payload=solved,
                iteration_count=1,
                backend_id="dud-executor",
                device_id="opaque-dud-device",
                residency_tier=residency.actual_tier,
            )

    residency = Residency()
    executor = Executor()

    monkeypatch.setattr(
        feedback,
        "solve_sudoku",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("direct model execution must not be reached")
        ),
    )

    traversal = feedback.execute_samsung_feedback_step(
        run_id="port-injection",
        refinement_step_index=0,
        prior_proposal=solved,
        diagnostic=diagnostic,
        reverse_trace=reverse_trace,
        clamp_state=state,
        release_bindings=bindings,
        immutable_givens=(0,) * 81,
        execution_port=executor,
        residency_port=residency,
    )

    assert traversal.learned_status == "SOLVED"
    assert traversal.learned_solution == solved
    assert traversal.released_cells == (0,)
    assert traversal.model_input_changed_cells == (0,)
    assert residency.released == ["binding-1"]
