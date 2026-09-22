from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "publication_assertions_v2.py"
SPEC = importlib.util.spec_from_file_location("pubv2", TOOL)
pubv2 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(pubv2)


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def run_tool(repo: Path, *args: str):
    return subprocess.run(
        [sys.executable, str(TOOL), "--root", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def seed(repo: Path) -> None:
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "pubv2-test")
    git(repo, "config", "user.email", "test@example.invalid")
    (repo / "manifests").mkdir()
    (repo / "PUBLISHED_RELEASES.json").write_text(
        json.dumps(
            {
                "published_releases": [],
                "schema": "elpis.published-releases.v1",
                "source_of_truth": "refs/tags/Elpis<semver>",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (repo / "FAILED_RELEASES.json").write_text(
        json.dumps(
            {"failed_releases": [], "schema": "elpis.failed-releases.v1"},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "seed")


def add_release(repo: Path, version: str, *, annotated: bool = True) -> tuple[str, str]:
    tag = f"Elpis{version}"
    manifest = repo / "manifests" / f"{tag}.RELEASE_MANIFEST.json"
    manifest.write_text(
        json.dumps(
            {"release_name": tag, "release_tag": tag, "version": version},
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    git(repo, "add", str(manifest.relative_to(repo)))
    git(repo, "commit", "-qm", f"seal {tag}")
    commit = git(repo, "rev-parse", "HEAD")
    if annotated:
        git(repo, "tag", "-a", tag, "-m", tag)
    else:
        git(repo, "tag", tag)
    return tag, commit


def receipt(tag: str, commit: str, base: int = 1000) -> dict:
    version = tag.removeprefix("Elpis")
    action_specs = pubv2.required_actions(tag)
    actions = {}
    for offset, (name, (workflow, event)) in enumerate(action_specs.items()):
        actions[name] = {
            "conclusion": "success",
            "event": event,
            "head_sha": commit,
            "run_id": base + offset,
            "workflow": workflow,
        }
    return {
        "release_tag": tag,
        "github_release": {
            "published_at": "2026-09-18T15:56:03Z",
            "release_id": base + 100,
            "repository": "abraxis717/Elpis",
            "tag_name": tag,
        },
        "github_actions": actions,
        "pypi": {
            "project": "elpisai",
            "version": version,
            "files": [
                {
                    "filename": f"elpisai-{version}-py3-none-any.whl",
                    "packagetype": "bdist_wheel",
                    "sha256": "1" * 64,
                    "upload_time_iso_8601": "2026-09-18T18:00:00Z",
                    "yanked": False,
                },
                {
                    "filename": f"elpisai-{version}.tar.gz",
                    "packagetype": "sdist",
                    "sha256": "2" * 64,
                    "upload_time_iso_8601": "2026-09-18T18:00:01Z",
                    "yanked": False,
                },
            ],
        },
    }


def write_receipt(repo: Path, value: dict, name: str = "receipt.json") -> Path:
    p = repo / name
    p.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return p



def test_227_historical_receipt_does_not_require_native(tmp_path: Path):
    repo = tmp_path / "repo"
    seed(repo)
    tag, commit = add_release(repo, "2.2.27")
    r = receipt(tag, commit)
    assert "tag_inference_native" not in r["github_actions"]
    rec = write_receipt(repo, r)
    proc = run_tool(repo, "--append-receipt", str(rec))
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_228_successor_receipt_requires_native(tmp_path: Path):
    repo = tmp_path / "repo"
    seed(repo)
    tag, commit = add_release(repo, "2.2.28")
    r = receipt(tag, commit)
    assert "tag_inference_native" in r["github_actions"]
    del r["github_actions"]["tag_inference_native"]
    rec = write_receipt(repo, r)
    proc = run_tool(repo, "--append-receipt", str(rec))
    assert proc.returncode != 0
    assert "GITHUB_ACTION_WITNESS_SET_INVALID" in proc.stdout


def test_append_binds_annotated_tag_commit_and_tagged_manifest(tmp_path: Path):
    repo = tmp_path / "repo"
    seed(repo)
    tag, commit = add_release(repo, "9.9.9")
    rec = write_receipt(repo, receipt(tag, commit))
    proc = run_tool(repo, "--append-receipt", str(rec))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    data = json.loads((repo / "PUBLICATION_ASSERTIONS.json").read_text())
    item = data["publication_assertions"][0]
    assert item["tag_object_type"] == "tag"
    assert item["peeled_object_type"] == "commit"
    assert item["peeled_commit"] == commit
    assert item["tag_object"] == git(repo, "rev-parse", tag)
    tagged = subprocess.check_output(
        ["git", "show", f"{commit}:manifests/{tag}.RELEASE_MANIFEST.json"], cwd=repo
    )
    import hashlib
    assert item["manifest_sha256"] == hashlib.sha256(tagged).hexdigest()
    assert run_tool(repo, "--check").returncode == 0


def test_lightweight_tag_is_rejected(tmp_path: Path):
    repo = tmp_path / "repo"
    seed(repo)
    tag, commit = add_release(repo, "9.9.9", annotated=False)
    rec = write_receipt(repo, receipt(tag, commit))
    proc = run_tool(repo, "--append-receipt", str(rec))
    assert proc.returncode != 0
    assert "ANNOTATED_TAG_REQUIRED" in proc.stdout


def test_checkout_manifest_must_equal_tagged_bytes(tmp_path: Path):
    repo = tmp_path / "repo"
    seed(repo)
    tag, commit = add_release(repo, "9.9.9")
    manifest = repo / "manifests" / f"{tag}.RELEASE_MANIFEST.json"
    manifest.write_text(manifest.read_text() + " ", encoding="utf-8")
    rec = write_receipt(repo, receipt(tag, commit))
    proc = run_tool(repo, "--append-receipt", str(rec))
    assert proc.returncode != 0
    assert "CHECKOUT_MANIFEST_DIFFERS_FROM_TAGGED_BYTES" in proc.stdout


def test_record_rejects_tag_object_substitution_even_same_commit(tmp_path: Path):
    repo = tmp_path / "repo"
    seed(repo)
    tag, commit = add_release(repo, "9.9.9")
    rec = write_receipt(repo, receipt(tag, commit))
    assert run_tool(repo, "--append-receipt", str(rec)).returncode == 0
    git(repo, "tag", "-d", tag)
    git(repo, "tag", "-a", tag, "-m", "replacement", commit)
    proc = run_tool(repo, "--check")
    assert proc.returncode != 0
    assert "PUBLICATION_TAG_OBJECT_MISMATCH" in proc.stdout


def test_legacy_v1_bytes_are_frozen_by_v2_header(tmp_path: Path):
    repo = tmp_path / "repo"
    seed(repo)
    tag, commit = add_release(repo, "9.9.9")
    rec = write_receipt(repo, receipt(tag, commit))
    assert run_tool(repo, "--append-receipt", str(rec)).returncode == 0
    legacy = repo / "PUBLISHED_RELEASES.json"
    payload = json.loads(legacy.read_text())
    payload["note"] = "tamper"
    legacy.write_text(json.dumps(payload) + "\n")
    proc = run_tool(repo, "--check")
    assert proc.returncode != 0
    assert "LEGACY_PUBLICATION_HISTORY_IDENTITY_MISMATCH" in proc.stdout


def test_action_witness_must_bind_release_commit(tmp_path: Path):
    repo = tmp_path / "repo"
    seed(repo)
    tag, commit = add_release(repo, "9.9.9")
    r = receipt(tag, commit)
    r["github_actions"]["tag_ci"]["head_sha"] = "0" * 40
    rec = write_receipt(repo, r)
    proc = run_tool(repo, "--append-receipt", str(rec))
    assert proc.returncode != 0
    assert "ACTION_HEAD_SHA_MISMATCH:tag_ci" in proc.stdout


def test_duplicate_action_ids_are_rejected(tmp_path: Path):
    repo = tmp_path / "repo"
    seed(repo)
    tag, commit = add_release(repo, "9.9.9")
    r = receipt(tag, commit)
    r["github_actions"]["pypi_publish"]["run_id"] = r["github_actions"]["release_event_ci"]["run_id"]
    rec = write_receipt(repo, r)
    proc = run_tool(repo, "--append-receipt", str(rec))
    assert proc.returncode != 0
    assert "GITHUB_ACTION_RUN_ID_DUPLICATE" in proc.stdout


def test_pypi_requires_exact_wheel_and_sdist(tmp_path: Path):
    repo = tmp_path / "repo"
    seed(repo)
    tag, commit = add_release(repo, "9.9.9")
    r = receipt(tag, commit)
    r["pypi"]["files"][1]["packagetype"] = "bdist_wheel"
    rec = write_receipt(repo, r)
    proc = run_tool(repo, "--append-receipt", str(rec))
    assert proc.returncode != 0
    assert "PYPI_EXPECTED_WHEEL_AND_SDIST_TYPES" in proc.stdout


def test_failed_release_cannot_be_asserted_published(tmp_path: Path):
    repo = tmp_path / "repo"
    seed(repo)
    tag, commit = add_release(repo, "9.9.9")
    (repo / "FAILED_RELEASES.json").write_text(
        json.dumps(
            {
                "schema": "elpis.failed-releases.v1",
                "failed_releases": [{"release_tag": tag}],
            }
        )
        + "\n"
    )
    rec = write_receipt(repo, receipt(tag, commit))
    proc = run_tool(repo, "--append-receipt", str(rec))
    assert proc.returncode != 0
    assert "PUBLICATION_ASSERTION_IS_FAILED" in proc.stdout


def test_duplicate_append_is_rejected(tmp_path: Path):
    repo = tmp_path / "repo"
    seed(repo)
    tag, commit = add_release(repo, "9.9.9")
    rec = write_receipt(repo, receipt(tag, commit))
    assert run_tool(repo, "--append-receipt", str(rec)).returncode == 0
    proc = run_tool(repo, "--append-receipt", str(rec))
    assert proc.returncode != 0
    assert "PUBLICATION_ASSERTION_DUPLICATE_TAG" in proc.stdout


def test_two_concurrent_same_tag_appends_have_one_winner(tmp_path: Path):
    if os.name == "nt":
        pytest.skip("POSIX concurrency witness")
    repo = tmp_path / "repo"
    seed(repo)
    tag, commit = add_release(repo, "9.9.9")
    rec = write_receipt(repo, receipt(tag, commit))
    cmd = [sys.executable, str(TOOL), "--root", str(repo), "--append-receipt", str(rec)]
    p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    p2 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    o1, e1 = p1.communicate(timeout=20)
    o2, e2 = p2.communicate(timeout=20)
    assert sorted([p1.returncode, p2.returncode]) == [0, 1], (o1, e1, o2, e2)
    assert run_tool(repo, "--check").returncode == 0
    data = json.loads((repo / "PUBLICATION_ASSERTIONS.json").read_text())
    assert len(data["publication_assertions"]) == 1


def test_atomic_replace_failure_preserves_old_bytes(tmp_path: Path, monkeypatch):
    path = tmp_path / "registry.json"
    path.write_bytes(b"old\n")

    def boom(src, dst):
        raise OSError("simulated rename crash")

    monkeypatch.setattr(pubv2.os, "replace", boom)
    with pytest.raises(OSError, match="simulated rename crash"):
        pubv2._atomic_replace(path, b"new\n")
    assert path.read_bytes() == b"old\n"


def test_receipt_does_not_infer_publication_from_tag_alone(tmp_path: Path):
    repo = tmp_path / "repo"
    seed(repo)
    add_release(repo, "9.9.9")
    proc = run_tool(repo, "--check")
    assert proc.returncode != 0
    assert "PUBLICATION_ASSERTIONS_MISSING" in proc.stdout


def test_manifest_hash_is_not_taken_from_dirty_worktree(tmp_path: Path):
    repo = tmp_path / "repo"
    seed(repo)
    tag, commit = add_release(repo, "9.9.9")
    clean_bytes = (repo / "manifests" / f"{tag}.RELEASE_MANIFEST.json").read_bytes()
    (repo / "manifests" / f"{tag}.RELEASE_MANIFEST.json").write_bytes(clean_bytes + b"\n")
    r = write_receipt(repo, receipt(tag, commit))
    proc = run_tool(repo, "--append-receipt", str(r))
    assert proc.returncode != 0
    assert not (repo / "PUBLICATION_ASSERTIONS.json").exists()


def test_observation_receipt_is_assertion_not_online_reverification(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    seed(repo)
    tag, commit = add_release(repo, "9.9.9")
    rec = write_receipt(repo, receipt(tag, commit))
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:1")
    monkeypatch.setenv("https_proxy", "http://127.0.0.1:1")
    proc = run_tool(repo, "--append-receipt", str(rec))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert run_tool(repo, "--check").returncode == 0


def test_v2_cannot_duplicate_legacy_published_version(tmp_path: Path):
    repo = tmp_path / "repo"
    seed(repo)
    tag, commit = add_release(repo, "9.9.9")
    legacy = json.loads((repo / "PUBLISHED_RELEASES.json").read_text())
    legacy["published_releases"].append({
        "manifest_path": f"manifests/{tag}.RELEASE_MANIFEST.json",
        "manifest_sha256": "0" * 64,
        "peeled_commit": commit,
        "release_tag": tag,
        "version": "9.9.9",
    })
    (repo / "PUBLISHED_RELEASES.json").write_text(json.dumps(legacy, indent=2) + "\n")
    rec = write_receipt(repo, receipt(tag, commit))
    proc = run_tool(repo, "--append-receipt", str(rec))
    assert proc.returncode != 0
    assert "PUBLICATION_ASSERTION_DUPLICATES_LEGACY" in proc.stdout


def test_gitless_export_validates_structural_publication_authority(
    tmp_path: Path,
):
    repo = tmp_path / "repo"
    seed(repo)

    tag, commit = add_release(repo, "9.9.9")
    rec = write_receipt(
        repo,
        receipt(tag, commit),
    )

    assert (
        run_tool(
            repo,
            "--append-receipt",
            str(rec),
        ).returncode
        == 0
    )

    export = tmp_path / "export"

    shutil.copytree(
        repo,
        export,
        ignore=shutil.ignore_patterns(".git"),
    )

    proc = run_tool(
        export,
        "--check-gitless",
    )

    assert proc.returncode == 0, (
        proc.stdout + proc.stderr
    )
    assert "mode=gitless-structural" in proc.stdout


def test_gitless_export_rejects_forged_successor_append(
    tmp_path: Path,
):
    repo = tmp_path / "repo"
    seed(repo)

    tag, commit = add_release(repo, "9.9.9")
    rec = write_receipt(
        repo,
        receipt(tag, commit),
    )

    assert (
        run_tool(
            repo,
            "--append-receipt",
            str(rec),
        ).returncode
        == 0
    )

    export = tmp_path / "export"

    shutil.copytree(
        repo,
        export,
        ignore=shutil.ignore_patterns(".git"),
    )

    registry = export / "PUBLICATION_ASSERTIONS.json"

    payload = json.loads(
        registry.read_text(encoding="utf-8")
    )

    forged = json.loads(
        json.dumps(
            payload["publication_assertions"][0]
        )
    )

    forged["release_tag"] = "Elpis10.0.0"
    forged["version"] = "10.0.0"
    forged["manifest_path"] = (
        "manifests/"
        "Elpis10.0.0.RELEASE_MANIFEST.json"
    )
    forged["github_release"]["tag_name"] = (
        "Elpis10.0.0"
    )
    forged["pypi"]["version"] = "10.0.0"

    payload["publication_assertions"].append(
        forged
    )

    registry.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )

    proc = run_tool(
        export,
        "--check-gitless",
    )

    assert proc.returncode != 0
    assert (
        "PUBLICATION_MANIFEST_MISSING:"
        "Elpis10.0.0"
        in proc.stdout
    )


def test_gitless_export_rejects_annotated_tag_type_claim_tamper(
    tmp_path: Path,
):
    repo = tmp_path / "repo"
    seed(repo)

    tag, commit = add_release(repo, "9.9.9")
    rec = write_receipt(
        repo,
        receipt(tag, commit),
    )

    assert (
        run_tool(
            repo,
            "--append-receipt",
            str(rec),
        ).returncode
        == 0
    )

    export = tmp_path / "export"

    shutil.copytree(
        repo,
        export,
        ignore=shutil.ignore_patterns(".git"),
    )

    registry = export / "PUBLICATION_ASSERTIONS.json"

    payload = json.loads(
        registry.read_text(encoding="utf-8")
    )

    payload[
        "publication_assertions"
    ][0]["tag_object_type"] = "commit"

    registry.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )

    proc = run_tool(
        export,
        "--check-gitless",
    )

    assert proc.returncode != 0
    assert (
        "PUBLICATION_TAG_OBJECT_TYPE_FIELD_INVALID:"
        "Elpis9.9.9"
        in proc.stdout
    )
