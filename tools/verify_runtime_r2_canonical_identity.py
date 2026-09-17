#!/usr/bin/env python3
"""Verify R2 receipt identity convergence and historical v1 compatibility."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for source_root in (ROOT / "src", ROOT / "runtime" / "R2" / "src"):
    value = str(source_root)
    if value not in sys.path:
        sys.path.insert(0, value)

from elpis.canonical_identity import canonical_json_bytes, content_digest
import elpis_runtime_r2.receipt as receipt_mod
from elpis_runtime_r2 import R2FeedbackRuntimeReceipt, SCHEMA

LEGACY_VECTOR = "a6b1c921b0de496fb6f3026e671c57d2b025788be06ee22471a87d02081d2b33"
V2_VECTOR = "d741aae0af4866e6e9fb438ea61cc6c63e81736c08243af3a5089ebe03f9b678"


def _receipt() -> R2FeedbackRuntimeReceipt:
    return R2FeedbackRuntimeReceipt.create(
        run_id="r2-legacy-vector",
        refinement_step_index=0,
        prior_proposal_digest="a" * 64,
        diagnostic_digest="b" * 64,
        residual_digest="c" * 64,
        resolution_digest="d" * 64,
        release_binding_table_digest="e" * 64,
        immutable_givens_digest="f" * 64,
        release_plan_digest="1" * 64,
        release_transaction_digest="2" * 64,
        clamp_state_before_digest="3" * 64,
        clamp_state_after_digest="4" * 64,
        released_cells=(0,),
        model_input_changed_cells=(0,),
        learned_status="SOLVED",
        learned_solution_digest="5" * 64,
        learned_iteration_count=1,
        traversal_digest="6" * 64,
    )


def main() -> int:
    current = _receipt()
    current_payload = current._payload_without_receipt_digest()

    if SCHEMA != "elpis.runtime-r2-feedback-receipt.v2":
        raise RuntimeError(f"R2_CURRENT_SCHEMA_NONPASS:{SCHEMA}")
    if receipt_mod._canonical_bytes(current_payload) != canonical_json_bytes(
        current_payload
    ):
        raise RuntimeError("R2_CANONICAL_BYTES_DIVERGE")
    if current.runtime_receipt_digest != content_digest(SCHEMA, current_payload):
        raise RuntimeError("R2_V2_DIGEST_DIVERGES")
    if current.runtime_receipt_digest != V2_VECTOR:
        raise RuntimeError("R2_V2_VECTOR_DRIFT")
    if not current.verify():
        raise RuntimeError("R2_V2_VERIFY_NONPASS")

    legacy_candidate = replace(
        current,
        schema=receipt_mod.LEGACY_SCHEMA,
        runtime_receipt_digest="",
    )
    legacy_payload = legacy_candidate._payload_without_receipt_digest()
    legacy_digest = receipt_mod._legacy_v1_digest(legacy_payload)
    if legacy_digest != LEGACY_VECTOR:
        raise RuntimeError("R2_V1_VECTOR_DRIFT")
    legacy = replace(
        legacy_candidate,
        runtime_receipt_digest=legacy_digest,
    )
    if not legacy.verify():
        raise RuntimeError("R2_V1_VERIFY_COMPATIBILITY_NONPASS")
    if content_digest(receipt_mod.LEGACY_SCHEMA, legacy_payload) == legacy_digest:
        raise RuntimeError("R2_V1_LEGACY_DISTINCTION_LOST")

    print(
        json.dumps(
            {
                "current_schema": SCHEMA,
                "current_digest": current.runtime_receipt_digest,
                "legacy_schema": receipt_mod.LEGACY_SCHEMA,
                "legacy_digest": legacy_digest,
                "canonical_bytes_equal": True,
                "current_matches_canonical_identity": True,
                "legacy_verification_preserved": True,
                "r2_root_dependency_added": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
