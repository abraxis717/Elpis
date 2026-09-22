"""Atomic value-state target orchestration and canonical, replayable receipts."""
from collections import deque
from dataclasses import dataclass,replace
from time import perf_counter_ns
import numpy as np
from elpis.inference.context import Snapshot
from elpis.inference.contracts import Code,InferenceError,identity,integer,require
from elpis.inference.neural import LatentInput,NeuralState,StepReceipt
from elpis.inference.prefetch import PrefetchPlan,execute_prefetch,plan_prefetch
from elpis.inference.structural import AddressProposal
from elpis.canonical_identity import CanonicalIdentityError


VALIDATED_STATE_CACHE_LIMIT=1024


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
    step_latents: tuple[tuple[LatentInput,...],...]=()
    step_proposals: tuple[tuple[AddressProposal,...],...]=()

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
        require(all(type(p) is AddressProposal for p in self.proposals),
                Code.INVALID,'proposal packet type')
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
        self._validated_states=set()
        self._validated_state_order=deque()

    def _remember_validated(self,digest):
        if digest in self._validated_states:
            return
        if len(self._validated_state_order)>=VALIDATED_STATE_CACHE_LIMIT:
            evicted=self._validated_state_order.popleft()
            self._validated_states.discard(evicted)
        self._validated_states.add(digest)
        self._validated_state_order.append(digest)

    def initial(self,context):
        require(type(context) is Snapshot)
        state=DecodeState(self.target.initial(context.digest),context)
        self._remember_validated(state.digest)
        return state

    def _validate_request_latents(self,latents):
        require(type(latents) is tuple,Code.INVALID,'latent packet collection')
        for packet in latents:
            require(type(packet) is LatentInput,Code.INVALID,'latent packet type')
            for name in ('channel','source_schema','source','context_snapshot','projection'):
                require(type(getattr(packet,name)) is str,Code.INVALID,'latent packet field')
            require(type(packet.values) is tuple,Code.INVALID,'latent packet values')
            for value in packet.values:
                require(type(value) in (int,float) and type(value) is not bool,
                        Code.INVALID,'latent packet scalar')
                require(bool(np.isfinite(value)),Code.INVALID,'latent packet scalar')

    def _validate_request_proposals(self,proposals,context_snapshot=None):
        require(type(proposals) is tuple,Code.INVALID,'proposal packet collection')
        for proposal in proposals:
            require(type(proposal) is AddressProposal,Code.INVALID,'proposal packet type')
            if context_snapshot is not None:
                require(proposal.context_snapshot==context_snapshot,
                        Code.STALE,'structural snapshot')

    def _validate_receipt_lineage(self,state):
        token_count=len(state.neural.tokens)
        expected_input=self.target.initial(state.context.digest).digest
        require(len(state.receipts)==token_count,Code.STALE,'receipt/token lineage')
        require(len(state.step_latents)==token_count,Code.STALE,'receipt latent-input lineage')
        require(len(state.step_proposals)==token_count,Code.STALE,'receipt proposal-input lineage')
        require(len(state.prefetch)==token_count,Code.STALE,'prefetch/token lineage')
        expected_structural=()
        for step,(token,receipt,latents,proposals,plan) in enumerate(zip(
            state.neural.tokens,state.receipts,state.step_latents,
            state.step_proposals,state.prefetch,strict=True
        )):
            require(type(receipt) is StepReceipt,Code.IDENTITY,'receipt type')
            require(receipt.model==self.target.model_identity,Code.IDENTITY,'receipt model')
            require(receipt.tokenizer==self.target.config.tokenizer,Code.IDENTITY,'receipt tokenizer')
            require(receipt.context_snapshot==state.context.digest,Code.STALE,'receipt context lineage')
            require(receipt.token==token,Code.IDENTITY,'receipt token lineage')
            require(receipt.input_state==expected_input,Code.STALE,'receipt input lineage')
            self._validate_request_latents(latents)
            self._validate_request_proposals(proposals,state.context.digest)
            require(type(plan) is PrefetchPlan,Code.IDENTITY,'prefetch plan type')
            expected_plan=plan_prefetch(
                committed_state=receipt.input_state,
                context_snapshot=state.context.digest,
                step=step,
                proposals=proposals,
                catalog=self.prefetch_catalog,
            )
            require(plan==expected_plan,Code.IDENTITY,'prefetch replay provenance')
            expected_structural=proposals
            expected_input=receipt.output_state
        require(expected_input==state.neural.digest,Code.STALE,'receipt output lineage')
        require(state.structural==expected_structural,Code.IDENTITY,'structural replay provenance')
        if state.digest in self._validated_states:
            return
        replayed=self.target.initial(state.context.digest)
        for token,receipt,latents in zip(
            state.neural.tokens,state.receipts,state.step_latents,strict=True
        ):
            replayed,expected_receipt=self.target.step(
                replayed,token,expected_state=replayed.digest,latents=latents
            )
            require(expected_receipt==receipt,Code.IDENTITY,'receipt provenance')
        require(replayed==state.neural,Code.IDENTITY,'neural replay provenance')
        self._remember_validated(state.digest)

    def _validate(self,state,request):
        self._validate_request_latents(request.latents)
        self._validate_request_proposals(request.proposals,state.context.digest)
        require(state.neural.context_snapshot==state.context.digest==request.context_snapshot,
                Code.STALE,'runtime context snapshot')
        require(state.neural.model==self.target.model_identity,Code.IDENTITY,'runtime model')
        self._validate_receipt_lineage(state)

    def _advance_validated(self,state,token,request,*,prefetch_enabled=False):
        plan=plan_prefetch(
            committed_state=state.neural.digest,
            context_snapshot=state.context.digest,
            step=len(state.neural.tokens),
            proposals=request.proposals,
            catalog=self.prefetch_catalog,
        )
        prefetch_results=()
        if prefetch_enabled:
            prefetch_results=execute_prefetch(
                self.target.rows.provider,plan,state=state.neural.digest,
                context_snapshot=state.context.digest,step=len(state.neural.tokens)
            )
        neural,receipt=self.target.step(
            state.neural,token,expected_state=state.neural.digest,latents=request.latents
        )
        out=DecodeState(
            neural=neural,
            context=state.context,
            structural=request.proposals,
            prefetch=state.prefetch+(plan,),
            receipts=state.receipts+(receipt,),
            step_latents=state.step_latents+(request.latents,),
            step_proposals=state.step_proposals+(request.proposals,),
        )
        return out,dict(target=dict(self.target.last_metrics),prefetch=prefetch_results)

    def advance(self,state,token,request,*,prefetch_enabled=False):
        self._validate(state,request)
        return self._advance_validated(state,token,request,prefetch_enabled=prefetch_enabled)

    def _failure_request_identity(self,request):
        try:
            return request.digest
        except Exception:
            def stable(value):
                if value is None or type(value) in (str,int,bool):
                    return value
                if type(value) is float and bool(np.isfinite(value)):
                    return value
                return {'type':type(value).__module__+'.'+type(value).__qualname__}
            latents=request.latents if type(request.latents) is tuple else ()
            proposals=request.proposals if type(request.proposals) is tuple else ()
            tokens=request.tokens if type(request.tokens) is tuple else ()
            return identity(
                'r3.invalid-request',
                dict(
                    request_id=stable(request.request_id),
                    context_snapshot=stable(request.context_snapshot),
                    mode=stable(request.mode),
                    token_count=len(tokens),
                    count=stable(request.count),
                    proposal_count=len(proposals),
                    proposal_types=tuple(
                        type(packet).__module__+'.'+type(packet).__qualname__
                        for packet in proposals
                    ),
                    latent_types=tuple(
                        type(packet).__module__+'.'+type(packet).__qualname__
                        for packet in latents
                    ),
                ),
            )

    def _receipt_structural(self,request):
        proposals=request.proposals if type(request.proposals) is tuple else ()
        result=[]
        for index,proposal in enumerate(proposals):
            if type(proposal) is AddressProposal:
                try:
                    result.append(proposal.digest)
                    continue
                except Exception:
                    pass
            result.append(identity(
                'r3.invalid-proposal',
                dict(index=index,type=type(proposal).__module__+'.'+type(proposal).__qualname__),
            ))
        return tuple(result)

    def receipt(self,request,before,after,*,draft=None,accepted=(),failure=None,
                request_identity=None):
        steps=after.receipts[len(before.receipts):]
        if request_identity is None:
            try:
                request_digest=request.digest
            except Exception:
                request_digest=self._failure_request_identity(request)
        else:
            request_digest=request_identity
        return RuntimeReceipt(
            request_digest,'elpis.runtime.r3.r1',self.target.model_identity,
            self.target.config.tokenizer,before.digest,before.context.digest,
            self._receipt_structural(request),steps,draft,accepted,after.digest,
            'COMMITTED' if failure is None else 'FAILED',failure
        )

    def execute(self,state,request,*,expected_state,prefetch_enabled=False):
        overlay=state; telemetry=[]
        try:
            base_digest=state.digest
            self._validate_request_latents(request.latents)
            self._validate_request_proposals(request.proposals)
            request_digest=request.digest
            require(base_digest==expected_state,Code.STALE,'runtime committed base')
            self._validate(state,request)
            if request.mode=='GREEDY':
                require(bool(state.neural.logits),detail='greedy generation needs prefill')
            count=len(request.tokens) if request.mode=='PREFILL' else request.count
            for i in range(count):
                token=request.tokens[i] if request.mode=='PREFILL' else int(np.argmax(overlay.neural.logits))
                overlay,metrics=self._advance_validated(
                    overlay,token,request,prefetch_enabled=prefetch_enabled
                )
                telemetry.append(metrics)
        except InferenceError as exc:
            return RuntimeResult(
                state,
                self.receipt(
                    request,state,state,failure=exc.code.value,
                    request_identity=self._failure_request_identity(request),
                ),
                tuple(telemetry),
            )
        except Exception as exc:
            raise typed_failure(exc) from exc
        start=perf_counter_ns()
        receipt=self.receipt(
            request,state,overlay,
            accepted=overlay.neural.tokens[len(state.neural.tokens):]
        )
        telemetry.append(dict(commit_ns=perf_counter_ns()-start))
        self._remember_validated(overlay.digest)
        return RuntimeResult(overlay,receipt,tuple(telemetry))

    def replay(self,state,request,receipt):
        result=self.execute(state,request,expected_state=state.digest)
        require(result.receipt==receipt,Code.IDENTITY,'runtime replay mismatch')
        return result
