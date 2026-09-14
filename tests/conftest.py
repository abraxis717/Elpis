from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


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
