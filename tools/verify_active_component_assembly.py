#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SELECTOR_REL = Path("manifests/ACTIVE_COMPONENT_ASSEMBLY.json")
RETIRED_ID = "elpis_nanbeige42_host"


def _load(root: Path, path: Path, label: str, errors: list[str]):
    full = root / path
    if not full.is_file():
        errors.append(f"MISSING:{label}:{path.as_posix()}")
        return None
    try:
        value = json.loads(full.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"INVALID_JSON:{label}:{type(exc).__name__}")
        return None
    if type(value) is not dict:
        errors.append(f"ROOT_NOT_OBJECT:{label}")
        return None
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(value) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _self_hash(value: dict, field: str) -> str:
    return hashlib.sha256(
        _canonical_bytes({k: v for k, v in value.items() if k != field})
    ).hexdigest()


def _safe_rel(value):
    if type(value) is not str or not value:
        return None
    rel = Path(value)
    if rel.is_absolute() or ".." in rel.parts:
        return None
    return rel


def verify(root: Path = ROOT) -> list[str]:
    root = root.resolve()
    errors: list[str] = []

    selector = _load(root, SELECTOR_REL, "selector", errors)
    if selector is None:
        return errors

    if selector.get("schema") != "elpis.active-component-assembly.v1":
        errors.append("SELECTOR_SCHEMA")
    if selector.get("active_assembly") != "ELPIS_CANONICAL_ASSEMBLY_R2":
        errors.append("SELECTOR_ACTIVE_ASSEMBLY")
    if selector.get("runtime_admission") is not False:
        errors.append("SELECTOR_RUNTIME_ADMISSION")
    if selector.get("canonical_only_component_ids") != []:
        errors.append("SELECTOR_CANONICAL_ONLY_NOT_EMPTY")
    if selector.get("retired_component_ids") != [RETIRED_ID]:
        errors.append("SELECTOR_RETIRED_IDS")

    loaded = {}
    for label, key in (
        ("canonical", "canonical_manifest"),
        ("registry", "component_registry"),
        ("public", "public_registry"),
        ("graph", "public_dependency_graph"),
    ):
        rel = _safe_rel(selector.get(key))
        if rel is None:
            errors.append(f"SELECTOR_PATH:{label}")
            continue
        loaded[label] = _load(root, rel, label, errors)

    if any(loaded.get(x) is None for x in ("canonical", "registry", "public", "graph")):
        return errors

    canonical = loaded["canonical"]
    registry = loaded["registry"]
    public = loaded["public"]
    graph = loaded["graph"]

    if canonical.get("assembly_version") != "ELPIS_CANONICAL_ASSEMBLY_R2":
        errors.append("CANONICAL_VERSION")
    if registry.get("assembly_version") != "ELPIS_CANONICAL_ASSEMBLY_R2":
        errors.append("REGISTRY_VERSION")
    if canonical.get("runtime_admission") is not False:
        errors.append("CANONICAL_RUNTIME_ADMISSION")
    if registry.get("runtime_admission") is not False:
        errors.append("REGISTRY_RUNTIME_ADMISSION")
    if public.get("runtime_admission") is not False:
        errors.append("PUBLIC_RUNTIME_ADMISSION")

    canonical_items = canonical.get("components")
    registry_items = registry.get("components")
    public_items = public.get("components")
    if not all(type(v) is list for v in (canonical_items, registry_items, public_items)):
        errors.append("COMPONENT_LIST")
        return errors

    can_ids = [
        item.get("component_id")
        for item in canonical_items
        if type(item) is dict
    ]
    reg_ids = [
        item.get("component_id")
        for item in registry_items
        if type(item) is dict
    ]
    pub_ids = [
        item.get("component_id")
        for item in public_items
        if type(item) is dict
    ]

    if any(type(x) is not str or not x for x in can_ids):
        errors.append("CANONICAL_ID")
    if any(type(x) is not str or not x for x in reg_ids):
        errors.append("REGISTRY_ID")
    if any(type(x) is not str or not x for x in pub_ids):
        errors.append("PUBLIC_ID")

    if len(can_ids) != len(set(can_ids)):
        errors.append("CANONICAL_DUPLICATE")
    if len(reg_ids) != len(set(reg_ids)):
        errors.append("REGISTRY_DUPLICATE")
    if len(pub_ids) != len(set(pub_ids)):
        errors.append("PUBLIC_DUPLICATE")

    if canonical.get("component_count") != len(can_ids) or len(can_ids) != 16:
        errors.append("CANONICAL_COUNT")
    if registry.get("component_count") != len(reg_ids) or len(reg_ids) != 16:
        errors.append("REGISTRY_COUNT")
    if public.get("component_count") != len(pub_ids) or len(pub_ids) != 16:
        errors.append("PUBLIC_COUNT")
    if selector.get("component_count") != 16:
        errors.append("SELECTOR_COUNT")
    if selector.get("public_component_count") != 16:
        errors.append("SELECTOR_PUBLIC_COUNT")

    can_set = set(can_ids)
    reg_set = set(reg_ids)
    pub_set = set(pub_ids)
    if can_set != reg_set:
        errors.append("CANONICAL_REGISTRY_ID_SET")
    if can_set != pub_set:
        errors.append("CANONICAL_PUBLIC_ID_SET")
    if RETIRED_ID in can_set | reg_set | pub_set:
        errors.append("RETIRED_ID_ACTIVE")

    if canonical.get("dependency_order") != can_ids:
        errors.append("CANONICAL_DEPENDENCY_ORDER")
    if canonical.get("manifest_self_hash") != _self_hash(
        canonical, "manifest_self_hash"
    ):
        errors.append("CANONICAL_SELF_HASH")

    reg_by = {
        x["component_id"]: x
        for x in registry_items
        if type(x) is dict and type(x.get("component_id")) is str
    }
    pub_by = {
        x["component_id"]: x
        for x in public_items
        if type(x) is dict and type(x.get("component_id")) is str
    }

    derived_edges = []
    for component_id in sorted(pub_set):
        reg = reg_by.get(component_id)
        pub = pub_by.get(component_id)
        if reg is None or pub is None:
            continue

        if reg.get("runtime_admission") is not False:
            errors.append(f"REGISTRY_RUNTIME:{component_id}")
        if pub.get("runtime_admission") is not False:
            errors.append(f"PUBLIC_RUNTIME:{component_id}")

        rel = _safe_rel(pub.get("public_path"))
        if rel is None:
            errors.append(f"PUBLIC_PATH:{component_id}")
            continue
        component_root = root / rel
        manifest_path = component_root / "COMPONENT_MANIFEST.json"
        if not component_root.is_dir():
            errors.append(f"PUBLIC_COMPONENT_MISSING:{component_id}")
            continue
        manifest = _load(
            root,
            rel / "COMPONENT_MANIFEST.json",
            f"manifest:{component_id}",
            errors,
        )
        if manifest is None:
            continue
        if manifest.get("component_id") != component_id:
            errors.append(f"MANIFEST_ID:{component_id}")
        if manifest.get("runtime_admission") is not False:
            errors.append(f"MANIFEST_RUNTIME:{component_id}")

        pub_deps = pub.get("dependencies")
        reg_deps = reg.get("dependencies")
        man_deps = manifest.get("dependencies")
        if pub_deps != reg_deps:
            errors.append(f"REGISTRY_DEPENDENCIES:{component_id}")
        if pub_deps != man_deps:
            errors.append(f"MANIFEST_DEPENDENCIES:{component_id}")

        if type(pub_deps) is not list:
            errors.append(f"PUBLIC_DEPENDENCIES:{component_id}")
        else:
            for dep in pub_deps:
                if dep not in pub_set:
                    errors.append(
                        f"PUBLIC_DEPENDENCY_NONPUBLIC:{component_id}:{dep}"
                    )
                derived_edges.append({"from": component_id, "to": dep})

    nodes = graph.get("nodes")
    if (
        type(nodes) is not list
        or len(nodes) != len(set(nodes))
        or set(nodes) != pub_set
    ):
        errors.append("GRAPH_NODE_SET")

    edges = graph.get("edges")
    if type(edges) is not list:
        errors.append("GRAPH_EDGES")
    else:
        try:
            actual = sorted(
                (
                    {"from": x["from"], "to": x["to"]}
                    for x in edges
                ),
                key=lambda x: (x["from"], x["to"]),
            )
            expected = sorted(
                derived_edges,
                key=lambda x: (x["from"], x["to"]),
            )
            if actual != expected:
                errors.append("GRAPH_DEPENDENCY_EDGES")
        except Exception:
            errors.append("GRAPH_EDGE_RECORD")

    legacy = selector.get("legacy_r1")
    if type(legacy) is not dict:
        errors.append("LEGACY_BINDING")
    else:
        for label, path_key, hash_key in (
            ("canonical", "canonical_manifest", "canonical_sha256"),
            ("registry", "component_registry", "component_registry_sha256"),
            ("public", "public_registry", "public_registry_sha256"),
            ("graph", "public_dependency_graph", "public_dependency_graph_sha256"),
        ):
            rel = _safe_rel(legacy.get(path_key))
            expected = legacy.get(hash_key)
            if rel is None or type(expected) is not str:
                errors.append(f"LEGACY_BINDING:{label}")
                continue
            path = root / rel
            if not path.is_file():
                errors.append(f"LEGACY_MISSING:{label}")
            elif _sha(path) != expected:
                errors.append(f"LEGACY_HASH:{label}")

    for retired_path in (
        "components/elpis_nanbeige42_host",
        "native/elpis-nanbeige42-host",
    ):
        if (root / retired_path).exists():
            errors.append(f"RETIRED_PATH_PRESENT:{retired_path}")

    return errors


def main() -> int:
    errors = verify(ROOT)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print(f"NONQUAL_ACTIVE_ASSEMBLY_R2 errors={len(errors)}")
        return 1
    print("PASS_ACTIVE_ASSEMBLY_R2 canonical=16 public=16 canonical_only=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
