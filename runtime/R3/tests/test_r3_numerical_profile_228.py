from __future__ import annotations
from dataclasses import replace
from elpis.inference.context import initial_snapshot
from elpis_runtime_r3 import InferenceRequest, RuntimeR3

def test_fresh_runtime_accepts_matching_numerical_profile(target):
    rt=RuntimeR3(target[0]); state=rt.initial(initial_snapshot())
    committed=rt.execute(
        state,InferenceRequest("p",state.context.digest,"PREFILL",(1,2,3)),
        expected_state=state.digest
    ).state
    restarted=RuntimeR3(target[0])
    result=restarted.execute(
        committed,InferenceRequest("g",committed.context.digest,"GREEDY",count=1),
        expected_state=committed.digest
    )
    assert result.receipt.terminal=="COMMITTED"

def test_fresh_runtime_rejects_mismatched_numerical_profile_before_replay(target):
    rt=RuntimeR3(target[0]); state=rt.initial(initial_snapshot())
    committed=rt.execute(
        state,InferenceRequest("p",state.context.digest,"PREFILL",(1,2,3)),
        expected_state=state.digest
    ).state
    forged=replace(committed,neural=replace(committed.neural,numerical_profile="0"*64))
    restarted=RuntimeR3(target[0])
    result=restarted.execute(
        forged,InferenceRequest("g",forged.context.digest,"GREEDY",count=1),
        expected_state=forged.digest
    )
    assert result.state==forged
    assert result.receipt.terminal=="FAILED"
    assert result.receipt.failure=="UNSUPPORTED"
    assert forged.digest not in restarted._validated_states
