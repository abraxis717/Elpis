from __future__ import annotations
from tools import release_git
import hashlib, json
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

def test_publication_registry_generation_policy_is_explicit():
    x=json.loads(BASE.read_text(encoding="utf-8"))
    regs=x["append_only_registries"]

    assert regs["FAILED_RELEASES.json"]["records"]
    assert regs["PUBLISHED_RELEASES.json"]["records"]
    assert regs["PUBLICATION_ASSERTIONS.json"]["records"]

    assert [
        row["version"]
        for row in regs["PUBLICATION_ASSERTIONS.json"]["records"]
    ] == ["2.2.19"]

    assert "PUBLISHED_RELEASES.json" not in x["permanent_files"]

    frozen=x["frozen_registry_files"]
    assert frozen["PUBLISHED_RELEASES.json"] == hashlib.sha256(
        (ROOT/"PUBLISHED_RELEASES.json").read_bytes()
    ).hexdigest()

    assert (
        x["policy"]["release_registries"]
        == "LEGACY_V1_BYTE_FROZEN_V2_APPEND_ONLY"
    )

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

    proc=release_git.run(
        ROOT,
        "show",
        "HEAD:tools/immutable_evidence_baseline_v1.json",
    )
    proc.check_returncode()
    assert proc.stdout==BASE.read_bytes()


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


