#!/usr/bin/env python3
"""Recompute and verify the current public canonical assembly.

Trust boundary:
- The VERSION-selected release/distribution manifest authenticates shipped
  COMPONENT_MANIFEST.json files through v2 byte pins or the v3 tree aggregate.
- ELPIS_CANONICAL_MANIFEST.json and COMPONENT_REGISTRY.json legacy manifest
  digest fields are preserved as historical consistency metadata. Their
  historical preimage is not redefined here.
- Structural claims (counts, IDs, dependencies, graph edges, mappings) are
  recomputed from the loaded inventories rather than pinned to magic counts.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import runpy
import sys
from typing import Any


CANONICAL_ONLY = {"elpis_nanbeige42_host"}
NON_SHIPPED_PATHS = (
    "components/elpis_nanbeige42_host",
    "native/elpis-nanbeige42-host",
)

CANONICAL_REL = Path("ELPIS_CANONICAL_MANIFEST.json")
COMPONENT_REGISTRY_REL = Path("COMPONENT_REGISTRY.json")
PUBLIC_REGISTRY_REL = Path("manifests/PUBLIC_COMPONENT_REGISTRY.json")
PUBLIC_GRAPH_REL = Path("manifests/PUBLIC_DEPENDENCY_GRAPH.json")


def _load_json(path: Path, label: str, errors: list[str]) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append(f"MISSING:{label}:{path}")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"INVALID_JSON:{label}:{type(exc).__name__}")
        return None
    if type(value) is not dict:
        errors.append(f"ROOT_NOT_OBJECT:{label}")
        return None
    return value


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_sha256(value: Any) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(ch in "0123456789abcdef" for ch in value)
    )


def _safe_relative(value: Any) -> Path | None:
    if type(value) is not str or not value:
        return None
    rel = Path(value)
    if rel.is_absolute() or ".." in rel.parts:
        return None
    return rel


def _id_list(
    container: dict[str, Any],
    field: str,
    label: str,
    errors: list[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    items = container.get(field)
    if type(items) is not list:
        errors.append(f"{label}_LIST")
        return [], []

    objects: list[dict[str, Any]] = []
    ids: list[str] = []
    for index, item in enumerate(items):
        if type(item) is not dict:
            errors.append(f"{label}_ITEM:{index}")
            continue
        component_id = item.get("component_id")
        if type(component_id) is not str or not component_id:
            errors.append(f"{label}_COMPONENT_ID:{index}")
            continue
        objects.append(item)
        ids.append(component_id)

    if len(ids) != len(set(ids)):
        errors.append(f"{label}_DUPLICATE_ID")
    return objects, ids


def _release_file_pins(
    root: Path,
    errors: list[str],
) -> tuple[Path | None, dict[str, str] | set[str]]:
    """Return legacy byte pins or v3-authenticated publication membership."""
    version_path = root / "VERSION"
    if not version_path.is_file():
        errors.append("VERSION_MISSING")
        return None, {}

    version = version_path.read_text(encoding="utf-8").strip()
    distribution_rel = Path(
        f"manifests/Elpis{version}.DISTRIBUTION_MANIFEST.json"
    )
    release_rel = Path(f"manifests/Elpis{version}.RELEASE_MANIFEST.json")
    authority_rel = (
        distribution_rel
        if (root / distribution_rel).is_file()
        else release_rel
    )
    authority = _load_json(
        root / authority_rel,
        "release_byte_authority",
        errors,
    )
    if authority is None:
        return authority_rel, {}

    if authority.get("schema") == "elpis.release-manifest.v3":
        compact = runpy.run_path(str(Path(__file__).with_name("release_tree_digest.py")))
        try:
            compact["require_successor"](version)
            if authority_rel != release_rel or any(
                authority.get(key) != expected for key, expected in (
                    ("version", version),
                    ("release_name", f"Elpis{version}"),
                    ("release_tag", f"Elpis{version}"),
                )
            ):
                raise ValueError("V3_RELEASE_SELECTION_MISMATCH")
            findings = compact["verify_record"](root, authority_rel.as_posix(), authority)
            if findings:
                errors.extend(f"RELEASE_AUTHORITY:{finding}" for finding in findings)
                return authority_rel, set()
            # Membership is independently derived, never supplied by the record.
            # In Git this also prevents untracked component files from acquiring
            # byte authority merely because the rest of the tree verifies.
            return authority_rel, set(compact["publication_paths"](root, authority_rel.as_posix()))
        except (ValueError, OSError, RuntimeError) as exc:
            errors.append(f"RELEASE_AUTHORITY:{exc}")
            return authority_rel, set()

    entries = authority.get("files")
    if type(entries) is not list:
        errors.append("RELEASE_AUTHORITY_FILES")
        return authority_rel, {}

    pins: dict[str, str] = {}
    for index, entry in enumerate(entries):
        if type(entry) is not dict:
            errors.append(f"RELEASE_AUTHORITY_ENTRY:{index}")
            continue
        rel = entry.get("path")
        digest = entry.get("sha256")
        if type(rel) is not str or not rel:
            errors.append(f"RELEASE_AUTHORITY_PATH:{index}")
            continue
        if not _is_sha256(digest):
            errors.append(f"RELEASE_AUTHORITY_DIGEST:{rel}")
            continue
        if rel in pins:
            errors.append(f"RELEASE_AUTHORITY_DUPLICATE:{rel}")
            continue
        pins[rel] = digest
    return authority_rel, pins


def _deps(
    item: dict[str, Any],
    component_id: str,
    label: str,
    errors: list[str],
) -> list[str] | None:
    value = item.get("dependencies")
    if (
        type(value) is not list
        or not all(type(dep) is str and dep for dep in value)
        or len(value) != len(set(value))
    ):
        errors.append(f"{label}_DEPENDENCIES:{component_id}")
        return None
    return value


def verify(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []

    canonical = _load_json(root / CANONICAL_REL, "canonical", errors)
    component_registry = _load_json(
        root / COMPONENT_REGISTRY_REL,
        "component_registry",
        errors,
    )
    public = _load_json(root / PUBLIC_REGISTRY_REL, "public_registry", errors)
    graph = _load_json(root / PUBLIC_GRAPH_REL, "public_graph", errors)
    _, release_pins = _release_file_pins(root, errors)

    if any(
        value is None
        for value in (canonical, component_registry, public, graph)
    ):
        return errors

    assert canonical is not None
    assert component_registry is not None
    assert public is not None
    assert graph is not None

    canonical_items, canonical_ids = _id_list(
        canonical, "components", "CANONICAL", errors
    )
    registry_items, registry_ids = _id_list(
        component_registry, "components", "COMPONENT_REGISTRY", errors
    )
    public_items, public_ids = _id_list(
        public, "components", "PUBLIC_REGISTRY", errors
    )

    if canonical.get("component_count") != len(canonical_items):
        errors.append("CANONICAL_COMPONENT_COUNT")
    if component_registry.get("component_count") != len(registry_items):
        errors.append("COMPONENT_REGISTRY_COMPONENT_COUNT")
    if public.get("component_count") != len(public_items):
        errors.append("PUBLIC_COMPONENT_COUNT")

    if canonical.get("runtime_admission") is not False:
        errors.append("CANONICAL_RUNTIME_ADMISSION")
    if component_registry.get("runtime_admission") is not False:
        errors.append("COMPONENT_REGISTRY_RUNTIME_ADMISSION")
    if public.get("runtime_admission") is not False:
        errors.append("PUBLIC_RUNTIME_ADMISSION")

    canonical_set = set(canonical_ids)
    registry_set = set(registry_ids)
    public_set = set(public_ids)

    if registry_set != canonical_set:
        errors.append("COMPONENT_REGISTRY_ID_SET")
    if not CANONICAL_ONLY <= canonical_set:
        errors.append("CANONICAL_ONLY_MISSING")
    if public_set != canonical_set - CANONICAL_ONLY:
        errors.append("PUBLIC_ID_SET")

    dependency_order = canonical.get("dependency_order")
    if dependency_order != canonical_ids:
        errors.append("CANONICAL_DEPENDENCY_ORDER")

    canonical_by_id = {
        item["component_id"]: item
        for item in canonical_items
        if item.get("component_id")
    }
    registry_by_id = {
        item["component_id"]: item
        for item in registry_items
        if item.get("component_id")
    }
    public_by_id = {
        item["component_id"]: item
        for item in public_items
        if item.get("component_id")
    }

    # Preserve legacy digest fields as historical metadata, but at least bind
    # the two legacy declarations to one another and require canonical syntax.
    # Current shipped bytes are authenticated independently below.
    for component_id in sorted(canonical_set & registry_set):
        can = canonical_by_id[component_id]
        reg = registry_by_id[component_id]
        can_digest = can.get("manifest_digest")
        reg_digest = reg.get("component_manifest_digest")
        if not _is_sha256(can_digest):
            errors.append(f"LEGACY_CANONICAL_DIGEST:{component_id}")
        if not _is_sha256(reg_digest):
            errors.append(f"LEGACY_REGISTRY_DIGEST:{component_id}")
        if can_digest != reg_digest:
            errors.append(f"LEGACY_DIGEST_BINDING:{component_id}")
        if can.get("relative_path") != reg.get("relative_path"):
            errors.append(f"LEGACY_RELATIVE_PATH_BINDING:{component_id}")
        if reg.get("runtime_admission") is not False:
            errors.append(f"REGISTRY_RUNTIME_ADMISSION:{component_id}")

    derived_edges: list[dict[str, str]] = []

    for component_id in sorted(public_set):
        pub = public_by_id[component_id]
        if pub.get("runtime_admission") is not False:
            errors.append(f"PUBLIC_COMPONENT_RUNTIME_ADMISSION:{component_id}")

        public_rel = _safe_relative(pub.get("public_path"))
        if public_rel is None:
            errors.append(f"PUBLIC_PATH:{component_id}")
            continue

        # Reject symlink traversal in the shipped mapping.
        cursor = root
        unsafe_symlink = False
        for part in public_rel.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                errors.append(f"PUBLIC_PATH_SYMLINK:{component_id}")
                unsafe_symlink = True
                break
        if unsafe_symlink:
            continue

        component_root = root / public_rel
        manifest_rel = public_rel / "COMPONENT_MANIFEST.json"
        manifest_path = root / manifest_rel
        if not component_root.is_dir():
            errors.append(f"PUBLIC_COMPONENT_PATH_MISSING:{component_id}")
            continue
        manifest = _load_json(
            manifest_path,
            f"component_manifest:{component_id}",
            errors,
        )
        if manifest is None:
            continue

        release_key = manifest_rel.as_posix()
        if release_key not in release_pins:
            errors.append(f"RELEASE_MANIFEST_PIN_MISSING:{component_id}")
        elif isinstance(release_pins, dict) and _sha256_file(manifest_path) != release_pins[release_key]:
            errors.append(f"RELEASE_MANIFEST_DIGEST:{component_id}")

        if manifest.get("component_id") != component_id:
            errors.append(f"MANIFEST_COMPONENT_ID:{component_id}")
        if manifest.get("runtime_admission") is not False:
            errors.append(f"MANIFEST_RUNTIME_ADMISSION:{component_id}")

        public_deps = _deps(pub, component_id, "PUBLIC", errors)
        manifest_deps = _deps(manifest, component_id, "MANIFEST", errors)
        registry = registry_by_id.get(component_id)
        registry_deps = (
            _deps(registry, component_id, "REGISTRY", errors)
            if registry is not None
            else None
        )

        if public_deps is not None:
            for dep in public_deps:
                if dep not in public_set:
                    errors.append(
                        f"PUBLIC_DEPENDENCY_NONPUBLIC:{component_id}:{dep}"
                    )
                derived_edges.append({"from": component_id, "to": dep})

        if (
            public_deps is not None
            and manifest_deps is not None
            and manifest_deps != public_deps
        ):
            errors.append(f"MANIFEST_DEPENDENCY_BINDING:{component_id}")
        if (
            public_deps is not None
            and registry_deps is not None
            and registry_deps != public_deps
        ):
            errors.append(f"REGISTRY_DEPENDENCY_BINDING:{component_id}")

    graph_nodes = graph.get("nodes")
    if (
        type(graph_nodes) is not list
        or len(graph_nodes) != len(set(graph_nodes))
        or set(graph_nodes) != public_set
    ):
        errors.append("GRAPH_NODE_SET")

    graph_edges = graph.get("edges")
    if type(graph_edges) is not list:
        errors.append("GRAPH_EDGES")
    else:
        normalized: list[dict[str, str]] = []
        valid = True
        for index, edge in enumerate(graph_edges):
            if (
                type(edge) is not dict
                or type(edge.get("from")) is not str
                or type(edge.get("to")) is not str
            ):
                errors.append(f"GRAPH_EDGE:{index}")
                valid = False
                continue
            normalized.append(
                {"from": edge["from"], "to": edge["to"]}
            )
        if valid:
            if len({
                (edge["from"], edge["to"]) for edge in normalized
            }) != len(normalized):
                errors.append("GRAPH_DUPLICATE_EDGE")
            expected_edges = sorted(
                derived_edges,
                key=lambda item: (item["from"], item["to"]),
            )
            actual_edges = sorted(
                normalized,
                key=lambda item: (item["from"], item["to"]),
            )
            if actual_edges != expected_edges:
                errors.append("GRAPH_DEPENDENCY_EDGES")

    for relative in NON_SHIPPED_PATHS:
        if (root / relative).exists():
            errors.append(f"CANONICAL_ONLY_PATH_SHIPPED:{relative}")

    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = verify(root)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print(f"FAIL: {len(errors)} canonical assembly error(s)")
        return 1

    print(
        "PASS: canonical assembly recomputed from derived inventories, "
        "manifest contents, dependency graph, and published byte authority; "
        "legacy manifest_digest fields are consistency-only metadata"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
