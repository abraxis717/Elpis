from __future__ import annotations

from dataclasses import fields
import importlib.util
import inspect
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
R2_SRC = ROOT / "runtime" / "R2" / "src"
if str(R2_SRC) not in sys.path:
    sys.path.insert(0, str(R2_SRC))

import elpis_runtime_r2
from elpis_runtime_r2 import R2FeedbackRuntimeReceipt
from elpis_runtime_r2.wiring import execute_feedback_transaction


REQUIRED_RECEIPT_FIELDS = (
    "schema",
    "profile",
    "run_id",
    "refinement_step_index",
    "prior_proposal_digest",
    "diagnostic_digest",
    "residual_digest",
    "resolution_digest",
    "release_binding_table_digest",
    "immutable_givens_digest",
    "release_plan_digest",
    "release_transaction_digest",
    "clamp_state_before_digest",
    "clamp_state_after_digest",
    "released_cells",
    "model_input_changed_cells",
    "learned_status",
    "learned_solution_digest",
    "learned_iteration_count",
    "traversal_digest",
    "runtime_receipt_digest",
)


def _receipt():
    return R2FeedbackRuntimeReceipt.create(
        run_id="r2-test",
        refinement_step_index=0,
        prior_proposal_digest="a" * 64,
        diagnostic_digest="b" * 64,
        residual_digest="c" * 64,
        resolution_digest="d" * 64,
        release_binding_table_digest="e" * 64,
        immutable_givens_digest="f" * 64,
        release_plan_digest="1" * 64,
        release_transaction_digest="2" * 64,
        clamp_state_before_digest="3" * 64,
        clamp_state_after_digest="4" * 64,
        released_cells=(0,),
        model_input_changed_cells=(0,),
        learned_status="SOLVED",
        learned_solution_digest="5" * 64,
        learned_iteration_count=1,
        traversal_digest="6" * 64,
    )


def test_r2_import_is_torch_lazy_and_admission_false():
    code = (
        "import sys;"
        f"sys.path.insert(0,{str(R2_SRC)!r});"
        "import elpis_runtime_r2;"
        "print('torch_loaded='+str('torch' in sys.modules));"
        "print('admission='+str(elpis_runtime_r2.RUNTIME_ADMISSION))"
    )
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.returncode == 0, proc.stderr
    assert "torch_loaded=False" in proc.stdout
    assert "admission=False" in proc.stdout


def test_r2_api_requires_prebound_authorities_and_has_no_raw_prompt():
    signature = inspect.signature(execute_feedback_transaction)
    names = tuple(signature.parameters)
    for required in (
        "diagnostic",
        "reverse_trace",
        "clamp_state",
        "release_bindings",
        "immutable_givens",
    ):
        assert required in names
    forbidden = {"prompt", "raw_prompt", "text", "query"}
    assert forbidden.isdisjoint(names)


def test_r2_receipt_schema_is_exact_and_deterministic():
    names = tuple(field.name for field in fields(R2FeedbackRuntimeReceipt))
    assert names == REQUIRED_RECEIPT_FIELDS
    a = _receipt()
    b = _receipt()
    assert a == b
    assert a.verify()
    assert b.verify()
    assert a.runtime_receipt_digest == b.runtime_receipt_digest
    assert a.to_canonical_json() == b.to_canonical_json()


def test_r2_namespace_exposes_no_writer_or_admission_mutator():
    public = set(elpis_runtime_r2.__all__)
    assert public == {
        "PROFILE",
        "RUNTIME_ADMISSION",
        "SCHEMA",
        "R2FeedbackRuntimeReceipt",
        "execute_feedback_transaction",
    }


