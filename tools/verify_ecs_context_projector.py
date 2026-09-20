#!/usr/bin/env python3
"""Verify the ECSContextProjector read-only component identity and boundaries."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
COMPONENT_REL = Path("components/ECSContextProjector")
MANIFEST_REL = COMPONENT_REL / "COMPONENT_MANIFEST.json"

QUALIFIED_CORE = {
    "__init__.py": "38209b7560752dadb9fa15f9fb09d0b5aa81d60048023ea551ba407cc0217051",
    "contracts.py": "424741f6390e68ca4930237c9c710109f359521ee2738978e3615489f1779e6c",
    "projector.py": "459aa5608678f0e28e5528bb7a5f2e8ecd0183fae4e42aefce5cd0de0eca2f55",
}
ADAPTER_SHA256 = "d74dbe83b5c52636ff677dfc05b467ee072c5384896f966a0ddf46cc233705e0"
DENIED = (
    "runtime_admission",
    "public_registry_admission",
    "mutation_authority",
    "execution_authority",
    "model_authority",
    "network_authority",
    "semantic_truth_authority",
    "history_authentication_authority",
    "canonical_admission_authority",
)

class VerificationError(ValueError):
    pass

def require(condition, reason):
    if not condition:
        raise VerificationError(reason)

def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("utf-8")

def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())

def safe_file(root: Path, rel_text: str) -> Path:
    rel = Path(rel_text)
    require(
        bool(rel.parts) and not rel.is_absolute() and ".." not in rel.parts,
        f"UNSAFE_PATH:{rel_text}",
    )
    cur = root
    for part in rel.parts:
        cur = cur / part
        require(not cur.is_symlink(), f"SYMLINK:{rel_text}")
    require(cur.is_file(), f"MISSING:{rel_text}")
    return cur

def inventory_entry(component: Path, rel_text: str) -> dict:
    p = safe_file(component, rel_text)
    data = p.read_bytes()
    return {"path": rel_text, "sha256": sha_bytes(data), "size": len(data)}

def component_inventory(component: Path) -> list[dict]:
    names = []
    for p in component.rglob("*"):
        rel = p.relative_to(component)
        if any(x in {"__pycache__", ".pytest_cache"} for x in rel.parts):
            continue
        require(not p.is_symlink(), f"SYMLINK:{rel.as_posix()}")
        if p.is_file() and rel.as_posix() != "COMPONENT_MANIFEST.json":
            names.append(rel.as_posix())
    return [inventory_entry(component, n) for n in sorted(names)]

def verify_adapter_structure(adapter_path: Path) -> None:
    tree = ast.parse(adapter_path.read_text(encoding="utf-8"), filename=str(adapter_path))
    private_attrs = sorted({
        n.attr for n in ast.walk(tree)
        if isinstance(n, ast.Attribute) and n.attr.startswith("_")
    })
    require(private_attrs == [], f"ADAPTER_PRIVATE_ATTRIBUTE:{private_attrs}")
    forbidden_calls = {
        "found_entity", "activate", "dormant", "reactivate", "terminate",
        "enqueue", "step", "run_until_quiescent", "checkpoint", "close", "open",
    }
    calls = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            calls.add(node.func.attr)
    require(
        not (calls & forbidden_calls),
        f"ADAPTER_MUTATION_CALL:{sorted(calls & forbidden_calls)}",
    )

def verify(root: Path = ROOT) -> dict:
    root = Path(root).resolve()
    component = root / COMPONENT_REL
    require(component.is_dir(), "COMPONENT_MISSING")
    manifest_path = safe_file(root, MANIFEST_REL.as_posix())
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    expected_fields = {
        "schema": "elpis.component_manifest.v1",
        "component_id": "ECSContextProjector",
        "component_path": COMPONENT_REL.as_posix(),
        "version": "R0",
        "component_role": "DETERMINISTIC_READ_ONLY_ECS_HISTORY_PROJECTION",
        "package_name": "elpis_ecs_context",
        "qualification_disposition": "QUALIFIED_READ_ONLY_COMPONENT",
        "dependencies": [],
        "runtime_import_dependencies": ["elpis_ecs"],
        "public_interface_paths": ["src/elpis_ecs_context/"],
        "qualification_command": "python tools/verify_ecs_context_projector.py",
        "qualification_gate": "tests/test_ecs_context_projector_component_contract.py",
        "integration_base_release": "Elpis2.2.22",
        "integration_base_commit": "85755f2e91cda900af857dacc4c2cadf799baa8c",
        "manifest_self_hash_contract":
            "sha256(canonical-json(manifest without manifest_self_hash))",
        "component_content_digest_contract":
            "sha256(canonical-json(source_inventory))",
        "qualified_core_sha256": QUALIFIED_CORE,
        "kernel_adapter_sha256": ADAPTER_SHA256,
    }
    for key, expected in expected_fields.items():
        require(manifest.get(key) == expected, f"MANIFEST_FIELD:{key}")

    for key in DENIED:
        require(manifest.get(key) is False, f"AUTHORITY_NOT_DENIED:{key}")

    claims = manifest.get("claims_not_made")
    require(type(claims) is list and claims, "CLAIMS_NOT_MADE")

    inv = component_inventory(component)
    require(manifest.get("source_inventory") == inv, "SOURCE_INVENTORY")
    require(
        manifest.get("component_content_digest") == sha_bytes(canonical(inv)),
        "COMPONENT_CONTENT_DIGEST",
    )

    no_self = {k: v for k, v in manifest.items() if k != "manifest_self_hash"}
    require(
        manifest.get("manifest_self_hash") == sha_bytes(canonical(no_self)),
        "MANIFEST_SELF_HASH",
    )

    for name, digest in QUALIFIED_CORE.items():
        p = component / "src/elpis_ecs_context" / name
        require(sha_file(p) == digest, f"QUALIFIED_CORE_BYTES:{name}")

    adapter = component / "src/elpis_ecs_context/kernel_adapter.py"
    require(sha_file(adapter) == ADAPTER_SHA256, "KERNEL_ADAPTER_BYTES")
    verify_adapter_structure(adapter)

    evidence = manifest.get("evidence_references")
    require(type(evidence) is dict, "EVIDENCE_REFERENCES")
    for rel, entry in sorted(evidence.items()):
        require(type(entry) is dict, f"EVIDENCE_ENTRY:{rel}")
        p = safe_file(root, rel)
        data = p.read_bytes()
        require(entry.get("path") == rel, f"EVIDENCE_PATH:{rel}")
        require(entry.get("sha256") == sha_bytes(data), f"EVIDENCE_SHA256:{rel}")
        require(entry.get("size") == len(data), f"EVIDENCE_SIZE:{rel}")

    return {
        "component_id": manifest["component_id"],
        "manifest_self_hash": manifest["manifest_self_hash"],
        "component_content_digest": manifest["component_content_digest"],
        "source_file_count": len(inv),
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        result = verify(args.root)
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 1
    print("PASS: ECSContextProjector component authority verified")
    print(json.dumps(result, sort_keys=True))
    return 0

if __name__ == "__main__":
    sys.exit(main())
