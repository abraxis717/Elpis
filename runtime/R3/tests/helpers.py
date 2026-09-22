"""Shared helpers for the R3 qualification suite."""
from __future__ import annotations

from dataclasses import replace

import numpy as np

from elpis_runtime_r3 import InferenceRequest, RuntimeR3
from elpis_runtime_r3.speculative import Draft, MarkovDrafter
from elpis.inference.context import initial_snapshot
from elpis.inference.neural import Tensor


def build_runtime(target):
    return RuntimeR3(target)


def prefill(rt, state, tokens=(1, 2, 3), tag="prefill"):
    req = InferenceRequest(tag, state.context.digest, "PREFILL", tokens)
    out = rt.execute(state, req, expected_state=state.digest)
    assert out.receipt.terminal == "COMMITTED"
    return out.state


def greedy(rt, state, count=1, tag="greedy"):
    req = InferenceRequest(tag, state.context.digest, "GREEDY", count=count)
    return rt.execute(state, req, expected_state=state.digest)


def make_drafter(rt, state, seed=61):
    rng = np.random.default_rng(seed)
    def t(shape):
        return Tensor(shape, (rng.normal(size=shape) * 0.1).astype("<f4").tobytes())
    return MarkovDrafter(
        target_model=rt.target.model_identity,
        hidden_projection=t((4, 16)),
        token_embedding=t((16, 2)),
        markov_projection=t((2, 16)),
        confidence_head=t((4, 1)),
    )


def nan_state(state):
    """Return a tampered state whose neural hidden carries a NaN float."""
    return replace(state, neural=replace(state.neural, hidden=(float("nan"),) + state.neural.hidden[1:]))