def test_r2_pyproject_has_no_torch_or_root_install_mutation():
    text = (ROOT / "runtime" / "R2" / "pyproject.toml").read_text()
    assert 'dependencies = []' in text
    assert "torch" not in text.lower()

    root_pyproject = (ROOT / "pyproject.toml").read_text()
    assert "runtime/R2/src" not in root_pyproject
    assert "elpis_runtime_r2" not in root_pyproject


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is None,
    reason="R2 integration execution requires optional torch dependency",
)
def test_r2_wrapper_preserves_real_feedback_traversal(monkeypatch):
    import hashlib

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
    from elpis_reference.refinement import RefinementResult, RefinementStep
    from elpis_reference.semantic_refinement import (
        SEMANTIC_OBJECT,
        ReverseTraceIndex,
        StructuralObservationRecord,
        TaskDiagnosticV1,
        TASK_REJECTION,
    )

    solved = tuple(
        int(v)
        for v in (
            "534678912672195348198342567859761423426853791713924856"
            "961537284287419635345286179"
        )
    )

    def h(text):
        return hashlib.sha256(text.encode()).hexdigest()

    state = ClampState.empty("r2-feedback-episode")
    tx = ClampTransaction(
        transaction_id="initial",
        episode_id=state.episode_id,
        expected_state_digest=state.digest(),
        proposals=(
            ClampProposal(
                proposal_id="assert-0",
                operation=ClampOperation.ASSERT,
                slot_id="slot-0",
                evidence_digest=h("evidence-0"),
                cell_index=0,
                value=solved[0],
            ),
        ),
    )
    applied = apply_clamp_transaction(state=state, transaction=tx)
    assert applied.accepted
    state = applied.state

    diagnostic = TaskDiagnosticV1(
        diagnostic_class=TASK_REJECTION,
        task_scope_id=state.episode_id,
        frame_index=0,
        subject_digest=feedback.samsung_proposal_digest(solved),
        producer_id="r2.test.validator.v1",
        locus_namespace=SEMANTIC_OBJECT,
        locus_identity=h("semantic-cell-0"),
        reason_codes=("TASK_REQUIREMENT_UNSATISFIED",),
        details_digest=h("details"),
    )
    reverse_trace = ReverseTraceIndex(
        (
            StructuralObservationRecord.create(
                source_semantic_object_digest=h("semantic-cell-0"),
                topology_vertex_digest=h("topology-0"),
                P7_capsule_digest=h("capsule-0"),
                P7_primary_cell_index=0,
            ),
        )
    )
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

    def fake_solver(puzzle, model_path=None, device="auto", max_steps=16):
        assert puzzle[0] == 0
        return RefinementResult(
            status="SOLVED",
            solution=solved,
            steps=(
                RefinementStep(
                    step=1,
                    valid=True,
                    complete=True,
                    conflicts=(),
                    proposal=solved,
                ),
            ),
            device="cpu",
        )

    monkeypatch.setattr(feedback, "solve_sudoku", fake_solver)

    receipt = execute_feedback_transaction(
        run_id="r2-run",
        refinement_step_index=0,
        prior_proposal=solved,
        diagnostic=diagnostic,
        reverse_trace=reverse_trace,
        clamp_state=state,
        release_bindings=bindings,
        immutable_givens=(0,) * 81,
        device="cpu",
        max_model_steps=4,
    )

    assert receipt.verify()
    assert receipt.profile == "SUDOKU_FEEDBACK_V1"
    assert receipt.released_cells == (0,)
    assert receipt.model_input_changed_cells == (0,)
    assert receipt.learned_status == "SOLVED"
    assert receipt.learned_solution_digest == feedback.samsung_proposal_digest(solved)


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is None,
    reason="R2 negative execution checks require optional torch dependency",
)
def test_r2_structural_rejection_fails_before_model(monkeypatch):
    import hashlib

    import elpis_reference.feedback_refinement as feedback
    from DarwinianMatrix.projector.constraints import ClampState
    from elpis_reference.projector_release import ReleaseBindingTableV1
    from elpis_reference.semantic_refinement import (
        SEMANTIC_OBJECT,
        ReverseTraceIndex,
        STRUCTURAL_REJECTION,
        TaskDiagnosticV1,
    )

    solved = tuple(
        int(v)
        for v in (
            "534678912672195348198342567859761423426853791713924856"
            "961537284287419635345286179"
        )
    )
    h = lambda text: hashlib.sha256(text.encode()).hexdigest()
    state = ClampState.empty("r2-reject-episode")
    diagnostic = TaskDiagnosticV1(
        diagnostic_class=STRUCTURAL_REJECTION,
        task_scope_id=state.episode_id,
        frame_index=0,
        subject_digest=feedback.samsung_proposal_digest(solved),
        producer_id="r2.test.validator.v1",
        locus_namespace=SEMANTIC_OBJECT,
        locus_identity=h("semantic-cell-0"),
        reason_codes=("STRUCTURAL_REJECTION",),
        details_digest=h("details"),
    )
    bindings = ReleaseBindingTableV1(
        episode_id=state.episode_id,
        clamp_state_digest=state.digest(),
        targets=(),
    )

    monkeypatch.setattr(
        feedback,
        "solve_sudoku",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("model must not run")
        ),
    )

    with pytest.raises(
        ValueError,
        match="structural rejection cannot become a task residual",
    ):
        execute_feedback_transaction(
            run_id="r2-reject",
            refinement_step_index=0,
            prior_proposal=solved,
            diagnostic=diagnostic,
            reverse_trace=ReverseTraceIndex(()),
            clamp_state=state,
            release_bindings=bindings,
            immutable_givens=(0,) * 81,
        )
