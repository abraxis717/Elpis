from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/"tools/runtime_admission_temporality.py"
BASELINE=ROOT/"tools/runtime_admission_temporality_v1.json"


def _run(*args:str)->subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable,"-B",str(TOOL),*args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def test_runtime_admission_temporality_passes_with_historical_false_preserved():
    proc=_run()
    assert proc.returncode==0,proc.stderr
    report=json.loads(proc.stdout)
    assert report["status"]=="PASS"
    assert set(report["active_values"])=={True}
    assert report["historical_false_count"]>=1
    assert report["production_override_findings"]==[]
    assert report["component_registry_scope"][
        "registry_runtime_admission"
    ] is False
    assert report["component_registry_scope"][
        "all_component_runtime_admission_false"
    ] is True

    false_paths={
        x[0] for x in report["historical_false_declarations"]
    }
    assert (
        "src/elpis_reference/structural_guidance/RUNTIME_E2E_SEAL_R0.json"
        in false_paths
    )


def test_temporality_baseline_is_reproducible_from_bound_commit():
    original=json.loads(BASELINE.read_text(encoding="utf-8"))
    assert (
        original["baseline_commit"]
        =="42524837092eeb5986b863d7fd3022e1efe04539"
    )
    tmp=ROOT/".runtime_admission_temporality_test.tmp.json"
    try:
        proc=_run("--emit-baseline","--baseline",str(tmp))
        assert proc.returncode==0,proc.stderr
        regenerated=json.loads(tmp.read_text(encoding="utf-8"))
        assert regenerated==original
    finally:
        tmp.unlink(missing_ok=True)



def test_distribution_manifests_are_historical_snapshots():
    data=json.loads(BASELINE.read_text(encoding="utf-8"))
    distribution=[
        x for x in data["declarations"]
        if x["path"].endswith(".DISTRIBUTION_MANIFEST.json")
    ]
    assert distribution
    assert all(
        x["category"]=="HISTORICAL_DISTRIBUTION_SNAPSHOT"
        for x in distribution
    )
    assert all("file_sha256" in x for x in distribution)

def test_historical_seal_cannot_be_reclassified_as_active_authority():
    data=json.loads(BASELINE.read_text(encoding="utf-8"))
    seal=[
        x for x in data["declarations"]
        if x["path"]
        =="src/elpis_reference/structural_guidance/RUNTIME_E2E_SEAL_R0.json"
    ]
    assert len(seal)==1
    assert seal[0]["value"] is False
    assert seal[0]["category"]=="HISTORICAL_SCOPED_EVIDENCE"

    tampered=copy.deepcopy(data)
    target=[
        x for x in tampered["declarations"]
        if x["path"]
        =="src/elpis_reference/structural_guidance/RUNTIME_E2E_SEAL_R0.json"
    ][0]
    target["category"]="ACTIVE_RUNTIME_SOURCE_AUTHORITY"

    tmp=ROOT/".runtime_admission_temporality_bad.tmp.json"
    try:
        tmp.write_text(
            json.dumps(tampered,indent=2,sort_keys=True)+"\n",
            encoding="utf-8",
        )
        proc=_run("--baseline",str(tmp))
        assert proc.returncode!=0
        assert "TEMPORALITY_CATEGORY_MISMATCH" in proc.stderr
    finally:
        tmp.unlink(missing_ok=True)


def _expected_future_write_once_temporality_records():
    imm=json.loads(
        (ROOT/"tools/immutable_evidence_baseline_v1.json").read_text(
            encoding="utf-8"
        )
    )
    records=[]
    for rel,spec in sorted(imm["write_once_paths"].items()):
        if not rel.startswith("manifests/Elpis") or not rel.endswith(
            ".RELEASE_MANIFEST.json"
        ):
            continue
        records.append({
            "path":rel,
            "syntax":"json_key",
            "locator":"/full_elpis_runtime_admission",
            "qualname":"<json>",
            "value":True,
            "category":"HISTORICAL_RELEASE_SNAPSHOT",
            "byte_authority":"FIRST_COMMITTED_BLOB_IMMUTABLE",
            "release":spec["release"],
        })
    return records


def test_future_release_manifest_temporality_matches_write_once_authority():
    data=json.loads(BASELINE.read_text(encoding="utf-8"))
    assert data["future_write_once_declarations"] == (
        _expected_future_write_once_temporality_records()
    )


def test_future_write_once_declaration_tracks_materialized_lifecycle_state():
    proc=_run()
    assert proc.returncode==0,proc.stderr
    report=json.loads(proc.stdout)

    future=_expected_future_write_once_temporality_records()
    materialized=[
        record for record in future
        if (ROOT/record["path"]).is_file()
    ]

    assert report["future_write_once_declaration_count"]==len(future)
    assert report["registered_declaration_count"]==(
        report["fixed_declaration_count"]+len(future)
    )
    assert report["future_write_once_materialized_count"]==len(materialized)
    assert report["current_declaration_count"]==(
        report["fixed_declaration_count"]+len(materialized)
    )
    assert report["future_write_once_materialized_declarations"]==[
        [
            record["path"],
            record["syntax"],
            record["qualname"],
            record["locator"],
        ]
        for record in materialized
    ]
