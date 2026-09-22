from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/verify_inference_native_locus.py"
MANIFEST = ROOT / "tools/inference_native_locus_v1.json"


def load_tool():
    spec = importlib.util.spec_from_file_location("native_locus", TOOL)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_native_locus_manifest_is_exact_and_live():
    proc = subprocess.run(
        [sys.executable, str(TOOL), "--check"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert payload["provider"]["count"] == 7
    assert payload["locus"]["count"] == 149
    assert len(payload["provider"]["nodeids"]) == 7
    assert len(payload["locus"]["nodeids"]) == 149
    assert payload["sources"]


def test_native_locus_rejects_nodeid_or_source_digest_mutation():
    tool = load_tool()
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    observed = json.loads(json.dumps(payload))

    observed["locus"]["nodeids"][0] += "_renamed"
    assert "NATIVE_LOCUS_MISMATCH:locus:nodeids" in tool.errors(payload, observed)

    observed = json.loads(json.dumps(payload))
    key = sorted(observed["sources"])[0]
    observed["sources"][key] = "0" * 64
    assert "NATIVE_LOCUS_TEST_SOURCE_DIGEST_MISMATCH" in tool.errors(payload, observed)
