from __future__ import annotations
import json
from pathlib import Path
import subprocess, sys

ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/"tools/verify_immutable_evidence.py"
BASE=ROOT/"tools/immutable_evidence_baseline_v1.json"

def run(*a):
    return subprocess.run([sys.executable,"-B",str(TOOL),*a],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)

def test_repository_immutability_gate_passes():
    p=run()
    assert p.returncode==0,p.stderr
    report=json.loads(p.stdout)
    assert report["status"]=="PASS"
    assert report["permanent_file_count"]>0
    assert report["identity_pin_count"]>=6

def test_permanent_evidence_contains_critical_records():
    x=json.loads(BASE.read_text(encoding="utf-8"))
    files=x["permanent_files"]
    assert "src/elpis_reference/structural_guidance/RUNTIME_E2E_SEAL_R0.json" in files
    assert "health/PUBLICATION_AUTHORITY.json" in files
    assert "docs/redteam/ELPIS_REDTEAM_2.2.7.md" in files
    assert any(p.endswith(".RELEASE_MANIFEST.json") for p in files)
    assert "components/Grid81/state/Canonical/Grid81/HEAD.json" in files

def test_release_registries_are_record_pinned_not_whole_file_frozen():
    x=json.loads(BASE.read_text(encoding="utf-8"))
    regs=x["append_only_registries"]
    assert regs["FAILED_RELEASES.json"]["records"]
    assert regs["PUBLISHED_RELEASES.json"]["records"]
    assert "FAILED_RELEASES.json" not in x["permanent_files"]
    assert "PUBLISHED_RELEASES.json" not in x["permanent_files"]

def test_trm_and_fprm_identity_are_generation_pinned():
    x=json.loads(BASE.read_text(encoding="utf-8"))
    pins=x["identity_generations"][-1]["pins"]
    by_key={(p["path"],p.get("name"),p.get("pointer")):p["value"] for p in pins}
    assert by_key[("src/elpis_reference/model.py","MODEL_SHA256",None)]=="6daec5f499d115beb14e23f3a9cf56d1166b99c1ccd36b185a19ea5dfec9a137"
    assert by_key[("src/elpis_reference/structural_guidance/authority.py","FROZEN_TRM0_CHECKPOINT_SHA256",None)]=="e58e44c9227d68971d0ab5f5e4f0eaf2e05d4faa97ec8232108aa73898273129"
    assert by_key[("src/elpis_reference/vendor/fprm/AUTHORITY.json",None,"/checkpoint/sha256")]=="6daec5f499d115beb14e23f3a9cf56d1166b99c1ccd36b185a19ea5dfec9a137"
    assert by_key[("src/elpis_reference/vendor/fprm/AUTHORITY.json",None,"/checkpoint/size")]==54637557

def test_bootstrap_provenance_is_frozen_and_baseline_is_committed():
    data=json.loads(BASE.read_text(encoding="utf-8"))
    bootstrap="e5e6e0d6007ecb27d6136d6ce67566d10d075dde"
    assert data["bootstrap_source_commit"]==bootstrap
    assert data["identity_generations"][0]["source_commit"]==bootstrap

    committed=subprocess.check_output(
        ["git","show","HEAD:tools/immutable_evidence_baseline_v1.json"],
        cwd=ROOT,
    )
    assert committed==BASE.read_bytes()


def test_dirty_baseline_is_not_ordinary_qualifiable(tmp_path):
    import importlib.util
    import subprocess

    spec=importlib.util.spec_from_file_location("immutability_gate",TOOL)
    assert spec and spec.loader
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    repo=tmp_path/"repo"
    repo.mkdir()
    subprocess.run(["git","init","-q"],cwd=repo,check=True)
    subprocess.run(["git","config","user.name","test"],cwd=repo,check=True)
    subprocess.run(["git","config","user.email","test@example.invalid"],cwd=repo,check=True)
    (repo/"baseline.json").write_text('{"v":1}\n',encoding="utf-8")
    subprocess.run(["git","add","baseline.json"],cwd=repo,check=True)
    subprocess.run(["git","commit","-qm","baseline"],cwd=repo,check=True)
    (repo/"baseline.json").write_text('{"v":2}\n',encoding="utf-8")

    errors=[]
    mod.verify_committed_baseline(repo,repo/"baseline.json",errors)
    assert len(errors)==1
    assert errors[0].startswith("BASELINE_WORKTREE_NOT_COMMITTED:")
