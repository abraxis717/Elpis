from __future__ import annotations
from tools import release_git

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/refresh_published_releases.py"
REGISTRY = ROOT / "PUBLISHED_RELEASES.json"
FAILED_RELEASES = ROOT / "FAILED_RELEASES.json"


def _git(root: Path, *args: str) -> str:
    proc = release_git.run(
        root,
        *args,
        text=True,
    )
    proc.check_returncode()
    return proc.stdout.strip()


def _run_tool(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(TOOL), "--root", str(root), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _repository_is_shallow() -> bool:
    return _git(ROOT, "rev-parse", "--is-shallow-repository") == "true"


def _require_complete_history(*, shallow: bool | None = None) -> None:
    if shallow is None:
        shallow = _repository_is_shallow()
    if shallow:
        raise AssertionError(
            "REPOSITORY_HISTORY_INCOMPLETE: published release registry "
            "qualification requires complete Git history"
        )


def _fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "published-registry-test")
    _git(repo, "config", "user.email", "test@example.invalid")
    (repo / "manifests").mkdir()
    (repo / "FAILED_RELEASES.json").write_text(
        json.dumps({"failed_releases": [], "schema": "elpis.failed-releases.v1"}, indent=2) + "\n",
        encoding="utf-8",
    )
    (repo / "PUBLISHED_RELEASES.json").write_text(
        json.dumps({
            "published_releases": [],
            "schema": "elpis.published-releases.v1",
            "source_of_truth": "refs/tags/Elpis<semver>",
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "seed")
    return repo


def _add_release_tag(repo: Path, version: str) -> tuple[str, str]:
    tag = f"Elpis{version}"
    manifest_rel = Path("manifests") / f"{tag}.RELEASE_MANIFEST.json"
    manifest = repo / manifest_rel
    manifest.write_text(
        json.dumps({"release_tag": tag, "version": version}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _git(repo, "add", manifest_rel.as_posix())
    _git(repo, "commit", "-qm", f"seal {tag}")
    commit = _git(repo, "rev-parse", "HEAD")
    _git(repo, "tag", "-a", tag, "-m", tag)
    return commit, hashlib.sha256(manifest.read_bytes()).hexdigest()


def _entry(repo: Path, version: str, commit: str, manifest_sha: str) -> dict:
    tag = f"Elpis{version}"
    return {
        "manifest_path": f"manifests/{tag}.RELEASE_MANIFEST.json",
        "manifest_sha256": manifest_sha,
        "peeled_commit": commit,
        "release_tag": tag,
        "version": version,
    }


def _write_registry(repo: Path, records: list[dict]) -> None:
    (repo / "PUBLISHED_RELEASES.json").write_text(
        json.dumps({
            "published_releases": records,
            "schema": "elpis.published-releases.v1",
            "source_of_truth": "refs/tags/Elpis<semver>",
        }, indent=2) + "\n",
        encoding="utf-8",
    )


def test_repository_published_registry_validates_explicit_assertions():
    _require_complete_history()
    proc = _run_tool(ROOT, "--check")
    assert proc.returncode == 0, proc.stdout + proc.stderr

    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    entries = data["published_releases"]
    versions = [entry["version"] for entry in entries]
    tags = [entry["release_tag"] for entry in entries]
    assert len(versions) == len(set(versions))
    assert len(tags) == len(set(tags))

    failed = {
        item["release_tag"]
        for item in json.loads(FAILED_RELEASES.read_text(encoding="utf-8"))["failed_releases"]
    }
    for entry in entries:
        tag = entry["release_tag"]
        assert tag not in failed
        assert entry["version"] == tag.removeprefix("Elpis")
        assert entry["peeled_commit"] == _git(ROOT, "rev-parse", f"refs/tags/{tag}^{{}}")
        manifest = ROOT / entry["manifest_path"]
        assert manifest.is_file()
        assert hashlib.sha256(manifest.read_bytes()).hexdigest() == entry["manifest_sha256"]


def test_current_tagged_but_unpublished_state_is_valid_when_present():
    _require_complete_history()
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    tag = f"Elpis{version}"
    published = {
        item["release_tag"]
        for item in json.loads(REGISTRY.read_text(encoding="utf-8"))["published_releases"]
    }
    failed = {
        item["release_tag"]
        for item in json.loads(FAILED_RELEASES.read_text(encoding="utf-8"))["failed_releases"]
    }
    exists = release_git.run(
        ROOT,
        "show-ref",
        "--verify",
        "--quiet",
        f"refs/tags/{tag}",
    ).returncode == 0
    if exists and tag not in published and tag not in failed:
        proc = _run_tool(ROOT, "--check")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert tag not in published


def test_semantic_tag_without_publication_assertion_is_valid(tmp_path: Path):
    repo = _fixture_repo(tmp_path)
    _add_release_tag(repo, "9.9.9")
    proc = _run_tool(repo, "--check")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_legacy_v1_append_surface_is_frozen(
    tmp_path: Path,
):
    repo = _fixture_repo(tmp_path)

    _add_release_tag(repo, "9.9.9")

    before = (
        repo / "PUBLISHED_RELEASES.json"
    ).read_bytes()

    proc = _run_tool(
        repo,
        "--append-tag",
        "Elpis9.9.9",
    )

    assert proc.returncode != 0
    assert (
        "LEGACY_PUBLISHED_REGISTRY_FROZEN_"
        "USE_PUBLICATION_ASSERTIONS_V2"
        in proc.stdout
    )

    assert (
        repo / "PUBLISHED_RELEASES.json"
    ).read_bytes() == before

    assert (
        _run_tool(repo, "--check").returncode
        == 0
    )


def test_legacy_v1_append_is_frozen_even_for_failed_tag(
    tmp_path: Path,
):
    repo = _fixture_repo(tmp_path)

    commit, digest = _add_release_tag(
        repo,
        "9.9.9",
    )

    failed = {
        "failed_releases": [
            {
                "disposition":
                    "SEALED_TAGGED_CI_FAILED_NOT_PUBLISHED",
                "failure_classes": [
                    "TEST_FAILURE"
                ],
                "manifest_path":
                    "manifests/"
                    "Elpis9.9.9.RELEASE_MANIFEST.json",
                "manifest_sha256": digest,
                "peeled_commit": commit,
                "release_tag": "Elpis9.9.9",
                "tag_object": _git(
                    repo,
                    "rev-parse",
                    "Elpis9.9.9^{tag}",
                ),
                "version": "9.9.9",
            }
        ],
        "schema": "elpis.failed-releases.v1",
    }

    (
        repo / "FAILED_RELEASES.json"
    ).write_text(
        json.dumps(failed, indent=2) + "\n",
        encoding="utf-8",
    )

    proc = _run_tool(
        repo,
        "--append-tag",
        "Elpis9.9.9",
    )

    assert proc.returncode != 0
    assert (
        "LEGACY_PUBLISHED_REGISTRY_FROZEN_"
        "USE_PUBLICATION_ASSERTIONS_V2"
        in proc.stdout
    )

def test_duplicate_published_tag_or_version_is_rejected(tmp_path: Path):
    repo = _fixture_repo(tmp_path)
    commit, digest = _add_release_tag(repo, "9.9.9")
    item = _entry(repo, "9.9.9", commit, digest)
    _write_registry(repo, [item, dict(item)])
    proc = _run_tool(repo, "--check")
    assert proc.returncode != 0
    assert "PUBLISHED_RELEASE_DUPLICATE" in proc.stdout


def test_manifest_hash_tamper_is_rejected(tmp_path: Path):
    repo = _fixture_repo(tmp_path)
    commit, digest = _add_release_tag(repo, "9.9.9")
    item = _entry(repo, "9.9.9", commit, digest)
    item["manifest_sha256"] = "0" * 64
    _write_registry(repo, [item])
    proc = _run_tool(repo, "--check")
    assert proc.returncode != 0
    assert "PUBLISHED_MANIFEST_SHA256_MISMATCH" in proc.stdout


def test_peeled_commit_tamper_is_rejected(tmp_path: Path):
    repo = _fixture_repo(tmp_path)
    commit, digest = _add_release_tag(repo, "9.9.9")
    item = _entry(repo, "9.9.9", commit, digest)
    item["peeled_commit"] = "0" * len(commit)
    _write_registry(repo, [item])
    proc = _run_tool(repo, "--check")
    assert proc.returncode != 0
    assert "PUBLISHED_PEELED_COMMIT_MISMATCH" in proc.stdout


def test_manifest_path_version_tag_incoherence_is_rejected(tmp_path: Path):
    repo = _fixture_repo(tmp_path)
    commit, digest = _add_release_tag(repo, "9.9.9")
    item = _entry(repo, "9.9.9", commit, digest)
    item["manifest_path"] = "manifests/Elpis9.9.8.RELEASE_MANIFEST.json"
    _write_registry(repo, [item])
    proc = _run_tool(repo, "--check")
    assert proc.returncode != 0
    assert "PUBLISHED_MANIFEST_PATH_MISMATCH" in proc.stdout


def test_published_record_for_failed_tag_is_rejected(tmp_path: Path):
    repo = _fixture_repo(tmp_path)
    commit, digest = _add_release_tag(repo, "9.9.9")
    item = _entry(repo, "9.9.9", commit, digest)
    _write_registry(repo, [item])
    failed = {
        "failed_releases": [{
            "disposition": "SEALED_TAGGED_CI_FAILED_NOT_PUBLISHED",
            "failure_classes": ["TEST_FAILURE"],
            "manifest_path": item["manifest_path"],
            "manifest_sha256": digest,
            "peeled_commit": commit,
            "release_tag": "Elpis9.9.9",
            "tag_object": _git(repo, "rev-parse", "Elpis9.9.9^{tag}"),
            "version": "9.9.9",
        }],
        "schema": "elpis.failed-releases.v1",
    }
    (repo / "FAILED_RELEASES.json").write_text(json.dumps(failed, indent=2) + "\n", encoding="utf-8")
    proc = _run_tool(repo, "--check")
    assert proc.returncode != 0
    assert "PUBLISHED_RELEASE_IS_FAILED" in proc.stdout


def test_missing_published_tag_is_rejected(tmp_path: Path):
    repo = _fixture_repo(tmp_path)
    commit, digest = _add_release_tag(repo, "9.9.9")
    item = _entry(repo, "9.9.9", commit, digest)
    _write_registry(repo, [item])
    _git(repo, "tag", "-d", "Elpis9.9.9")
    proc = _run_tool(repo, "--check")
    assert proc.returncode != 0
    assert "PUBLISHED_RELEASE_TAG_MISSING" in proc.stdout


def test_non_monotonic_registry_order_is_rejected(tmp_path: Path):
    repo = _fixture_repo(tmp_path)
    c1, d1 = _add_release_tag(repo, "9.9.8")
    c2, d2 = _add_release_tag(repo, "9.9.9")
    _write_registry(repo, [_entry(repo, "9.9.9", c2, d2), _entry(repo, "9.9.8", c1, d1)])
    proc = _run_tool(repo, "--check")
    assert proc.returncode != 0
    assert "PUBLISHED_RELEASE_ORDER_INVALID" in proc.stdout


def test_shallow_history_failure_is_explicit() -> None:
    with pytest.raises(AssertionError, match="REPOSITORY_HISTORY_INCOMPLETE"):
        _require_complete_history(shallow=True)


def test_failed_release_2_2_18_is_bound_to_distinct_publication_authority_failure():
    _require_complete_history()
    payload = json.loads(FAILED_RELEASES.read_text(encoding="utf-8"))
    entries = {item["release_tag"]: item for item in payload["failed_releases"]}
    item = entries["Elpis2.2.18"]
    assert item["version"] == "2.2.18"
    assert item["disposition"] == "SEALED_TAGGED_CI_FAILED_NOT_PUBLISHED"
    assert item["tag_object"] == "beb4cd6131c6a1c072fc427de3f26c8e0e10b980"
    assert item["peeled_commit"] == "0a32fc5ee7d2e34487150fd39f432b1993d47c22"
    assert item["manifest_sha256"] == "b7ad8112d01ea102f44cf06ec1064d296e1657b07d5c5113c06c9d5dbbdfd95b"
    assert item["failure_classes"] == [
        "PREPUBLICATION_TAG_CONFLATED_WITH_PUBLISHED_RELEASE_AUTHORITY",
        "PUBLISHED_RELEASE_TAG_PROJECTION_REJECTED_TAGGED_UNPUBLISHED_STATE",
    ]
    assert _git(ROOT, "rev-parse", "Elpis2.2.18^{tag}") == item["tag_object"]
    assert _git(ROOT, "rev-parse", "Elpis2.2.18^{}") == item["peeled_commit"]
