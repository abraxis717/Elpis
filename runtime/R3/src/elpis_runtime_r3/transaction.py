"""Atomic value-state target orchestration and canonical, replayable receipts."""
from dataclasses import dataclass,replace
from time import perf_counter_ns
import numpy as np
from elpis.inference.context import Snapshot
from elpis.inference.contracts import Code,InferenceError,identity,integer,require
from elpis.inference.neural import LatentInput,NeuralState,StepReceipt
from elpis.inference.prefetch import PrefetchPlan,execute_prefetch,plan_prefetch
from elpis.inference.structural import AddressProposal
from elpis.canonical_identity import CanonicalIdentityError


def typed_failure(exc):
    """Map a non-canonical identity error to the typed failure contract.

    A tampered state/request may carry non-canonical values (e.g. NaN floats)
    whose digest raises CanonicalIdentityError. The public contract is that
    every typed failure is an InferenceError; a non-canonical identity is a
    tampered identity. Any other exception is returned unchanged so genuine
    bugs are never swallowed.
    """
    if isinstance(exc, CanonicalIdentityError):
        return InferenceError(Code.IDENTITY, 'non-canonical identity')
    return exc


@dataclass(frozen=True)
class DecodeState:
    neural: NeuralState
    context: Snapshot
    structural: tuple[AddressProposal,...]=()
    prefetch: tuple[PrefetchPlan,...]=()
    receipts: tuple[StepReceipt,...]=()

    @property
    def digest(self): return identity('r3.committed-state',self)


@dataclass(frozen=True)
class InferenceRequest:
    request_id: str
    context_snapshot: str
    mode: str
    tokens: tuple[int,...]=()
    count: int=0
    proposals: tuple[AddressProposal,...]=()
    latents: tuple[LatentInput,...]=()

    def __post_init__(self):
        require(bool(self.request_id) and self.mode in ('PREFILL','GREEDY'))
        require(type(self.tokens) is tuple and type(self.proposals) is tuple and type(self.latents) is tuple)
        integer(self.count)
        require((self.mode=='PREFILL' and self.count==0) or (self.mode=='GREEDY' and not self.tokens),detail='request mode payload')

    @property
    def digest(self): return identity('r3.request',self)


@dataclass(frozen=True)
class RuntimeReceipt:
    request: str
    runtime_schema: str
    model: str
    tokenizer: str
    input_state: str
    context_snapshot: str
    structural: tuple[str,...]
    target_steps: tuple[StepReceipt,...]
    draft: str | None
    accepted_prefix: tuple[int,...]
    output_state: str
    terminal: str
    failure: str | None

    @property
    def digest(self): return identity('r3.receipt',self)


@dataclass(frozen=True)
class RuntimeResult:
    state: DecodeState
    receipt: RuntimeReceipt
    telemetry: tuple[dict,...]


