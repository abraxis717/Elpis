from __future__ import annotations

import hashlib
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
R3_SRC = ROOT / 'runtime' / 'R3' / 'src'
if str(R3_SRC) not in sys.path:
    sys.path.insert(0, str(R3_SRC))

from elpis.inference.contracts import identity
from elpis_runtime_r1.contracts import RetrievalBundle, RetrievalItem
from elpis_runtime_r1.errors import R1BundleValidationError
from elpis_runtime_r3.r1_adapter import from_r1_bundle


def _bundle():
    text = 'retrieved evidence'
    item = RetrievalItem(
        chunk_digest='6' * 64,
        doc_digest='7' * 64,
        namespace='fixture',
        authority='fixture',
        graph_parent_digest='0' * 64,
        text_digest=hashlib.sha256(text.encode()).hexdigest(),
        fusion_score_key=1,
        dense_score_key=1,
        lexical_rank=1,
        dense_rank=1,
        final_rank=0,
        source_mask=3,
        item_kind=1,
        graph_hop=0,
        edge_type=0,
        edge_authority=0,
        text=text,
        text_bytes=len(text.encode()),
    )
    return RetrievalBundle(
        query_digest='1' * 64,
        corpus_manifest_digest='2' * 64,
        vector_index_manifest_digest='3' * 64,
        graph_snapshot_digest='4' * 64,
        fusion_policy_digest='5' * 64,
        bundle_digest='8' * 64,
        hacf_package_digest='9' * 64,
        corpus_epoch=1,
        vector_index_epoch=1,
        items=(item,),
    )


def test_r1_adapter_preserves_r1_validation_and_proposal_only_boundary():
    bundle = _bundle()
    export = identity('r1-bundle-export', bundle.to_canonical_dict())
    proposal = from_r1_bundle(
        bundle,
        expected_query=bundle.query_digest,
        expected_corpus=bundle.corpus_manifest_digest,
        expected_bundle=export,
        context_snapshot='a' * 64,
        query_overlay='b' * 64,
    )
    assert proposal.route_key == 'HACF_R1'
    assert proposal.objects == ('6' * 64,)
    assert proposal.provenance == (
        export,
        bundle.graph_snapshot_digest,
        bundle.hacf_package_digest,
    )
    assert not proposal.semantic_authority
    assert not proposal.execution_authority
    assert not proposal.runtime_admission


def test_r1_adapter_does_not_bypass_r1_validation():
    bundle = _bundle()
    export = identity('r1-bundle-export', bundle.to_canonical_dict())
    with pytest.raises(R1BundleValidationError, match='QUERY_DIGEST_MISMATCH'):
        from_r1_bundle(
            bundle,
            expected_query='0' * 64,
            expected_corpus=bundle.corpus_manifest_digest,
            expected_bundle=export,
            context_snapshot='a' * 64,
            query_overlay='b' * 64,
        )
