#!/usr/bin/env python3
"""Qualify the frozen, verification-only Furyan R0 component.

Default: verify identity/boundaries, then run local conformance and the existing
44,005-case root science gate in a fresh hermetic pytest process. --identity-only
checks metadata and source boundaries; it does NOT claim scientific qualification.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
COMPONENT_REL = Path("components/FuryanLocusOracle")
MANIFEST_REL = COMPONENT_REL / "COMPONENT_MANIFEST.json"
ROOT_GATE = "tests/test_furyan_release_integration.py"
LOCAL_GATE = "components/FuryanLocusOracle/tests/test_furyan_qualification.py"
# One immutable anchor for the original eleven file hashes, migrated from the
# root gate. Rehashing edited R0 bytes in the manifest cannot qualify a successor.
FROZEN_INVENTORY_SHA256 = "2896619e9056277ee04ca10f809fb8b3591e5d1dc06b35b30878f7fc49e7c35c"
PROVENANCE = {
    "source_commit": "59241be905c15947deddbdc67ae1bf3de81620cb",
    "source_tree": "72b4be025992e16020e5f7a76f3b60ca089a1e7c",
    "source_parent_commit": "dcbc011d7f55707e4fdf998de744f7794675a656",
    "qualification_base_commit": "3222c77099ae152e02287b63276e95d805794333",
    "qualification_base_tree": "020b8764364fb89bdd903b4fcffb67cd768a1753",
}
DENIED_AUTHORITIES = (
    "runtime_admission", "public_registry_admission", "admission_authority",
    "execution_authority", "allocation_authority", "generated_source_execution_authority",
    "model_authority", "semantic_truth_authority", "production_allocator_substitution",
)
# Closed per-file import graph, including every transitive local dependency.
# The reference cannot even import transport or certificate code. The validator
# can share transport only; it cannot invoke candidate search or matching.
IMPORTS = {
    "FuryanLocusOracle.py": {"json", "sys", "contract"},
    "certificate_validator.py": {"contract"},
    "contract.py": {"hashlib", "json", "re"},
    "tests/reference.py": {"itertools", "functools"},
    "tests/baseline.py": {"reference"},
    "tests/corpus.py": {"itertools", "json"},
}
FORBIDDEN_NAMES = {
    "__import__", "__builtins__", "eval", "exec", "compile", "open",
    "getattr", "setattr", "delattr", "globals", "locals", "vars", "breakpoint",
}
SYS_ATTRIBUTES = {"stdin", "stdout"}


class QualificationError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise QualificationError(reason)


def canonical(value):
    # Same canonical JSON convention as the internal successor manifests.
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe_file(root, name):
    rel = Path(name)
    require(not rel.is_absolute() and ".." not in rel.parts and bool(rel.parts),
            f"UNSAFE_PATH:{name}")
    cursor = root
    for part in rel.parts:
        cursor = cursor / part
        require(not cursor.is_symlink(), f"SYMLINK:{name}")
    require(cursor.is_file(), f"MISSING:{name}")
    return cursor


def inventory_entry(root, name):
    data = safe_file(root, name).read_bytes()
    return {"path": name, "sha256": sha(data), "size": len(data)}


def audit_source(name, source):
    """Closed imports plus rejection of dynamic loaders/introspection.

    This is a structural audit of byte-pinned source, not a general Python
    sandbox. Immutability rejects arbitrary rewrites even if they pass this AST
    policy; negative tests exercise this policy separately from the byte pins.
    """
    tree = ast.parse(source, filename=name)
    modules = set()
    sys_aliases = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
                if alias.name == "sys":
                    sys_aliases.add(alias.asname or "sys")
        elif isinstance(node, ast.ImportFrom):
            require(node.level == 0 and all(a.name != "*" for a in node.names),
                    f"IMPORT_BOUNDARY:{name}")
            modules.add(node.module)
            require(node.module != "sys", f"DYNAMIC_ACCESS:{name}")
        elif isinstance(node, ast.Name):
            require(node.id not in FORBIDDEN_NAMES, f"DYNAMIC_ACCESS:{name}")
        elif isinstance(node, ast.Attribute):
            require(not node.attr.startswith("__"), f"DYNAMIC_ACCESS:{name}")
    require(modules == IMPORTS[name], f"IMPORT_BOUNDARY:{name}:{sorted(modules)}")
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in sys_aliases:
            # Every sys reference must be a direct access to CLI streams.
            require(any(isinstance(parent, ast.Attribute) and parent.value is node
                        and parent.attr in SYS_ATTRIBUTES for parent in ast.walk(tree)),
                    f"DYNAMIC_ACCESS:{name}")
    return sorted(modules)


def verify(root=ROOT):
    """Fail closed without executing any component code; also usable in exports."""
    root = Path(root).resolve()
    manifest = json.loads(safe_file(root, MANIFEST_REL).read_text(encoding="utf-8"))
    for key, expected in {
        "schema": "elpis.component_manifest.v1",
        "component_id": "FuryanLocusOracle_R0",
        "component_path": COMPONENT_REL.as_posix(),
        "version": "R0",
        "component_role": "INDEPENDENT_MATHEMATICAL_FALSIFIER",
        "qualification_disposition": "QUALIFIED_VERIFICATION_COMPONENT",
        "dependencies": [],
        "provenance": PROVENANCE,
        "manifest_self_hash_contract": "sha256(canonical-json(manifest without manifest_self_hash))",
        "component_content_digest_contract": "sha256(canonical-json(source_inventory))",
        "qualification_command": "python tools/verify_furyan_locus_oracle.py",
        "scientific_gate": ROOT_GATE,
        "local_conformance_gate": LOCAL_GATE,
    }.items():
        require(manifest.get(key) == expected, f"MANIFEST_FIELD:{key}")
    for key in DENIED_AUTHORITIES:
        require(manifest.get(key) is False, f"AUTHORITY:{key}")
    require(manifest.get("manifest_self_hash") == sha(canonical({
        k: v for k, v in manifest.items() if k != "manifest_self_hash"
    })), "MANIFEST_SELF_HASH")
    component = root / COMPONENT_REL
    frozen = manifest["frozen_r0_files"]
    require(sha(canonical(frozen)) == FROZEN_INVENTORY_SHA256,
            "FROZEN_R0_AUTHORITY_CHANGED:qualify a versioned successor")
    for name, digest in frozen.items():
        require(sha(safe_file(component, name).read_bytes()) == digest,
                f"FROZEN_R0_BYTES:{name}")
    require(manifest["model_digest"] == frozen["FURYAN_R0_SPEC.md"], "MODEL_DIGEST")
    names = []
    for path in component.rglob("*"):
        rel = path.relative_to(component)
        require(not path.is_symlink(), f"SYMLINK:{rel}")
        if any(p in {"__pycache__", ".pytest_cache"} for p in rel.parts):
            continue
        if path.is_file() and rel.as_posix() != "COMPONENT_MANIFEST.json":
            names.append(rel.as_posix())
    actual = [inventory_entry(component, name) for name in sorted(names)]
    require(manifest["source_inventory"] == actual, "SOURCE_INVENTORY")
    require(manifest["component_content_digest"] == sha(canonical(actual)), "CONTENT_DIGEST")
    evidence = manifest["evidence_references"]
    require(set(evidence) == {ROOT_GATE, "tools/verify_furyan_locus_oracle.py"}, "EVIDENCE_SET")
    for name, expected in evidence.items():
        require(inventory_entry(root, name) == expected, f"EVIDENCE_BYTES:{name}")
    imports = {name: audit_source(name, safe_file(component, name).read_text(encoding="utf-8"))
               for name in IMPORTS}
    for registry in ("manifests/PUBLIC_COMPONENT_REGISTRY.json", "COMPONENT_REGISTRY.json"):
        data = json.loads(safe_file(root, registry).read_text(encoding="utf-8"))
        require(all(item["component_id"] != manifest["component_id"] for item in data["components"]),
                f"UNQUALIFIED_REGISTRY_ADMISSION:{registry}")
    return {"status": "IDENTITY_AND_INDEPENDENCE_PASS", "component_id": manifest["component_id"],
            "manifest_self_hash": manifest["manifest_self_hash"], "frozen_files": len(frozen),
            "imports": imports, "runtime_admission": False, "public_registry_admission": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity-only", action="store_true")
    args = parser.parse_args()
    try:
        report = verify()
        print(json.dumps(report, sort_keys=True), flush=True)
        if args.identity_only:
            return 0
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
        with tempfile.TemporaryDirectory(prefix=".furyan-qualification-", dir=ROOT) as scratch:
            env["TMPDIR"] = scratch
            result = subprocess.run([
                sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-o", "addopts=", "-v",
                "--basetemp", str(Path(scratch) / "pytest"), LOCAL_GATE, ROOT_GATE,
            ], cwd=ROOT, env=env)
        if result.returncode:
            print("FURYAN_R0_NONQUAL:scientific_or_conformance_gate_failed", flush=True)
            return result.returncode
        verify()  # Detect byte changes during qualification too.
        print("FURYAN_R0_QUALIFIED:44005_core_cases;12_mutants_killed;verification_only", flush=True)
        return 0
    except (QualificationError, OSError, ValueError, KeyError, TypeError, SyntaxError) as exc:
        print(f"FURYAN_R0_NONQUAL:{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
