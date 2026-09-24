"""Exercise the real postpublication qualification branches before publication.

Only temporary repositories are mutated. Verification observers check the
extracted archive payload, independently of the live fixture's different bytes.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

from tools import release_git

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.2.31"
MANIFEST = f"manifests/Elpis{VERSION}.RELEASE_MANIFEST.json"
MARKER = b"qualified seal bytes\x00\xff\n"


def load_test(name):
    spec = importlib.util.spec_from_file_location("branch_" + name, ROOT / "tests" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_git(root, *args):
    proc = release_git.run(root, *args)
    proc.check_returncode()
    return proc.stdout.strip()


@pytest.mark.parametrize("branch", ["hygiene", "sealed_control"])
@pytest.mark.parametrize("outcome", ["success", "git_failure", "wrong_payload"])
def test_published_archive_authority(tmp_path, monkeypatch, branch, outcome):
    root = tmp_path / "published"
    root.mkdir()
    fixture_git(root, "init", "-q")
    fixture_git(root, "config", "user.name", "Qualification Fixture")
    fixture_git(root, "config", "user.email", "fixture@example.invalid")
    fixture_git(root, "config", "commit.gpgsign", "false")
    paths = {
        "VERSION", "pyproject.toml", "CITATION.cff", "README.md",
        "tools/verify_public_release.py", "tests/test_current_release_hygiene.py",
        f"RELEASE_NOTES/Elpis{VERSION}.md", "payload.bin",
    }
    for rel in paths:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(MARKER if rel == "payload.bin" else b"fixture\n")
    (root / "VERSION").write_text(VERSION + "\n")
    manifest = root / MANIFEST
    manifest.parent.mkdir()
    manifest.write_text(json.dumps({
        "schema": "elpis.release-manifest.v3", "package_name": "elpisai",
        "version": VERSION, "release_name": "Elpis" + VERSION,
        "release_tag": "Elpis" + VERSION, "publication_policy": "fixture",
    }))
    raw_manifest = manifest.read_bytes()
    fixture_git(root, "add", ".")
    fixture_git(root, "commit", "-qm", "qualified candidate")
    candidate = fixture_git(root, "rev-parse", "HEAD").decode()
    expected_archive = release_git.run(root, "archive", "--format=tar", candidate).stdout
    (root / "payload.bin").write_bytes(b"different replacement and live bytes\n")
    fixture_git(root, "add", ".")
    fixture_git(root, "commit", "-qm", "replacement fixture")
    replacement = fixture_git(root, "rev-parse", "HEAD").decode()
    wrong_archive = release_git.run(root, "archive", "--format=tar", replacement).stdout
    fixture_git(root, "replace", candidate, replacement)
    assert fixture_git(root, "rev-parse", "refs/replace/" + candidate).decode() == replacement
    published = {
        "version": VERSION, "release_tag": "Elpis" + VERSION,
        "manifest_path": MANIFEST, "manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(),
        "peeled_commit": candidate, "peeled_object_type": "commit",
    }
    (root / "PUBLISHED_RELEASES.json").write_text(json.dumps({"published_releases": []}))
    (root / "PUBLICATION_ASSERTIONS.json").write_text(json.dumps({"publication_assertions": [published]}))

    decoy = tmp_path / "decoy"
    decoy.mkdir()
    fixture_git(decoy, "init", "-q")
    for key, value in {
        "GIT_DIR": str(decoy / ".git"), "GIT_WORK_TREE": str(decoy),
        "GIT_INDEX_FILE": str(decoy / ".git/index"),
        "GIT_OBJECT_DIRECTORY": str(decoy / ".git/objects"),
        "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(decoy / ".git/objects"),
        "GIT_REPLACE_REF_BASE": "refs/review-unused/", "GIT_SHALLOW_FILE": str(decoy / "missing"),
        "GIT_GRAFT_FILE": str(decoy / "missing"), "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "core.bare", "GIT_CONFIG_VALUE_0": "true",
    }.items():
        monkeypatch.setenv(key, value)

    calls = []
    verified = []
    real_run = release_git.run

    def archive_read(observed_root, *args, **kwargs):
        assert observed_root == root
        assert args == ("archive", "--format=tar", candidate)
        proc = real_run(observed_root, *args, **kwargs)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout == expected_archive
        calls.append(proc.stdout)
        if outcome == "git_failure":
            return subprocess.CompletedProcess(proc.args, 128, b"", b"fixture archive failure")
        if outcome == "wrong_payload":
            return subprocess.CompletedProcess(proc.args, 0, wrong_archive, b"")
        return proc

    def verify_extracted(extracted):
        assert extracted != root
        assert (extracted / MANIFEST).read_bytes() == raw_manifest
        assert (extracted / "payload.bin").read_bytes() == MARKER, "archive payload mismatch"
        verified.append(extracted)

    monkeypatch.setattr(release_git, "run", archive_read)
    if branch == "hygiene":
        module = load_test("test_current_release_hygiene")
        monkeypatch.setattr(module, "ROOT", root)

        def verify_record(extracted, rel, data):
            assert rel == MANIFEST
            verify_extracted(extracted)
            return []

        monkeypatch.setattr(module.runpy, "run_path", lambda path: {
            "require_successor": lambda version: None,
            "verify_record": verify_record,
            "publication_paths": lambda *args, **kwargs: paths,
        })
        invoke = module.test_current_manifest_and_published_registry_are_truthful_when_present
    else:
        module = load_test("test_seal_release_mutations")
        monkeypatch.setattr(module, "REPO", root)

        def verifier(extracted, *args):
            verify_extracted(extracted)
            return subprocess.CompletedProcess(args, 0, "PASS", "")

        monkeypatch.setattr(module, "run", verifier)
        destination = tmp_path / "extracted"
        destination.mkdir()
        invoke = lambda: module.test_real_sealed_tree_verifies_without_reseal(destination)
    if outcome == "success":
        invoke()
        assert len(verified) == 1
    else:
        diagnostic = "fixture archive failure" if outcome == "git_failure" else "archive payload mismatch"
        with pytest.raises(AssertionError, match=diagnostic):
            invoke()
        assert not verified
    assert calls == [expected_archive]
