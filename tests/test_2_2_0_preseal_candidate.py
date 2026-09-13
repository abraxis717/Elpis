from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def _release_identities():
    tree = ast.parse(
        (ROOT / "tools/verify_public_release.py").read_text(encoding="utf-8")
    )
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "RELEASE_IDENTITIES"
                for target in node.targets
            )
        ):
            return ast.literal_eval(node.value)
    raise AssertionError("RELEASE_IDENTITIES missing")


def test_2_2_0_current_release_declarations_are_exact() -> None:
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "2.2.0"

    project = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]
    assert project["version"] == "2.2.0"

    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert re.search(r'(?m)^version: "2\.2\.0"$', citation)

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert readme.count("**Release line: Elpis2.2.0**") == 1
    assert (
        "[`RELEASE_NOTES/Elpis2.2.0.md`]"
        "(RELEASE_NOTES/Elpis2.2.0.md)"
    ) in readme

    notes = (ROOT / "RELEASE_NOTES/Elpis2.2.0.md").read_text(
        encoding="utf-8"
    )
    assert notes.startswith("# Elpis2.2.0\n\n## Version: v2.2.0\n")
    assert "PUBLISHED_RELEASES.json" in notes

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.startswith(
        "## Elpis2.2.0 — Portability, release-integrity, "
        "and bounded internal capability successor\n"
    )


def test_2_2_0_release_identity_is_ratified_without_reinterpreting_baselines() -> None:
    identities = _release_identities()
    assert identities["2.2.0"] == {
        "primitive_closure_commit": (
            "482d4064321392108b87124cd47343d9c748f5bc"
        ),
        "base_release_commit": (
            "c911af22e01ee35c441d65e8dbcad18694bdcb2a"
        ),
    }


def test_adoption_policy_remains_internal_only() -> None:
    policy = json.loads(
        (
            ROOT / "manifests/ELPIS_2_2_0_ADOPTION_POLICY_R0.json"
        ).read_text(encoding="utf-8")
    )
    assert policy["target_release"] == "2.2.0"
    for item in policy["candidates"]:
        assert item["disposition"] == "SHIP_INTERNAL_QUALIFIED"
        assert item["stable_package_root_api"] is False
        assert item["runtime_admission_change"] is False


def test_pre_tag_publication_registry_remains_unchanged() -> None:
    registry = json.loads(
        (ROOT / "PUBLISHED_RELEASES.json").read_text(encoding="utf-8")
    )
    raw = json.dumps(registry, sort_keys=True)
    assert "2.2.0" not in raw
    assert "Elpis2.2.0" not in raw


def test_write_once_candidate_manifest_exists_and_targets_2_2_0() -> None:
    path = ROOT / "manifests/Elpis2.2.0.RELEASE_MANIFEST.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema"] == "elpis.release-manifest.v2"
    assert data["release_name"] == "Elpis2.2.0"
    assert data["release_tag"] == "Elpis2.2.0"
    assert data["version"] == "2.2.0"
    paths = {entry["path"] for entry in data["files"]}
    assert "manifests/ELPIS_2_2_0_ADOPTION_POLICY_R0.json" in paths
    assert "tests/test_2_2_0_adoption_policy.py" in paths
    assert "tests/test_2_2_0_preseal_candidate.py" in paths
    assert "RELEASE_NOTES/Elpis2.2.0.md" in paths
    assert "manifests/Elpis2.2.0.RELEASE_MANIFEST.json" not in paths
    assert "PUBLISHED_RELEASES.json" not in paths
