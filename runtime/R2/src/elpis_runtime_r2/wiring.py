"""Thin authority-preserving wrapper around the qualified feedback traversal."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from .receipt import R2FeedbackRuntimeReceipt

RUNTIME_ADMISSION = False


def execute_feedback_transaction(
    *,
    run_id: str,
    refinement_step_index: int,
    prior_proposal: Sequence[int],
    diagnostic: Any,
    reverse_trace: Any,
    clamp_state: Any,
    release_bindings: Any,
    immutable_givens: Sequence[int],
    evidence_slots: Sequence[Any] = (),
    model_path: Path | None = None,
    device: str = "auto",
    max_model_steps: int = 1000,
) -> R2FeedbackRuntimeReceipt:
    """Execute exactly one already-authorized bounded feedback traversal.

    This wrapper does not derive semantic, trace, release-binding, or immutable-
    given authority. Callers must provide those objects explicitly.

    Imports of the learned feedback path are deliberately lazy so importing the
    R2 package itself never makes Torch a base dependency.
    """
    from elpis_reference.feedback_refinement import (
        execute_samsung_feedback_step,
        samsung_proposal_digest,
    )

    traversal = execute_samsung_feedback_step(
        run_id=run_id,
        refinement_step_index=refinement_step_index,
        prior_proposal=prior_proposal,
        diagnostic=diagnostic,
        reverse_trace=reverse_trace,
        clamp_state=clamp_state,
        release_bindings=release_bindings,
        immutable_givens=immutable_givens,
        evidence_slots=evidence_slots,
        model_path=model_path,
        device=device,
        max_model_steps=max_model_steps,
    )

    learned_solution_digest = (
        samsung_proposal_digest(traversal.learned_solution)
        if traversal.learned_solution is not None
        else None
    )

    return R2FeedbackRuntimeReceipt.create(
        run_id=traversal.run_id,
        refinement_step_index=traversal.refinement_step_index,
        prior_proposal_digest=traversal.prior_proposal_digest,
        diagnostic_digest=traversal.diagnostic_digest,
        residual_digest=traversal.residual_digest,
        resolution_digest=traversal.resolution_digest,
        release_binding_table_digest=traversal.release_binding_table_digest,
        immutable_givens_digest=traversal.immutable_givens_digest,
        release_plan_digest=traversal.release_plan_digest,
        release_transaction_digest=traversal.release_transaction_digest,
        clamp_state_before_digest=traversal.clamp_state_before_digest,
        clamp_state_after_digest=traversal.clamp_state_after_digest,
        released_cells=tuple(traversal.released_cells),
        model_input_changed_cells=tuple(
            traversal.model_input_changed_cells
        ),
        learned_status=traversal.learned_status,
        learned_solution_digest=learned_solution_digest,
        learned_iteration_count=traversal.learned_iteration_count,
        traversal_digest=traversal.traversal_digest,
    )
