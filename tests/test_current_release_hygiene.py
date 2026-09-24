from __future__ import annotations

from tools import release_git

import hashlib
import io
import json
from pathlib import Path
import runpy
import subprocess
import tarfile
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]

_FORWARD_LIFECYCLE_MARKERS = (
    "pre-seal",
    "pre-publication",
    "remain separate later gates",
    "remains a separate later gate",
    "remain later gates",
    "remains a later gate",
)


def _published_records() -> list[dict]:
    legacy = json.loads(
        (
            ROOT
            / "PUBLISHED_RELEASES.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    successor = json.loads(
        (
            ROOT
            / "PUBLICATION_ASSERTIONS.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    return [
        *legacy["published_releases"],
        *successor[
            "publication_assertions"
        ],
    ]


def _published_versions() -> set[str]:
    return {
        entry["version"]
        for entry in _published_records()
    }


def _assert_release_note_lifecycle_neutral(text: str) -> None:
    normalized = " ".join(text.lower().split())
    offenders = [
        marker
        for marker in _FORWARD_LIFECYCLE_MARKERS
        if marker in normalized
    ]
    assert not offenders, (
        "RELEASE_NOTE_FORWARD_LIFECYCLE_CLAIM:"
        + ",".join(offenders)
    )


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

    release_section = readme.split("## Release Notes", 1)[1].split("## Install and quick start", 1)[0]
    assert release_section.strip().startswith(f"**Elpis{version}**")

    note = ROOT / f"RELEASE_NOTES/Elpis{version}.md"
    assert note.is_file()
    # Historical published notes are immutable evidence. For every current
    # unpublished successor, the note itself must remain lifecycle-neutral so
    # sealing/tagging/publication cannot make its prose stale.
    if version not in _published_versions():
        _assert_release_note_lifecycle_neutral(
            note.read_text(encoding="utf-8")
        )

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
            manifest_rel = manifest.relative_to(ROOT).as_posix()

            published_current = [
                entry
                for entry in _published_records()
                if entry["version"] == version
            ]

            if published_current:
                assert len(published_current) == 1
                published = published_current[0]
                assert published["manifest_path"] == manifest_rel
                assert published["manifest_sha256"] == manifest_sha
                peeled = published["peeled_commit"]
                assert published["peeled_object_type"] == "commit"

                if (ROOT / ".git").exists():
                    proc = release_git.run(ROOT, "archive", "--format=tar", peeled)
                    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
                    with tempfile.TemporaryDirectory() as td:
                        sealed_root = Path(td)
                        with tarfile.open(
                            fileobj=io.BytesIO(proc.stdout),
                            mode="r:",
                        ) as archive:
                            archive.extractall(sealed_root)
                        sealed_manifest = sealed_root / manifest_rel
                        assert hashlib.sha256(
                            sealed_manifest.read_bytes()
                        ).hexdigest() == manifest_sha
                        assert compact["verify_record"](
                            sealed_root, manifest_rel, data
                        ) == []
                        paths = set(
                            compact["publication_paths"](
                                sealed_root,
                                manifest_rel,
                                policy=data["publication_policy"],
                            )
                        )
                else:
                    paths = set(
                        compact["publication_paths"](
                            ROOT,
                            manifest_rel,
                            policy=data["publication_policy"],
                        )
                    )
            else:
                assert compact["verify_record"](ROOT, manifest_rel, data) == []
                paths = set(
                    compact["publication_paths"](
                        ROOT,
                        manifest_rel,
                        policy=data["publication_policy"],
                    )
                )
        else:
            paths = {entry["path"] for entry in data["files"]}
        assert "VERSION" in paths
        assert "pyproject.toml" in paths
        assert "CITATION.cff" in paths
        assert "README.md" in paths
        assert "tools/verify_public_release.py" in paths
        assert "tests/test_current_release_hygiene.py" in paths
        assert f"RELEASE_NOTES/Elpis{version}.md" in paths

    entries = _published_records()

    versions = [
        entry["version"]
        for entry in entries
    ]

    tags = [
        entry["release_tag"]
        for entry in entries
    ]

    assert len(versions) == len(
        set(versions)
    )
    assert len(tags) == len(
        set(tags)
    )

    current = [
        entry
        for entry in entries
        if entry["version"] == version
    ]

    if current:
        assert len(current) == 1
        assert manifest_sha is not None

        entry = current[0]

        assert (
            entry["release_tag"]
            == f"Elpis{version}"
        )

        assert (
            entry["manifest_path"]
            == (
                f"manifests/"
                f"Elpis{version}."
                f"RELEASE_MANIFEST.json"
            )
        )

        assert (
            entry["manifest_sha256"]
            == manifest_sha
        )


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
    assert 'python tools/release_git_cli.py archive HEAD | tar -x -C "$INSTALL_SRC"' in ci
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

def test_release_note_lifecycle_guard_rejects_forward_state_claims():
    for phrase in (
        "This is a pre-seal successor candidate.",
        "This is a pre-publication candidate.",
        "Manifest sealing and tag creation remain separate later gates.",
        "Publication remains a later gate.",
    ):
        try:
            _assert_release_note_lifecycle_neutral(
                "# Release\n\n" + phrase + "\n"
            )
        except AssertionError as exc:
            assert "RELEASE_NOTE_FORWARD_LIFECYCLE_CLAIM" in str(exc)
        else:
            raise AssertionError(
                f"forward lifecycle phrase unexpectedly accepted: {phrase}"
            )


def test_release_note_lifecycle_guard_accepts_lifecycle_neutral_text():
    _assert_release_note_lifecycle_neutral(
        "# ElpisX\n\n"
        "This release records qualified corrective behavior and its "
        "sealed technical scope.\n"
    )


def test_base_install_no_torch_ci_contract_is_exact():
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    start = ci.index("  base-install-no-torch:\n")
    end = ci.index("\n  canonical-projector-release:\n", start)
    job = ci[start:end]

    assert "name: Base install without optional Torch" in job
    assert "python -m venv /tmp/elpis-base-no-torch" in job
    assert "/tmp/elpis-base-no-torch/bin/python -m pip install . pytest==9.0.2" in job
    assert "[trm]" not in job
    assert 'find_spec("torch") is None' in job
    assert "tests/test_optional_torch_collection_contract.py" in job
    assert "tests/test_p0_validator_ingress.py" in job
    assert "tests/test_projector_release_adapter.py" in job
    assert "tests/test_direct_semantic_replay.py" in job
    assert 'grep -F "21 passed, 9 skipped"' in job
    assert "tests/test_feedback_refinement.py" in job
    assert 'grep -F "1 passed, 1 skipped"' in job
    assert "-o addopts=" in job