class RuntimeR3:
    """Explicit in-process invocation. No plugin/provider admission or isolation claim."""
    def __init__(self,target,*,prefetch_catalog=None):
        self.target=target
        self.prefetch_catalog={} if prefetch_catalog is None else dict(prefetch_catalog)

    def initial(self,context):
        require(type(context) is Snapshot)
        try:
            return DecodeState(self.target.initial(context.digest),context)
        except InferenceError:
            raise
        except Exception as exc:
            raise typed_failure(exc) from exc

    def _validate_receipt_lineage(self,state):
        expected_input=self.target.initial(state.context.digest).digest
        for token,receipt in zip(state.neural.tokens,state.receipts,strict=True):
            require(type(receipt) is StepReceipt,Code.IDENTITY,'receipt type')
            require(receipt.model==self.target.model_identity,Code.IDENTITY,'receipt model')
            require(receipt.tokenizer==self.target.config.tokenizer,Code.IDENTITY,'receipt tokenizer')
            require(receipt.context_snapshot==state.context.digest,Code.STALE,'receipt context lineage')
            require(receipt.token==token,Code.IDENTITY,'receipt token lineage')
            require(receipt.input_state==expected_input,Code.STALE,'receipt input lineage')
            expected_input=receipt.output_state
        require(expected_input==state.neural.digest,Code.STALE,'receipt output lineage')

    def _validate(self,state,request):
        require(state.neural.context_snapshot==state.context.digest==request.context_snapshot,
                Code.STALE,'runtime context snapshot')
        require(state.neural.model==self.target.model_identity,Code.IDENTITY,'runtime model')
        for p in request.proposals:
            require(type(p) is AddressProposal and p.context_snapshot==state.context.digest,
                    Code.STALE,'structural snapshot')
        require(len(state.receipts)==len(state.neural.tokens),Code.STALE,'receipt/token lineage')
        self._validate_receipt_lineage(state)

    def advance(self,state,token,request,*,prefetch_enabled=False):
        self._validate(state,request)
        plan=plan_prefetch(committed_state=state.neural.digest,context_snapshot=state.context.digest,
                           step=len(state.neural.tokens),proposals=request.proposals,catalog=self.prefetch_catalog)
        prefetch_results=()
        if prefetch_enabled:
            prefetch_results=execute_prefetch(self.target.rows.provider,plan,state=state.neural.digest,
                    context_snapshot=state.context.digest,step=len(state.neural.tokens))
        neural,receipt=self.target.step(state.neural,token,expected_state=state.neural.digest,latents=request.latents)
        out=DecodeState(neural,state.context,request.proposals,state.prefetch+(plan,),state.receipts+(receipt,))
        return out,dict(target=dict(self.target.last_metrics),prefetch=prefetch_results)

    def receipt(self,request,before,after,*,draft=None,accepted=(),failure=None):
        steps=after.receipts[len(before.receipts):]
        return RuntimeReceipt(request.digest,'elpis.runtime.r3.r0',self.target.model_identity,
               self.target.config.tokenizer,before.digest,before.context.digest,
               tuple(p.digest for p in request.proposals),steps,draft,accepted,after.digest,
               'COMMITTED' if failure is None else 'FAILED',failure)

    def execute(self,state,request,*,expected_state,prefetch_enabled=False):
        overlay=state; telemetry=[]
        try:
            # Fail closed on a non-canonical (tampered) identity before any work,
            # so the failure-receipt path below only ever sees canonical digests.
            base_digest=state.digest
            request_digest=request.digest  # noqa: F841  (canonicality gate)
            require(base_digest==expected_state,Code.STALE,'runtime committed base')
            self._validate(state,request)
            if request.mode=='GREEDY': require(bool(state.neural.logits),detail='greedy generation needs prefill')
            count=len(request.tokens) if request.mode=='PREFILL' else request.count
            for i in range(count):
                token=request.tokens[i] if request.mode=='PREFILL' else int(np.argmax(overlay.neural.logits))
                overlay,metrics=self.advance(overlay,token,request,prefetch_enabled=prefetch_enabled)
                telemetry.append(metrics)
        except InferenceError as exc:
            # Physical cache warming may survive failure; semantic state cannot.
            return RuntimeResult(state,self.receipt(request,state,state,failure=exc.code.value),tuple(telemetry))
        except Exception as exc:
            # A non-canonical (tampered) identity must fail closed as a typed
            # identity error, never as an untyped canonicalization error.
            raise typed_failure(exc) from exc
        start=perf_counter_ns()
        receipt=self.receipt(request,state,overlay,accepted=overlay.neural.tokens[len(state.neural.tokens):])
        telemetry.append(dict(commit_ns=perf_counter_ns()-start))
        return RuntimeResult(overlay,receipt,tuple(telemetry))

    def replay(self,state,request,receipt):
        result=self.execute(state,request,expected_state=state.digest)
        require(result.receipt==receipt,Code.IDENTITY,'runtime replay mismatch')
        return result
