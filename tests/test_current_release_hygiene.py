from __future__ import annotations

import hashlib
import json
from pathlib import Path
import runpy
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def _current_version() -> str:
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def test_current_release_metadata_and_registration_are_atomic():
    version = _current_version()
    assert version

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == version

    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert f'version: "{version}"' in citation

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"**Release line: Elpis{version}**" in readme
    assert f"RELEASE_NOTES/Elpis{version}.md" in readme

    note = ROOT / f"RELEASE_NOTES/Elpis{version}.md"
    assert note.is_file()

    index = (ROOT / "RELEASE_NOTES/README.md").read_text(encoding="utf-8")
    assert f"Current: [`Elpis{version}.md`](Elpis{version}.md)" in index
    assert f"- [`Elpis{version}.md`](Elpis{version}.md)" in index

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.startswith(f"## Elpis{version}")

    ns = runpy.run_path(str(ROOT / "tools/verify_public_release.py"))
    assert ns["RELEASE_VERSION"] == version
    assert version in ns["RELEASE_IDENTITIES"]


def test_current_manifest_and_published_registry_are_truthful_when_present():
    version = _current_version()
    manifest = ROOT / f"manifests/Elpis{version}.RELEASE_MANIFEST.json"

    manifest_sha = None
    if manifest.exists():
        raw = manifest.read_bytes()
        manifest_sha = hashlib.sha256(raw).hexdigest()
        data = json.loads(raw)
        assert data["schema"] in {"elpis.release-manifest.v2", "elpis.release-manifest.v3"}
        assert data["package_name"] == "elpisai"
        assert data["version"] == version
        assert data["release_name"] == f"Elpis{version}"
        assert data["release_tag"] == f"Elpis{version}"
        if data["schema"] == "elpis.release-manifest.v3":
            compact = runpy.run_path(str(ROOT / "tools/release_tree_digest.py"))
            compact["require_successor"](version)
            assert compact["verify_record"](ROOT, manifest.relative_to(ROOT).as_posix(), data) == []
            paths = set(compact["publication_paths"](ROOT, manifest.relative_to(ROOT).as_posix()))
        else:
            paths = {entry["path"] for entry in data["files"]}
        assert "VERSION" in paths
        assert "pyproject.toml" in paths
        assert "CITATION.cff" in paths
        assert "README.md" in paths
        assert "tools/verify_public_release.py" in paths
        assert "tests/test_current_release_hygiene.py" in paths
        assert f"RELEASE_NOTES/Elpis{version}.md" in paths

    registry = json.loads((ROOT / "PUBLISHED_RELEASES.json").read_text(encoding="utf-8"))
    entries = registry["published_releases"]
    versions = [entry["version"] for entry in entries]
    assert len(versions) == len(set(versions))

    current = [entry for entry in entries if entry["version"] == version]
    if current:
        assert len(current) == 1
        assert manifest_sha is not None
        entry = current[0]
        assert entry["release_tag"] == f"Elpis{version}"
        assert entry["manifest_path"] == f"manifests/Elpis{version}.RELEASE_MANIFEST.json"
        assert entry["manifest_sha256"] == manifest_sha


def test_repository_completeness_explicitly_separates_source_only_integrations():
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    source_only_tests = (
        "tests/test_grid81_application_promotion_source_identity.py",
        "tests/test_grid81_promotion_candidate_runtime_integration.py",
        "tests/test_grid81_candidate_publication_runtime_integration.py",
    )
    source_roots = (
        "components/Grid81DeterministicCanonicalPromotionPlanner/src",
        "components/Grid81DeterministicCanonicalPromotionAuthority/src",
        "components/Grid81DeterministicCanonicalCandidateConstructor/src",
        "components/Grid81DeterministicCanonicalPublisher/src",
    )

    assert "Complete installed/root top-level test suite" in ci
    assert "Source-only downstream Grid81 integration tests" in ci
    assert "env -u PYTHONPATH" in ci
    assert 'PYTHONPATH=""\n          python -m pytest -q -p no:cacheprovider tests/' not in ci
    assert 'INSTALL_SRC="$(mktemp -d)"' in ci
    assert 'git archive HEAD | tar -x -C "$INSTALL_SRC"' in ci
    assert 'python -m pip install "$INSTALL_SRC[trm]" pytest==9.0.2' in ci
    assert (
        '      - name: Install repository-completeness dependencies\n'
        '        run: python -m pip install ".[trm]" pytest==9.0.2\n'
        not in ci
    )

    for test in source_only_tests:
        assert f"--ignore={test}" in ci
        assert ci.count(test) >= 2

    for root in source_roots:
        assert root in ci

    assert "Qualify installed assembly from pristine throwaway source copy" in ci
