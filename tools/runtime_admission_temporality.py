#!/usr/bin/env python3
"""Runtime-admission authority temporality gate.

Whole-runtime admission declarations are not a flat set of values:
- live source/release-policy declarations are active authority and must agree;
- immutable release manifests are historical release snapshots;
- RUNTIME_E2E_SEAL_R0.json is historical scoped evidence;
- PUBLIC_COMPONENT_REGISTRY.runtime_admission is a deliberately different
  component-registry scope.

Historical declarations retain exact bytes and provenance. They do not override
active authority.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Any

SCHEMA="elpis.runtime-admission-temporality.v1"
BASELINE_COMMIT="42524837092eeb5986b863d7fd3022e1efe04539"

ACTIVE_CATEGORIES={
    "ACTIVE_RUNTIME_SOURCE_AUTHORITY",
    "ACTIVE_RELEASE_EMISSION_POLICY",
    "ACTIVE_RELEASE_VERIFICATION_POLICY",
}
HISTORICAL_CATEGORIES={
    "HISTORICAL_RELEASE_SNAPSHOT",
    "HISTORICAL_DISTRIBUTION_SNAPSHOT",
    "HISTORICAL_SCOPED_EVIDENCE",
}
ALLOWED_CATEGORIES=ACTIVE_CATEGORIES | HISTORICAL_CATEGORIES

AUTHORITY_PATH="src/elpis_reference/structural_guidance/authority.py"
SEAL_PATH="src/elpis_reference/structural_guidance/RUNTIME_E2E_SEAL_R0.json"
PUBLIC_REGISTRY="manifests/PUBLIC_COMPONENT_REGISTRY.json"
RELEASE_RE=re.compile(r"^manifests/Elpis[^/]+\.RELEASE_MANIFEST\.json$")
DISTRIBUTION_RE=re.compile(r"^manifests/Elpis[^/]+\.DISTRIBUTION_MANIFEST\.json$")

PRODUCTION_ROOTS=(
    "src",
    "components",
    "runtime",
    "ECS/runtime",
    "native/elpis-header/src",
)
EXCLUDED_PARTS={"tests","__pycache__",".venv","venv"}


class TemporalityError(RuntimeError):
    pass


def _git(root:Path,*args:str)->bytes:
    p=subprocess.run(
        ["git","-C",str(root),*args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if p.returncode:
        raise TemporalityError(
            f"GIT_FAILED:{' '.join(args)}:"
            f"{p.stderr.decode(errors='replace').strip()}"
        )
    return p.stdout


def _tracked(root:Path,commit:str|None)->list[str]:
    raw=(
        _git(root,"ls-files","-z")
        if commit is None
        else _git(root,"ls-tree","-r","--name-only","-z",commit)
    )
    return sorted(
        x.decode("utf-8")
        for x in raw.split(b"\0")
        if x
    )


def _bytes(root:Path,rel:str,commit:str|None)->bytes:
    if commit is None:
        return (root/rel).read_bytes()
    return _git(root,"show",f"{commit}:{rel}")


def _text(root:Path,rel:str,commit:str|None)->str:
    return _bytes(root,rel,commit).decode("utf-8")


def _sha(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()


def _qualname(parents:list[str])->str:
    return ".".join(parents) if parents else "<module>"


def _python_declarations(rel:str,source:str)->list[dict[str,Any]]:
    try:
        tree=ast.parse(source,filename=rel)
    except SyntaxError as exc:
        raise TemporalityError(f"PARSE_FAILED:{rel}:{exc}") from exc

    records:list[dict[str,Any]]=[]
    parents:list[str]=[]
    dict_counts:dict[str,int]={}

    class Visitor(ast.NodeVisitor):
        def visit_ClassDef(self,node:ast.ClassDef)->Any:
            parents.append(node.name)
            self.generic_visit(node)
            parents.pop()

        def visit_FunctionDef(self,node:ast.FunctionDef)->Any:
            parents.append(node.name)
            self.generic_visit(node)
            parents.pop()

        def visit_AsyncFunctionDef(self,node:ast.AsyncFunctionDef)->Any:
            parents.append(node.name)
            self.generic_visit(node)
            parents.pop()

        def visit_Assign(self,node:ast.Assign)->Any:
            if (
                len(node.targets)==1
                and isinstance(node.targets[0],ast.Name)
                and node.targets[0].id=="FULL_ELPIS_RUNTIME_ADMISSION"
                and isinstance(node.value,ast.Constant)
                and isinstance(node.value.value,bool)
            ):
                records.append({
                    "path":rel,
                    "syntax":"python_assignment",
                    "locator":"FULL_ELPIS_RUNTIME_ADMISSION",
                    "qualname":_qualname(parents),
                    "value":node.value.value,
                })
            self.generic_visit(node)

        def visit_AnnAssign(self,node:ast.AnnAssign)->Any:
            if (
                isinstance(node.target,ast.Name)
                and node.target.id=="FULL_ELPIS_RUNTIME_ADMISSION"
                and isinstance(node.value,ast.Constant)
                and isinstance(node.value.value,bool)
            ):
                records.append({
                    "path":rel,
                    "syntax":"python_assignment",
                    "locator":"FULL_ELPIS_RUNTIME_ADMISSION",
                    "qualname":_qualname(parents),
                    "value":node.value.value,
                })
            self.generic_visit(node)

        def visit_Dict(self,node:ast.Dict)->Any:
            for key,value in zip(node.keys,node.values):
                if (
                    isinstance(key,ast.Constant)
                    and key.value=="full_elpis_runtime_admission"
                    and isinstance(value,ast.Constant)
                    and isinstance(value.value,bool)
                ):
                    q=_qualname(parents)
                    idx=dict_counts.get(q,0)
                    dict_counts[q]=idx+1
                    records.append({
                        "path":rel,
                        "syntax":"python_dict_literal",
                        "locator":f"full_elpis_runtime_admission#{idx}",
                        "qualname":q,
                        "value":value.value,
                    })
            self.generic_visit(node)

    Visitor().visit(tree)
    return records


def _walk_json(value:Any,pointer:str="")->list[tuple[str,bool]]:
    found:list[tuple[str,bool]]=[]
    if isinstance(value,dict):
        for key,item in value.items():
            esc=str(key).replace("~","~0").replace("/","~1")
            ptr=f"{pointer}/{esc}"
            if key=="full_elpis_runtime_admission" and isinstance(item,bool):
                found.append((ptr,item))
            found.extend(_walk_json(item,ptr))
    elif isinstance(value,list):
        for idx,item in enumerate(value):
            found.extend(_walk_json(item,f"{pointer}/{idx}"))
    return found


def _json_declarations(rel:str,source:str)->list[dict[str,Any]]:
    try:
        data=json.loads(source)
    except json.JSONDecodeError as exc:
        raise TemporalityError(f"JSON_PARSE_FAILED:{rel}:{exc}") from exc
    return [
        {
            "path":rel,
            "syntax":"json_key",
            "locator":pointer,
            "qualname":"<json>",
            "value":value,
        }
        for pointer,value in _walk_json(data)
    ]


def scan(root:Path,commit:str|None=None)->list[dict[str,Any]]:
    records:list[dict[str,Any]]=[]
    for rel in _tracked(root,commit):
        p=PurePosixPath(rel)
        if p.suffix==".py":
            # Tests contain assertions, not governing declarations.
            if any(part in EXCLUDED_PARTS for part in p.parts):
                continue
            source=_text(root,rel,commit)
            if (
                "FULL_ELPIS_RUNTIME_ADMISSION" in source
                or "full_elpis_runtime_admission" in source
            ):
                records.extend(_python_declarations(rel,source))
        elif p.suffix==".json":
            # Only parse JSON files that can actually contain the field.
            source=_text(root,rel,commit)
            if '"full_elpis_runtime_admission"' in source:
                records.extend(_json_declarations(rel,source))
    return sorted(
        records,
        key=lambda x:(x["path"],x["syntax"],x["qualname"],x["locator"]),
    )


def identity(record:dict[str,Any])->tuple[str,str,str,str]:
    return (
        record["path"],
        record["syntax"],
        record["qualname"],
        record["locator"],
    )


def classify(record:dict[str,Any])->str:
    path=record["path"]
    syntax=record["syntax"]
    locator=record["locator"]

    if (
        path==AUTHORITY_PATH
        and syntax=="python_assignment"
        and locator=="FULL_ELPIS_RUNTIME_ADMISSION"
    ):
        return "ACTIVE_RUNTIME_SOURCE_AUTHORITY"

    if (
        path=="tools/seal_release.py"
        and syntax=="python_dict_literal"
    ):
        return "ACTIVE_RELEASE_EMISSION_POLICY"

    if (
        path=="tools/verify_public_release.py"
        and syntax=="python_dict_literal"
    ):
        return "ACTIVE_RELEASE_VERIFICATION_POLICY"

    if (
        path==SEAL_PATH
        and syntax=="json_key"
        and locator=="/full_elpis_runtime_admission"
    ):
        return "HISTORICAL_SCOPED_EVIDENCE"

    if (
        RELEASE_RE.fullmatch(path)
        and syntax=="json_key"
        and locator=="/full_elpis_runtime_admission"
    ):
        return "HISTORICAL_RELEASE_SNAPSHOT"

    if (
        DISTRIBUTION_RE.fullmatch(path)
        and syntax=="json_key"
        and locator=="/full_elpis_runtime_admission"
    ):
        return "HISTORICAL_DISTRIBUTION_SNAPSHOT"

    raise TemporalityError(
        "UNCLASSIFIED_RUNTIME_ADMISSION_DECLARATION:"
        f"{identity(record)}={record['value']!r}"
    )


def _production_override_refs(root:Path)->list[str]:
    findings:list[str]=[]
    for rel in _tracked(root,None):
        p=PurePosixPath(rel)
        if p.suffix!=".py":
            continue
        if not any(
            rel==base or rel.startswith(base+"/")
            for base in PRODUCTION_ROOTS
        ):
            continue
        if any(part in EXCLUDED_PARTS for part in p.parts):
            continue
        source=_text(root,rel,None)
        try:
            tree=ast.parse(source,filename=rel)
        except SyntaxError as exc:
            raise TemporalityError(f"PARSE_FAILED:{rel}:{exc}") from exc
        for node in ast.walk(tree):
            if isinstance(node,ast.Constant) and isinstance(node.value,str):
                if "RUNTIME_E2E_SEAL_R0.json" in node.value:
                    findings.append(
                        f"HISTORICAL_SEAL_REFERENCED_BY_PRODUCTION:{rel}:{node.lineno}"
                    )
                if node.value=="full_elpis_runtime_admission":
                    findings.append(
                        f"HISTORICAL_JSON_ADMISSION_KEY_REFERENCED_BY_PRODUCTION:{rel}:{node.lineno}"
                    )
    return sorted(set(findings))


def build_baseline(root:Path)->dict[str,Any]:
    declarations=scan(root,BASELINE_COMMIT)
    records=[]
    for record in declarations:
        category=classify(record)
        enriched=dict(record)
        enriched["category"]=category
        if category in HISTORICAL_CATEGORIES:
            enriched["file_sha256"]=_sha(
                _bytes(root,record["path"],BASELINE_COMMIT)
            )
        records.append(enriched)

    active=[x for x in records if x["category"] in ACTIVE_CATEGORIES]
    if not active:
        raise TemporalityError("NO_ACTIVE_RUNTIME_ADMISSION_AUTHORITY")
    active_values={x["value"] for x in active}
    if active_values!={True}:
        raise TemporalityError(
            f"BASELINE_ACTIVE_AUTHORITIES_DISAGREE:{sorted(active_values)}"
        )

    return {
        "schema":SCHEMA,
        "baseline_commit":BASELINE_COMMIT,
        "policy":{
            "active_authorities":"MUST_AGREE_TRUE",
            "historical_evidence":"EXACT_BYTES_AND_VALUE_IMMUTABLE",
            "historical_override":"PRODUCTION_RUNTIME_MUST_NOT_READ_HISTORICAL_SEAL_OR_JSON_ADMISSION_KEY",
            "component_registry_scope":"DISTINCT_FROM_WHOLE_RUNTIME_ADMISSION",
            "new_declarations":"MUST_BE_EXPLICITLY_CLASSIFIED",
        },
        "declarations":records,
    }


def load_baseline(path:Path)->dict[str,Any]:
    data=json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema")!=SCHEMA:
        raise TemporalityError("TEMPORALITY_SCHEMA_INVALID")
    if data.get("baseline_commit")!=BASELINE_COMMIT:
        raise TemporalityError("TEMPORALITY_BASELINE_COMMIT_INVALID")
    records=data.get("declarations")
    if not isinstance(records,list):
        raise TemporalityError("TEMPORALITY_DECLARATIONS_INVALID")
    seen=set()
    for record in records:
        key=identity(record)
        if key in seen:
            raise TemporalityError(f"TEMPORALITY_DUPLICATE:{key}")
        seen.add(key)
        expected=classify(record)
        if record.get("category")!=expected:
            raise TemporalityError(
                f"TEMPORALITY_CATEGORY_MISMATCH:{key}:"
                f"{record.get('category')}!={expected}"
            )
        if expected in HISTORICAL_CATEGORIES:
            digest=record.get("file_sha256")
            if not isinstance(digest,str) or len(digest)!=64:
                raise TemporalityError(f"HISTORICAL_HASH_MISSING:{key}")
    return data


def _registry_scope(root:Path)->dict[str,Any]:
    registry=json.loads((root/PUBLIC_REGISTRY).read_text(encoding="utf-8"))
    top=registry.get("runtime_admission")
    components=registry.get("components")
    if top is not False:
        raise TemporalityError("PUBLIC_COMPONENT_REGISTRY_SCOPE_NOT_FALSE")
    if not isinstance(components,list) or not components:
        raise TemporalityError("PUBLIC_COMPONENT_REGISTRY_COMPONENTS_MISSING")
    bad=[
        x.get("component_id") or x.get("name") or "<unknown>"
        for x in components
        if x.get("runtime_admission") is not False
    ]
    if bad:
        raise TemporalityError(
            f"PUBLIC_COMPONENT_REGISTRY_COMPONENT_SCOPE_NONFALSE:{bad}"
        )
    return {
        "registry_runtime_admission":top,
        "component_count":len(components),
        "all_component_runtime_admission_false":True,
    }


def verify(root:Path,baseline_path:Path)->dict[str,Any]:
    baseline=load_baseline(baseline_path)
    registered={identity(x):x for x in baseline["declarations"]}
    current={identity(x):x for x in scan(root,None)}
    errors:list[str]=[]

    if set(current)!=set(registered):
        for key in sorted(set(current)-set(registered)):
            errors.append(f"UNREGISTERED_DECLARATION:{key}")
        for key in sorted(set(registered)-set(current)):
            errors.append(f"REGISTERED_DECLARATION_MISSING:{key}")

    active_values=[]
    historical_false=[]
    historical_true=[]

    for key,entry in registered.items():
        now=current.get(key)
        if now is None:
            continue
        expected_category=entry["category"]
        try:
            actual_category=classify(now)
        except TemporalityError as exc:
            errors.append(str(exc))
            continue
        if actual_category!=expected_category:
            errors.append(
                f"CATEGORY_DRIFT:{key}:{actual_category}!={expected_category}"
            )
            continue

        if expected_category in ACTIVE_CATEGORIES:
            active_values.append(now["value"])
        else:
            actual_hash=_sha(_bytes(root,now["path"],None))
            if actual_hash!=entry["file_sha256"]:
                errors.append(
                    f"HISTORICAL_BYTES_CHANGED:{key}:"
                    f"{actual_hash}!={entry['file_sha256']}"
                )
            if now["value"]!=entry["value"]:
                errors.append(
                    f"HISTORICAL_VALUE_CHANGED:{key}:"
                    f"{now['value']}!={entry['value']}"
                )
            (historical_true if now["value"] else historical_false).append(key)

    if not active_values:
        errors.append("NO_ACTIVE_AUTHORITIES")
    elif set(active_values)!={True}:
        errors.append(f"ACTIVE_AUTHORITIES_DISAGREE:{active_values}")

    override_findings=_production_override_refs(root)
    errors.extend(override_findings)

    try:
        scope=_registry_scope(root)
    except TemporalityError as exc:
        errors.append(str(exc))
        scope={}

    categories:dict[str,int]={}
    for entry in registered.values():
        c=entry["category"]
        categories[c]=categories.get(c,0)+1

    report={
        "schema":SCHEMA,
        "baseline_commit":BASELINE_COMMIT,
        "registered_declaration_count":len(registered),
        "current_declaration_count":len(current),
        "categories":dict(sorted(categories.items())),
        "active_values":active_values,
        "historical_true_count":len(historical_true),
        "historical_false_count":len(historical_false),
        "historical_false_declarations":[list(x) for x in historical_false],
        "production_override_findings":override_findings,
        "component_registry_scope":scope,
        "errors":errors,
        "status":"PASS" if not errors else "NONPASS",
    }
    if errors:
        raise TemporalityError(
            "RUNTIME_ADMISSION_TEMPORALITY_NONPASS:\n"+"\n".join(errors)
        )
    return report


def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--baseline",type=Path,default=None)
    parser.add_argument("--emit-baseline",action="store_true")
    args=parser.parse_args(argv)

    root=args.root.resolve()
    baseline=(
        args.baseline.resolve()
        if args.baseline is not None
        else root/"tools/runtime_admission_temporality_v1.json"
    )

    if args.emit_baseline:
        data=build_baseline(root)
        baseline.parent.mkdir(parents=True,exist_ok=True)
        baseline.write_text(
            json.dumps(data,indent=2,sort_keys=True,ensure_ascii=False)+"\n",
            encoding="utf-8",
        )
        print(json.dumps({
            "status":"EMITTED",
            "path":str(baseline),
            "baseline_commit":BASELINE_COMMIT,
            "declaration_count":len(data["declarations"]),
        },sort_keys=True))
        return 0

    report=verify(root,baseline)
    print(json.dumps(report,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
