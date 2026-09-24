import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _function_source(rel: str, name: str) -> str:
    path = ROOT / rel
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=rel)

    hits = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]
    assert len(hits) == 1

    node = hits[0]
    lines = source.splitlines()
    return chr(10).join(
        lines[node.lineno - 1 : node.end_lineno]
    )


def test_known_authority_readers_use_release_git():
    targets = (
        (
            "tests/test_current_release_hygiene.py",
            "test_current_manifest_and_published_registry_are_truthful_when_present",
        ),
        (
            "tests/test_seal_release_mutations.py",
            "test_real_sealed_tree_verifies_without_reseal",
        ),
        (
            "tests/test_seal_release_mutations.py",
            "copy_repo",
        ),
        (
            "tests/test_compact_release_manifest_v3.py",
            "test_historical_v2_archive_verifies_without_migration",
        ),
        (
            "tests/test_physical_release_snapshot.py",
            "checkout",
        ),
        (
            "tests/test_release_immutability_gate_integration.py",
            "test_public_release_embedded_gate_rejects_model_identity_mutation",
        ),
        (
            "tests/test_immutable_evidence_contract.py",
            "test_bootstrap_provenance_is_frozen_and_baseline_is_committed",
        ),
        (
            "tests/test_grid81_writer_successor_component_manifests_r0.py",
            "_tracked_inventory",
        ),
        (
            "tests/test_grid81_writer_successor_component_manifests_r0.py",
            "test_qualification_commits_are_ancestors_of_current_engineering_head",
        ),
        (
            "tests/test_tag_disposition_closure.py",
            "_git",
        ),
        (
            "tests/test_published_releases_registry.py",
            "_git",
        ),
        (
            "tests/test_published_releases_registry.py",
            "test_current_tagged_but_unpublished_state_is_valid_when_present",
        ),
        (
            "tests/test_2_2_29_failed_seal.py",
            "_git",
        ),
    )

    for rel, name in targets:
        source = _function_source(rel, name)
        assert "release_git." in source
        assert '["git"' not in source
        assert "['git'" not in source


def test_hosted_authority_reads_use_streaming_boundary():
    workflows = (
        ".github/workflows/pypi-publish.yaml",
        ".github/workflows/ci.yml",
        ".github/workflows/reference-runtime.yml",
    )
    authority_commands = re.compile(
        r"\bgit\s+(?:fetch|cat-file|rev-parse|rev-list|archive|show)\b"
    )

    findings = []

    for rel in workflows:
        for lineno, line in enumerate(
            (ROOT / rel).read_text(encoding="utf-8").splitlines(),
            1,
        ):
            if authority_commands.search(line):
                findings.append(f"{rel}:{lineno}:{line.strip()}")

    assert findings == []


def test_streaming_cli_routes_through_shared_boundary():
    cli = (
        ROOT / "tools/release_git_cli.py"
    ).read_text(encoding="utf-8")
    shared = (
        ROOT / "tools/release_git.py"
    ).read_text(encoding="utf-8")

    assert "release_git.run_stream(" in cli
    assert '["git", "--no-replace-objects"]' in shared
    assert "env=sealed_git_env()" in shared
