from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "digest_sink_census.py"
BASELINE = ROOT / "tools" / "direct_sha256_sink_census_v1.json"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(TOOL), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def test_direct_sha256_sink_census_is_closed_and_complete():
    proc = _run()
    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)
    assert report["status"] == "PASS"
    assert report["current_sink_count"] > 0
    assert report["current_sink_count"] <= report["registered_sink_count"]
    assert report["categories"].get(
        "CANONICAL_IDENTITY_V1_AUTHORITY"
    ) == 1
    assert report["categories"].get(
        "R2_ZERO_DEP_CANONICAL_IDENTITY_V1_EQUIVALENT"
    ) == 1
    assert report["categories"].get(
        "R2_LEGACY_V1_PROTOCOL_IDENTITY"
    ) == 1
    assert "UNREGISTERED" not in report["categories"]


def test_historical_direct_sha256_entries_are_bound_to_q0a_commit():
    data = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert (
        data["baseline_commit"]
        == "b7606061417db38a1f36a0db5a565cfe3bf2906e"
    )
    assert (
        data["policy"]["new_structured_identity"]
        == "MUST_USE_ELPIS_CANONICAL_IDENTITY"
    )
    assert (
        data["policy"]["historical_direct_sha256"]
        == "MUST_BE_PROVABLY_PRESENT_AT_BASELINE_COMMIT"
    )

    identities = [
        (
            x["path"],
            x["qualname"],
            x["fingerprint"],
            x["occurrence"],
        )
        for x in data["sinks"]
    ]
    assert len(identities) == len(set(identities))

    tmp = ROOT / ".digest_sink_census_test.tmp.json"
    try:
        proc = _run("--emit-baseline", "--baseline", str(tmp))
        assert proc.returncode == 0, proc.stderr
        regenerated = json.loads(tmp.read_text(encoding="utf-8"))
        assert regenerated == data
    finally:
        tmp.unlink(missing_ok=True)
