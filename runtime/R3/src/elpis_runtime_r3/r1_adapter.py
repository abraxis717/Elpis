"""Runtime-R1 retrieval adapter for experimental Runtime R3.

The independent `elpis.inference` primitive package does not import Runtime R1.
R1-specific validation remains at this orchestration boundary.
"""
from __future__ import annotations

from elpis.inference.contracts import Code, identity, require
from elpis.inference.structural import AddressProposal
from elpis_runtime_r1.bundle_validation import validate_bundle
from elpis_runtime_r1.budget import RetrievalBudget


def from_r1_bundle(
    bundle,
    *,
    expected_query,
    expected_corpus,
    expected_bundle,
    context_snapshot,
    query_overlay,
):
    validate_bundle(
        bundle,
        expected_query,
        expected_corpus,
        RetrievalBudget(),
    )
    require(
        identity('r1-bundle-export', bundle.to_canonical_dict()) == expected_bundle,
        Code.IDENTITY,
        'R1 export pin',
    )
    return AddressProposal(
        expected_query,
        bundle.bundle_digest,
        expected_corpus,
        context_snapshot,
        query_overlay,
        'HACF_R1',
        (),
        tuple(item.chunk_digest for item in bundle.items),
        (),
        0.5,
        (
            expected_bundle,
            bundle.graph_snapshot_digest,
            bundle.hacf_package_digest,
        ),
    )
