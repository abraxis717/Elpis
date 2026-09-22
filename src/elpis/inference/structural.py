"""Consumption adapters for existing proposal surfaces; no reverse imports.

Regex/HACF's legacy proposal digest is preserved as provenance. A pinned raw
export digest and current source/corpus/overlay identities bind transport;
new records use Elpis canonical identity. Confidence never grants authority.
"""
from dataclasses import dataclass
import json
import math
from .contracts import Code, ProposalOnly, digest_value, identity, require
from .file_assets import raw_digest


@dataclass(frozen=True)
class RouteRule:
    key: str
    banks: tuple[str,...]=()
    expert_families: tuple[str,...]=()


@dataclass(frozen=True)
class AddressProposal(ProposalOnly):
    source: str
    regex_result: str
    corpus: str
    context_snapshot: str
    query_overlay: str
    route_key: str
    banks: tuple[str,...]
    objects: tuple[str,...]
    expert_families: tuple[str,...]
    confidence: float | None
    provenance: tuple[str,...]

    def __post_init__(self):
        for d in (self.source,self.regex_result,self.corpus,self.context_snapshot,self.query_overlay): digest_value(d)
        require(self.confidence is None or
                (type(self.confidence) in (int,float) and type(self.confidence) is not bool and
                 math.isfinite(self.confidence) and 0<=self.confidence<=1))
        require(bool(self.route_key))
        for values in (self.banks,self.objects,self.expert_families,self.provenance):
            require(type(values) is tuple and all(type(x) is str and bool(x) for x in values))

    @property
    def digest(self): return identity('structural-address',self)


def _strict_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: '+str(key))
        result[key]=value
    return result


def _reject_constant(value):
    raise ValueError('non-finite JSON constant: '+value)


def from_regex_hacf(payload,*,expected_payload,expected_source,expected_corpus,
                    context_snapshot,query_overlay,rules):
    require(type(payload) is bytes and len(payload)<=4<<20,detail='bounded ingress export')
    require(raw_digest(payload)==expected_payload,Code.IDENTITY,'ingress transport digest')
    try:
        result=json.loads(payload,object_pairs_hook=_strict_object,parse_constant=_reject_constant)
    except (ValueError,UnicodeError) as exc:
        from .contracts import InferenceError
        raise InferenceError(Code.INVALID,'ingress JSON') from exc
    require(type(result) is dict and result.get('schema')=='elpis.regex-hacf-context-proposal.r1',detail='ingress schema')
    for authority in ('semantic_authority','admission_authority','execution_authority','runtime_admission'):
        require(result.get(authority) is False,Code.IDENTITY,'ingress authority widening')
    require(result.get('candidate_status')=='PROPOSED_UNADMITTED',Code.IDENTITY,'ingress status')
    require(result.get('source_sha256')==expected_source,Code.IDENTITY,'ingress source')
    proposal_digest=result.get('proposal_digest')
    digest_value(proposal_digest)
    hacf=result.get('hacf')
    require(type(hacf) is dict and hacf.get('corpus_manifest_digest')==expected_corpus,Code.STALE,'HACF corpus')
    graph_digest=hacf.get('context_graph_manifest_digest')
    digest_value(graph_digest)
    retrieval=hacf.get('retrieval')
    require(type(retrieval) is list and len(retrieval)<=1024,detail='bounded retrieval proposals')
    require(type(rules) is tuple and all(type(r) is RouteRule for r in rules))
    rule_map={r.key:r for r in rules}
    require(len(rule_map)==len(rules),detail='duplicate structural rule')
    rule_identity=identity('structural-rules',rules)
    proposals=[]
    for row in retrieval:
        require(type(row) is dict and type(row.get('pattern_id')) is str,detail='structural route')
        key=row['pattern_id']; rule=rule_map.get(key,RouteRule(key))
        hits=row.get('hacf_primary_hits')
        require(type(hits) is list and len(hits)<=1024,detail='bounded HACF candidates')
        objects=[]
        for hit in hits:
            require(type(hit) is dict,detail='HACF candidate')
            objects.append(digest_value(hit.get('chunk_digest')))
        proposals.append(AddressProposal(expected_source,proposal_digest,expected_corpus,
                         context_snapshot,query_overlay,key,rule.banks,tuple(objects),rule.expert_families,
                         None,(expected_payload,rule_identity,graph_digest)))
    return tuple(proposals)
