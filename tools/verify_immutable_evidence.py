#!/usr/bin/env python3
"""Repository immutability gate.

Category A: permanent evidence bytes + append-only release registries.
Category B: supersedable identity generations. Existing generations are
append-only historical records; the latest generation must match the tree.

This is intentionally not a general "freeze the repository" mechanism.
Contracts, tests, tools, docs and versioned policies remain mutable.
"""
from __future__ import annotations
import argparse, ast, hashlib, json, subprocess, tomllib
from pathlib import Path
from typing import Any

SCHEMA="elpis.repository-immutability.v1"
BASELINE_NAME="immutable_evidence_baseline_v1.json"

class GateError(RuntimeError): pass

def hbytes(b:bytes)->str: return hashlib.sha256(b).hexdigest()
def hfile(p:Path)->str: return hbytes(p.read_bytes())
def canonical_hash(x:Any)->str:
    return hbytes(json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode())

def git(root:Path,*args:str,check=True)->bytes:
    p=subprocess.run(["git","-C",str(root),*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if check and p.returncode:
        raise GateError(f"GIT_FAILED:{' '.join(args)}:{p.stderr.decode(errors='replace')}")
    return p.stdout if p.returncode==0 else b""

def git_head(root:Path)->str:
    return git(root,"rev-parse","HEAD").decode().strip()

def parent_baseline(root:Path)->dict|None:
    p=subprocess.run(["git","-C",str(root),"show",f"HEAD^:tools/{BASELINE_NAME}"],
                     stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if p.returncode: return None
    return json.loads(p.stdout.decode())

def permanent_paths(root:Path)->list[str]:
    found:set[str]=set()
    for pat in ("manifests/Elpis*.RELEASE_MANIFEST.json","manifests/Elpis*.DISTRIBUTION_MANIFEST.json"):
        for p in root.glob(pat):
            if p.is_file(): found.add(p.relative_to(root).as_posix())

    exact=[
      "docs/redteam/ELPIS_REDTEAM_2.2.7.md",
      "docs/redteam/ELPIS_REDTEAM_2.2.7_SOURCE_SHA256SUMS",
      "ECS/ECS_AUTHORITY/STRUCTURAL_R0/FROZEN_WRITABLE_BOUNDARY.json",
      "src/elpis_reference/structural_guidance/RUNTIME_E2E_SEAL_R0.json",
      "health/PUBLICATION_AUTHORITY.json",
      "components/Grid81/state/Canonical/Grid81/HEAD.json",
    ]
    for rel in exact:
        if (root/rel).is_file(): found.add(rel)

    gen=root/"components/Grid81/state/Canonical/Grid81/generations"
    if gen.is_dir():
        for p in gen.glob("*.json"):
            if p.is_file(): found.add(p.relative_to(root).as_posix())

    sci=root/"ECS/science"
    markers=tuple(f"BRANCH{i}" for i in range(35,41))
    tokens=("EVIDENCE_AUTHORITY","FINAL_ADJUDICATION","PREDECESSOR_AUTHORITY_CENSUS",
            "INTERVENTION_CONSTRUCTION_AUTHORITY","SHA256SUMS")
    if sci.is_dir():
        for p in sci.rglob("*"):
            if not p.is_file(): continue
            rel=p.relative_to(root).as_posix()
            if not any(m in rel for m in markers): continue
            if "PRECOMMIT_V0" in p.parts or any(t in p.name for t in tokens):
                found.add(rel)
    return sorted(found)

def registry_snapshot(root:Path,rel:str,list_key:str)->dict:
    data=json.loads((root/rel).read_text(encoding="utf-8"))
    records=data.get(list_key)
    if not isinstance(records,list): raise GateError(f"REGISTRY_LIST_INVALID:{rel}:{list_key}")
    out=[]
    for rec in records:
        if not isinstance(rec,dict) or not isinstance(rec.get("version"),str):
            raise GateError(f"REGISTRY_RECORD_INVALID:{rel}")
        out.append({"version":rec["version"],"sha256":canonical_hash(rec)})
    meta={k:v for k,v in data.items() if k!=list_key}
    return {"list_key":list_key,"metadata":meta,"records":out}

def py_constant(path:Path,name:str)->Any:
    tree=ast.parse(path.read_text(encoding="utf-8"),filename=str(path))
    for n in tree.body:
        if isinstance(n,(ast.Assign,ast.AnnAssign)):
            target=n.targets[0] if isinstance(n,ast.Assign) and len(n.targets)==1 else (n.target if isinstance(n,ast.AnnAssign) else None)
            if isinstance(target,ast.Name) and target.id==name:
                return ast.literal_eval(n.value)
    raise GateError(f"PY_CONSTANT_NOT_FOUND:{path}:{name}")

def json_pointer(path:Path,pointer:str)->Any:
    x=json.loads(path.read_text(encoding="utf-8"))
    for raw in pointer.strip("/").split("/") if pointer.strip("/") else []:
        key=raw.replace("~1","/").replace("~0","~")
        x=x[int(key)] if isinstance(x,list) else x[key]
    return x

def current_component_manifest_pins(root:Path)->list[dict]:
    reg=json.loads((root/"manifests/PUBLIC_COMPONENT_REGISTRY.json").read_text(encoding="utf-8"))
    pins=[]
    for c in reg["components"]:
        p=root/c["public_path"]/"COMPONENT_MANIFEST.json"
        if p.is_file():
            pins.append({"kind":"file_sha256","path":p.relative_to(root).as_posix(),"value":hfile(p)})
    return sorted(pins,key=lambda x:x["path"])

def identity_generation(root:Path,source_commit:str)->dict:
    pins=[
      {"kind":"python_constant","path":"src/elpis_reference/model.py","name":"MODEL_SHA256",
       "value":py_constant(root/"src/elpis_reference/model.py","MODEL_SHA256")},
      {"kind":"python_constant","path":"src/elpis_reference/structural_guidance/authority.py","name":"FROZEN_TRM0_CHECKPOINT_SHA256",
       "value":py_constant(root/"src/elpis_reference/structural_guidance/authority.py","FROZEN_TRM0_CHECKPOINT_SHA256")},
      {"kind":"json_pointer","path":"src/elpis_reference/vendor/fprm/AUTHORITY.json","pointer":"/checkpoint/sha256",
       "value":json_pointer(root/"src/elpis_reference/vendor/fprm/AUTHORITY.json","/checkpoint/sha256")},
      {"kind":"json_pointer","path":"src/elpis_reference/vendor/fprm/AUTHORITY.json","pointer":"/checkpoint/size",
       "value":json_pointer(root/"src/elpis_reference/vendor/fprm/AUTHORITY.json","/checkpoint/size")},
      {"kind":"file_sha256","path":"components/TRMFractalSpine/registry/model_ports.toml",
       "value":hfile(root/"components/TRMFractalSpine/registry/model_ports.toml")},
      {"kind":"file_sha256","path":"components/TRMFractalSpine/registry/models.toml",
       "value":hfile(root/"components/TRMFractalSpine/registry/models.toml")},
    ]
    pins.extend(current_component_manifest_pins(root))
    return {
      "generation_id":"ELPIS_2_2_14_BOOTSTRAP_R0",
      "source_commit":source_commit,
      "supersession_rule":"APPEND_NEW_GENERATION_NEVER_EDIT_PRIOR_GENERATION",
      "pins":pins,
    }

def capture(root:Path)->dict:
    head=git_head(root)
    files={rel:hfile(root/rel) for rel in permanent_paths(root)}
    return {
      "schema":SCHEMA,
      "bootstrap_source_commit":head,
      "policy":{
        "permanent_evidence":"BYTE_IMMUTABLE_AND_PATHSET_CLOSED",
        "release_registries":"EXISTING_RECORDS_IMMUTABLE_APPEND_ONLY",
        "identity_generations":"LATEST_MUST_MATCH_TREE_PRIOR_GENERATIONS_IMMUTABLE",
        "not_frozen":"contracts_tests_tools_docs_versioned_policies",
      },
      "permanent_files":files,
      "append_only_registries":{
        "FAILED_RELEASES.json":registry_snapshot(root,"FAILED_RELEASES.json","failed_releases"),
        "PUBLISHED_RELEASES.json":registry_snapshot(root,"PUBLISHED_RELEASES.json","published_releases"),
      },
      "identity_generations":[identity_generation(root,head)],
    }

def check_pin(root:Path,pin:dict)->str|None:
    kind=pin["kind"]; path=root/pin["path"]
    if not path.is_file(): return f"IDENTITY_PIN_MISSING:{pin['path']}"
    try:
        if kind=="file_sha256": got=hfile(path)
        elif kind=="python_constant": got=py_constant(path,pin["name"])
        elif kind=="json_pointer": got=json_pointer(path,pin["pointer"])
        else: return f"IDENTITY_PIN_KIND_UNKNOWN:{kind}"
    except Exception as e:
        return f"IDENTITY_PIN_READ_ERROR:{pin['path']}:{type(e).__name__}:{e}"
    if got!=pin["value"]:
        label=pin.get("name") or pin.get("pointer") or "sha256"
        return f"FROZEN_IDENTITY_DRIFT:{pin['path']}:{label}:{got!r}:{pin['value']!r}"
    return None

def prefix_equal(old:list,new:list)->bool:
    return len(new)>=len(old) and new[:len(old)]==old

def verify_history(root:Path,base:dict,errors:list[str])->None:
    prev=parent_baseline(root)
    if prev is None:
        head=git_head(root)
        parent=git(root,"rev-parse","HEAD^",check=False).decode().strip()
        if base["bootstrap_source_commit"] not in {head,parent}:
            errors.append("BOOTSTRAP_SOURCE_COMMIT_NOT_HEAD_OR_PARENT")
        return
    if prev.get("schema")!=SCHEMA:
        errors.append("PARENT_BASELINE_SCHEMA_INVALID"); return
    for rel,want in prev.get("permanent_files",{}).items():
        if base.get("permanent_files",{}).get(rel)!=want:
            errors.append(f"BASELINE_OLD_FILE_ENTRY_CHANGED_OR_REMOVED:{rel}")
    for rel,preg in prev.get("append_only_registries",{}).items():
        creg=base.get("append_only_registries",{}).get(rel)
        if not creg:
            errors.append(f"BASELINE_REGISTRY_REMOVED:{rel}"); continue
        if preg.get("metadata")!=creg.get("metadata"):
            errors.append(f"BASELINE_REGISTRY_METADATA_CHANGED:{rel}")
        if not prefix_equal(preg.get("records",[]),creg.get("records",[])):
            errors.append(f"BASELINE_REGISTRY_HISTORY_REWRITTEN:{rel}")
    if not prefix_equal(prev.get("identity_generations",[]),base.get("identity_generations",[])):
        errors.append("BASELINE_IDENTITY_GENERATION_HISTORY_REWRITTEN")

def verify(root:Path,baseline_path:Path,check_history=True)->dict:
    base=json.loads(baseline_path.read_text(encoding="utf-8"))
    if base.get("schema")!=SCHEMA: raise GateError("BASELINE_SCHEMA_INVALID")
    errors=[]
    selected=permanent_paths(root)
    registered=sorted(base.get("permanent_files",{}))
    if selected!=registered:
        for p in sorted(set(selected)-set(registered)): errors.append(f"UNREGISTERED_IMMUTABLE_EVIDENCE:{p}")
        for p in sorted(set(registered)-set(selected)): errors.append(f"IMMUTABLE_EVIDENCE_PATH_MISSING:{p}")
    for rel,want in sorted(base["permanent_files"].items()):
        p=root/rel
        if not p.is_file(): errors.append(f"MISSING_EVIDENCE:{rel}")
        elif hfile(p)!=want: errors.append(f"EVIDENCE_MUTATED:{rel}:{hfile(p)}:{want}")

    for rel,snap in base["append_only_registries"].items():
        current=registry_snapshot(root,rel,snap["list_key"])
        if current["metadata"]!=snap["metadata"]: errors.append(f"REGISTRY_METADATA_CHANGED:{rel}")
        if current["records"]!=snap["records"]:
            errors.append(f"REGISTRY_BASELINE_UPDATE_REQUIRED_OR_PRIOR_RECORD_CHANGED:{rel}")

    gens=base.get("identity_generations",[])
    if not gens: errors.append("NO_IDENTITY_GENERATION")
    else:
        for pin in gens[-1]["pins"]:
            err=check_pin(root,pin)
            if err: errors.append(err)

    # Existing 2.2.7 byte-freeze remains an independent authority.
    vf=root/"tools/verify_frozen_authority_immutability.py"
    if vf.is_file():
        p=subprocess.run([__import__("sys").executable,"-B",str(vf)],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        if p.returncode: errors.append("EXISTING_FROZEN_AUTHORITY_GATE_NONPASS:"+p.stdout.decode(errors="replace").strip())

    if check_history:
        try: verify_history(root,base,errors)
        except Exception as e: errors.append(f"BASELINE_HISTORY_CHECK_ERROR:{type(e).__name__}:{e}")

    report={
      "schema":SCHEMA,
      "permanent_file_count":len(base["permanent_files"]),
      "failed_registry_record_count":len(base["append_only_registries"]["FAILED_RELEASES.json"]["records"]),
      "published_registry_record_count":len(base["append_only_registries"]["PUBLISHED_RELEASES.json"]["records"]),
      "identity_generation_count":len(gens),
      "identity_pin_count":len(gens[-1]["pins"]) if gens else 0,
      "errors":errors,
      "status":"PASS" if not errors else "NONPASS",
    }
    if errors: raise GateError("REPOSITORY_IMMUTABILITY_NONPASS:\n"+"\n".join(errors))
    return report

def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument("--baseline",type=Path,default=None)
    ap.add_argument("--emit-bootstrap",action="store_true")
    args=ap.parse_args(argv)
    root=args.root.resolve()
    base=args.baseline.resolve() if args.baseline else root/"tools"/BASELINE_NAME
    if args.emit_bootstrap:
        x=capture(root); base.write_text(json.dumps(x,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
        print(json.dumps({"status":"EMITTED","path":str(base),"permanent_file_count":len(x["permanent_files"]),
                          "identity_pin_count":len(x["identity_generations"][-1]["pins"])},sort_keys=True)); return 0
    print(json.dumps(verify(root,base),sort_keys=True)); return 0

if __name__=="__main__": raise SystemExit(main())
