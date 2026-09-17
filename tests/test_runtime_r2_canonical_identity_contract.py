from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ROOT_SRC = ROOT / "src"
R2_SRC = ROOT / "runtime" / "R2" / "src"
for source_root in (ROOT_SRC, R2_SRC):
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


def test_r2_new_receipts_use_v2_canonical_identity_framing():
    receipt = _receipt()
    payload = receipt._payload_without_receipt_digest()
    assert SCHEMA == "elpis.runtime-r2-feedback-receipt.v2"
    assert receipt.schema == SCHEMA
    assert receipt_mod._canonical_bytes(payload) == canonical_json_bytes(payload)
    assert receipt.runtime_receipt_digest == content_digest(SCHEMA, payload)
    assert receipt.runtime_receipt_digest == V2_VECTOR
    assert receipt.verify()


def test_r2_v1_receipt_digest_semantics_remain_verifiable():
    current = _receipt()
    legacy_candidate = replace(
        current,
        schema=receipt_mod.LEGACY_SCHEMA,
        runtime_receipt_digest="",
    )
    payload = legacy_candidate._payload_without_receipt_digest()
    assert receipt_mod._legacy_v1_digest(payload) == LEGACY_VECTOR

    legacy = replace(
        legacy_candidate,
        runtime_receipt_digest=LEGACY_VECTOR,
    )
    assert legacy.verify()
    assert content_digest(receipt_mod.LEGACY_SCHEMA, payload) != LEGACY_VECTOR


def test_r2_unknown_receipt_schema_fails_closed():
    receipt = replace(
        _receipt(),
        schema="elpis.runtime-r2-feedback-receipt.v999",
    )
    assert not receipt.verify()


def test_r2_create_rejects_caller_supplied_schema():
    kwargs = _receipt()._payload_without_receipt_digest()
    kwargs.pop("profile")
    kwargs.pop("schema")
    try:
        R2FeedbackRuntimeReceipt.create(schema=receipt_mod.LEGACY_SCHEMA, **kwargs)
    except TypeError as exc:
        assert str(exc) == "schema is derived"
    else:
        raise AssertionError("caller-supplied schema must be rejected")


def test_r2_package_remains_standalone_zero_dependency_import():
    code = (
        "import sys;"
        f"sys.path.insert(0,{str(R2_SRC)!r});"
        "import elpis_runtime_r2;"
        "assert elpis_runtime_r2.SCHEMA == "
        "'elpis.runtime-r2-feedback-receipt.v2';"
        "assert 'elpis' not in sys.modules;"
        "print('PASS_R2_STANDALONE_CANONICAL_IDENTITY')"
    )
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.returncode == 0, proc.stderr
    assert "PASS_R2_STANDALONE_CANONICAL_IDENTITY" in proc.stdout