def _git(repo:Path,*args:str)->subprocess.CompletedProcess:
    return subprocess.run(
        ["git","-C",str(repo),*args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


def _write_once_module():
    import importlib.util
    spec=importlib.util.spec_from_file_location("immutability_gate",TOOL)
    assert spec and spec.loader
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _tiny_git_repo(tmp_path:Path)->Path:
    repo=tmp_path/"repo"
    repo.mkdir()
    _git(repo,"init","-q")
    _git(repo,"config","user.name","immutability-test")
    _git(repo,"config","user.email","immutability@example.invalid")
    (repo/"seed.txt").write_text("seed\n",encoding="utf-8")
    _git(repo,"add","seed.txt")
    _git(repo,"commit","-qm","seed")
    return repo


def test_2_2_14_manifest_is_predeclared_write_once_not_hash_cyclic():
    data=json.loads(BASE.read_text(encoding="utf-8"))
    rel="manifests/Elpis2.2.14.RELEASE_MANIFEST.json"
    assert rel not in data["permanent_files"]
    assert data["write_once_paths"][rel] == {
        "rule":"FIRST_COMMITTED_BLOB_IMMUTABLE",
        "release":"Elpis2.2.14",
    }


def test_declared_write_once_path_allows_absent_then_untracked_first_materialization(tmp_path):
    mod=_write_once_module()
    repo=_tiny_git_repo(tmp_path)
    rel="manifests/Elpis9.9.9.RELEASE_MANIFEST.json"
    spec={"rule":mod.WRITE_ONCE_RULE,"release":"Elpis9.9.9"}
    assert mod.verify_write_once_path(repo,rel,spec,check_history=True)==[]
    path=repo/rel
    path.parent.mkdir()
    path.write_text('{"sealed":true}\n',encoding="utf-8")
    assert mod.verify_write_once_path(repo,rel,spec,check_history=True)==[]


def test_first_committed_write_once_blob_is_dynamically_pinned(tmp_path):
    mod=_write_once_module()
    repo=_tiny_git_repo(tmp_path)
    rel="manifests/Elpis9.9.9.RELEASE_MANIFEST.json"
    spec={"rule":mod.WRITE_ONCE_RULE,"release":"Elpis9.9.9"}
    path=repo/rel
    path.parent.mkdir()
    path.write_text('{"sealed":true}\n',encoding="utf-8")
    _git(repo,"add",rel)
    _git(repo,"commit","-qm","seal")
    assert mod.verify_write_once_path(repo,rel,spec,check_history=True)==[]

    path.write_text('{"sealed":false}\n',encoding="utf-8")
    errors=mod.verify_write_once_path(repo,rel,spec,check_history=True)
    assert any(e.startswith("WRITE_ONCE_BYTES_MUTATED:") for e in errors)
    assert any(e.startswith("WRITE_ONCE_WORKTREE_DIRTY:") for e in errors)


def test_committed_write_once_mutation_is_rejected_even_after_clean_commit(tmp_path):
    mod=_write_once_module()
    repo=_tiny_git_repo(tmp_path)
    rel="manifests/Elpis9.9.9.RELEASE_MANIFEST.json"
    spec={"rule":mod.WRITE_ONCE_RULE,"release":"Elpis9.9.9"}
    path=repo/rel
    path.parent.mkdir()
    path.write_text("A\n",encoding="utf-8")
    _git(repo,"add",rel)
    _git(repo,"commit","-qm","seal")
    path.write_text("B\n",encoding="utf-8")
    _git(repo,"add",rel)
    _git(repo,"commit","-qm","illegal rewrite")
    errors=mod.verify_write_once_path(repo,rel,spec,check_history=True)
    assert any(e.startswith("WRITE_ONCE_HISTORY_MUTATED:") for e in errors)


def test_committed_write_once_delete_is_rejected(tmp_path):
    mod=_write_once_module()
    repo=_tiny_git_repo(tmp_path)
    rel="manifests/Elpis9.9.9.RELEASE_MANIFEST.json"
    spec={"rule":mod.WRITE_ONCE_RULE,"release":"Elpis9.9.9"}
    path=repo/rel
    path.parent.mkdir()
    path.write_text("A\n",encoding="utf-8")
    _git(repo,"add",rel)
    _git(repo,"commit","-qm","seal")
    path.unlink()
    _git(repo,"add","-A")
    _git(repo,"commit","-qm","illegal delete")
    errors=mod.verify_write_once_path(repo,rel,spec,check_history=True)
    assert any(e.startswith("WRITE_ONCE_HISTORY_DELETED:") for e in errors)
    assert f"WRITE_ONCE_PATH_MISSING:{rel}" in errors


def test_gitless_write_once_declaration_defers_history_proof_to_git_checkout(tmp_path):
    mod=_write_once_module()
    root=tmp_path/"export"
    rel="manifests/Elpis9.9.9.RELEASE_MANIFEST.json"
    path=root/rel
    path.parent.mkdir(parents=True)
    path.write_text("{}\n",encoding="utf-8")
    spec={"rule":mod.WRITE_ONCE_RULE,"release":"Elpis9.9.9"}
    assert mod.verify_write_once_path(root,rel,spec,check_history=False)==[]


def test_release_manifest_write_once_declarations_are_noncyclic_and_self_named():
    data=json.loads(BASE.read_text(encoding="utf-8"))
    seen=[]
    for rel,spec in sorted(data["write_once_paths"].items()):
        if not (
            rel.startswith("manifests/Elpis")
            and rel.endswith(".RELEASE_MANIFEST.json")
        ):
            continue
        seen.append(rel)
        assert rel not in data["permanent_files"]
        assert spec["rule"]=="FIRST_COMMITTED_BLOB_IMMUTABLE"
        expected=Path(rel).name.removesuffix(".RELEASE_MANIFEST.json")
        assert spec["release"]==expected

    current=(ROOT/"VERSION").read_text(encoding="utf-8").strip()
    assert f"manifests/Elpis{current}.RELEASE_MANIFEST.json" in seen
    assert "manifests/Elpis2.2.14.RELEASE_MANIFEST.json" in seen


def test_legacy_published_registry_is_byte_frozen_by_transition_gate(tmp_path):
    mod=_write_once_module()
    snap={
        "list_key":"published_releases",
        "metadata":{
            "schema":"elpis.published-releases.v1",
            "source_of_truth":"refs/tags/Elpis<semver>",
        },
        "records":[
            {"version":"2.2.17","sha256":"a"*64},
        ],
    }
    current={
        "list_key":snap["list_key"],
        "metadata":snap["metadata"],
        "records":[
            *snap["records"],
            {"version":"2.2.19","sha256":"b"*64},
        ],
    }
    assert mod.registry_transition_errors(
        tmp_path,
        "PUBLISHED_RELEASES.json",
        snap,
        current,
    ) == [
        "LEGACY_PUBLISHED_REGISTRY_FROZEN:"
        "PUBLISHED_RELEASES.json"
    ]


def test_legacy_published_registry_prior_rewrite_is_rejected(tmp_path):
    mod=_write_once_module()
    snap={
        "list_key":"published_releases",
        "metadata":{
            "schema":"elpis.published-releases.v1",
            "source_of_truth":"refs/tags/Elpis<semver>",
        },
        "records":[
            {"version":"2.2.17","sha256":"a"*64},
        ],
    }
    current={
        "list_key":snap["list_key"],
        "metadata":snap["metadata"],
        "records":[
            {"version":"2.2.17","sha256":"c"*64},
        ],
    }
    assert mod.registry_transition_errors(
        tmp_path,
        "PUBLISHED_RELEASES.json",
        snap,
        current,
    ) == [
        "LEGACY_PUBLISHED_REGISTRY_FROZEN:"
        "PUBLISHED_RELEASES.json"
    ]


def _v2_transition_snapshot():
    return {
        "list_key":"publication_assertions",
        "metadata":{
            "legacy_publication_history":{
                "path":"PUBLISHED_RELEASES.json",
                "schema":"elpis.published-releases.v1",
                "sha256":"f"*64,
            },
            "publication_fact_authority":
                "explicit-observation-receipts",
            "release_identity_authority":
                "annotated-ref:refs/tags/Elpis<semver>",
            "schema":"elpis.publication-assertions.v2",
        },
        "records":[
            {"version":"2.2.19","sha256":"a"*64},
        ],
    }


def test_publication_assertions_v2_append_is_structurally_prefix_only(tmp_path):
    mod=_write_once_module()
    snap=_v2_transition_snapshot()
    current={
        "list_key":snap["list_key"],
        "metadata":snap["metadata"],
        "records":[
            *snap["records"],
            {"version":"2.2.20","sha256":"b"*64},
        ],
    }
    assert mod.registry_transition_errors(
        tmp_path,
        "PUBLICATION_ASSERTIONS.json",
        snap,
        current,
    ) == []


def test_publication_assertions_v2_prior_rewrite_is_rejected(tmp_path):
    mod=_write_once_module()
    snap=_v2_transition_snapshot()
    current={
        "list_key":snap["list_key"],
        "metadata":snap["metadata"],
        "records":[
            {"version":"2.2.19","sha256":"c"*64},
        ],
    }
    assert mod.registry_transition_errors(
        tmp_path,
        "PUBLICATION_ASSERTIONS.json",
        snap,
        current,
    ) == [
        "PUBLICATION_ASSERTIONS_PRIOR_RECORD_CHANGED:"
        "PUBLICATION_ASSERTIONS.json"
    ]


def test_publication_assertions_v2_metadata_rewrite_is_rejected(tmp_path):
    mod=_write_once_module()
    snap=_v2_transition_snapshot()
    current={
        "list_key":snap["list_key"],
        "metadata":{
            **snap["metadata"],
            "publication_fact_authority":"tampered",
        },
        "records":snap["records"],
    }
    assert mod.registry_transition_errors(
        tmp_path,
        "PUBLICATION_ASSERTIONS.json",
        snap,
        current,
    ) == [
        "REGISTRY_METADATA_CHANGED:"
        "PUBLICATION_ASSERTIONS.json"
    ]


def test_gitless_v2_prefix_transition_defers_git_semantic_proof(tmp_path):
    mod=_write_once_module()
    snap=_v2_transition_snapshot()
    current={
        "list_key":snap["list_key"],
        "metadata":snap["metadata"],
        "records":[
            *snap["records"],
            {"version":"2.2.20","sha256":"d"*64},
        ],
    }
    assert mod.registry_transition_errors(
        tmp_path,
        "PUBLICATION_ASSERTIONS.json",
        snap,
        current,
        check_tag_projection=False,
    ) == []



def test_v2_checker_mode_tracks_git_history_availability():
    import ast

    source = (
        ROOT / "tools/verify_immutable_evidence.py"
    ).read_text(encoding="utf-8")

    tree = ast.parse(
        source,
        filename="tools/verify_immutable_evidence.py",
    )

    assignments = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue

        if any(
            isinstance(target, ast.Name)
            and target.id == "checker_mode"
            for target in node.targets
        ):
            assignments.append(node.value)

    assert len(assignments) == 1

    value = assignments[0]

    assert isinstance(value, ast.IfExp)

    assert isinstance(value.test, ast.Name)
    assert value.test.id == "check_history"

    assert isinstance(value.body, ast.Constant)
    assert value.body.value == "--check"

    assert isinstance(value.orelse, ast.Constant)
    assert value.orelse.value == "--check-gitless"
