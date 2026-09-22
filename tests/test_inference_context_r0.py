from dataclasses import replace
import pytest
from elpis.inference.context import *
from elpis.inference.contracts import InferenceError


def populated():
    s=initial_snapshot()
    for i in range(4):
        item=ContextItem(str(i),'canonical-evidence',str(i).encode(),Lifetime.DYNAMIC)
        s=append_context(s,item,expected=s.digest)
    return s


def test_compaction_preserves_canonical_evidence_and_forks():
    s=populated()
    summary=ContextItem('summary','tiny-model',b'lossy',Lifetime.DYNAMIC)
    out,record=compact_context(s,0,2,summary,expected=s.digest,replacement_digest=summary.digest,policy='fixture-v1',reason='bounded context')
    verify_compaction(s,out,record)
    assert out.canonical==s.canonical and out.visible[0]==summary
    fork=fork_context(out,'child',expected=out.digest)
    item=ContextItem('temporary','tool',b'data',Lifetime.EPHEMERAL)
    child=append_context(fork,item,expected=fork.digest)
    assert child.visible!=out.visible and out.digest==record.output_snapshot
    retired=retire_context(child,'temporary',expected=child.digest,reason='turn end')
    assert retired.visible==out.visible and retired.canonical[-1]==item


def test_context_planted_defects():
    s=populated(); replacement=ContextItem('summary','model',b'lossy',Lifetime.DYNAMIC)
    with pytest.raises(InferenceError,match='STALE'): append_context(s,replacement,expected='0'*64)
    with pytest.raises(InferenceError,match='overwrite'): append_context(s,s.canonical[0],expected=s.digest)
    with pytest.raises(InferenceError): retire_context(s,'0',expected=s.digest,reason='attempt')
    for bounds in [(-1,2),(2,1),(0,5)]:
        with pytest.raises(InferenceError):
            compact_context(s,*bounds,replacement,expected=s.digest,replacement_digest=replacement.digest,policy='p',reason='r')
    with pytest.raises(InferenceError,match='replacement'):
        compact_context(s,0,2,replacement,expected=s.digest,replacement_digest='0'*64,policy='p',reason='r')
    out,rec=compact_context(s,0,2,replacement,expected=s.digest,replacement_digest=replacement.digest,policy='p',reason='r')
    for mutated in [replace(rec,input_snapshot='0'*64),replace(rec,replacement='0'*64),replace(rec,preserved=())]:
        with pytest.raises(InferenceError): verify_compaction(s,out,mutated)
    assert not replacement.semantic_authority and not out.mutation_authority
    with pytest.raises((AttributeError,TypeError)):
        object.__setattr__(out,'semantic_authority',True)


def test_compaction_verifier_binds_entire_output_snapshot():
    s=populated()
    replacement=ContextItem('summary-x','model',b'lossy',Lifetime.DYNAMIC)
    out,record=compact_context(
        s,1,3,replacement,expected=s.digest,replacement_digest=replacement.digest,
        policy='p',reason='r'
    )
    verify_compaction(s,out,record)
    for mutated in (
        replace(out,branch='forged'),
        replace(out,generation=out.generation+1),
        replace(out,retired=('forged',)),
    ):
        with pytest.raises(InferenceError):
            verify_compaction(s,mutated,replace(record,output_snapshot=mutated.digest))
