from __future__ import annotations

import os
from pathlib import Path
import tomllib

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _pytest_source_roots() -> tuple[Path, ...]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    rels = data["tool"]["pytest"]["ini_options"]["pythonpath"]
    return tuple((ROOT / rel).resolve() for rel in rels)


_roots = _pytest_source_roots()
_existing = os.environ.get("PYTHONPATH")
_parts = [str(path) for path in _roots]
if _existing:
    _parts.append(_existing)
os.environ["PYTHONPATH"] = os.pathsep.join(_parts)


# These tests verify Git history, tracked inventories, or release sealing.
# They are repository-provenance tests, not runtime/package portability tests.
GIT_AUTHORITY_TEST_MODULES = frozenset(
    {
        "tests/test_grid81_writer_successor_assembly_verifier_r0.py",
        "tests/test_grid81_writer_successor_component_manifests_r0.py",
        "tests/test_published_releases_registry.py",
        "tests/test_seal_release_mutations.py",
    }
)


def pytest_collection_modifyitems(config, items) -> None:
    del config
    for item in items:
        try:
            rel = item.path.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            continue
        if rel in GIT_AUTHORITY_TEST_MODULES:
            item.add_marker(pytest.mark.requires_git)
