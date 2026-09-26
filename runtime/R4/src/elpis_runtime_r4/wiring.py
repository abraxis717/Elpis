"""Qualified-inactive EvolutionPathGate -> Darwinian episode composition.

This module owns no semantic, mutation, model, token, selection, heredity, or
runtime-admission authority.  It performs one placement operation only: the
already-qualified EvolutionPathGate is evaluated immediately before the
already-existing DarwinianMatrix episode transaction.
"""
from __future__ import annotations

from typing import Any

from elpis_evolution_path_gate import (
    EvolutionPathAssertion,
    EvolutionPathGate,
    GateExecuted,
    GateRejected,
)

PROFILE = "EVOLUTION_PATH_DARWINIAN_GUARDED_ATTEMPT_R0"
RUNTIME_ADMISSION = False


def execute_guarded_darwinian_attempt(
    *,
    gate: EvolutionPathGate,
    assertion: EvolutionPathAssertion,
    projection: Any,
    state: Any,
    random_seed: int,
    adapter: Any,
    target_viability: float,
    neighbors: Any,
    config: Any | None = None,
    region_map: Any | None = None,
    epsilon: float = 1e-3,
    window: int = 4,
) -> GateRejected | GateExecuted:
    """Evaluate one path assertion and, only if admitted, advance once.

    The Darwinian import is intentionally lazy. Importing R4 does not import
    Torch or construct Darwinian/FPRM/model state. EvolutionPathGate remains the
    sole path-precondition authority and DarwinianMatrix remains the sole owner
    of the episode transaction itself.
    """
    from DarwinianMatrix.controller.episode import advance_episode

    return gate.execute(
        assertion=assertion,
        state=state,
        projection=projection,
        advance=advance_episode,
        advance_kwargs={
            "random_seed": random_seed,
            "adapter": adapter,
            "target_viability": target_viability,
            "neighbors": neighbors,
            "config": config,
            "region_map": region_map,
            "epsilon": epsilon,
            "window": window,
        },
    )
